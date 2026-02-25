# Usage Examples

Practical examples for using the Contract-AI-System.

## Table of Contents

- [Basic Contract Analysis](#basic-contract-analysis)
- [Advanced Analysis with OCR](#advanced-analysis-with-ocr)
- [Disagreement Handling](#disagreement-handling)
- [Export Operations](#export-operations)
- [Performance Optimization](#performance-optimization)
- [Batch Processing](#batch-processing)
- [Integration Examples](#integration-examples)
- [Error Handling](#error-handling)

---

## Basic Contract Analysis

### Simple Analysis

```python
from src.agents.contract_analyzer_agent import ContractAnalyzerAgent
from src.services.llm_gateway import LLMGateway
from src.models.database import get_db

# Initialize services
llm_gateway = LLMGateway()

with get_db() as db:
    # Create analyzer agent
    analyzer = ContractAnalyzerAgent(
        llm_gateway=llm_gateway,
        db_session=db,
        contract_id="contract_001"
    )

    # Analyze contract
    result = analyzer.execute(
        document_path="/path/to/contract.pdf",
        metadata={
            "contract_type": "supply",
            "counterparty_inn": "1234567890"
        }
    )

    # Print results
    print(f"Analysis ID: {result['analysis_id']}")
    print(f"Status: {result['status']}")
    print(f"Found {len(result['risks'])} risks")

    # Print risks by severity
    for risk in result['risks']:
        print(f"\n[{risk.severity.upper()}] {risk.risk_type}")
        print(f"Description: {risk.description}")
        print(f"Affected Clause: {risk.affected_clause}")
        print(f"Legal Basis: {risk.legal_basis}")

    # Print recommendations
    print(f"\nRecommendations: {len(result['recommendations'])}")
    for rec in result['recommendations']:
        print(f"- [{rec.priority.upper()}] {rec.description}")

    # Check next action
    print(f"\nNext Action: {result['next_action']}")
```

**Output:**
```
Analysis ID: analysis_123abc
Status: success
Found 5 risks

[CRITICAL] Unlimited Liability
Description: Договор содержит положения о неограниченной ответственности...
Affected Clause: Раздел 5.2, пункт 3
Legal Basis: Статья 401 ГК РФ...

[HIGH] Payment Terms
Description: Условия оплаты не содержат защитных механизмов...
Affected Clause: Раздел 3.1
Legal Basis: Статья 486 ГК РФ...

Recommendations: 8
- [HIGH] Добавить ограничение ответственности суммой договора
- [MEDIUM] Включить условие об аванс платеже

Next Action: review_queue
```

---

## Advanced Analysis with OCR

### Scanned Document Analysis

```python
from src.agents.contract_analyzer_agent import ContractAnalyzerAgent
from src.services.llm_gateway import LLMGateway
from src.services.ocr_service import OCRService
from src.models.database import get_db

# Initialize OCR service
ocr = OCRService(
    language='rus+eng',  # Russian + English
    dpi=300             # High quality
)

# Check if document is scanned
pdf_path = "/path/to/scanned_contract.pdf"
is_scanned, reason = ocr.detect_if_scanned(pdf_path)

print(f"Is scanned: {is_scanned}")
print(f"Reason: {reason}")

# Analyze with OCR enabled
llm_gateway = LLMGateway()

with get_db() as db:
    analyzer = ContractAnalyzerAgent(
        llm_gateway=llm_gateway,
        db_session=db,
        contract_id="contract_002"
    )

    result = analyzer.execute(
        document_path=pdf_path,
        metadata={
            "contract_type": "lease",
            "enable_ocr": True,  # Enable OCR
            "ocr_max_pages": 10  # Limit to first 10 pages
        }
    )

    print(f"OCR processed: {result['metadata'].get('ocr_used', False)}")
    print(f"Pages processed: {result['metadata'].get('ocr_pages', 0)}")
```

**Output:**
```
Is scanned: True
Reason: Low text density (15 characters), likely image-based PDF

OCR processed: True
Pages processed: 10
Analysis ID: analysis_456def
Found 3 risks
```

---

## Disagreement Handling

### Generate Objections

```python
from src.agents.disagreement_agent import DisagreementAgent
from src.services.llm_gateway import LLMGateway
from src.models.database import get_db

llm_gateway = LLMGateway()

with get_db() as db:
    # Create disagreement agent
    disagreement_agent = DisagreementAgent(
        llm_gateway=llm_gateway,
        db_session=db,
        analysis_id="analysis_123abc"
    )

    # Define disagreement points
    disagreement_points = [
        "Цена завышена на 15% по сравнению с рыночными аналогами",
        "Срок поставки 60 дней не соответствует нашим требованиям (30 дней)",
        "Условие о неустойке 0.1% является несправедливым"
    ]

    # Generate objections
    result = disagreement_agent.execute(
        contract_id="contract_001",
        disagreement_points=disagreement_points
    )

    print(f"Disagreement ID: {result['disagreement_id']}")
    print(f"Total objections: {result['total_objections']}")

    # Print each objection
    for i, objection in enumerate(result['objections'], 1):
        print(f"\n=== Objection {i} ===")
        print(f"Priority: {objection.priority}")
        print(f"\nОбоснование:")
        print(objection.objection_text)
        print(f"\nПравовая база:")
        print(objection.legal_basis)
        print(f"\nПодтверждающие документы:")
        print(objection.supporting_documents)
```

**Output:**
```
Disagreement ID: disagreement_789ghi
Total objections: 3

=== Objection 1 ===
Priority: high

Обоснование:
Цена, указанная в договоре, превышает среднерыночную стоимость аналогичных
товаров на 15%. Согласно проведенному анализу рынка, справедливая цена
составляет 85,000 руб. вместо указанных 100,000 руб...

Правовая база:
- Статья 424 ГК РФ (Цена договора)
- Статья 10 ГК РФ (Пределы осуществления гражданских прав)
- Постановление Пленума ВАС РФ №16 от 14.03.2014...

Подтверждающие документы:
["Аналитическая записка о рыночных ценах", "Коммерческие предложения конкурентов"]
```

### Provide Feedback

```python
from src.agents.disagreement_agent import DisagreementAgent

with get_db() as db:
    disagreement_agent = DisagreementAgent(
        llm_gateway=llm_gateway,
        db_session=db,
        analysis_id="analysis_123abc"
    )

    # Provide feedback on objection effectiveness
    feedback = disagreement_agent.provide_feedback(
        objection_id=1,
        effectiveness="effective",
        comments="Контрагент согласился пересмотреть цену. Снижение на 12%."
    )

    print(f"Feedback recorded: {feedback['feedback_id']}")
    print(f"Effectiveness: {feedback['effectiveness']}")
```

---

## Export Operations

### Export to PDF

```python
from src.agents.export_agent import ExportAgent
from src.services.llm_gateway import LLMGateway
from src.models.database import get_db

llm_gateway = LLMGateway()

with get_db() as db:
    export_agent = ExportAgent(
        llm_gateway=llm_gateway,
        db_session=db,
        analysis_id="analysis_123abc"
    )

    # Export to PDF with annotations
    result = export_agent.execute(
        export_format="pdf",
        options={
            "include_annotations": True,      # Visual highlights
            "include_recommendations": True,  # Recommendations section
            "include_suggested_changes": True,# Suggested changes section
            "language": "ru"                  # Russian language
        }
    )

    print(f"Export successful: {result['status']}")
    print(f"File path: {result['file_path']}")
    print(f"File size: {result['file_size']} bytes")
    print(f"Export log ID: {result['export_log_id']}")
```

### Export to DOCX

```python
# Export to editable DOCX
result = export_agent.execute(
    export_format="docx",
    options={
        "include_annotations": True,
        "include_recommendations": True,
        "include_suggested_changes": True,
        "enable_track_changes": True  # Enable tracked changes in DOCX
    }
)

print(f"DOCX exported: {result['file_path']}")
```

### Send via Email

```python
# Send analysis results via email
result = export_agent.execute(
    export_format="email",
    options={
        "email": "lawyer@company.com",
        "cc": ["manager@company.com"],
        "subject": "Анализ договора поставки №123",
        "body": "Направляем результаты анализа договора.",
        "include_annotations": True,
        "include_recommendations": True
    }
)

print(f"Email sent: {result['status']}")
print(f"Recipients: {result['recipients']}")
```

### Export to EDO System

```python
# Export to Electronic Document Management system
result = export_agent.execute(
    export_format="edo",
    options={
        "edo_endpoint": "https://edo.company.com/api/upload",
        "edo_api_key": "your_edo_api_key",
        "document_type": "contract_analysis",
        "metadata": {
            "department": "legal",
            "priority": "high"
        }
    }
)

print(f"EDO upload: {result['status']}")
print(f"EDO document ID: {result['edo_document_id']}")
```

---

## Performance Optimization

### Using Cache

```python
from src.services.cache_service import CacheService
from src.services.llm_gateway import LLMGateway
from src.services.fns_api import FNSAPIClient

# Initialize cache with Redis
cache = CacheService(
    redis_url="redis://localhost:6379/0",
    max_size=10000,
    default_ttl=3600  # 1 hour
)

# Use cache with LLM Gateway
llm_gateway = LLMGateway(cache=cache)

# Use cache decorator for expensive operations
fns_client = FNSAPIClient()

@cache.cached(ttl=600, key_prefix="fns")
def get_company_info_cached(inn: str):
    return fns_client.get_company_info(inn)

# First call - fetches from API (slow)
import time
start = time.time()
company1 = get_company_info_cached("1234567890")
print(f"First call: {time.time() - start:.2f}s")  # ~2.5s

# Second call - returns from cache (fast)
start = time.time()
company2 = get_company_info_cached("1234567890")
print(f"Second call: {time.time() - start:.2f}s")  # ~0.001s

# Check cache statistics
stats = cache.get_stats()
print(f"Cache hits: {stats['hits']}")
print(f"Cache misses: {stats['misses']}")
print(f"Hit rate: {stats['hit_rate']:.1%}")
```

**Output:**
```
First call: 2.47s
Second call: 0.001s
Cache hits: 1
Cache misses: 1
Hit rate: 50.0%
```

### Using Async API Client

```python
import asyncio
from src.services.async_api_client import AsyncAPIClient

async def fetch_multiple_companies():
    """Fetch company info for multiple INNs in parallel"""

    inns = ["1234567890", "0987654321", "1111111111"]
    urls = [f"https://api.example.com/companies/{inn}" for inn in inns]

    async with AsyncAPIClient(max_connections=10) as client:
        # Parallel requests
        results = await client.batch_get(urls)

        for inn, result in zip(inns, results):
            if result:
                print(f"{inn}: {result['name']}")
            else:
                print(f"{inn}: Failed to fetch")

# Run async function
asyncio.run(fetch_multiple_companies())

# Or from sync context
from src.services.async_api_client import run_async
results = run_async(fetch_multiple_companies())
```

**Output:**
```
1234567890: ООО "Компания 1"
0987654321: АО "Компания 2"
1111111111: ИП Иванов И.И.
Total time: 0.8s (vs 6.9s sequential)
```

### Using Optimized Queries

```python
from src.services.optimized_queries import OptimizedQueries
from src.models.database import get_db

with get_db() as db:
    optimized = OptimizedQueries(db_session=db)

    # BAD: N+1 problem
    # disagreements = db.query(Disagreement).all()  # 1 query
    # for d in disagreements:
    #     objections = db.query(DisagreementObjection).filter_by(
    #         disagreement_id=d.id
    #     ).all()  # N queries!

    # GOOD: Optimized with eager loading
    disagreements = optimized.get_disagreements_with_objections(
        limit=100
    )  # 1 query total!

    for d in disagreements:
        print(f"Disagreement: {d.id}")
        print(f"Objections: {len(d.objections)}")  # Already loaded!

    # Even better: 3 levels deep
    disagreements = optimized.get_disagreements_with_objections_and_feedback()

    for d in disagreements:
        for obj in d.objections:
            for fb in obj.feedback:  # All loaded in 1 query!
                print(f"Feedback: {fb.effectiveness}")
```

---

## Batch Processing

### Batch Contract Analysis

```python
from src.agents.contract_analyzer_agent import ContractAnalyzerAgent
from src.services.llm_gateway import LLMGateway
from src.services.cache_service import CacheService
from src.models.database import get_db
import asyncio
from pathlib import Path

async def analyze_contracts_batch(contract_paths: list):
    """Analyze multiple contracts in batch"""

    # Initialize with caching
    cache = CacheService(redis_url="redis://localhost:6379/0")
    llm_gateway = LLMGateway(cache=cache)

    results = []

    with get_db() as db:
        for i, path in enumerate(contract_paths, 1):
            contract_id = f"contract_{i:03d}"

            analyzer = ContractAnalyzerAgent(
                llm_gateway=llm_gateway,
                db_session=db,
                contract_id=contract_id
            )

            print(f"Analyzing {i}/{len(contract_paths)}: {Path(path).name}")

            result = analyzer.execute(
                document_path=path,
                metadata={"contract_type": "supply"}
            )

            results.append({
                "contract_id": contract_id,
                "file": Path(path).name,
                "status": result['status'],
                "risks": len(result['risks']),
                "critical_risks": len([
                    r for r in result['risks']
                    if r.severity == 'critical'
                ])
            })

    return results

# Analyze 10 contracts
contract_files = [
    "/path/to/contract1.pdf",
    "/path/to/contract2.pdf",
    "/path/to/contract3.pdf",
    # ... more files
]

import time
start = time.time()
results = asyncio.run(analyze_contracts_batch(contract_files))
duration = time.time() - start

# Print summary
print(f"\n=== Batch Analysis Complete ===")
print(f"Total contracts: {len(results)}")
print(f"Total time: {duration:.2f}s")
print(f"Average time per contract: {duration/len(results):.2f}s")

total_risks = sum(r['risks'] for r in results)
critical_risks = sum(r['critical_risks'] for r in results)

print(f"Total risks found: {total_risks}")
print(f"Critical risks: {critical_risks}")

# Print individual results
print("\n=== Individual Results ===")
for r in results:
    print(f"{r['contract_id']}: {r['file']} - {r['risks']} risks "
          f"({r['critical_risks']} critical)")
```

**Output:**
```
Analyzing 1/10: contract_supply_001.pdf
Analyzing 2/10: contract_supply_002.pdf
...

=== Batch Analysis Complete ===
Total contracts: 10
Total time: 47.3s
Average time per contract: 4.7s
Total risks found: 42
Critical risks: 8

=== Individual Results ===
contract_001: contract_supply_001.pdf - 5 risks (1 critical)
contract_002: contract_supply_002.pdf - 3 risks (0 critical)
...
```

---

## Integration Examples

### REST API Integration

```python
import requests

# API endpoint
BASE_URL = "http://localhost:8000/api/v1"

# 1. Upload and analyze contract
files = {"file": open("contract.pdf", "rb")}
data = {
    "contract_type": "supply",
    "counterparty_inn": "1234567890"
}

response = requests.post(
    f"{BASE_URL}/contracts/analyze",
    files=files,
    data=data
)

result = response.json()
analysis_id = result['analysis_id']

print(f"Analysis ID: {analysis_id}")
print(f"Risks found: {len(result['risks'])}")

# 2. Get analysis results
response = requests.get(
    f"{BASE_URL}/contracts/analysis/{analysis_id}"
)

analysis = response.json()
print(f"Status: {analysis['status']}")

# 3. Generate disagreement objections
response = requests.post(
    f"{BASE_URL}/disagreements/generate",
    json={
        "analysis_id": analysis_id,
        "disagreement_points": [
            "Цена завышена на 15%",
            "Срок поставки не соответствует требованиям"
        ]
    }
)

disagreement = response.json()
print(f"Objections generated: {len(disagreement['objections'])}")

# 4. Export to PDF
response = requests.post(
    f"{BASE_URL}/export/{analysis_id}",
    json={
        "format": "pdf",
        "options": {
            "include_annotations": True,
            "include_recommendations": True
        }
    }
)

export_result = response.json()

# Download file
file_response = requests.get(export_result['download_url'])
with open("analysis_result.pdf", "wb") as f:
    f.write(file_response.content)

print("PDF downloaded successfully")
```

### Python SDK Integration

```python
from contract_ai_sdk import ContractAIClient

# Initialize client
client = ContractAIClient(
    api_key="your_api_key",
    base_url="http://localhost:8000"
)

# Analyze contract
analysis = client.analyze_contract(
    file_path="/path/to/contract.pdf",
    contract_type="supply",
    counterparty_inn="1234567890"
)

print(f"Analysis ID: {analysis.id}")
print(f"Risks: {len(analysis.risks)}")

# Generate objections
disagreement = client.generate_objections(
    analysis_id=analysis.id,
    points=["Цена завышена на 15%"]
)

# Export
pdf_path = client.export_to_pdf(
    analysis_id=analysis.id,
    include_annotations=True
)

print(f"Exported to: {pdf_path}")
```

---

## Error Handling

### Comprehensive Error Handling

```python
from src.agents.contract_analyzer_agent import ContractAnalyzerAgent
from src.services.llm_gateway import LLMGateway
from src.models.database import get_db
from src.utils.exceptions import (
    ContractAnalysisError,
    LLMGatewayError,
    DocumentParsingError,
    OCRError
)
from loguru import logger

def analyze_contract_safe(document_path: str):
    """Analyze contract with comprehensive error handling"""

    llm_gateway = LLMGateway()

    try:
        with get_db() as db:
            analyzer = ContractAnalyzerAgent(
                llm_gateway=llm_gateway,
                db_session=db,
                contract_id="contract_001"
            )

            result = analyzer.execute(
                document_path=document_path,
                metadata={
                    "contract_type": "supply",
                    "enable_ocr": True
                }
            )

            return result

    except DocumentParsingError as e:
        logger.error(f"Failed to parse document: {e}")
        return {
            "status": "failed",
            "error": "document_parsing_error",
            "message": str(e)
        }

    except OCRError as e:
        logger.error(f"OCR processing failed: {e}")
        # Retry without OCR
        try:
            result = analyzer.execute(
                document_path=document_path,
                metadata={"enable_ocr": False}
            )
            logger.warning("Retried without OCR successfully")
            return result
        except Exception as retry_error:
            logger.error(f"Retry failed: {retry_error}")
            return {"status": "failed", "error": "ocr_error"}

    except LLMGatewayError as e:
        logger.error(f"LLM API call failed: {e}")
        return {
            "status": "failed",
            "error": "llm_error",
            "message": "Failed to communicate with AI service"
        }

    except ContractAnalysisError as e:
        logger.error(f"Analysis failed: {e}")
        return {
            "status": "failed",
            "error": "analysis_error",
            "message": str(e)
        }

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return {
            "status": "failed",
            "error": "unknown_error",
            "message": "An unexpected error occurred"
        }

# Use safe analyzer
result = analyze_contract_safe("/path/to/contract.pdf")

if result['status'] == 'success':
    print(f"Analysis successful: {len(result['risks'])} risks found")
else:
    print(f"Analysis failed: {result['error']}")
    print(f"Message: {result['message']}")
```

### Retry Logic

```python
import time
from functools import wraps

def retry_on_failure(max_retries=3, delay=1.0, backoff=2.0):
    """Decorator for retrying failed operations"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay

            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"Max retries ({max_retries}) reached")
                        raise

                    logger.warning(
                        f"Attempt {retries}/{max_retries} failed: {e}. "
                        f"Retrying in {current_delay}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff

        return wrapper
    return decorator

# Use retry decorator
@retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
def analyze_with_retry(document_path: str):
    analyzer = ContractAnalyzerAgent(...)
    return analyzer.execute(document_path)

# Will retry up to 3 times with exponential backoff
result = analyze_with_retry("/path/to/contract.pdf")
```

---

## Complete Workflow Example

```python
#!/usr/bin/env python
"""
Complete workflow: Analysis -> Disagreement -> Export
"""

from src.agents.contract_analyzer_agent import ContractAnalyzerAgent
from src.agents.disagreement_agent import DisagreementAgent
from src.agents.export_agent import ExportAgent
from src.services.llm_gateway import LLMGateway
from src.services.cache_service import CacheService
from src.models.database import get_db
from loguru import logger

def complete_contract_workflow(contract_path: str, contract_type: str):
    """Complete contract analysis workflow"""

    # Initialize services with caching
    cache = CacheService(redis_url="redis://localhost:6379/0")
    llm_gateway = LLMGateway(cache=cache)

    contract_id = "contract_workflow_001"

    with get_db() as db:
        # Step 1: Analyze contract
        logger.info("Step 1: Analyzing contract...")
        analyzer = ContractAnalyzerAgent(
            llm_gateway=llm_gateway,
            db_session=db,
            contract_id=contract_id
        )

        analysis_result = analyzer.execute(
            document_path=contract_path,
            metadata={
                "contract_type": contract_type,
                "enable_ocr": True
            }
        )

        logger.info(f"Analysis complete. Found {len(analysis_result['risks'])} risks")

        # Step 2: Generate disagreement objections (if high-risk)
        critical_risks = [r for r in analysis_result['risks'] if r.severity == 'critical']

        if critical_risks:
            logger.info("Step 2: Generating objections for critical risks...")

            disagreement_agent = DisagreementAgent(
                llm_gateway=llm_gateway,
                db_session=db,
                analysis_id=analysis_result['analysis_id']
            )

            disagreement_points = [r.description for r in critical_risks]

            disagreement_result = disagreement_agent.execute(
                contract_id=contract_id,
                disagreement_points=disagreement_points
            )

            logger.info(f"Generated {len(disagreement_result['objections'])} objections")
        else:
            logger.info("Step 2: Skipped (no critical risks)")
            disagreement_result = None

        # Step 3: Export results
        logger.info("Step 3: Exporting results...")

        export_agent = ExportAgent(
            llm_gateway=llm_gateway,
            db_session=db,
            analysis_id=analysis_result['analysis_id']
        )

        # Export to PDF
        pdf_result = export_agent.execute(
            export_format="pdf",
            options={
                "include_annotations": True,
                "include_recommendations": True,
                "include_suggested_changes": True
            }
        )

        logger.info(f"PDF exported: {pdf_result['file_path']}")

        # Export to DOCX
        docx_result = export_agent.execute(
            export_format="docx",
            options={
                "include_annotations": True,
                "enable_track_changes": True
            }
        )

        logger.info(f"DOCX exported: {docx_result['file_path']}")

        # Send email notification
        email_result = export_agent.execute(
            export_format="email",
            options={
                "email": "lawyer@company.com",
                "subject": f"Анализ договора: {contract_type}",
                "include_recommendations": True
            }
        )

        logger.info(f"Email sent to: {email_result['recipients']}")

        # Step 4: Summary
        logger.info("=== Workflow Complete ===")
        logger.info(f"Contract: {contract_id}")
        logger.info(f"Analysis ID: {analysis_result['analysis_id']}")
        logger.info(f"Total risks: {len(analysis_result['risks'])}")
        logger.info(f"Critical risks: {len(critical_risks)}")
        logger.info(f"Objections: {len(disagreement_result['objections']) if disagreement_result else 0}")
        logger.info(f"PDF: {pdf_result['file_path']}")
        logger.info(f"DOCX: {docx_result['file_path']}")

        return {
            "analysis": analysis_result,
            "disagreement": disagreement_result,
            "exports": {
                "pdf": pdf_result,
                "docx": docx_result,
                "email": email_result
            }
        }

# Run complete workflow
if __name__ == "__main__":
    result = complete_contract_workflow(
        contract_path="/path/to/contract.pdf",
        contract_type="supply"
    )
```

**Output:**
```
2025-01-15 10:00:00 | INFO | Step 1: Analyzing contract...
2025-01-15 10:00:45 | INFO | Analysis complete. Found 5 risks
2025-01-15 10:00:45 | INFO | Step 2: Generating objections for critical risks...
2025-01-15 10:01:15 | INFO | Generated 2 objections
2025-01-15 10:01:15 | INFO | Step 3: Exporting results...
2025-01-15 10:01:25 | INFO | PDF exported: /exports/analysis_123abc.pdf
2025-01-15 10:01:30 | INFO | DOCX exported: /exports/analysis_123abc.docx
2025-01-15 10:01:32 | INFO | Email sent to: ['lawyer@company.com']
2025-01-15 10:01:32 | INFO | === Workflow Complete ===
2025-01-15 10:01:32 | INFO | Contract: contract_workflow_001
2025-01-15 10:01:32 | INFO | Analysis ID: analysis_123abc
2025-01-15 10:01:32 | INFO | Total risks: 5
2025-01-15 10:01:32 | INFO | Critical risks: 2
2025-01-15 10:01:32 | INFO | Objections: 2
2025-01-15 10:01:32 | INFO | PDF: /exports/analysis_123abc.pdf
2025-01-15 10:01:32 | INFO | DOCX: /exports/analysis_123abc.docx
```

---

For more information, see:
- [API Documentation](../api/README.md)
- [Architecture Documentation](../architecture/README.md)
- [Deployment Guide](../deployment/README.md)
