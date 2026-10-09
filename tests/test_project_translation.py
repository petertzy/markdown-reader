"""Project-wide Markdown translation: protection, discovery, and task control."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.project_translation import (
    ProjectTranslationError,
    cancel_project_translation,
    discover_markdown_files,
    protect_markdown,
    reset_project_translations,
    restore_markdown,
    run_project_translation,
    start_project_translation,
    translate_markdown_document,
    wait_for_project_translation,
)


def _french(content: str, source: str, target: str) -> str:
    del source, target
    return content.replace("Hello", "Bonjour").replace("World", "Monde")


def test_code_fence_and_inline_code_round_trip():
    source = "Hello\n\n```python\nprint('Hello')\n```\n\nSee `Hello` World.\n"
    translated = translate_markdown_document(source, "English", "French", _french)
    assert (
        translated
        == "Bonjour\n\n```python\nprint('Hello')\n```\n\nSee `Hello` Monde.\n"
    )


def test_link_text_is_translated_and_url_is_kept():
    source = "Hello [World](https://example.com/Hello)."
    translated = translate_markdown_document(source, "English", "French", _french)
    assert translated == "Bonjour [Monde](https://example.com/Hello)."


def test_image_alt_is_translated_and_path_is_kept():
    source = "![Hello World](./images/Hello.png)"
    translated = translate_markdown_document(source, "English", "French", _french)
    assert translated == "![Bonjour Monde](./images/Hello.png)"


def test_autolink_bare_url_and_math_stay_verbatim():
    source = (
        "Hello <https://example.com/Hello> and https://example.com/World. $E = Hello$."
    )
    translated = translate_markdown_document(source, "English", "French", _french)
    assert (
        translated
        == "Bonjour <https://example.com/Hello> and https://example.com/World. $E = Hello$."
    )


def test_front_matter_keys_stay_and_prose_values_change():
    source = "---\ntitle: Hello World\ndraft: true\ntags:\n  - Hello\n---\n\nHello\n"
    translated = translate_markdown_document(source, "English", "French", _french)
    assert translated == (
        "---\ntitle: Bonjour Monde\ndraft: true\ntags:\n  - Hello\n---\n\nBonjour\n"
    )


def test_html_comment_is_not_translated():
    source = "Hello <!-- Hello World --> World"
    translated = translate_markdown_document(source, "English", "French", _french)
    assert translated == "Bonjour <!-- Hello World --> Monde"


def test_existing_protection_token_in_prose_is_preserved():
    source = "Hello <!--MR:0--> World"
    translated = translate_markdown_document(source, "English", "French", _french)
    assert translated == "Bonjour <!--MR:0--> Monde"


def test_dropped_token_fails_instead_of_writing_a_broken_file(tmp_path: Path):
    source = tmp_path / "note.md"
    source.write_text("Hello `code`\n", encoding="utf-8")

    def drop_tokens(content: str, source_language: str, target_language: str) -> str:
        del source_language, target_language
        return "Bonjour only"

    with pytest.raises(ProjectTranslationError):
        translate_markdown_document(
            source.read_text(encoding="utf-8"), "en", "fr", drop_tokens
        )

    result = run_project_translation(
        root=tmp_path,
        source_language="English",
        target_language="French",
        translator=drop_tokens,
        output_dir=tmp_path / "out",
    )
    assert result["failed"] == 1
    assert result["files"][0]["status"] == "failed"
    assert source.read_text(encoding="utf-8") == "Hello `code`\n"
    assert not (tmp_path / "out" / "note.md").exists()


def test_discover_skips_vendor_hidden_and_non_markdown(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "docs" / "b.markdown").write_text("b", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("no", encoding="utf-8")
    (tmp_path / ".secret.md").write_text("no", encoding="utf-8")
    vendor = tmp_path / "node_modules"
    vendor.mkdir()
    (vendor / "dep.md").write_text("no", encoding="utf-8")
    link = tmp_path / "linked.md"
    link.symlink_to(tmp_path / "docs" / "a.md")

    assert [
        path.relative_to(tmp_path).as_posix()
        for path in discover_markdown_files(tmp_path)
    ] == [
        "docs/a.md",
        "docs/b.markdown",
    ]


def test_project_run_mirrors_structure_and_keeps_going_after_a_failure(tmp_path: Path):
    (tmp_path / "chapters").mkdir()
    (tmp_path / "README.md").write_text("Hello\n", encoding="utf-8")
    (tmp_path / "chapters" / "one.md").write_text("```\nHello\n```\n", encoding="utf-8")
    (tmp_path / "chapters" / "two.md").write_text("World\n", encoding="utf-8")

    def flaky(content: str, source_language: str, target_language: str) -> str:
        if "World" in content:
            raise RuntimeError("provider down")
        return _french(content, source_language, target_language)

    output = tmp_path / "translations"
    result = run_project_translation(
        root=tmp_path,
        source_language="English",
        target_language="French",
        translator=flaky,
        output_dir=output,
    )
    assert result["translated"] == 1
    assert result["unchanged"] == 1
    assert result["failed"] == 1
    assert result["status"] == "completed"
    assert (output / "README.md").read_text(encoding="utf-8") == "Bonjour\n"
    assert (output / "chapters" / "one.md").read_text(
        encoding="utf-8"
    ) == "```\nHello\n```\n"
    assert not (output / "chapters" / "two.md").exists()
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "Hello\n"


def test_cancel_stops_before_later_files(tmp_path: Path):
    for name in ("a.md", "b.md"):
        (tmp_path / name).write_text("Hello\n", encoding="utf-8")
    started = threading.Event()
    cancel = threading.Event()

    def slow(content: str, source_language: str, target_language: str) -> str:
        started.set()
        time.sleep(0.2)
        return _french(content, source_language, target_language)

    def cancel_once(record: dict) -> None:
        if record["status"] == "running":
            cancel.set()

    result = run_project_translation(
        root=tmp_path,
        source_language="English",
        target_language="French",
        translator=slow,
        output_dir=tmp_path / "out",
        cancel_event=cancel,
        on_file=cancel_once,
    )
    assert started.is_set()
    assert result["status"] == "cancelled"
    assert result["translated"] == 1
    assert result["cancelled"] == 1
    assert (tmp_path / "out" / "b.md").exists() is False


def test_output_directory_cannot_contain_the_project(tmp_path: Path):
    (tmp_path / "a.md").write_text("Hello\n", encoding="utf-8")
    with pytest.raises(ProjectTranslationError):
        run_project_translation(
            root=tmp_path,
            source_language="English",
            target_language="French",
            translator=_french,
            output_dir=tmp_path,
        )


def test_api_translates_project_and_reports_missing_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    reset_project_translations()
    monkeypatch.setattr("backend.project_translation.default_translator", _french)
    (tmp_path / "a.md").write_text("Hello World\n", encoding="utf-8")
    client = TestClient(app)
    missing = client.get("/api/ai/translate/project/missing")
    assert missing.status_code == 404

    created = client.post(
        "/api/ai/translate/project",
        json={
            "root": str(tmp_path),
            "source_language": "English",
            "target_language": "French",
            "output_dir": str(tmp_path / "out"),
        },
    )
    assert created.status_code == 200
    task_id = created.json()["id"]
    finished = wait_for_project_translation(task_id, timeout=5)
    assert finished["status"] == "completed"
    assert finished["translated"] == 1
    assert (tmp_path / "out" / "a.md").read_text(encoding="utf-8") == "Bonjour Monde\n"
    assert (tmp_path / "a.md").read_text(encoding="utf-8") == "Hello World\n"


def test_api_rejects_a_missing_folder(tmp_path: Path):
    client = TestClient(app)
    response = client.post(
        "/api/ai/translate/project",
        json={"root": str(tmp_path / "nope"), "target_language": "French"},
    )
    assert response.status_code == 400


def test_api_cancel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    reset_project_translations()
    (tmp_path / "a.md").write_text("Hello\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("Hello\n", encoding="utf-8")
    started = threading.Event()

    def slow(content: str, source_language: str, target_language: str) -> str:
        started.set()
        time.sleep(0.4)
        return _french(content, source_language, target_language)

    monkeypatch.setattr("backend.project_translation.default_translator", slow)
    snapshot = start_project_translation(
        root=str(tmp_path),
        source_language="English",
        target_language="French",
        output_dir=str(tmp_path / "out"),
    )
    assert started.wait(1)
    cancelled = cancel_project_translation(snapshot["id"])
    assert cancelled is not None
    finished = wait_for_project_translation(snapshot["id"], timeout=2)
    assert finished["status"] == "cancelled"
    assert finished["cancelled"] >= 1


def test_restore_rejects_an_invented_token():
    masked, slots = protect_markdown("Hello `code`")
    with pytest.raises(ProjectTranslationError):
        restore_markdown(masked + "<!--MR:9-->", slots)
