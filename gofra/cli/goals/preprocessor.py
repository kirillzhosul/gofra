from __future__ import annotations

import sys
from typing import TYPE_CHECKING, NoReturn

from gofra.cli.output import cli_message
from gofra.lexer import tokenize_from_raw
from gofra.lexer.io.io import open_source_file_line_stream
from gofra.lexer.tokens import TokenLocation
from gofra.preprocessor.macros.registry import registry_from_raw_definitions
from gofra.preprocessor.preprocessor import preprocess_file

if TYPE_CHECKING:
    from gofra.cli.parser.arguments import CLIArguments


def cli_perform_preprocess_goal(args: CLIArguments) -> NoReturn:
    """Perform preprocess only goal that emits preprocessed tokens into stdout."""
    assert args.preprocess_only, (
        "Cannot perform preprocessor goal with no preprocessor flag set!"
    )

    if args.output_file_is_specified:
        cli_message(
            "ERROR",
            "Output file has no effect for preprocess only goal, please pipe output via posix pipe (`>`) into desired file!",
        )
        return sys.exit(1)

    if len(args.source_filepaths) > 1:
        cli_message(
            "ERROR",
            "Multiple source files has not effect for preprocess only goal, as it has no linkage, please specify single file!",
        )
        return sys.exit(1)

    macros_registry = registry_from_raw_definitions(
        location=TokenLocation.cli(),
        definitions=args.definitions,
    ).inject_propagated_defaults(target=args.target)

    path = args.source_filepaths[0]
    io = open_source_file_line_stream(path)
    lexer = tokenize_from_raw(path, io)
    preprocessor = preprocess_file(
        args.source_filepaths[0],
        lexer,
        args.include_paths,
        macros=macros_registry,
    )

    for token in preprocessor:
        token_text = str(token.text)
        print(token_text, end=" ")

    return sys.exit(0)
