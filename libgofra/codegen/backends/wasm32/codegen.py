from collections.abc import Callable, MutableMapping, Sequence
from typing import IO, assert_never

from libgofra.hir.function import Function
from libgofra.hir.module import Module
from libgofra.hir.operator import FunctionCallOperand, Operator, OperatorType
from libgofra.hir.variable import Variable
from libgofra.targets.target import Target
from libgofra.types._base import PrimitiveType, Type
from libgofra.types.composite.pointer import PointerType
from libgofra.types.composite.string import StringType
from libgofra.types.primitive.character import CharType


class WASM32CodegenBackend:
    target: Target
    module: Module
    fd: IO[str]
    on_warning: Callable[[str], None]

    symtable: MutableMapping[str, int]
    _symtable_next_offset: int = 0

    _strings_to_load: MutableMapping[int, tuple[str, str]]

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
        self.fd = fd
        self.on_warning = on_warning

        self.symtable = {}
        self._symtable_next_offset = 0
        self._strings_to_load = {}

    def emit_build_global_symtable(self, *, _imported_memory: bool = True) -> None:
        if _imported_memory:
            self.fd.write('\t(import "env" "memory" (memory 1))\n')
        else:
            self.fd.write("\t(memory 1)\n")

        if not self.module.variables:
            return
        for var in self.module.variables.values():
            if var.is_constant:
                continue  # Global symbol, not linear memory

            init_mem = ""
            match var.initial_value:
                case int():
                    init_mem = _int_to_wat_bytes(
                        var.initial_value,
                        size=var.size_in_bytes,
                    )
                case None:
                    init_mem = _int_to_wat_bytes(0, size=var.size_in_bytes)
                case _:
                    raise NotImplementedError(var.initial_value, var)
            page_mem_spec = "(memory 0)"
            addr_offset_spec = f"(i64.const {self._symtable_next_offset})"
            self.fd.write(f'\t(data {page_mem_spec} {addr_offset_spec} "{init_mem}")')
            self.fd.write(f" ;; {var.name}\n")

            self.symtable[var.name] = self._symtable_next_offset
            self._symtable_next_offset += var.size_in_bytes

    def emit_global_symbol_decls(self) -> None:
        for var in self.module.variables.values():
            if not var.is_constant:
                continue
            self.fd.write(_get_wat_global_symbol_decl_spec(var))

    def emit(self) -> None:
        self.fd.write("(module\n")
        self.wasm32_extern_functions()
        self.wasm32_module_scope_decls()
        self.wasm32_executable_functions()
        self.wasm32_static_data_string_section()
        self.wasm32_emit_intrinsic_op_defs()
        self.fd.write(")")
        assert not self._strings_to_load, "Unloaded strings"

    def wasm32_emit_intrinsic_op_defs(self) -> None:
        self.fd.write(
            "\t(func $swap (param i64 i64) (result i64 i64) (local.get 1) (local.get 0))",
        )

    def wasm32_static_data_string_section(
        self,
    ) -> None:
        page_mem_spec = "(memory 0)"

        for symtable_idx, str_val in self._strings_to_load.items():
            view_size = StringType().size_in_bytes
            data_ptr = symtable_idx + view_size

            string_raw, string_op = str_val
            addr_offset_spec = f"(i32.const {symtable_idx})"
            view_struct_data = _int_to_wat_bytes(data_ptr, size=8) + _int_to_wat_bytes(
                len(string_op),
                size=8,
            )
            self.fd.write(
                f'\t(data {page_mem_spec} {addr_offset_spec} "{view_struct_data}")',
            )
            self.fd.write(" ;; String-View\n")

            addr_offset_spec = f"(i32.const {symtable_idx + view_size})"
            self.fd.write(f'\t(data {page_mem_spec} {addr_offset_spec} "{string_raw}")')
            self.fd.write(" ;; String\n")

        self._strings_to_load.clear()

    def wasm32_module_scope_decls(self) -> None:
        self.emit_build_global_symtable()
        self.emit_global_symbol_decls()

    def wasm32_executable_functions(self) -> None:
        for function in self.module.functions.values():
            if function.is_external:
                continue
            assert not function.is_no_return
            assert not function.variables, (
                f"Locals not implemented {function.defined_at}"
            )

            self.fd.write(_get_wat_function_decl_spec(function))

            for param_i, param in enumerate(function.parameters):
                assert param.size_in_bytes <= 8
                assert not param.is_fp
                self.fd.write(f"\t\tlocal.get {param_i}\n")

            self.wasm32_instruction_set(function.operators, function)
            self.fd.write("\t)\n")

    def wasm32_extern_functions(self) -> None:
        for function in self.module.functions.values():
            if not function.is_external:
                continue

            self.fd.write(_get_wat_function_decl_spec(function))
            assert not function.has_executable_operators

    def wasm32_operator_instructions(
        self,
        op: Operator,
        idx: int,
        owner_function: Function,
    ) -> None:
        _ = idx
        match op.type:
            case OperatorType.PUSH_INTEGER:
                assert isinstance(op.operand, int)
                self.fd.write(f"\t\ti64.const {op.operand}\n")
            case OperatorType.ARITHMETIC_PLUS:
                self.fd.write("\t\ti64.add\n")
            case OperatorType.PUSH_FLOAT:
                assert isinstance(op.operand, float)
                self.fd.write(f"\t\tf64.const {op.operand}\n")
            case OperatorType.STACK_DROP:
                self.fd.write("\t\tdrop\n")
            case OperatorType.INLINE_RAW_ASM:
                assert isinstance(op.operand, str)
                self.fd.write(op.operand)
            case OperatorType.ARITHMETIC_MULTIPLY:
                self.fd.write("\t\ti64.mul\n")
            case OperatorType.ARITHMETIC_MINUS:
                self.fd.write("\t\ti64.sub\n")
            case OperatorType.BITWISE_AND:
                self.fd.write("\t\ti64.and\n")
            case OperatorType.BITWISE_OR:
                self.fd.write("\t\ti64.or\n")
            case OperatorType.BITWISE_XOR:
                self.fd.write("\t\ti64.xor\n")
            case OperatorType.FUNCTION_CALL:
                assert isinstance(op.operand, FunctionCallOperand)
                assert op.operand.module is None
                self.fd.write(f"\t\tcall ${op.operand.func_name}\n")
            case OperatorType.FUNCTION_RETURN:
                self.fd.write("\t\treturn\n")
            case OperatorType.SYSCALL:
                msg = f"Syscall at {op.location} is not supported by WASM target, please use system function calls!"
                raise ValueError(msg)
            case OperatorType.DEBUGGER_BREAKPOINT:
                msg = "Debugger breakpoint is not implemented in WASM"
                raise NotImplementedError(msg)
            case OperatorType.COMPILE_TIME_ERROR | OperatorType.STATIC_TYPE_CAST:
                ...
            case OperatorType.STRUCT_FIELD_OFFSET:
                assert isinstance(op.operand, tuple)
                struct, field = op.operand
                field_offset = struct.get_field_offset(field)
                if field_offset:
                    # only relatable as operation is pointer is not already at first structure field
                    self.fd.write(f"\t\ti64.const {field_offset}\n")
                    self.fd.write("\t\ti64.add\n")

            case OperatorType.PUSH_VARIABLE_VALUE:
                assert isinstance(op.operand, str)
                if op.operand not in owner_function.variables:
                    sym_var = self.module.variables[op.operand]
                    if sym_var.is_constant:
                        self.fd.write(f"\t\tglobal.get ${op.operand}\n")
                    else:
                        offset = self.symtable[op.operand]
                        self.fd.write(
                            f"\t\ti32.const {offset} ;; symtable offset sym={op.operand}\n",
                        )
                        sym_t = _get_wat_primitive_type(sym_var.type)
                        self.fd.write(f"\t\t{sym_t}.load\n")
                else:
                    raise NotImplementedError

            case OperatorType.PUSH_VARIABLE_ADDRESS:
                assert isinstance(op.operand, str)
                offset = self.symtable[op.operand]
                self.fd.write(
                    f"\t\ti64.const {offset} ;; symtable offset sym={op.operand}\n",
                )
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
                self.fd.write(f"\t\ti64.const {offset} ;; symtable offset string\n")
            case OperatorType.STACK_SWAP:
                self.fd.write("\t\tcall $swap\n")

            case (
                OperatorType.PUSH_VARIABLE_ADDRESS
                | OperatorType.LOAD_PARAM_ARGUMENT
                | OperatorType.CONDITIONAL_IF
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
                | OperatorType.MEMORY_VARIABLE_READ
                | OperatorType.MEMORY_VARIABLE_WRITE
            ):
                raise NotImplementedError(op)
            case _:
                assert_never(op.type)

    def wasm32_instruction_set(
        self,
        operators: Sequence[Operator],
        owner_function: Function,
    ) -> None:
        """Write executable instructions from given operators."""
        for idx, operator in enumerate(operators):
            self.wasm32_operator_instructions(operator, idx, owner_function)


