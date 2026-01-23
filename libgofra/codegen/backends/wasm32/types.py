from typing import Literal

from libgofra.types._base import PrimitiveType, Type
from libgofra.types.composite.pointer import PointerType

type WASM_NUMBER_TYPES = Literal["i32", "i64", "f32", "f64"]
type WASM_VECTOR_TYPES = Literal["v128"]
type WASM_TYPE = WASM_NUMBER_TYPES | WASM_VECTOR_TYPES


WASM_POINTER_TYPE: WASM_NUMBER_TYPES = "i64"

# Extends all types to 64 bit version
# As current codegen prohibits and cannot deal with i64/i32 so we always use 64 bits
# and read their lower bytes
WASM_EXTEND_PRIMITIVE_NON_64BIT_TYPES = True


def wasm_type_from_primitive(primitive: Type) -> WASM_TYPE:
    """Get WASM (WAT) type from primitive type that can be used for stack operation."""
    if isinstance(primitive, PointerType):
        return WASM_POINTER_TYPE

    assert isinstance(primitive, PrimitiveType), f"Type {primitive} is not an primitive"

    if WASM_EXTEND_PRIMITIVE_NON_64BIT_TYPES:
        return "f64" if primitive.is_fp else "i64"

    if primitive.size_in_bytes <= 4:
        # FPU
        return "f32" if primitive.is_fp else "i32"

    assert primitive.size_in_bytes <= 8, f"Type {primitive} is too big for stack"
    return "f64" if primitive.is_fp else "i64"
