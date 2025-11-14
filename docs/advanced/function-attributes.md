# Function Attributes

Function attributes in Gofra are defined like so:
```ebnf
FunctionDef = {"global" | "extern" | "no_return" | "inline}, "func", ...FunctionRestDef
```

Here is description of each attribute


## `no_return` attribute

Marks function as having no possible way out, for example `exit` system function, these function must has no return value

Compiler will warn you if you have function that always calls to `no_return` functions, and emit possible other warnings

`no-return` allows to emit general compiler warnings/errors and perform possible optimizations, mostly used in compiler library, but useful if you calling `exit` function and has nothing more

This checks appears only at compile-time and has no effect on runtime

```gofra
no_return func void x[]
    // Must has no way out
end


func void x1[]
   call exit // warning, always calling to `no_return` function - propagate attribute

   2 2 + drop // warning, unreachable code, and allows to apply optimizations like DCE
end


func void x1[]
    false if == 
        call exit // may have conditional `no_return` calls without any warning
    end
end
```

## `inline` attribute

Functions that marked as `inline` has no real-call in runtime, it expands their tokens right into caller block
These function cannot have local variables as may pollute original caller blocks

TODO: For now, inline functions has lack of compiler-time checks (e.g typechecking), and may be not so safe to use, and are hard to debug, non-inlineable functions are always better now

For more information what is inlining and optimization look into [Optimizations](./optimizations.md) documentation


For example:
```gofra
func int reduce_pairs[int,int,int,int]
    + + +
end

func void main[]
    1 2 3 4 reduce_pairs // yields 10
end

// After inlining this is becomes:
inline func int reduce_pairs[int,int,int,int]
    + + +
end

// And main is reduced to:
func void main[]
    1 2 3 4 + + + // yields 10
end
```


## `extern` attribute

Functions marked with `extern` attribute will be treated as externally defined via FFI (Gofra ones, other C-FFI) for example external function `puts` from `libc` is declared as:
```gofra
extern func int _puts[*char[]]
```

This means function symbol `_puts` is not available inside current object file (co-program) but will appear later at linkage step within another object file (library)

For more information what is FFI look into [FFI](./ffi.md) documentation


## `global` attribute

Function marked with `global` attribute are opposite to `extern` ones - they expose this function symbol to object file and allow other object files to link with it