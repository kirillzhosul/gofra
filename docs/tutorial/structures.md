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

Person.age // will push an pointer to an `age` field so you can write / read from it
```

## Alignment on CPUs

All structures are alignment by default to machine alignment


## Big Caveats

- Structs are not passed according to C-FFI ABI
- Structs have no constructors
- ... and much more as this feature is being in development an mainly used as drop-in replacement to defining an structs with `char[32]` or `int[2]`...


## HIR perspective

Accessing an structure field will as by default emit `PUSH_VARIABLE_ADDRESS` HIR operator which is followed by `STRUCT_FIELD_OFFSET` which is resolved to `ADDR(VAR) + FIELD_OFFSET(field)` so `*struct` resolve into `*struct.field` as auto type inference from structure type


## LIR perspective

Structure type by default is an complex type with collection of field types and their ordering respectfully
`STRUCT_FIELD_OFFSET` is an almost inline-assembly code generation which performs addition right inside runtime