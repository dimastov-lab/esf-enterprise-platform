# AML Governance Platform — DATA-1 Design

**Дата:** 2026-08-05  
**Продукт:** AML Governance Platform (новое standalone-приложение)  
**Мера:** DATA-1 — учёт исходов алертов транзакционного мониторинга  
**Основание:** AML Audit 2 — мультиагентный 2026, находка F25 (Critical-корень)  
**Статус:** Approved — к реализации

---

## Контекст

Банк генерирует ~16 850 алертов/год из 18 TM-правил. Исходы алертов (ложное срабатывание / эскалация / СПО) нигде не хранятся в машиночитаемом виде. Следствие: precision/recall любого правила неизмеримы, любой тюнинг — действие вслепую.

DATA-1 — единственная из 37 roadmap-мер, которая не зависит ни от внешних систем, ни от смежных проектов. Её реализация разблокирует: FB-1 (backtesting), TUN-1/TUN-2 (пилоты порогов), ARCH-1 (дедупликация), DATA-2 (чистка масок).

---

## Решения

| Параметр | Решение |
|---|---|
| Тип | Новое standalone-приложение (не расширение ESF) |
| Стек | FastAPI + SQLAlchemy + PostgreSQL + Alembic + Docker |
| UI | Jinja2 + минимальный HTML (как ESF) |
| Деплой | On-premise в ЦОД банка, `docker compose up` |
| Интеграция на старте | CSV/XLSX-импорт алертов; REST API — следующая фаза |

---

## Архитектура

Строго слоями: **Router → Service → Repository → Database**.  
Никакого SQL вне репозиториев. Никакой бизнес-логики в роутерах.

```
aml-platform/
  backend/
    app/
      main.py
      core/
        config.py          ← Settings (env-vars)
        security.py        ← session auth, RBAC
      db/
        session.py
        base.py
      models/
        alert.py           ← Alert
        disposition.py     ← AlertDisposition (ядро DATA-1)
        rule.py            ← Rule (каталог правил)
        user.py            ← User (analyst / mlro / admin)
      repositories/
        alert_repo.py
        disposition_repo.py
        report_repo.py
      services/
        alert_service.py
        disposition_service.py
        report_service.py
      routers/
        alerts.py
        dispositions.py
        reports.py
        auth.py
      templates/
        alerts/
          list.html
          detail.html
          close.html
        reports/
          matrix.html
        auth/
          login.html
  alembic/
  tests/
  docker-compose.yml
  requirements.txt
```

---

## Модель данных

### `alerts`

Источник данных — импортируется из ТМ-системы банка.

| Поле | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `external_id` | string unique | ID в ТМ-системе банка (для идемпотентного upsert) |
| `rule_id` | string FK→rules | Правило-источник (7.1, №4, РС_103…) |
| `client_id` | string | Идентификатор клиента |
| `amount` | numeric | Сумма операции |
| `alert_dt` | timestamp | Момент срабатывания |
| `status` | enum OPEN/CLOSED | OPEN при импорте |
| `raw_payload` | JSON | Исходные поля из ТМ |

### `alert_dispositions` (ядро DATA-1)

| Поле | Тип | Обяз. | Описание |
|---|---|---|---|
| `id` | UUID PK | да | |
| `alert_id` | UUID FK | да | Один алерт — одна финальная запись |
| `rule_id` | string | да | Копируется из алерта |
| `outcome_code` | enum D1 | да | Итоговое решение |
| `outcome_reason_code` | enum D2 | усл. | **Обязательно при `CLOSED_FP`** |
| `outcome_dt` | timestamp | да | Момент простановки финального исхода |
| `analyst_id` | UUID FK | да | Кто принял решение |
| `escalated_flag` | bool | да | |
| `escalated_dt` | timestamp | усл. | Обязательно при `escalated_flag=true` |
| `case_id` | string | нет | Дело/расследование |
| `sar_flag` | bool | да | СПО направлено |
| `sar_dt` | date | усл. | Обязательно при `sar_flag=true` |
| `sar_number` | string | усл. | Регномер СПО |
| `correlation_id` | UUID | нет | Группа связанных алертов (основа ARCH-1) |
| `parent_alert_id` | UUID | усл. | Обязательно при `outcome_code=DUPLICATE` |
| `outcome_source` | enum LIVE/RETRO | да | Текущая работа или историческая разметка |
| `review_minutes` | int | нет | Трудозатраты (стоимость шума) |
| `qa_flag` | bool | нет | Попал в QA-выборку |
| `qa_result` | enum AGREE/DISAGREE | усл. | |

### `rules`

| Поле | Тип | Описание |
|---|---|---|
| `id` | string PK | 7.1, №4, РС_103… |
| `name` | string | Название сценария |
| `status` | enum ACTIVE/RETIRED | |
| `alerts_per_year` | int | Из аудита |
| `description` | text | |

### Справочник D1 — исходы (Enum в коде)

| Код | Название |
|---|---|
| `PENDING` | В работе (промежуточный, не финальный) |
| `CLOSED_FP` | Ложное срабатывание (требует D2) |
| `CLOSED_NO_RISK` | Объяснено, риска нет |
| `ESCALATED_REJECTED` | Эскалирован, не подтверждён |
| `ESCALATED_CONFIRMED` | Подозрение подтверждено |
| `SAR_FILED` | Направлено СПО |
| `DUPLICATE` | Дубль (требует `parent_alert_id`) |

