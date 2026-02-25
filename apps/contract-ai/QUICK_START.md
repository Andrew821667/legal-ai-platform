# Contract AI System - Quick Start Guide

## 🚀 Fastest Way to Start

### Option 1: Desktop Launcher (Recommended)
**Double-click the icon on your desktop:**
```
📱 launch_contract_ai.command
```

This will:
- Start all 3 services (Backend + Frontend + Admin)
- Open browser tabs automatically
- Show you login credentials

### Option 2: Command Line
```bash
cd /Users/andrew/.claude-worktrees/Contract-AI-System-/blissful-hellman
./start_all.sh
```

---

## 🌐 Access Points

| Service | URL | Description |
|---------|-----|-------------|
| **Main App** | http://localhost:3000 | User interface (Next.js) |
| **Admin Panel** | http://localhost:8501 | Admin dashboard (Streamlit) |
| **API Docs** | http://localhost:8000/api/docs | REST API documentation |
| **API Health** | http://localhost:8000/health | Backend health check |

---

## 👥 Default Credentials

### Admin Panel (http://localhost:8501)
```
Email:    admin@contractai.local
Password: Admin123!
```

### Main App (http://localhost:3000)
```
Junior Lawyer:  junior@contractai.local / Junior123!
Lawyer:         lawyer@contractai.local / Lawyer123!
Senior Lawyer:  senior@contractai.local / Senior123!
VIP Client:     vip@contractai.local    / Vip123!
Demo User:      demo1@example.com       / Demo123!
```

📄 **Full list:** See `CREDENTIALS.txt` file

---

## 🛑 How to Stop

### Option 1: Stop Script
```bash
cd /Users/andrew/.claude-worktrees/Contract-AI-System-/blissful-hellman
./stop_all.sh
```

### Option 2: Manual
```bash
# Kill by port
lsof -ti:8000 | xargs kill -9  # Backend
lsof -ti:3000 | xargs kill -9  # Frontend
lsof -ti:8501 | xargs kill -9  # Admin
```

---

## 📋 System Architecture

```
┌─────────────────────────────────────────┐
│  USERS (Lawyers, Clients)              │
└──────────────┬──────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  NEXT.JS FRONTEND (Port 3000)           │
│  - Modern React UI                       │
│  - Contract upload & analysis            │
│  - Document generation                   │
│  - User dashboard                        │
└──────────────┬───────────────────────────┘
               │ REST API
               ▼
┌──────────────────────────────────────────┐
│  FASTAPI BACKEND (Port 8000)            │
│  - Authentication (JWT)                  │
│  - 7 AI Agents                           │
│  - Contract processing                   │
│  - Database operations                   │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  ADMINS                                  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  STREAMLIT ADMIN (Port 8501)            │
│  - User management                       │
│  - Demo link generation                  │
│  - Analytics dashboard                   │
│  - System settings                       │
└──────────────────────────────────────────┘
```

---

## 🔧 Troubleshooting

### Services won't start

**1. Check if ports are in use:**
```bash
lsof -i :8000  # Backend
lsof -i :3000  # Frontend
lsof -i :8501  # Admin
```

**2. Kill processes on ports:**
```bash
lsof -ti:8000 | xargs kill -9
lsof -ti:3000 | xargs kill -9
lsof -ti:8501 | xargs kill -9
```

**3. Check logs:**
```bash
tail -f logs/backend.log
tail -f logs/frontend.log
tail -f logs/admin.log
```

### Database issues

**Reinitialize database:**
```bash
rm contract_ai.db
python3 database/init_users.py
```

### Frontend dependencies issues

**Reinstall:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Missing .env file

**Copy from example:**
```bash
cp .env.example .env
# Then edit .env and add your API keys
```

---

## 📦 What's Included

### Backend (FastAPI)
- ✅ REST API with OpenAPI docs
- ✅ JWT authentication
- ✅ 7 AI agents for contract processing
- ✅ SQLite database
- ✅ Rate limiting & security middleware

### Frontend (Next.js)
- ✅ Modern React 18 + TypeScript
- ✅ TailwindCSS styling
- ✅ React Query for data fetching
- ✅ Responsive design
- ✅ Real-time updates

### Admin Panel (Streamlit)
- ✅ User management (CRUD)
- ✅ Demo token generation
- ✅ Analytics dashboard
- ✅ System settings
- ✅ Audit logs

---

## 🧑‍💼 User Roles & Permissions

| Role | Tier | Contracts/Day | LLM Requests/Day | Features |
|------|------|---------------|------------------|----------|
| **demo** | demo | 3 | 10 | Basic analysis only |
| **junior_lawyer** | basic | 50 | 100 | Standard features |
| **lawyer** | pro | 200 | 500 | All features |
| **senior_lawyer** | pro | 200 | 500 | All features + task management |
| **admin** | enterprise | ∞ | ∞ | Everything + admin panel |

---

## 📚 Additional Resources

- **Full Documentation:** `CONTRACT_AI_SYSTEM_SPECIFICATION.md`
- **API Reference:** http://localhost:8000/api/docs
- **Project Status:** `CLAUDE.md`
- **Test Reports:** `TESTING_REPORT.md`

---

## 💡 Tips

1. **First time setup:** Desktop launcher will auto-initialize everything
2. **Development:** Use `./start_all.sh` for more control
3. **Production:** Change all passwords in `CREDENTIALS.txt`
4. **Demo links:** Generate from admin panel for clients
5. **Monitoring:** Check logs in `logs/` directory

---

## 🆘 Support

If you encounter issues:

1. Check logs in `logs/` directory
2. Verify all services are running: `ps aux | grep -E "(uvicorn|streamlit|next)"`
3. Check ports: `lsof -i :8000 -i :3000 -i :8501`
4. Restart services: `./stop_all.sh && ./start_all.sh`

---

## 🔐 Security Notes

⚠️ **IMPORTANT:**
- Change default passwords before deploying to production
- Never commit `.env` or `CREDENTIALS.txt` to version control
- Use HTTPS in production
- Enable 2FA for admin accounts
- Regularly rotate API keys

---

**Version:** 2.0.0
**Last Updated:** December 2025
**License:** MIT
