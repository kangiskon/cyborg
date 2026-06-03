#!/usr/bin/env bash

set -Eeuo pipefail

APP_NAME="frontkind-ai-receptionist"
APP_USER="frontkind"
APP_GROUP="frontkind"
INSTALL_DIR="/opt/${APP_NAME}"
BACKEND_PORT="8001"
FRONTEND_PORT="3000"
NGINX_SITE="/etc/nginx/sites-available/${APP_NAME}"
NGINX_SITE_LINK="/etc/nginx/sites-enabled/${APP_NAME}"
BACKEND_ENV_FILE="/etc/${APP_NAME}/backend.env"
FRONTEND_ENV_FILE="/etc/${APP_NAME}/frontend.env"
MONGO_DB_NAME="ai_receptionist"
NODE_MAJOR="20"
MONGODB_MAJOR="8.0"

print_step() {
  printf '\n\033[1;32m==> %s\033[0m\n' "$1"
}

print_warn() {
  printf '\n\033[1;33mWARN: %s\033[0m\n' "$1"
}

print_error() {
  printf '\n\033[1;31mERROR: %s\033[0m\n' "$1" >&2
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    print_error "Run this installer with sudo: sudo bash install_ubuntu_24_04.sh"
    exit 1
  fi
}

require_ubuntu_2404() {
  if [[ ! -f /etc/os-release ]]; then
    print_error "Cannot detect operating system. Ubuntu 24.04 is required."
    exit 1
  fi
  # shellcheck disable=SC1091
  source /etc/os-release
  if [[ "${ID:-}" != "ubuntu" || "${VERSION_ID:-}" != "24.04" ]]; then
    print_error "This installer targets Ubuntu 24.04. Detected: ${PRETTY_NAME:-unknown}."
    exit 1
  fi
}

require_app_source() {
  if [[ ! -d "backend" || ! -d "frontend" ]]; then
    print_error "Run this script from the app root containing backend/ and frontend/."
    exit 1
  fi
}

prompt_secret() {
  local label="$1"
  local variable_name="$2"
  local value=""
  while [[ -z "${value}" ]]; do
    read -r -s -p "${label}: " value
    printf '\n'
    if [[ -z "${value}" ]]; then
      print_warn "${label} cannot be empty."
    fi
  done
  printf -v "${variable_name}" '%s' "${value}"
}

prompt_value() {
  local label="$1"
  local variable_name="$2"
  local default_value="$3"
  local value=""
  read -r -p "${label} [${default_value}]: " value
  value="${value:-${default_value}}"
  printf -v "${variable_name}" '%s' "${value}"
}

generate_secret() {
  openssl rand -hex 32
}

install_system_packages() {
  print_step "Installing system packages"
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    nginx \
    openssl \
    python3 \
    python3-pip \
    python3-venv \
    rsync \
    ufw
}

install_node() {
  print_step "Installing Node.js ${NODE_MAJOR} and Yarn"
  if ! command -v node >/dev/null 2>&1 || ! node --version | grep -q "^v${NODE_MAJOR}\."; then
    curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
    DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
  fi
  if ! command -v yarn >/dev/null 2>&1; then
    npm install -g yarn
  fi
}

install_mongodb() {
  print_step "Installing MongoDB ${MONGODB_MAJOR} locally"
  if ! command -v mongod >/dev/null 2>&1; then
    curl -fsSL "https://www.mongodb.org/static/pgp/server-${MONGODB_MAJOR}.asc" | gpg --dearmor -o "/usr/share/keyrings/mongodb-server-${MONGODB_MAJOR}.gpg"
    echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-${MONGODB_MAJOR}.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/${MONGODB_MAJOR} multiverse" > "/etc/apt/sources.list.d/mongodb-org-${MONGODB_MAJOR}.list"
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y mongodb-org
  fi
  systemctl enable mongod
  systemctl restart mongod
}

create_app_user() {
  print_step "Creating application user"
  if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    useradd --system --create-home --shell /usr/sbin/nologin "${APP_USER}"
  fi
}

copy_application() {
  print_step "Copying application to ${INSTALL_DIR}"
  mkdir -p "${INSTALL_DIR}"
  rsync -a --delete \
    --exclude ".git" \
    --exclude "backend/venv" \
    --exclude "frontend/node_modules" \
    --exclude "frontend/build" \
    --exclude "*.pyc" \
    --exclude "__pycache__" \
    ./ "${INSTALL_DIR}/"
  chown -R "${APP_USER}:${APP_GROUP}" "${INSTALL_DIR}"
}

