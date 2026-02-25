# -*- coding: utf-8 -*-
"""
IDP Orchestrator - координация всего процесса обработки документов
Главная точка входа для Intelligent Document Processing
"""
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from loguru import logger

from ..schemas.idp_schemas import IntermediateJSONSchema, validate_intermediate_json
from ..models.database import get_db
from sqlalchemy.orm import Session


class IDPOrchestrator:
    """
    Координирует весь процесс IDP обработки документов

    Ответственность:
    1. Классификация типа документа
    2. Выбор оптимального пайплайна
    3. Координация этапов обработки
    4. Логирование и мониторинг
    5. Обработка ошибок
    """

    def __init__(
        self,
        db_session: Session,
        file_storage=None,
        llm_gateway=None
    ):
        self.db = db_session
        self.storage = file_storage
        self.llm = llm_gateway

        # Компоненты пайплайна (будут инициализированы при первом использовании)
        self._classifier = None
        self._layout_analyzer = None
        self._ocr_service = None
        self._entity_extractor = None
        self._schema_mapper = None

    @property
    def classifier(self):
        """Lazy loading DocumentClassifier"""
        if self._classifier is None:
            from .document_classifier import DocumentClassifier
            self._classifier = DocumentClassifier()
        return self._classifier

    @property
    def layout_analyzer(self):
        """Lazy loading LayoutAnalyzer"""
        if self._layout_analyzer is None:
            from .layout_analyzer import LayoutAnalyzer
            self._layout_analyzer = LayoutAnalyzer()
        return self._layout_analyzer

    @property
    def ocr_service(self):
        """Lazy loading EnhancedOCRService"""
        if self._ocr_service is None:
            from .ocr_service import EnhancedOCRService
            self._ocr_service = EnhancedOCRService()
        return self._ocr_service

    @property
    def entity_extractor(self):
        """Lazy loading MultiLevelEntityExtractor"""
        if self._entity_extractor is None:
            from .entity_extractor import MultiLevelEntityExtractor
            self._entity_extractor = MultiLevelEntityExtractor(self.llm)
        return self._entity_extractor

    @property
    def schema_mapper(self):
        """Lazy loading SchemaMapper"""
        if self._schema_mapper is None:
            from .schema_mapper import SchemaMapper
            self._schema_mapper = SchemaMapper(self.db)
        return self._schema_mapper

    async def process_document(
        self,
        contract_id: str,
        file_data: bytes,
        filename: str,
        idp_mode: str = 'auto'
    ) -> Dict[str, Any]:
        """
        Главный метод обработки документа

        Args:
            contract_id: ID договора в БД
            file_data: Бинарные данные файла
            filename: Имя файла
            idp_mode: Режим обработки ('auto', 'fast', 'deep')

        Returns:
            Dict с результатами обработки
        """
        logger.info(f"🚀 Starting IDP processing for contract {contract_id} (mode: {idp_mode})")
        start_time = datetime.now()

        try:
            # ====== ЭТАП 1: INGESTION & CLASSIFICATION ======
            logger.info(f"📥 Stage 1: Ingestion & Classification")
            stage_start = datetime.now()

            # Сохраняем оригинал файла
            file_path = self._save_original_file(contract_id, file_data, filename)

            # Классифицируем тип документа
            doc_type = self.classifier.classify(file_path)
            self._log_stage(
                contract_id=contract_id,
                stage='classification',
                status='success',
                output_data={
                    'format': doc_type.format,
                    'is_searchable': doc_type.is_searchable,
                    'page_count': doc_type.page_count,
                    'confidence': doc_type.confidence
                },
                duration_ms=(datetime.now() - stage_start).total_seconds() * 1000
            )

            # ====== ЭТАП 2: ROUTE TO PIPELINE ======
            logger.info(f"🔀 Routing to pipeline: {doc_type.format}")

            if doc_type.format == 'xml':
                intermediate = await self._process_xml(contract_id, file_path)

            elif doc_type.format == 'pdf' and doc_type.is_searchable:
                intermediate = await self._process_searchable_pdf(
                    contract_id, file_path, idp_mode
                )

            elif doc_type.format in ['pdf', 'jpg', 'png']:
                intermediate = await self._process_scanned_document(
                    contract_id, file_path, idp_mode
                )

            else:
                raise ValueError(f"Unsupported format: {doc_type.format}")

            # ====== ЭТАП 5: VALIDATION ======
            logger.info(f"✅ Stage 5: Validation")
            stage_start = datetime.now()

            try:
                validated = validate_intermediate_json(intermediate.dict())
                self._log_stage(
                    contract_id=contract_id,
                    stage='validation',
                    status='success',
                    output_data={'fields_count': len(validated.dict().keys())},
                    duration_ms=(datetime.now() - stage_start).total_seconds() * 1000
                )
            except Exception as validation_error:
                logger.warning(f"⚠️ Validation issues: {validation_error}")
                self._log_stage(
                    contract_id=contract_id,
                    stage='validation',
                    status='partial',
                    output_data={},
                    error_message=str(validation_error),
                    duration_ms=(datetime.now() - stage_start).total_seconds() * 1000
                )
                # Создаем quality issues
                self._create_quality_issues(contract_id, validation_error)

            # ====== ЭТАП 6: STORAGE ======
            logger.info(f"💾 Stage 6: Storage")
            stage_start = datetime.now()

            core_id = await self.schema_mapper.save_to_database(
                contract_id, intermediate.dict()
            )

            self._log_stage(
                contract_id=contract_id,
                stage='storage',
                status='success',
                output_data={'core_id': core_id},
                duration_ms=(datetime.now() - stage_start).total_seconds() * 1000
            )

            # ====== ЗАВЕРШЕНИЕ ======
            total_duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"✅ IDP processing completed for contract {contract_id} in {total_duration:.2f}s")

            return {
                'success': True,
                'contract_id': contract_id,
                'core_id': core_id,
                'duration_sec': total_duration,
                'intermediate_json': intermediate.dict()
            }

        except Exception as e:
            logger.error(f"❌ IDP processing failed for contract {contract_id}: {e}")
            import traceback
            traceback.print_exc()

            self._log_stage(
                contract_id=contract_id,
                stage='processing',
                status='failed',
                output_data={},
                error_message=str(e),
                duration_ms=(datetime.now() - start_time).total_seconds() * 1000
            )

            return {
                'success': False,
                'contract_id': contract_id,
                'error': str(e)
            }

    async def _process_xml(
        self,
        contract_id: str,
        file_path: str
    ) -> IntermediateJSONSchema:
        """
        Обработка XML документа (детерминированный парсинг)
        """
        logger.info(f"📄 Processing XML document: {file_path}")
        stage_start = datetime.now()

        # Используем существующий DocumentParser
        from ..services.document_parser import DocumentParser
        parser = DocumentParser()

        xml_data = parser.parse(file_path)

        # Преобразуем XML → Intermediate JSON
        intermediate = self._xml_to_intermediate(xml_data)

        self._log_stage(
            contract_id=contract_id,
            stage='xml_parsing',
            status='success',
            output_data={
                'method': 'deterministic',
                'fields_extracted': len(intermediate.keys())
            },
            duration_ms=(datetime.now() - stage_start).total_seconds() * 1000
        )

        return IntermediateJSONSchema(**intermediate)

    async def _process_searchable_pdf(
        self,
        contract_id: str,
        file_path: str,
        idp_mode: str
    ) -> IntermediateJSONSchema:
        """
        Обработка searchable PDF (с текстовым слоем)
        """
        logger.info(f"📃 Processing searchable PDF: {file_path}")

        # ====== ЭТАП 2: LAYOUT ANALYSIS ======
        stage_start = datetime.now()
        logger.info(f"🔍 Stage 2: Layout Analysis")

        pages = self._convert_pdf_to_images(file_path)
        blocks = []

        for page_num, page_img in enumerate(pages):
            page_blocks = self.layout_analyzer.segment_document(page_img)
            blocks.extend(page_blocks)

        self._log_stage(
            contract_id=contract_id,
            stage='layout_analysis',
            status='success',
            output_data={
                'pages': len(pages),
                'blocks': len(blocks)
            },
            duration_ms=(datetime.now() - stage_start).total_seconds() * 1000
        )

        # ====== ЭТАП 3: CASCADING EXTRACTION ======
        stage_start = datetime.now()
        logger.info(f"🔬 Stage 3: Cascading Extraction")

        intermediate = await self.entity_extractor.extract_all(
            blocks, mode=idp_mode
        )

        self._log_stage(
            contract_id=contract_id,
            stage='entity_extraction',
            status='success',
            output_data={
                'method': 'cascading',
                'mode': idp_mode
            },
            duration_ms=(datetime.now() - stage_start).total_seconds() * 1000
        )

        return intermediate

    async def _process_scanned_document(
        self,
        contract_id: str,
        file_path: str,
        idp_mode: str
    ) -> IntermediateJSONSchema:
        """
        Обработка скана/фото (максимальная сложность)
        """
        logger.info(f"📸 Processing scanned document: {file_path}")

        pages = self._convert_pdf_to_images(file_path)

        # ====== ЭТАП 2: OCR ======
        stage_start = datetime.now()
        logger.info(f"👁️ Stage 2: OCR")

        ocr_results = []
        for page_num, page_img in enumerate(pages):
            ocr_result = self.ocr_service.extract_text(
                page_img,
                prefer_structure=True  # PaddleOCR
            )
            ocr_results.append(ocr_result)

        avg_confidence = sum(r.confidence for r in ocr_results if r.confidence) / len(ocr_results)

        self._log_stage(
            contract_id=contract_id,
            stage='ocr',
            status='success',
            output_data={
                'pages': len(pages),
                'avg_confidence': avg_confidence,
                'engine': 'paddleocr'
            },
            duration_ms=(datetime.now() - stage_start).total_seconds() * 1000
        )

        # ====== ЭТАП 3: LAYOUT ANALYSIS ======
        stage_start = datetime.now()
        logger.info(f"🔍 Stage 3: Layout Analysis")

        blocks = []
        for page_num, page_img in enumerate(pages):
            page_blocks = self.layout_analyzer.segment_document(page_img)

            # Обогащаем блоки текстом из OCR
            for block in page_blocks:
                block.text = self._extract_text_from_ocr(
                    ocr_results[page_num], block.bbox
                )

            blocks.extend(page_blocks)

        self._log_stage(
            contract_id=contract_id,
            stage='layout_analysis',
            status='success',
            output_data={
                'pages': len(pages),
                'blocks': len(blocks)
            },
            duration_ms=(datetime.now() - stage_start).total_seconds() * 1000
        )

        # ====== ЭТАП 4: CASCADING EXTRACTION ======
        stage_start = datetime.now()
        logger.info(f"🔬 Stage 4: Cascading Extraction")

        intermediate = await self.entity_extractor.extract_all(
            blocks, mode=idp_mode
        )

        self._log_stage(
            contract_id=contract_id,
            stage='entity_extraction',
            status='success',
            output_data={
                'method': 'cascading',
                'mode': idp_mode
            },
            duration_ms=(datetime.now() - stage_start).total_seconds() * 1000
        )

        return intermediate

    # ============================================================
    # Helper Methods
    # ============================================================

    def _save_original_file(
        self,
        contract_id: str,
        file_data: bytes,
        filename: str
    ) -> str:
        """Сохранение оригинала файла"""
        if self.storage:
            return self.storage.store_original(
                contract_id, file_data, Path(filename).suffix
            )
        else:
            # Fallback: сохраняем локально
            file_path = Path(f"data/contracts/originals/{contract_id}{Path(filename).suffix}")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(file_data)
            return str(file_path)

    def _convert_pdf_to_images(self, pdf_path: str) -> List[Any]:
        """Конвертация PDF в изображения"""
        from pdf2image import convert_from_path

        try:
            images = convert_from_path(pdf_path, dpi=300)
            return images
        except Exception as e:
            logger.error(f"PDF to images conversion failed: {e}")
            raise

    def _extract_text_from_ocr(
        self,
        ocr_result,
        bbox: tuple
    ) -> str:
        """Извлечение текста из OCR результата по bbox"""
        # TODO: Реализовать извлечение текста из bbox
        return ocr_result.text if hasattr(ocr_result, 'text') else ""

    def _xml_to_intermediate(self, xml_data: str) -> Dict[str, Any]:
        """Преобразование XML → Intermediate JSON"""
        from lxml import etree
        from ..utils.xml_security import parse_xml_safely

        try:
            root = parse_xml_safely(xml_data)

            intermediate = {
                'doc_number': root.findtext('.//doc_number', default='UNKNOWN'),
                'signed_date': root.findtext('.//signed_date'),
                'total_amount': root.findtext('.//total_amount'),
                'currency': root.findtext('.//currency', default='RUB'),
                'parties': [],
                'items': [],
                'payment_schedule': [],
                'rules': [],
                'attributes': {}
            }

            # Извлекаем стороны
            for party_elem in root.findall('.//party'):
                party = {
                    'role': party_elem.get('role', 'unknown'),
                    'name': party_elem.findtext('name', ''),
                    'inn': party_elem.findtext('inn'),
                    'legal_address': party_elem.findtext('address')
                }
                intermediate['parties'].append(party)

            # TODO: Извлечь остальные данные из XML

            return intermediate

        except Exception as e:
            logger.error(f"XML to intermediate conversion failed: {e}")
            raise

    def _log_stage(
        self,
        contract_id: str,
        stage: str,
        status: str,
        output_data: Dict[str, Any],
        duration_ms: float,
        error_message: Optional[str] = None,
        tokens_used: Optional[int] = None,
        cost_usd: Optional[float] = None
    ):
        """Логирование этапа обработки в БД"""
        from ..models.idp_models import IDPExtractionLog

        log_entry = IDPExtractionLog(
            contract_id=contract_id,
            stage=stage,
            status=status,
            output_data=output_data,
            error_message=error_message,
            duration_ms=int(duration_ms),
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            created_at=datetime.now()
        )

        self.db.add(log_entry)
        self.db.commit()

        logger.info(f"📝 Logged stage: {stage} ({status}) - {duration_ms:.0f}ms")

    def _create_quality_issues(
        self,
        contract_id: str,
        validation_error: Exception
    ):
        """Создание записей о проблемах качества"""
        from ..models.idp_models import IDPQualityIssue

        # TODO: Парсить validation_error и создавать детальные issues

        issue = IDPQualityIssue(
            contract_id=contract_id,
            issue_type='validation_error',
            severity='warning',
            description=str(validation_error),
            requires_manual_review=True,
            status='open'
        )

        self.db.add(issue)
        self.db.commit()


# Экспорт
__all__ = ['IDPOrchestrator']
