"""
tests/test_files_endpoints.py
=============================
Endpoint tests for the files router's listing behavior.
"""

from __future__ import annotations

import os
import shutil
import tempfile

from fastapi.testclient import TestClient

from backend.main import app


def _dir_with_files() -> str:
    td = tempfile.mkdtemp()
    for name, body in (
        ("a.md", "markdown"),
        ("notes.txt", "text"),
        ("noext", "extensionless"),
    ):
        with open(os.path.join(td, name), "w", encoding="utf-8") as f:
            f.write(body)
    return td


def _list_names(td: str, extensions: str) -> list[str]:
    with TestClient(app) as client:
        response = client.get(
            "/api/files/list", params={"path": td, "extensions": extensions}
        )
        assert response.status_code == 200, response.text
        return sorted(entry["name"] for entry in response.json()["entries"])


def test_extension_filter_ignores_empty_segments():
    # A stray trailing comma ("md,") is the same filter as "md"; it must not
    # silently let extensionless files through because "" landed in the
    # allowlist.
    td = _dir_with_files()
    try:
        assert _list_names(td, "md") == ["a.md"]
        assert _list_names(td, "md,") == ["a.md"]
        assert _list_names(td, "md, ,txt") == ["a.md", "notes.txt"]
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_extension_filter_keeps_no_extensionless_file_for_any_segment_form():
    # Empty raw segments and segments that normalise to empty after dropping
    # optional leading dots must never match the extensionless file.
    td = _dir_with_files()
    try:
        for raw in ("md,", "md, ", ",md", " md ", "md,.", "md,.."):
            names = _list_names(td, raw)
            assert "noext" not in names, raw
            assert "a.md" in names, raw
    finally:
        shutil.rmtree(td, ignore_errors=True)


# ── UTF-8 BOM handling ──────────────────────────────────────────────────────


def _write_bom_file(directory: str, name: str, body: bytes) -> str:
    path = os.path.join(directory, name)
    with open(path, "wb") as file_obj:
        file_obj.write(b"\xef\xbb\xbf" + body)
    return path


def test_read_endpoint_strips_a_utf8_bom():
    # Windows editors prepend a UTF-8 BOM. If it survives the read it becomes an
    # invisible first character, so "# Title" is no longer recognised as a
    # heading and the outline loses the document's title.
    td = tempfile.mkdtemp()
    try:
        path = _write_bom_file(td, "note.md", b"# Title\n\nBody.\n")
        with TestClient(app) as client:
            response = client.get("/api/files/read", params={"path": path})
        assert response.status_code == 200, response.text
        assert response.json()["content"] == "# Title\n\nBody.\n"
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_convert_local_markdown_strips_a_utf8_bom():
    from backend.routers.files import _convert_local_file_to_markdown

    td = tempfile.mkdtemp()
    try:
        path = _write_bom_file(td, "note.md", b"# Title\n\nBody.\n")
        assert _convert_local_file_to_markdown(path, "note.md") == "# Title\n\nBody.\n"
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_convert_local_html_strips_a_utf8_bom():
    from backend.routers.files import _convert_local_file_to_markdown

    td = tempfile.mkdtemp()
    try:
        path = _write_bom_file(
            td, "page.html", b"<html><body><h1>Title</h1></body></html>"
        )
        converted = _convert_local_file_to_markdown(path, "page.html")
        assert "\ufeff" not in converted
        assert "Title" in converted
    finally:
        shutil.rmtree(td, ignore_errors=True)


# ── Project explorer: create / rename / delete ─────────────────────────────


def _project() -> str:
    td = tempfile.mkdtemp()
    os.makedirs(os.path.join(td, "docs"))
    with open(os.path.join(td, "docs", "a.md"), "w", encoding="utf-8") as f:
        f.write("# A\n")
    return td


