# Stack management operators

For managing an stack you must have some less-or-more complex commands for example like `swap` or `rot`, language supports some of them


# SWAP
Mnemonics: `a b -> b a`

Swaps two arguments from stack, for example for reaching second argument

Example
```gofra
3 2      - // 1
3 2 swap - // -1
```

# DROP
Mnemonics: `a -> _`

Drops element from stack

Example:
```gofra
2 2 100 drop + // 4, and empty stack
```

# COPY
Mnemonics: `a -> a a`

Copies element from stack

Example:
```gofra
2 copy // 2 2 on stack
```

# Tips and Tricks

 - `swap` is useful when initializing local variables by function arguments values. For example:
    ```gofra
    func int str2int[
        *char[],
        int
    ] do
        var len int; &len swap !<
        var ptr *char[]; &ptr swap !<
        ...
    end
    ```
    In this example, the `len` variable is initialized by the `int` value from the arguments and
     the `ptr` variable is initilized by the `*char[]` value from the arguments.
-  `copy` is useful when increasing or decreasing some value. For example:
    ```
    var number int = 0;

    &number copy ?> 10 + !< // number = number + 10
    ```
