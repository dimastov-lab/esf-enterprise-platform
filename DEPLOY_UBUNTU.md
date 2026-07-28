# Deploying the ESF Enterprise Platform on an Ubuntu VPS

A single, copy‑pasteable walkthrough for a fresh **Ubuntu 22.04 / 24.04 LTS** server, using
**Docker + PostgreSQL + Nginx + HTTPS**. It uses the repo's production stack as‑is:
`docker-compose.prod.yml` (services **db**, **app**, **nginx**), `backend/Dockerfile`,
`infra/nginx/nginx.conf`, and `.env.production`. **No application code is changed by this guide.**

> Already know Docker? The whole thing is: put the repo on the server → fill `.env.production` →
> `docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build` → create the
> first admin → drop in TLS certs. Everything below is the careful version.

Related docs: `INSTALL.md` (concise), `OPERATIONS.md` (runbook), `BACKUP.md`, and
`docs/history/ENTERPRISE_FINAL_CERTIFICATION.md` (security/production posture).

---

## 0. Architecture on the server

```
Internet ──443/80──> [ nginx container ]  TLS termination, security headers, /static, /healthz
                           │ proxy_pass http://app:8000
                           ▼
                     [ app container ]    FastAPI + uvicorn (workers), renders PDF/QR
                           │ DATABASE_URL (host = "db")
                           ▼
                     [ db container ]     PostgreSQL 15  (NOT published to the host)
```

- Only **nginx** publishes host ports (80, 443). `db` and `app` are reachable only on the internal
  Docker network — Postgres is never exposed to the internet.
- The **app entrypoint runs `alembic upgrade head` automatically** on every start, then launches
  uvicorn. You do not run migrations by hand.
- Persistent state lives in two named Docker volumes: **`pg_data`** (the database — critical) and
  **`esf_storage`** (generated QR PNGs — regenerable from the DB).

---

## 1. Server requirements

| Item | Minimum | Recommended |
|------|---------|-------------|
| OS | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| vCPU | 1 | 2+ (PDF rendering is CPU‑bound) |
| RAM | 1 GB | 2–4 GB |
| Disk | 15 GB | 25 GB+ SSD |
| Access | `sudo`/root shell | dedicated deploy user with sudo |
| Network | public IPv4 | IPv4 (+ optional IPv6) |

You also need a **domain name** you control (e.g. `esf.example.com`) and the ability to edit its
DNS records.

---

## 2. DNS setup

Point the domain at your server **before** requesting TLS certificates.

1. Find your server's public IP: `curl -4 ifconfig.co`
2. At your DNS provider, create:
   - `A` record: `esf.example.com` → `<server-ipv4>` (TTL 300 while setting up)
   - *(optional)* `AAAA` record → `<server-ipv6>`
3. Verify propagation (wait until it returns your server IP):
   ```bash
   dig +short esf.example.com
   ```

Do not continue to the HTTPS step until `dig` returns the correct IP.

---

## 3. Initial server hardening (recommended)

```bash
# As root or with sudo, on the server:
adduser deploy && usermod -aG sudo deploy        # a non-root deploy user
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy   # copy your SSH key (if using root now)

# Firewall: allow SSH + web only
sudo apt-get update
sudo apt-get install -y ufw
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

Log in as `deploy` for the rest of this guide.

---

## 4. Install Docker Engine + Compose plugin

Use Docker's official APT repository (the `docker compose` v2 plugin is included):

```bash
# Remove any distro Docker, then install the official packages
sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Run docker without sudo (log out/in afterwards to apply the group)
sudo usermod -aG docker "$USER"
newgrp docker

docker --version && docker compose version   # verify
```

---

## 5. Put the project on the server

Clone (or `scp`) the repository into the deploy user's home:

```bash
cd ~
git clone <your-repo-url> esf && cd esf
# ...or copy your local checkout:  rsync -az --exclude .venv ./ deploy@server:~/esf/
```

All commands below are run from the repository root (`~/esf`).

---

## 6. Configure `.env.production`

```bash
cp .env.production.example .env.production
```

Generate strong secrets and edit the file:

```bash
# A 64-hex-char session key (the app REFUSES to start in production without a real one):
python3 -c "import secrets; print(secrets.token_hex(32))"
# A strong database password:
openssl rand -hex 24
```

Edit `.env.production` and set **at minimum**:

| Variable | Set to |
|----------|--------|
| `POSTGRES_PASSWORD` | the `openssl rand` value |
| `DATABASE_URL` | `postgresql+psycopg2://esf:<same-password>@db:5432/esf` (host **must** be `db`) |
| `SECRET_KEY` | the `token_hex(32)` value |
| `PUBLIC_BASE_URL` | `https://esf.example.com` (your real HTTPS host — used in QR/public links) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | the first admin's credentials (used in step 9) |
| `TZ` | e.g. `Asia/Bishkek` (affects logs + document timestamps) |
| `WEB_CONCURRENCY` | uvicorn workers, e.g. `2` (see note below) |

Lock the file down — it holds secrets and must never be committed:

