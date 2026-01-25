# First-class functions (Lambdas)

*Gofra* is an language with [**first-class functions**](https://en.wikipedia.org/wiki/First-class_function) it does support passing functions as arguments to other functions, returning them as return value from other functions and store into memory


## Function type

To work with function as types/values you need to interact with **Function Type** it is defined same as default functions except, type expression goes into *type* block:

```gofra
// Define an type that describes function (Function Type)
type F func void _[]
type F func int _[int a, int b]
type F func int _[int, int]

func void f[F function] // Use that type
func void f[func void _[int, int] function] // Inline function type

var f F; // Holds function
```

While defining an function type, name and parameter names is dropped within type holder, which means you can define auxiliary name / parameter names, but general convention is to name function `_`.

## Treating functions as Function Type

`pointer_of_proc` allows to acquire Function Type from specified function e.g:
```
func void f[int a] ... end

func void main[]
    var f func void _[int];

    &f pointer_of_proc f !<
end
```

This keyword pushes Function Type (e.g function pointer) onto the stack, allowing storing and passing it to other functions

## Lambda function definition

You can define function within another one, by using `lambda` function definition like so:
```gofra
// Create function that return another function
type F_T func int _[int, int]
func F_T create_function[]
    lambda func int _[int, int]
        + // sum arguments
    end
    return
end
```

`lambda` definition always returns an **Function Type** as pointer of your fresh lambda function

## Calling an Function Type

You cannot directly *call* an pointer (Function Type), you, unfortunately must store it inside some holder, and use `call` keyword/operator
```
func void f[]
    ...
end

func void main[]
    var v func void _[];
    &v pointer_of_proc f !<

    call v
end
```
## `functools`

*Gofra* provides general high-order functions within that module (`std/functools.gof`)
- `i_map`
- `i_reduce`

This is simple primitives that is extensible for your actual usage


## Closure Proposal

Closures is yet not available in *Gofra*, lambda functions is not capturing-lambda-functions