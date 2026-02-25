"""
Document Processor - Главный оркестратор пайплайна обработки

Pipeline:
1. Text Extraction (PDF/DOCX/OCR)
2. Level 1 Extraction (regex/SpaCy)
3. LLM Extraction (через Smart Router)
4. RAG Filter (похожие договоры)
5. Validation (Pydantic)
6. Save to DB (с processing_pipeline для "стеклянного ящика")
"""

import logging
import time
import json
from typing import Dict, Any, Optional, BinaryIO
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

from src.services.text_extractor import TextExtractor
from src.services.level1_extractor import Level1Extractor
from src.services.llm_extractor import LLMExtractor
from src.services.validation_service import ValidationService
from src.services.rag_service import RAGService
from src.services.contract_section_analyzer import ContractSectionAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class ProcessingStage:
    """Результат одного этапа обработки"""
    name: str
    status: str  # 'success', 'failed', 'skipped'
    duration_sec: float
    results: Dict[str, Any]
    error: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class DocumentProcessingResult:
    """Полный результат обработки документа"""
    document_id: Optional[int]  # ID в БД (если сохранено)
    status: str  # 'completed', 'failed', 'pending_approval'

    # Промежуточные результаты (для стеклянного ящика)
    stages: list[ProcessingStage]

    # Финальные извлеченные данные
    extracted_data: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]

    # Метрики
    total_time_sec: float
    total_cost_usd: float
    model_used: str

    # Текст документа
    raw_text: str

    # Данные для сохранения форматирования
    original_file_bytes: Optional[bytes] = None
    docx_file_bytes: Optional[bytes] = None
    original_format: str = ''

    def to_dict(self) -> Dict[str, Any]:
        """Конвертирует в dict для JSON (без бинарных данных)"""
        return {
            'document_id': self.document_id,
            'status': self.status,
            'stages': [asdict(s) for s in self.stages],
            'extracted_data': self.extracted_data,
            'validation_result': self.validation_result,
            'total_time_sec': self.total_time_sec,
            'total_cost_usd': self.total_cost_usd,
            'model_used': self.model_used,
            'raw_text': self.raw_text,
            'original_format': self.original_format,
            'has_docx': self.docx_file_bytes is not None
        }


