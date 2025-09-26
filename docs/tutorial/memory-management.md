# Memory management
Most goal of an program is to manage an memory, in Gofra of course you have ways to manage bytes

Size (width) of that load / store instructions is different by CPU architecture pointer-width and word-size

# Store into memory
Mnemonics: `a b -> _ _`
Intrinsic: `!<`

Consumes two arguments from stack [address, value] and stores that value at given address
Example
```gofra
var somevar int 


somevar 1 !< // store 1 into somevar
```

# Load from memory
Mnemonics: `a -> b`
Intrinsic: `?>`

Consumes one argument from stack [address] and loads value at given address

Example
```gofra
var somevar int 


somevar 1 !< // store 1 into somevar
somevar ?> // load 1 into stack from somevar
```