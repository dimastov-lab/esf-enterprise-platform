# ESF External Acceptance

## Current verdict

**READY FOR EXTERNAL ACCEPTANCE; public-deployment gate remains open.**

Evidence produced 2026-08-08:

- source suite: 267 passed;
- production compose: db/app/nginx healthy;
- migration: `e1f1d7a7bf24 (head)`;
- local trusted TLS: `https://esf.local`, HTTP→HTTPS 301, HTTPS 200;
- full production smoke: 12/12 — login, create, publish, public verification,
  PDF, QR and critical-log check;
- production secret file: outside the repository, mode 600;
- pre-acceptance database backup created before admin bootstrap.

This is not a public-production acceptance signature: `esf.local` uses a local
mkcert CA. Closing the external gate requires a real controlled domain/VPS and
an independent named acceptor.

## Final external gate

1. Deploy the reviewed SHA to the public target using `DEPLOY_UBUNTU.md`.
2. Run `scripts/prod_smoke_test.sh` on staging (it creates an immutable test
   document).
3. Run the non-mutating public probe from outside the target network:
   `BASE_URL=https://<domain> bash scripts/external_acceptance_probe.sh`.
4. Record deployment SHA, domain, smoke/probe outputs, acceptor name, date and
   verdict here. No secret or credential is recorded.

| Field | Value |
| --- | --- |
| Deployment SHA | Pending public deployment |
| Public domain | Pending owner infrastructure |
| External acceptor | Pending |
| Acceptance date | Pending |
| Verdict | OPEN |