class DocumentProcessor:
    """
    Главный оркестратор обработки документов

    Координирует все этапы пайплайна и сохраняет
    промежуточные результаты для "стеклянного ящика"
    """

    def __init__(self,
                 api_key: str = None,
                 model: str = "deepseek-chat",
                 base_url: str = None,
                 openai_api_key: str = None,
                 use_ocr: bool = True,
                 use_rag: bool = True,
                 use_section_analysis: bool = True):
        """
        Args:
            api_key: API ключ (DeepSeek или OpenAI)
            model: Модель для LLM extraction
            base_url: Base URL API (для DeepSeek: https://api.deepseek.com/v1)
            openai_api_key: Deprecated, используйте api_key
            use_ocr: Использовать ли OCR для сканов
            use_rag: Использовать ли RAG filter
            use_section_analysis: Использовать ли детальный анализ разделов
        """
        # Обратная совместимость: openai_api_key -> api_key
        effective_key = api_key or openai_api_key

        self.text_extractor = TextExtractor(use_ocr=use_ocr)
        self.level1_extractor = Level1Extractor()
        self.llm_extractor = LLMExtractor(
            api_key=effective_key, model=model, base_url=base_url
        )
        self.validation_service = ValidationService()

        # RAG с автоматическим fallback
        self.use_rag = use_rag
        self.rag_service = None

        if use_rag:
            try:
                logger.warning("RAG initialization skipped: db_session should be provided externally")
                self.use_rag = False
            except Exception as e:
                logger.warning(f"RAG initialization failed: {e}. Fallback to LLM-only mode.")
                self.use_rag = False

        # Анализ разделов
        self.use_section_analysis = use_section_analysis
        self.section_analyzer = ContractSectionAnalyzer(
            model=model, api_key=effective_key, base_url=base_url
        ) if use_section_analysis else None

        logger.info(f"DocumentProcessor initialized: model={model}, base_url={base_url or 'default'}, ocr={use_ocr}, rag={self.use_rag}, section_analysis={use_section_analysis}")

    async def process_document(self,
                               file_path: str | Path | BinaryIO,
                               file_extension: Optional[str] = None) -> DocumentProcessingResult:
        """
        Обрабатывает документ через весь пайплайн

        Args:
            file_path: Путь к файлу или file-like объект
            file_extension: Расширение файла (если file_path - это BinaryIO)

        Returns:
            DocumentProcessingResult с полными результатами
        """
        start_time = time.time()
        stages = []
        total_cost = 0.0

        try:
            # Stage 1: Text Extraction
            logger.info("Stage 1: Text Extraction...")
            stage_start = time.time()

            extraction_result = self.text_extractor.extract(file_path, file_extension)
            raw_text = extraction_result.text

            # Сохраняем bytes файлов для работы с форматированием
            original_file_bytes = extraction_result.original_file_bytes
            docx_file_bytes = extraction_result.docx_file_bytes
            original_format = extraction_result.original_format

            stages.append(ProcessingStage(
                name="text_extraction",
                status="success",
                duration_sec=time.time() - stage_start,
                results={
                    "method": extraction_result.method,
                    "pages": extraction_result.pages,
                    "chars": len(raw_text),
                    "confidence": extraction_result.confidence,
                    "metadata": extraction_result.metadata,
                    "original_format": original_format,
                    "has_docx": docx_file_bytes is not None
                },
                metadata={"text_preview": raw_text[:500]}  # Превью для UI
            ))

            # Stage 2: Level 1 Extraction
            logger.info("Stage 2: Level 1 Extraction...")
            stage_start = time.time()

            level1_results = self.level1_extractor.extract(raw_text)

            # Форматируем для удобного просмотра
            level1_summary = {
                entity_type: [
                    {
                        "value": e.value,
                        "normalized": str(e.normalized) if hasattr(e.normalized, '__str__') else e.normalized,
                        "confidence": e.confidence,
                        "position": e.position,
                        "context": e.context
                    }
                    for e in entities
                ]
                for entity_type, entities in level1_results.items()
            }

            stages.append(ProcessingStage(
                name="level1_extraction",
                status="success",
                duration_sec=time.time() - stage_start,
                results={
                    "entities_count": sum(len(v) for v in level1_results.values()),
                    "by_type": {k: len(v) for k, v in level1_results.items()},
                    "details": level1_summary
                }
            ))

            # Stage 3: LLM Extraction
            logger.info("Stage 3: LLM Extraction...")
            stage_start = time.time()

            llm_result = await self.llm_extractor.extract(raw_text, level1_results)
            total_cost += llm_result.cost_usd

            stages.append(ProcessingStage(
                name="llm_extraction",
                status="success",
                duration_sec=llm_result.processing_time,
                results={
                    "data": llm_result.data,
                    "model": llm_result.model_used,
                    "tokens_input": llm_result.tokens_input,
                    "tokens_output": llm_result.tokens_output,
                    "cost_usd": llm_result.cost_usd,
                    "confidence": llm_result.confidence
                },
                metadata={"raw_response_preview": llm_result.raw_response[:500]}
            ))

            # Stage 4: RAG Filter (если включен)
            if self.use_rag and self.rag_service:
                logger.info("Stage 4: RAG Filter...")
                stage_start = time.time()

                try:
                    # Ищем похожие договоры
                    contract_subject = llm_result.data.get("subject", {}).get("description", "")

                    if contract_subject:
                        similar_contracts = await self.rag_service.find_similar_contracts(
                            contract_subject,
                            top_k=3
                        )

                        stages.append(ProcessingStage(
                            name="rag_filter",
                            status="success",
                            duration_sec=time.time() - stage_start,
                            results={
                                "similar_contracts_found": len(similar_contracts),
                                "contracts": similar_contracts
                            }
                        ))
                    else:
                        stages.append(ProcessingStage(
                            name="rag_filter",
                            status="skipped",
                            duration_sec=0,
                            results={"reason": "No contract subject found"}
                        ))

                except Exception as e:
                    logger.warning(f"RAG filter failed: {e}")
                    stages.append(ProcessingStage(
                        name="rag_filter",
                        status="failed",
                        duration_sec=time.time() - stage_start,
                        results={},
                        error=str(e)
                    ))

            # Stage 5: Validation
            logger.info("Stage 5: Validation...")
            stage_start = time.time()

            validation_result = self.validation_service.validate(llm_result.data)

            stages.append(ProcessingStage(
                name="validation",
                status="success" if validation_result.is_valid else "failed",
                duration_sec=time.time() - stage_start,
                results={
                    "is_valid": validation_result.is_valid,
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                    "errors_count": len(validation_result.errors),
                    "warnings_count": len(validation_result.warnings)
                }
            ))

            # Stage 6: Section Analysis (опционально)
            section_analysis_result = None
            if self.use_section_analysis and self.section_analyzer:
                logger.info("Stage 6: Section Analysis...")
                stage_start = time.time()

                try:
                    # Собираем похожие договоры из RAG stage
                    similar_contracts = []
                    for stage in stages:
                        if stage.name == "rag_filter" and stage.status == "success":
                            similar_contracts = stage.results.get("contracts", [])
                            break

                    # Запускаем полный анализ разделов
                    section_analysis_result = await self.section_analyzer.analyze_full_contract(
                        raw_text,
                        similar_contracts,
                        llm_result.data
                    )

                    stages.append(ProcessingStage(
                        name="section_analysis",
                        status="success",
                        duration_sec=time.time() - stage_start,
                        results={
                            "sections_count": len(section_analysis_result.get("sections", [])),
                            "sections": [
                                {
                                    "number": s.number,
                                    "title": s.title,
                                    "text_length": len(s.text)
                                }
                                for s in section_analysis_result.get("sections", [])
                            ],
                            "section_analyses": [
                                {
                                    "section_number": a.section_number,
                                    "section_title": a.section_title,
                                    "comparison": a.own_contracts_comparison,
                                    "legal_check": a.rag_legal_check,
                                    "conclusion": a.conclusion,
                                    "warnings_count": len(a.warnings),
                                    "recommendations_count": len(a.recommendations)
                                }
                                for a in section_analysis_result.get("section_analyses", [])
                            ],
                            "complex_analysis": {
                                "overall_score": section_analysis_result.get("complex_analysis").overall_score,
                                "legal_reliability": section_analysis_result.get("complex_analysis").legal_reliability,
                                "compliance_percent": section_analysis_result.get("complex_analysis").compliance_percent
                            },
                            # Полные данные для UI
                            "full_data": section_analysis_result
                        }
                    ))

                    logger.info(f"Section analysis completed: {len(section_analysis_result.get('sections', []))} sections analyzed")

                except Exception as e:
                    logger.error(f"Section analysis failed: {e}")
                    stages.append(ProcessingStage(
                        name="section_analysis",
                        status="failed",
                        duration_sec=time.time() - stage_start,
                        results={},
                        error=str(e)
                    ))

            # Финальный результат
            total_time = time.time() - start_time

            result = DocumentProcessingResult(
                document_id=None,  # Будет заполнено при сохранении в БД
                status="completed" if validation_result.is_valid else "pending_approval",
                stages=stages,
                extracted_data=llm_result.data,
                validation_result={
                    "is_valid": validation_result.is_valid,
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings
                },
                total_time_sec=total_time,
                total_cost_usd=total_cost,
                model_used=llm_result.model_used,
                raw_text=raw_text,
                original_file_bytes=original_file_bytes,
                docx_file_bytes=docx_file_bytes,
                original_format=original_format
            )

            logger.info(f"Document processing completed: "
                       f"status={result.status}, "
                       f"time={total_time:.2f}s, "
                       f"cost=${total_cost:.6f}, "
                       f"format={original_format}, "
                       f"has_docx={'yes' if docx_file_bytes else 'no'}")

            return result

        except Exception as e:
            logger.error(f"Document processing failed: {e}", exc_info=True)

            # Возвращаем результат с ошибкой
            return DocumentProcessingResult(
                document_id=None,
                status="failed",
                stages=stages,
                extracted_data=None,
                validation_result=None,
                total_time_sec=time.time() - start_time,
                total_cost_usd=total_cost,
                model_used="",
                raw_text=""
            )
