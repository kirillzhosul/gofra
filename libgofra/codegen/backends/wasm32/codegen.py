from collections.abc import (
    Callable,
    Generator,
    MutableMapping,
    MutableSequence,
    Sequence,
)
from typing import IO, assert_never

from libgofra.codegen.backends.wasm32.memory import (
    wasm_init_mem_from_var_initial_value,
    wasm_pack_string_view_to_memory,
)
from libgofra.codegen.backends.wasm32.sexpr import (
    DataNode,
    ExportNode,
    FunctionNode,
    GlobalSymbolNode,
    I64ConstNode,
    ImportNode,
    InstructionCallNode,
    InstructionNode,
    InstructionsNode,
    MemoryNode,
    ModuleNode,
    ParamNode,
    ResultNode,
    SExpr,
)
from libgofra.codegen.backends.wasm32.types import wasm_type_from_primitive
from libgofra.hir.function import Function
from libgofra.hir.module import Module
from libgofra.hir.operator import FunctionCallOperand, Operator, OperatorType
from libgofra.hir.variable import Variable, VariableStorageClass
from libgofra.targets.target import Target
from libgofra.types._base import Type
from libgofra.types.composite.string import StringType
from libgofra.types.primitive.character import CharType
from libgofra.types.primitive.integers import I64Type


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

    def __init__(
        self,
        target: Target,
        module: Module,
        fd: IO[str],
        on_warning: Callable[[str], None],
    ) -> None:
        assert target.architecture == "WASM32"
        assert not module.dependencies, "Not implemented"

        self.target = target
        self.module = module
        self._fd = fd
        self.on_warning = on_warning

        self.symtable = {}
        self._symtable_next_offset = 0
        self._strings_to_load = {}
        self.spilled_stack_vars_slots = []

    def emit_build_global_symtable(self) -> Generator[SExpr]:
        memory = MemoryNode(min_pages=1)
        if self.shared_import_memory:
            memory = ImportNode("env", "memory", memory)
        yield memory

        if not self.module.variables:
            return
        for var in self.module.variables.values():
            if var.is_constant:
                continue  # Global symbol, not linear memory

            init_mem = wasm_init_mem_from_var_initial_value(var)
            yield DataNode(self._symtable_next_offset, init_mem)
            # comment=var.name,

            self.symtable[var.name] = self._symtable_next_offset
            self._symtable_next_offset += var.size_in_bytes

    def emit_global_symbol_decls(self) -> Generator[SExpr]:
        for var in self.module.variables.values():
            if not var.is_constant:
                continue
            yield (_get_wat_global_symbol_decl_spec(var))

    def emit(self) -> None:
        module = self.build_node_tree()
        self._fd.write(module.build())
        assert not self.spilled_stack_vars_slots, "Unloaded stack variable"
        assert not self._strings_to_load, "Unloaded strings"

    def build_node_tree(self) -> ModuleNode:
        mod_node = ModuleNode()
        mod_node.add_nodes(self.wasm32_extern_functions())
        mod_node.add_nodes(self.wasm32_module_scope_decls())
        mod_node.add_nodes(self.wasm32_emit_intrinsic_op_defs())
        mod_node.add_nodes(self.wasm32_executable_functions())
        mod_node.add_nodes(self.wasm32_static_data_string_section())
        mod_node.add_nodes(self.wasm32_spilled_static_section())
        return mod_node

    def wasm32_spilled_static_section(self) -> Generator[SExpr]:
        for slot in self.spilled_stack_vars_slots:
            slot_offset, slot_var = slot
            # TODO: Although, stack variables are un-initialized this behavior now is undocumented
            # TODO: Spilling always is a bad practice - may use locals from WASM specs
            yield (
                DataNode(slot_offset, wasm_init_mem_from_var_initial_value(slot_var))
            )
            # comment=f"Spilled from local {slot_var.name} at {slot_var.defined_at}",
        self.spilled_stack_vars_slots.clear()

    def wasm32_emit_intrinsic_op_defs(self) -> Generator[SExpr]:
        yield SExpr(
            "func",
            "$swap",
            ParamNode(["i64", "i64"]),
            SExpr("result", "i64", "i64"),
            InstructionNode("local.get", 1),
            InstructionNode("local.get", 0),
        )

        yield SExpr(
            "func",
            "$@swap_i64i32",
            ParamNode(["i64", "i32"]),
            SExpr("result", "i32", "i64"),
            InstructionNode("local.get", 1),
            InstructionNode("local.get", 0),
        )

    def wasm32_static_data_string_section(
        self,
    ) -> Generator[SExpr]:
        for symtable_idx, str_val in self._strings_to_load.items():
            view_size = StringType().size_in_bytes
            data_ptr = symtable_idx + view_size

            string_raw, string_op = str_val
            data = wasm_pack_string_view_to_memory(data_ptr, len(string_op))

            yield DataNode(symtable_idx, data)
            yield DataNode(symtable_idx + view_size, string_raw)
        self._strings_to_load.clear()

    def wasm32_module_scope_decls(self) -> Generator[SExpr]:
        yield from self.emit_build_global_symtable()
        yield from self.emit_global_symbol_decls()

    def wasm32_executable_functions(self) -> Generator[SExpr]:
        for function in self.module.functions.values():
            if function.is_external:
                continue
            assert not function.is_no_return

            node = _get_wat_function_decl_spec(function)

            for param_i, param in enumerate(function.parameters):
                assert param.size_in_bytes <= 8
                assert not param.is_fp
                node.add_node(InstructionNode("local.get", param_i))

            spilled_mem_vars: MutableMapping[str, int] = {}
            for local_var in function.variables.values():
                assert not local_var.is_constant
                assert local_var.is_function_scope
                assert local_var.storage_class == VariableStorageClass.STACK
                spilled_mem_vars[local_var.name] = self._symtable_next_offset
                slot = (self._symtable_next_offset, local_var)
                self.spilled_stack_vars_slots.append(slot)
                self._symtable_next_offset += local_var.size_in_bytes

            for instr_node in self.wasm32_instruction_set(
                function.operators,
                function,
                spilled_mem_vars,
            ).items:
                node.add_node(instr_node)

            node.finite_stmt = True
            yield node

    def wasm32_extern_functions(self) -> Generator[FunctionNode | ImportNode]:
        for function in self.module.functions.values():
            if not function.is_external:
                continue

            yield _get_wat_function_decl_spec(function)
            assert not function.has_executable_operators

    def wasm32_operator_instructions(
        self,
        op: Operator,
        idx: int,
        owner_function: Function,
        _mem_spilled_stack_vars: MutableMapping[str, int],
    ) -> Generator[InstructionNode | I64ConstNode]:
        _ = idx
        match op.type:
            case OperatorType.PUSH_INTEGER:
                assert isinstance(op.operand, int)
                yield InstructionNode(f"i64.const {op.operand}")
            case OperatorType.ARITHMETIC_PLUS:
                yield InstructionNode("i64.add")
            case OperatorType.PUSH_FLOAT:
                assert isinstance(op.operand, float)
                yield InstructionNode(f"f64.const {op.operand}")
            case OperatorType.STACK_DROP:
                yield InstructionNode("drop")
            case OperatorType.INLINE_RAW_ASM:
                assert isinstance(op.operand, str)
                yield InstructionNode(op.operand)
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
            case OperatorType.FUNCTION_CALL:
                assert isinstance(op.operand, FunctionCallOperand)
                assert op.operand.module is None
                yield InstructionCallNode(op.operand.func_name)
            case OperatorType.FUNCTION_RETURN:
                yield InstructionNode("return")
            case OperatorType.SYSCALL:
                msg = f"Syscall at {op.location} is not supported by WASM target, please use system function calls!"
                raise ValueError(msg)
            case OperatorType.DEBUGGER_BREAKPOINT:
                yield InstructionNode("unreachable")
            case OperatorType.COMPILE_TIME_ERROR | OperatorType.STATIC_TYPE_CAST:
                raise ValueError
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
                        # ;; symtable offset sym={op.operand}
                        yield InstructionNode(f"i32.const {offset}")
                        yield InstructionNode(f"{sym_t}.load")
                        return
                else:
                    spilled_sym_offset = _mem_spilled_stack_vars[op.operand]
                    sym_var = owner_function.variables[op.operand]
                    sym_t = wasm_type_from_primitive(sym_var.type)
                    # ;; symtable offset sym={op.operand} (spilled local)
                    yield InstructionNode(f"i32.const {spilled_sym_offset}")
                    yield InstructionNode(f"{sym_t}.load")
                    return
            case OperatorType.PUSH_VARIABLE_ADDRESS:
                assert isinstance(op.operand, str)
                if op.operand in _mem_spilled_stack_vars:
                    offset = _mem_spilled_stack_vars[op.operand]
                else:
                    offset = self.symtable[op.operand]
                yield InstructionNode(f"i32.const {offset}")
                # ;; symtable offset sym={op.operand}

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
                yield I64ConstNode(offset)  # ;; symtable offset string
            case OperatorType.MEMORY_VARIABLE_READ:
                load_type = I64Type()
                load_wasm_type = wasm_type_from_primitive(load_type)

                yield InstructionNode(f"{load_wasm_type}.load")
            case OperatorType.MEMORY_VARIABLE_WRITE:
                yield InstructionNode("i64.store")
            case OperatorType.STACK_SWAP:
                yield InstructionCallNode("swap")
            case OperatorType.LOAD_PARAM_ARGUMENT:
                # TODO: This instruction is not that bad but using this approach is not supportable well
                # Migrate to named arguments
                assert isinstance(op.operand, str)
                assert op.operand in _mem_spilled_stack_vars
                offset = _mem_spilled_stack_vars[op.operand]

                # ;; symtable offset sym={op.operand}
                yield InstructionNode(f"i32.const {offset} ")
                yield InstructionCallNode("@swap_i64i32")
                yield InstructionNode("i64.store")
                return
            case (
                OperatorType.CONDITIONAL_IF
                | OperatorType.CONDITIONAL_DO
                | OperatorType.CONDITIONAL_WHILE
                | OperatorType.CONDITIONAL_FOR
                | OperatorType.CONDITIONAL_END
                | OperatorType.STACK_SWAP
                | OperatorType.STACK_COPY
                | OperatorType.ARITHMETIC_DIVIDE
                | OperatorType.ARITHMETIC_MODULUS
                | OperatorType.COMPARE_EQUALS
                | OperatorType.COMPARE_NOT_EQUALS
                | OperatorType.COMPARE_LESS
                | OperatorType.COMPARE_GREATER
                | OperatorType.COMPARE_LESS_EQUALS
                | OperatorType.LOGICAL_OR
                | OperatorType.COMPARE_GREATER_EQUALS
                | OperatorType.LOGICAL_AND
                | OperatorType.LOGICAL_NOT
                | OperatorType.SHIFT_RIGHT
                | OperatorType.SHIFT_LEFT
            ):
                raise NotImplementedError(op)
            case _:
                assert_never(op.type)

    def wasm32_instruction_set(
        self,
        operators: Sequence[Operator],
        owner_function: Function,
        _mem_spilled_stack_vars: MutableMapping[str, int],
    ) -> InstructionsNode:
        """Write executable instructions from given operators."""
        instructions_node = InstructionsNode()
        for idx, operator in enumerate(operators):
            instructions_node.add_nodes(
                list(
                    self.wasm32_operator_instructions(
                        operator,
                        idx,
                        owner_function,
                        _mem_spilled_stack_vars=_mem_spilled_stack_vars,
                    ),
                ),
            )
        return instructions_node


def _get_wat_global_symbol_decl_spec(var: Variable[Type]) -> GlobalSymbolNode:
    assert var.is_global_scope
    assert var.initial_value is not None, f"uninitialized symbol {var.name} for WASM"

    match var.initial_value:
        case int():
            return GlobalSymbolNode(
                var.name,
                store_type=wasm_type_from_primitive(var.type),
                initializer=I64ConstNode(var.initial_value),
                is_mutable=var.is_constant,
            )
        case _:
            msg = f"Cannot define global symbol in wasm with default value {var.initial_value}, not implemented unwinding constant Initializers."
            raise NotImplementedError(msg)


def _get_wat_function_decl_spec(function: Function) -> FunctionNode | ImportNode:
    decl = _get_wasm_internal_function_decl_spec(function)

    if function.is_external:
        extern_from_module = "env"
        return ImportNode(extern_from_module, function.name, decl)

    return decl


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
