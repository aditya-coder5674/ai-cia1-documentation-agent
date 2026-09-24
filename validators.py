"""Validation and export helpers for generated documentation."""
from __future__ import annotations

import json
from pathlib import Path


def validate_document(project: dict, document: dict) -> tuple[float, list[str]]:
    issues: list[str] = []
    requirements = document.get("requirements", [])
    tests = document.get("test_cases", [])
    requirement_ids = {item.get("id") for item in requirements}
    seen_req_ids: set[str] = set()
    for feature in project["features"]:
        if not any(item.get("feature", "").casefold() == feature.casefold() for item in requirements):
            issues.append(f"Missing requirement for feature: {feature}")
    for item in requirements:
        req_id = item.get("id", "")
        if req_id in seen_req_ids:
            issues.append(f"Duplicate requirement ID: {req_id}")
        seen_req_ids.add(req_id)
        types = {test.get("type") for test in tests if test.get("requirement_id") == req_id}
        for kind in ("positive", "negative"):
            if kind not in types:
                issues.append(f"{req_id} is missing a {kind} test case")
    for test in tests:
        if test.get("requirement_id") not in requirement_ids:
            issues.append(f"{test.get('id', 'Test')} references an unknown requirement")
    complete = sum(
        {test.get("type") for test in tests if test.get("requirement_id") == req.get("id")} >= {"positive", "negative"}
        for req in requirements
    )
    return (round(100 * complete / len(requirements), 1) if requirements else 0.0), issues


def save_outputs(document: dict, project_name: str, score: float, folder: str = "output") -> tuple[Path, Path]:
    target = Path(folder)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "srs_generated.json"
    md_path = target / "srs_generated.md"
    json_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    lines = [f"# {project_name} - Software Requirements Specification", "", f"**Coverage:** {score:.1f}%", "", "## Requirements", "", "| ID | Feature | Requirement |", "|---|---|---|"]
    lines += [f"| {r.get('id','')} | {r.get('feature','')} | {r.get('text','').replace('|', '\\|')} |" for r in document.get("requirements", [])]
    lines += ["", "## Test cases", "", "| ID | Requirement | Type | Description |", "|---|---|---|---|"]
    lines += [f"| {t.get('id','')} | {t.get('requirement_id','')} | {t.get('type','')} | {t.get('description','').replace('|', '\\|')} |" for t in document.get("test_cases", [])]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path, json_path
