"""Regression checks for the desktop WebView security policy."""

from __future__ import annotations

import json
from pathlib import Path

TAURI_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "frontend" / "src-tauri" / "tauri.conf.json"
)


def test_csp_limits_connect_requests_to_the_local_backend():
    config = json.loads(TAURI_CONFIG_PATH.read_text(encoding="utf-8"))
    csp = config["app"]["security"]["csp"]

    assert "connect-src 'self' http://127.0.0.1:*" in csp
    assert "connect-src 'self' http://127.0.0.1:* https:" not in csp
