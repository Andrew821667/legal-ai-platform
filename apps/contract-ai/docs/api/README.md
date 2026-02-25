# API Documentation

Complete API reference for Contract-AI-System components.

## Table of Contents

- [Core Services](#core-services)
  - [ContractAnalyzerAgent](#contractanalyzeragent)
  - [DisagreementAgent](#disagreementagent)
  - [ExportAgent](#exportagent)
- [Supporting Services](#supporting-services)
  - [ClauseExtractor](#clauseextractor)
  - [RiskAnalyzer](#riskanalyzer)
  - [RecommendationGenerator](#recommendationgenerator)
  - [MetadataAnalyzer](#metadataanalyzer)
  - [CacheService](#cacheservice)
  - [AsyncAPIClient](#asyncapiclient)
  - [OptimizedQueries](#optimizedqueries)
  - [OCRService](#ocrservice)
  - [FNSAPIClient](#fnsapiclient)
  - [TrackedChangesParser](#trackedchangesparser)
- [Models](#models)
- [Database Operations](#database-operations)

---

## Core Services

### ContractAnalyzerAgent

**Location:** `src/agents/contract_analyzer_agent.py`

Main agent for comprehensive contract analysis.

#### Initialization

```python
from src.agents.contract_analyzer_agent import ContractAnalyzerAgent
from src.services.llm_gateway import LLMGateway

llm_gateway = LLMGateway()
analyzer = ContractAnalyzerAgent(
    llm_gateway=llm_gateway,
    db_session=db_session,
    contract_id="contract_123"
)
```

#### Methods

##### `execute(document_path: str, metadata: Optional[Dict] = None) -> Dict[str, Any]`

Performs full contract analysis.

**Parameters:**
- `document_path` (str): Path to contract file (PDF, DOCX, XML)
- `metadata` (Optional[Dict]): Additional metadata
  - `contract_type` (str): Type of contract
  - `counterparty_inn` (str): Counterparty INN
  - `enable_ocr` (bool): Enable OCR for scanned documents

**Returns:** Dict containing:
- `status` (str): "success" or "failed"
- `analysis_id` (str): Analysis result ID
- `risks` (List[ContractRisk]): Identified risks
- `recommendations` (List[ContractRecommendation]): Recommendations
- `suggested_changes` (List[ContractSuggestedChange]): Suggested changes
- `annotations` (List[ContractAnnotation]): Document annotations
- `metadata` (Dict): Analysis metadata
- `next_action` (str): Next workflow action

**Example:**

```python
result = analyzer.execute(
    document_path="/path/to/contract.pdf",
    metadata={
        "contract_type": "supply",
        "counterparty_inn": "1234567890",
        "enable_ocr": True
    }
)

print(f"Found {len(result['risks'])} risks")
for risk in result['risks']:
    print(f"- {risk.description} (severity: {risk.severity})")
```

##### `get_system_prompt() -> str`

Returns the system prompt for LLM interactions.

**Returns:** System prompt string

---

### DisagreementAgent

**Location:** `src/agents/disagreement_agent.py`

Agent for handling disagreements and generating objections.

#### Initialization

```python
from src.agents.disagreement_agent import DisagreementAgent

disagreement_agent = DisagreementAgent(
    llm_gateway=llm_gateway,
    db_session=db_session,
    analysis_id="analysis_123"
)
```

#### Methods

##### `execute(contract_id: str, disagreement_points: List[str]) -> Dict[str, Any]`

Generates objections for disagreement points.

**Parameters:**
- `contract_id` (str): Contract identifier
- `disagreement_points` (List[str]): List of disagreement descriptions

**Returns:** Dict containing:
- `status` (str): "success" or "failed"
- `disagreement_id` (str): Created disagreement ID
- `objections` (List[DisagreementObjection]): Generated objections
- `total_objections` (int): Number of objections

**Example:**

```python
result = disagreement_agent.execute(
    contract_id="contract_123",
    disagreement_points=[
        "Цена завышена на 15%",
        "Срок поставки не соответствует нашим требованиям"
    ]
)

for objection in result['objections']:
    print(f"Objection: {objection.objection_text}")
    print(f"Legal basis: {objection.legal_basis}")
```

##### `provide_feedback(objection_id: int, effectiveness: str, comments: str) -> Dict[str, Any]`

Records feedback on objection effectiveness.

**Parameters:**
- `objection_id` (int): Objection identifier
- `effectiveness` (str): "effective", "partially_effective", "ineffective"
- `comments` (str): Feedback comments

**Returns:** Feedback record dict

---

### ExportAgent

**Location:** `src/agents/export_agent.py`

Agent for exporting analysis results in various formats.

#### Initialization

```python
from src.agents.export_agent import ExportAgent

export_agent = ExportAgent(
    llm_gateway=llm_gateway,
    db_session=db_session,
    analysis_id="analysis_123"
)
```

#### Methods

##### `execute(export_format: str, options: Optional[Dict] = None) -> Dict[str, Any]`

Exports analysis results in specified format.

**Parameters:**
- `export_format` (str): "pdf", "docx", "json", "email", "edo"
- `options` (Optional[Dict]): Export options
  - `include_annotations` (bool): Include visual annotations
  - `include_recommendations` (bool): Include recommendations
  - `email` (str): Email address for email export
  - `edo_endpoint` (str): EDO system endpoint

**Returns:** Dict containing:
- `status` (str): "success" or "failed"
- `file_path` (str): Path to exported file
- `export_log_id` (str): Export log identifier

**Example:**

```python
# Export to PDF
result = export_agent.execute(
    export_format="pdf",
    options={
        "include_annotations": True,
        "include_recommendations": True
    }
)

print(f"Exported to: {result['file_path']}")

# Send via email
result = export_agent.execute(
    export_format="email",
    options={
        "email": "lawyer@company.com",
        "include_annotations": True
    }
)
```

---

## Supporting Services

### ClauseExtractor

**Location:** `src/services/clause_extractor.py`

Extracts contract structure and individual clauses.

#### Methods

##### `extract_structure(xml_content: str) -> Dict[str, Any]` (static)

Extracts high-level contract structure.

**Parameters:**
- `xml_content` (str): XML representation of contract

**Returns:** Dict containing:
- `parties` (Dict): Contract parties information
- `price` (float): Contract price
- `currency` (str): Currency code
- `term_start` (str): Contract start date
- `term_end` (str): Contract end date
- `contract_type` (str): Type of contract

**Example:**

```python
from src.services.clause_extractor import ClauseExtractor

structure = ClauseExtractor.extract_structure(xml_content)
print(f"Contract type: {structure['contract_type']}")
print(f"Price: {structure['price']} {structure['currency']}")
```

##### `extract_clauses(xml_content: str, max_clauses: int = 50) -> List[Dict[str, Any]]` (static)

Extracts individual contract clauses for analysis.

**Parameters:**
- `xml_content` (str): XML representation of contract
- `max_clauses` (int): Maximum clauses to extract (default: 50)

**Returns:** List of clause dicts:
- `id` (str): Clause identifier
- `text` (str): Clause text
- `xpath` (str): XPath location
- `depth` (int): Nesting depth
- `section` (str): Section name

---

### RiskAnalyzer

**Location:** `src/services/risk_analyzer.py`

Analyzes contract clauses for risks.

#### Initialization

```python
from src.services.risk_analyzer import RiskAnalyzer

risk_analyzer = RiskAnalyzer(llm_gateway=llm_gateway)
```

#### Methods

##### `analyze_clauses_batch(clauses: List[Dict], rag_context: Optional[Dict] = None, batch_size: int = 15) -> List[Dict]`

Analyzes multiple clauses in batches for performance.

**Parameters:**
- `clauses` (List[Dict]): List of clause dicts from ClauseExtractor
- `rag_context` (Optional[Dict]): RAG context for enhanced analysis
- `batch_size` (int): Batch size for processing (default: 15)

**Returns:** List of analysis results

**Example:**

```python
clauses = ClauseExtractor.extract_clauses(xml_content)
analyses = risk_analyzer.analyze_clauses_batch(
    clauses=clauses,
    rag_context=rag_context,
    batch_size=15
)

for analysis in analyses:
    print(f"Clause: {analysis['clause_text'][:50]}...")
    print(f"Risk level: {analysis['risk_level']}")
```

##### `identify_risks(clause_analyses: List[Dict]) -> List[ContractRisk]`

Extracts ContractRisk objects from analyses.

**Parameters:**
- `clause_analyses` (List[Dict]): Analysis results from analyze_clauses_batch

**Returns:** List of ContractRisk model instances

---

### RecommendationGenerator

**Location:** `src/services/recommendation_generator.py`

Generates recommendations and suggested changes.

#### Initialization

```python
from src.services.recommendation_generator import RecommendationGenerator

rec_generator = RecommendationGenerator(
    llm_gateway=llm_gateway,
    system_prompt=system_prompt
)
```

#### Methods

##### `generate_recommendations(risks: List[ContractRisk], rag_context: Dict) -> List[ContractRecommendation]`

Generates recommendations based on identified risks.

**Parameters:**
- `risks` (List[ContractRisk]): Identified risks
- `rag_context` (Dict): RAG context for enhanced recommendations

**Returns:** List of ContractRecommendation instances

##### `generate_suggested_changes(xml_content: str, structure: Dict, risks: List[ContractRisk], recommendations: List[ContractRecommendation], rag_context: Dict) -> List[ContractSuggestedChange]`

Generates specific text changes to fix identified risks.

**Parameters:**
- `xml_content` (str): Contract XML
- `structure` (Dict): Contract structure from ClauseExtractor
- `risks` (List[ContractRisk]): Identified risks
- `recommendations` (List[ContractRecommendation]): Generated recommendations
- `rag_context` (Dict): RAG context

**Returns:** List of ContractSuggestedChange instances

##### `generate_annotations(risks: List[ContractRisk], recommendations: List[ContractRecommendation], suggested_changes: List[ContractSuggestedChange]) -> List[ContractAnnotation]`

Generates visual annotations for document sections.

**Parameters:**
- `risks` (List[ContractRisk]): Identified risks
- `recommendations` (List[ContractRecommendation]): Recommendations
- `suggested_changes` (List[ContractSuggestedChange]): Suggested changes

**Returns:** List of ContractAnnotation instances

---

### MetadataAnalyzer

**Location:** `src/services/metadata_analyzer.py`

Analyzes contract metadata and external data.

#### Initialization

```python
from src.services.metadata_analyzer import MetadataAnalyzer

metadata_analyzer = MetadataAnalyzer(
    llm_gateway=llm_gateway,
    counterparty_service=counterparty_service,
    template_manager=template_manager,
    system_prompt=system_prompt
)
```

#### Methods

##### `check_counterparties(xml_content: str, metadata: Dict) -> Dict[str, Any]`

Checks counterparty information via external APIs.

**Parameters:**
- `xml_content` (str): Contract XML
- `metadata` (Dict): Contract metadata with INN

**Returns:** Dict with counterparty verification results

##### `predict_disputes(xml_content: str, risks: List[ContractRisk], rag_context: Dict) -> Dict[str, Any]`

Predicts probability of disputes arising from contract.

**Parameters:**
- `xml_content` (str): Contract XML
- `risks` (List[ContractRisk]): Identified risks
- `rag_context` (Dict): RAG context

**Returns:** Dict containing:
- `dispute_probability` (float): 0.0 to 1.0
- `dispute_reasons` (List[str]): Potential dispute causes
- `preventive_measures` (List[str]): Suggested preventive actions

##### `determine_next_action(risks: List[ContractRisk], dispute_prediction: Dict) -> str`

Determines next workflow action based on analysis.

**Parameters:**
- `risks` (List[ContractRisk]): Identified risks
- `dispute_prediction` (Dict): Dispute prediction results

**Returns:** "review_queue" or "export"

---

### CacheService

**Location:** `src/services/cache_service.py`

Multi-layer caching service for performance optimization.

#### Initialization

```python
from src.services.cache_service import CacheService

# In-memory only
cache = CacheService(max_size=1000, default_ttl=3600)

# With Redis backend
cache = CacheService(
    redis_url="redis://localhost:6379/0",
    max_size=1000,
    default_ttl=3600
)
```

#### Methods

##### `get(key: str) -> Optional[Any]`

Gets value from cache.

**Parameters:**
- `key` (str): Cache key

**Returns:** Cached value or None

##### `set(key: str, value: Any, ttl: Optional[int] = None) -> None`

Sets value in cache.

**Parameters:**
- `key` (str): Cache key
- `value` (Any): Value to cache (will be serialized)
- `ttl` (Optional[int]): Time-to-live in seconds

##### `cached(ttl: Optional[int] = None, key_prefix: str = "") -> Callable`

Decorator for caching function results.

**Example:**

```python
@cache.cached(ttl=600, key_prefix="fns")
def get_company_info(inn: str):
    # Expensive operation
    return fetch_from_api(inn)

# First call - fetches from API
result = get_company_info("1234567890")

# Second call - returns from cache
result = get_company_info("1234567890")  # Instant!
```

##### `invalidate(key: str) -> None`

Invalidates cache entry.

##### `clear() -> None`

Clears all cache entries.

---

### AsyncAPIClient

**Location:** `src/services/async_api_client.py`

Asynchronous HTTP client for parallel API calls.

#### Initialization

```python
from src.services.async_api_client import AsyncAPIClient

client = AsyncAPIClient(
    timeout=30,
    max_connections=100,
    max_retries=3,
    retry_delay=1.0,
    rate_limit_requests=100,  # Max 100 requests
    rate_limit_period=1.0     # per 1 second
)
```

#### Methods

##### `async get(url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None, retry: bool = True) -> Dict[str, Any]`

Performs async GET request.

**Parameters:**
- `url` (str): Request URL
- `params` (Optional[Dict]): Query parameters
- `headers` (Optional[Dict]): HTTP headers
- `retry` (bool): Enable automatic retries

**Returns:** Response JSON

**Example:**

```python
async with AsyncAPIClient() as client:
    data = await client.get(
        "https://api.example.com/companies",
        params={"inn": "1234567890"}
    )
```

##### `async batch_get(urls: List[str], params: Optional[List[Dict]] = None, headers: Optional[Dict] = None) -> List[Optional[Dict]]`

Batch async GET requests (parallel).

**Parameters:**
- `urls` (List[str]): List of URLs
- `params` (Optional[List[Dict]]): List of params for each URL
- `headers` (Optional[Dict]): Common headers

**Returns:** List of responses (None for failed requests)

**Example:**

```python
async with AsyncAPIClient() as client:
    urls = [
        "https://api.example.com/company/1",
        "https://api.example.com/company/2",
        "https://api.example.com/company/3"
    ]
    results = await client.batch_get(urls)

    for result in results:
        if result:
            print(f"Company: {result['name']}")
```

##### `run_async(coro)` (utility function)

Runs async coroutine from sync context.

**Example:**

```python
from src.services.async_api_client import run_async

def sync_function():
    async def async_work():
        async with AsyncAPIClient() as client:
            return await client.get("https://api.example.com/data")

    result = run_async(async_work())
    return result
```

---

### OptimizedQueries

**Location:** `src/services/optimized_queries.py`

Optimized database queries with eager loading to eliminate N+1 problems.

#### Initialization

```python
from src.services.optimized_queries import OptimizedQueries

optimized = OptimizedQueries(db_session=db_session)
```

#### Methods

##### `get_disagreements_with_objections(start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, limit: Optional[int] = None) -> List[Disagreement]`

Gets disagreements with objections eagerly loaded (1 query vs 1+N).

**Parameters:**
- `start_date` (Optional[datetime]): Filter by creation date (from)
- `end_date` (Optional[datetime]): Filter by creation date (to)
- `limit` (Optional[int]): Max results

**Returns:** List of Disagreement objects with objections loaded

**Example:**

```python
# OLD WAY (N+1 problem):
disagreements = db.query(Disagreement).all()  # 1 query
for d in disagreements:
    objections = db.query(DisagreementObjection).filter_by(
        disagreement_id=d.id
    ).all()  # N queries!

# NEW WAY (optimized):
disagreements = optimized.get_disagreements_with_objections()  # 1 query
for d in disagreements:
    objections = d.objections  # Already loaded!
```

##### `get_disagreements_with_objections_and_feedback(disagreement_ids: Optional[List[str]] = None, min_effectiveness: Optional[float] = None) -> List[Disagreement]`

Gets disagreements with objections AND feedback (3 levels deep, 1 query).

##### `get_contracts_with_risks(status: Optional[str] = None, assigned_to: Optional[str] = None, risk_level: Optional[str] = None, days_back: int = 30) -> List[Contract]`

Gets contracts with risks eagerly loaded.

##### `get_high_risk_contracts_summary() -> List[Dict[str, Any]]`

Gets summary of high-risk contracts using aggregation (fast).

##### `get_objections_batch(disagreement_ids: List[str]) -> Dict[str, List[DisagreementObjection]]`

Batch loads objections for multiple disagreements (1 query).

---

### OCRService

**Location:** `src/services/ocr_service.py`

OCR service for text extraction from scanned documents.

#### Initialization

```python
from src.services.ocr_service import OCRService

ocr = OCRService(
    language='rus+eng',  # Tesseract language(s)
    dpi=300,            # Image resolution
    tesseract_path='/usr/bin/tesseract'  # Optional custom path
)
```

#### Methods

##### `extract_text_from_pdf(pdf_path: str, max_pages: Optional[int] = None) -> str`

Extracts text from scanned PDF using OCR.

**Parameters:**
- `pdf_path` (str): Path to PDF file
- `max_pages` (Optional[int]): Maximum pages to process (None = all)

**Returns:** Extracted text

**Example:**

```python
text = ocr.extract_text_from_pdf(
    "/path/to/scanned_contract.pdf",
    max_pages=10
)
print(f"Extracted {len(text)} characters")
```

##### `extract_text_from_image(image_path: str) -> str`

Extracts text from image file.

##### `detect_if_scanned(pdf_path: str, threshold: int = 100) -> Tuple[bool, str]`

Detects if PDF is scanned (image-based) or text-based.

**Returns:** Tuple of (is_scanned, reason)

---

### FNSAPIClient

**Location:** `src/services/fns_api.py`

Client for FNS (Federal Tax Service) EGRUL API.

#### Initialization

```python
from src.services.fns_api import FNSAPIClient

# Official FNS API
fns = FNSAPIClient()

# With Dadata.ru premium
fns = FNSAPIClient(
    api_key="your_dadata_api_key",
    use_dadata=True
)
```

#### Methods

##### `get_company_info(inn: str) -> Dict[str, Any]`

Gets company information by INN.

**Parameters:**
- `inn` (str): INN (10 or 12 digits)

**Returns:** Dict containing:
- `found` (bool): Whether company was found
- `full_name` (str): Full company name
- `short_name` (str): Short name
- `inn` (str): INN
- `ogrn` (str): OGRN
- `kpp` (str): KPP
- `address` (str): Legal address
- `director` (str): Director name
- `registration_date` (str): Registration date
- `status` (str): Company status

**Example:**

```python
company = fns.get_company_info("1234567890")
if company['found']:
    print(f"Company: {company['full_name']}")
    print(f"Director: {company['director']}")
    print(f"Status: {company['status']}")
```

##### `check_inn_format(inn: str) -> Dict[str, Any]`

Validates INN format and checksum.

**Returns:** Dict with validation results

---

### TrackedChangesParser

**Location:** `src/services/tracked_changes_parser.py`

Parser for DOCX tracked changes (revision marks).

#### Initialization

```python
from src.services.tracked_changes_parser import TrackedChangesParser

parser = TrackedChangesParser()
```

#### Methods

##### `parse_tracked_changes(docx_path: str) -> List[Dict[str, Any]]`

Parses tracked changes from DOCX file.

**Parameters:**
- `docx_path` (str): Path to DOCX file

**Returns:** List of change dicts:
- `type` (str): "insertion", "deletion", "move_from", "move_to"
- `author` (str): Change author
- `date` (str): Change timestamp
- `text` (str): Changed text
- `change_id` (str): Change identifier

**Example:**

```python
changes = parser.parse_tracked_changes("/path/to/contract.docx")

for change in changes:
    print(f"{change['type']} by {change['author']}: {change['text'][:50]}")
```

##### `accept_all_changes(docx_path: str, output_path: str) -> None`

Accepts all tracked changes in document.

##### `reject_all_changes(docx_path: str, output_path: str) -> None`

Rejects all tracked changes in document.

---

## Models

### ContractRisk

**Location:** `src/models/analyzer_models.py`

Represents an identified contract risk.

**Fields:**
- `id` (int): Primary key
- `analysis_id` (str): Foreign key to AnalysisResult
- `contract_id` (str): Foreign key to Contract
- `risk_type` (str): Type of risk
- `severity` (str): "critical", "high", "medium", "low"
- `description` (str): Risk description
- `affected_clause` (str): Affected contract clause
- `legal_basis` (str): Legal basis for risk
- `potential_consequences` (str): Potential consequences
- `created_at` (datetime): Creation timestamp

### ContractRecommendation

**Location:** `src/models/analyzer_models.py`

Represents a recommendation for risk mitigation.

**Fields:**
- `id` (int): Primary key
- `analysis_id` (str): Foreign key to AnalysisResult
- `contract_id` (str): Foreign key to Contract
- `category` (str): Recommendation category
- `priority` (str): "high", "medium", "low"
- `description` (str): Recommendation text
- `implementation_steps` (str): Steps to implement
- `legal_references` (str): Legal references
- `created_at` (datetime): Creation timestamp

### Disagreement

**Location:** `src/models/disagreement_models.py`

Represents a contract disagreement.

**Fields:**
- `id` (str): Primary key (UUID)
- `contract_id` (str): Foreign key to Contract
- `analysis_id` (str): Foreign key to AnalysisResult
- `disagreement_points` (JSON): List of disagreement points
- `status` (str): "draft", "submitted", "resolved"
- `effectiveness_score` (float): Effectiveness score (0.0-1.0)
- `created_at` (datetime): Creation timestamp
- `objections` (relationship): List of DisagreementObjection

### DisagreementObjection

**Location:** `src/models/disagreement_models.py`

Represents an objection to a disagreement point.

**Fields:**
- `id` (int): Primary key
- `disagreement_id` (str): Foreign key to Disagreement
- `objection_text` (str): Objection text
- `legal_basis` (str): Legal basis
- `supporting_documents` (JSON): Supporting document references
- `priority` (str): "high", "medium", "low"
- `created_at` (datetime): Creation timestamp
- `feedback` (relationship): List of DisagreementFeedback

---

## Database Operations

### Session Management

```python
from src.models.database import get_db

# Using context manager
with get_db() as db:
    contracts = db.query(Contract).all()

# Or manual management
db = next(get_db())
try:
    contracts = db.query(Contract).all()
    db.commit()
finally:
    db.close()
```

### Optimized Queries

```python
from src.services.optimized_queries import OptimizedQueries

# Use optimized queries to avoid N+1 problems
optimized = OptimizedQueries(db)

# Instead of:
# disagreements = db.query(Disagreement).all()  # N+1 problem!
# Use:
disagreements = optimized.get_disagreements_with_objections()
```

### Transaction Management

```python
from src.models.database import get_db

with get_db() as db:
    try:
        # Create contract
        contract = Contract(...)
        db.add(contract)
        db.flush()  # Get contract ID without committing

        # Create analysis
        analysis = AnalysisResult(contract_id=contract.id, ...)
        db.add(analysis)

        db.commit()  # Commit transaction
    except Exception as e:
        db.rollback()  # Rollback on error
        raise
```

---

## Complete Usage Example

```python
from src.agents.contract_analyzer_agent import ContractAnalyzerAgent
from src.agents.disagreement_agent import DisagreementAgent
from src.agents.export_agent import ExportAgent
from src.services.llm_gateway import LLMGateway
from src.services.cache_service import CacheService
from src.models.database import get_db

# Initialize services
cache = CacheService(redis_url="redis://localhost:6379/0")
llm_gateway = LLMGateway(cache=cache)

with get_db() as db:
    # Step 1: Analyze contract
    analyzer = ContractAnalyzerAgent(
        llm_gateway=llm_gateway,
        db_session=db,
        contract_id="contract_123"
    )

    analysis_result = analyzer.execute(
        document_path="/path/to/contract.pdf",
        metadata={
            "contract_type": "supply",
            "counterparty_inn": "1234567890",
            "enable_ocr": True
        }
    )

    print(f"Analysis complete: {len(analysis_result['risks'])} risks found")

    # Step 2: Generate disagreement objections
    if analysis_result['risks']:
        disagreement_agent = DisagreementAgent(
            llm_gateway=llm_gateway,
            db_session=db,
            analysis_id=analysis_result['analysis_id']
        )

        disagreement_result = disagreement_agent.execute(
            contract_id="contract_123",
            disagreement_points=[
                "Цена завышена на 15%",
                "Срок поставки не соответствует требованиям"
            ]
        )

        print(f"Generated {len(disagreement_result['objections'])} objections")

    # Step 3: Export results
    export_agent = ExportAgent(
        llm_gateway=llm_gateway,
        db_session=db,
        analysis_id=analysis_result['analysis_id']
    )

    export_result = export_agent.execute(
        export_format="pdf",
        options={
            "include_annotations": True,
            "include_recommendations": True
        }
    )

    print(f"Exported to: {export_result['file_path']}")
```

---

## Error Handling

All services raise specific exceptions:

```python
from src.utils.exceptions import (
    ContractAnalysisError,
    LLMGatewayError,
    CacheError,
    OCRError,
    APIClientError
)

try:
    result = analyzer.execute(document_path)
except ContractAnalysisError as e:
    logger.error(f"Analysis failed: {e}")
except LLMGatewayError as e:
    logger.error(f"LLM call failed: {e}")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
```

---

## Performance Tips

1. **Use Caching:**
   ```python
   cache = CacheService(redis_url="redis://localhost:6379/0")
   llm_gateway = LLMGateway(cache=cache)
   ```

2. **Use Batch Processing:**
   ```python
   # Analyze multiple clauses in batches
   risk_analyzer.analyze_clauses_batch(clauses, batch_size=15)
   ```

3. **Use Optimized Queries:**
   ```python
   # Avoid N+1 problems
   optimized = OptimizedQueries(db)
   disagreements = optimized.get_disagreements_with_objections()
   ```

4. **Use Async for External APIs:**
   ```python
   async with AsyncAPIClient() as client:
       results = await client.batch_get(urls)  # Parallel requests
   ```

5. **Enable OCR Only When Needed:**
   ```python
   # OCR is slow - only use for scanned documents
   analyzer.execute(document_path, metadata={"enable_ocr": False})
   ```

---

## API Rate Limits

### External APIs

- **FNS EGRUL API:** 10 requests/minute (official), unlimited (Dadata.ru premium)
- **OpenAI API:** Varies by plan (see OpenAI docs)
- **Anthropic Claude API:** Varies by plan (see Anthropic docs)

### Internal Rate Limiting

Configure in `AsyncAPIClient`:

```python
client = AsyncAPIClient(
    rate_limit_requests=100,  # Max requests
    rate_limit_period=1.0     # Per second
)
```

---

For more examples, see [Usage Examples](../examples/README.md).

For architecture details, see [Architecture Documentation](../architecture/README.md).

For deployment, see [Deployment Guide](../deployment/README.md).
