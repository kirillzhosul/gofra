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


## `for` Statement

The `for` loop is under the hood is same/using `while` construction but adds syntactical sugar for auto-constraints and counters (iterator)

Planned features: Soon, there will be feature for using array as an `in` qualifier and `0..array` respectfully

At entering the loop, iterator variable will be set to low threshold of range
Range is exclusive (not inclusive)
#### Example
```gofra
for i in 0..10 do
    // i will be [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
end

for i in 10..0 do
    // i will be [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
end

var x int = 5;
for i in 0..x do // variables is allowed only on RHS for now, TODO
    // Step always will be 1, reversed iterations is not possible!
    // i will be [0, 1, 2, 3, 4]
end
```

#### Comparison to `while` HIR syntactical sugar

Something like this:
```gofra
for i in 0..10 do
end
```

Is being translated by compiler frontend into something like

```gofra
var i int = 0;

while i 10 < do // For variable range 10 is replaced ith loading variable, for reversed range, will be `>`
    // body of for
    &i i 1 + !< // Decrement if reversed
end
```