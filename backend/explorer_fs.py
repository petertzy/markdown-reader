"""
backend/explorer_fs.py
======================
Filesystem primitives for the project explorer's file management (issue #455).

The explorer promises never to overwrite an existing entry. Checking first and
then acting leaves a window in which another program can create the
destination, so every operation here asks the operating system to refuse an
occupied name itself:

* Rename / move use ``renameat2(RENAME_NOREPLACE)`` on Linux,
  ``renamex_np(RENAME_EXCL)`` on macOS, and ``os.rename`` on Windows, which
  never replaces an existing entry there.
* Copy creates the new file with ``O_EXCL`` (``open(..., "xb")``) and new
  folders with ``mkdir``, both of which fail if the name is taken.

Only when a filesystem does not support the no-replace rename (for example
some network filesystems) does :func:`rename_no_replace` fall back to a check
followed by a plain rename. That fallback still refuses names it can see, but
cannot rule out an entry created in between.

Symlinks and Windows junctions are handled as links: they are renamed, moved,
copied and removed as the link itself, and never followed to their target.

All functions raise :class:`FileExistsError` when the destination is taken.
"""

from __future__ import annotations

import ctypes
import errno
import os
import shutil
import stat
import sys
import uuid
from pathlib import Path

# Errors meaning "this filesystem / kernel does not support the call", as
# opposed to a real failure such as a missing file or an occupied name.
_UNSUPPORTED_ERRNOS = {
    errno.ENOSYS,
    errno.EINVAL,
    getattr(errno, "ENOTSUP", errno.EINVAL),
    getattr(errno, "EOPNOTSUPP", errno.EINVAL),
}

_AT_FDCWD = -100  # Linux: resolve relative paths against the working directory.
_RENAME_NOREPLACE = 1  # Linux renameat2 flag.
_RENAME_EXCL = 0x00000004  # macOS renamex_np flag.
# Windows reparse tag of a junction. Defined here because the ``stat`` module
# only provides IO_REPARSE_TAG_* constants on Windows.
_IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003


class UnsupportedEntryError(Exception):
    """Raised for entries the explorer refuses to copy (Windows junctions)."""


def _libc_function(name: str):
    """Return the C library function ``name``, or ``None`` if unavailable."""
    try:
        return getattr(ctypes.CDLL(None, use_errno=True), name)
    except (AttributeError, OSError):
        return None


def entry_exists(path: Path) -> bool:
    """
    Whether a directory entry occupies ``path``.

    Unlike ``Path.exists()``, a dangling symlink counts as occupied.

    :param Path path: Path to check.

    :return: True if anything, including a broken link, is at ``path``.
    """
    return os.path.lexists(path)


def is_link(path: Path) -> bool:
    """
    Whether ``path`` is a symlink or a Windows junction (not followed).

    :param Path path: Path to check.

    :return: True for symlinks (including dangling ones) and junctions.
    """
    try:
        info = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    return _is_junction_stat(info)


def _is_junction_stat(info: os.stat_result) -> bool:
    return getattr(info, "st_reparse_tag", 0) == _IO_REPARSE_TAG_MOUNT_POINT


def _native_rename_no_replace(src: Path, dst: Path) -> bool:
    """
    Rename with the OS's no-replace call.

    :return: True if the rename was done, False if the platform or filesystem
        does not support a no-replace rename.

    :raises OSError: ``FileExistsError`` if ``dst`` is taken, or any other
        error from the rename.
    """
    if sys.platform == "win32":
        # MoveFileEx without MOVEFILE_REPLACE_EXISTING: never replaces.
        os.rename(src, dst)
        return True

    if sys.platform.startswith("linux"):
        func = _libc_function("renameat2")
        args = (
            _AT_FDCWD,
            os.fsencode(src),
            _AT_FDCWD,
            os.fsencode(dst),
            _RENAME_NOREPLACE,
        )
    elif sys.platform == "darwin":
        func = _libc_function("renamex_np")
        args = (os.fsencode(src), os.fsencode(dst), _RENAME_EXCL)
    else:
        return False
    if func is None:
        return False

    if func(*args) == 0:
        return True
    code = ctypes.get_errno()
    if code in _UNSUPPORTED_ERRNOS:
        return False
    raise OSError(code, os.strerror(code), str(src), None, str(dst))


