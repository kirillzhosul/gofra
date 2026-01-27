from collections.abc import (
    Callable,
    Generator,
    Mapping,
    MutableMapping,
    MutableSequence,
    Sequence,
)
from typing import IO, Literal, assert_never

from libgofra.codegen.backends.general import CODEGEN_GOFRA_CONTEXT_LABEL
from libgofra.codegen.backends.wasm32.memory import (
    wasm_pack_integer_to_memory,
    wasm_pack_string_view_to_memory,
)
from libgofra.codegen.backends.wasm32.sexpr import (
    BlockLoopNode,
    BlockNode,
    CommentNode,
    DataNode,
    ExportNode,
    FunctionNode,
    GlobalSymbolNode,
    I64ConstNode,
    IfThenBlockNode,
    ImportNode,
    InstructionCallNode,
    InstructionNode,
    InstructionsNode,
    MemoryNode,
    ModuleNode,
    ModuleStartSymbolNode,
    ParamNode,
    ResultNode,
    SExpr,
    ThenBlockNode,
)
from libgofra.codegen.backends.wasm32.types import wasm_type_from_primitive
from libgofra.codegen.config import CodegenConfig
from libgofra.hir.function import PARAMS_T, Function
from libgofra.hir.initializer import (
    VariableIntArrayInitializerValue,
    VariableIntFieldedStructureInitializerValue,
    VariableStringPtrInitializerValue,
)
from libgofra.hir.module import Module
from libgofra.hir.operator import FunctionCallOperand, Operator, OperatorType
from libgofra.hir.variable import Variable, VariableStorageClass
from libgofra.targets.target import Target
from libgofra.types._base import PrimitiveType, Type
from libgofra.types.composite.array import ArrayType
from libgofra.types.composite.string import StringType
from libgofra.types.composite.structure import StructureType
from libgofra.types.primitive.character import CharType
from libgofra.types.primitive.integers import I64Type

MUTABLE_CONST_NON_DATA_SYMBOLS = True


