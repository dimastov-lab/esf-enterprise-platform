# Security Policy

The ESF Enterprise Platform issues, stores, and publicly verifies Kyrgyz electronic
VAT invoices (ЭСФ — СЧЁТ-ФАКТУРА, form STI-007). It handles **legally- and
financially-significant documents** (invoice data, immutable published snapshots,
user accounts, audit trails). Security reports are taken seriously and prioritized.

## Supported versions

| Version                         | Supported          |
| ------------------------------- | ------------------ |
| v1.1.3 (current, RC1)           | ✅ Yes             |
| Earlier v1.1.x / v1.0.x         | ⚠️ Best-effort only |
| Pre-release / development snapshots | ❌ No          |

Only the latest release line receives security fixes. Please upgrade to the current
version before reporting an issue against an older build.

## Reporting a vulnerability

**Do not open a public issue, pull request, or public discussion for security
problems.**

Report privately by email to **dimastov@me.com** with:

- a description of the vulnerability and its impact;
- steps to reproduce (proof-of-concept if available);
- affected version / commit and environment;
- any suggested remediation.

Please give the maintainer reasonable time to investigate and ship a fix before any
public disclosure (coordinated disclosure).

### Response timeframe

- **Acknowledgement:** within **72 hours** of your report.
- **Initial assessment / triage:** within **7 days**.
- **Fix or mitigation plan:** communicated after triage, prioritized by severity
  (critical issues affecting document integrity, snapshot immutability,
  authentication, or the audit log are treated as highest priority).

## IMPORTANT: generated documents are NON-OFFICIAL

This platform is a faithful **functional and visual clone** of the STI-007 form. It
is **not connected to the State Tax Service (ГНС) system at `esf.salyk.kg`** and does
**not** apply a digital signature (ЭЦП).

As a result, documents produced by this platform have **no legal validity** and are
**NON-OFFICIAL**. The QR code and public verification page reproduce the official
format for fidelity, but they do not constitute registration with, or verification
by, the tax authority. Do not represent generated invoices as officially issued or
legally binding ESF documents. Tax-authority integration and legally valid issuance
are explicitly out of scope (see `TECHNICAL_DEBT.md` and `RELEASE_NOTES.md`).

## Deployment security reminders

- Always serve over **HTTPS**; the session cookie is `Secure` only in production.
- Set a unique, strong `SECRET_KEY` (the app refuses to start in production with a
  default/empty key) and a strong database password.
- Keep `.env.production` out of version control.
- Take and off-host regular `pg_dump` backups (see `BACKUP.md`).
