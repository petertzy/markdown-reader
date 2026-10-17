"""Tests for bounded, reviewable project Work tasks."""

import json

import pytest
from fastapi import HTTPException

from backend import project_work as work


@pytest.fixture(autouse=True)
def clear_tasks():
    work.TASKS.clear()
    yield
    work.TASKS.clear()


@pytest.fixture
def project(tmp_path):
    (tmp_path / "guide.md").write_text("# Guide\n")
    (tmp_path / "notes.txt").write_text("Notes\n")
    (tmp_path / ".private.md").write_text("Hidden\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "skip.md").write_text("Skip\n")
    return tmp_path


def answer(**payload):
    return lambda *_: json.dumps({"summary": "Test response", **payload})


def test_discovers_names_then_reads_requested_files_and_proposes_batch(project):
    task = work.start(str(project), "Update documentation", {})
    assert task["file_count"] == 2
    seen = []

    def request(_, context):
        seen.append(json.loads(context))
        return json.dumps({"read": ["guide.md"], "summary": "Read guide"})

    task = work.step(task["id"], request)
    assert seen[0]["read_files"] == {}
    assert task["inspected"] == ["guide.md"]
    task = work.step(
        task["id"], answer(changes=[{"path": "guide.md", "content": "# Updated\n"}])
    )
    assert task["status"] == "review"
    assert task["changes"][0]["path"] == "guide.md"
    assert "-# Guide" in task["changes"][0]["diff"]
    assert (project / "guide.md").read_text() == "# Guide\n"


def test_open_buffer_is_context_but_disk_is_revalidated(project):
    task = work.start(str(project), "Edit", {str(project / "guide.md"): "Unsaved\n"})
    work.step(task["id"], answer(read=["guide.md", "notes.txt"]))
    task = work.step(
        task["id"], answer(changes=[{"path": "guide.md", "content": "Proposed\n"}])
    )
    assert task["changes"][0]["diff"].startswith("--- guide.md")
    work.validate(task["id"])
    (project / "notes.txt").write_text("External change\n")
    with pytest.raises(HTTPException) as error:
        work.validate(task["id"])
    assert error.value.status_code == 409


@pytest.mark.parametrize(
    "path", ["../outside.md", "/tmp/outside.md", ".private.md", "missing.md"]
)
def test_rejects_unsafe_or_unknown_reads(project, path):
    task = work.start(str(project), "Edit", {})
    with pytest.raises(ValueError):
        work.step(task["id"], answer(read=[path]))


def test_rejects_changes_to_unread_or_duplicate_files(project):
    task = work.start(str(project), "Edit", {})
    with pytest.raises(ValueError):
        work.step(task["id"], answer(changes=[{"path": "guide.md", "content": "No"}]))
    task = work.start(str(project), "Edit", {})
    work.step(task["id"], answer(read=["guide.md"]))
    with pytest.raises(ValueError):
        work.step(
            task["id"],
            answer(
                changes=[
                    {"path": "guide.md", "content": "One"},
                    {"path": "guide.md", "content": "Two"},
                ]
            ),
        )


def test_discards_and_expires_tasks(project, monkeypatch):
    task = work.start(str(project), "Edit", {})
    work.discard(task["id"])
    with pytest.raises(HTTPException):
        work.validate(task["id"])
    task = work.start(str(project), "Edit", {})
    monkeypatch.setattr(work, "TASK_TTL_SECONDS", 0)
    with pytest.raises(HTTPException):
        work.validate(task["id"])


def test_rejects_overlapping_steps_and_blank_instructions(project):
    with pytest.raises(ValueError, match="instruction"):
        work.start(str(project), "   ", {})
    task = work.start(str(project), "Edit", {})
    work.TASKS[task["id"]]["busy"] = True
    with pytest.raises(HTTPException) as error:
        work.step(task["id"], answer(read=["guide.md"]))
    assert error.value.status_code == 409
