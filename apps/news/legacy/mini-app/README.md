# AI Verdict News - Telegram Mini App

Modern web interface for managing AI News Aggregator via Telegram Mini Apps.

## Features

- **Dashboard** - Real-time statistics with charts and key metrics
- **Content Manager** - Review and moderate draft articles
- **Analytics** - Detailed analytics with engagement metrics
- **Settings** - Manage system settings (sources, LLM models, auto-publish, etc.)

## Tech Stack

- **Frontend**: Next.js 14 + React 18 + TypeScript
- **Styling**: Tailwind CSS + shadcn/ui components
- **Charts**: Recharts
- **Telegram**: @telegram-apps/sdk-react
- **Backend**: FastAPI (see `/api/miniapp` endpoints in main app)

## Setup

### 1. Install dependencies

```bash
cd mini-app
npm install
```

### 2. Configure environment

Create `.env.local`:

```bash
# Backend API URL - замените на ваш реальный API сервер
NEXT_PUBLIC_API_URL=https://your-api-server.com

# Telegram Bot Username (без @)
NEXT_PUBLIC_BOT_USERNAME=your_bot_username

# Production URL (для Vercel будет автоматически установлен)
NEXT_PUBLIC_BASE_URL=https://your-app.vercel.app
```

**Важно для production:**
- `NEXT_PUBLIC_API_URL` должен указывать на ваш развернутый FastAPI сервер
- В Vercel настройках добавьте эту переменную окружения

### 3. Run development server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to see the app.

## Deployment

### Option 1: Vercel (Recommended)

1. Push code to GitHub
2. Import project in [Vercel](https://vercel.com)
3. Set environment variables
4. Deploy

### Option 2: Docker

```bash
# Build
docker build -t legal-ai-miniapp .

# Run
docker run -p 3000:3000 --env-file .env.local legal-ai-miniapp
```

## Backend Integration

The Mini App requires FastAPI backend with these endpoints:

- `GET /api/miniapp/dashboard/stats` - Dashboard statistics
- `GET /api/miniapp/drafts` - List of draft articles
- `POST /api/miniapp/drafts/{id}/approve` - Approve draft
- `POST /api/miniapp/drafts/{id}/reject` - Reject draft
- `GET /api/miniapp/published` - Published articles
- `GET /api/miniapp/published/stats` - Analytics
- `GET /api/miniapp/settings` - System settings
- `PUT /api/miniapp/settings` - Update settings

See `app/api/miniapp.py` in the main project.

## Telegram Bot Setup

Add this to your `.env` in the main project:

```bash
MINI_APP_URL=https://your-vercel-app.vercel.app
```

The bot will automatically add a "🚀 Открыть Mini App" button in the main menu.

## Development

```bash
# Run dev server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Lint code
npm run lint
```

## Project Structure

```
mini-app/
├── src/
│   ├── app/              # Next.js pages
│   │   ├── page.tsx      # Dashboard
│   │   ├── drafts/       # Content manager
│   │   ├── analytics/    # Analytics
│   │   └── settings/     # Settings
│   ├── components/       # React components
│   │   ├── ui/           # shadcn/ui components
│   │   └── TelegramProvider.tsx
│   ├── lib/              # Utilities
│   │   ├── api.ts        # API client
│   │   └── utils.ts      # Helper functions
│   └── types/            # TypeScript types
├── public/               # Static files
└── package.json
```

## Authentication

The Mini App uses Telegram WebApp init data for authentication. The init data is sent to the backend via the `X-Telegram-Init-Data` header.

In production, the backend should verify the hash using the bot token.

## Notes

- The app is designed to work inside Telegram only
- Requires a valid Telegram bot token
- Backend must be accessible from the internet for production
- CORS is configured to allow all origins (restrict in production)
