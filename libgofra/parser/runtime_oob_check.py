from libgofra.feature_flags import (
    FEATURE_RUNTIME_ARRAY_OOB_CHECKS,
)
from libgofra.hir.operator import OperatorType
from libgofra.hir.variable import (
    Variable,
)
from libgofra.lexer.tokens import Token, TokenType
from libgofra.parser._context import ParserContext
from libgofra.types.primitive.integers import I64Type


def emit_runtime_hir_oob_check(
    context: ParserContext,
    token: Token,
    index_var: Variable[I64Type],
    elements_const: int,
) -> None:
    """Push operators to perform OOB check at runtime.

    TODO(@kirillzhosul): Must be reworked into runtime lib?:
    Possibly introduce runtime include library, should requires via something like `require_runtime_function`
    """
    assert FEATURE_RUNTIME_ARRAY_OOB_CHECKS
    if "eprint_fatal" not in context.functions:
        msg = "Cannot do FEATURE_RUNTIME_ARRAY_OOB_CHECKS unless stdlib (`eprint_fatal`) is available for panic"
        raise ValueError(msg)
    panic_msg = "Runtime OOB error: tried to access array with out-of-bounds index, step into debugger for help!\\n"
    context.push_new_operator(
        OperatorType.PUSH_VARIABLE_VALUE,
        token,
        operand=index_var.name,
    )
    context.push_new_operator(
        OperatorType.PUSH_INTEGER,
        operand=elements_const,
        token=token,
    )
    context.push_new_operator(OperatorType.COMPARE_GREATER_EQUALS, token)
    context.push_new_operator(OperatorType.CONDITIONAL_IF, token, is_contextual=True)
    if True:
        context.push_new_operator(
            OperatorType.PUSH_STRING,
            operand=panic_msg,
            token=Token(
                type=TokenType.STRING,
                text=f'"{panic_msg}"',
                value=panic_msg,
                location=token.location,
            ),
        )
        context.push_new_operator(
            OperatorType.FUNCTION_CALL,
            token=token,
            operand="eprint_fatal",
        )
    context.push_new_operator(OperatorType.CONDITIONAL_END, token=token)
    _, if_op, _ = context.pop_context_stack()
    if_op.jumps_to_operator_idx = context.current_operator - 1
