# Настройка SSH ключей для CI/CD

Эта инструкция поможет настроить безопасную аутентификацию через SSH ключи вместо пароля для автоматического деплоя.

## Зачем нужны SSH ключи?

✅ **Безопаснее** - ключ сложнее скомпрометировать чем пароль
✅ **Удобнее** - не нужно хранить пароль в GitHub Secrets
✅ **Надежнее** - ключи не передаются по сети в открытом виде

---

## Шаг 1: Генерация SSH ключа на VDS

Подключитесь к вашему VDS серверу и выполните:

```bash
# Генерируем SSH ключ для GitHub Actions
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions_deploy -N ""
```

Будет создано 2 файла:
- `~/.ssh/github_actions_deploy` - **приватный ключ** (добавим в GitHub Secrets)
- `~/.ssh/github_actions_deploy.pub` - **публичный ключ** (добавим на сервер)

---

## Шаг 2: Добавление публичного ключа в authorized_keys

На VDS сервере выполните:

```bash
# Добавляем публичный ключ в authorized_keys
cat ~/.ssh/github_actions_deploy.pub >> ~/.ssh/authorized_keys

# Проверяем права доступа
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

---

## Шаг 3: Копирование приватного ключа

Скопируйте **весь** приватный ключ:

```bash
cat ~/.ssh/github_actions_deploy
```

**ВАЖНО:** Скопируйте полностью, включая строки:
```
-----BEGIN OPENSSH PRIVATE KEY-----
...весь ключ...
-----END OPENSSH PRIVATE KEY-----
```

---

## Шаг 4: Добавление ключа в GitHub Secrets

1. Откройте: https://github.com/Andrew821667/legal-ai-bot/settings/secrets/actions

2. Добавьте новый secret:
   - **Name:** `VDS_SSH_PRIVATE_KEY`
   - **Value:** Вставьте скопированный приватный ключ

3. Добавьте также (если еще нет):
   - **Name:** `VDS_HOST`
   - **Value:** IP адрес или домен вашего VDS (например: `123.45.67.89`)

   - **Name:** `VDS_USERNAME`
   - **Value:** имя пользователя на VDS (обычно `root`)

   - **Name:** `VDS_PORT` (опционально, по умолчанию 22)
   - **Value:** SSH порт (обычно `22`)

4. **УДАЛИТЕ** старый secret `VDS_PASSWORD` - он больше не нужен

---

## Шаг 5: Тестирование

После настройки secrets, сделайте push в main ветку:

```bash
git push origin main
```

GitHub Actions автоматически запустит деплой с использованием SSH ключа.

Проверьте логи workflow здесь:
https://github.com/Andrew821667/legal-ai-bot/actions

---

## Проверка SSH подключения вручную

Для проверки что ключ работает, с VDS сервера выполните:

```bash
ssh -i ~/.ssh/github_actions_deploy username@localhost
```

Если подключение успешно - всё настроено правильно!

---

## Troubleshooting

### Ошибка: "Permission denied (publickey)"

**Решение:**
```bash
# Проверьте права доступа
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
chmod 600 ~/.ssh/github_actions_deploy

# Проверьте что ключ добавлен
cat ~/.ssh/authorized_keys | grep github-actions-deploy
```

### Ошибка: "Bad owner or permissions"

**Решение:**
```bash
# Права должны быть строгими
chmod 700 ~/.ssh
chmod 600 ~/.ssh/*
```

### GitHub Actions не может подключиться

**Проверьте:**
1. Скопирован ли **весь** приватный ключ (включая BEGIN/END)
2. Правильный ли VDS_HOST (IP или домен)
3. Правильный ли VDS_USERNAME
4. Открыт ли SSH порт в firewall

---

## Безопасность

⚠️ **НИКОГДА** не коммитьте приватный ключ в Git!
⚠️ Храните приватный ключ **только** в GitHub Secrets
⚠️ После настройки удалите `VDS_PASSWORD` из secrets

---

**Готово!** Теперь деплой использует безопасную аутентификацию через SSH ключи.
