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
    retry_failed_project_translation,
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




def test_indented_code_and_implicit_references_are_not_translated():
    source = (
        "Hello\n\n"
        "    print('Hello')\n\n"
        "[Hello][] and [World].\n\n"
        "[Hello]: ./guide.md\n"
        "[World]: ./world.md\n"
    )
    translated = translate_markdown_document(source, "English", "French", _french)
    assert "print('Hello')" in translated
    assert "[Hello][]" in translated
    assert "[World]." in translated
    assert "[Hello]: ./guide.md" in translated
    assert "[World]: ./world.md" in translated


def test_relative_image_assets_are_copied_with_translated_markdown(tmp_path: Path):
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "diagram.png").write_bytes(b"image-bytes")
    (tmp_path / "guide.md").write_text(
        "Hello ![Diagram](images/diagram.png)\n", encoding="utf-8"
    )

    output = tmp_path / "translated"
    result = run_project_translation(
        root=tmp_path,
        source_language="English",
        target_language="French",
        translator=_french,
        output_dir=output,
    )

    assert result["translated"] == 1
    assert (output / "guide.md").read_text(encoding="utf-8") == (
        "Bonjour ![Diagram](images/diagram.png)\n"
    )
    assert (output / "images" / "diagram.png").read_bytes() == b"image-bytes"


def test_retry_only_reprocesses_files_that_failed(tmp_path: Path):
    reset_project_translations()
    (tmp_path / "good.md").write_text("Hello\n", encoding="utf-8")
    (tmp_path / "retry.md").write_text("World\n", encoding="utf-8")

    def fail_world(content: str, source: str, target: str) -> str:
        if "World" in content:
            raise RuntimeError("temporary provider error")
        return _french(content, source, target)

    started = start_project_translation(
        root=str(tmp_path),
        source_language="English",
        target_language="French",
        output_dir=str(tmp_path / "out"),
        translator=fail_world,
    )
    completed = wait_for_project_translation(started["id"])
    assert completed["failed"] == 1

    retried = retry_failed_project_translation(completed["id"], translator=_french)
    assert retried is not None
    retried_completed = wait_for_project_translation(retried["id"])
    assert retried_completed["total"] == 1
    assert retried_completed["translated"] == 1
    assert retried_completed["failed"] == 0
    assert retried_completed["files"][0]["rel_path"] == "retry.md"
    assert (tmp_path / "out" / "retry.md").read_text(encoding="utf-8") == "Monde\n"


def test_default_output_is_visible_and_not_discovered_as_source(tmp_path: Path):
    (tmp_path / "guide.md").write_text("Hello\n", encoding="utf-8")

    first = run_project_translation(
        root=tmp_path,
        source_language="English",
        target_language="French",
        translator=_french,
    )
    output = tmp_path / "translations" / "french"
    assert first["total"] == 1
    assert first["output_dir"] == str(output)
    assert (output / "guide.md").read_text(encoding="utf-8") == "Bonjour\n"

    second = run_project_translation(
        root=tmp_path,
        source_language="English",
        target_language="French",
        translator=_french,
    )
    assert second["total"] == 1
    assert second["files"][0]["rel_path"] == "guide.md"
