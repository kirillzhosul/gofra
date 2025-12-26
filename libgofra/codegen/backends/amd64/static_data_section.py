from collections.abc import Mapping

from libgofra.codegen.backends.amd64._context import AMD64CodegenContext
from libgofra.codegen.sections._factory import SectionType
from libgofra.hir.variable import Variable
from libgofra.types._base import PrimitiveType, Type
from libgofra.types.primitive.character import CharType
from libgofra.types.primitive.integers import I64Type


def initialize_static_data_section(
    context: AMD64CodegenContext,
    static_strings: Mapping[str, str],
    static_variables: Mapping[str, Variable[Type]],
) -> None:
    """Initialize data section fields with given values.

    Section is an tuple (label, data)
    Data is an string (raw ASCII) or number (zeroed memory blob)
    TODO(@kirillzhosul, @stepanzubkov): Review alignment for data sections.
    """
    write_uninitialized_data_section(context, static_variables)
    write_initialized_data_section(context, static_strings, static_variables)
    # Must defined after others - string initializer may forward reference them
    # but we define them by single-pass within writing initializer
    write_text_string_section(context, static_strings, reference_suffix="d")


def write_initialized_data_section(
    context: AMD64CodegenContext,
    strings: Mapping[str, str],
    variables: Mapping[str, Variable[Type]],
) -> None:
    """Initialize data section fields with given values.

    Section is an tuple (label, data)
    Data is an string (raw ASCII) or number (zeroed memory blob)
    """
    variables = {k: v for k, v in variables.items() if v.initial_value is not None}

    if not variables and not strings:
        return

    context.section(SectionType.DATA)

    for name, variable in variables.items():
        _write_static_segment_const_variable_initializer(
            context,
            variable,
            symbol_name=name,
        )

    for name, data in strings.items():
        # TODO: Proper alignment
        decoded_string = data.encode().decode("unicode_escape")
        length = len(decoded_string)
        context.fd.write(f"{name}: \n\t.quad {name}d\n\t.quad {length}\n")


def _get_ddd_for_type(t: PrimitiveType) -> str:
    """Get Data Definition Directive for type based on byte size."""
    type_size = t.size_in_bytes
    if type_size <= 1:
        return ".byte"
    if type_size <= 2:
        return ".value"
    if type_size <= 4:
        return ".long"
    if type_size <= 8:
        return ".quad"
    msg = f"Cannot get DDD for symbol of type {t}, max byte size is capped"
    raise ValueError(msg)


def _write_static_segment_const_variable_initializer(
    context: AMD64CodegenContext,
    variable: Variable[Type],
    symbol_name: str,
) -> None:
    _ = context
    type_size = variable.size_in_bytes

    assert variable.initial_value is not None
    match variable.type:
        case CharType() | I64Type():
            assert isinstance(variable.initial_value, int)
            if type_size == 0:
                context.on_warning(
                    f"Variable {variable.name} has zero byte size (type {variable.type}) this variable will be not defined as symbol!",
                )
                return
            # TODO(@kirillzhosul): review realignment of static variables
            ddd = _get_ddd_for_type(variable.type)
            context.fd.write(f"{symbol_name}: {ddd} {variable.initial_value}\n")
        case _:
            msg = f"Has no known initializer codegen logic for type {variable.type}"
            raise ValueError(msg)


def write_uninitialized_data_section(
    context: AMD64CodegenContext,
    variables: Mapping[str, Variable[Type]],
) -> None:
    """Emit data section with uninitialized variables."""
    uninitialized_variables = {
        k: v for k, v in variables.items() if v.initial_value is None
    }

    if not uninitialized_variables:
        return

    context.section(SectionType.BSS)
    for name, variable in uninitialized_variables.items():
        type_size = variable.size_in_bytes
        assert type_size, f"Variables must have size (from {variable.name})"
        context.fd.write(f"{name}: .space {type_size}\n")


def write_text_string_section(
    context: AMD64CodegenContext,
    strings: Mapping[str, str],
    *,
    reference_suffix: str,
) -> None:
    """Emit text section with pure string text.

    :param reference_suffix: Append to each string symbol as it may overlap with real structure of string.
    """
    if not strings:
        return
    context.section(SectionType.STRINGS)
    for name, data in strings.items():
        context.fd.write(f'{name}{reference_suffix}: .asciz "{data}"\n')
