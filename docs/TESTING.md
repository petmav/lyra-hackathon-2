# Testing

Praetor has three test layers:

1. Unit and service tests through `npm test`.
2. Web type/build checks from `apps/web`.
3. Live platform E2E checks through `npm run test:e2e`.

## Comprehensive E2E

`npm run test:e2e` runs `scripts/e2e_platform.py` against a live stack. It is intentionally a single run file so CI, demos, and handoff testing all exercise the same critical path.

Default targets:

```bash
npm run test:e2e
```

Equivalent explicit command:

```bash
python scripts/e2e_platform.py --api-base http://localhost:8000 --web-base http://localhost:3000
```

The E2E suite checks:

- API health and production runtime mode.
- Runtime readiness for model providers and JSON Stack secrets.
- Model provider registry and offline provider checks.
- Assets, obligations, and controls endpoints.
- Workflow catalog and `code_compliance_scan_full` execution.
- Workflow event hash-chain continuity.
- Proposed-change read, sandbox run, approve, and apply lifecycle.
- Hook catalog, JSON Stack catalog, JSON Stack preview, and missing-secret failure behavior.
- MCP JSON-RPC health negotiation against the GitHub stub.
- Corpus ingest and search.
- Findings, evidence sweep, evidence records, and audit-packet generation.
- Sandbox lifecycle plus newline-delimited sandbox log streaming.
- Main web routes against the live API-backed frontend.

Use `--skip-web` when testing only the API stack:

```bash
python scripts/e2e_platform.py --skip-web
```

The script exits non-zero on any failed check and prints a pass/fail summary.
