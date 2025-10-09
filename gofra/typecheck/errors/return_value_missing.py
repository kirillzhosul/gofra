from gofra.exceptions import GofraError
from gofra.hir.function import Function


class ReturnValueMissingTypecheckError(GofraError):
    def __init__(
        self,
        owner: Function,
    ) -> None:
        super().__init__()
        self.owner = owner

    def __repr__(self) -> str:
        return f"""Return value missing

Function '{self.owner.name}' defined at {self.owner.defined_at} 
return value type is '{self.owner.return_type}' but it is missing at the end (empty stack)

Did you forgot to push return value?

[return-value-missing]"""
