# Type casting

There is always situations when you need to cast one type to another to silence errors from typechecker as it quite dumb and may stay on your way
For that you have type casting feature (static type casts) only


## Static type cast

Static type cast is an form of casting to an desired type which has no effect on runtime, only compile-time type checking only
to statically cast to an type you may do following
```gofra
var a char

a typecast int 2 * // by default multiplying an char is not possible
```

typecasts is always in form of:
```gofra
typecast {type_definition_from_scope}
```

You may write any arbitrary and composite / complex types inside typecast (e.g cast to an pointer to an struct)