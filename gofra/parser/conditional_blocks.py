from dataclasses import dataclass
from typing import Literal, cast

from gofra.hir.operator import OperatorType
from gofra.hir.variable import Variable, VariableScopeClass, VariableStorageClass
from gofra.lexer.keywords import Keyword
from gofra.lexer.tokens import Token, TokenType
from gofra.parser._context import ParserContext
from gofra.parser.exceptions import (
    ParserEmptyIfBodyError,
    ParserEndAfterWhileError,
    ParserEndWithoutContextError,
    ParserNoWhileConditionOperatorsError,
    ParserNoWhileOrForBeforeDoError,
)
from gofra.types._base import Type
from gofra.types.composite.array import ArrayType
from gofra.types.composite.pointer import PointerType
from gofra.types.primitive.integers import I64Type


@dataclass(frozen=True, slots=True)
class RangeQualifierForeach:
    iterator: Variable[Type]
    iterable: Variable[ArrayType]
    step: Literal[1] = 1


@dataclass(frozen=True, slots=True)
class RangeQualifierRange:
    iterator: Variable[Type]
    a: int
    b: int | Variable[Type]
    step: int = 1


type RangeQualifier = RangeQualifierForeach | RangeQualifierRange


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
                is_contextual=True,
            )
        case Keyword.DO:
            if not context.has_context_stack():
                raise ParserNoWhileOrForBeforeDoError(do_token=token)

            operator_while_idx, context_loop, compiler_loop_metadata = (
                context.pop_context_stack()
            )
            if context_loop.type not in (
                OperatorType.CONDITIONAL_WHILE,
                OperatorType.CONDITIONAL_FOR,
            ):
                raise ParserNoWhileOrForBeforeDoError(do_token=token)

            # Code below was used to deal with while only
            # but we introduced `for` and this code is not modified
            # By logic this code works but requires refactoring and proper error messages
            loop_condition_len = context.current_operator - operator_while_idx - 1
            if loop_condition_len == 0:
                # TODO(@kirillzhosul): Allow to specify/treat this as an warning or something like that
                # as this prevents UB and not a proper error
                raise ParserNoWhileConditionOperatorsError(
                    while_token=context_loop.token,
                )

            context.push_new_operator(
                type=OperatorType.CONDITIONAL_DO,
                token=token,
                is_contextual=True,
            )
            if context_loop.type == OperatorType.CONDITIONAL_FOR:
                # Propagate compiler metadata on for iterator
                # to the `do` block so `end` can spill syntactical sugar
                loop_context = context.pop_context_stack()
                context.context_stack.append(
                    (*loop_context[:2], compiler_loop_metadata),
                )
            context.operators[-1].jumps_to_operator_idx = operator_while_idx
            return None
        case Keyword.WHILE:
            return context.push_new_operator(
                type=OperatorType.CONDITIONAL_WHILE,
                token=token,
                is_contextual=True,
            )
        case Keyword.FOR:
            qualifier = parse_for_range_qualifier(context, token)
            context.expect_token(TokenType.KEYWORD)
            # TODO(@kirillzhosul): Mostly requires reworking HIR into single HIR load-and-store instruction
            # Code below adds some syntactical sugar which is inlined here

            return unwrap_for_operators_syntactical_sugar(
                context,
                token,
                qualifier=qualifier,
            )
        case Keyword.END:
            if not context.has_context_stack():
                raise ParserEndWithoutContextError(end_token=token)

            context_operator_idx, context_operator, loop_compiler_metadata = (
                context.pop_context_stack()
            )

            if context_operator.type == OperatorType.CONDITIONAL_DO:
                assert context_operator.jumps_to_operator_idx is not None
                loop_block_start = context.operators[
                    context_operator.jumps_to_operator_idx
                ]
                if loop_block_start.type == OperatorType.CONDITIONAL_FOR:
                    assert loop_compiler_metadata

                    # Here we have compiler metadata for `for` loop syntactical sugar
                    qualifier = loop_compiler_metadata

                    assert qualifier.step != 0, (
                        "Step must be non-zero as being implicit infinite loop"
                    )
                    if isinstance(qualifier, RangeQualifierRange):
                        step_abs = abs(qualifier.step)
                        step_op = (
                            OperatorType.ARITHMETIC_PLUS
                            if qualifier.step > 0
                            else OperatorType.ARITHMETIC_MINUS
                        )
                        # Gofra: `&iterator iterator 1 + !<`
                        context.push_new_operator(
                            OperatorType.PUSH_VARIABLE_ADDRESS,
                            token=token,
                            operand=qualifier.iterator.name,
                        )
                        operators_read_sint64_variable(
                            context,
                            token,
                            variable=qualifier.iterator,
                        )
                        context.push_new_operator(
                            OperatorType.PUSH_INTEGER,
                            token=token,
                            operand=step_abs,
                        )
                        context.push_new_operator(step_op, token)
                        context.push_new_operator(
                            OperatorType.MEMORY_VARIABLE_WRITE,
                            token,
                        )
                    else:
                        assert qualifier.step == 1
                        context.push_new_operator(
                            OperatorType.PUSH_VARIABLE_ADDRESS,
                            token=token,
                            operand=qualifier.iterator.name,
                        )
                        context.push_new_operator(
                            OperatorType.PUSH_VARIABLE_ADDRESS,
                            token=token,
                            operand=qualifier.iterator.name,
                        )
                        context.push_new_operator(
                            OperatorType.MEMORY_VARIABLE_READ,
                            token=token,
                        )
                        context.push_new_operator(
                            OperatorType.PUSH_INTEGER,
                            token=token,
                            operand=qualifier.iterable.type.element_type.size_in_bytes,
                        )
                        context.push_new_operator(OperatorType.ARITHMETIC_PLUS, token)
                        context.push_new_operator(
                            OperatorType.MEMORY_VARIABLE_WRITE,
                            token,
                        )
            context.push_new_operator(
                type=OperatorType.CONDITIONAL_END,
                token=token,
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


def parse_for_range_qualifier(
    context: ParserContext,
    token: Token,
) -> RangeQualifier:
    iterator_identifier = context.next_token()
    if iterator_identifier.type != TokenType.IDENTIFIER:
        msg = f"For loop expected identifier as iterator after `for` but got {iterator_identifier.type} at {iterator_identifier.location}"
        raise ValueError(msg)

    iterator_varname = iterator_identifier.text
    if context.name_is_already_taken(iterator_varname):
        conflicting_variable = context.search_variable_in_context_parents(
            iterator_varname,
        )
        assert conflicting_variable
        if not isinstance(conflicting_variable.type, I64Type):
            # TODO(@kirillzhosul): Saying about i64 but may be back-patched
            msg = f"For loop iterator {iterator_varname} used at {token.location} has conflict with variable of same name that has type {conflicting_variable.type}, if you use variable as iterator which is defined, its type must be an I64, otherwise use another name."
            raise ValueError(msg)
    else:
        context.variables[iterator_varname] = Variable(
            name=iterator_varname,
            defined_at=iterator_identifier.location,
            storage_class=VariableStorageClass.STACK,
            scope_class=VariableScopeClass.FUNCTION,
            type=I64Type(),
        )

    iterator = context.variables[iterator_varname]
    in_token = context.next_token()
    if in_token.type != TokenType.KEYWORD or in_token.value != Keyword.IN:
        msg = f"Expected `IN` keyword in for block but got {in_token.type} at {in_token.location}"
        raise ValueError(msg)

    # Consume range qualifier

    # TODO(@kirillzhosul): Requires more generic refactor

    if context.peek_token().type == TokenType.IDENTIFIER:
        iterable_identifier_tok = context.next_token()
        if _peek_for_dot_dot_syntax(context):
            context.push_token_back_upfront_peeked(iterable_identifier_tok)
            range_from_qualifier_name = context.next_token().text

            range_from_qualifier = context.search_variable_in_context_parents(
                range_from_qualifier_name,
            )
            if not range_from_qualifier:
                msg = f"Unknown variable `{range_from_qualifier}` in `for-loop` block."
                raise ValueError(msg)
            if not isinstance(range_from_qualifier.type, (I64Type, ArrayType)):
                msg = f"Expected `{range_from_qualifier_name}` to be an I64/Array type but got {range_from_qualifier.type} in `for-loop` block at {in_token.location}, as it used as range qualifier bounds."
                raise ValueError(msg)
        else:
            iterable_identifier_name = iterable_identifier_tok.text

            iterable_identifier = context.search_variable_in_context_parents(
                iterable_identifier_name,
            )

            if not iterable_identifier:
                msg = f"Unknown variable `{iterable_identifier}` in `for-loop` block used as iterable at {iterable_identifier_tok.location}."
                raise ValueError(msg)
            if iterable_identifier.storage_class == VariableStorageClass.STACK:
                msg = "Prohibited to use stack located iterable, currently leads to segmentation faults"
                raise ValueError(msg)
            if not isinstance(iterable_identifier.type, ArrayType):
                msg = f"Expected `{iterable_identifier_name}` to be an Array type but got {iterable_identifier.type} in `for-loop` block at {in_token.location}, as it used as range qualifier iterable."
                raise ValueError(msg)
            iterable_identifier = cast("Variable[ArrayType]", iterable_identifier)
            assert iterable_identifier.type.element_type.size_in_bytes == 8, (
                "Expected iterable that has elements of byte size 8 only"
            )

            # Back-patch iterator defined before as now we know that we iterate array
            context.variables[iterator_varname] = Variable(
                name=iterator_varname,
                defined_at=iterator_identifier.location,
                storage_class=VariableStorageClass.STACK,
                scope_class=VariableScopeClass.FUNCTION,
                type=PointerType(points_to=iterable_identifier.type.element_type),
            )

            return RangeQualifierForeach(
                iterator=iterator,
                iterable=iterable_identifier,
            )

    elif context.peek_token().type != TokenType.INTEGER:
        msg = f"For loop at {in_token.location} expects integer or identifier as range qualifier but got {context.peek_token().type}"
        raise ValueError(msg)

    step = 1
    # Probably - an range qualifier (`x..n`)
    # at least currently only this is allowed
    range_from_qualifier = cast("int", (context.next_token().value))
    _consume_dot_dot_syntax(context)
    if context.peek_token().type == TokenType.INTEGER:
        range_to_qualifier = cast("int", (context.next_token().value))
        step = 1 if range_to_qualifier >= range_from_qualifier else -1
    elif context.peek_token().type == TokenType.IDENTIFIER:
        range_to_qualifier_name = context.next_token().text

        range_to_qualifier = context.search_variable_in_context_parents(
            range_to_qualifier_name,
        )
        if not range_to_qualifier:
            msg = f"Unknown variable `{range_to_qualifier_name}` in `for-loop` block."
            raise ValueError(msg)
        if not isinstance(range_to_qualifier.type, (I64Type, ArrayType)):
            msg = f"Expected `{range_to_qualifier_name}` to be an I64/Array type but got {range_to_qualifier.type} in `for-loop` block at {in_token.location}, as it used as range qualifier bounds."
            raise ValueError(msg)

    else:
        msg = "Either integer or identifier expected, but got here somehow, unreachable"
        raise ValueError(msg)

    return RangeQualifierRange(
        iterator=iterator,
        a=range_from_qualifier,
        b=range_to_qualifier,
        step=step,
    )


def _consume_dot_dot_syntax(context: ParserContext) -> None:
    context.expect_token(TokenType.DOT)
    context.next_token()
    context.expect_token(TokenType.DOT)
    context.next_token()


def _peek_for_dot_dot_syntax(context: ParserContext) -> bool:
    """Check if next tokens are containing `..` (dot-dot) syntax."""
    dot_t1 = context.next_token()
    if dot_t1.type != TokenType.DOT:
        context.push_token_back_upfront_peeked(dot_t1)
        return False

    dot_t2 = context.next_token()
    if dot_t2.type != TokenType.DOT:
        context.push_token_back_upfront_peeked(dot_t1)
        context.push_token_back_upfront_peeked(dot_t2)
        return False

    context.push_token_back_upfront_peeked(dot_t1)
    context.push_token_back_upfront_peeked(dot_t2)
    return True


def unwrap_for_operators_syntactical_sugar(
    context: ParserContext,
    token: Token,
    qualifier: RangeQualifier,
) -> None:
    assert qualifier.step != 0, "Step must be non-zero as being implicit infinite loop"
    if isinstance(qualifier, RangeQualifierRange):
        a = qualifier.a
        b = qualifier.b
        step = qualifier.step

        # Initializer block: Set initial value for iterator
        operators_set_sint64_variable(
            context,
            token,
            value=a,
            variable=qualifier.iterator,
        )

        context.push_new_operator(
            OperatorType.CONDITIONAL_FOR,
            token,
            is_contextual=True,
        )
        loop_context = context.pop_context_stack()
        context.context_stack.append((*loop_context[:2], qualifier))

        operators_read_sint64_variable(context, token, variable=qualifier.iterator)

        if isinstance(b, Variable):
            if isinstance(b.type, I64Type):
                operators_read_sint64_variable(context, token, variable=b)
            else:
                assert isinstance(b.type, ArrayType)
                context.push_new_operator(
                    OperatorType.PUSH_INTEGER,
                    token=token,
                    operand=b.type.elements_count,
                )
        else:
            context.push_new_operator(
                OperatorType.PUSH_INTEGER,
                token=token,
                operand=b,
            )

        compare_op = (
            OperatorType.COMPARE_LESS if step > 0 else OperatorType.COMPARE_GREATER
        )
        context.push_new_operator(compare_op, token=token)
        return
    assert isinstance(qualifier, RangeQualifierForeach)

    # Initializer block: Set initial value for iterator
    # For for-each it is idx = *iterable
    context.push_new_operator(
        OperatorType.PUSH_VARIABLE_ADDRESS,
        token=token,
        operand=qualifier.iterator.name,
    )

    context.push_new_operator(
        OperatorType.PUSH_VARIABLE_ADDRESS,
        token=token,
        operand=qualifier.iterable.name,
    )
    context.push_new_operator(
        OperatorType.MEMORY_VARIABLE_WRITE,
        token=token,
    )

    context.push_new_operator(
        OperatorType.CONDITIONAL_FOR,
        token,
        is_contextual=True,
    )
    loop_context = context.pop_context_stack()
    context.context_stack.append((*loop_context[:2], qualifier))

    context.push_new_operator(
        OperatorType.PUSH_VARIABLE_ADDRESS,
        token=token,
        operand=qualifier.iterator.name,
    )
    context.push_new_operator(
        OperatorType.MEMORY_VARIABLE_READ,
        token=token,
    )
    context.push_new_operator(
        OperatorType.STATIC_TYPE_CAST,
        token=token,
        operand=I64Type(),
    )

    assert isinstance(qualifier.iterable.type, ArrayType)
    # *X (X is array type), iterator as pointer within iterable
    context.push_new_operator(
        OperatorType.PUSH_VARIABLE_ADDRESS,
        token=token,
        operand=qualifier.iterable.name,
    )

    # *X and *X but first must be already advanced as being an iterator
    iterable_t = qualifier.iterable.type
    end_of_array_offset = iterable_t.element_type.size_in_bytes * (
        iterable_t.elements_count
    )
    context.push_new_operator(
        OperatorType.PUSH_INTEGER,
        token=token,
        operand=end_of_array_offset,
    )
    context.push_new_operator(OperatorType.ARITHMETIC_PLUS, token=token)
    assert qualifier.step == 1
    context.push_new_operator(
        OperatorType.STATIC_TYPE_CAST,
        token=token,
        operand=I64Type(),
    )

    # Compares *X and *X (second must be greater until we reached end of array memory blob)
    context.push_new_operator(OperatorType.COMPARE_LESS, token=token)
    return
    # Requires syntactical sugar to be added to the close context block


def operators_read_sint64_variable(
    context: ParserContext,
    token: Token,
    variable: Variable[Type],
) -> None:
    """Write operators to read specified variable onto stack."""
    # TODO(@kirillzhosul): This probably must form new HIR operation after we rework memory I/O and other stuff
    context.push_new_operator(
        OperatorType.PUSH_VARIABLE_ADDRESS,
        token=token,
        operand=variable.name,
    )
    context.push_new_operator(
        OperatorType.MEMORY_VARIABLE_READ,
        token=token,
    )


def operators_set_sint64_variable(
    context: ParserContext,
    token: Token,
    value: int,
    variable: Variable[Type],
) -> None:
    """Write operators to set specified variable given value."""
    # TODO(@kirillzhosul): This probably must form new HIR operation after we rework memory I/O and other stuff
    context.push_new_operator(
        OperatorType.PUSH_VARIABLE_ADDRESS,
        token=token,
        operand=variable.name,
    )
    context.push_new_operator(
        OperatorType.PUSH_INTEGER,
        token=token,
        operand=value,
    )
    context.push_new_operator(
        OperatorType.MEMORY_VARIABLE_WRITE,
        token=token,
    )
