from gofra.lexer.tokens import Token
from gofra.preprocessor.exceptions import PreprocessorError


class PreprocessorConditionalNoMacroNameError(PreprocessorError):
    def __init__(self, *args: object, conditional_token: Token) -> None:
        super().__init__(*args)
        self.conditional_token = conditional_token

    def __repr__(self) -> str:
        return f"""No macro name specified at preprocessor condition at {self.conditional_token.location}

Expected macro name after conditional block!"""


class PreprocessorConditionalConsumeUntilEndifContextSwitchError(PreprocessorError):
    def __init__(self, *args: object, conditional_token: Token) -> None:
        super().__init__(*args)
        self.conditional_token = conditional_token

    def __repr__(self) -> str:
        return f"""Preprocessor conditional block got context (file) switch while consuming an block at {self.conditional_token.location}.

This is caused probably by an unclosed preprocessor block (e.g no `#endif`).
(Consuming an conditional block should not switch an tokenizer context, as is means current processed file is probably changed)."""
