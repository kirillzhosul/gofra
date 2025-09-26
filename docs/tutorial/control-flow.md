# Control flow constructions

### If

`if` is an control flow block construction that consumes single boolean type argument and if it is not equals to 0 - jumps into block body, otherwise jumps to own closure `end` block
```gofra
0 1 == if 
    // will not happen
end

1 1 == if
    // will fall here
end
```

### While-do

`while` is an control flow block construction that consumes single boolean type argument and if it is not equals to 0 - jumps into block body, otherwise jumps to own closure `end` block, but in difference with if, will always jump back to while after reaching own `end`, so only way to left that loop is out of that condition
```gofra
var counter int 
counter 0 !<

while counter < 10 do
    // Will print 10 times
    "Hello!" print

    counter copy ?> inc !<
end
```

In control-flow reference graph:
`while` -> `end`
`do` -> `while`
`end` -> `while`


### Additional notes on logic operators

Language supports logical AND (`&&`) and OR (`||`), read more at operator / intrinsics page.