def _get_wat_global_symbol_decl_spec(var: Variable[Type]) -> str:
    wat_t = _get_wat_primitive_type(var.type)
    sym_type_spec = f"{wat_t}" if var.is_constant else f"(mut {wat_t})"

    assert var.is_global_scope
    assert var.initial_value is not None, f"uninitialized symbol {var.name} for WASM"

    match var.initial_value:
        case int():
            return f"\t(global ${var.name} {sym_type_spec} (i64.const {var.initial_value}))\n"
        case _:
            raise NotImplementedError(var.initial_value)


def _get_wat_function_decl_spec(function: Function) -> str:
    decl = f"func ${function.name}"
    extern_from_module = "env"

    if function.is_external:
        decl = f'import "{extern_from_module}" "{function.name}" ({decl}'
    if function.is_public:
        decl += f' (export "{function.name}")'

    if function.parameters:
        # TODO: WAT/WASM allows named function params
        param_spec = [_get_wat_primitive_type(param) for param in function.parameters]
        decl += f" (param {' '.join(param_spec)})"

    if function.has_return_value():
        assert function.return_type.size_in_bytes <= 8
        return_type = _get_wat_primitive_type(function.return_type)
        decl += f" (result {return_type})"
    if function.is_external:
        decl += "))"
    return f"\t({decl}\n"


def _get_wat_primitive_type(t: Type) -> str:
    """Get primitive type from Gofra to WAT."""
    if isinstance(t, PointerType):
        return "i64"

    assert isinstance(t, PrimitiveType), t
    if t.size_in_bytes <= 4:
        return "f32" if t.is_fp else "i32"
    assert t.size_in_bytes <= 8
    return "f64" if t.is_fp else "i64"


def _int_to_wat_bytes(value: int, size: int = 8) -> str:
    """Transform integer to bytes data for WAT memory data."""
    data = value.to_bytes(size, "little")
    return "".join(f"\\{byte:02X}" for byte in data)
