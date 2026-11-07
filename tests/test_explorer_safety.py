"""
tests/test_explorer_safety.py
=============================
Filesystem-safety tests for the project explorer's file management (#455):

* names taken by dangling symlinks are treated as occupied;
* create / rename / copy / move never replace an entry that appears between
  the existence check and the operation;
* symlinks and junctions are acted on as links, never followed to targets.

Symlink tests need permission to create symlinks (on Windows: Developer Mode
or an elevated shell) and are skipped otherwise. Junction tests run on Windows
only and need no special permission.
"""

from __future__ import annotations

import errno
import os
import shutil
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient

from backend import explorer_fs
from backend.main import app
from backend.routers import files


def _write(path: str, body: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.fixture()
def project():
    td = tempfile.mkdtemp()
    os.makedirs(os.path.join(td, "docs"))
    _write(os.path.join(td, "docs", "a.md"), "# A\n")
    _write(os.path.join(td, "b.md"), "keep me")
    yield td
    shutil.rmtree(td, ignore_errors=True)


@pytest.fixture()
def outside():
    td = tempfile.mkdtemp()
    _write(os.path.join(td, "secret.md"), "outside")
    yield td
    shutil.rmtree(td, ignore_errors=True)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def _symlink(target: str, link: str, *, is_dir: bool = False) -> None:
    try:
        os.symlink(target, link, target_is_directory=is_dir)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"cannot create symlinks here: {exc}")


def _junction(target: str, link: str) -> None:
    if sys.platform != "win32":
        pytest.skip("junctions are Windows-only")
    import _winapi

    _winapi.CreateJunction(target, link)


def _key(path) -> str:
    return os.path.normcase(os.path.realpath(path))


def _pretend_free(monkeypatch, *paths: str) -> None:
    """
    Make the up-front existence check miss ``paths``, as if another program
    created them after the check: the operation itself must still refuse.
    """
    real = explorer_fs.entry_exists
    hidden = {_key(path) for path in paths}
    monkeypatch.setattr(
        explorer_fs,
        "entry_exists",
        lambda path: False if _key(path) in hidden else real(path),
    )


def _post(client, action: str, **body):
    return client.post(f"/api/files/{action}", json=body)


# ── No-replace primitives ───────────────────────────────────────────────────


def test_rename_no_replace_refuses_an_existing_file_and_folder(tmp_path):
    src = tmp_path / "src.md"
    src.write_text("new")
    taken_file = tmp_path / "taken.md"
    taken_file.write_text("old")
    taken_dir = tmp_path / "taken"
    taken_dir.mkdir()

    for taken in (taken_file, taken_dir):
        with pytest.raises(FileExistsError):
            explorer_fs.rename_no_replace(src, taken)
    assert taken_file.read_text() == "old"
    assert src.read_text() == "new"


def test_rename_no_replace_refuses_a_dangling_symlink(tmp_path):
    src = tmp_path / "src.md"
    src.write_text("new")
    link = tmp_path / "link.md"
    _symlink(str(tmp_path / "missing"), str(link))

    with pytest.raises(FileExistsError):
        explorer_fs.rename_no_replace(src, link)
    assert os.path.islink(link) and src.exists()


def test_copy_no_replace_refuses_an_existing_file_and_folder(tmp_path):
    src_file = tmp_path / "a.md"
    src_file.write_text("new")
    src_dir = tmp_path / "dir"
    src_dir.mkdir()
    taken = tmp_path / "taken.md"
    taken.write_text("old")

    with pytest.raises(FileExistsError):
        explorer_fs.copy_no_replace(src_file, taken)
    with pytest.raises(FileExistsError):
        explorer_fs.copy_no_replace(src_dir, src_dir)
    assert taken.read_text() == "old"


def test_move_across_filesystems_copies_then_renames_without_replacing(
    tmp_path, monkeypatch
):
    real_rename = explorer_fs.rename_no_replace
    calls = []

    def rename_cross_device_once(src, dst):
        calls.append(dst)
        if len(calls) == 1:
            raise OSError(errno.EXDEV, "cross-device link")
        real_rename(src, dst)

    monkeypatch.setattr(explorer_fs, "rename_no_replace", rename_cross_device_once)
    src = tmp_path / "docs"
    src.mkdir()
    (src / "a.md").write_text("# A")
    dst = tmp_path / "archive" / "docs"
    dst.parent.mkdir()

    explorer_fs.move_no_replace(src, dst)
    assert (dst / "a.md").read_text() == "# A"
    assert not src.exists()
    assert sorted(os.listdir(dst.parent)) == ["docs"], "no staging copy left"

    # The fallback refuses an occupied destination and keeps the source.
    calls.clear()
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(FileExistsError):
        explorer_fs.move_no_replace(other, dst)
    assert other.exists()
    assert sorted(os.listdir(dst.parent)) == ["docs"]


