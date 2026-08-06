# ACTION REQUIRED — три задачи, которые может выполнить только владелец

Эти пункты **нельзя** безопасно автоматизировать (личные данные, живые секреты, внешний УЦ).
Все команды ниже — для macOS/zsh. Ни один реальный секрет в этом файле не приводится.

> Приоритет P0 — до любой демонстрации вовне и до боевого деплоя.

## Статус (проверено 2026-08-03)

- **R-1 — ✅ ВЫПОЛНЕНО.** Личных материалов в папке репозитория больше нет; они перенесены в
  `~/Desktop/ESF-Private-Materials` (проверено по полному списку из §1). Осталось по желанию:
  зашифровать этот каталог (encrypted DMG), раз в нём паспорта и материалы дела.
- **I-2 — ✅ ВЫПОЛНЕНО (2026-08-06).** Новые секреты сгенерированы (openssl rand) и записаны
  в `~/.secrets/esf/.env.production` (права 600, вне iCloud / Desktop). Файл содержит свежие
  `SECRET_KEY` (64 hex), `POSTGRES_PASSWORD` (24 b64), `ADMIN_PASSWORD` (18 b64). **Перед
  боевым деплоем:** заменить `PUBLIC_BASE_URL=https://esf.example.com` на реальный домен;
  если БД уже запущена со старым паролем — выполнить `ALTER USER esf WITH PASSWORD '…'`.
- **I-1 — открыт.** Выполняется на боевом сервере с реальным доменом (см. §3); из локальной
  среды недоступно.

---

## 1. Вынести личные юр/фин материалы из папки репозитория (R-1, High) — ✅ выполнено

Эти файлы **не** в git (`.gitignore` их закрывает), но физически лежат в дереве репозитория и
одним `git add -f` / бэкапом / расшариванием папки могут утечь. Перенесите их в отдельный каталог
**вне** репозитория.

```bash
cd ~/Desktop
mkdir -p ESF-Private-Materials
cd ESF-Enterprise-Clean-Starter
mv "ПАКЕТ_ДОКАЗАТЕЛЬСТВ" "ПАКЕТ_ДОКАЗАТЕЛЬСТВ 2" "ПАКЕТ_ДОКАЗАТЕЛЬСТВ 3" \
   "ПАКЕТ_НОТАРИУС" "Доказательства_фото" "_review" \
   "Материалы_потерпевшего_для_адвоката.pdf" "Долг_Михаила_реестр.xlsx" \
   "РП_Комплаенс_на_01.07.26.xlsx" "пост_контроль.xlsx" \
   "Проект_обращения_в_Банк_России.docx" \
   deck.pdf deck.pptx invest.py heic2 \
   ~/Desktop/ESF-Private-Materials/ 2>/dev/null
echo "Готово. Проверьте: ls ~/Desktop/ESF-Private-Materials/"
```

Это обратимо (просто перемещение). Каталог `ESF-Private-Materials` — вне git, платформы не касается.
Рассмотрите шифрование этого каталога (например, зашифрованный DMG), раз в нём паспорта и материалы дела.

---

## 2. Убрать боевые секреты с синхронизируемого Desktop и ротировать их (I-2, High)

`.env.production` содержит **реальные** `SECRET_KEY` / `POSTGRES_PASSWORD` / `ADMIN_PASSWORD`
в открытом виде на `~/Desktop` (обычно синхронизируется в iCloud). Их надо (а) убрать с Desktop,
(б) ротировать, потому что они уже могли попасть в облачные бэкапы.

Сгенерировать новые значения:

```bash
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))"
python3 -c "import secrets; print('ADMIN_PASSWORD=' + secrets.token_urlsafe(18))"
```

Затем:
1. Внесите новые значения в `.env.production` (и синхронно в `DATABASE_URL`).
2. Держите боевой `.env.production` **вне** синхронизируемых папок (не в `~/Desktop`, не в iCloud Drive).
   Идеально — секрет-стор/Docker secrets на самом сервере, а не файл на ноутбуке.
3. Смените пароль пользователя БД, если она уже развёрнута со старым паролем:
   ```sql
   ALTER USER esf WITH PASSWORD '<новый POSTGRES_PASSWORD>';
   ```
4. `PUBLIC_BASE_URL` в `.env.production` сейчас `https://localhost` — замените на реальный
   собственный домен деплоя (приложение теперь **не стартует** в проде с пустым значением или
   с `salyk.kg` — это сделано в рамках аудита, S-0).

---

## 3. Настоящий TLS-сертификат вместо самоподписанного localhost (I-1, High)

`infra/nginx/certs/{fullchain,privkey}.pem` — самоподписанные заглушки `CN=localhost`. Браузеры и
сканеры QR отвергнут такой сертификат (а публичная проверка ЭСФ — это весь смысл продукта).

На боевом сервере с реальным доменом:

```bash
# Пример через certbot (Let's Encrypt), домен esf.example.com:
sudo certbot certonly --standalone -d esf.example.com
sudo cp /etc/letsencrypt/live/esf.example.com/fullchain.pem infra/nginx/certs/fullchain.pem
sudo cp /etc/letsencrypt/live/esf.example.com/privkey.pem  infra/nginx/certs/privkey.pem
# затем перезапустить nginx-контейнер и настроить авто-обновление (certbot renew в cron/systemd-timer)
```

Приватный ключ самоподписанной заглушки — одноразовый localhost-ключ, но всё равно
перегенерируйте его на сервере, а не переиспользуйте с ноутбука.

---

### Отмеченное как сделанное в аудите (для контекста)

- S-0 (клон госформы): `PUBLIC_BASE_URL` теперь fail-closed + отклоняет `salyk.kg`; добавлен
  ДЕМО-водяной знак во всех режимах рендера.
- Удалён мёртвый код (`backend/legacy/`), пустые каталоги, пустой `frontend/`.
- Документация вычищена (12 отчётных файлов → `docs/history/`, добавлены LICENSE/SECURITY.md/
  CONTRIBUTING/.editorconfig, выверены версии/число тестов).
- CI: сборка Docker-образа + smoke, порог покрытия; pre-commit: gitleaks + bandit + detect-private-key;
  compose: resource-limits; Dockerfile: HEALTHCHECK.

Полный отчёт и план — в `AUDIT_2026-07-28.md`.
