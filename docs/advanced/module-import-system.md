# Module and imports system

[This is WIP feature, both documentation and implementation is unfinished, use at your own risk]


Currently, *Gofra* has 2 ways of injecting code from other files, *C/C++* way with preprocessor: `#include` (read more at preprocessor page), and new Work-In-Progress module system that must be enabled with `libgofra` `FEATURE_ALLOW_MODULES` flag


# Definition of an module

Module in *Gofra* context - is an single file that is treated as module, and compiled internally separately into its own object file.

For example lets define two modules:
```gofra
// > a.gof
import b;

func void main[]
    call b.hello_world;
end
```

```gofra
// > b.gof
#include "std"

pub func void hello_world[]
    "Hello, World!" call println
end
```

First one, `a`, is our root module for compilation - we compile from `gofra a.gof`, as it is defines entry point (*main*)

Under the hood, *Gofra* will start from compiling `a.gof`, find `import` statement and try to process `b.gof` module, when it is processed, compiler, and `a.gof` processing especially, knowns that it depends on `b.gof` and call to `b.hello_world` must be resolved (public function is available for root module), after parsing and processing, it will be compiled to `a.o` (core object file) and `a$mod_dependencies` (inside cache), which holds `b.o` that is linked against root `a.o` to single `a` executable!

# Importing an module
```gofra
import a; // implicitly `a.gof` as `a`
import a as my_module; // implicitly `a.gof` as `my_module`
import "my_file.gof" as m; // explicitly `my_file.gof` as `m`

//(in both above string allowed)
```


# Visibility of symbols

By default, all symbols treated as *private* you must mark exposed symbols via `pub` attribute modifier

|Visibility|Description|
|----------|-----------|
|Public    |Symbol is available both inside own module and its dependant modules|
|Private   |Symbol is available only within its own module|

If you try to call private symbol from other module, compiler will emit an error and stop compilation:
```
Tried to call private/internal function symbol ... (defined at ...) from module named as `...` (import from ...):
Either make it public or not use prohibited symbols!
```

# Known problems and limitations
- Inline functions cannot be exposed
- Types, definition and structs cannot be exposed
- Cannot alias import symbol
- Cannot partially import symbols from module
- REPL does not supports modules
- Testkit does not supports modules
- Possibly, pollution of internal macros registry when including other files (TBD)
- Duplicate symbol reference (no implicit name mangling)
- (only linear dependency graph is possible to resolve for now)

# Resolving circular dependencies

TBD (circular dependencies drop compiler, not implemented in any way)


# Module symbol mangling for external linkage and FFI

Currently, there is no mangling, but it is temporary problem/luck
This prohibits to have non-linear/real graph dependencies, yet allows simple FFI calls

Later (TODO), symbols will be always/conditionally mangled for resolving problems of duplicate symbols in object files

# Order of searching modules

Search algorithm is same as preprocessor include: 
- Try module name from current directory
- Try CLI toolchain directory
- Try include paths (obscured with CLI flag for preprocessor)


# Incremental compilation 

By default, modules never compiled incrementally and always being being rebuilt, this behavior can be overridden with `--incremental` flag, internally compiler decide to not rebuild based on modified time difference from artifact (object/assembly file) and original module file (*.gof)


# Order of dependencies

Dependencies compiled and resolved based on order from source e.g if *a* import *b* and then *c* with *e* compiled will build linear graph like this:
```
a -> b -+-> c
        |
        +-> d
```

There is some sort of DAG topological sorting applied to compiled modules (a->b->c->d), final resolving is on back of LTO and linkage.

Notice that currently, possible of recompiling modules when there is same dependency over an graph on multiple nodes

# Typechecking and optimizations for dependencies

Typechecking is applied to every module, each function symbol is re-typechecked on compilation

For optimizer passes, firstly *Gofra* traverses and optimizes dependencies in topological sort order (DAG TSO), then applies final optimizer pass for root module (rule: dependencies first, to perform expensive and high-level optimizations within root module over already-optimized dependencies)