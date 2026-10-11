# 🤖 MAX-бот «IT-служба колледжа»

Бот мессенджера **MAX** для приема и сопровождения заявок в техническую поддержку колледжа.
Выполняет роль **тонкого клиента**: принимает вебхуки MAX, ведет диалоги с пользователями
и всю бизнес-логику (баллы, лимиты, статусы) делегирует **Core API**.

> База знаний по MAX API: <https://dev.max.ru/docs>

---

## 1. Архитектура

```text
┌──────────┐   webhook POST    ┌─────────────────────────┐   REST (httpx)   ┌────────────┐
│   MAX    │ ────────────────► │  max_bot (этот проект)  │ ───────────────► │ Core API   │
│ (мессенджер)│ ◄────────────── │  aiohttp + aiogram 3.x  │ ◄─────────────── │ (бизнес-   │
└──────────┘   /v3/messages    │  FSM-states ──► Redis   │                  │  логика)   │
                               └─────────────────────────┘                  └────────────┘
                                          ▲
                               polling    │  (фон, опционально)
                          ┌───────────────┴──────────────┐
                          │ notification_worker.py       │
                          └──────────────────────────────┘
```

**Принципы:**
* Бот **не содержит** бизнес-логики: проверка лимитов, списание баллов, валидация статусов — на стороне Core API.
* Все запросы к Core API идут только через `max_bot/core/api_client.py`.
* Состояния многошаговых диалогов (FSM) хранятся в **Redis**.
* Логирование всех действий — через `middlewares/logging_middleware.py` (structlog/formatting).

### Структура проекта

```text
.
├── Dockerfile                   # образ бота (python:3.11-slim)
├── docker-compose.yml           # redis + bot + notification-worker
└── max_bot/
    ├── main.py                  # точка входа: aiohttp webhook-сервер (POST /webhook/max)
    ├── bot.py                   # адаптер MAX поверх aiogram (MaxSession → REST MAX)
    ├── mappers.py               # конвертация payload'а MAX ↔ типы aiogram
    ├── notification_worker.py   # фоновый воркер уведомлений (Вариант 1 из ТЗ)
    ├── requirements.txt
    ├── .env.example
    ├── core/
    │   ├── config.py            # pydantic-settings: токен MAX, URL/ключ Core API, Redis
    │   ├── api_client.py        # httpx-клиент Core API + исключение CoreApiError
    │   └── redis_client.py      # подключение Redis (RedisStorage для FSM)
    ├── handlers/
    │   ├── start.py             # старт, /help, главное меню, синхронизация профиля
    │   ├── tickets.py           # создание (FSM), список, детали, сообщения, отмена/закрытие
    │   ├── profile.py           # профиль, баланс баллов, рейтинг
    │   ├── callbacks.py         # fallback для неизвестных кнопок
    │   └── errors.py            # глобальный обработчик ошибок (402/429/403/5xx)
    ├── states/ticket_states.py  # состояния диалога создания заявки
    ├── keyboards/               # inline-клавиатуры (главное меню, тикеты, подтверждения)
    ├── services/
    │   ├── message_formatter.py # шаблоны текстов сообщений
    │   └── notification_sender.py # логика доставки уведомлений
    ├── middlewares/logging_middleware.py
    └── utils/helpers.py
```

---

## 2. Требования

* Python **3.11+**
* Redis **7.x** (для FSM)
* Доступный Core API колледжа
* Зарегистрированный бот в панели разработчика MAX (токен)
* Публичный **HTTPS** URL для вебхуков (nginx/traefik + сертификат; MAX не отправляет вебхуки на HTTP)
* Docker + Docker Compose v2 (для контейнерного запуска; команда `docker compose version`)

---

## 3. Быстрый старт (без Docker)

```bash
# 1. Клонировать репозиторий
git clone <repo-url> && cd server_bot_it

# 2. Виртуальное окружение + зависимости
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r max_bot/requirements.txt

# 3. Конфигурация
cp max_bot/.env.example max_bot/.env
# откройте max_bot/.env и заполните MAX_BOT_TOKEN, CORE_API_URL, CORE_API_KEY,
# WEBHOOK_URL, SECRET_TOKEN, REDIS_URL

# 4. Локальный Redis (если нет)
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 5. Запуск webhook-сервера (слушает 0.0.0.0:8080)
python -m max_bot.main

# 6. (Опционально) фоновые уведомления — отдельным процессом
python -m max_bot.notification_worker
```

Local smoke-test без MAX:

```bash
curl http://localhost:8080/healthz                 # {"status": "ok"}
curl -X POST http://localhost:8080/webhook/max \
     -H 'Content-Type: application/json' \
     -H 'X-Max-Webhook-Secret: <SECRET_TOKEN>' \
     -d '{"update_type":"message_new","body":{"message":{"sender":{"user_id":123,"type":"user"},"text":"/start","created_at":1}}}'
```

