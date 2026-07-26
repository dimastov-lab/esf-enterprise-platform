# CODING_STANDARDS.md

Architecture: Controller → Service → Repository → Database.
No business logic in routers/controllers.
No DB access from templates.
No duplicate STI-007 templates.

UI: official document look, not generic Bootstrap.
Use compact typography, hairline borders, HTML tables, fixed document layout.

PDF: use WeasyPrint and existing HTML/CSS template.

Database: PostgreSQL only. One Base, one engine. UUID for public identity.

Safety: no permanent deletes, DB drops, or stack changes without approval.
