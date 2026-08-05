# ESF → AIOS SDK Convergence Design

**Дата:** 2026-08-05  
**Статус:** Approved  
**Область:** ESF как доменный модуль поверх AIOS Core API/SDK (ADR-0015)

---

## Контекст

AIOS Core ACCEPTED (13/13, main@529e019, 2026-08-05). Критический путь теперь — доменные модули поверх AIOS Core API/SDK/events.

ESF v1.1.6 — полностью feature-complete документарная платформа. Fitness-check CI уже зафиксирован (PR #18/#19): ни один файл ESF не может импортировать `aios.*` напрямую — только `aios_sdk`.

Сейчас ESF работает автономно: собственный auth (Argon2id + JWT), собственный audit-лог, собственный lifecycle документов. Цель — сделать ESF полным доменным модулем: Tasks + Memories + AIOS Identity.

---

## Решения

| Вопрос | Решение |
|---|---|
| Глубина интеграции | Полный доменный модуль (Tasks + Identity + Memories) |
| Поведение при недоступности AIOS | Конфиг-управляемый режим (`AIOS_ENABLED`) |
| Auth | AIOS-only: user-table удаляется, токены выпускает AIOS |

---

## Архитектура

```
ESF (domain module)
  │
  ├── Layer 1 — Tasks     → aios_sdk.TasksAPI
  ├── Layer 2 — Identity  → AIOS JWT validation middleware
  └── Layer 3 — Memories  → aios_sdk.MemoriesAPI
          │
          └──► AIOS Core HTTP API
```

**`AIOSBridgeService`** (`backend/app/core/aios_bridge.py`) — единственная точка входа в SDK внутри ESF. Ни роутеры, ни сервисы не импортируют `aios_sdk` напрямую. При `AIOS_ENABLED=false` — все методы no-op.

---

## Новая конфигурация

```
AIOS_ENABLED       bool   = False
AIOS_BASE_URL      str    = "http://localhost:8100"
AIOS_TOKEN         str    = ""      # service-account токен ESF в AIOS
AIOS_WORKSPACE_ID  str    = ""      # AIOS workspace для ESF
AIOS_TOKEN_FILE    str    = ""      # Docker secrets (аналог SECRET_KEY_FILE)
```

---

## Layer 1 — Tasks

### Маппинг lifecycle

| Переход ESF | Вызов SDK |
|---|---|
| `create_document` | `tasks.create(...)` → сохраняем `aios_task_id` |
| `DRAFT → VALIDATED` | `tasks.start(aios_task_id)` |
| `VALIDATED → SNAPSHOT_CREATED` | `tasks.escalate(aios_task_id)` |
| `SNAPSHOT_CREATED → PUBLISHED` | `tasks.complete(aios_task_id)` |

### Параметры задачи

```python
CreateTaskRequest(
    title=f"ESF-{document.reg_number or document.id}",
    description=f"ESF document lifecycle: {document.document_type}",
)
```

### Поведение при ошибке

Fire-and-forget: AIOS-ошибка логируется (`logger.warning`), ESF-операция не прерывается. Это временная мягкость — в Layer 2 AIOS становится обязательным.

### Изменения кода

- `backend/requirements.txt` + `requirements.lock` — добавить `aios-sdk` (пакет из `~/Projects/aios`, editable install или wheel)
- `backend/app/core/aios_bridge.py` — новый, `AIOSBridgeService`
- `backend/app/core/config.py` — 5 новых полей
- `backend/app/services/esf_service.py` — вызовы bridge в lifecycle-методах
- `backend/app/models/esf_document.py` — новая колонка `aios_task_id`
- Alembic-миграция: `aios_task_id VARCHAR(255) NULL` в `esf_documents`

### Тесты Layer 1

- `AIOSBridgeService` мокируется через pytest fixture
- Task создаётся при создании документа
- Lifecycle-переходы вызывают правильные SDK-методы
- AIOS-ошибка не прерывает ESF-операцию

---

## Layer 2 — Identity

**Активируется:** `AIOS_ENABLED=true` — жёсткое требование, AIOS обязателен.

### Удаляется

- `POST /auth/token` (роутер `auth.py` или полностью, или сведён к 404)
- `backend/app/core/passwords.py` — Argon2id хешер
- `backend/app/core/jwt.py` — генерация токенов (остаётся только валидация)
- `backend/app/repositories/user_repository.py`
- `backend/app/models/user.py`
- Alembic-миграция: `DROP TABLE users` (обратимая)

### Добавляется

`AIOSBridgeService.verify_token(token: str) → AIOSIdentity`

```python
@dataclass
class AIOSIdentity:
    principal: str       # aios identity id
    tenant_id: str
    roles: list[str]     # маппятся на ESF RBAC: admin/operator/viewer
```

Реализация: вызов AIOS `/api/v1/auth/validate` или проверка подписи JWT публичным ключом AIOS (уточняется при реализации по актуальному API).

`app/core/security.py`: `get_current_user` → `get_current_identity`, возвращает `AIOSIdentity`. Все роутеры получают `identity` вместо `user`.

### Dev-доступ

```bash
aios auth issue --tenant esf-prod --principal admin --role admin
```

Документируется в `README.md`. `admin/admin123` удаляется.

### Тесты Layer 2

- Auth с mock AIOS token-validator
- `POST /auth/token` → 404
- Маппинг ролей AIOS → ESF RBAC

---

## Layer 3 — Memories

### Что пишется

Только опубликованные снапшоты (`PUBLISHED`). Промежуточные состояния не пишутся.

### Вызов

```python
aios.memories.create_in_workspace(
    workspace_id=AIOS_WORKSPACE_ID,
    request=CreateMemoryRequest(
        kind="esf_snapshot",
        content=snapshot.snapshot_data,
        status="active",
    ),
    idempotency_key=str(snapshot.id),    # UUID снапшота
)
```

`snapshot.id` как `Idempotency-Key` — гарантирует ровно одну запись при retry.

### Источник истины

`ESFSnapshot` в Postgres — canonical. AIOS Memory — аудит-копия, кросс-доменно доступная AML, Golden Record. ESF не читает из AIOS Memories.

### Новая колонка

`aios_memory_id VARCHAR(255) NULL` в `esf_snapshots` — хранит ID записи AIOS для трассировки.

### Тесты Layer 3

- Два вызова publish → один `aios_memory_id` (идемпотентность)
- AIOS-ошибка не откатывает публикацию в ESF

---

## Таблица изменений

| Слой | Ветка | Новые файлы | Удаляемые файлы | Миграции |
|---|---|---|---|---|
| Tasks | `feat/aios-tasks` | `aios_bridge.py` | — | `aios_task_id` в `esf_documents` |
| Identity | `feat/aios-identity` | — | `passwords.py`, `user.py`, `user_repository.py` | DROP TABLE users |
| Memories | `feat/aios-memories` | — | — | `aios_memory_id` в `esf_snapshots` |

---

## Порядок деплоя

```
1. Layer 1 + AIOS_ENABLED=false → ESF работает как раньше
2. Поднять AIOS рядом с ESF
   aios workspace create esf-prod
   aios auth issue --principal esf-svc → AIOS_TOKEN
3. AIOS_ENABLED=true → Tasks начинают записываться
4. Layer 2 → провизионировать пользователей через aios auth issue
5. Layer 3 → новые публикации пишутся в AIOS Memories
```

---

## Вне скоупа

- Backfill существующих документов в AIOS Tasks/Memories — отдельный скрипт после Layer 3
- Outbox-паттерн для гарантированной доставки
- Чтение данных ESF из AIOS (ESF остаётся canonical)
- Миграция данных AIOS при смене схемы
