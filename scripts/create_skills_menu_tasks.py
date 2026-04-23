#!/usr/bin/env python3
"""Batch-create GitHub issues for the Skills Menu feature track.

Usage examples:
  python scripts/create_skills_menu_tasks.py --dry-run
  python scripts/create_skills_menu_tasks.py
  python scripts/create_skills_menu_tasks.py --repo owner/repo
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskIssue:
    title: str
    body: str
    labels: list[str]


DEFAULT_TASKS: list[TaskIssue] = [
    TaskIssue(
        title="feat(skills): add declarative skill registry + persistence",
        labels=["feature", "ai", "enhancement"],
        body=(
            "## Goal\n"
            "Create a declarative skills registry (no executable plugin code) and persist installed/enabled state in user settings.\n\n"
            "## Scope\n"
            "- Add a skills schema: id, title, description, prompt, requires_selection, category, enabled, version\n"
            "- Add load/save helpers in logic layer\n"
            "- Keep backward compatibility with current automation templates\n"
            "- Ensure invalid entries are sanitized\n\n"
            "## Acceptance Criteria\n"
            "- [ ] Skills can be loaded from built-in defaults\n"
            "- [ ] Installed/enabled state persists across restarts\n"
            "- [ ] Unknown/invalid fields are handled safely\n"
            "- [ ] Existing AI template behavior does not regress\n"
        ),
    ),
    TaskIssue(
        title="feat(ui): add top-level Skills menu",
        labels=["feature", "ui", "enhancement"],
        body=(
            "## Goal\n"
            "Add a new top-level menu named Skills for discoverability and management.\n\n"
            "## Scope\n"
            "- Add Skills menu in menubar\n"
            "- Include entries: Browse Skills, Installed Skills, Manage Skills\n"
            "- Keep layout and behavior consistent on macOS and Windows\n\n"
            "## Acceptance Criteria\n"
            "- [ ] Skills menu appears in the menubar\n"
            "- [ ] Menu actions open the correct dialogs/views\n"
            "- [ ] Keyboard/mouse interaction behaves consistently with other menus\n"
        ),
    ),
    TaskIssue(
        title="feat(ui): build Skills Manager dialog (install/uninstall/toggle)",
        labels=["feature", "ui", "ai"],
        body=(
            "## Goal\n"
            "Provide a dialog to install, uninstall, and enable/disable skills.\n\n"
            "## Scope\n"
            "- List built-in skill catalog and installed state\n"
            "- One-click install/uninstall\n"
            "- Toggle enabled state for installed skills\n"
            "- Show skill details and selection requirements\n\n"
            "## Acceptance Criteria\n"
            "- [ ] User can install a skill\n"
            "- [ ] User can uninstall a skill\n"
            "- [ ] User can enable/disable installed skills\n"
            "- [ ] Changes persist after app restart\n"
        ),
    ),
    TaskIssue(
        title="feat(ai): drive Automation Template picker from enabled skills",
        labels=["feature", "ai", "ui"],
        body=(
            "## Goal\n"
            "Use enabled skills as the source of truth for AI automation templates shown in the panel.\n\n"
            "## Scope\n"
            "- Replace static template list wiring with skills-backed list\n"
            "- Keep current Run Template flow\n"
            "- Preserve selection-required validation\n"
            "- Handle empty enabled-skills state gracefully\n\n"
            "## Acceptance Criteria\n"
            "- [ ] Only enabled skills appear in template selector\n"
            "- [ ] Disabled/uninstalled skills do not appear\n"
            "- [ ] Run Template still sends prompt correctly\n"
            "- [ ] No crash when zero skills are enabled\n"
        ),
    ),
    TaskIssue(
        title="feat(safety): enforce declarative-only skills and action guardrails",
        labels=["security", "ai", "enhancement"],
        body=(
            "## Goal\n"
            "Ensure the skills system remains declarative-only and does not execute arbitrary code.\n\n"
            "## Scope\n"
            "- Restrict skills to prompt + metadata only\n"
            "- Reject executable/script fields in registry\n"
            "- Keep AI action types within existing editor-safe boundaries\n"
            "- Add explicit validation error messages\n\n"
            "## Acceptance Criteria\n"
            "- [ ] No dynamic code loading from skill definitions\n"
            "- [ ] Unsafe fields are ignored or rejected\n"
            "- [ ] Validation behavior is covered by tests\n"
        ),
    ),
    TaskIssue(
        title="test: add unit tests for skills persistence and sanitization",
        labels=["tests", "ai", "enhancement"],
        body=(
            "## Goal\n"
            "Add logic-level tests for skill loading/saving and schema validation.\n\n"
            "## Scope\n"
            "- Tests for built-in defaults\n"
            "- Tests for persisted installed/enabled state\n"
            "- Tests for invalid/malformed entries\n"
            "- Tests for backward compatibility with current templates\n\n"
            "## Acceptance Criteria\n"
            "- [ ] New tests fail before implementation and pass after\n"
            "- [ ] Edge cases are covered (empty ids, wrong types, duplicates)\n"
            "- [ ] CI test suite remains green\n"
        ),
    ),
    TaskIssue(
        title="test: add UI helper tests for Skills menu and manager workflows",
        labels=["tests", "ui", "enhancement"],
        body=(
            "## Goal\n"
            "Expand UI helper tests for skill installation and toggling workflows.\n\n"
            "## Scope\n"
            "- Test menu creation wiring\n"
            "- Test install/uninstall actions\n"
            "- Test enabled filter reflected in template choices\n"
            "- Test empty-state and error-state behavior\n\n"
            "## Acceptance Criteria\n"
            "- [ ] Menu action callbacks are covered\n"
            "- [ ] Skills state transitions are covered\n"
            "- [ ] No regressions in existing AI UI helper tests\n"
        ),
    ),
    TaskIssue(
        title="docs: update README with Skills concept and usage",
        labels=["documentation", "enhancement"],
        body=(
            "## Goal\n"
            "Document the new Skills menu, installation model, and safety boundaries.\n\n"
            "## Scope\n"
            "- Add Skills section to README\n"
            "- Explain install/uninstall/enable flow\n"
            "- Clarify declarative-only model and no arbitrary plugin code\n"
            "- Add at least one end-to-end usage example\n\n"
            "## Acceptance Criteria\n"
            "- [ ] README includes Skills menu instructions\n"
            "- [ ] Safety model is explicitly described\n"
            "- [ ] Example is accurate and reproducible\n"
        ),
    ),
]


def _check_gh_cli_available() -> None:
    if shutil.which("gh") is None:
        raise RuntimeError(
            "GitHub CLI (gh) was not found. Install it first: https://cli.github.com/"
        )


def _run_gh(
    args: list[str], capture_output: bool = True
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh", *args],
        check=False,
        text=True,
        capture_output=capture_output,
    )


def _resolve_repo_name(explicit_repo: str | None) -> str:
    if explicit_repo:
        return explicit_repo.strip()

    cmd = _run_gh(["repo", "view", "--json", "nameWithOwner"])
    if cmd.returncode != 0:
        raise RuntimeError(
            "Could not resolve current repository via 'gh repo view'. "
            "Use --repo owner/name explicitly.\n"
            f"stderr: {cmd.stderr.strip()}"
        )

    try:
        payload = json.loads(cmd.stdout)
        value = str(payload.get("nameWithOwner", "")).strip()
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid JSON returned by 'gh repo view'.") from exc

    if not value:
        raise RuntimeError("Repository name is empty. Use --repo owner/name.")
    return value


def _create_issue(repo: str, task: TaskIssue, dry_run: bool) -> str:
    labels = ",".join(task.labels)
    if dry_run:
        return f"[dry-run] {task.title} | labels={labels}"

    args = [
        "issue",
        "create",
        "--repo",
        repo,
        "--title",
        task.title,
        "--body",
        task.body,
    ]
    if labels:
        args.extend(["--label", labels])

    cmd = _run_gh(args)
    if cmd.returncode != 0:
        stderr = (cmd.stderr or "").strip()
        raise RuntimeError(f"Failed to create issue '{task.title}': {stderr}")

    return (cmd.stdout or "").strip() or f"Created: {task.title}"


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a batch of Skills Menu related GitHub issues."
    )
    parser.add_argument(
        "--repo",
        default="",
        help="Target repository in owner/name format. Defaults to current gh repo.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview issues without creating them.",
    )
    parser.add_argument(
        "--from-index",
        type=int,
        default=1,
        help="1-based start index in the predefined task list.",
    )
    parser.add_argument(
        "--to-index",
        type=int,
        default=len(DEFAULT_TASKS),
        help="1-based end index in the predefined task list.",
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str]) -> int:
    args = _parse_args(argv)

    if args.from_index < 1 or args.to_index < args.from_index:
        print(
            "Invalid index range. Ensure 1 <= from-index <= to-index.", file=sys.stderr
        )
        return 2

    selected = DEFAULT_TASKS[args.from_index - 1 : args.to_index]
    if not selected:
        print("No tasks selected for the provided index range.", file=sys.stderr)
        return 2

    try:
        _check_gh_cli_available()
        repo = _resolve_repo_name(args.repo or None)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Target repo: {repo}")
    print(f"Task count: {len(selected)}")
    if args.dry_run:
        print("Mode: dry-run (no issues will be created)")

    failures = 0
    for index, task in enumerate(selected, start=args.from_index):
        print(f"\n[{index}] {task.title}")
        try:
            outcome = _create_issue(repo, task, args.dry_run)
            print(outcome)
        except RuntimeError as exc:
            failures += 1
            print(f"Error: {exc}", file=sys.stderr)

    if failures:
        print(f"\nCompleted with {failures} failure(s).", file=sys.stderr)
        return 1

    print("\nCompleted successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
