#!/usr/bin/env bash
set -Eeuo pipefail

BASE_URL="${BASE_URL:?Set BASE_URL to the public HTTPS origin}"
case "$BASE_URL" in https://*) ;; *) echo "BASE_URL must use https://" >&2; exit 2;; esac

HOST="$(python3 -c 'import sys,urllib.parse; print(urllib.parse.urlsplit(sys.argv[1]).hostname or "")' "$BASE_URL")"
if [[ -z "$HOST" ]]; then echo "BASE_URL has no host" >&2; exit 2; fi
if [[ "${ALLOW_NONPUBLIC:-0}" != "1" && "$HOST" =~ (^localhost$|\.local$|^127\.) ]]; then
  echo "external acceptance requires a public host" >&2
  exit 2
fi

WORK="$(mktemp -d)"
trap 'find "$WORK" -type f -delete; rmdir "$WORK"' EXIT
pass=0
ok() { echo "[PASS] $1"; pass=$((pass + 1)); }
fail() { echo "[FAIL] $1" >&2; exit 1; }

http_code="$(curl -sS --max-time 20 -o /dev/null -w '%{http_code}' "http://$HOST/")"
[[ "$http_code" == "301" || "$http_code" == "308" ]] && ok "HTTP redirects to HTTPS" || fail "HTTP redirect status is $http_code"

https_code="$(curl -sS --max-time 30 -D "$WORK/headers" -o "$WORK/body" -w '%{http_code}' "$BASE_URL/")"
[[ "$https_code" == "200" ]] && ok "HTTPS health endpoint returns 200" || fail "HTTPS returned $https_code"
grep -q 'running' "$WORK/body" && ok "health body reports running" || fail "unexpected health body"

login_code="$(curl -sS --max-time 30 -o /dev/null -w '%{http_code}' "$BASE_URL/login")"
[[ "$login_code" == "200" ]] && ok "login surface returns 200" || fail "login returned $login_code"

for header in strict-transport-security content-security-policy x-content-type-options x-frame-options referrer-policy; do
  grep -qi "^$header:" "$WORK/headers" && ok "$header present" || fail "$header missing"
done

openssl s_client -connect "$HOST:443" -servername "$HOST" </dev/null 2>/dev/null > "$WORK/cert-chain"
openssl x509 -in "$WORK/cert-chain" -noout -checkend 604800 >/dev/null \
  && ok "TLS certificate valid for at least 7 days" \
  || fail "TLS certificate expires within 7 days or is invalid"

echo "EXTERNAL PUBLIC PROBE: GREEN ($pass checks)"