# ── Endpoints: names taken by dangling symlinks ─────────────────────────────


def test_dangling_symlinks_count_as_occupied_names(client, project):
    docs = os.path.join(project, "docs")
    _symlink(os.path.join(project, "missing"), os.path.join(docs, "new.md"))
    _symlink(os.path.join(project, "missing"), os.path.join(project, "a.md"))
    _symlink(os.path.join(project, "missing"), os.path.join(docs, "b.md"))

    created = _post(client, "create", root=project, parent=docs, name="new.md")
    renamed = _post(
        client,
        "rename",
        root=project,
        path=os.path.join(docs, "a.md"),
        new_name="b.md",
    )
    moved = _post(
        client,
        "move",
        root=project,
        path=os.path.join(docs, "a.md"),
        dest_parent=project,
    )
    copied = _post(
        client,
        "copy",
        root=project,
        path=os.path.join(docs, "a.md"),
        dest_parent=project,
    )

    assert [created.status_code, renamed.status_code, moved.status_code] == [409] * 3
    assert copied.status_code == 200, copied.text
    assert os.path.basename(copied.json()["path"]) == "a copy.md"
    # The links are untouched and the source stayed where it was.
    for link in ("docs/new.md", "a.md", "docs/b.md"):
        assert os.path.islink(os.path.join(project, link))
    assert _read(os.path.join(docs, "a.md")) == "# A\n"


# ── Endpoints: an entry created between the check and the operation ─────────


def test_create_refuses_a_name_taken_after_the_check(client, project, monkeypatch):
    _pretend_free(
        monkeypatch, os.path.join(project, "b.md"), os.path.join(project, "docs")
    )
    file_res = _post(client, "create", root=project, parent=project, name="b.md")
    dir_res = _post(
        client, "create", root=project, parent=project, name="docs", is_dir=True
    )
    assert [file_res.status_code, dir_res.status_code] == [409, 409]
    assert _read(os.path.join(project, "b.md")) == "keep me"


def test_rename_refuses_a_name_taken_after_the_check(client, project, monkeypatch):
    _write(os.path.join(project, "docs", "c.md"), "keep me")
    _pretend_free(monkeypatch, os.path.join(project, "docs", "c.md"))
    response = _post(
        client,
        "rename",
        root=project,
        path=os.path.join(project, "docs", "a.md"),
        new_name="c.md",
    )
    assert response.status_code == 409
    assert _read(os.path.join(project, "docs", "c.md")) == "keep me"
    assert _read(os.path.join(project, "docs", "a.md")) == "# A\n"


def test_move_refuses_a_name_taken_after_the_check(client, project, monkeypatch):
    _write(os.path.join(project, "docs", "b.md"), "moving")
    _pretend_free(monkeypatch, os.path.join(project, "b.md"))
    response = _post(
        client,
        "move",
        root=project,
        path=os.path.join(project, "docs", "b.md"),
        dest_parent=project,
    )
    assert response.status_code == 409
    assert _read(os.path.join(project, "b.md")) == "keep me"
    assert _read(os.path.join(project, "docs", "b.md")) == "moving"


def test_copy_picks_the_next_name_when_one_is_taken_after_the_check(
    client, project, monkeypatch
):
    taken = os.path.join(project, "a.md")
    _write(taken, "keep me")
    _pretend_free(monkeypatch, taken)
    response = _post(
        client,
        "copy",
        root=project,
        path=os.path.join(project, "docs", "a.md"),
        dest_parent=project,
    )
    assert response.status_code == 200, response.text
    assert os.path.basename(response.json()["path"]) == "a copy.md"
    assert _read(taken) == "keep me"


# ── Endpoints: symlinks are handled as links ────────────────────────────────


