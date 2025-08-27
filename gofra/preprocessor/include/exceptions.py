from pathlib import Path

from gofra.lexer.tokens import Token
from gofra.preprocessor.exceptions import PreprocessorError


class PreprocessorIncludeFileNotFoundError(PreprocessorError):
    def __init__(self, *args: object, include_token: Token, include_path: Path) -> None:
        super().__init__(*args)
        self.include_token = include_token
        self.include_path = include_path

    def __repr__(self) -> str:
        return f"""Unable to include file '{self.include_path}' requested at {self.include_token.location}

File does not exists!

Please check that this file exists, or try updating include directory paths.
Requested path directly resolves to '{self.include_path.resolve()}'
(Does not includes import directory traverses)

Did you supplied wrong name/path?"""


class PreprocessorIncludeNoPathError(PreprocessorError):
    def __init__(self, *args: object, include_token: Token) -> None:
        super().__init__(*args)
        self.include_token = include_token

    def __repr__(self) -> str:
        return f"""'include' has no path at {self.include_token.location}!

Expected there will be include path after 'include' as string.

Did you forgot to add path?"""


class PreprocessorIncludeNonStringNameError(PreprocessorError):
    def __init__(self, *args: object, include_path_token: Token) -> None:
        super().__init__(*args)
        self.include_path_token = include_path_token

    def __repr__(self) -> str:
        return f"""Invalid include path type at {self.include_path_token.location}!

Expected include path as string with quotes.

Did you forgot to add quotes?"""


class PreprocessorIncludeCurrentFileError(PreprocessorError):
    def __init__(self, *args: object, include_path_token: Token) -> None:
        super().__init__(*args)
        self.include_path_token = include_path_token

    def __repr__(self) -> str:
        return f"""Tried to include current file within include at {self.include_path_token.location}!
Including self is prohibited and will lead to no actions, so please remove self-import

Did you mistyped import path?"""
