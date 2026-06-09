# SSR Benchmark Infra

Инфраструктурный репозиторий для развёртывания, переключения и тестирования экспериментального стенда сравнительного анализа SSR-фреймворков Next.js, Nuxt и SvelteKit. Репозиторий отделяет инфраструктуру и автоматизацию развёртывания от репозиториев приложений, что соответствует практике разделения build-артефактов и средовых настроек по разным уровням CI/CD.[1][2]

## Назначение

Репозиторий используется для управления изолированными VPS-серверами, на которых размещаются тестовые веб-приложения типов `landing` и `catalog` для трёх SSR-фреймворков. Такая схема соответствует целям воспроизводимого деплоя и независимого сравнения производительности в одинаковых условиях.[3][4]

Основные задачи репозитория:
- хранение `docker compose` конфигураций для `next-vps`, `nuxt-vps` и `svelte-vps`;
- автоматизация деплоя по SSH через GitHub Actions;
- переключение активного сервиса (`landing` / `catalog`) перед benchmark-прогонами;
- запуск Lighthouse smoke-проверок и нагрузочных сценариев k6.[5][4][6][7]

## Структура

```text
ssr-benchmark-infra/
  deploy/
    next-vps/
      compose.yaml
      .env.example
    nuxt-vps/
      compose.yaml
      .env.example
    svelte-vps/
      compose.yaml
      .env.example
  scripts/
    deploy.py
    switch_service.py
    healthcheck.py
  lighthouse/
    configs/
      landing/
        lighthouserc.json
      catalog/
        lighthouserc.json
  k6/
    landing.js
    catalog.js
  .github/
    workflows/
      deploy.yml
      lighthouse-smoke.yml
      benchmark.yml
  docs/
    ARCHITECTURE.md
    DEPLOY.md
    BENCHMARK.md
```

## Компоненты

| Компонент | Назначение |
|---|---|
| `deploy/*/compose.yaml` | Описание стеков конкретных VPS с двумя сервисами одного фреймворка.[3] |
| `scripts/deploy.py` | Удалённый деплой через SSH, логин в GHCR, `docker compose pull` и `up -d`.[4][5] |
| `scripts/switch_service.py` | Переключение между `landing` и `catalog` на одном VPS через `docker compose up/stop`.[8][9] |
| `scripts/healthcheck.py` | Проверка готовности HTTP-сервиса перед Lighthouse и k6.[4] |
| `lighthouse/configs/*` | Конфиги Lighthouse CI для разных типов приложений.[10][11] |
| `k6/*.js` | Сценарии baseline и stress-нагрузки на базе arrival-rate executor'ов.[12][13] |
| `.github/workflows/*` | GitHub Actions для деплоя и benchmark-пайплайнов.[14][1] |

## Окружения GitHub

Для репозитория рекомендуется создать GitHub Environments `next-production`, `nuxt-production` и `svelte-production`. GitHub Environments позволяют изолированно хранить secrets и variables для разных deployment targets и использовать их прямо в workflow через поле `environment`.[1][15]

### Рекомендуемые secrets

- `SSH_HOST`
- `SSH_PORT`
- `SSH_USER`
- `GHCR_TOKEN`

### Рекомендуемые variables

- `DEPLOY_PATH`
- `GHCR_USERNAME`

## Базовый сценарий работы

1. Приложение в app-repo собирает Docker-образ и публикует его в GHCR через GitHub Actions.[16][17]
2. В `ssr-benchmark-infra` вручную запускается `deploy.yml` с указанием `target`, `service` и `tag`.[14][1]
3. Скрипт `deploy.py` копирует `compose.yaml` и `.env` на VPS, логинится в GHCR и выполняет `docker compose pull && docker compose up -d`.[4][5]
4. Затем `healthcheck.py` подтверждает доступность URL сервиса перед измерениями.[4]
5. После этого запускаются `lighthouse-smoke.yml` или `benchmark.yml` для метрик Lighthouse и нагрузочного тестирования k6.[6][7][18]

## Требования

- GitHub repository с включёнными Actions и настроенными Environments.[1][14]
- Три VPS для размещения Next.js, Nuxt и SvelteKit, плюс отдельный сервер для генерации нагрузки и телеметрии — именно такая схема лучше обеспечивает изоляцию и воспроизводимость измерений.[3][4]
- Docker Engine и Docker Compose plugin на каждом VPS, поскольку удалённый деплой выполняется через команды `docker compose` по SSH.[3][19]
- Доступ к GHCR для получения Docker-образов; GHCR работает как обычный container registry и поддерживается Docker client и Compose.[17][20]

## Документация

Подробности вынесены в отдельные документы:
- [ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- [DEPLOY.md](./docs/DEPLOY.md)
- [BENCHMARK.md](./docs/BENCHMARK.md)