def test_delete_removes_a_symlink_not_its_target(client, project, monkeypatch):
    trashed = []
    monkeypatch.setattr(files, "_move_to_trash", trashed.append)
    target = os.path.join(project, "docs", "a.md")
    link = os.path.join(project, "link.md")
    dangling = os.path.join(project, "dangling.md")
    _symlink(target, link)
    _symlink(os.path.join(project, "missing"), dangling)

    for path in (link, dangling):
        response = _post(client, "delete", root=project, path=path)
        assert response.status_code == 200, response.text
        assert not os.path.lexists(path)
    assert _read(target) == "# A\n"
    assert trashed == [], "links are removed directly, not via the trash"


def test_rename_renames_the_symlink_not_its_target(client, project):
    target = os.path.join(project, "docs", "a.md")
    link = os.path.join(project, "link.md")
    _symlink(target, link)

    response = _post(client, "rename", root=project, path=link, new_name="renamed.md")
    assert response.status_code == 200, response.text
    assert os.path.islink(os.path.join(project, "renamed.md"))
    assert os.path.isfile(target), "the target keeps its name"


def test_links_pointing_outside_the_project_affect_only_the_link(
    client, project, outside, monkeypatch
):
    monkeypatch.setattr(files, "_move_to_trash", lambda path: None)
    secret = os.path.join(outside, "secret.md")
    link = os.path.join(project, "out.md")
    _symlink(secret, link)

    copied = _post(client, "copy", root=project, path=link, dest_parent=project)
    renamed = _post(client, "rename", root=project, path=link, new_name="out2.md")
    deleted = _post(
        client, "delete", root=project, path=os.path.join(project, "out2.md")
    )

    assert [copied.status_code, renamed.status_code, deleted.status_code] == [200] * 3
    copy_path = copied.json()["path"]
    assert os.path.islink(copy_path), "a link is copied as a link, not its content"
    assert os.readlink(copy_path) == secret
    assert os.listdir(outside) == ["secret.md"]
    assert _read(secret) == "outside"


def test_folders_linked_to_outside_the_project_cannot_be_written_into(
    client, project, outside
):
    link = os.path.join(project, "outlink")
    _symlink(outside, link, is_dir=True)

    created = _post(client, "create", root=project, parent=link, name="x.md")
    pasted = _post(
        client,
        "copy",
        root=project,
        path=os.path.join(project, "b.md"),
        dest_parent=link,
    )
    assert [created.status_code, pasted.status_code] == [403, 403]
    assert os.listdir(outside) == ["secret.md"]


def test_copying_a_folder_keeps_symlinks_inside_it_as_links(client, project, outside):
    secret = os.path.join(outside, "secret.md")
    _symlink(secret, os.path.join(project, "docs", "out.md"))

    response = _post(
        client,
        "copy",
        root=project,
        path=os.path.join(project, "docs"),
        dest_parent=project,
    )
    assert response.status_code == 200, response.text
    copied_link = os.path.join(project, "docs copy", "out.md")
    assert os.path.islink(copied_link)
    assert os.readlink(copied_link) == secret


# ── Endpoints: Windows junctions (no special permission needed) ─────────────


def test_junctions_are_handled_as_links(client, project, outside, monkeypatch):
    trashed = []
    monkeypatch.setattr(files, "_move_to_trash", trashed.append)
    junction = os.path.join(project, "junction")
    _junction(outside, junction)

    pasted_into = _post(
        client,
        "copy",
        root=project,
        path=os.path.join(project, "b.md"),
        dest_parent=junction,
    )
    copied = _post(client, "copy", root=project, path=junction, dest_parent=project)
    renamed = _post(client, "rename", root=project, path=junction, new_name="junction2")
    deleted = _post(
        client, "delete", root=project, path=os.path.join(project, "junction2")
    )

    assert pasted_into.status_code == 403
    assert copied.status_code == 400
    assert [renamed.status_code, deleted.status_code] == [200, 200]
    assert not os.path.lexists(os.path.join(project, "junction2"))
    assert trashed == []
    assert os.listdir(outside) == ["secret.md"], "the junction's target is untouched"


def test_copying_a_folder_that_contains_a_junction_is_refused(client, project, outside):
    _junction(outside, os.path.join(project, "docs", "junction"))
    response = _post(
        client,
        "copy",
        root=project,
        path=os.path.join(project, "docs"),
        dest_parent=project,
    )
    assert response.status_code == 400
    assert not os.path.exists(os.path.join(project, "docs copy"))
