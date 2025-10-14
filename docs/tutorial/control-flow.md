# Control Flow Constructs

Gofra provides essential control flow constructs for conditional execution and looping.

## `if` Statement
The `if` statement evaluates a boolean condition and executes the block if the condition is non-zero.

#### Syntax
```gofra
<condition> if
    // code to execute if condition is true
end
```

#### Example
```gofra
// This block will NOT execute
0 1 == if 
    "This will not print" print
end

// This block WILL execute
1 1 == if
    "This will print" print
end

// Using variables
var is_valid bool
true is_valid !<

is_valid ?> if
    "Valid state" print
end
```

## `while` Statement

The `while` loop repeatedly executes a block of code as long as the condition remains non-zero. The loop continues until the condition evaluates to false (zero).

#### Syntax
```gofra
while <condition> do
    // code to execute repeatedly
end
```

#### Example
```gofra
var counter int
counter 0 !<  // Initialize counter to 0

while 
    counter 10 < // condition
do
    "Hello! Iteration: " print
    counter print_integer  // Print current counter value
    "\n" print
    
    counter copy ?> 1 + !<  // Increment counter
end
```

#### Control flow pattern
```text
while → (condition check) → do → end → while (loop back)
                    │
                    ↓ (condition false)
               (exit loop)
```