class WASM32CodegenBackend:
    target: Target
    module: Module
    _fd: IO[str]
    on_warning: Callable[[str], None]

    symtable: MutableMapping[str, int]
    _symtable_next_offset: int = 0

    _strings_to_load: MutableMapping[int, tuple[str, str]]

    spilled_stack_vars_slots: MutableSequence[tuple[int, Variable[Type]]]
    shared_import_memory: bool = True

    wasm_module_start_as_entry_ref: bool = False

    wasm_import_module: str = "env"
    requested_inlined_intrinsics: set[Literal["swap", "swap_i64i32", "copy"]]

    def __init__(
        self,
        target: Target,
        module: Module,
        fd: IO[str],
        on_warning: Callable[[str], None],
        config: CodegenConfig,
    ) -> None:
        assert target.architecture == "WASM32"
        assert not module.dependencies, "Not implemented"

        if config.dwarf_emit_cfi:
            on_warning("DWARF CFI is not applicable to WASM codegen, omitting!")

        if config.align_functions_bytes is not None:
            on_warning(
                "Overriding functions alignment is not applicable to WASM codegen, omitting!",
            )

        self.target = target
        self.module = module
        self._fd = fd
        self.on_warning = on_warning

        self.symtable = {}
        self._symtable_next_offset = 0
        self._strings_to_load = {}
        self.spilled_stack_vars_slots = []
        self.requested_inlined_intrinsics = set()
        self.config = config

        self.on_warning(
            "WASM target is WIP, it has possible interference with how base (x64, ARM) codegen work!",
        )

    def build_memory_pages_node(self) -> ImportNode | MemoryNode:
        memory = MemoryNode(min_pages=1)
        if self.shared_import_memory:
            return ImportNode(self.wasm_import_module, "memory", memory)
        return memory

    def wasm_init_mem_from_var_initial_value(self, var: Variable[Type]) -> str:
        match var.initial_value:
            case int():
                init_mem = wasm_pack_integer_to_memory(
                    var.initial_value,
                    size=var.size_in_bytes,
                )
            case None:
                init_mem = wasm_pack_integer_to_memory(0, size=var.size_in_bytes)
            case VariableIntFieldedStructureInitializerValue():
                struct = var.type
                assert isinstance(struct, StructureType)
                prev_taken_bytes = 0
                init_mem = ""
                for field in struct.order:
                    value = var.initial_value.values[field]

                    field_t = struct.get_field_type(field)
                    assert isinstance(field_t, PrimitiveType), field_t

                    padding = struct.get_field_offset(field) - prev_taken_bytes

                    if padding:
                        init_mem += wasm_pack_integer_to_memory(0, size=padding)
                    init_mem += wasm_pack_integer_to_memory(
                        value,
                        size=field_t.size_in_bytes,
                    )

                    prev_taken_bytes += field_t.size_in_bytes + padding
            case VariableStringPtrInitializerValue():
                string_raw = var.initial_value.string
                self._strings_to_load[self._symtable_next_offset] = (
                    string_raw,
                    string_raw,
                )

                slice_size = StringType().size_in_bytes
                str_size = CharType().size_in_bytes * len(string_raw)
                offset = self._symtable_next_offset
                self._symtable_next_offset += slice_size
                self._symtable_next_offset += str_size

                init_mem = wasm_pack_integer_to_memory(offset, size=var.size_in_bytes)
            case VariableIntArrayInitializerValue():
                init_mem = ""
                assert isinstance(var.type, ArrayType)
                values = var.initial_value.values

                element_size = var.type.element_type.size_in_bytes
                for value in var.initial_value.values:
                    init_mem += wasm_pack_integer_to_memory(
                        value,
                        size=element_size,
                    )
                empty_cells = var.type.elements_count - len(values)
                if not empty_cells:
                    return init_mem
                if var.initial_value.default == 0:
                    bytes_total = var.type.size_in_bytes
                    bytes_taken = len(values) * element_size
                    bytes_free = bytes_total - bytes_taken
                    init_mem += wasm_pack_integer_to_memory(0, size=bytes_free)
                else:
                    fill_with = var.initial_value.default
                    cell_size = I64Type().size_in_bytes
                    for _ in range(empty_cells):
                        init_mem += wasm_pack_integer_to_memory(
                            fill_with,
                            size=cell_size,
                        )

            case _:
                raise NotImplementedError(var.initial_value, var)

        return init_mem

    def build_and_allocate_data_node_from_variable(
        self,
        variable: Variable[Type],
    ) -> DataNode:
        init_mem = self.wasm_init_mem_from_var_initial_value(variable)
        node = DataNode(self._symtable_next_offset, init_mem)

        # Allocate and shift symtable
        self.symtable[variable.name] = self._symtable_next_offset
        self._symtable_next_offset += variable.size_in_bytes
        return node

    def build_global_mutable_data(self) -> Generator[DataNode]:
        for var in self.module.variables.values():
            if var.is_constant and not MUTABLE_CONST_NON_DATA_SYMBOLS:
                continue  # Global symbol, not linear memory

            yield self.build_and_allocate_data_node_from_variable(var)

    def build_global_immutable_data(self) -> Generator[GlobalSymbolNode]:
        if MUTABLE_CONST_NON_DATA_SYMBOLS:
            return
        for var in self.module.variables.values():
            if not var.is_constant:
                continue
            yield self.build_global_variable_symbol_node(var)

    def build_global_variable_symbol_node(
        self,
        var: Variable[Type],
    ) -> GlobalSymbolNode:
        assert var.is_global_scope
        assert var.initial_value is not None, (
            f"uninitialized symbol {var.name} for WASM"
        )

        match var.initial_value:
            case int():
                return GlobalSymbolNode(
                    var.name,
                    store_type=wasm_type_from_primitive(var.type),
                    initializer=I64ConstNode(var.initial_value),
                    is_mutable=var.is_constant,
                )
            case VariableStringPtrInitializerValue():
                string_raw = var.initial_value.string
                self._strings_to_load[self._symtable_next_offset] = (
                    string_raw,
                    string_raw,
                )

                slice_size = StringType().size_in_bytes
                str_size = CharType().size_in_bytes * len(string_raw)
                offset = self._symtable_next_offset
                self._symtable_next_offset += slice_size
                self._symtable_next_offset += str_size

                return GlobalSymbolNode(
                    var.name,
                    store_type=wasm_type_from_primitive(var.type),
                    initializer=I64ConstNode(offset),
                    is_mutable=var.is_constant,
                )
            case _:
                msg = f"Cannot define global symbol in wasm with default value {var.initial_value}, not implemented unwinding constant Initializers."
                raise NotImplementedError(msg)

    def build_module_scope_data(self) -> Generator[DataNode | GlobalSymbolNode]:
        yield from self.build_global_mutable_data()
        yield from self.build_global_immutable_data()

    def build_extern_function_imports(self) -> Generator[ImportNode]:
        for function in self.module.functions.values():
            if not function.is_external:
                continue

            function_specification = _get_wasm_internal_function_decl_spec(function)
            yield ImportNode(
                self.wasm_import_module,
                function.name,
                function_specification,
            )

    def build_requested_inlined_intrinsics_decls(self) -> Generator[FunctionNode]:
        if "swap" in self.requested_inlined_intrinsics:
            node = FunctionNode("swap")
            node.add_node(ParamNode(["i64", "i64"]))
            node.add_node(ResultNode("i64"))
            node.add_node(ResultNode("i64"))
            node.add_node(InstructionNode("local.get", 1))
            node.add_node(InstructionNode("local.get", 0))
            yield node

        if "swap_i64i32" in self.requested_inlined_intrinsics:
            node = FunctionNode("swap_i64i32")
            node.add_node(ParamNode(["i64", "i32"]))
            node.add_node(ResultNode("i32"))
            node.add_node(ResultNode("i64"))
            node.add_node(InstructionNode("local.get", 1))
            node.add_node(InstructionNode("local.get", 0))
            yield node

        if "copy" in self.requested_inlined_intrinsics:
            node = FunctionNode("copy")
            node.add_node(ParamNode(["i64"]))
            node.add_node(ResultNode("i64"))
            node.add_node(ResultNode("i64"))
            node.add_node(InstructionNode("local.get", 0))
            node.add_node(InstructionNode("local.get", 0))
            yield node

    def build_static_strings_data(
        self,
    ) -> Generator[DataNode]:
        # TODO: As global symbol node? or left mutable data node
        view_size = StringType().size_in_bytes
        for symtable_idx, str_val in self._strings_to_load.items():
            data_ptr = symtable_idx + view_size

            string_raw, string_op = str_val
            data = wasm_pack_string_view_to_memory(data_ptr, len(string_op))

            yield DataNode(symtable_idx, data)
            yield DataNode(symtable_idx + view_size, string_raw)
        self._strings_to_load.clear()

    def build_module_node_tree(self) -> ModuleNode:
        mod_node = ModuleNode()
        mod_node.add_nodes(self.build_extern_function_imports())
        mod_node.add_node(self.build_memory_pages_node())
        mod_node.add_nodes(self.build_module_scope_data())
        mod_node.add_nodes(self.build_executable_functions())
        mod_node.add_nodes(self.build_static_strings_data())
        mod_node.add_nodes(self.build_spilled_stack_vars_slots())
        mod_node.add_nodes(self.build_requested_inlined_intrinsics_decls())

        if self.wasm_module_start_as_entry_ref and self.module.entry_point_ref:
            mod_node.add_node(ModuleStartSymbolNode(self.module.entry_point_ref.name))

        return mod_node

    def emit(self) -> None:
        module = self.build_module_node_tree()
        assert not self.spilled_stack_vars_slots, "Unloaded stack variable"
        assert not self._strings_to_load, "Unloaded strings"
        skipped_sexpr_types = (
            (CommentNode,) if self.config.no_compiler_comments else None
        )
        s_node = module.build(skipped_sexpr_types=skipped_sexpr_types)
        self._fd.write(s_node)

    def build_spilled_stack_vars_slots(self) -> Generator[DataNode]:
        # TODO: Although, stack variables are un-initialized this behavior now is undocumented
        # TODO: Spilling always is a bad practice - may use locals from WASM specs
        for slot in self.spilled_stack_vars_slots:
            slot_offset, slot_var = slot
            init_mem = self.wasm_init_mem_from_var_initial_value(slot_var)
            yield DataNode(slot_offset, init_mem)
        self.spilled_stack_vars_slots.clear()

    def build_executable_functions(self) -> Generator[SExpr]:
        for function in self.module.functions.values():
            if function.is_external:
                continue

            node = _get_wasm_internal_function_decl_spec(function)

            node.add_nodes(self._function_prologue_load_params(function.parameters))

            spilled_mem_vars = self._function_allocate_spilled_stack_var_slots(
                function.variables,
            )

            node.add_node("\n")
            for instr_node in self.build_instruction_set_blocked(
                function.operators,
                function,
                spilled_mem_vars,
            ).items:
                node.add_node(instr_node)

            node.finite_stmt = True
            yield node

    def _function_allocate_spilled_stack_var_slots(
        self,
        variables: Mapping[str, Variable[Type]],
    ) -> MutableMapping[str, int]:
        spilled_mem_vars: MutableMapping[str, int] = {}
        for var in variables.values():
            assert not var.is_constant
            assert var.is_function_scope
            assert var.storage_class == VariableStorageClass.STACK

            spilled_mem_vars[var.name] = self._symtable_next_offset
            slot = (self._symtable_next_offset, var)
            self.spilled_stack_vars_slots.append(slot)
            self._symtable_next_offset += var.size_in_bytes

            if var.initial_value:
                self.on_warning(
                    f"Local variable {var.name} at {var.defined_at} is spilled for WASM codegen, but has initial value! This may lead to read after polluting with other function call, consider manual initializer logic",
                )
        return spilled_mem_vars

    def _function_prologue_load_params(
        self,
        params: PARAMS_T,
    ) -> Generator[InstructionNode]:
        for param_i, param in enumerate(params):
            assert param.size_in_bytes <= 8
            assert not param.is_fp
            yield InstructionNode("local.get", param_i)

    def build_instruction_set_blocked(
        self,
        operators: Sequence[Operator],
        owner_function: Function,
        _mem_spilled_stack_vars: MutableMapping[str, int],
    ) -> InstructionsNode:
        """Write executable instructions from given operators."""
        instructions_node = InstructionsNode()

        block_refs: list[InstructionsNode | ThenBlockNode | BlockLoopNode] = [
            instructions_node,
        ]

        for idx, operator in enumerate(operators):
            match operator.type:
                case OperatorType.CONDITIONAL_IF:
                    block_node = IfThenBlockNode()
                    instructions_node.add_node("\t")
                    instructions_node.add_node(InstructionNode("i32.wrap_i64"))
                    instructions_node.add_node(block_node)
                    instructions_node.add_node(CommentNode(operator.location))
                    instructions_node.add_node("\n")
                    block_refs.append(block_node.then_branch_ref)
                    continue
                case OperatorType.CONDITIONAL_END:
                    block = block_refs.pop()
                    assert isinstance(block, ThenBlockNode | BlockLoopNode), repr(block)
                    if not isinstance(block, BlockLoopNode):
                        continue
                    label = CODEGEN_GOFRA_CONTEXT_LABEL % (owner_function.name, idx)
                    if isinstance(operator.jumps_to_operator_idx, int):
                        label_to = CODEGEN_GOFRA_CONTEXT_LABEL % (
                            owner_function.name,
                            operator.jumps_to_operator_idx,
                        )
                        block.add_node(InstructionNode("br", f"${label_to + '_start'}"))
                    continue
                case OperatorType.CONDITIONAL_WHILE | OperatorType.CONDITIONAL_FOR:
                    label = CODEGEN_GOFRA_CONTEXT_LABEL % (owner_function.name, idx)

                    block_node = BlockNode(name=label + "_end")
                    loop_node = BlockLoopNode(name=label + "_start")
                    block_node.add_node(loop_node)
                    instructions_node.add_node("\t")
                    instructions_node.add_node(block_node)
                    instructions_node.add_node(CommentNode(operator.location))
                    instructions_node.add_node("\n")
                    block_refs.append(loop_node)
                    continue
                case OperatorType.CONDITIONAL_DO:
                    assert block_refs
                    target = block_refs[-1]
                    assert isinstance(operator.jumps_to_operator_idx, int)
                    end_op = operators[operator.jumps_to_operator_idx]
                    assert end_op.type == OperatorType.CONDITIONAL_END
                    assert end_op.jumps_to_operator_idx
                    label_to = CODEGEN_GOFRA_CONTEXT_LABEL % (
                        owner_function.name,
                        end_op.jumps_to_operator_idx,
                    )
                    target.add_node(InstructionNode("i64.eqz"))
                    target.add_node(
                        InstructionNode("br_if ", f"${label_to + '_end'}"),
                    )
                    continue
                case _:
                    pass

            assert block_refs
            target = block_refs[-1]
            instr_generator = self.build_operator_wasm_instructions(
                operator,
                owner_function,
                _mem_spilled_stack_vars=_mem_spilled_stack_vars,
            )

            target.add_node("\t")
            target.add_nodes(instr_generator)
            target.add_node(
                CommentNode(repr(operator.type.name) + " " + str(operator.location)),
            )
            target.add_node("\n")

        instructions_node.add_node(" ")
        return instructions_node

    def build_operator_wasm_instructions(
        self,
        op: Operator,
        owner_function: Function,
        _mem_spilled_stack_vars: MutableMapping[str, int],
    ) -> Generator[InstructionNode | I64ConstNode]:
        match op.type:
            # Simple operators
            # E.g math
            case OperatorType.PUSH_INTEGER:
                assert isinstance(op.operand, int)
                yield InstructionNode("i64.const", op.operand)  # I64ConstNode
            case OperatorType.ARITHMETIC_PLUS:
                yield InstructionNode("i64.add")
            case OperatorType.PUSH_FLOAT:
                assert isinstance(op.operand, float)
                yield InstructionNode("f64.const", op.operand)
            case OperatorType.STACK_DROP:
                yield InstructionNode("drop")
            case OperatorType.ARITHMETIC_MULTIPLY:
                yield InstructionNode("i64.mul")
            case OperatorType.ARITHMETIC_MINUS:
                yield InstructionNode("i64.sub")
            case OperatorType.BITWISE_AND:
                yield InstructionNode("i64.and")
            case OperatorType.BITWISE_OR:
                yield InstructionNode("i64.or")
            case OperatorType.BITWISE_XOR:
                yield InstructionNode("i64.xor")
            case OperatorType.COMPARE_LESS:
                yield InstructionNode("i64.lt_s")
                yield InstructionNode("i64.extend_i32_u")
            case OperatorType.COMPARE_EQUALS:
                yield InstructionNode("i64.eq")
                yield InstructionNode("i64.extend_i32_u")
            case OperatorType.COMPARE_NOT_EQUALS:
                yield InstructionNode("i64.ne")
                yield InstructionNode("i64.extend_i32_u")
            case OperatorType.COMPARE_GREATER:
                yield InstructionNode("i64.gt_s")
                yield InstructionNode("i64.extend_i32_u")
            case OperatorType.COMPARE_GREATER_EQUALS:
                yield InstructionNode("i64.lt_s")
                yield InstructionNode("i32.eqz")
                yield InstructionNode("i64.extend_i32_u")
            case OperatorType.COMPARE_LESS_EQUALS:
                yield InstructionNode("i64.gt_s")
                yield InstructionNode("i32.eqz")
                yield InstructionNode("i64.extend_i32_u")
            case OperatorType.ARITHMETIC_MODULUS:
                yield InstructionNode("i64.rem_s")
            case OperatorType.ARITHMETIC_DIVIDE:
                yield InstructionNode("i64.div_s")
            case OperatorType.STACK_SWAP:
                self.requested_inlined_intrinsics.add("swap")
                yield InstructionCallNode("swap")
            case OperatorType.STACK_COPY:
                self.requested_inlined_intrinsics.add("copy")
                yield InstructionCallNode("copy")
            # Other instructions
            case OperatorType.INLINE_RAW_ASM:
                assert isinstance(op.operand, str)
                yield InstructionNode(op.operand)
            case OperatorType.SYSCALL:
                msg = f"Syscall at {op.location} is not supported by WASM target, please use system function calls!"
                raise ValueError(msg)
            case OperatorType.DEBUGGER_BREAKPOINT:
                yield InstructionNode("unreachable")
            case OperatorType.COMPILE_TIME_ERROR | OperatorType.STATIC_TYPE_CAST:
                ...
            # Function instructions
            case OperatorType.FUNCTION_CALL:
                assert isinstance(op.operand, FunctionCallOperand)
                assert op.operand.module is None
                assert op.operand.get_name() not in self.requested_inlined_intrinsics, (
                    f"Call to function requested as inlined intrinsic by WASM codegen ({op.operand.get_name()})"
                )
                yield InstructionCallNode(op.operand.get_name())
            case OperatorType.FUNCTION_RETURN:
                yield InstructionNode("return")
            # Memory I/O operations
            case OperatorType.STRUCT_FIELD_OFFSET:
                assert isinstance(op.operand, tuple)
                struct, field = op.operand
                field_offset = struct.get_field_offset(field)
                if field_offset:
                    # only relatable as operation is pointer is not already at first structure field
                    yield I64ConstNode(field_offset)
                    yield InstructionNode("i64.add")
                    return
                return
            case OperatorType.PUSH_VARIABLE_VALUE:
                assert isinstance(op.operand, str)
                if op.operand not in owner_function.variables:
                    sym_var = self.module.variables[op.operand]
                    if sym_var.is_constant:
                        yield InstructionNode(f"global.get ${op.operand}")
                        return
                    else:
                        offset = self.symtable[op.operand]
                        sym_t = wasm_type_from_primitive(sym_var.type)
                        yield InstructionNode(f"i32.const {offset}")
                        yield InstructionNode(f"{sym_t}.load")
                        yield CommentNode(f"Symbol={op.operand}")
                        return
                else:
                    spilled_sym_offset = _mem_spilled_stack_vars[op.operand]
                    sym_var = owner_function.variables[op.operand]
                    sym_t = wasm_type_from_primitive(sym_var.type)
                    yield InstructionNode(f"i32.const {spilled_sym_offset}")
                    yield InstructionNode(f"{sym_t}.load")
                    yield CommentNode(f"Symbol={op.operand} (spilled local)")
                    return
            case OperatorType.PUSH_VARIABLE_ADDRESS:
                assert isinstance(op.operand, str)
                if op.operand in _mem_spilled_stack_vars:
                    offset = _mem_spilled_stack_vars[op.operand]
                elif op.operand in self.symtable:
                    offset = self.symtable[op.operand]
                else:
                    raise ValueError(op.operand)
                yield InstructionNode("i64.const", f"{offset}")
                yield CommentNode(f"Symbol=&{op.operand}")
            case OperatorType.PUSH_STRING:
                assert isinstance(op.operand, str)
                string_raw = str(op.token.text[1:-1])
                self._strings_to_load[self._symtable_next_offset] = (
                    string_raw,
                    op.operand,
                )

                slice_size = StringType().size_in_bytes
                str_size = CharType().size_in_bytes * len(op.operand)
                offset = self._symtable_next_offset
                self._symtable_next_offset += slice_size
                self._symtable_next_offset += str_size
                yield I64ConstNode(offset)
                yield CommentNode("symtable offset string")
            case OperatorType.MEMORY_VARIABLE_READ:
                load_type = I64Type()
                load_wasm_type = wasm_type_from_primitive(load_type)

                yield InstructionNode("i32.wrap_i64")
                yield InstructionNode(f"{load_wasm_type}.load")
            case OperatorType.MEMORY_VARIABLE_WRITE:
                self.requested_inlined_intrinsics.add("swap")

                self.requested_inlined_intrinsics.add("swap_i64i32")
                yield InstructionCallNode("swap")
                yield InstructionNode("i32.wrap_i64")
                yield InstructionCallNode("swap_i64i32")
                yield InstructionNode("i64.store")
            case OperatorType.LOAD_PARAM_ARGUMENT:
                # TODO: This instruction is not that bad but using this approach is not supportable well
                # Migrate to named arguments
                assert isinstance(op.operand, str)
                assert op.operand in _mem_spilled_stack_vars
                offset = _mem_spilled_stack_vars[op.operand]

                yield InstructionNode(f"i32.const {offset} ")
                self.requested_inlined_intrinsics.add("swap_i64i32")
                yield InstructionCallNode("swap_i64i32")

                yield InstructionNode("i64.store")
                yield CommentNode(f"symtable offset sym={op.operand}")
                return
            case (
                OperatorType.CONDITIONAL_DO
                | OperatorType.CONDITIONAL_IF
                | OperatorType.CONDITIONAL_END
                | OperatorType.CONDITIONAL_WHILE
                | OperatorType.CONDITIONAL_FOR
            ):
                # Must be resolved by high-level instruction set
                msg = f"{op} must be handled as block-ref"
                raise ValueError(msg)
            case OperatorType.SHIFT_LEFT:
                yield InstructionNode("i64.shl")
            case OperatorType.SHIFT_RIGHT:
                yield InstructionNode("i64.shr_u")
            case OperatorType.LOGICAL_AND:
                yield InstructionNode("i64.and")
            case OperatorType.LOGICAL_OR:
                yield InstructionNode("i64.or")
            case OperatorType.LOGICAL_NOT:
                yield InstructionNode("i64.const", 0)
                yield InstructionNode("i64.eq")
                yield InstructionNode("i64.extend_i32_u")
            case OperatorType.PUSH_FUNCTION_POINTER:
                raise NotImplementedError(op)
            case OperatorType.FUNCTION_CALL_FROM_STACK_POINTER:
                raise NotImplementedError(op)
            case _:
                assert_never(op.type)


def _get_wasm_internal_function_decl_spec(function: Function) -> FunctionNode:
    decl = FunctionNode(function.name)

    if function.is_public:
        decl.add_node(ExportNode(function.name))

    if function.parameters:
        # TODO: WAT/WASM allows named function params
        params = ParamNode(wasm_type_from_primitive(p) for p in function.parameters)
        decl.add_node(params)

    if function.has_return_value():
        assert function.return_type.size_in_bytes <= 8
        return_type = wasm_type_from_primitive(function.return_type)
        decl.add_node(ResultNode(return_type))

    return decl
