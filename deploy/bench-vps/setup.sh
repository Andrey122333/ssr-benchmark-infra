#!/bin/bash
# bench-vps/setup.sh
# Настройка выделенного сервера для нагрузочного тестирования (k6)
# Поддерживаемые ОС: Ubuntu 22.04 / 24.04, Debian 11 / 12
# Запуск: bash setup.sh

set -euo pipefail

# ── Цвета ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
RESET='\033[0m'

log()  { echo -e "${GREEN}[+]${RESET} $1"; }
warn() { echo -e "${YELLOW}[!]${RESET} $1"; }
die()  { echo -e "${RED}[✗]${RESET} $1" >&2; exit 1; }

# ── Конфигурация ─────────────────────────────────────────────────────────────
BENCH_USER="${BENCH_USER:-bench}"
BENCH_BASE_PATH="${BENCH_BASE_PATH:-/opt/bench}"
K6_SCRIPTS_PATH="${BENCH_BASE_PATH}/k6"
RESULTS_PATH="${BENCH_BASE_PATH}/results"

# ── Проверка окружения ────────────────────────────────────────────────────────
[[ "$(id -u)" -eq 0 ]] || die "Запустите скрипт с правами root: sudo bash setup.sh"

OS_ID=$(. /etc/os-release && echo "$ID")
OS_VER=$(. /etc/os-release && echo "$VERSION_ID")
log "Обнаружена ОС: ${OS_ID} ${OS_VER}"

[[ "$OS_ID" =~ ^(ubuntu|debian)$ ]] || die "Поддерживаются только Ubuntu и Debian"

# ── Системные зависимости ─────────────────────────────────────────────────────
log "Обновление пакетов..."
apt-get update -qq
apt-get install -y -qq \
  curl \
  gnupg \
  ca-certificates \
  lsb-release \
  jq \
  htop \
  sysstat \
  net-tools \
  > /dev/null

# ── Установка k6 ─────────────────────────────────────────────────────────────
log "Установка k6..."

K6_KEYRING="/usr/share/keyrings/k6-archive-keyring.gpg"

if ! gpg --no-default-keyring \
     --keyring "$K6_KEYRING" \
     --keyserver hkp://keyserver.ubuntu.com:80 \
     --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69 2>/dev/null; then
  warn "Основной keyserver недоступен, пробуем резервный..."
  gpg --no-default-keyring \
    --keyring "$K6_KEYRING" \
    --keyserver hkp://keys.openpgp.org:80 \
    --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
fi

echo "deb [signed-by=${K6_KEYRING}] https://dl.k6.io/deb stable main" \
  | tee /etc/apt/sources.list.d/k6.list > /dev/null

apt-get update -qq
apt-get install -y -qq k6 > /dev/null

K6_VERSION=$(k6 version | head -1)
log "Установлено: ${K6_VERSION}"

# ── Создание системного пользователя ─────────────────────────────────────────
if ! id "$BENCH_USER" &>/dev/null; then
  log "Создание пользователя: ${BENCH_USER}"
  useradd --system --create-home --shell /bin/bash "$BENCH_USER"
else
  warn "Пользователь ${BENCH_USER} уже существует, пропуск"
fi

# ── Создание директорий ───────────────────────────────────────────────────────
log "Создание рабочих директорий..."
mkdir -p "${K6_SCRIPTS_PATH}"
mkdir -p "${RESULTS_PATH}"

chown -R "${BENCH_USER}:${BENCH_USER}" "${BENCH_BASE_PATH}"
chmod 755 "${BENCH_BASE_PATH}"
chmod 755 "${K6_SCRIPTS_PATH}"
chmod 777 "${RESULTS_PATH}"   # CI-runner пишет результаты без su

# ── Настройка SSH-директории для пользователя ─────────────────────────────────
BENCH_HOME=$(getent passwd "$BENCH_USER" | cut -d: -f6)
mkdir -p "${BENCH_HOME}/.ssh"
chmod 700 "${BENCH_HOME}/.ssh"
touch "${BENCH_HOME}/.ssh/authorized_keys"
chmod 600 "${BENCH_HOME}/.ssh/authorized_keys"
chown -R "${BENCH_USER}:${BENCH_USER}" "${BENCH_HOME}/.ssh"

# ── Настройка лимитов для нагрузочного тестирования ──────────────────────────
log "Настройка системных лимитов..."

LIMITS_CONF="/etc/security/limits.d/bench.conf"
cat > "$LIMITS_CONF" << EOF
# Лимиты для нагрузочного тестирования k6
${BENCH_USER} soft nofile 65536
${BENCH_USER} hard nofile 65536
root         soft nofile 65536
root         hard nofile 65536
EOF

SYSCTL_CONF="/etc/sysctl.d/99-bench.conf"
cat > "$SYSCTL_CONF" << EOF
# Настройки сети для нагрузочного тестирования
net.ipv4.ip_local_port_range = 1024 65535
net.core.somaxconn = 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
net.core.netdev_max_backlog = 65536
EOF

sysctl -p "$SYSCTL_CONF" > /dev/null
log "Системные лимиты применены"

# ── Создание .env из .env.example ─────────────────────────────────────────────
ENV_EXAMPLE="$(dirname "$0")/.env.example"
ENV_FILE="${BENCH_BASE_PATH}/.env"

if [[ -f "$ENV_EXAMPLE" && ! -f "$ENV_FILE" ]]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  chown "${BENCH_USER}:${BENCH_USER}" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  log ".env создан из .env.example — заполните переменные"
elif [[ -f "$ENV_FILE" ]]; then
  warn ".env уже существует, пропуск"
fi

# ── Итог ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}══════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}  Bench-сервер настроен успешно${RESET}"
echo -e "${BOLD}══════════════════════════════════════════════════${RESET}"
echo ""
echo -e "  k6              : ${K6_VERSION}"
echo -e "  Пользователь    : ${BENCH_USER}"
echo -e "  Скрипты k6      : ${K6_SCRIPTS_PATH}"
echo -e "  Результаты      : ${RESULTS_PATH}"
echo -e "  Лимиты файлов   : 65536"
echo ""
echo -e "${YELLOW}Следующие шаги:${RESET}"
echo -e "  1. Добавьте публичный ключ CI в:"
echo -e "     ${BENCH_HOME}/.ssh/authorized_keys"
echo -e "  2. Заполните переменные в ${BENCH_BASE_PATH}/.env"
echo -e "  3. Проверьте доступность: ssh ${BENCH_USER}@<IP> 'k6 version'"
echo ""
