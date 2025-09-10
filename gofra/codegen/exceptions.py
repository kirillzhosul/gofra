from gofra.exceptions import GofraError
from gofra.targets import Target


class CodegenUnsupportedBackendTargetPairError(GofraError):
    def __init__(
        self,
        *args: object,
        target: Target,
    ) -> None:
        super().__init__(*args)
        self.target = target

    def __repr__(self) -> str:
        return f"""Code generation failed

Unsupported target '{self.target.triplet}' (only triplet shown)!
Please read documentation to find available target pairs!
"""
