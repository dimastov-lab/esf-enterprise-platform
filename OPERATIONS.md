# OPERATIONS.md — ESF Enterprise Platform runbook

```bash
DC="docker compose -f docker-compose.prod.yml --env-file .env.production"
```

## Administrator login
Open `https://<your-host>/login` and sign in. Admins see **Пользователи** (`/admin/users`) and
**Аудит** (`/admin/audit`) links on the dashboard.

## Create users
UI (preferred): `/admin/users` → fill username/password, choose role **ADMIN** or **ISSUER** →
*Создать*. ISSUER can create/edit/publish their own documents; ADMIN sees everything and manages users.

First admin / scripted:
```bash
$DC exec app python scripts/create_admin.py <username> '<password>'
```

## Reset a password
There is no self-service reset UI. An operator resets a password with a one-off command that
reuses the app's own hashing (no app change):
```bash
$DC exec app python - <<'PY'
from app.db.session import SessionLocal
from app.core.passwords import hash_password
from app.models import User
u, newpw = "username_here", "NewStrongPass123"
db = SessionLocal()
user = db.query(User).filter(User.username == u).one()
user.hashed_password = hash_password(newpw)
db.commit(); db.close()
print("password updated for", u)
PY
```

## Disable / lock out a user
```bash
$DC exec app python - <<'PY'
from app.db.session import SessionLocal
from app.models import User
db=SessionLocal(); x=db.query(User).filter(User.username=="username_here").one()
x.is_active=False; db.commit(); db.close(); print("disabled")
PY
```
Inactive users cannot authenticate (set `is_active=True` to re-enable).

## View logs
```bash
$DC logs -f app          # app + access logs
$DC logs --tail=200 app
$DC logs nginx | tail -100
$DC logs db | tail -100
```
Audit trail of business actions (login, publish, delete, public view, PDF download) is in the UI:
`/admin/audit`.

## Restart services
```bash
$DC restart app          # app only
$DC restart nginx        # proxy only (e.g. after cert renewal)
$DC restart              # whole stack
```

## Health check
```bash
$DC ps                                   # STATUS should be healthy
curl -k https://<your-host>/healthz      # nginx -> "ok"
curl -k https://<your-host>/             # app health JSON {"status":"running",...}
./scripts/prod_smoke_test.sh             # full end-to-end
```

## TLS certificate renewal (Let's Encrypt)
```bash
sudo certbot renew
sudo cp /etc/letsencrypt/live/<domain>/fullchain.pem infra/nginx/certs/
sudo cp /etc/letsencrypt/live/<domain>/privkey.pem  infra/nginx/certs/
$DC restart nginx
```

## Common troubleshooting
| Symptom | Cause / fix |
|---|---|
| App container exits immediately, log: *"SECRET_KEY must be set…"* | `SECRET_KEY` is empty/default in `.env.production`. Set a real value (fail-closed by design). |
| Can log in form submits but you land back on /login | Browser not on HTTPS. Session cookie is `Secure` in production; access via `https://`. |
| `502 Bad Gateway` from nginx | App not healthy yet or crashed. `$DC ps`, `$DC logs app`. |
| Migrations / `alembic current` not at head | `$DC exec app alembic upgrade head`; check DB health `$DC logs db`. |
| PDF endpoint 500 / blank | WeasyPrint native libs — they are in the image; rebuild with `$DC build app`. Check `$DC logs app`. |
| Duplicate ESF number on save → 409 | Expected: the entered `НОМЕР` is already used. Use a unique number or leave blank (auto-assigned at publish). |
| Login locked / 429 | Login rate limit (5 failures / 5 min per IP). Wait, or `$DC restart app` to clear the in-process counter. |
| Public verification returns 404 | The document is not PUBLISHED (only published docs are publicly verifiable). |
