# Function type and Function pointer

## `pointer_of_proc`

Pushes pointer of specified function onto the stack
```
func void f[]
    ...
end


pointer_of_proc f // () -> void
```


## Defining an function type

```
func void f[]
    ...
end


type FunctionType func void _[]

var x FunctionType;
var v func void _[];
```

## Calling from function type holder

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