# DEFINITION_OF_DONE.md

A task is complete only when:
1. Feature works end-to-end.
2. App starts without runtime/import errors.
3. Existing completed flows still work.
4. No duplicate STI-007 templates.
5. PDF layout is not duplicated outside HTML/CSS unless approved.
6. Documentation updated.
7. TODO.md and PROJECT_STATE.md updated.
8. Known issues recorded in TECHNICAL_DEBT.md.
9. Next task selected automatically.

Security:
- edit routes require auth/dev context;
- owner/admin guard exists;
- public route is read-only;
- URLs use UUID, not sequential ID.
