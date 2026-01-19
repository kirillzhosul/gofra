from collections.abc import Callable, MutableMapping, Sequence
from typing import IO, assert_never

from libgofra.codegen.backends.wasm32.memory import (
    wasm_define_data,
    wasm_pack_integer_to_memory,
    wasm_pack_string_view_to_memory,
)
from libgofra.codegen.backends.wasm32.sexpr import SExpr
from libgofra.codegen.backends.wasm32.types import wasm_type_from_primitive
from libgofra.hir.function import Function
from libgofra.hir.module import Module
from libgofra.hir.operator import FunctionCallOperand, Operator, OperatorType
from libgofra.hir.variable import Variable
from libgofra.targets.target import Target
from libgofra.types._base import Type
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
        self.fd = fd
        self.on_warning = on_warning

        self.symtable = {}
        self._symtable_next_offset = 0
        self._strings_to_load = {}

    def write_sexpr(
        self,
        expr: SExpr,
        indent: int = 0,
        comment: str | None = None,
    ) -> None:
        s = f"{'\t' * indent}{expr.build()}"
        if comment:
            s += f" ;; {comment}"

        self.fd.write(f"{s}\n")

    def write_instr(self, instr: str | SExpr) -> None:
        self.fd.write(f"\t\t{instr}\n")

    def emit_build_global_symtable(self) -> None:
        memory = SExpr("memory", 1)
        if self.shared_import_memory:
            memory = SExpr("import", '"env"', '"memory"', memory)
        self.write_sexpr(memory, indent=1)

        if not self.module.variables:
            return
        for var in self.module.variables.values():
            if var.is_constant:
                continue  # Global symbol, not linear memory

            init_mem = ""
            match var.initial_value:
                case int():
                    init_mem = wasm_pack_integer_to_memory(
                        var.initial_value,
                        size=var.size_in_bytes,
                    )
                case None:
                    init_mem = wasm_pack_integer_to_memory(0, size=var.size_in_bytes)
                case _:
                    raise NotImplementedError(var.initial_value, var)
            self.write_sexpr(
                wasm_define_data(self._symtable_next_offset, init_mem),
                indent=1,
                comment=var.name,
            )

            self.symtable[var.name] = self._symtable_next_offset
            self._symtable_next_offset += var.size_in_bytes

    def emit_global_symbol_decls(self) -> None:
        for var in self.module.variables.values():
            if not var.is_constant:
                continue
            self.write_sexpr(
                _get_wat_global_symbol_decl_spec(var),
                indent=1,
            )

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
        for symtable_idx, str_val in self._strings_to_load.items():
            view_size = StringType().size_in_bytes
            data_ptr = symtable_idx + view_size

            string_raw, string_op = str_val
            data = wasm_pack_string_view_to_memory(data_ptr, len(string_op))

            self.write_sexpr(
                wasm_define_data(symtable_idx, data),
                indent=1,
                comment="String View",
            )

            self.write_sexpr(
                wasm_define_data(symtable_idx + view_size, string_raw),
                indent=1,
                comment="String",
            )
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

            self.fd.write("\t")
            self.fd.write(_get_wat_function_decl_spec(function))
            self.fd.write("\n")

            for param_i, param in enumerate(function.parameters):
                assert param.size_in_bytes <= 8
                assert not param.is_fp
                self.write_sexpr(SExpr("local.get", param_i), indent=2)

            self.wasm32_instruction_set(function.operators, function)
            self.fd.write("\t)\n")

    def wasm32_extern_functions(self) -> None:
        for function in self.module.functions.values():
            if not function.is_external:
                continue

            self.fd.write("\t")
            self.fd.write(_get_wat_function_decl_spec(function))
            self.fd.write("\n")

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
                self.write_instr(f"i64.const {op.operand}")
            case OperatorType.ARITHMETIC_PLUS:
                self.write_instr("i64.add")
            case OperatorType.PUSH_FLOAT:
                assert isinstance(op.operand, float)
                self.write_instr(f"f64.const {op.operand}")
            case OperatorType.STACK_DROP:
                self.write_instr("drop")
            case OperatorType.INLINE_RAW_ASM:
                assert isinstance(op.operand, str)
                self.write_instr(op.operand)
            case OperatorType.ARITHMETIC_MULTIPLY:
                self.write_instr("i64.mul")
            case OperatorType.ARITHMETIC_MINUS:
                self.write_instr("i64.sub")
            case OperatorType.BITWISE_AND:
                self.write_instr("i64.and")
            case OperatorType.BITWISE_OR:
                self.write_instr("i64.or")
            case OperatorType.BITWISE_XOR:
                self.write_instr("i64.xor")
            case OperatorType.FUNCTION_CALL:
                assert isinstance(op.operand, FunctionCallOperand)
                assert op.operand.module is None
                self.write_instr(f"call ${op.operand.func_name}")
            case OperatorType.FUNCTION_RETURN:
                self.write_instr("return")
            case OperatorType.SYSCALL:
                msg = f"Syscall at {op.location} is not supported by WASM target, please use system function calls!"
                raise ValueError(msg)
            case OperatorType.DEBUGGER_BREAKPOINT:
                self.write_instr("unreachable")
            case OperatorType.COMPILE_TIME_ERROR | OperatorType.STATIC_TYPE_CAST:
                ...
            case OperatorType.STRUCT_FIELD_OFFSET:
                assert isinstance(op.operand, tuple)
                struct, field = op.operand
                field_offset = struct.get_field_offset(field)
                if field_offset:
                    # only relatable as operation is pointer is not already at first structure field
                    self.write_instr(f"i64.const {field_offset}")
                    self.write_instr("i64.add\n")

            case OperatorType.PUSH_VARIABLE_VALUE:
                assert isinstance(op.operand, str)
                if op.operand not in owner_function.variables:
                    sym_var = self.module.variables[op.operand]
                    if sym_var.is_constant:
                        self.write_instr(f"global.get ${op.operand}")
                    else:
                        offset = self.symtable[op.operand]
                        self.write_instr(
                            f"i32.const {offset} ;; symtable offset sym={op.operand}",
                        )
                        sym_t = wasm_type_from_primitive(sym_var.type)
                        self.write_instr(f"{sym_t}.load")
                else:
                    raise NotImplementedError

            case OperatorType.PUSH_VARIABLE_ADDRESS:
                assert isinstance(op.operand, str)
                offset = self.symtable[op.operand]
                self.write_instr(
                    f"i64.const {offset} ;; symtable offset sym={op.operand}",
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
                self.write_instr(f"i64.const {offset} ;; symtable offset string")
            case OperatorType.STACK_SWAP:
                self.write_instr("call $swap")
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


def _get_wat_global_symbol_decl_spec(var: Variable[Type]) -> SExpr:
    wat_t = wasm_type_from_primitive(var.type)
    sym_type_spec = wat_t if var.is_constant else SExpr("mut", wat_t)

    assert var.is_global_scope
    assert var.initial_value is not None, f"uninitialized symbol {var.name} for WASM"

    match var.initial_value:
        case int():
            value = SExpr("i64.const", var.initial_value)
            return SExpr("global", f"${var.name}", sym_type_spec, value)
        case _:
            msg = f"Cannot define global symbol in wasm with default value {var.initial_value}, not implemented unwinding constant Initializers."
            raise NotImplementedError(msg)


def _get_wat_function_decl_spec(function: Function) -> str:
    decl = _get_wasm_internal_function_decl_spec(function)

    if function.is_external:
        extern_from_module = "env"
        decl = SExpr("import", f'"{extern_from_module}"', f'"{function.name}"', decl)

    e = decl.build()
    if not function.is_external:
        e = e[:-1]
    return e


def _get_wasm_internal_function_decl_spec(function: Function) -> SExpr:
    decl = SExpr("func", f"${function.name}")

    if function.is_public:
        decl.add_node(SExpr("export", f'"{function.name}"'))

    if function.parameters:
        # TODO: WAT/WASM allows named function params
        param_spec = [wasm_type_from_primitive(param) for param in function.parameters]
        decl.add_node(SExpr("param", " ".join(param_spec)))

    if function.has_return_value():
        assert function.return_type.size_in_bytes <= 8
        return_type = wasm_type_from_primitive(function.return_type)
        decl.add_node(SExpr("result", return_type))

    return decl
