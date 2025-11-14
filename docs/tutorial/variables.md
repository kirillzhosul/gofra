# Variables

**That page is being written, and only may be used as quick-overview**

Variables is an container for your arbitrary data (within variable type size), they can be *static* (*global*) and *local* (to functions)


## Variable definitions

Variable definitions looks like that:
```gofra

// Primitive type
var {name} [type]

// Composite type
var array {type}[{size_in_elements}]
var ptr *{type}

var complex **int[32] // pointer to an pointer containing array of integers
```

It must start with `var` then `name` and `type`

## Initializers
```gofra
var x int = 10;
var x char = 'a'; // or 97
var x *string = "Hello, World";
var x int[3] = [1, 2, 3] // Has size inference and validation, rest undefined is always treated as zero initialized (even for stack)
```

## Type inference and auto types

If defining an variable without an type and it has proper initializer, type may be omitted:
```gofra
var x = 5; // int
var x = "test" // *string
var x = [1, 2, 3] // int[3]
var error = [] // Error: is it int[] or whatever else possible? Requires type explicitly
```

## Type casting at initializer

For few simple types auto type casting (e.g reinterpret cast) is allowed:
```gofra
var x bool = 1; // Reinterpret(*) bytes as bool and allow proper type
var x char = 97 // 'a'
```

## Constants

Variable with initializer known at compile time may become const by using this syntax:
```gofra
const x = 5;
const var = 10;
```

Constants are prohibited to obtain their memory address (restricted modifications) and allows optimizer to apply inlining/unwind and DCE on usage

## Primitive and composite types: differences

Primitive type is such type that only contains an size of memory blob and nothing more inside

Composite type is such type which contains another type inside (may be primitive or complex) that it refers to (e.g array of elements contains primitive type of an single element and pointer is containing type of memory it refers to (pointer to an integer is an complex pointer type referencing integer and string is in general an complex type as it refers to array of caricature (contiguous memory blob) as another complex type))

Primitive types:
- int
- char
- byte

Composite type
- Array of {primitive|complex type}
- Pointer to {primitive|complex type}
- Structure with set of {primitive|complex} type inside
Composite types may contain another complex types so pointer to array of pointers to integer is an 2-level complex type


## Local and static (global) variable location: differences

Static variable is such variable that is defined outside of an function (e.g at top level) while being compiled it located in static memory segment at runtime (e.g data / bss) section, it always initialized and persist it value between function calls (as anyone may modify that variable)

Local variable is such variable that is define inside an function, while being compiled it will be translated into local region on an stack, so with each function call with that variable it will be reset


```gofra
// Global variable
// located in static binary segment
var global int

func void main[]
    // Local variable
    // located and initialized at stack
    var local int
end
```

Using local/global storage type of variables has no differences for end-user programmer, as it differs at code generation level and only will affect memory layout

## Local variables: alignment on CPUs
Each local variable must be alignment on most architectures (CPUs) so for example definition of three local variables like that:
```gofra
var a int
var b int
var c byte
``` 
will result in 24 bytes total space allocated at callee, as:
int: 8 bytes
int: 8 bytes
byte: 1 byte

that sums to 17, but for example on AARCH64 stack must be aligned by 16 bytes so we must align that to next value: 32 bytes
and space that is left after two first integers has 16 (15, excluding third variable) more space which is unusable
