# Generic Types

#### This page uses some general terminology of [Type Theory](https://en.wikipedia.org/wiki/Type_theory) for [Type Systems](https://en.wikipedia.org/wiki/Type_system)

Generics in Gofra are form of lazy template for any concrete type

## Current limitations and known problems

These must be resolved later
- Applying generic type requires type parameter name
- Cannot define generic for function
- Cannot apply/reference generic in form of defining another generic

## Concrete types

By default any primitives type (`int`, `char`, ...) are concrete types, this means they have known size in bytes, and structure field / variable can has type of concrete kind.

Composite types (Pointers, Arrays) with primitive types also concrete - they has known size directly

Only concrete types may be used inside any non *type-expression definition* (e.g `type`) form (unless for Generics they must applied into Concrete types with Generic Type Parameters)

## Defining an generic type

```gofra

// Generic defined as *Identity* (apply Type Parameter to concrete type of same type)
type Identity{T} = T

// Pointer to generic type parameter
type XT{T} = *T 

// Array of type T with size N (where N is value type parameter)
type Array{T, N} = T[N]

// Sort of dynamic array / slice view with generics
// Struct will be different each application into concrete one
struct Slice{T, K}
    data *T[K]
    len int
end
```

## Applying generic types into concrete one

As far you know - generic types cannot be used outside of `type` definition, you need to apply them otherwise

Applying generic type - is same as transforming it to generic one with known size and types
```gofra
type Identity{T} = T

// Applying generic type into concrete (expanding type parameters)
var HasConcreteType = Identity{T = int}
// typeof is `int`

// With value type arguments
var arr Array{T = int, N = 3}
```

## Terminology

- **Type Parameter**: `T` in `Identity{T}`
- **Type Argument**: `int` in `Identity{T = int}`  
- **Generic Type**: `Identity{T}` (unapplied)
- **Applied Generic**: `Identity{T = int}` (concrete)
- **Concrete Type**: Fully resolved type with known size