write_environment_files() {
  print_step "Configuring environment values"
  mkdir -p "/etc/${APP_NAME}"

  local default_public_url="http://$(hostname -I | awk '{print $1}')"
  local public_url=""
  local emergent_llm_key=""
  local admin_code=""
  local staff_code=""
  local viewer_code=""
  local staff_secret=""

  prompt_value "Public app URL or server IP URL" public_url "${default_public_url}"
  prompt_secret "Emergent LLM key for GPT responses" emergent_llm_key
  prompt_value "Admin staff access code" admin_code "FK-ADMIN-$(openssl rand -hex 3 | tr '[:lower:]' '[:upper:]')"
  prompt_value "Staff access code" staff_code "FK-STAFF-$(openssl rand -hex 3 | tr '[:lower:]' '[:upper:]')"
  prompt_value "Viewer access code" viewer_code "FK-VIEW-$(openssl rand -hex 3 | tr '[:lower:]' '[:upper:]')"
  staff_secret="$(generate_secret)"

  cat > "${BACKEND_ENV_FILE}" <<EOF
MONGO_URL="mongodb://127.0.0.1:27017"
DB_NAME="${MONGO_DB_NAME}"
CORS_ORIGINS="${public_url}"
EMERGENT_LLM_KEY="${emergent_llm_key}"
STAFF_AUTH_SECRET="${staff_secret}"
STAFF_ADMIN_ACCESS_CODE="${admin_code}"
STAFF_STAFF_ACCESS_CODE="${staff_code}"
STAFF_VIEWER_ACCESS_CODE="${viewer_code}"
EOF

  cat > "${FRONTEND_ENV_FILE}" <<EOF
REACT_APP_BACKEND_URL="${public_url}"
EOF

  cp "${BACKEND_ENV_FILE}" "${INSTALL_DIR}/backend/.env"
  cp "${FRONTEND_ENV_FILE}" "${INSTALL_DIR}/frontend/.env"
  chown -R "${APP_USER}:${APP_GROUP}" "/etc/${APP_NAME}" "${INSTALL_DIR}/backend/.env" "${INSTALL_DIR}/frontend/.env"
  chmod 600 "${BACKEND_ENV_FILE}" "${FRONTEND_ENV_FILE}" "${INSTALL_DIR}/backend/.env" "${INSTALL_DIR}/frontend/.env"

  print_step "Staff access codes"
  printf 'Admin:  %s\n' "${admin_code}"
  printf 'Staff:  %s\n' "${staff_code}"
  printf 'Viewer: %s\n' "${viewer_code}"
  printf 'Save these codes somewhere secure.\n'
}

install_backend() {
  print_step "Installing backend Python dependencies"
  cd "${INSTALL_DIR}/backend"
  python3 -m venv venv
  "${INSTALL_DIR}/backend/venv/bin/pip" install --upgrade pip
  "${INSTALL_DIR}/backend/venv/bin/pip" install -r requirements.txt
  chown -R "${APP_USER}:${APP_GROUP}" "${INSTALL_DIR}/backend"
}

build_frontend() {
  print_step "Installing and building frontend"
  cd "${INSTALL_DIR}/frontend"
  sudo -u "${APP_USER}" yarn install --frozen-lockfile
  sudo -u "${APP_USER}" yarn build
}

write_systemd_services() {
  print_step "Creating systemd services"
  cat > "/etc/systemd/system/${APP_NAME}-backend.service" <<EOF
[Unit]
Description=Frontkind AI Receptionist Backend
After=network.target mongod.service
Requires=mongod.service

[Service]
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${INSTALL_DIR}/backend
EnvironmentFile=${BACKEND_ENV_FILE}
ExecStart=${INSTALL_DIR}/backend/venv/bin/uvicorn server:app --host 127.0.0.1 --port ${BACKEND_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable "${APP_NAME}-backend.service"
  systemctl restart "${APP_NAME}-backend.service"
}

configure_nginx() {
  print_step "Configuring Nginx"
  cat > "${NGINX_SITE}" <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    root ${INSTALL_DIR}/frontend/build;
    index index.html;

    client_max_body_size 20m;

    location /api/ {
        proxy_pass http://127.0.0.1:${BACKEND_PORT}/api/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        try_files \$uri /index.html;
    }
}
EOF

  rm -f /etc/nginx/sites-enabled/default
  ln -sf "${NGINX_SITE}" "${NGINX_SITE_LINK}"
  nginx -t
  systemctl enable nginx
  systemctl reload nginx
}

configure_firewall() {
  print_step "Configuring firewall"
  ufw allow OpenSSH >/dev/null || true
  ufw allow 'Nginx Full' >/dev/null || true
  if ufw status | grep -q inactive; then
    print_warn "UFW is installed but inactive. Enable it later with: sudo ufw enable"
  fi
}

print_summary() {
  local server_ip
  server_ip="$(hostname -I | awk '{print $1}')"
  print_step "Installation complete"
  printf 'App URL:      http://%s\n' "${server_ip}"
  printf 'Backend:      systemctl status %s-backend\n' "${APP_NAME}"
  printf 'Nginx:        systemctl status nginx\n'
  printf 'MongoDB:      systemctl status mongod\n'
  printf '\nTo configure a domain later, update:\n'
  printf '  %s\n' "${NGINX_SITE}"
  printf '  %s\n' "${FRONTEND_ENV_FILE}"
  printf '  %s\n' "${BACKEND_ENV_FILE}"
  printf '\nThen rebuild frontend and reload services.\n'
}

main() {
  require_root
  require_ubuntu_2404
  require_app_source
  install_system_packages
  install_node
  install_mongodb
  create_app_user
  copy_application
  write_environment_files
  install_backend
  build_frontend
  write_systemd_services
  configure_nginx
  configure_firewall
  print_summary
}

main "$@"
