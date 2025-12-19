"""HIR - High Level Intermediate Representation.

HIR is an form of representing code in level, higher from tokenizer lexemes (lexer tokens)
For example `2 2 +` forms and [Operator.INTEGER(2), Operator.INTEGER(2), Operator.PLUS)
(Complex examples is for example variable type definition which is an complex token stream formed in an container with another container with type)

As Gofra is an concatenative stack-based language, HIR does not contain any AST (abstract-syntax-tree)
"""
