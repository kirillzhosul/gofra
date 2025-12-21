from hashlib import md5
from pathlib import Path

from gofra.cli.parser.arguments import CLIArguments
from libgofra.hir.module import Module


def _is_file_modified_after(a: Path, b: Path) -> bool:
    """Return true if *b* is modified after than *a*."""
    a_mat = a.stat().st_mtime
    b_mat = b.stat().st_mtime
    return b_mat >= a_mat


def is_module_needs_rebuild(
    args: CLIArguments,
    mod: Module,
    rebuild_artifact: Path,
) -> bool:
    # Possibly, this may fail due to incremental compilation
    # if some dependency was invalidated ?
    if not args.incremental_compilation:
        return True
    if not rebuild_artifact.exists(follow_symlinks=False):
        return True
    return _is_file_modified_after(rebuild_artifact, mod.path)


def get_module_hash(mod: Module) -> str:
    mod_str = str(mod.path.absolute()).encode()
    mod_hash = md5(mod_str, usedforsecurity=False)
    mod_file_name = mod.path.with_suffix("").name
    return mod_file_name + "_" + mod_hash.hexdigest()
