from gofra.hir.operator import OperatorType
from gofra.lexer.keywords import Keyword
from gofra.lexer.tokens import Token
from gofra.parser._context import ParserContext
from gofra.parser.exceptions import (
    ParserEmptyIfBodyError,
    ParserEndAfterWhileError,
    ParserEndWithoutContextError,
    ParserNoWhileBeforeDoError,
    ParserNoWhileConditionOperatorsError,
)


def consume_conditional_block_keyword_from_token(
    context: ParserContext,
    token: Token,
) -> None:
    assert isinstance(token.value, Keyword)
    match token.value:
        case Keyword.IF:
            return context.push_new_operator(
                type=OperatorType.CONDITIONAL_IF,
                token=token,
                operand=None,
                is_contextual=True,
            )
        case Keyword.DO:
            if not context.has_context_stack():
                raise ParserNoWhileBeforeDoError(do_token=token)

            operator_while_idx, context_while = context.pop_context_stack()
            if context_while.type != OperatorType.CONDITIONAL_WHILE:
                raise ParserNoWhileBeforeDoError(do_token=token)

            while_condition_len = context.current_operator - operator_while_idx - 1
            if while_condition_len == 0:
                raise ParserNoWhileConditionOperatorsError(
                    while_token=context_while.token,
                )

            context.push_new_operator(
                type=OperatorType.CONDITIONAL_DO,
                token=token,
                operand=None,
                is_contextual=True,
            )
            context.operators[-1].jumps_to_operator_idx = operator_while_idx
            return None
        case Keyword.WHILE:
            return context.push_new_operator(
                type=OperatorType.CONDITIONAL_WHILE,
                token=token,
                operand=None,
                is_contextual=True,
            )
        case Keyword.END:
            if not context.has_context_stack():
                raise ParserEndWithoutContextError(end_token=token)

            context_operator_idx, context_operator = context.pop_context_stack()

            context.push_new_operator(
                type=OperatorType.CONDITIONAL_END,
                token=token,
                operand=None,
                is_contextual=False,
            )
            prev_context_jumps_at = context_operator.jumps_to_operator_idx
            context_operator.jumps_to_operator_idx = context.current_operator - 1

            match context_operator.type:
                case OperatorType.CONDITIONAL_DO:
                    context.operators[-1].jumps_to_operator_idx = prev_context_jumps_at
                case OperatorType.CONDITIONAL_IF:
                    if_body_size = context.current_operator - context_operator_idx - 2
                    if if_body_size == 0:
                        raise ParserEmptyIfBodyError(if_token=context_operator.token)
                case OperatorType.CONDITIONAL_WHILE:
                    raise ParserEndAfterWhileError(end_token=token)
                case _:
                    raise AssertionError

            return None
        case _:
            raise AssertionError
