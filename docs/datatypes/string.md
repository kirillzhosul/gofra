# String data type

Strings in Gofra are represented via *Fat Pointers* (Or also called *String View* and *String Slice*) 

Using `string` data type:
```gofra
var str *string = "text" // Type may be omitted

"another text" // Pushes *string on stack

str.data // Push underlying *boxed* pointer to CStr (*char[])
str.len // Size (bytes) of the string (character length in UTF-8 as single byte for character)
```

Internally, `string` structure type is available for any compiled program and defined like so:
```
type struct string
    data *char[]
    len int
end
```

That structure takes 16 bytes (8 bytes ptr, 8 bytes len)

Strings defined internally in source code located in *static* data segment (must has Read-Only memory protection)