def test_create_file_and_folder_inside_project():
    td = _project()
    try:
        with TestClient(app) as client:
            file_res = client.post(
                "/api/files/create",
                json={"root": td, "parent": td, "name": "new.md"},
            )
            dir_res = client.post(
                "/api/files/create",
                json={"root": td, "parent": td, "name": "sub", "is_dir": True},
            )
        assert file_res.status_code == 200, file_res.text
        assert dir_res.status_code == 200, dir_res.text
        assert os.path.isfile(os.path.join(td, "new.md"))
        assert os.path.isdir(os.path.join(td, "sub"))
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_create_refuses_existing_entry():
    td = _project()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/files/create",
                json={"root": td, "parent": td, "name": "docs", "is_dir": True},
            )
        assert response.status_code == 409
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_names_that_are_paths_are_rejected():
    # A name like "../escape.md" would otherwise create a file outside the
    # folder the user right-clicked.
    td = _project()
    try:
        with TestClient(app) as client:
            for name in ("", "  ", ".", "..", "../escape.md", "a/b.md", "a\b.md"):
                response = client.post(
                    "/api/files/create",
                    json={"root": td, "parent": td, "name": name},
                )
                assert response.status_code == 400, name
        assert not os.path.exists(os.path.join(os.path.dirname(td), "escape.md"))
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_rename_file_keeps_it_in_the_same_folder():
    td = _project()
    old = os.path.join(td, "docs", "a.md")
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/files/rename",
                json={"root": td, "path": old, "new_name": "b.md"},
            )
        assert response.status_code == 200, response.text
        assert not os.path.exists(old)
        assert os.path.isfile(os.path.join(td, "docs", "b.md"))
        assert os.path.samefile(
            response.json()["path"], os.path.join(td, "docs", "b.md")
        )
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_rename_refuses_to_overwrite_a_sibling():
    td = _project()
    sibling = os.path.join(td, "docs", "b.md")
    with open(sibling, "w", encoding="utf-8") as f:
        f.write("keep me")
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/files/rename",
                json={
                    "root": td,
                    "path": os.path.join(td, "docs", "a.md"),
                    "new_name": "b.md",
                },
            )
        assert response.status_code == 409
        with open(sibling, encoding="utf-8") as f:
            assert f.read() == "keep me"
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_delete_moves_entry_to_trash(monkeypatch):
    from backend.routers import files

    trashed: list[str] = []
    monkeypatch.setattr(files, "_move_to_trash", lambda path: trashed.append(str(path)))
    td = _project()
    target = os.path.join(td, "docs")
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/files/delete", json={"root": td, "path": target}
            )
        assert response.status_code == 200, response.text
        assert len(trashed) == 1
        assert os.path.samefile(trashed[0], target)
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_operations_outside_the_project_are_refused(monkeypatch):
    from backend.routers import files

    monkeypatch.setattr(files, "_move_to_trash", lambda path: None)
    td = _project()
    outside = tempfile.mkdtemp()
    outside_file = os.path.join(outside, "secret.md")
    with open(outside_file, "w", encoding="utf-8") as f:
        f.write("x")
    try:
        with TestClient(app) as client:
            responses = [
                client.post(
                    "/api/files/delete", json={"root": td, "path": outside_file}
                ),
                client.post(
                    "/api/files/delete",
                    json={"root": td, "path": os.path.join(td, "..", "x")},
                ),
                client.post(
                    "/api/files/rename",
                    json={"root": td, "path": outside_file, "new_name": "y.md"},
                ),
                client.post(
                    "/api/files/create",
                    json={"root": td, "parent": outside, "name": "z.md"},
                ),
                # The project folder itself cannot be deleted or renamed.
                client.post("/api/files/delete", json={"root": td, "path": td}),
                client.post(
                    "/api/files/rename",
                    json={"root": td, "path": td, "new_name": "renamed"},
                ),
            ]
        assert [r.status_code for r in responses] == [403] * len(responses)
        assert os.path.isfile(outside_file)
        assert not os.path.exists(os.path.join(outside, "z.md"))
    finally:
        shutil.rmtree(td, ignore_errors=True)
        shutil.rmtree(outside, ignore_errors=True)


# ── Project explorer: cut / copy / paste ───────────────────────────────────


