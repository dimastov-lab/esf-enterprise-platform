# SPRINT_7R_PROMPT.md

Start Sprint 7R — QR + Public Verification + Result Page.

Goal:
Complete the external verification flow.

Use the existing same template:
backend/app/templates/esf/form.html

Do NOT create a duplicate public template.

Scope:
1. Generate QR PNG for each ESF.
2. QR content: /esf/check-esf?documentUUID={uuid}
3. Add GET /qr/{uuid}.png
4. Add GET /esf/check-esf?documentUUID={uuid}
5. Public route: no login, read-only, no edit controls, same template with mode="public".
6. Add GET /result/{uuid}

Definition of Done:
- QR file is generated.
- /qr/{uuid}.png returns PNG.
- Public check page opens without login.
- Public page visually matches existing STI-007 template.
- /result/{uuid} works.
- PDF link works from result page.
- No duplicate templates.
- Docs updated.
- Continue automatically to next TODO item unless blocked.
