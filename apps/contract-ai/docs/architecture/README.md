# Architecture Documentation

Comprehensive architecture overview of the Contract-AI-System.

## Table of Contents

- [System Overview](#system-overview)
- [High-Level Architecture](#high-level-architecture)
- [Component Architecture](#component-architecture)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [Agent Architecture](#agent-architecture)
- [Service Layer](#service-layer)
- [Integration Architecture](#integration-architecture)
- [Security Architecture](#security-architecture)
- [Performance Architecture](#performance-architecture)
- [Scalability Considerations](#scalability-considerations)

---

## System Overview

Contract-AI-System is a multi-agent AI system for comprehensive contract analysis, disagreement handling, and export management. The system leverages LLM capabilities (GPT-4, Claude-2) with RAG (Retrieval-Augmented Generation) for enhanced accuracy.

### Core Capabilities

1. **Contract Analysis** - Automated risk identification, compliance checking, clause extraction
2. **Disagreement Handling** - Legal objection generation with reasoning
3. **Export Management** - Multi-format export (PDF, DOCX, Email, EDO)
4. **Performance Optimization** - Multi-layer caching, async processing, batch operations
5. **External Integrations** - FNS EGRUL API, OCR, tracked changes parsing

### Technology Stack

**Backend:**
- Python 3.9+
- FastAPI (async web framework)
- SQLAlchemy 2.0 (ORM)
- PostgreSQL / SQLite (database)
- Redis (caching)

**AI/ML:**
- OpenAI (GPT-4, GPT-3.5-turbo)
- Anthropic Claude (Claude-2)
- LangChain (orchestration)
- ChromaDB (vector storage)

**Document Processing:**
- python-docx (DOCX parsing)
- PyPDF2 / pdfplumber (PDF parsing)
- pytesseract (OCR)
- lxml (XML processing)
- ReportLab (PDF generation)

**Infrastructure:**
- Docker / Kubernetes (containerization)
- Nginx (reverse proxy)
- Prometheus + Grafana (monitoring)
- Redis (caching + rate limiting)

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │   Web    │  │   API    │  │  Mobile  │  │   CLI    │       │
│  │   UI     │  │  Clients │  │   App    │  │  Tools   │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTPS/REST API
┌────────────────────────┴────────────────────────────────────────┐
│                      API Gateway Layer                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  FastAPI Application (Rate Limiting, Auth, Validation)  │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────────┐
│                       Agent Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Contract    │  │ Disagreement │  │    Export    │         │
│  │  Analyzer    │  │    Agent     │  │    Agent     │         │
│  │    Agent     │  │              │  │              │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                  │                  │                 │
│  ┌──────┴──────────────────┴──────────────────┴───────┐        │
│  │           LLM Gateway (Unified Interface)          │        │
│  └──────┬────────────────────────────────────┬────────┘        │
│         │                                     │                 │
│  ┌──────┴────────┐                  ┌────────┴────────┐        │
│  │  OpenAI API   │                  │ Anthropic API   │        │
│  │  (GPT-4)      │                  │  (Claude-2)     │        │
│  └───────────────┘                  └─────────────────┘        │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────────┐
│                      Service Layer                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Clause    │  │    Risk     │  │Recommenda-  │            │
│  │  Extractor  │  │  Analyzer   │  │tion Gen.    │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  Metadata   │  │    Cache    │  │   Async     │            │
│  │  Analyzer   │  │   Service   │  │ API Client  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │     OCR     │  │   FNS API   │  │   Tracked   │            │
│  │   Service   │  │   Client    │  │   Changes   │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────────┐
│                       Data Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  PostgreSQL  │  │    Redis     │  │   ChromaDB   │         │
│  │  (Primary)   │  │   (Cache)    │  │   (Vectors)  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────────┐
│                    External Services                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  FNS EGRUL   │  │  Dadata.ru   │  │     EDO      │         │
│  │     API      │  │     API      │  │   Systems    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. API Gateway Layer

**Responsibilities:**
- HTTP request routing
- Authentication & authorization
- Rate limiting
- Request validation
- Response formatting
- CORS handling

**Key Components:**

```python
# src/main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter

app = FastAPI(
    title="Contract AI System",
    version="2.0.0",
    docs_url="/docs"
)

# Middleware
app.add_middleware(CORSMiddleware, allow_origins=["*"])
app.add_middleware(RateLimitMiddleware, max_requests=100)

# Routes
app.include_router(contract_router, prefix="/api/v1/contracts")
app.include_router(disagreement_router, prefix="/api/v1/disagreements")
app.include_router(export_router, prefix="/api/v1/export")
```

### 2. Agent Layer

Multi-agent architecture with specialized agents:

**ContractAnalyzerAgent** - Main contract analysis
- Clause extraction
- Risk identification
- Recommendation generation
- Metadata analysis
- Counterparty verification
- Dispute prediction

**DisagreementAgent** - Legal objection generation
- Disagreement point analysis
- Legal basis identification
- Supporting document references
- Effectiveness tracking

**ExportAgent** - Multi-format export
- PDF generation with annotations
- DOCX generation
- Email sending
- EDO integration

**Architecture Pattern:**

```python
class BaseAgent(ABC):
    """Base class for all agents"""

    def __init__(self, llm_gateway: LLMGateway, db_session: Session):
        self.llm_gateway = llm_gateway
        self.db = db_session

    @abstractmethod
    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """Main execution method"""
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Returns agent-specific system prompt"""
        pass
```

### 3. LLM Gateway

Unified interface for multiple LLM providers:

```python
class LLMGateway:
    """Unified gateway for multiple LLM providers"""

    def __init__(self, cache: Optional[CacheService] = None):
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        self.anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.cache = cache

    def chat_completion(
        self,
        messages: List[Dict],
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        use_cache: bool = True
    ) -> str:
        """Unified chat completion interface"""

        # Check cache first
        if use_cache and self.cache:
            cache_key = self._generate_cache_key(messages, model)
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        # Route to appropriate provider
        if model.startswith("gpt"):
            response = self._openai_completion(messages, model, temperature, max_tokens)
        elif model.startswith("claude"):
            response = self._anthropic_completion(messages, model, temperature, max_tokens)

        # Cache result
        if use_cache and self.cache:
            self.cache.set(cache_key, response, ttl=3600)

        return response
```

### 4. Service Layer

Modular services following Single Responsibility Principle:

**ClauseExtractor** (src/services/clause_extractor.py):
- Static methods for contract structure extraction
- Clause identification and parsing
- XPath-based clause location

**RiskAnalyzer** (src/services/risk_analyzer.py):
- Batch clause analysis (15 clauses/batch)
- Risk identification
- Severity classification
- Legal basis extraction

**RecommendationGenerator** (src/services/recommendation_generator.py):
- Recommendation generation
- Suggested text changes
- Visual annotations
- Priority assignment

**MetadataAnalyzer** (src/services/metadata_analyzer.py):
- Counterparty verification
- Dispute probability prediction
- Template compliance checking
- Workflow routing

**CacheService** (src/services/cache_service.py):
- Multi-layer caching (Redis + in-memory)
- LRU eviction
- TTL management
- Decorator-based caching

**AsyncAPIClient** (src/services/async_api_client.py):
- Async HTTP client
- Connection pooling
- Retry logic with exponential backoff
- Rate limiting (token bucket)

**OptimizedQueries** (src/services/optimized_queries.py):
- N+1 query elimination
- Eager loading patterns
- Batch operations
- Aggregation queries

---

## Data Flow

### Contract Analysis Flow

```
1. Client Upload
   │
   ├─→ POST /api/v1/contracts/analyze
   │   - file: contract.pdf
   │   - metadata: {contract_type, counterparty_inn}
   │
2. API Gateway
   │
   ├─→ Validation (file type, size, format)
   ├─→ Rate limiting check
   ├─→ Authentication
   │
3. ContractAnalyzerAgent.execute()
   │
   ├─→ DocumentParser
   │   ├─→ PDF/DOCX parsing
   │   ├─→ OCR (if scanned)
   │   └─→ XML conversion
   │
   ├─→ ClauseExtractor
   │   ├─→ extract_structure() - High-level info
   │   └─→ extract_clauses() - Individual clauses
   │
   ├─→ MetadataAnalyzer
   │   ├─→ check_counterparties()
   │   │   └─→ FNSAPIClient.get_company_info()
   │   │       ├─→ Cache check
   │   │       └─→ External API call (if not cached)
   │   └─→ Template comparison
   │
   ├─→ RiskAnalyzer
   │   ├─→ analyze_clauses_batch() [Batch size: 15]
   │   │   └─→ LLMGateway.chat_completion()
   │   │       ├─→ Cache check
   │   │       ├─→ OpenAI/Anthropic API
   │   │       └─→ Cache result
   │   └─→ identify_risks()
   │
   ├─→ RecommendationGenerator
   │   ├─→ generate_recommendations()
   │   ├─→ generate_suggested_changes()
   │   └─→ generate_annotations()
   │
   ├─→ MetadataAnalyzer
   │   ├─→ predict_disputes()
   │   └─→ determine_next_action()
   │
   └─→ Save to Database
       ├─→ AnalysisResult
       ├─→ ContractRisk (N records)
       ├─→ ContractRecommendation (N records)
       ├─→ ContractSuggestedChange (N records)
       └─→ ContractAnnotation (N records)
   │
4. Response to Client
   └─→ {analysis_id, risks, recommendations, next_action}
```

### Caching Flow

```
Request → Cache Check
          │
          ├─→ Hit: Return cached value (instant)
          │
          └─→ Miss:
              ├─→ Execute operation (slow)
              ├─→ Store in cache
              │   ├─→ In-memory cache (fast access)
              │   └─→ Redis (persistent, distributed)
              └─→ Return result

Cache Layers:
1. In-memory LRU cache (10k entries, instant access)
2. Redis cache (distributed, persistent)
3. Database (source of truth)
```

### Async API Flow

```
Parallel API Calls:

Sequential (OLD):
├─→ API Call 1 (2s)
├─→ API Call 2 (2s)
├─→ API Call 3 (2s)
└─→ Total: 6s

Async (NEW):
├─→ API Call 1 ─┐
├─→ API Call 2 ─┼─→ asyncio.gather() → 2s total
└─→ API Call 3 ─┘

Implementation:
async with AsyncAPIClient() as client:
    results = await client.batch_get([url1, url2, url3])
```

---

## Database Schema

### Core Tables

**contracts** - Contract metadata
```sql
CREATE TABLE contracts (
    id VARCHAR PRIMARY KEY,
    file_name VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    file_hash VARCHAR UNIQUE,
    contract_type VARCHAR,
    status VARCHAR,  -- pending, in_progress, review, completed
    risk_level VARCHAR,  -- low, medium, high, critical
    assigned_to VARCHAR,
    upload_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_contracts_status_upload ON contracts(status, upload_date DESC);
CREATE INDEX idx_contracts_risk_upload ON contracts(risk_level, upload_date DESC);
```

**analysis_results** - Analysis results
```sql
CREATE TABLE analysis_results (
    id VARCHAR PRIMARY KEY,
    contract_id VARCHAR REFERENCES contracts(id),
    analysis_type VARCHAR,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_analysis_contract_created ON analysis_results(contract_id, created_at DESC);
```

**contract_risks** - Identified risks
```sql
CREATE TABLE contract_risks (
    id SERIAL PRIMARY KEY,
    analysis_id VARCHAR REFERENCES analysis_results(id),
    contract_id VARCHAR REFERENCES contracts(id),
    risk_type VARCHAR,
    severity VARCHAR,  -- critical, high, medium, low
    description TEXT,
    affected_clause TEXT,
    legal_basis TEXT,
    potential_consequences TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Composite indexes for performance
CREATE INDEX idx_risks_contract_severity ON contract_risks(contract_id, severity);
CREATE INDEX idx_risks_contract_type ON contract_risks(contract_id, risk_type);
```

**contract_recommendations** - Recommendations
```sql
CREATE TABLE contract_recommendations (
    id SERIAL PRIMARY KEY,
    analysis_id VARCHAR REFERENCES analysis_results(id),
    contract_id VARCHAR REFERENCES contracts(id),
    category VARCHAR,
    priority VARCHAR,  -- high, medium, low
    description TEXT,
    implementation_steps TEXT,
    legal_references TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_recommendations_contract_priority ON contract_recommendations(contract_id, priority);
```

**disagreements** - Disagreement records
```sql
CREATE TABLE disagreements (
    id VARCHAR PRIMARY KEY,
    contract_id VARCHAR REFERENCES contracts(id),
    analysis_id VARCHAR REFERENCES analysis_results(id),
    disagreement_points JSONB,
    status VARCHAR,  -- draft, submitted, resolved
    effectiveness_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_disagreement_created_status ON disagreements(created_at DESC, status);
CREATE INDEX idx_disagreement_effectiveness ON disagreements(effectiveness_score DESC)
    WHERE effectiveness_score IS NOT NULL;
```

**disagreement_objections** - Generated objections
```sql
CREATE TABLE disagreement_objections (
    id SERIAL PRIMARY KEY,
    disagreement_id VARCHAR REFERENCES disagreements(id),
    objection_text TEXT,
    legal_basis TEXT,
    supporting_documents JSONB,
    priority VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_objections_disagreement_created ON disagreement_objections(disagreement_id, created_at DESC);
```

### Relationships

```
contracts (1) ──→ (N) analysis_results
                       │
                       ├──→ (N) contract_risks
                       ├──→ (N) contract_recommendations
                       ├──→ (N) contract_suggested_changes
                       └──→ (N) contract_annotations

contracts (1) ──→ (N) disagreements
                       │
                       └──→ (N) disagreement_objections
                                │
                                └──→ (N) disagreement_feedback
```

---

## Agent Architecture

### Agent Execution Pattern

All agents follow a consistent execution pattern:

```python
class ContractAnalyzerAgent(BaseAgent):
    """
    Contract Analyzer Agent

    Responsibilities:
    1. Document parsing
    2. Structure extraction
    3. Risk analysis
    4. Recommendation generation
    5. Metadata analysis
    """

    def execute(self, document_path: str, metadata: Dict) -> Dict[str, Any]:
        """
        Main execution flow

        Phase 1: Parsing & Extraction
        Phase 2: External Data Gathering
        Phase 3: AI Analysis
        Phase 4: Synthesis & Storage
        """

        # Phase 1: Parsing
        parsed_xml = self.parse_document(document_path)
        structure = self.clause_extractor.extract_structure(parsed_xml)
        clauses = self.clause_extractor.extract_clauses(parsed_xml)

        # Phase 2: External Data
        counterparty_data = self.metadata_analyzer.check_counterparties(
            parsed_xml, metadata
        )
        rag_context = self.get_rag_context(structure['contract_type'])

        # Phase 3: AI Analysis (with caching & batching)
        clause_analyses = self.risk_analyzer.analyze_clauses_batch(
            clauses, rag_context, batch_size=15
        )
        risks = self.risk_analyzer.identify_risks(clause_analyses)

        # Phase 4: Synthesis
        recommendations = self.recommendation_generator.generate_recommendations(
            risks, rag_context
        )
        suggested_changes = self.recommendation_generator.generate_suggested_changes(
            parsed_xml, structure, risks, recommendations, rag_context
        )

        # Save to database
        return self.save_analysis(...)
```

### Agent Communication

Agents communicate through:

1. **Shared Database** - Primary state storage
2. **Message Passing** - Event-driven updates (future)
3. **Direct Calls** - Synchronous agent invocation

---

## Service Layer

### Modular Design

Services are stateless and independent:

```
┌─────────────────────────────────────────────────┐
│              Agent Layer                        │
│  ┌──────────────────────────────────────────┐  │
│  │   ContractAnalyzerAgent                  │  │
│  └───┬────────────┬────────────┬────────────┘  │
│      │            │            │                │
└──────┼────────────┼────────────┼────────────────┘
       │            │            │
       ▼            ▼            ▼
┌─────────────────────────────────────────────────┐
│              Service Layer                      │
│  ┌────────┐  ┌────────┐  ┌────────────────┐   │
│  │Clause  │  │Risk    │  │Recommendation  │   │
│  │Extract │  │Analyze │  │Generator       │   │
│  └────────┘  └────────┘  └────────────────┘   │
│                                                 │
│  ┌────────┐  ┌────────┐  ┌────────────────┐   │
│  │Metadata│  │Cache   │  │AsyncAPIClient  │   │
│  │Analyze │  │Service │  │                │   │
│  └────────┘  └────────┘  └────────────────┘   │
└─────────────────────────────────────────────────┘
```

### Service Contracts

Each service has a well-defined interface:

```python
# Input/Output contracts
class ClauseExtractor:
    @staticmethod
    def extract_structure(xml_content: str) -> Dict[str, Any]:
        """
        Input: XML string
        Output: {
            'parties': Dict,
            'price': float,
            'currency': str,
            'term_start': str,
            'term_end': str,
            'contract_type': str
        }
        """
```

---

## Integration Architecture

### External API Integration

```
┌─────────────────────────────────────────────────┐
│         Contract-AI-System                      │
│  ┌──────────────────────────────────────────┐  │
│  │         AsyncAPIClient                   │  │
│  │  ┌────────────┐  ┌─────────────────┐    │  │
│  │  │Connection  │  │Rate Limiting    │    │  │
│  │  │Pool        │  │(Token Bucket)   │    │  │
│  │  └────────────┘  └─────────────────┘    │  │
│  └─────────┬──────────────────────────────────┘│
│            │                                    │
└────────────┼────────────────────────────────────┘
             │
       ┌─────┴─────┬────────────┬──────────┐
       │           │            │          │
       ▼           ▼            ▼          ▼
┌──────────┐ ┌──────────┐ ┌─────────┐ ┌──────┐
│FNS EGRUL │ │Dadata.ru │ │ OpenAI  │ │Claude│
│   API    │ │   API    │ │   API   │ │ API  │
└──────────┘ └──────────┘ └─────────┘ └──────┘
```

### Future Integration (Phase 11)

```
┌─────────────────────────────────────────────────┐
│         legal-ai-website                        │
│  ┌──────────────────────────────────────────┐  │
│  │         React Frontend                   │  │
│  └─────────┬────────────────────────────────┘  │
│            │ HTTP/WebSocket                     │
└────────────┼────────────────────────────────────┘
             │
       ┌─────┴─────┐
       │           │
       ▼           ▼
┌──────────┐ ┌──────────┐
│  REST    │ │WebSocket │
│   API    │ │  Server  │
└─────┬────┘ └────┬─────┘
      │           │
┌─────┴───────────┴─────┐
│ Contract-AI-System    │
│  - Analysis API       │
│  - Real-time updates  │
│  - Webhook events     │
└───────────────────────┘
```

---

## Security Architecture

### Defense in Depth

```
Layer 1: Network Security
├─→ Firewall (UFW/iptables)
├─→ TLS 1.2+ encryption
└─→ DDoS protection

Layer 2: API Security
├─→ Rate limiting (100 req/min)
├─→ Input validation
├─→ Authentication (JWT)
└─→ Authorization (RBAC)

Layer 3: Application Security
├─→ SQL injection prevention (SQLAlchemy ORM)
├─→ XSS prevention (output sanitization)
├─→ CSRF protection
└─→ Secure file upload

Layer 4: Data Security
├─→ Encrypted at rest (database encryption)
├─→ Encrypted in transit (TLS)
├─→ Secret management (environment variables)
└─→ Regular backups

Layer 5: Monitoring
├─→ Audit logging
├─→ Anomaly detection
├─→ Security alerts
└─→ Compliance reporting
```

### Authentication Flow

```
Client Request
   │
   ├─→ Include JWT token in Authorization header
   │
API Gateway
   │
   ├─→ Validate JWT signature
   ├─→ Check token expiration
   ├─→ Extract user claims
   │
Authorization
   │
   ├─→ Check user role
   ├─→ Verify resource permissions
   │
Proceed to Handler
```

---

## Performance Architecture

### Multi-Layer Optimization

```
1. Application Layer
   ├─→ Async processing (asyncio, aiohttp)
   ├─→ Batch operations (15 clauses/batch)
   ├─→ Connection pooling
   └─→ Worker processes (Gunicorn)

2. Caching Layer
   ├─→ In-memory LRU cache (instant access)
   ├─→ Redis cache (distributed)
   ├─→ HTTP caching headers
   └─→ 40%+ cache hit rate

3. Database Layer
   ├─→ Composite indexes (20+ indexes)
   ├─→ Eager loading (N+1 elimination)
   ├─→ Connection pooling
   ├─→ Query optimization
   └─→ Partial indexes (PostgreSQL)

4. API Layer
   ├─→ Parallel API calls
   ├─→ Retry with exponential backoff
   ├─→ Circuit breaker pattern
   └─→ Request deduplication
```

### Performance Metrics

**Before Optimization:**
- 50 clauses: 100 seconds
- 10 contracts: 1000 seconds (17 minutes)
- Cost: $5.00 per batch

**After Phase 8 Optimization:**
- 50 clauses: 8 seconds (with caching: 3 seconds)
- 10 contracts: 8 seconds (parallel processing)
- Cost: $0.90 per batch (82% savings)
- **Speedup: 125x**

---

## Scalability Considerations

### Horizontal Scaling

```
┌──────────────────────────────────────────┐
│          Load Balancer (Nginx)           │
└───────┬──────────┬──────────┬────────────┘
        │          │          │
        ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│  App     │ │  App     │ │  App     │
│Instance 1│ │Instance 2│ │Instance 3│
└─────┬────┘ └─────┬────┘ └─────┬────┘
      │            │            │
      └────────────┴────────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
         ▼                   ▼
    ┌─────────┐         ┌─────────┐
    │   DB    │         │  Redis  │
    │(Primary)│         │ Cluster │
    └─────────┘         └─────────┘
```

### Vertical Scaling

- **CPU:** Multi-core processing with worker pools
- **Memory:** Increased cache size, larger connection pools
- **Disk:** SSD for database, larger storage for documents

### Database Scaling

```
Master-Replica Setup:

┌──────────┐
│  Master  │ ←── Writes
│    DB    │
└────┬─────┘
     │ Replication
     ├─────────────┬─────────────┐
     ▼             ▼             ▼
┌─────────┐   ┌─────────┐   ┌─────────┐
│Replica 1│   │Replica 2│   │Replica 3│ ←── Reads
└─────────┘   └─────────┘   └─────────┘
```

### Cache Scaling

```
Redis Cluster:

┌─────────┐   ┌─────────┐   ┌─────────┐
│ Redis 1 │   │ Redis 2 │   │ Redis 3 │
│Shard 1  │   │Shard 2  │   │Shard 3  │
└─────────┘   └─────────┘   └─────────┘
     │             │             │
     └─────────────┴─────────────┘
              │
         Consistent Hashing
```

---

## Design Patterns

### Used Patterns

1. **Agent Pattern** - Autonomous agents for specialized tasks
2. **Strategy Pattern** - Pluggable LLM providers
3. **Decorator Pattern** - Caching decorator
4. **Factory Pattern** - Document parser factory
5. **Repository Pattern** - Database abstraction
6. **Gateway Pattern** - LLM gateway
7. **Observer Pattern** - Event-driven updates (planned)

### Example: Strategy Pattern (LLM Selection)

```python
class LLMGateway:
    def __init__(self):
        self.providers = {
            'gpt-4': OpenAIProvider(),
            'gpt-3.5-turbo': OpenAIProvider(),
            'claude-2': AnthropicProvider()
        }

    def chat_completion(self, messages: List[Dict], model: str):
        # Strategy pattern - select provider based on model
        provider = self.providers.get(model)
        return provider.complete(messages)
```

---

## Technology Decisions

### Why FastAPI?

- Async support (crucial for performance)
- Automatic API documentation (OpenAPI)
- Type hints support
- High performance (comparable to Node.js)

### Why PostgreSQL?

- ACID compliance
- JSON support (JSONB)
- Partial indexes
- Full-text search
- Mature ecosystem

### Why Redis?

- In-memory speed
- Persistence options
- Distributed caching
- Pub/Sub support
- Rate limiting

### Why LangChain?

- LLM abstraction
- RAG orchestration
- Vector store integration
- Chain composition

---

For more details, see:
- [API Documentation](../api/README.md)
- [Deployment Guide](../deployment/README.md)
- [Performance Optimization](../performance/llm_batching_optimization.md)
- [Future Development](../FUTURE_DEVELOPMENT.md)
