from gofra.exceptions import GofraError
from gofra.parser.functions.function import Function


class ReturnValueMissingTypecheckError(GofraError):
    def __init__(
        self,
        owner: Function,
    ) -> None:
        super().__init__()
        self.owner = owner

    def __repr__(self) -> str:
        return f"""Return value missing

Function '{self.owner.name}' defined at {self.owner.location} 
return value type is '{self.owner.type_contract_out}' but it is missing at the end (empty stack)

Did you forgot to push return value?

[return-value-missing]"""
