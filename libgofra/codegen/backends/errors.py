from libgofra.exceptions import GofraError


class FrameTableLocatableError(GofraError):
    def __init__(self, local_space_size: int, store_pair_max_range: int) -> None:
        self.local_space_size = local_space_size
        self.store_pair_max_range = store_pair_max_range

    def __repr__(self) -> str:
        return f"""Cannot locate current local variables on a frame or relocate them!

Please locate big local variables in global space! Max local frame size: {self.store_pair_max_range}, but currently it is: {self.local_space_size} bytes (aligned)!

This is possibly compiler limitation which is currently not supported by Gofra, please locate big local variables in global space!

{self.generic_error_name}"""