### Справочник D2 — причины FP (Enum в коде)

| Код | Причина | Адресует меру |
|---|---|---|
| `FP_LEGIT_BUSINESS` | Обычная хоз. деятельность | TUN-2 |
| `FP_KNOWN_COUNTERPARTY` | Контрагент ранее проверен | TUN-2 (whitelist) |
| `FP_THRESHOLD_LOW` | Порог занижен для сегмента | TUN-1 |
| `FP_SEGMENT_MISMATCH` | Правило не учитывает ОКВЭД | TUN-2 |
| `FP_TEXT_MATCH` | Ложное совпадение по маске | DATA-2 |
| `FP_DUPLICATE_LOGIC` | Сработали дублирующие правила | MRG-1…4 |
| `FP_DATA_ERROR` | Ошибка данных/справочника | GOV-3 |
| `FP_ONE_OFF` | Разовая, объяснённая | тюнингу не подлежит |

---

## Data Flow

### Закрытие алерта аналитиком

```
1. GET /alerts/{id}         → AlertRepo.get_by_id()  →  detail.html
2. POST /alerts/{id}/close  {outcome_code, reason_code, ...}
3. DispositionService.close_alert():
     a. Проверить alert.status == OPEN  (иначе AlreadyClosedError → 409)
     b. Валидировать бизнес-правила:
          CLOSED_FP  → outcome_reason_code обязателен  (InvalidDispositionError → 422)
          DUPLICATE  → parent_alert_id обязателен
          escalated_flag=true → escalated_dt обязателен
     c. Создать AlertDisposition (outcome_source=LIVE)
     d. Обновить alert.status = CLOSED
     e. Commit (всё в одной транзакции)
4. Redirect → /alerts/{id}  с flash-сообщением
```

### Импорт алертов (CSV)

```
POST /alerts/import  (multipart file)
  AlertService.import_from_csv():
    - Валидация схемы строк (rule_id существует, amount > 0, alert_dt parseable)
    - Upsert по external_id (идемпотентно — повторный импорт безопасен)
    - status=OPEN по умолчанию
    - Возвращает {imported: N, skipped: M, errors: [...]}
```

### Отчёт rule × month × outcome

```
GET /reports/matrix?rule_id=7.1&from=2026-01&to=2026-08
  ReportService.rule_month_matrix()
    → ReportRepo: один GROUP BY alert_dt_month, outcome_code запрос
    → HTML-таблица + кнопка CSV-экспорт
```

---

## Бизнес-инварианты (enforcement в DispositionService)

1. Алерт в статусе CLOSED закрыть повторно нельзя → `AlertAlreadyClosedError`.
2. `CLOSED_FP` без `outcome_reason_code` → `InvalidDispositionError`.
3. `DUPLICATE` без `parent_alert_id` → `InvalidDispositionError`.
4. `escalated_flag=true` без `escalated_dt` → `InvalidDispositionError`.
5. `sar_flag=true` без `sar_dt` → `InvalidDispositionError`.
6. `PENDING` — не финальный исход; алерт старше 30 дней в PENDING попадает в отчёт просроченных.

Роутеры транслируют доменные исключения в HTTP-ответы (422/409). Неожиданные 500 → `{error, detail}` JSON.

---

## RBAC

| Роль | Может |
|---|---|
| `analyst` | Просматривать алерты, закрывать с outcome |
| `mlro` | Всё analyst + эскалировать, формировать СПО, QA-выборка |
| `admin` | Всё mlro + импорт алертов, управление пользователями, справочники правил |

---

## Тесты

**Unit (pytest, без БД):**
- `DispositionService.close_alert()`: все ветки валидации
  - CLOSED_FP без reason → `InvalidDispositionError`
  - DUPLICATE без parent → `InvalidDispositionError`
  - Уже закрытый → `AlertAlreadyClosedError`
- `AlertService.import_from_csv()`: невалидная схема → ошибки без падения

**Integration (TestClient + test-DB):**
- Полный flow: импорт CSV → список алертов → закрытие → отчёт
- Попытка повторного закрытия → 409
- Попытка закрыть без reason при CLOSED_FP → 422

**Smoke:**
- `docker compose up` → `GET /health` → 200

---

## Критерии приёмки DATA-1

1. Поля таблицы `alert_dispositions` и справочники D1/D2 заведены.
2. Система не позволяет закрыть алерт без `outcome_code` (HTTP 422).
3. `CLOSED_FP` без `outcome_reason_code` → HTTP 422.
4. По топ-3 правилам (7.1, №4, РС_103) работает историческая разметка с `outcome_source=RETRO`.
5. Отчёт rule × month × outcome × reason выгружается в CSV.
6. Все юнит + интеграционные тесты зелёные.
7. `docker compose up` → приложение запускается, миграции применяются автоматически.

---

## Следующие меры (после DATA-1)

| Мера | Зависит от | Описание |
|---|---|---|
| FB-1 | DATA-1 | Backtesting-стенд: precision/recall по накопленным исходам |
| TUN-1 | DATA-1 | Пилот сегментных порогов (7.1, РС_103) |
| TUN-2 | DATA-1 | ОКВЭД-first и whitelist (№4, №3) |
| ARCH-1 | DATA-1 | Слой дедупликации алертов (correlation_id) |
| DATA-2 | DATA-1 | Чистка масок словоформ (№4, №5) |
