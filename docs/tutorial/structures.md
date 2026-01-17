# Structures

Structs currently is an something like type-definition with proper type checking and field accessors (auto-shift)

## Defining an structure type

```gofra
struct name
    field type
    ...
end
```

For example defining an person struct
```gofra
struct Person
    age int
    name *char[]
end
```

## Accessing an structure field
```gofra
var stepan Person // initialize variable of type Person

stepan.age // will push an pointer to an `age` field so you can write / read from it
```

## Forward reference and self-reference

Forward reference of structures as children field is allowed:

```gofra
struct X
    id int
    child X
end // 16 bytes
// This will define X as (8 byte int + 8 byte X (int))
```

## Alignment on CPUs and packed layout

By default, all structures being aligned in memory according to max alignment of its own fields, e.g if biggest field type is `int` (8 bytes) then alignment for whole structure must be same amount of bytes

This can be overridden by specifying `packed` attribute for structure, which means *do not apply any alignment, place all fields as-is linearly in memory*

```gofra
struct bad_layout
    a char // 1 byte
    b int  // 8 byte
    c char // 1 byte
end // Unpacked, 24 bytes

struct packed packed_layout
    a char // 1 byte
    b int  // 8 byte
    c char // 1 byte
end // Packed, 10 bytes
```


```
Packed (tight memory layout)
|-------------|
|a|    b   |c||     => 10 bytes
|-------------|


Aligned (thin memory layout)
|-------------------------------------------|
|a|...padding...|     b     |...padding...|c|     => 24 bytes
|-------------------------------------------|

Padding is from both sides to properly align *int* (8 bytes) field access on CPU
```

## Reordering
Reordering is a process when for performance reasons fields of structure being re-ordered to solve alignment issues (redundant padding on structure memory layout) 

By default, structures does not apply reordering, this behavior can be overridden by specifying `reorder` attribute for structure.

```gofra
struct bad_layout
    a char // 1 byte
    b int  // 8 byte
    c char // 1 byte
end // Unpacked, 24 bytes

struct reorder reordered_layout
    a char // 1 byte
    b int  // 8 byte
    c char // 1 byte
end // Unpacked, reordered 16 bytes
// Order was transformed into [b, a, c] (int, char, char) re-using padding from int to char
```

## HIR perspective

Accessing an structure field will as by default emit `PUSH_VARIABLE_ADDRESS` HIR operator which is followed by `STRUCT_FIELD_OFFSET` which is resolved to `ADDR(VAR) + FIELD_OFFSET(field)` so `*struct` resolve into `*struct.field` as auto type inference from structure type


## LIR perspective

Structure type by default is an complex type with collection of field types and their ordering respectfully
`STRUCT_FIELD_OFFSET` is an almost inline-assembly code generation which performs addition right inside runtime
