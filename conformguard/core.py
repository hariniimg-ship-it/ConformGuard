from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


@dataclass
class RunSummary:
    component: str
    total: int
    passed: int
    failed: int
    skipped: int
    score: float
    cases: list[dict[str, Any]]
    source: str

    @property
    def status(self) -> str:
        return "PASS" if self.failed == 0 else "FAIL"

    def to_dict(self) -> dict[str, Any]:
        return {"component": self.component, "total": self.total, "passed": self.passed,
                "failed": self.failed, "skipped": self.skipped, "score": self.score,
                "status": self.status, "source": self.source, "cases": self.cases}


def load_json(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def request_json(url: str, token: str | None = None, timeout: int = 30) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, headers=headers), timeout=timeout) as response:  # nosec B310: user-configured endpoint
        return json.loads(response.read().decode("utf-8"))


def normalize(component: str, payload: dict[str, Any], source: str) -> RunSummary:
    """Normalize several common conformance result shapes into one stable schema."""
    raw_cases = payload.get("cases") or payload.get("tests") or payload.get("results") or []
    cases: list[dict[str, Any]] = []
    for item in raw_cases:
        name = item.get("name") or item.get("test") or item.get("id") or "unnamed-test"
        raw_status = str(item.get("status") or item.get("result") or "unknown").lower()
        status = "passed" if raw_status in {"pass", "passed", "success", "ok"} else ("skipped" if raw_status in {"skip", "skipped"} else "failed")
        cases.append({"id": str(item.get("id") or name), "name": name, "status": status,
                      "detail": item.get("detail") or item.get("message") or ""})
    total = len(cases)
    passed = sum(c["status"] == "passed" for c in cases)
    failed = sum(c["status"] == "failed" for c in cases)
    skipped = sum(c["status"] == "skipped" for c in cases)
    score = round((passed / total * 100) if total else 0.0, 2)
    return RunSummary(component, total, passed, failed, skipped, score, cases, source)


def compare(current: RunSummary, previous: dict[str, Any] | None) -> dict[str, Any]:
    if not previous:
        return {"baseline_found": False, "new_failures": [], "score_delta": None, "regression": False}
    prior_component = (previous.get("components") or {}).get(current.component, previous)
    prior_cases = {str(c.get("id") or c.get("name")): c.get("status") for c in prior_component.get("cases", [])}
    new_failures = [c["id"] for c in current.cases if c["status"] == "failed" and prior_cases.get(c["id"]) == "passed"]
    prior_score = float(prior_component.get("score", 0))
    return {"baseline_found": True, "new_failures": new_failures,
            "score_delta": round(current.score - prior_score, 2), "regression": bool(new_failures)}


def evaluate(run: RunSummary, regression: dict[str, Any], min_score: float, block_regression: bool) -> list[dict[str, str]]:
    gates = [{"gate": "all tests pass", "status": "PASS" if run.failed == 0 else "FAIL",
              "detail": f"{run.failed} failed of {run.total}"},
             {"gate": f"minimum score ({min_score:.1f})", "status": "PASS" if run.score >= min_score else "FAIL",
              "detail": f"score is {run.score:.1f}"}]
    if block_regression:
        gates.append({"gate": "no newly failing tests", "status": "FAIL" if regression["regression"] else "PASS",
                      "detail": ", ".join(regression["new_failures"]) or "none"})
    return gates


def report(components: dict[str, RunSummary], regressions: dict[str, dict[str, Any]], gates: dict[str, list[dict[str, str]]], config: dict[str, Any]) -> dict[str, Any]:
    all_gates = [gate for values in gates.values() for gate in values]
    return {"schema_version": "1.0", "generated_at": datetime.now(timezone.utc).isoformat(),
            "project": config.get("project", "ConformGuard"), "components": {k: v.to_dict() for k, v in components.items()},
            "regressions": regressions, "quality_gates": gates,
            "status": "PASS" if all(g["status"] == "PASS" for g in all_gates) else "BLOCKED"}


def markdown_report(result: dict[str, Any]) -> str:
    lines = [f"# ConformGuard report: {result['status']}", "", f"Generated: {result['generated_at']}", "",
             "| Component | Tests | Passed | Failed | Score |", "|---|---:|---:|---:|---:|"]
    for name, item in result["components"].items():
        lines.append(f"| {name} | {item['total']} | {item['passed']} | {item['failed']} | {item['score']:.1f}% |")
    lines += ["", "## Quality gates", "", "| Component | Gate | Status | Detail |", "|---|---|---|---|"]
    for component, entries in result["quality_gates"].items():
        for gate in entries:
            lines.append(f"| {component} | {gate['gate']} | {gate['status']} | {gate['detail']} |")
    return "\n".join(lines) + "\n"
