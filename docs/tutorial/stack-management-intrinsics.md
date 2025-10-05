# Stack management intrinsics

For managing an stack you must have some less-or-more complex commands for example like `swap` or `rot`, language supports some of them


# SWAP
Mnemonics: `a b -> b a`

Swaps two arguments from stack, for example for reaching second argument

Example
```gofra
3 2      - // 1
2 3 swap - // -1
```

# DROP
Mnemonics: `a -> _`

Drops element from stack

Example:
```gofra
2 2 2 drop + // 4, and empty stack
```