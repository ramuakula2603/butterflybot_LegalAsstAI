#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/venv"
ENV_FILE="$ROOT_DIR/.env"
ENV_EXAMPLE="$ROOT_DIR/.env.example"

APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-8001}"

usage() {
  cat <<'EOF'
Usage: ./deploy/deploy.sh [--with-systemd] [--with-nginx]

What this script does:
  1) Creates/uses local Python venv
  2) Installs requirements
  3) Bootstraps .env from .env.example (first run only)
  4) Starts or restarts butterflybot.service if --with-systemd is passed

Flags:
  --with-systemd   Install/update systemd unit from deploy/systemd template and restart service
  --with-nginx     Install/update nginx site config from deploy/nginx template and reload nginx

Environment overrides:
  APP_HOST=<host>  (default: 127.0.0.1)
  APP_PORT=<port>  (default: 8001)

Examples:
  ./deploy/deploy.sh
  ./deploy/deploy.sh --with-systemd
  APP_PORT=9000 ./deploy/deploy.sh --with-systemd --with-nginx
EOF
}

WITH_SYSTEMD=false
WITH_NGINX=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-systemd)
      WITH_SYSTEMD=true
      shift
      ;;
    --with-nginx)
      WITH_NGINX=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

echo "[1/5] Preparing virtual environment"
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "[2/5] Installing dependencies"
pip install --upgrade pip
pip install -r "$ROOT_DIR/requirements.txt"

echo "[3/5] Preparing environment file"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  echo "Created .env from .env.example. Update secrets before production use."
fi

if [[ "$WITH_SYSTEMD" == true ]]; then
  echo "[4/5] Installing/updating systemd service"
  sudo cp "$ROOT_DIR/deploy/systemd/butterflybot.service" /etc/systemd/system/butterflybot.service
  sudo systemctl daemon-reload
  sudo systemctl enable butterflybot
  sudo systemctl restart butterflybot
  sudo systemctl status butterflybot --no-pager
else
  echo "[4/5] Skipping systemd install"
fi

if [[ "$WITH_NGINX" == true ]]; then
  echo "[5/5] Installing/updating nginx config"
  sudo cp "$ROOT_DIR/deploy/nginx/butterflybot.conf" /etc/nginx/sites-available/butterflybot.conf
  sudo ln -sf /etc/nginx/sites-available/butterflybot.conf /etc/nginx/sites-enabled/butterflybot.conf
  sudo nginx -t
  sudo systemctl reload nginx
else
  echo "[5/5] Skipping nginx install"
fi

if [[ "$WITH_SYSTEMD" == false ]]; then
  echo
  echo "Manual run command:"
  echo "  source venv/bin/activate && uvicorn main:app --host $APP_HOST --port $APP_PORT"
fi

echo "Deployment helper completed."