def rename_no_replace(src: Path, dst: Path) -> None:
    """
    Rename ``src`` to ``dst``, refusing to replace an existing entry.

    The refusal is atomic on Windows, Linux and macOS (see the module notes).
    ``src`` is renamed as itself, so a symlink is renamed as the link.

    :param Path src: Entry to rename.
    :param Path dst: New path; must not exist.

    :raises FileExistsError: If ``dst`` is taken.
    :raises OSError: For any other filesystem error, including ``EXDEV`` when
        ``src`` and ``dst`` are on different filesystems.
    """
    if _native_rename_no_replace(src, dst):
        return
    # Fallback for filesystems without a no-replace rename.
    if entry_exists(dst):
        raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(dst))
    os.rename(src, dst)


def copy_no_replace(src: Path, dst: Path) -> None:
    """
    Copy ``src`` to ``dst``, refusing to replace an existing entry.

    * A symlink is copied as a new link with the same target, so a link that
      points outside the project never pulls that content in.
    * A folder is copied with its contents; symlinks inside it are copied as
      links. ``dst`` is created with ``mkdir``, which fails if it is taken.
    * A file is written to a new file opened with ``O_EXCL``.

    :param Path src: Entry to copy.
    :param Path dst: Path of the copy; must not exist.

    :raises FileExistsError: If ``dst`` is taken.
    :raises UnsupportedEntryError: If ``src`` is or contains a Windows junction.
    """
    info = os.lstat(src)
    if _is_junction_stat(info):
        raise UnsupportedEntryError(f"Cannot copy a junction: {src.name}")

    if stat.S_ISLNK(info.st_mode):
        os.symlink(os.readlink(src), dst, target_is_directory=src.is_dir())
    elif stat.S_ISDIR(info.st_mode):
        _refuse_junctions_inside(src)
        shutil.copytree(src, dst, symlinks=True)
    else:
        with open(src, "rb") as source, open(dst, "xb") as target:
            try:
                shutil.copyfileobj(source, target)
            except BaseException:
                target.close()
                os.unlink(dst)
                raise
        shutil.copystat(src, dst)


def _refuse_junctions_inside(folder: Path) -> None:
    """``shutil.copytree`` would copy through a junction, so refuse those."""
    if sys.platform != "win32":
        return
    pending = [folder]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                if _is_junction_stat(entry.stat(follow_symlinks=False)):
                    raise UnsupportedEntryError(
                        f"Cannot copy a folder that contains a junction: {entry.name}"
                    )
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))


def move_no_replace(src: Path, dst: Path) -> None:
    """
    Move ``src`` to ``dst``, refusing to replace an existing entry.

    Within one filesystem this is :func:`rename_no_replace`. Across
    filesystems, ``src`` is copied to a temporary name next to ``dst``, then
    renamed into place with no-replace semantics, and only then removed.

    :param Path src: Entry to move.
    :param Path dst: New path; must not exist.

    :raises FileExistsError: If ``dst`` is taken. ``src`` is left in place.
    """
    try:
        rename_no_replace(src, dst)
        return
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise

    staging = dst.with_name(f".{dst.name}.{uuid.uuid4().hex}.partial")
    copy_no_replace(src, staging)
    try:
        rename_no_replace(staging, dst)
    except BaseException:
        remove_entry(staging)
        raise
    remove_entry(src)


def remove_link(path: Path) -> None:
    """
    Remove a symlink or junction itself, leaving its target untouched.

    :param Path path: The link to remove.
    """
    info = os.lstat(path)
    is_dir_link = sys.platform == "win32" and bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_DIRECTORY
    )
    if is_dir_link:
        os.rmdir(path)  # Directory symlinks and junctions on Windows.
    else:
        os.unlink(path)


def remove_entry(path: Path) -> None:
    """Permanently remove ``path`` (used only for the move's own copies)."""
    if is_link(path):
        remove_link(path)
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        os.unlink(path)
