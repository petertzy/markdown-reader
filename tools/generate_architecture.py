#!/usr/bin/env python3
"""Generate a self-contained architecture explorer from repository source files."""

import argparse
import ast
import json
import os
import re
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path

EXCLUDED = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    ".venv",
    "__pycache__",
    "coverage",
}
HIDDEN_FUNCTION_VIEWS = {"backend/ai_logic.py", "backend/citation_logic.py"}
CALL_RE = re.compile(r"\b([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)\s*\(")
TS_DEF = re.compile(
    r"\b(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(|\b(?:export\s+)?(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>",
    re.M,
)
TS_IMPORT = re.compile(
    r"\b(?:import|export)\s+(?:[^;]*?\s+from\s+)?[\'\"]([^\'\"]+)[\'\"]", re.S
)


def files(root):
    extensions = {".py", ".ts", ".tsx", ".js", ".mjs"}
    for directory, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED)
        for name in sorted(names):
            path = Path(directory) / name
            if path.suffix in extensions and path.is_file():
                yield path


def analyze(root):
    entries = []
    for path in files(root):
        rel = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8", errors="replace")
        defs = []
        edges = []
        if path.suffix == ".py":
            try:
                tree = ast.parse(source, filename=rel)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defs.append(
                        (node.name, node.lineno, node.end_lineno or node.lineno)
                    )
                    for call in ast.walk(node):
                        if isinstance(call, ast.Call):
                            if isinstance(call.func, ast.Name):
                                edges.append((node.name, call.func.id, call.lineno))
                            elif isinstance(call.func, ast.Attribute):
                                edges.append((node.name, call.func.attr, call.lineno))
        else:
            newline_positions = [i for i, char in enumerate(source) if char == "\n"]

            def line_number(offset):
                return bisect_left(newline_positions, offset) + 1

            matches = list(TS_DEF.finditer(source))
            for i, match in enumerate(matches):
                name = match.group(1) or match.group(2)
                start = line_number(match.start())
                end_pos = (
                    matches[i + 1].start() if i + 1 < len(matches) else len(source)
                )
                end = line_number(end_pos)
                defs.append((name, start, end))
                body = source[match.end() : end_pos]
                for call in CALL_RE.finditer(body):
                    callee = call.group(1).split(".")[-1]
                    edges.append(
                        (name, callee, line_number(match.end() + call.start()))
                    )
        entries.append({"file": rel, "defs": defs, "edges": edges})
    return entries


def make_views(entries, root):
    grouped = defaultdict(list)
    for entry in entries:
        path = entry["file"]
        if path.startswith("frontend/src/"):
            group = "Frontend functions"
        elif path.startswith("backend/"):
            group = "Backend functions"
        elif path.startswith("frontend/src-tauri/"):
            group = "Desktop functions"
        else:
            continue
        grouped[group].append(entry)
    views = []
    for index, (group, subset) in enumerate(grouped.items()):
        by_name = defaultdict(list)
        for entry in subset:
            for name, start, end in entry["defs"]:
                by_name[name].append((entry["file"], start, end))
        nodes = []
        edges = set()
        ids = {}
        for entry in subset:
            for name, start, end in entry["defs"]:
                identifier = f"{entry['file']}:{name}:{start}"
                ids[(entry["file"], name)] = identifier
                nodes.append(
                    {
                        "id": identifier,
                        "title": name[:29],
                        "subtitle": entry["file"].split("/")[-1][:35],
                        "files": [entry["file"]],
                        "line": start,
                        "description": f"Defined at {entry['file']}:{start}-{end}.",
                        "kind": "module",
                        "x": 0,
                        "y": 0,
                    }
                )
        for entry in subset:
            for caller, callee, line in entry["edges"]:
                src = ids.get((entry["file"], caller))
                if not src:
                    continue
                candidates = by_name.get(callee, [])
                same_file = [x for x in candidates if x[0] == entry["file"]]
                if same_file:
                    target = ids.get((same_file[0][0], callee))
                    if target and target != src:
                        edges.add((src, target))
        # Split large graphs into per-file views to retain legibility.
        for entry in subset:
            if entry["file"] in HIDDEN_FUNCTION_VIEWS:
                continue
            local = [n.copy() for n in nodes if n["files"][0] == entry["file"]]
            if len(local) < 2:
                continue
            local_ids = {n["id"] for n in local}
            local_edges = [
                list(e)
                for e in sorted(edges)
                if e[0] in local_ids and e[1] in local_ids
            ]
            if len(local) > 120:
                local = local[:120]
                local_ids = {n["id"] for n in local}
                local_edges = [
                    e for e in local_edges if e[0] in local_ids and e[1] in local_ids
                ]
            views.append(
                {
                    "id": f"functions-{len(views)}",
                    "title": entry["file"].split("/")[-1] + " calls",
                    "subtitle": entry["file"] + " | local static calls",
                    "nodes": local,
                    "edges": local_edges,
                }
            )
    return views