def _transfer(client, action: str, root: str, path: str, dest: str):
    return client.post(
        f"/api/files/{action}", json={"root": root, "path": path, "dest_parent": dest}
    )


def test_copy_keeps_the_name_in_another_folder():
    td = _project()
    try:
        with TestClient(app) as client:
            response = _transfer(
                client, "copy", td, os.path.join(td, "docs", "a.md"), td
            )
        assert response.status_code == 200, response.text
        assert os.path.samefile(response.json()["path"], os.path.join(td, "a.md"))
        assert os.path.isfile(os.path.join(td, "docs", "a.md")), "source is kept"
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_copy_into_the_same_folder_picks_a_copy_name():
    td = _project()
    source = os.path.join(td, "docs", "a.md")
    try:
        with TestClient(app) as client:
            first = _transfer(client, "copy", td, source, os.path.join(td, "docs"))
            second = _transfer(client, "copy", td, source, os.path.join(td, "docs"))
            folder = _transfer(client, "copy", td, os.path.join(td, "docs"), td)
        names = [os.path.basename(r.json()["path"]) for r in (first, second, folder)]
        assert names == ["a copy.md", "a copy 2.md", "docs copy"]
        with open(os.path.join(td, "docs copy", "a.md"), encoding="utf-8") as f:
            assert f.read() == "# A\n", "folders are copied with their contents"
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_move_puts_the_entry_in_the_destination():
    td = _project()
    os.makedirs(os.path.join(td, "archive"))
    try:
        with TestClient(app) as client:
            response = _transfer(
                client,
                "move",
                td,
                os.path.join(td, "docs"),
                os.path.join(td, "archive"),
            )
        assert response.status_code == 200, response.text
        assert not os.path.exists(os.path.join(td, "docs"))
        assert os.path.isfile(os.path.join(td, "archive", "docs", "a.md"))
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_move_refuses_to_overwrite_and_pasting_in_place_is_a_no_op():
    td = _project()
    with open(os.path.join(td, "a.md"), "w", encoding="utf-8") as f:
        f.write("keep me")
    source = os.path.join(td, "docs", "a.md")
    try:
        with TestClient(app) as client:
            clash = _transfer(client, "move", td, source, td)
            in_place = _transfer(client, "move", td, source, os.path.join(td, "docs"))
        assert clash.status_code == 409
        with open(os.path.join(td, "a.md"), encoding="utf-8") as f:
            assert f.read() == "keep me"
        assert in_place.status_code == 200, in_place.text
        assert os.path.isfile(source)
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_a_folder_cannot_be_pasted_into_itself():
    td = _project()
    docs = os.path.join(td, "docs")
    os.makedirs(os.path.join(docs, "inner"))
    try:
        with TestClient(app) as client:
            codes = [
                _transfer(client, action, td, docs, dest).status_code
                for action in ("copy", "move")
                for dest in (docs, os.path.join(docs, "inner"))
            ]
        assert codes == [400] * 4
        assert sorted(os.listdir(docs)) == ["a.md", "inner"]
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_copy_and_move_outside_the_project_are_refused():
    td = _project()
    outside = tempfile.mkdtemp()
    outside_file = os.path.join(outside, "secret.md")
    with open(outside_file, "w", encoding="utf-8") as f:
        f.write("x")
    source = os.path.join(td, "docs", "a.md")
    try:
        with TestClient(app) as client:
            codes = [
                _transfer(client, "copy", td, source, outside).status_code,
                _transfer(client, "move", td, source, outside).status_code,
                _transfer(client, "copy", td, outside_file, td).status_code,
                _transfer(client, "move", td, outside_file, td).status_code,
                # The project folder itself cannot be cut or copied.
                _transfer(client, "move", td, td, os.path.join(td, "docs")).status_code,
            ]
        assert codes == [403] * 5
        assert os.listdir(outside) == ["secret.md"]
        assert os.path.isfile(source)
    finally:
        shutil.rmtree(td, ignore_errors=True)
        shutil.rmtree(outside, ignore_errors=True)
