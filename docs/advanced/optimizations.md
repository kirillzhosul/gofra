# Optimizer and optimizations

Gofra has builtin optimizer that helps optimize your code 
(from top-level HIR optimizations to low-level LIR ones according to selected target)

By default optimizer and all optimizations is disabled for development assistance and decreased build time, 
optimizations may be enabled via CLI using `-O{N}` flag with desired level of optimizations (`-01`, `-02` is supported for now)


## Optimizer level features

| Optimization      | Minimum level |
|:------------------|:--------------|
| DCE               | 1             |
| Function inlining | 1             |


# Optimization features (passes)

Here is an list of all possible optimizations that optimizer may apply

## DCE (Dead-Code-Elimination)
---
Minimum optimization level: **1** (`-O1`) <br/>
Impact: **Reduced binary size**
Flag: `-fdce`, `fno-dce`

DCE searches for functions that is not being called at least once and removes them from final IR so them does not appear in final binary as being unused.
Does not removes `public` functions as their usage is outside of an Gofra program.


For example this function may be removed by DCE
```gofra
// [Additionally, most of binary size comes for example from libraries which gives you a lot of functions]
include "std.gof"

func void test_function[]
    // This function is unused so it will be safely remove
    ...
end

func void main[]
    "Hello, World!\n" print
end
```

`--dce-max-iterations` affects max iterations that DCE may perform, by default it is around **128** which is mostly fine, for example if function is removed, optimizer must review program code again as that function may reference other functions which is became unused due to removed that initial function.

## Function inlining
---
Minimum optimization level: **1** (`-O1`) <br/>
Impact: **Increased binary size**, **Increased performance**
Flag: `-finline-functions`, `fno-inline-functions`


Function inlining automatically marks simple / small functions as inlineable and resolves their usages after that marking.
Inlining is not performed for recursive functions, as it will break not only the code but also optimizer itself (while resolving inline function reference infinite amount of iterations until threshold)
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
// [which is also may be optimized using CF (constant-folding)]

```

`--inline-functions-max-iterations` affects max iterations for function inlining to search for new inlined function usage in other functions. 
Low limit will result into unknown function call at assembler stage. This may slightly increase final binary size

`--inline-functions-max-operators` affects max amount of operators to treat function as inlineable. 
Setting big number will lead to almost all function will be treated as inline ones.
