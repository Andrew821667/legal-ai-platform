# ⚡ Быстрый старт - Деплой на Vercel за 5 минут

## 1️⃣ Подготовка (1 мин)

```bash
cd /home/user/Telegram_channel_auto
git add mini-app/
git commit -m "feat: Prepare mini-app for Vercel deployment"
git push origin claude/test-telegram-news-api-Hm0TL
```

## 2️⃣ Vercel Setup (2 мин)

1. Откройте https://vercel.com
2. **Sign Up** → **Continue with GitHub**
3. **Add New** → **Project**
4. Выберите `Telegram_channel_auto`
5. **Root Directory** → Нажмите **Edit** → Введите `mini-app`
6. **Environment Variables**:
   ```
   NEXT_PUBLIC_API_URL=http://your-backend.com
   NEXT_PUBLIC_BOT_USERNAME=your_bot_username
   ```
7. Нажмите **Deploy**

## 3️⃣ Локальный backend через ngrok (1 мин)

Если backend локально:

```bash
# Установите ngrok (один раз)
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Получите токен на https://dashboard.ngrok.com/get-started/your-authtoken
ngrok authtoken YOUR_TOKEN

# Запустите туннель
ngrok http 8000
```

Скопируйте URL (например `https://abc123.ngrok.io`) и обновите `NEXT_PUBLIC_API_URL` в Vercel.

## 4️⃣ Настройка Telegram Bot (1 мин)

1. Откройте @BotFather
2. `/mybots` → Ваш бот → **Bot Settings**
3. **Menu Button** → **Edit Menu Button URL**
4. Вставьте ваш Vercel URL: `https://your-app.vercel.app`
5. **Edit Menu Button Text** → `📊 Аналитика`

## 5️⃣ Проверка

1. Откройте бота в Telegram
2. Нажмите кнопку меню (рядом с полем ввода)
3. Выберите **"📊 Аналитика"**
4. Mini App должен открыться! 🎉

---

## 🔧 Если что-то не работает

**Backend не доступен?**
```bash
# Проверьте что Docker контейнеры запущены
docker compose ps

# Проверьте логи FastAPI
docker compose logs app

# Проверьте ngrok
curl https://your-ngrok-url.ngrok.io/api/miniapp/dashboard/stats
```

**Mini App не загружается?**
- Проверьте Vercel Logs: https://vercel.com/your-project/logs
- Проверьте Environment Variables в Vercel Settings
- Убедитесь что URL в BotFather правильный

**Данные не загружаются?**
- Откройте DevTools в Telegram Desktop (Ctrl+Shift+I)
- Проверьте Console и Network tabs
- Убедитесь что CORS настроен в FastAPI

---

## 📝 Чеклист

- [ ] Код запушен на GitHub
- [ ] Проект создан в Vercel с Root Directory = `mini-app`
- [ ] Environment Variables добавлены
- [ ] Деплой завершён успешно
- [ ] Ngrok запущен (если backend локально)
- [ ] URL добавлен в BotFather Menu Button
- [ ] Mini App открывается в боте

---

## 🚀 Готово к использованию!

Полная инструкция: см. `VERCEL_DEPLOY.md`
