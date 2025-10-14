# Type checker


Type checking is always performed by default at compile-time (unless `-nt` or `--no-typecheck` flag is passed)
It validates all stack usages and function calls


## Implementation

Type checker is implemented as type-stack machine which behaves like stack based machine but operates on types
So for example `2` will resolve into `typestack = [INT]`

Typechecker will perform type safety validation even for unused functions (expect function calls, as there is no calls for unused functions)
Unless you apply [DCE](./optimizations.md) optimization at compile-time (as it performed before type checker stage)

Type checker will go into each function and validate its return type and stack usage and emit an error if something weird is found

When typechecker found an call inside current function, it will consume desired parameters as arguments from type stack and push return type unless it not `void` type

## Type comparison

Typechecker always uses strategy called `strict-same-type` which means types must be always same and no inference / type lowering is possible (you must always statically type cast for fixing errors)
Possible next update will introduce something new, allowing to use `implicit-byte-size` strategy or any type lowering automatically at typechecker stage

## Is type checker affects runtime / generate code?

Type checker is meant to only type-safety feature, so no generated code is affected by typechecker, even type casts are static ones and only applied to type checker, not anything else