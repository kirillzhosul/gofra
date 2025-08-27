from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.consts import GOFRA_ENTRY_POINT
from gofra.exceptions import GofraError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from gofra.lexer.tokens import Token, TokenLocation
    from gofra.parser.functions.function import FunctionTypeContract


class ParserDirtyNonPreprocessedTokenError(GofraError):
    def __init__(self, *args: object, token: Token) -> None:
        super().__init__(*args)
        self.token = token

    def __repr__(
        self,
    ) -> str:
        return f"""Got dirty non preprocessed token from tokenizer at parser stage.

`{self.token.text}` at {self.token.location}

Probably this is not an language user fault.
Did you forgot to call preprocessor stage to resolve these dirty tokens?"""


class ParserExhaustiveContextStackError(GofraError):
    def __repr__(self) -> str:
        return """Exhaustive context stack!
All context blocks should be folded at the end

Do you have not closed block?"""


class ParserUnfinishedWhileDoBlockError(GofraError):
    def __init__(self, *args: object, token: Token) -> None:
        super().__init__(*args)
        self.token = token

    def __repr__(self) -> str:
        return f"""Unclosed 'while ... do' block at {self.token.location}!
Expected there will be 'end' block after 'do' and 'do' after 'while'.

Did you forgot to open/close 'do' block?"""


class ParserUnfinishedIfBlockError(GofraError):
    def __init__(self, *args: object, if_token: Token) -> None:
        super().__init__(*args)
        self.if_token = if_token

    def __repr__(self) -> str:
        return f"""Unclosed 'if' block at {self.if_token.location}!
Expected there will be 'end' block after 'if'.

Did you forgot to close 'if' block?"""


class ParserUnknownWordError(GofraError):
    def __init__(
        self,
        *args: object,
        word_token: Token,
        macro_names: Iterable[str],
        best_match: str | None = None,
    ) -> None:
        super().__init__(*args)
        self.word_token = word_token
        self.macro_names = macro_names
        self.best_match = best_match

    def __repr__(self) -> str:
        return f"""Encountered an unknown name '{self.word_token.text}' at {self.word_token.location}!
Expected intrinsic or macro name.

Available macro names: {", ".join(self.macro_names) or "..."}""" + (
            f"\nDid you mean '{self.best_match}'?" if self.best_match else ""
        )


class ParserNoWhileBeforeDoError(GofraError):
    def __init__(self, *args: object, do_token: Token) -> None:
        super().__init__(*args)
        self.do_token = do_token

    def __repr__(self) -> str:
        return f"""No 'while' before 'do' at {self.do_token.location}!
Expected there will be 'while' block before 'do'.

Did you forgot to add starting block?"""


class ParserEndAfterWhileError(GofraError):
    def __init__(self, *args: object, end_token: Token) -> None:
        super().__init__(*args)
        self.end_token = end_token

    def __repr__(self) -> str:
        return f"""'end' after 'while' block  at {self.end_token.location}!
Expected there will be 'do' block after 'while'.

Did you forgot to add 'do' block?"""


class ParserEndWithoutContextError(GofraError):
    def __init__(self, *args: object, end_token: Token) -> None:
        super().__init__(*args)
        self.end_token = end_token

    def __repr__(self) -> str:
        return f"""'end' used without context at {self.end_token.location}!
Expected there will be context block before 'end'.

Did you forgot to add context block?"""


class ParserNoWhileConditionOperatorsError(GofraError):
    def __init__(self, *args: object, while_token: Token) -> None:
        super().__init__(*args)
        self.while_token = while_token

    def __repr__(self) -> str:
        return f"""'while ... do' used without condition inside at {self.while_token.location}!
Expected there will be at least something in condition before 'do'.
This will lead to infinite loop, which may cause undefined behavior.
Please use 'while true do .. end' if this is your intense.

Did you forgot to add condition?"""


class ExternNoFunctionNameError(GofraError):
    def __init__(self, *args: object, macro_token: Token) -> None:
        super().__init__(*args)
        self.macro_token = macro_token

    def __repr__(self) -> str:
        return f"""No 'extern' function name specified at {self.macro_token.location}!
Extern functions should have name after 'extern' keyword

Do you have unfinished extern function definition?"""


class ParserExternNonWordNameError(GofraError):
    def __init__(self, *args: object, function_name_token: Token) -> None:
        super().__init__(*args)
        self.function_name_token = function_name_token

    def __repr__(self) -> str:
        return f"""Non word name for extern function name at {self.function_name_token.location}!
Extern function signature should have name as word after 'extern' keyword but got '{self.function_name_token.type.name}'!"""


class ParserExternRedefinesMacroError(GofraError):
    def __init__(
        self,
        *args: object,
        redefine_extern_function_name_token: Token,
        original_macro_location: TokenLocation,
        original_macro_name: str,
    ) -> None:
        super().__init__(*args)
        self.redefine_extern_function_name_token = redefine_extern_function_name_token
        self.original_macro_location = original_macro_location
        self.original_macro_name = original_macro_name

    def __repr__(self) -> str:
        return f"""Redefinition of an macro '{self.original_macro_name}' at {self.redefine_extern_function_name_token.location} inside extern function!
Original definition found at {self.original_macro_location}!
Extern cannot redefine macro names!"""


class ParserExternRedefinesLanguageDefinitionError(GofraError):
    def __init__(
        self,
        *args: object,
        extern_token: Token,
        extern_function_name: str,
    ) -> None:
        super().__init__(*args)
        self.extern_token = extern_token
        self.extern_function_name = extern_function_name

    def __repr__(self) -> str:
        return (
            f"Extern function '{self.extern_function_name}' at {self.extern_token.location}"
            " tries to redefine language definition!"
        )


class ParserEmptyIfBodyError(GofraError):
    def __init__(self, *args: object, if_token: Token) -> None:
        super().__init__(*args)
        self.if_token = if_token

    def __repr__(self) -> str:
        return f"""If condition at {self.if_token.location} has no body!
If condition should always have body as otherwise this has no effect!"""


class ParserNoEntryFunctionError(GofraError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

    def __repr__(self) -> str:
        return f"""Expected entry point function '{GOFRA_ENTRY_POINT}' but it does not exists!"""


class ParserEntryPointFunctionTypeContractInError(GofraError):
    def __init__(self, *args: object, type_contract_in: FunctionTypeContract) -> None:
        super().__init__(*args)
        self.type_contract_in = type_contract_in

    def __repr__(self) -> str:
        return f"""Entry point function '{GOFRA_ENTRY_POINT}' violates type contract!

Entry point function cannot have type contract in!
But currently it have type contract in: {self.type_contract_in}
"""


class ParserEntryPointFunctionTypeContractOutError(GofraError):
    def __init__(self, *args: object, type_contract_out: FunctionTypeContract) -> None:
        super().__init__(*args)
        self.type_contract_out = type_contract_out

    def __repr__(self) -> str:
        return f"""Entry point function '{GOFRA_ENTRY_POINT}' violates type contract!

Entry point function cannot have type contract out!
But currently it have type contract out: {self.type_contract_out}
"""


class ParserEntryPointFunctionModifiersError(GofraError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

    def __repr__(self) -> str:
        return f"""Entry point function '{GOFRA_ENTRY_POINT}' violates modifiers signature!

Entry point function cannot be external or inlined!
"""


class ParserTopLevelError(GofraError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

    def __repr__(self) -> str:
        return """Expected

Entry point function cannot be external or inlined!
"""
