from gofra.feature_flags import FEATURE_DEREFERENCE_VARIABLES_BY_DEFAULT
from gofra.hir.operator import OperatorType
from gofra.hir.variable import Variable, VariableScopeClass, VariableStorageClass
from gofra.lexer.tokens import Token, TokenType
from gofra.parser._context import ParserContext
from gofra.parser.exceptions import ParserVariableNameAlreadyDefinedAsVariableError
from gofra.parser.types import parser_type_from_tokenizer
from gofra.types.composite.array import ArrayType
from gofra.types.composite.structure import StructureType


def get_all_scopes_variables(
    child: ParserContext,
) -> list[Variable]:
    context_ref = child
    variables: list[Variable] = []
    while True:
        variables.extend(context_ref.variables.values())

        if context_ref.parent:
            context_ref = context_ref.parent
            continue

        return variables


def unpack_variable_definition_from_token(
    context: ParserContext,
) -> None:
    varname_token = context.next_token()
    if varname_token.type != TokenType.IDENTIFIER:
        msg = "Expected variable name after variable keyword"
        raise ValueError(msg)
    assert isinstance(varname_token.value, str)

    typename = parser_type_from_tokenizer(context)
    varname = varname_token.text

    if varname in context.variables:
        raise ParserVariableNameAlreadyDefinedAsVariableError(
            token=varname_token,
            name=varname,
        )

    if context.name_is_already_taken(varname):
        msg = f"Variable name {varname} is already taken by other definition"
        raise ValueError(msg)

    storage_class = (
        VariableStorageClass.STATIC
        if context.is_top_level
        else VariableStorageClass.STACK
    )
    scope_class = (
        VariableScopeClass.GLOBAL
        if context.is_top_level
        else VariableScopeClass.FUNCTION
    )
    context.variables[varname] = Variable(
        name=varname,
        type=typename,
        defined_at=varname_token.location,
        scope_class=scope_class,
        storage_class=storage_class,
    )


def try_push_variable_reference(context: ParserContext, token: Token) -> bool:
    assert token.type == TokenType.IDENTIFIER

    varname = token.text

    is_reference = not FEATURE_DEREFERENCE_VARIABLES_BY_DEFAULT
    array_index_at = None
    struct_field_accessor = None

    if varname.startswith("&"):
        is_reference = True
        varname = varname.removeprefix("&")

    if context.peek_token().type == TokenType.LBRACKET:
        _ = context.next_token()  # Consume LBRACKET

        elements_token = context.next_token()
        if elements_token.type != TokenType.INTEGER:
            msg = (
                f"Expected array index inside of [], but got {elements_token.type.name}"
            )
            raise ValueError(msg)

        rbracket = context.next_token()
        if rbracket.type != TokenType.RBRACKET:
            msg = f"Expected RBRACKET after array index element qualifier but got {rbracket.type.name}"
            raise ValueError(msg)

        assert isinstance(elements_token.value, int)
        array_index_at = elements_token.value

    accessor_token = context.peek_token()
    if (
        accessor_token.type == TokenType.DOT
        and not accessor_token.has_trailing_whitespace
    ):
        _ = context.next_token()  # Consume DOT
        if array_index_at is not None:
            msg = "Referencing an field from an struct within array accessor is not implemented yet."
            raise NotImplementedError(msg)
        struct_field_accessor = context.next_token()
        if struct_field_accessor.type != TokenType.IDENTIFIER:
            msg = f"Expected struct field accessor to be an identifier, but got {struct_field_accessor.type.name}"
            raise ValueError(msg)

    variable = context.search_variable_in_context_parents(varname)
    if not variable:
        return False

    context.push_new_operator(
        type=OperatorType.PUSH_VARIABLE_ADDRESS,
        token=token,
        operand=varname,
    )

    if struct_field_accessor:
        if not is_reference:
            msg = "Struct field accessors are implemented only for references."
            raise NotImplementedError(msg)
        if not isinstance(variable.type, StructureType):
            msg = "cannot get field-offset-of (e.g .field) for non-structure types."
            raise ValueError(msg)

        field = struct_field_accessor.text
        if field not in variable.type.fields:
            msg = f"Field accessor {field} at {token.location} is unknown for structure {variable.type.name}"
            raise ValueError(msg)

        context.push_new_operator(
            type=OperatorType.STRUCT_FIELD_OFFSET,
            token=token,
            operand=f"{variable.type.name}.{field}",
        )

    if array_index_at is not None:
        if not isinstance(variable.type, ArrayType):
            msg = "cannot get index-of (e.g []) for non-array types."
            raise ValueError(msg)

        if array_index_at < 0:
            msg = "Negative indexing inside arrays is prohibited"
            raise ValueError(msg)

        if variable.type.is_index_oob(array_index_at):
            msg = f"OOB (out-of-bounds) for array access `{token.text}` at {token.location}, array has {variable.type.elements_count} elements"
            raise ValueError(msg)

        shift_in_bytes = variable.type.get_index_offset(array_index_at)
        if shift_in_bytes:
            context.push_new_operator(
                type=OperatorType.PUSH_INTEGER,
                token=token,
                operand=shift_in_bytes,
            )
            context.push_new_operator(
                type=OperatorType.ARITHMETIC_PLUS,
                token=token,
            )

    if not is_reference:
        context.push_new_operator(
            type=OperatorType.MEMORY_VARIABLE_READ,
            token=token,
        )
    return True
