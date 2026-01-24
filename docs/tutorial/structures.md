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



## `offset_of`

`offset_of` pushes byte offset for specified field for given structure (concrete ones)
```
offset_of {STRUCTURE_TYPE} {FIELD_NAME}
```

It takes into account any alignment / reordering that is possible, and offset will be always same, as those whose will be used inside low-level machine code / ABI calls
```
struct Foo
    // No special alignment, simple struct
    a int
    b int
end


offset_of Foo a // 0
offset_of Foo b // 8
```

## Generic structure types

```
// Define generic struct with type param T
struct Generic{T}
    field_a T
    field_b T
    field_c int
end

var x Generic{T = int} // Variable with concrete type
```