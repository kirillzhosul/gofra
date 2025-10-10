from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.consts import GOFRA_ENTRY_POINT
from gofra.exceptions import GofraError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from gofra.lexer.tokens import Token


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


class ParserUnknownIdentifierError(GofraError):
    def __init__(
        self,
        *args: object,
        word_token: Token,
        names_available: Iterable[str],
        best_match: str | None = None,
    ) -> None:
        super().__init__(*args)
        self.word_token = word_token
        self.names_available = names_available
        self.best_match = best_match

    def __repr__(self) -> str:
        return f"""Encountered an unknown identifier '{self.word_token.text}' at {self.word_token.location}!

Available names: {", ".join(self.names_available) or "...":{512}}""" + (
            f"\nDid you mean '{self.best_match}'?" if self.best_match else ""
        )


class ParserUnknownFunctionError(GofraError):
    def __init__(
        self,
        *args: object,
        token: Token,
        functions_available: Iterable[str],
        best_match: str | None = None,
    ) -> None:
        super().__init__(*args)
        self.token = token
        self.functions_available = functions_available
        self.best_match = best_match

    def __repr__(self) -> str:
        return f"""Encountered an unknown function name '{self.token.text}' at {self.token.location}!

Available function names: {", ".join(self.functions_available) or "..."}""" + (
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


class ParserEntryPointFunctionModifiersError(GofraError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

    def __repr__(self) -> str:
        return f"""Entry point function '{GOFRA_ENTRY_POINT}' violates modifiers signature!

Entry point function cannot be external or inlined!
"""


class ParserVariableNameAlreadyDefinedAsVariableError(GofraError):
    def __init__(self, *args: object, token: Token, name: str) -> None:
        super().__init__(*args)
        self.token = token
        self.name = name

    def __repr__(self) -> str:
        return f"""Tried to redefine variable with name {self.name} at {self.token.location}

Variable is already defined."""


class ParserTopLevelError(GofraError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

    def __repr__(self) -> str:
        return """Expected

Entry point function cannot be external or inlined!
"""
