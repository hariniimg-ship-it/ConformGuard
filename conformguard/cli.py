from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import compare, evaluate, load_json, markdown_report, normalize, report, request_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and guard identity conformance checks.")
    parser.add_argument("--component", choices=["certify", "verify"])
    parser.add_argument("--combined", action="store_true", help="Run certify and verify.")
    parser.add_argument("--config", default="config/conformguard.json")
    parser.add_argument("--mock", action="store_true", help="Use bundled sample responses.")
    parser.add_argument("--baseline", help="Previous ConformGuard JSON report.")
    parser.add_argument("--output-dir", default="artifacts")
    args = parser.parse_args()
    if not args.component and not args.combined:
        parser.error("choose --component certify|verify or --combined")
    config = load_json(args.config)
    components = [args.component] if args.component else ["certify", "verify"]
    baseline = load_json(args.baseline) if args.baseline else None
    runs, regressions, gates = {}, {}, {}
    for component in components:
        component_config = config["components"][component]
        if args.mock:
            payload = load_json(Path(args.config).parent.parent / component_config["mock_result"])
            source = "mock"
        else:
            endpoint = component_config.get("endpoint")
            if not endpoint or "REPLACE_" in endpoint:
                print(f"{component}: endpoint is a placeholder; use --mock or configure an endpoint", file=sys.stderr)
                return 2
            payload = request_json(endpoint, component_config.get("token_env") and __import__("os").environ.get(component_config["token_env"]))
            source = endpoint
        run = normalize(component, payload, source)
        regression = compare(run, baseline)
        runs[component] = run
        regressions[component] = regression
        gates[component] = evaluate(run, regression, float(config["quality_gate"]["minimum_score"]), bool(config["quality_gate"]["block_regressions"]))
    result = report(runs, regressions, gates, config)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (out / "report.md").write_text(markdown_report(result), encoding="utf-8")
    print(f"ConformGuard {result['status']}: JSON={out / 'report.json'} Markdown={out / 'report.md'}")
    for name, run in runs.items(): print(f"  {name}: {run.passed}/{run.total} passed; score {run.score:.1f}%")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
