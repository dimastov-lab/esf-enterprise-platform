#!/usr/bin/env bash
# Production smoke test for the ESF Enterprise Platform.
# Run on the server after `docker compose -f docker-compose.prod.yml up -d`.
#
#   ./scripts/prod_smoke_test.sh
#
# Env overrides:
#   BASE_URL          public base (default https://localhost; uses curl -k for self-signed)
#   ENV_FILE          compose env file (default .env.production)
#   ADMIN_USERNAME    admin login (default from env file / "admin")
#   ADMIN_PASSWORD    admin password (must exist; create with scripts/create_admin.py)
#
# NOTE: this creates and publishes one test document (published docs are immutable
# and cannot be deleted) — prefer running it against staging.

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env.production}"
if [ -f "$ENV_FILE" ]; then set -a; . "$ENV_FILE"; set +a; fi
BASE_URL="${BASE_URL:-https://localhost}"
COMPOSE="docker compose -f $ROOT/docker-compose.prod.yml --env-file $ENV_FILE"
CURL="curl -ksS -m 30"
JAR="$(mktemp)"; trap 'rm -f "$JAR" /tmp/esf_*.tmp' EXIT
pass=0; fail=0
ok(){ echo "  [PASS] $1"; pass=$((pass + 1)); }
no(){ echo "  [FAIL] $1"; fail=$((fail + 1)); }
chk(){ if [ "$1" = "$2" ]; then ok "$3 ($1)"; else no "$3 (got '$1', want '$2')"; fi; }

echo "== 1. Application starts (health) =="
code=$($CURL -o /tmp/esf_h.tmp -w '%{http_code}' "$BASE_URL/")
chk "$code" 200 "GET / health"
grep -q running /tmp/esf_h.tmp && ok "health reports running" || no "health body unexpected"

echo "== 2/3. Database available + migration current =="
cur=$($COMPOSE exec -T app alembic current 2>/dev/null | tr -d '\r')
echo "    alembic current: ${cur:-<none>}"
echo "$cur" | grep -q "(head)" && ok "DB reachable & migration at head" || no "migration not at head / DB unreachable"

echo "== 4. Login page returns 200 =="
code=$($CURL -o /dev/null -w '%{http_code}' "$BASE_URL/login"); chk "$code" 200 "GET /login"

echo "== 5. Dashboard accessible after login =="
$CURL -c "$JAR" -b "$JAR" -o /dev/null -X POST "$BASE_URL/login" \
  --data-urlencode "username=${ADMIN_USERNAME:-admin}" \
  --data-urlencode "password=${ADMIN_PASSWORD:-}" >/dev/null
code=$($CURL -c "$JAR" -b "$JAR" -o /tmp/esf_dash.tmp -w '%{http_code}' "$BASE_URL/dashboard")
chk "$code" 200 "GET /dashboard (authenticated)"
CSRF=$(grep -o 'name="csrf_token" value="[^"]*"' /tmp/esf_dash.tmp | head -1 | sed 's/.*value="//; s/"//')
[ -n "$CSRF" ] && ok "CSRF token obtained" || no "CSRF token not found (login may have failed)"

echo "== create + publish a test document =="
loc=$($CURL -c "$JAR" -b "$JAR" -o /dev/null -w '%{redirect_url}' "$BASE_URL/esf/new")
UUID="${loc##*/esf/}"
[ -n "$UUID" ] && [ "$UUID" != "$loc" ] && ok "draft created ($UUID)" || { no "draft create failed"; UUID=""; }
FORM="csrf_token=$CSRF&supplier_inn=01610201710254&supplier_name=SmokeSupplier&buyer_inn=6686063027&buyer_name=SmokeBuyer&currency_code=643&currency_rate=1.2263&director_name=SmokeDirector&item_tnved=7308400009&item_name=SmokeItem&item_unit=kg&item_price=100&item_qty=10&item_vat_rate=0&item_vat_amount=0&item_nsp=0"
if [ -n "$UUID" ]; then
  $CURL -c "$JAR" -b "$JAR" -o /dev/null -X POST "$BASE_URL/esf/$UUID/save" -H "X-CSRF-Token: $CSRF" --data "$FORM" >/dev/null
  pub=$($CURL -c "$JAR" -b "$JAR" -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/esf/$UUID/publish" -H "X-CSRF-Token: $CSRF" --data "$FORM")
  chk "$pub" 303 "publish (redirect to result)"
fi

echo "== 6. Public verification works =="
if [ -n "$UUID" ]; then
  code=$($CURL -o /dev/null -w '%{http_code}' "$BASE_URL/esf/check-esf?documentUUID=$UUID")
  chk "$code" 200 "GET /esf/check-esf (published)"
fi

echo "== 7. PDF generation works =="
if [ -n "$UUID" ]; then
  ct=$($CURL -c "$JAR" -b "$JAR" -o /tmp/esf_t.pdf -w '%{content_type}' "$BASE_URL/pdf/$UUID.pdf")
  head -c4 /tmp/esf_t.pdf | grep -q "%PDF" && ok "PDF generated ($ct)" || no "PDF not generated"
fi

echo "== 8. QR generation works =="
if [ -n "$UUID" ]; then
  ct=$($CURL -o /tmp/esf_t.png -w '%{content_type}' "$BASE_URL/qr/$UUID.png")
  chk "$ct" "image/png" "GET /qr/{uuid}.png"
fi

echo "== 9. No critical startup errors =="
errs=$($COMPOSE logs app 2>&1 | grep -iE "traceback|critical|fatal" | wc -l | tr -d ' ')
[ "$errs" = "0" ] && ok "no critical errors in app logs" || no "$errs suspicious log line(s) — review: $COMPOSE logs app"

echo
echo "RESULT: $pass passed, $fail failed"
if [ "$fail" = "0" ]; then echo "SMOKE TEST: GREEN"; exit 0; else echo "SMOKE TEST: RED"; exit 1; fi