```bash
chmod 600 .env.production
grep -q '^\.env\.production$' .gitignore || echo '.env.production' >> .gitignore
```

> **`WEB_CONCURRENCY` note:** the login rate‑limiter is per‑process. For strict brute‑force limits
> use `WEB_CONCURRENCY=1`, or accept per‑worker limits with more workers (see `TECHNICAL_DEBT.md`
> TD‑019). 2 workers is a good default for a small VPS.

---

## 7. Obtain TLS certificates (HTTPS)

Nginx expects certificates at **`infra/nginx/certs/fullchain.pem`** and
**`infra/nginx/certs/privkey.pem`**. The bundled `nginx.conf` terminates TLS (TLS 1.2/1.3),
redirects HTTP→HTTPS, and sends HSTS + security headers.

Use **Let's Encrypt via certbot in standalone mode** (it binds port 80 itself, so run it *before*
starting the nginx container). DNS from step 2 must already resolve to this server.

```bash
sudo apt-get install -y certbot
sudo mkdir -p ~/esf/infra/nginx/certs

# Port 80 must be free right now (nginx container not started yet).
sudo certbot certonly --standalone -d esf.example.com \
  --non-interactive --agree-tos -m you@example.com

# Copy the issued certs to where the compose stack mounts them:
sudo cp /etc/letsencrypt/live/esf.example.com/fullchain.pem ~/esf/infra/nginx/certs/fullchain.pem
sudo cp /etc/letsencrypt/live/esf.example.com/privkey.pem  ~/esf/infra/nginx/certs/privkey.pem
sudo chown "$USER":"$USER" ~/esf/infra/nginx/certs/*.pem
```

**Testing without a domain?** Generate a self‑signed cert instead (browsers will warn; fine for a
smoke test):

```bash
mkdir -p infra/nginx/certs
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout infra/nginx/certs/privkey.pem \
  -out    infra/nginx/certs/fullchain.pem \
  -subj "/CN=$(curl -4 -s ifconfig.co)"
```

Certificate **renewal** is covered in step 12.

---

## 8. Build and start the stack

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

This builds the app image, starts `db` → `app` (which auto‑applies migrations) → `nginx`.
Watch it come up healthy:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps
# all three services should reach "healthy"

# Follow the app logs until you see "migrations OK" then uvicorn startup:
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f app
```

> Tip: export a shorthand so you type less —
> `alias dcp='docker compose -f docker-compose.prod.yml --env-file .env.production'`
> Then it's just `dcp ps`, `dcp logs -f app`, etc. The rest of this guide uses the full command.

---

## 9. Create the first admin user

In production **no admin is auto‑seeded**. Create one with the bundled script (it reads
`ADMIN_USERNAME` / `ADMIN_PASSWORD` from `.env.production`, and is idempotent):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production \
  exec app python scripts/create_admin.py
# -> "Admin user 'admin' created."   (or "already exists — nothing to do")
```

Or pass explicit credentials instead of relying on the env vars:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production \
  exec app python scripts/create_admin.py myadmin 'a-strong-password'
```

You can now log in at `https://esf.example.com/login`.

---

## 10. Smoke test

Validate the full flow (health, login, create → publish, public page, PDF, QR, logs) with the
bundled script. It creates and **publishes one test document** (published docs are immutable and
cannot be deleted), so prefer running it against staging if you keep production clean:

```bash
BASE_URL="https://esf.example.com" ./scripts/prod_smoke_test.sh
# ...
# RESULT: N passed, 0 failed
# SMOKE TEST: GREEN
```

For a self‑signed cert the script already uses `curl -k`, so it works against `https://localhost`
on the server too:

```bash
./scripts/prod_smoke_test.sh          # defaults to https://localhost
```

---

## 11. Backups

**The database is the only critical backup** (all documents, immutable snapshots, users). QR PNGs
in the `esf_storage` volume are regenerated from the DB on demand, so backing them up is optional.

```bash
# --- Database dump (run from the repo root) ---
docker compose -f docker-compose.prod.yml --env-file .env.production \
  exec -T db pg_dump -U esf esf | gzip > ~/esf-backup-$(date +%F).sql.gz

# --- (optional) QR assets volume ---
docker run --rm -v esf_esf_storage:/data -v "$PWD":/backup alpine \
  tar czf /backup/esf-qr-$(date +%F).tgz -C /data .
```

> The QR volume's full name is `<project>_esf_storage` (compose prefixes the project directory
> name — `esf` here → `esf_esf_storage`). Confirm with `docker volume ls`.

**Automate it** with cron (nightly at 02:30, keep 14 days):

```bash
crontab -e
# add:
30 2 * * * cd /home/deploy/esf && docker compose -f docker-compose.prod.yml --env-file .env.production exec -T db pg_dump -U esf esf | gzip > /home/deploy/backups/esf-$(date +\%F).sql.gz && find /home/deploy/backups -name 'esf-*.sql.gz' -mtime +14 -delete
```

Always take a fresh dump **before** deploying a schema change. Store copies off‑host (e.g. `rclone`
to object storage). See `BACKUP.md` for more.

---

## 12. Restore