def inject(template, views, sha):
    # Existing explorer uses a constant view array and a DOM-based SVG renderer.
    script = (
        '<script id="generated-architecture-data">window.ARCHITECTURE_GENERATED='
        + json.dumps({"views": views, "sha": sha}, ensure_ascii=True).replace(
            "<", "\\u003c"
        )
        + ";</script>"
    )
    template = template.replace(
        "<script>\nconst ROOT=", script + "\n<script>\nconst ROOT=", 1
    )
    template = template.replace("const views=[", "const views=[", 1)
    marker = "const nav=document.getElementById('nav')"
    template = template.replace(
        marker,
        """const generated=window.ARCHITECTURE_GENERATED;
if(generated?.views?.length) views.push(...generated.views);
function autoLayout(view){
  const indegree=new Map(view.nodes.map(n=>[n.id,0]));
  const children=new Map(view.nodes.map(n=>[n.id,[]]));
  for(const [a,b] of view.edges){if(indegree.has(a)&&indegree.has(b)){indegree.set(b,indegree.get(b)+1);children.get(a).push(b)}}
  const queue=[...indegree].filter(([,d])=>d===0).map(([id])=>id);
  const levels=new Map(queue.map(id=>[id,0]));
  while(queue.length){const id=queue.shift();for(const to of children.get(id)){indegree.set(to,indegree.get(to)-1);levels.set(to,Math.max(levels.get(to)||0,(levels.get(id)||0)+1));if(indegree.get(to)===0)queue.push(to)}}
  for(const node of view.nodes) if(!levels.has(node.id))levels.set(node.id,0);
  const buckets=new Map();for(const node of view.nodes){const level=Math.min(levels.get(node.id),12);if(!buckets.has(level))buckets.set(level,[]);buckets.get(level).push(node)}
  for(const [level,items] of buckets) items.forEach((node,i)=>{node.x=40+level*260;node.y=40+i*105});
}
for(const view of views) if(view.id.startsWith('functions-')) autoLayout(view);
"""
        + marker,
        1,
    )
    template = template.replace(
        "['01','02','03','04','05'][i]", "String(i+1).padStart(2,'0')"
    )
    template = template.replace(
        "a.href=ROOT+path", "a.href=ROOT+path+(node.line?'#L'+node.line:'')"
    )
    template = template.replace(
        "Math.min((rect.width-36)/maxX,(rect.height-36)/maxY,1.35)",
        "Math.min((rect.width-36)/maxX,(rect.height-36)/maxY,1.35)",
    )
    return template


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--template", default="docs/architecture/template.html")
    parser.add_argument("--output", default="docs/architecture/index.html")
    parser.add_argument("--sha", default="local")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    template = (root / args.template).read_text(encoding="utf-8")
    result = inject(template, make_views(analyze(root), root), args.sha)
    dest = root / args.output
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(result, encoding="utf-8")
    print(f"Generated {dest.relative_to(root)}")


if __name__ == "__main__":
    main()
