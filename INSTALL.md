# INSTALL.md — ESF Enterprise Platform (production)

Clean-server installation. Target: a fresh Linux server (Ubuntu 22.04/24.04 or Debian 12).
Everything runs in Docker; no Python/Postgres needed on the host.

## 1. Server requirements

- Linux x86_64, 2 vCPU / 2 GB RAM / 10 GB disk (minimum).
- Outbound internet for pulling images during build.
- Open inbound ports **80** and **443**.
- A DNS name pointing at the server (recommended; needed for real TLS certs).

## 2. Install Docker + Compose plugin

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"   # log out/in so the group applies
docker --version && docker compose version
```

## 3. Get the repository

```bash
git clone <your-repo-url> esf && cd esf
```

## 4. Environment

```bash
cp .env.production.example .env.production
# Generate strong secrets:
python3 -c "import secrets;print(secrets.token_hex(32))"   # -> SECRET_KEY
openssl rand -hex 24                                         # -> POSTGRES_PASSWORD
nano .env.production
```
Set at minimum: `SECRET_KEY`, `POSTGRES_PASSWORD` (and the same password inside `DATABASE_URL`),
`PUBLIC_BASE_URL` (your public HTTPS URL), `TZ`, `ADMIN_PASSWORD`.
The app **refuses to start in production with a default/empty `SECRET_KEY`**.

## 5. TLS certificates (required — sessions use Secure cookies)

Place a certificate and key here:
```
infra/nginx/certs/fullchain.pem
infra/nginx/certs/privkey.pem
```
Production (Let's Encrypt): obtain certs with certbot on the host and copy/symlink them in, e.g.
```bash
sudo certbot certonly --standalone -d esf.example.com
mkdir -p infra/nginx/certs
sudo cp /etc/letsencrypt/live/esf.example.com/fullchain.pem infra/nginx/certs/
sudo cp /etc/letsencrypt/live/esf.example.com/privkey.pem  infra/nginx/certs/
```
Testing only (self-signed; browser/`curl -k` will warn):
```bash
mkdir -p infra/nginx/certs
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout infra/nginx/certs/privkey.pem -out infra/nginx/certs/fullchain.pem \
  -subj "/CN=localhost"
```

## 6. Build & start (database init + migration are automatic)

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```
On first start the app container runs `alembic upgrade head` automatically (creating all tables),
then serves the app. PostgreSQL data persists in the `pg_data` volume.

## 7. Create the first administrator

No admin is auto-created in production. Create one (uses `ADMIN_USERNAME`/`ADMIN_PASSWORD` from
your env file, or pass explicitly):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production \
  exec app python scripts/create_admin.py
# or: ... exec app python scripts/create_admin.py myadmin 'StrongPass123'
```

## 8. Verify

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps   # all healthy
./scripts/prod_smoke_test.sh                                              # end-to-end checks
```
Then open `https://<your-host>/login` and sign in with the admin account.

See **DEPLOY.md** for updates/rollback, **OPERATIONS.md** for day-to-day runbooks,
**BACKUP.md** for backups.