---

## 4. Запуск в Docker Compose

Файл `docker-compose.yml` описывает три сервиса:

| Сервис | Назначение | Порт |
|---|---|---|
| `redis` | Хранилище состояний FSM (AOF-персистентность, volume `redis_data`) | 6379 |
| `bot` | Webhook-сервер бота (aiohttp + aiogram Dispatcher) | 8080 |
| `notification-worker` | Фоновый опрос Core API и доставка уведомлений в MAX | — |

```bash
# 1. Конфигурация обязательна
cp max_bot/.env.example max_bot/.env && nano max_bot/.env

# 2. Сборка и запуск
docker compose up -d --build

# 3. Наблюдение
docker compose ps
docker compose logs -f bot
docker compose logs -f notification-worker

# 4. Остановка / полная очистка
docker compose down            # остановить
docker compose down -v         # + удалить volume Redis (сброс FSM-состояний)
```

Переменные из `.env` подхватываются сервисами через `env_file`; адреса внутри сети
compose переопределены: `REDIS_URL=redis://redis:6379/0`,
`CORE_API_URL=${CORE_API_URL:-http://core-api:8000}` (если Core API поднят в той же
сети — подключите его к `max_bot_net`, иначе укажите внешний URL).

> ⚠️ Примечание о версии: директива `version:` в верхнем уровне файла Compose
> **устарела** согласно Compose Specification — актуальные Docker Compose v2+
> определяют версию самостоятельно (`docker compose version`). Поэтому в файле
> используется современный формат без `version:` (это корректно и для v2.5+,
> и для CLI-сборок вида «v5.x»).

### TLS / reverse-proxy

MAX доставляет вебхуки только по HTTPS. Поднимите nginx (пример закомментирован
в `docker-compose.yml`) или Traefik/Caddy, который проксирует `443 → bot:8080`
и добавляет HSTS. Путь вебхука: `/webhook/max`.

---

## 5. Переменные окружения (`.env`)

| Переменная | Пример | Описание |
|---|---|---|
| `MAX_BOT_TOKEN` | `xxxx` | Токен бота из панели MAX (заголовок `Authorization: token …`) |
| `MAX_API_URL` | `https://maxapi.ru/v3` | Базовый URL REST-API MAX |
| `MAX_WEBHOOK_PATH` | `/webhook/max` | Путь эндпоинта приема вебхуков |
| `WEBHOOK_URL` | `https://bot.college.ru/webhook/max` | Публичный HTTPS URL для саморегистрации вебхука |
| `SECRET_TOKEN` | `random-string` | Проверка заголовка `X-Max-Webhook-Secret` |
| `CORE_API_URL` | `http://core-api:8000` | Адрес Core API |
| `CORE_API_KEY` | `key` | Заголовок `X-API-Key` для Core API |
| `CORE_API_TIMEOUT` | `15.0` | Таймаут HTTP-запросов, сек |
| `REDIS_URL` | `redis://redis:6379/0` | Подключение к Redis (FSM) |
| `HOST` / `PORT` | `0.0.0.0` / `8080` | Адрес webhook-сервера |
| `ENVIRONMENT` | `production` | Режим (влияет на формат логов) |
| `LOG_LEVEL` | `INFO` | Уровень логирования |

---

## 6. Команды и сценарии бота

### Команды
| Команда | Действие |
|---|---|
| Старт / `menu` | Главное меню + синхронизация профиля с Core API |
| `help` / кнопка ℹ️ | Список возможностей и инструкция |

### Главное меню (inline-кнопки)
| Кнопка | callback_data | Что происходит |
|---|---|---|
| 🆕 Создать заявку | `ticket_create` | Запускает многошаговый FSM-диалог |
| 📋 Мои заявки | `ticket_list` | `GET /api/v1/tickets?status=active` + клавиатура |
| 👤 Профиль и баланс | `profile` | `GET /api/v1/users/{id}/profile` (рейтинг, баллы) |
| ℹ️ Помощь | `help` | Текст справки |

### Создание заявки (FSM, состояния в Redis)
1. `WAITING_FOR_TYPE` — выбор типа (`GET /api/v1/references/ticket-types`)
2. `WAITING_FOR_ADDRESS` — выбор корпуса (`GET /api/v1/references/addresses`)
3. `WAITING_FOR_CABINET` — номер кабинета (или «Пропустить»)
4. `WAITING_FOR_TITLE` — тема заявки (текстом)
5. `WAITING_FOR_DESCRIPTION` — описание (текстом)
6. `WAITING_FOR_CONFIRMATION` — карточка-превью + кнопки ✅/❌
   * `confirm_yes` → `POST /api/v1/tickets`; при успехе — номер заявки и новый баланс;
     при `insufficient_points` — сообщение о недостатке баллов
   * `confirm_no` → сброс диалога

