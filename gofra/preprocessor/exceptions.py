from gofra.exceptions import GofraError


class PreprocessorError(GofraError):
    """General error within preprocessor.

    Should not be used directly as not provides information about error source!
    """

    def __repr__(self) -> str:
        return """General preprocessor error occurred. 

Please open an issue about that undocumented behavior!
"""
