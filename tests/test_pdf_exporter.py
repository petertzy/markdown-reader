from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_pdf_exporter(monkeypatch):
    captured: dict[str, str] = {}

    class FakeHTML:
        def __init__(self, *, string: str):
            captured["html"] = string

        def write_pdf(self, output_path: str) -> None:
            captured["output_path"] = output_path

    fake_weasyprint = types.ModuleType("weasyprint")
    fake_weasyprint.HTML = FakeHTML
    monkeypatch.setitem(sys.modules, "weasyprint", fake_weasyprint)

    module_path = Path(__file__).parents[1] / "backend" / "pdf_exporter.py"
    spec = importlib.util.spec_from_file_location("pdf_exporter_under_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, captured


def test_pdf_export_overrides_renderer_code_whitespace(monkeypatch, tmp_path: Path):
    exporter, captured = _load_pdf_exporter(monkeypatch)

    output_path = tmp_path / "document.pdf"
    exporter.export_markdown_to_pdf("<pre><code>long line</code></pre>", str(output_path))

    css = captured["html"]
    assert "pre code { white-space: pre-wrap; overflow-wrap: anywhere; word-break: break-word; }" in css
    assert captured["output_path"] == str(output_path)