### Управление заявками
* **Список тикетов**: активные / все / закрытые (фильтр-кнопки).
* **Детали тикета**: `ticket_<id>` — статус, исполнитель, история.
* ➕ **Добавить сообщение**: FSM-шаг ввода текста → `POST /api/v1/tickets/<id>/messages`.
* ❌ **Отменить заявку** / 🔒 **Закрыть** — доступны только если разрешает статус
  (решение принимает Core API; бот показывает его ответ).

### Синхронизация профиля
При первом взаимодействии (Старт/`user_joined`):
1. `GET /v3/users/{user_id}` — данные из MAX;
2. `PUT /api/v1/users/{max_user_id}/profile` — upsert в Core API
   (first_name, name, username, raw_profile).

---

## 7. Обработка ошибок

Все сетевые сбои Core API конвертируются в `CoreApiError(status_code, detail)`
(см. `core/api_client.py`) и перехватываются глобальным обработчиком
(`handlers/errors.py`):

| Код | Ситуация | Ответ пользователю |
|---|---|---|
| `402` | Недостаточно баллов | ❌ Недостаточно баллов для выполнения действия |
| `429` | Превышен лимит заявок | ⏳ Превышен лимит. Попробуйте позже |
| `403` | Пользователь заблокирован | 🚫 Вы заблокированы. Обратитесь в поддержку |
| `5xx/иное` | Сбой Core API | ❌ Произошла ошибка. Попробуйте позже (+ запись в лог) |

Неизвестные `callback_data` обрабатываются fallback-роутером (`handlers/callbacks.py`)
— пользователю показывается актуальное главное меню вместо «зависшей» кнопки.

---

## 8. Уведомления (опционально)

Реализован **Вариант 1** из ТЗ — периодический опрос:

```text
notification_worker.py (каждые 10 c):
  GET /api/v1/notifications/pending  →  POST /v3/messages (MAX)  →
  POST /api/v1/notifications/{id}/sent | /failed
```

Запускается как отдельный контейнер `notification-worker` в compose либо вручную:
`python -m max_bot.notification_worker`. Корректно останавливается по SIGTERM
(`docker compose stop`).

**Вариант 2** (push от Core API на `/webhook/notification`) может быть добавлен
в `main.py` как второй роут aiohttp — инфраструктура для этого уже готова.

---

## 9. Интеграция с MAX: что настроить в панели

1. Создать бот в панели разработчика MAX, получить токен → `MAX_BOT_TOKEN`.
2. Указать URL вебхука: `https://<ваш-домен>/webhook/max` и секрет → `SECRET_TOKEN`.
   (Бот попытается зарегистрировать вебхук сам при наличии `WEBHOOK_URL`.)
3. Обрабатываемые события: `message_new`, `message_callback`, `user_joined`.

Формат исходящей кнопки (как в ТЗ):

```json
{
  "user_id": 123456,
  "text": "Выберите действие:",
  "inline_keyboard": [[
    {"text": "🆕 Создать заявку", "callback_data": "ticket_create"},
    {"text": "📋 Мои заявки",     "callback_data": "ticket_list"}
  ]]
}
```

---

## 10. Чек-лист приемки (Definition of Done)

- [x] Бот принимает вебхуки от MAX (`POST /webhook/max`, проверка секрета)
- [x] Создание тикета через многошаговый диалог (FSM, 6 шагов + подтверждение)
- [x] Просмотр списка и деталей своих тикетов
- [x] Добавление сообщения в тикет, отмена/закрытие
- [x] Все запросы к Core API — только через `core/api_client.py`
- [x] Обработаны ошибки API: 402, 429, 403, 5xx (глобальный error-handler)
- [x] Состояния диалогов хранятся в Redis (`RedisStorage`)
- [x] Логирование всех действий (middleware + structlog-friendly)
- [x] Docker Compose: redis + bot + notification-worker
- [x] README, `.env.example`, `requirements.txt`

---

## 11. Разработка

```bash
# Линт (опционально)
pip install ruff && ruff check max_bot

# Тестовый прогон без реального MAX: поднимите redis и отправьте
# фейковый вебхук через curl (см. раздел 3, Local smoke-test)
```

Полезные команды Docker:

```bash
docker compose build bot                 # пересобрать образ после изменений кода
docker compose up -d --force-recreate bot
docker compose exec bot python -c "import max_bot.main"   # проверка импортов
docker volume rm server_bot_it_redis_data                 # сброс FSM-состояний
```
