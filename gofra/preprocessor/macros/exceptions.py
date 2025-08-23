from gofra.lexer.tokens import Token, TokenLocation
from gofra.preprocessor.exceptions import PreprocessorError


class PreprocessorNoMacroNameError(PreprocessorError):
    def __init__(self, *args: object, macro_token: Token) -> None:
        super().__init__(*args)
        self.macro_token = macro_token

    def __repr__(self) -> str:
        return f"""No 'macro' name specified at {self.macro_token.location}!
Macros should have name after 'macro' keyword as word

Do you have unfinished macro definition?"""


class PreprocessorMacroNonWordNameError(PreprocessorError):
    def __init__(self, *args: object, macro_name_token: Token) -> None:
        super().__init__(*args)
        self.macro_name_token = macro_name_token

    def __repr__(self) -> str:
        return f"""Non word name for macro at {self.macro_name_token.location}!

Macros should have name as word after 'macro' keyword but got '{self.macro_name_token.type.name}'!"""


class PreprocessorMacroRedefinedError(PreprocessorError):
    def __init__(
        self,
        *args: object,
        redefine_macro_name_token: Token,
        original_macro_location: TokenLocation,
    ) -> None:
        super().__init__(*args)
        self.redefine_macro_name_token = redefine_macro_name_token
        self.original_macro_location = original_macro_location

    def __repr__(self) -> str:
        return f"""Redefinition of an macro '{self.redefine_macro_name_token.text}' at {self.redefine_macro_name_token.location}

Original definition found at {self.original_macro_location}.

Only single definition allowed for macros."""


class PreprocessorMacroRedefinesLanguageDefinitionError(PreprocessorError):
    def __init__(self, *args: object, macro_token: Token, macro_name: str) -> None:
        super().__init__(*args)
        self.macro_token = macro_token
        self.macro_name = macro_name

    def __repr__(self) -> str:
        return f"""Macro '{self.macro_name}' at {self.macro_token.location} tries to redefine language definition!"""


class PreprocessorUnclosedMacroError(PreprocessorError):
    def __init__(self, *args: object, macro_token: Token, macro_name: str) -> None:
        super().__init__(*args)
        self.macro_token = macro_token
        self.macro_name = macro_name

    def __repr__(self) -> str:
        return f"""Unclosed macro '{self.macro_name}' at {self.macro_token.location}!

Macro definition should have 'end' to close block.

Did you forgot to close macro definition?"""


class PreprocessorMacroDefinesMacroError(PreprocessorError):
    def __init__(self, *args: object, macro_token: Token, macro_name: str) -> None:
        super().__init__(*args)
        self.macro_token = macro_token
        self.macro_name = macro_name

    def __repr__(self) -> str:
        return f"""Macro '{self.macro_name}' at {self.macro_token.location} defines another macro inside!

Macro cannot define another macro inside their bodies."""