Restore a dump into the running stack (this **overwrites** current data — be sure):

```bash
# 1. (safety) take a dump of the current state first, if the DB still works.
# 2. Recreate a clean schema, then load the dump:
gunzip -c ~/esf-backup-YYYY-MM-DD.sql.gz | \
  docker compose -f docker-compose.prod.yml --env-file .env.production \
  exec -T db psql -U esf -d esf
```

If you need a completely empty database first:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production \
  exec -T db psql -U esf -d postgres -c "DROP DATABASE esf;" -c "CREATE DATABASE esf OWNER esf;"
# then load the dump as above; the app will re-run migrations on next restart if needed.
```

Immutable snapshots and their sha256 hashes are preserved by a dump/restore, so the legal copies
remain intact.

### TLS certificate renewal

Let's Encrypt certs last 90 days. Renew and re‑copy them into the mount, then reload nginx. Because
the nginx container holds port 80, renew in standalone mode with a brief stop, or use a deploy hook:

```bash
# Simple monthly cron (renews, copies, reloads nginx):
sudo crontab -e
# add (03:15 on the 1st of each month):
15 3 1 * * certbot renew --standalone --pre-hook "cd /home/deploy/esf && docker compose -f docker-compose.prod.yml --env-file .env.production stop nginx" --post-hook "cp /etc/letsencrypt/live/esf.example.com/fullchain.pem /home/deploy/esf/infra/nginx/certs/fullchain.pem && cp /etc/letsencrypt/live/esf.example.com/privkey.pem /home/deploy/esf/infra/nginx/certs/privkey.pem && cd /home/deploy/esf && docker compose -f docker-compose.prod.yml --env-file .env.production start nginx"
```

---

## 13. Day‑2 operations (quick reference)

```bash
# Health / status
docker compose -f docker-compose.prod.yml --env-file .env.production ps
curl -k https://localhost/healthz            # nginx edge health -> "ok"
curl -sk https://localhost/ | head           # app health JSON via nginx

# Logs (rotated by Docker's json-file driver)
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f app
docker compose -f docker-compose.prod.yml --env-file .env.production logs --since 1h nginx

# Restart / stop
docker compose -f docker-compose.prod.yml --env-file .env.production restart app
docker compose -f docker-compose.prod.yml --env-file .env.production down     # stop all (keeps volumes)

# Deploy an update (pull code, rebuild, migrations auto-run on app start)
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Each request carries an `X-Request-ID` and logs a structured JSON access line
(`method`, `path`, `status`, `duration_ms`) — grep the app logs by request id when debugging.

---

## 14. Troubleshooting

| Symptom | Cause & fix |
|---------|-------------|
| App container restarts / exits | Check `logs app`. Most common: bad `DATABASE_URL` (host must be `db`) or the entrypoint's migration retries exhausted because `db` is unhealthy. |
| `SECRET_KEY must be set…` in logs | `SECRET_KEY` is empty/default in `.env.production`. Set a real `token_hex(32)` value and recreate: `up -d`. |
| 502 Bad Gateway from nginx | `app` not healthy yet (PDF libs load on first render) — wait for `start_period`, or `logs app` for a stacktrace. |
| Browser TLS warning | Self‑signed cert, or cert/key mismatch. Verify `infra/nginx/certs/fullchain.pem` + `privkey.pem` are the real pair, then `restart nginx`. |
| certbot fails to bind :80 | The nginx container is using it. Stop nginx first (`stop nginx`), issue/renew, then `start nginx`. |
| Login fails for the admin | The admin isn't created in production automatically — run step 9. Verify with `logs app` (a failed login is audited). |
| DB connection refused | `db` still starting or unhealthy: `ps` should show `healthy`; check `logs db`. |
| Public/QR link points at wrong host | `PUBLIC_BASE_URL` is wrong. Fix it in `.env.production` and `up -d` (QR is regenerated on next request). |
| Changes to `nginx.conf` not applied | It's mounted read‑only; `restart nginx` to reload. |

---

## 15. Production checklist

- [ ] DNS `A` record resolves to the server (`dig +short esf.example.com`).
- [ ] `ufw` allows only 22/80/443.
- [ ] `.env.production` has a real `SECRET_KEY`, strong `POSTGRES_PASSWORD`, correct `DATABASE_URL`
      (host `db`), and `PUBLIC_BASE_URL=https://<your-host>`; file is `chmod 600` and git‑ignored.
- [ ] `ENVIRONMENT=production` (disables dev admin seed + `/dev` preview, enables `Secure` cookies).
- [ ] Real TLS certs present at `infra/nginx/certs/` (Let's Encrypt), renewal cron installed.
- [ ] All three services `healthy` (`ps`).
- [ ] First admin created (step 9); default dev creds are **not** usable in production.
- [ ] Smoke test **GREEN** (step 10).
- [ ] Nightly DB backup cron installed and writing to off‑host storage.
- [ ] You have tested a **restore** into a scratch database at least once.

Once every box is checked, the platform is live and operable. For the security/production posture
and known limitations, see `docs/history/ENTERPRISE_FINAL_CERTIFICATION.md`.
