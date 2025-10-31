# Memory management

Memory management is a fundamental aspect of programming. Gofra provides direct memory access operations for loading and storing data.


# Critical notice
Currently, in gofra load and store operations works with always 8-bytes data, so this will cause some overwriting of memory layout, consider that while using critical to memory operations

# Memory operations

## Store into memory
Stores a value at a specified memory address.

**Mnemonic: `a b -> _ _`**

**Intrinsic: `!<`**

Consumes two values from the stack: `[address, value]`

- Stores value at memory location `address`
- Both values are removed from the stack

### Syntax
```gofra
<address> <value> !<
```

### Examples
```gofra
// Store to a variable
var name int
&name 1 !<  // Store 1 into name

// Store to calculated address
var array int[10]
&array 0 + 42 !<  // Store 42 at array[0]
&array 8 + 99 !<  // Store 99 at array[8] (if int is 4 bytes)
```

## Load from memory
Stores a value at a specified memory address.

**Mnemonic: `a -> b`**

**Intrinsic: `?>`**

Consumes one value from the stack: `[address]`

- Loads the value from memory location `address`
- Pushes the loaded value onto the stack

### Syntax
```gofra
<address> ?>
```
To push variable onto stack:
```gofra
<variable>
```

### Examples
```gofra
// Load from a variable
var name int
&name 1 !<    // Store 1 into name

&name ?>      // Load value from name (pushes 1 onto stack)
// or
name

print_integer   // Prints 1

// Load from array element
var numbers int[3]
&numbers 0 + 10 !<    // numbers[0] = 10
&numbers 8 + 20 !<    // numbers[1] = 20 (assuming 8-byte integers)
&numbers 0 + ?> print // Load and print numbers[0]
```

# Memory Size Considerations

- **Pointer Width**: Determined by CPU architecture (typically 32-bit or 64-bit)
- **Word Size**: Architecture-dependent, affects natural memory alignment
- **Type Sizes**: Different data types occupy different amounts of memory

# Type size reference
```gofra
var b char    // 1 byte
var i int     // 4 or 8 bytes (architecture-dependent)
var p *int     // 4 or 8 bytes (pointer width)
```
