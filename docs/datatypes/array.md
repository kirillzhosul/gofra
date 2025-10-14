# Array data type

In Gofra *array* is a composite data type that represents a pointer to a contiguous segment of memory storing a fixed number of elements of the same specified type. 
Unlike dynamic collections, arrays in Gofra have a predetermined size that cannot be changed after declaration.

## Layout

In memory, as array being contiguous blob of memory, it corresponding value points at first element in memory
shifting that pointer
```
//  [element0element1element2]
//   ^       ^
// array ptr |
//      ptr+sizeof
```

So accessing memory at array pointer will lead to reading its first element
While second element is at pointer + size of array element

For `int8` which size is 8 bytes, `var array int[3]` according to image above has memory layout like

array      -> pointer to an first element
array + 8  -> pointer to an second element
array + 16 -> pointer to an third element

For convenient usage of layout, see *Accessing array element* section

## Syntax

Array type is defined as element type followed by square brackets
```gofra
int[32] // Array of 32 integer elements 
int[] // Incomplete array definition, for type parameters
```

## Initialization
Arrays currently does not have constructors, and by default all arrays are zero-initialized
You has to manually initialize array with memory write instructions

## Incomplete array type definition

As you see before, there is possibility to define an incomplete type for array (e.g `int[]`) this has no effect while used as variable or field type
as leading to generation of an empty blob segment (zero elements by default, meaning size of array is zero, no way to generate that blob or it is inaccessible)
This incomplete array types is used as function parameters, as mark that array has any arbitrary size while passed to desired function:
```gofra
func void incomplete_array[int[]]
    ...
end
```

This function can be called with array of any size like `int[32]` or `int[1]` but any other type is prohibited
Mostly, useful for accepting array of character as strings, as size is useless mostly for these function (e.g to calculate string size)

## Accessing array element

As documented in *Layout* section, you must already know how does array layouts in memory, but using pointer arithmetics is weird as you can access direct array indices at runtime via
```gofra
var array int[32]

array[0] // pointer to an first element, same as `array`
array[3] // pointer to third element, same as `array + sizeof(int) * 3` or `array + 8 * 3` which is shift pointer by 24
```
### Pointer arithmetics equivalent
```gofra
var array int[32]

array 8 0 * + // pointer to first element
array 8 3 * + // pointer to third element
```

### OOB (Out-Of-Bounds)

Gofra performs compile-time bounds checking where possible:
```gofra
var array int[5]
array[5] // Compilation error: OOB for array access
```