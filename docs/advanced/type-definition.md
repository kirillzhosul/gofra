# Type definition

Gofra has `type` keyword that allows define types (Generic types, type aliases)

## Type alias(ing)

Type definition allows to define type alias to arbitrary data type
```gofra
type Alias = int

var x Alias = 5; // same as int
```


## Generics

Type definitions is also used to define an generic type
```gofra
type Generic{T} = T
```

Read more at [Generic](./generic-types.md) types page
