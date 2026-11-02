#!/usr/bin/env bash
# Instalator zbieracza ofert do aplikacji Zakupy. Można uruchamiać wielokrotnie (aktualizuje kod, zostawia klucz i adres).
# Uruchom jako root:  curl -fsSL https://raw.githubusercontent.com/lewym90/zakupy/main/server/deploy/install.sh | bash
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Uruchom jako root."; exit 1; }

REPO_TGZ="https://github.com/lewym90/zakupy/archive/refs/heads/main.tar.gz"
APP=/opt/zakupy-zbieracz
STATE=/var/lib/zakupy-zbieracz
OUT=/var/www/zakupy-data
ENVF=/etc/zakupy-zbieracz.env
USR=zakupy

echo "== 1/6 Pakiety systemowe"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv curl ca-certificates openssl >/dev/null

echo "== 2/6 Kod"
id "$USR" >/dev/null 2>&1 || useradd --system --home "$STATE" --shell /usr/sbin/nologin "$USR"
mkdir -p "$APP" "$STATE" "$OUT"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
curl -fsSL "$REPO_TGZ" | tar -xz -C "$tmp" --strip-components=2 zakupy-main/server
rm -rf "$APP/zbieracz"; cp -r "$tmp/zbieracz" "$APP/zbieracz"
chown -R "$USR:$USR" "$STATE" "$OUT"; chmod 755 "$OUT"

echo "== 3/6 Python i przeglądarka (to potrwa kilka minut)"
[ -d "$APP/venv" ] || python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --upgrade pip playwright
export PLAYWRIGHT_BROWSERS_PATH="$APP/browsers"
"$APP/venv/bin/playwright" install --with-deps chromium >/dev/null
chmod -R a+rX "$APP"

echo "== 4/6 Ustawienia"
if [ ! -f "$ENVF" ]; then
  TOKEN=$(openssl rand -hex 16)
  cat > "$ENVF" <<ENV
# Klucz Gemini wpisz po znaku =, zapisz, i gotowe. Bez cudzysłowów.
GEMINI_API_KEY=
# Tajny fragment adresu ofert. Nie udostępniaj.
TOKEN=$TOKEN
ZBIERACZ_OUT=$OUT
ZBIERACZ_STATE=$STATE
PLAYWRIGHT_BROWSERS_PATH=$APP/browsers
ENV
  chmod 640 "$ENVF"; chown root:"$USR" "$ENVF"
fi
TOKEN=$(grep '^TOKEN=' "$ENVF" | cut -d= -f2)

echo "== 5/6 Uruchamianie dwa razy dziennie"
cat > /etc/systemd/system/zakupy-zbieracz.service <<UNIT
[Unit]
Description=Zbieracz ofert (Zakupy)
After=network-online.target
[Service]
Type=oneshot
User=$USR
EnvironmentFile=$ENVF
ExecStart=$APP/venv/bin/python $APP/zbieracz/run.py
TimeoutStartSec=3h
Nice=10
UNIT
cat > /etc/systemd/system/zakupy-zbieracz.timer <<UNIT
[Unit]
Description=Zbieracz ofert - 2x dziennie
[Timer]
OnCalendar=*-*-* 05:20,17:40
RandomizedDelaySec=15min
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now zakupy-zbieracz.timer >/dev/null

echo "== 6/6 Adres dla aplikacji"
CADDYF=/etc/caddy/conf.d/zakupy.caddy
URL=""
if command -v caddy >/dev/null && [ -d /etc/caddy/conf.d ]; then
  [ -f "$CADDYF" ] && cp "$CADDYF" "$CADDYF.bak"
  cat > "$CADDYF" <<CADDY
# adres: <twoja-domena>/zakupy-oferty/$TOKEN/oferty.json
handle_path /zakupy-oferty/$TOKEN/* {
	root * $OUT
	header Access-Control-Allow-Origin *
	header Cache-Control "no-cache"
	file_server
}
CADDY
  if grep -Rqs "conf.d" /etc/caddy/Caddyfile && caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
    systemctl reload caddy && echo "Caddy przeładowany."
  else
    echo "UWAGA: Caddy nie przyjął konfiguracji - wycofuję zmianę."
    if [ -f "$CADDYF.bak" ]; then mv "$CADDYF.bak" "$CADDYF"; else rm -f "$CADDYF"; fi
  fi
  echo "Plik $CADDYF wymaga, by Twój blok z domeną miał 'import /etc/caddy/conf.d/*.caddy' w środku."
else
  echo "Nie widzę Caddy w /etc/caddy/conf.d - ścieżkę do $OUT trzeba wystawić ręcznie."
fi

echo
echo "Pierwszy odczyt uruchamiam w tle:  journalctl -u zakupy-zbieracz -f"
systemctl start --no-block zakupy-zbieracz.service
echo "GOTOWE. Klucz Gemini: nano $ENVF  (potem: systemctl restart zakupy-zbieracz)"
echo "Token adresu: $TOKEN"
