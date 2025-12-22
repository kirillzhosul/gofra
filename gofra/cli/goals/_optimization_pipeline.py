from gofra.cli.output import cli_message
from gofra.cli.parser.arguments import CLIArguments
from libgofra.hir.module import Module
from libgofra.optimizer.pipeline import create_optimizer_pipeline


def cli_process_optimization_pipeline(
    program: Module,
    args: CLIArguments,
) -> None:
    """Apply optimization pipeline for program according to CLI arguments."""
    pipeline = create_optimizer_pipeline(args.optimizer)
    for optimizer_pass, optimizer_pass_name in pipeline:
        cli_message(
            level="INFO",
            text=f"Applying optimizer '{optimizer_pass_name}' pass",
            verbose=args.verbose,
        )
        optimizer_pass(program)
