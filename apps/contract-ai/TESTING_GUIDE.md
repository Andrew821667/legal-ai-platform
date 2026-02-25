# Contract AI System - Testing Guide

## Quick Start

**Desktop Shortcuts** (✅ WORKING):
- **"Contract AI.command"** - Запускает все сервисы (Backend + Frontend)
- **"Contract AI Stop.command"** - Останавливает все сервисы

**URLs:**
- Frontend: http://localhost:3000 ✅
- Backend API: http://localhost:8000 ✅
- Admin Panel: http://localhost:8501 ⚠️ (optional, not in worktree)

**Status:** Desktop shortcuts fixed and working! (Dec 4, 2025)

---

## Test Users & Credentials

### Production Database Users

| Email | Password | Role | Description |
|-------|----------|------|-------------|
| admin@contractai.local | Admin123! | admin | System Administrator - Full access |
| senior@contractai.local | *Unknown* | senior_lawyer | Senior Lawyer - Advanced features |
| lawyer@contractai.local | Lawyer123! | lawyer | Regular Lawyer - Standard access |
| junior@contractai.local | Junior123! | junior_lawyer | Junior Lawyer - Limited access |
| vip@contractai.local | *Unknown* | senior_lawyer | VIP Client |
| demo1@example.com | *Unknown* | demo | Demo User 1 |
| demo2@example.com | *Unknown* | demo | Demo User 2 |
| trial@example.com | *Unknown* | junior_lawyer | Trial User |

### Frontend Demo Mode (Works without backend)

| Email | Password | Description |
|-------|----------|-------------|
| demo@example.com | demo123 | Quick demo access |
| admin@example.com | admin123 | Admin demo access |

*Note: Demo mode stores fake token in localStorage and redirects to dashboard*

---

## Role-Based Access (Design)

### Admin Role
**Access Level:** Full system control

**Features:**
- User management (create, edit, delete users)
- System configuration
- All lawyer features
- Analytics & reporting
- Audit logs
- Template management
- LLM provider configuration

### Senior Lawyer Role
**Access Level:** Advanced features

**Features:**
- Contract analysis (unlimited)
- Contract generation
- Contract comparison
- Protocol generation
- Advanced analytics
- Template editing
- Export to all formats (DOCX, PDF, JSON)
- Version history

### Lawyer Role
**Access Level:** Standard professional

**Features:**
- Contract analysis (limited quota)
- Contract generation (from templates only)
- Contract comparison (limited)
- Basic analytics
- Export to DOCX, PDF
- View version history

### Junior Lawyer Role
**Access Level:** Basic access

**Features:**
- Contract analysis (basic, limited quota)
- View contracts
- View analysis results
- Export to PDF only
- No generation capabilities

---

## API Integration Status

### OpenAI GPT Integration
**Status:** ✅ Configured

```
OPENAI_API_KEY=sk-proj-ooeLD5fDT-YZk7RqbV37lVsGj...
```

**Models in use:**
- gpt-4o-mini (Level 1 analysis, fast & cheap)
- gpt-4o (Level 2 deep analysis, expensive)

**Test command:**
```bash
# From project root
python -c "from src.services.llm_gateway import LLMGateway; gw = LLMGateway(); print(gw.complete('Test', 'Say hello'))"
```

### Other Providers (Optional)
- Anthropic Claude: Configured
- Perplexity: Configured
- YandexGPT: Available
- GigaChat: Available

---

## Feature Status

### ✅ Implemented (Backend)
- Contract analysis with AI
- Two-level analysis system (fast + deep)
- Contract generation from templates
- Version comparison
- Protocol of disagreements generation
- RAG system for context
- Export to DOCX/PDF/JSON
- User roles & permissions
- LLM cost tracking

### ✅ Implemented (Frontend)
- Modern UI with gradients & animations
- Landing page
- Login/Register pages (with demo mode)
- Dashboard
- Pricing page
- Contract upload (drag & drop)
- Contract list (filters & search)

### ⚠️ Partially Implemented
- Admin functionality (backend exists, frontend UI missing)
- Role-based UI differences (all users see same interface)
- Analytics dashboard

### ❌ Not Yet Implemented
- Contract generation UI
- Version comparison UI
- Protocol generation UI
- Advanced analytics visualizations
- Template editor UI
- User management UI
- Real-time notifications

---

## Testing Workflows

### Workflow 1: Contract Analysis
1. Login with any user
2. Navigate to "Upload Contract"
3. Drag & drop PDF/DOCX file
4. Fill in metadata (contract type, parties)
5. Click "Загрузить и проанализировать"
6. View analysis results (risks, recommendations, scores)

### Workflow 2: Contract List
1. Login with any user
2. Navigate to "Contracts"
3. Use search/filters
4. Click contract card to view details
5. View risk badges and scores

### Workflow 3: Demo Mode (No Backend Required)
1. Go to http://localhost:3000/login
2. Use demo@example.com / demo123
3. Dashboard loads with mock data
4. Explore UI without API calls

---

## Known Issues & Limitations

### Frontend
1. **No role-based UI**: All users see same interface regardless of role
2. **No admin features visible**: Admin login doesn't show admin-specific UI
3. **Mock data in contracts list**: Real API integration pending
4. **No generate function**: UI not implemented yet

### Backend
1. **Async blocking**: Some RAG/LLM calls are synchronous
2. **RAG system fragmentation**: Multiple RAG implementations exist
3. **No observability**: Missing metrics for RAG performance
4. **No integration tests**: End-to-end tests needed

### General
1. ✅ **Desktop shortcut**: FIXED - теперь запускает Backend + Frontend корректно
2. **Repository cleanup needed**: Old code artifacts present
3. **LLM limiting strategy unclear**: Confusion between request count vs tokens/cost
4. **Missing passwords**: Some test users have unknown passwords

---

## Next Steps

### High Priority
1. Add role-based UI visibility (show/hide features per role)
2. Add admin panel UI to frontend
3. Implement contract generation UI
4. Clean up repository artifacts
5. Document all test user passwords

### Medium Priority
1. Fix async/await blocking issues
2. Unify RAG systems
3. Add observability/metrics
4. Create integration tests
5. Implement color themes per role

### Low Priority
1. Advanced analytics
2. Real-time notifications
3. Template editor UI
4. User management UI

---

## Quick Commands

```bash
# Start everything
cd /Users/andrew/.claude-worktrees/Contract-AI-System-/blissful-hellman
./start_all.sh

# Stop everything
./stop_all.sh

# Start only frontend
cd frontend && npm run dev

# Start only backend
cd /Users/andrew/Contract-AI-System- && streamlit run app.py

# Check running processes
ps aux | grep -E "node|streamlit|uvicorn"

# Check ports
lsof -i :3000  # Frontend
lsof -i :8000  # Backend
lsof -i :8501  # Admin
```

---

**Last Updated:** 2025-12-04
**Version:** 1.0
