"""System level I/O permissions.

(e.g Operating system permissions on filesystem)
Useful for manipulating on an output executable from an toolchain
"""

import stat
import sys
from pathlib import Path


def apply_file_executable_permissions(filepath: Path) -> None:
    """Change file permissions to make it executable in secure manner.

    :param filepath: Path to file
    :raises OSError: If path is not an file.
    :raises PermissionError: If it is an symlink or not enough permissions to change file mode
    """
    if sys.platform == "win32":
        return

    if not filepath.is_file():
        msg = f"Cannot apply file executable permissions for an non-file ({filepath}), this is probably an bug in the toolchain"
        raise OSError(msg)

    if filepath.is_symlink():
        msg = "Cannot securely apply executable permission on symlink, this is security consideration and probably an bug in the toolchain"
        raise PermissionError(msg)

    # Securely append only execution for current user (owner) and others in his group
    executable_mode = stat.S_IXUSR | stat.S_IXGRP
    prohibit_mode = ~stat.S_IXOTH

    # Do not override permissions with new, append only possible new ones and remove insecure
    current_mode = filepath.stat().st_mode
    new_mode = (current_mode | executable_mode) & prohibit_mode
    filepath.chmod(mode=new_mode, follow_symlinks=False)
