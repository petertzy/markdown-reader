"""Regression checks for the desktop WebView security policy."""

from __future__ import annotations

import json
from pathlib import Path

TAURI_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "frontend" / "src-tauri" / "tauri.conf.json"
)
TAURI_HOST_PATH = (
    Path(__file__).resolve().parents[1] / "frontend" / "src-tauri" / "src" / "lib.rs"
)


def test_csp_limits_connect_requests_to_the_local_backend():
    config = json.loads(TAURI_CONFIG_PATH.read_text(encoding="utf-8"))
    csp = config["app"]["security"]["csp"]

    assert "connect-src 'self' http://127.0.0.1:*" in csp
    assert "connect-src 'self' http://127.0.0.1:* https:" not in csp


def test_webview_cannot_invoke_a_command_that_returns_the_backend_token():
    host_source = TAURI_HOST_PATH.read_text(encoding="utf-8")

    assert "fn get_backend_token" not in host_source
    assert "async fn proxy_backend_request" in host_source
