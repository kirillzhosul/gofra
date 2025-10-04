from gofra.typecheck.containers.typestack import TypeStack


class TypecheckerState:
    # Typecheck emulates runtime type stack
    # this structure contains runtime values mapped to an types
    # e.g in runtime we have `2 2` and this maps to stack [2, 2]
    # At typechecker stage we deal with types so `2 2` becomes [INT, INT]
    stack: TypeStack
