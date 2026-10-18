#!/usr/bin/env bash
# Uji HTTPS terisolasi (WP-3.6b): tumpukan sementara (proyek compose sendiri, data sementara, port 8443/8080)
# dengan overlay compose.tls.yaml; memeriksa pengalihan HTTP->HTTPS, HSTS, cookie Secure/HttpOnly, CSP, aset
# statis, login lewat HTTPS, dan `check --deploy`. Tidak menyentuh stack dev. Butuh Docker dan internet (image).
set -euo pipefail
cd "$(dirname "$0")/.."

TMP="$(mktemp -d)"
PROJECT=snr-tlscheck
HTTPS_PORT=8443
HTTP_PORT=8080
export SNR_HOST_DATA="$TMP/data" SNR_CERTS_DIR="$TMP/certs" SNR_HTTPS_PORT=$HTTPS_PORT SNR_HTTP_PORT=$HTTP_PORT
export SNR_DOMAIN=localhost DJANGO_ALLOWED_HOSTS=localhost
export DJANGO_CSRF_TRUSTED_ORIGINS="https://localhost:$HTTPS_PORT"
export DJANGO_SECRET_KEY="$(openssl rand -base64 48 | tr -d '/+=')"
export POSTGRES_PASSWORD="$(openssl rand -base64 18 | tr -d '/+=')"
export POSTGRES_DB=snr POSTGRES_USER=snr
PW="$(openssl rand -base64 18 | tr -d '/+=')"
mkdir -p "$SNR_HOST_DATA"/{data/postgres,evidence,exports,browser-profiles,static} "$SNR_CERTS_DIR"
DC=(docker compose -p $PROJECT -f compose.yaml -f compose.tls.yaml)

cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    echo "--- log web/proxy (gagal) ---" >&2
    "${DC[@]}" logs --no-color --tail 25 web proxy 2>&1 | tail -60 >&2 || true
  fi
  "${DC[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  chmod -R u+w "$TMP" 2>/dev/null || true
  rm -rf "$TMP"
}
trap cleanup EXIT

fail() { echo "GAGAL: $*" >&2; exit 1; }
ok() { echo "  ok  $*"; }

echo "== membangun frontend dan menjalankan tumpukan HTTPS"
"${DC[@]}" --profile build run --rm frontend-build >/dev/null
"${DC[@]}" up -d --build postgres valkey web proxy >/dev/null
for _ in $(seq 1 60); do
  [ "$(curl -sk -o /dev/null -w '%{http_code}' https://localhost:$HTTPS_PORT/api/auth/csrf/ 2>/dev/null || true)" = "200" ] && break
  sleep 2
done

B="https://localhost:$HTTPS_PORT"
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://localhost:$HTTP_PORT/") || true
loc=$(curl -s -o /dev/null -w '%{redirect_url}' --max-time 10 "http://localhost:$HTTP_PORT/") || true
[[ "$code" =~ ^30[78]$ ]] && [[ "$loc" == https://* ]] || fail "HTTP tidak dialihkan ke HTTPS (kode $code, tujuan '$loc')"
ok "HTTP dialihkan ke HTTPS ($code)"

headers="$(curl -sk -D - -o /dev/null "$B/")"
echo "$headers" | grep -qi '^content-security-policy:.*default-src' || fail "CSP tidak ada pada frontend"
echo "$headers" | grep -qi '^x-content-type-options: nosniff' || fail "nosniff tidak ada"
echo "$headers" | grep -qi '^server:' && fail "header Server bocor"
ok "frontend dilayani lewat HTTPS dengan CSP dan nosniff, tanpa header Server"

asset="$(curl -sk "$B/" | grep -o '/assets/[^"]*\.js' | head -1)"
[ -n "$asset" ] && [ "$(curl -sk -o /dev/null -w '%{http_code}' "$B$asset")" = "200" ] || fail "aset JS frontend tidak terlayani"
[ "$(curl -sk -o /dev/null -w '%{http_code}' "$B/login")" = "200" ] || fail "rute SPA tidak jatuh ke index.html"
ok "aset frontend dan rute SPA terlayani"

[ "$(curl -sk -o /dev/null -w '%{http_code}' "$B/static/admin/css/base.css")" = "200" ] || fail "static admin tidak terlayani"
ok "static admin terlayani (collectstatic)"

JAR="$TMP/jar"
csrf_headers="$(curl -sk -c "$JAR" -D - -o /dev/null "$B/api/auth/csrf/")"
echo "$csrf_headers" | grep -qi '^strict-transport-security: max-age=3600' || fail "HSTS tidak ada"
echo "$csrf_headers" | grep -i '^set-cookie: csrftoken' | grep -qi 'secure' || fail "cookie CSRF tidak Secure"
ok "HSTS ada dan cookie CSRF Secure"

"${DC[@]}" exec -T web python manage.py shell -c \
  "from django.contrib.auth.models import User; User.objects.create_user('uji_tls', password='$PW')" >/dev/null
TOKEN="$(awk '/csrftoken/{print $7}' "$JAR")"
login="$(curl -sk -b "$JAR" -c "$JAR" -D - -o /dev/null -H "X-CSRFToken: $TOKEN" -H "Referer: $B/" \
  -H 'Content-Type: application/json' -d "{\"username\":\"uji_tls\",\"password\":\"$PW\"}" "$B/api/auth/login/")"
echo "$login" | head -1 | grep -q ' 200' || fail "login lewat HTTPS gagal: $(echo "$login" | head -1)"
echo "$login" | grep -i '^set-cookie: sessionid' | grep -qi 'secure' || fail "cookie sesi tidak Secure"
echo "$login" | grep -i '^set-cookie: sessionid' | grep -qi 'httponly' || fail "cookie sesi tidak HttpOnly"
ok "login lewat HTTPS berhasil; cookie sesi Secure dan HttpOnly"

docker run --rm --network host -v "$PWD/deployment/tls_flow.py:/tls_flow.py:ro" \
  -e TLS_BASE_URL="$B" -e TLS_USER=uji_tls -e TLS_PASSWORD="$PW" \
  social-media-snr-worker-browser python /tls_flow.py || fail "alur browser lewat HTTPS gagal (CSP/cookie)"

"${DC[@]}" exec -T web python manage.py check --deploy --fail-level WARNING >/dev/null || fail "check --deploy memberi peringatan"
ok "manage.py check --deploy bersih"
echo "UJI HTTPS LULUS"
