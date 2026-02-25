# RAG System - Complete Implementation

## Overview
Full-featured RAG (Retrieval-Augmented Generation) system for legal document search and question answering.

## Features

### ✅ Multiple Embedding Models
1. **OpenAI text-embedding-3-large** (API) - Best quality, requires API key
2. **E5-mistral-7b-instruct** - Large open-source model (7B parameters)
3. **multilingual-e5-small** - Compact multilingual model
4. **BGE-M3** - Best open-source for multilingual (100+ languages)
5. **paraphrase-multilingual-MiniLM-L12-v2** - Default, balanced

### ✅ Multiple Reranking Models
1. **Cohere Rerank** (API) - 100+ languages, requires API key
2. **mxbai-rerank-large-v1** - Open-source cross-encoder (1.5B params)
3. **BAAI/bge-reranker-large** - Open-source reranker
4. **ms-marco-MiniLM-L-12-v2** - Compact cross-encoder (default)

### ✅ Collections
- **laws** - Legal acts and regulations
- **case_law** - Court decisions and precedents
- **templates** - Contract templates
- **knowledge** - General legal knowledge base

### ✅ Search Capabilities
- **Vector search** - Semantic similarity using embeddings
- **Keyword search** - Traditional text matching
- **Hybrid search** - Combined vector + keyword
- **Metadata filtering** - Filter by doc_type, date, source, etc.
- **Re-ranking** - Improve relevance with cross-encoders

## Installation

```bash
# Install dependencies
pip install chromadb sentence-transformers

# Optional: For OpenAI embeddings
pip install openai

# Optional: For Cohere reranking
pip install cohere
```

## Quick Start

### Basic Usage (Local Models)

```python
from src.services.rag_system import RAGSystem
from src.models import SessionLocal

# Initialize
db = SessionLocal()
rag = RAGSystem(
    db_session=db,
    embedding_model="paraphrase-multilingual",  # or "multilingual-e5-small", "bge-m3"
    reranker_model="ms-marco"  # or "bge-reranker", "mxbai-rerank"
)

# Index a document
rag.index_document(
    doc_id="gk_rf_421",
    content="Статья 421. Свобода договора...",
    metadata={"title": "ГК РФ Статья 421", "doc_type": "law"},
    collection="laws"
)

# Search
results = rag.search(
    query="свобода договора",
    collection="laws",
    top_k=5
)

for doc in results:
    print(f"{doc.doc_id}: {doc.score:.3f}")
    print(doc.content[:100])
```

### Advanced: OpenAI Embeddings

```python
rag = RAGSystem(
    db_session=db,
    use_openai_embeddings=True,
    openai_api_key="your-api-key",
    reranker_model="ms-marco"
)
```

### Hybrid Search

```python
results = rag.hybrid_search(
    query="договор поставки существенные условия",
    collection="knowledge",
    top_k=5,
    keyword_weight=0.3  # 30% keyword, 70% vector
)
```

### Generate Answer with RAG

```python
from src.services.llm_gateway import LLMGateway

llm = LLMGateway(provider="openai", api_key="your-key")
rag = RAGSystem(db_session=db, llm_gateway=llm)

answer, sources = rag.generate_answer(
    query="Какие условия обязательны для договора поставки?",
    collection="knowledge",
    top_k=3
)

print(answer)
for doc in sources:
    print(f"Source: {doc.metadata.get('title')}")
```

## Testing

### Mock Test (No Dependencies Required)
```bash
python test_rag_system_mock.py
```

### Full Test (Requires Dependencies)
```bash
# Install first
pip install chromadb sentence-transformers

# Run tests
python test_rag_system.py
```

## Model Selection Guide

### Embedding Models

| Model | Size | Languages | Speed | Use Case |
|-------|------|-----------|-------|----------|
| paraphrase-multilingual | ~420MB | 50+ | Fast | Default, balanced |
| multilingual-e5-small | ~470MB | 100+ | Fast | Multilingual, compact |
| bge-m3 | ~2.2GB | 100+ | Medium | Best quality multilingual |
| e5-mistral | ~15GB | English | Slow | Highest quality (EN) |
| OpenAI | API | 100+ | Fast | Best quality, requires API |

### Reranking Models

| Model | Size | Speed | Use Case |
|-------|------|-------|----------|
| ms-marco | ~130MB | Fast | Default, good balance |
| bge-reranker | ~1.3GB | Medium | Better quality |
| mxbai-rerank | ~2.8GB | Slow | Best open-source |
| Cohere | API | Fast | Best quality, requires API |

## Architecture

```
RAGSystem
├── ChromaDB (Vector Storage)
│   ├── laws collection
│   ├── case_law collection
│   ├── templates collection
│   └── knowledge collection
├── Embedding Models
│   ├── Local (sentence-transformers)
│   └── API (OpenAI)
├── Reranking Models
│   ├── Local (cross-encoders)
│   └── API (Cohere)
└── LLM Integration
    └── LLMGateway (7 providers)
```

## Configuration

### Environment Variables
```bash
# For OpenAI embeddings
export OPENAI_API_KEY="sk-..."

# For Cohere reranking
export COHERE_API_KEY="..."
```

### Custom Parameters
```python
rag = RAGSystem(
    db_session=db,
    chroma_persist_dir="data/chromadb",  # Storage location
    embedding_model="bge-m3",  # Embedding model
    reranker_model="mxbai-rerank",  # Reranker
    llm_gateway=llm  # For answer generation
)

# Adjust chunking
rag.chunk_size = 512  # tokens per chunk
rag.chunk_overlap = 128  # overlap between chunks
```

## Performance Tips

1. **For Russian legal texts**: Use `bge-m3` or `multilingual-e5-small`
2. **For production with budget**: Use local models (free)
3. **For best quality**: Use OpenAI embeddings + Cohere reranking (paid)
4. **For speed**: Use `paraphrase-multilingual` + `ms-marco`
5. **For accuracy**: Enable reranking with cross-encoders

## Status

✅ **Code Complete** - All features implemented
✅ **Tested** - Mock tests passing
⏳ **Dependencies** - Install chromadb + sentence-transformers to run full tests
📊 **Data** - Framework ready, needs legal document population

## Next Steps

1. Install dependencies: `pip install chromadb sentence-transformers`
2. Run full tests: `python test_rag_system.py`
3. Populate collections with legal documents
4. Integrate with Contract Analyzer Agent
5. Fine-tune embedding models on legal domain (optional)
