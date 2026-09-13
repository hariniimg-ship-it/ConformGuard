# ConformGuard

ConformGuard is a lightweight, runnable MVP that turns conformance-suite output into a single CI quality gate. It supports separate **certify** and **verify** runs, a combined run, deterministic mock results, normalization, regression detection, JSON/Markdown reports, Docker, and GitHub Actions.

## Fast demo

Requirements: Python 3.10+ (no packages need to be installed).

```powershell
python -m conformguard.cli --combined --mock --output-dir artifacts
```

Expected console output:

```text
ConformGuard PASS: JSON=artifacts/report.json Markdown=artifacts/report.md
  certify: 3/3 passed; score 100.0%
  verify: 3/3 passed; score 100.0%
```

Run one component:

```powershell
python -m conformguard.cli --component certify --mock
python -m conformguard.cli --component verify --mock
```

Run in Docker:

```powershell
docker compose up --build
```

## What it does

1. Fetches an external JSON result (or reads bundled mock JSON).
2. Normalizes common `tests`, `cases`, and `results` payload shapes to a stable schema.
3. Compares every current failure against a previous report's passing test IDs.
4. Blocks when a test fails, the score is lower than `quality_gate.minimum_score`, or a newly failing test is found.
5. Writes `report.json` (automation-friendly) and `report.md` (human-friendly).

Use a previous report as the baseline:

```powershell
python -m conformguard.cli --combined --mock --baseline examples/baseline-pass.json
```

## Live integrations: configure deliberately

`config/conformguard.json` contains **placeholders**, not working production URLs. Replace the component `endpoint` values with the endpoint that returns your OpenID Conformance Suite job results and your Inji verification results. Set the associated bearer token variables before a live run:

```powershell
$env:CONFORMGUARD_OPENID_TOKEN = 'your-openid-token'
$env:CONFORMGUARD_INJI_TOKEN = 'your-inji-token'
python -m conformguard.cli --combined
```

The runner expects a JSON collection under `tests`, `cases`, or `results`; every element needs a name/id and a status/result. Map or proxy proprietary suite payloads into that shape if needed. Authentication, job triggering, polling, and exact endpoint paths vary by your OpenID Suite/Inji deployment, so they are intentionally configuration/integration work rather than hard-coded claims.

## Regression demo

To see a block, temporarily replace `data/certify-mock.json` with `examples/regression-result.json`, then run with `--baseline examples/baseline-pass.json`. The exit code is `1`, and `report.json` records `oidc-auth-code-pkce` as a newly failing test. Restore the original mock file afterward.

## Repository layout

```text
conformguard/          Python package and CLI
config/                quality gate and endpoint placeholders
data/                  immediate runnable mock suite results
examples/              baseline and intentional regression response
scripts/               quick PowerShell demo
.github/workflows/     CI report artifact workflow
Dockerfile, docker-compose.yml
