# -*- coding: utf-8 -*-
"""
Contract Analyzer Agent - Deep analysis of contracts with risk identification
"""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from lxml import etree
from loguru import logger

from .base_agent import BaseAgent, AgentResult
from ..services.llm_gateway import LLMGateway
from ..services.template_manager import TemplateManager
from ..services.counterparty_service import CounterpartyService
from ..services.clause_extractor import ClauseExtractor
from ..services.risk_analyzer import RiskAnalyzer
from ..services.recommendation_generator import RecommendationGenerator
from ..services.metadata_analyzer import MetadataAnalyzer
from ..models.analyzer_models import (
    ContractRisk, ContractRecommendation, ContractAnnotation,
    ContractSuggestedChange
)
from ..models.database import Contract, AnalysisResult
from ..utils.xml_security import parse_xml_safely, XMLSecurityError
from config.settings import settings

# Optional RAG import
try:
    from ..services.rag_system import RAGSystem
except ImportError:
    RAGSystem = None


class ContractAnalyzerAgent(BaseAgent):
    """
    Agent for deep contract analysis

    Capabilities:
    - Maximum depth analysis (all risk types)
    - RAG integration (analogues + precedents + legal norms)
    - Risk identification (financial, legal, operational, reputational)
    - Automatic change suggestions with LLM
    - Template comparison
    - Counterparty checking (optional)
    - Dispute probability prediction
    - Annotated XML generation
    """

    def __init__(
        self,
        llm_gateway: LLMGateway = None,
        db_session = None,
        template_manager: Optional[TemplateManager] = None,
        rag_system: Optional['RAGSystem'] = None,
        counterparty_service: Optional[CounterpartyService] = None
    ):
        # Если LLM не передан, создаём с быстрой моделью для первого уровня
        if llm_gateway is None:
            from config.settings import settings
            llm_gateway = LLMGateway(model=settings.llm_quick_model)

        super().__init__(llm_gateway, db_session)
        self.template_manager = template_manager or TemplateManager(db_session)
        self.rag_system = rag_system
        self.counterparty_service = counterparty_service or CounterpartyService()

        # Initialize refactored service modules
        self.clause_extractor = ClauseExtractor()
        self.risk_analyzer = RiskAnalyzer(llm_gateway)
        self.recommendation_generator = RecommendationGenerator(
            llm_gateway,
            system_prompt=self.get_system_prompt()
        )
        self.metadata_analyzer = MetadataAnalyzer(
            llm_gateway,
            counterparty_service=self.counterparty_service,
            template_manager=self.template_manager,
            system_prompt=self.get_system_prompt()
        )

    def get_name(self) -> str:
        return "ContractAnalyzerAgent"

    def get_system_prompt(self) -> str:
        return """You are a contract analysis expert specializing in Russian contract law.

Your task is to perform deep analysis of contracts and identify:
1. RISKS (financial, legal, operational, reputational)
   - Severity: critical, significant, minor
   - Probability: high, medium, low
   - Consequences: qualitative assessment (no monetary values)

2. RECOMMENDATIONS for contract improvement
   - Priority: critical, high, medium, low
   - Category: legal_compliance, risk_mitigation, financial_optimization, etc.
   - Expected benefit and implementation complexity

3. SUGGESTED CHANGES (automatic via LLM)
   - Original text and suggested replacement
   - Issue description and reasoning
   - Legal basis (references to laws, articles)
   - Change type: addition, modification, deletion, clarification

4. DISPUTE PROBABILITY PREDICTION
   - Overall score and reasoning
   - Specific clauses that may lead to disputes

5. ANNOTATIONS for document sections
   - Type: risk, warning, info, suggestion
   - Location via xpath
   - Related risks/recommendations

Always provide structured JSON output with all identified issues.
Use RAG sources (precedents, legal norms, analogues) to support your analysis.
"""

    def execute(self, state: Dict[str, Any]) -> AgentResult:
        """
        Execute contract analysis

        Expected state:
        - contract_id: ID of contract to analyze
        - parsed_xml: Parsed XML content
        - metadata: Contract metadata
        - check_counterparty: Optional flag to check counterparty info

        Returns:
        - analysis_id: ID of created analysis
        - risks: List of identified risks
        - recommendations: List of recommendations
        - suggested_changes: List of suggested changes
        - annotations: List of annotations
        - dispute_probability: Dispute prediction
        - counterparty_data: Optional counterparty check results
        - next_action: 'review_queue' or 'export'
        """
        try:
            contract_id = state.get('contract_id')
            parsed_xml = state.get('parsed_xml')
            metadata = state.get('metadata', {})
            check_counterparty = state.get('check_counterparty', False)

            if not contract_id or not parsed_xml:
                return AgentResult(
                    success=False,
                    data={},
                    error="Missing contract_id or parsed_xml"
                )

            logger.info(f"Starting analysis for contract {contract_id}")

            # 1. Get contract from DB
            contract = self.db.query(Contract).filter(
                Contract.id == contract_id
            ).first()

            if not contract:
                return AgentResult(
                    success=False,
                    data={},
                    error=f"Contract {contract_id} not found"
                )

            # 2. Create analysis result record
            analysis = self._create_analysis_record(contract)

            # 3. Extract contract structure
            structure = self.clause_extractor.extract_structure(parsed_xml)

            # 4. Optional: Check counterparty
            counterparty_data = None
            if check_counterparty:
                counterparty_data = self.metadata_analyzer.check_counterparties(parsed_xml, metadata)

            # 5. Analyze with RAG context
            rag_context = self._get_rag_context(parsed_xml, metadata)

            # 6. Identify risks
            risks = self._identify_risks(
                parsed_xml, structure, rag_context, counterparty_data
            )
            self._save_risks(analysis.id, contract.id, risks)

            # 7. Generate recommendations
            recommendations = self.recommendation_generator.generate_recommendations(
                risks, rag_context
            )
            self._save_recommendations(analysis.id, contract.id, recommendations)

            # 8. Generate suggested changes (LLM)
            suggested_changes = self.recommendation_generator.generate_suggested_changes(
                parsed_xml, structure, risks, recommendations, rag_context
            )
            self._save_suggested_changes(analysis.id, contract.id, suggested_changes)

            # 9. Generate annotations
            annotations = self.recommendation_generator.generate_annotations(
                risks, recommendations, suggested_changes
            )
            self._save_annotations(analysis.id, contract.id, annotations)

            # 10. Predict dispute probability
            dispute_prediction = self.metadata_analyzer.predict_disputes(
                parsed_xml, risks, rag_context
            )

            # 11. Compare with templates (if available)
            template_comparison = self.metadata_analyzer.compare_with_templates(
                parsed_xml, metadata.get('contract_type')
            )

            # 12. Update analysis record with results
            # Store metadata in risks_by_category as JSON
            import json
            analysis.risks_by_category = json.dumps({
                'risk_count': len(risks),
                'recommendation_count': len(recommendations),
                'suggested_changes_count': len(suggested_changes),
                'dispute_probability': dispute_prediction.get('score'),
                'template_comparison': template_comparison,
                'counterparty_checked': counterparty_data is not None
            }, ensure_ascii=False)
            self.db.commit()
            self.db.refresh(analysis)

            # 13. Determine next action
            next_action = self.metadata_analyzer.determine_next_action(risks, dispute_prediction)

            logger.info(f"Analysis completed: {len(risks)} risks, {len(recommendations)} recommendations")

            # Get detailed clause analyses if available
            clause_analyses = getattr(self, '_clause_analyses', [])

            return AgentResult(
                success=True,
                data={
                    'analysis_id': analysis.id,
                    'contract_id': contract.id,
                    'risks': [self._risk_to_dict(r) for r in risks],
                    'recommendations': [self._recommendation_to_dict(r) for r in recommendations],
                    'suggested_changes': [self._change_to_dict(c) for c in suggested_changes],
                    'annotations': [self._annotation_to_dict(a) for a in annotations],
                    'dispute_prediction': dispute_prediction,
                    'template_comparison': template_comparison,
                    'counterparty_data': counterparty_data,
                    'clause_analyses': clause_analyses  # Детальный анализ каждого пункта
                },
                next_action=next_action,
                metadata={
                    'message': f"Analysis completed: {len(risks)} risks identified, {len(recommendations)} recommendations, {len(clause_analyses)} clauses analyzed"
                }
            )

        except Exception as e:
            logger.error(f"Contract analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return AgentResult(
                success=False,
                data={},
                error=str(e)
            )

    def _create_analysis_record(self, contract: Contract) -> AnalysisResult:
        """Create analysis result record"""
        analysis = AnalysisResult(
            contract_id=contract.id,
            entities='{}',
            compliance_issues='{}',
            legal_issues='{}',
            risks_by_category='{}',
            recommendations='{}',
            version=1
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def _extract_structure(self, xml_content: str) -> Dict[str, Any]:
        """Extract contract structure for analysis"""
        try:
            tree = parse_xml_safely(xml_content)
            root = tree

            structure = {
                'sections': [],
                'parties': [],
                'price_info': {},
                'term_info': {},
                'payment_terms': [],
                'liability_clauses': [],
                'dispute_resolution': {}
            }

            # Extract parties
            parties = root.findall('.//party')
            for party in parties:
                party_info = {
                    'role': party.get('role', 'unknown'),
                    'name': party.findtext('name', ''),
                    'inn': party.findtext('inn', ''),
                    'xpath': f'//{party.tag}[@role="{party.get("role", "")}"]'
                }
                structure['parties'].append(party_info)

            # Extract price info
            price_elem = root.find('.//price')
            if price_elem is not None:
                structure['price_info'] = {
                    'amount': price_elem.findtext('amount', ''),
                    'currency': price_elem.findtext('currency', 'RUB'),
                    'xpath': f'//{price_elem.tag}'
                }

            # Extract term info
            term_elem = root.find('.//term')
            if term_elem is not None:
                structure['term_info'] = {
                    'start': term_elem.findtext('start', ''),
                    'end': term_elem.findtext('end', ''),
                    'xpath': f'//{term_elem.tag}'
                }

            # Extract all sections with detailed info
            for elem in root.iter():
                if elem.tag not in ['contract', 'party', 'price', 'term']:
                    text_content = elem.text or ''
                    # Also capture text from child elements
                    full_text = ''.join(elem.itertext()).strip()

                    structure['sections'].append({
                        'tag': elem.tag,
                        'text': text_content,
                        'full_text': full_text,
                        'xpath': f'//{elem.tag}',
                        'attributes': dict(elem.attrib)
                    })

            return structure

        except Exception as e:
            logger.error(f"Structure extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _extract_contract_clauses(self, xml_content: str) -> List[Dict[str, Any]]:
        """
        Extract individual contract clauses for detailed analysis
        Разбивает договор на отдельные пункты для детального анализа
        """
        try:
            logger.info("Starting clause extraction from XML...")
            tree = parse_xml_safely(xml_content)
            root = tree

            logger.info(f"Root tag: {root.tag}, children: {len(list(root))}")

            clauses = []
            clause_counter = 1

            # Рекурсивная функция для извлечения пунктов
            def extract_recursive(element, parent_path="", level=0):
                nonlocal clause_counter

                # Пропускаем только contract и metadata на верхнем уровне
                if level == 0 and element.tag in ['contract', 'document', 'root']:
                    logger.info(f"Processing root element: {element.tag}")
                    for child in element:
                        extract_recursive(child, element.tag, level + 1)
                    return

                # Получаем текст элемента
                elem_text = (element.text or '').strip()

                # Собираем весь текст из дочерних элементов
                full_text = ''.join(element.itertext()).strip()

                # Определяем тип пункта
                clause_type = self._determine_clause_type(element.tag, full_text)

                # Путь к пункту
                current_path = f"{parent_path}/{element.tag}" if parent_path else element.tag

                # Если есть содержательный текст - это пункт договора
                # Снижаем порог до 5 символов для захвата коротких пунктов
                if full_text and len(full_text) > 5:
                    clause = {
                        'id': f"clause_{clause_counter}",
                        'number': clause_counter,
                        'tag': element.tag,
                        'path': current_path,
                        'xpath': current_path,  # Use path instead of getpath
                        'title': self._extract_clause_title(element.tag, full_text),
                        'text': full_text[:2000],  # Ограничиваем текст 2000 символов
                        'type': clause_type,
                        'level': level,
                        'attributes': dict(element.attrib),
                        'children_count': len(list(element))
                    }
                    clauses.append(clause)
                    logger.debug(f"Clause {clause_counter}: {element.tag} - {full_text[:50]}")
                    clause_counter += 1

                    # Если у элемента нет детей - не идём дальше
                    if len(list(element)) == 0:
                        return

                # Рекурсивно обрабатываем дочерние элементы
                for child in element:
                    extract_recursive(child, current_path, level + 1)

            extract_recursive(root)

            logger.info(f"✓ Extracted {len(clauses)} contract clauses for detailed analysis")

            # Если не нашли пунктов - попробуем альтернативный метод
            if len(clauses) == 0:
                logger.warning("No clauses found with standard extraction, trying alternative method...")
                clauses = self._extract_clauses_alternative(xml_content)
                logger.info(f"Alternative method found {len(clauses)} clauses")

            return clauses

        except Exception as e:
            logger.error(f"Clause extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _extract_clauses_alternative(self, xml_content: str) -> List[Dict[str, Any]]:
        """
        Alternative method: split contract into sections based on XML structure
        Специально для DocumentParser который создаёт <clauses><clause>...</clause></clauses>
        """
        try:
            tree = parse_xml_safely(xml_content)
            clauses = []

            # СНАЧАЛА пробуем найти <clauses><clause> структуру от DocumentParser
            clauses_container = tree.find('.//clauses')
            if clauses_container is not None:
                logger.info("Found <clauses> container from DocumentParser")
                clause_elements = clauses_container.findall('clause')
                logger.info(f"Found {len(clause_elements)} clause elements")

                for idx, clause_elem in enumerate(clause_elements, 1):
                    # Извлекаем title и content
                    title_elem = clause_elem.find('title')
                    content_elem = clause_elem.find('content')

                    title = title_elem.text if title_elem is not None and title_elem.text else f"Пункт {idx}"

                    # Собираем весь текст из content
                    if content_elem is not None:
                        paragraphs = content_elem.findall('paragraph')
                        full_text = '\n'.join([p.text for p in paragraphs if p.text])
                    else:
                        full_text = ''.join(clause_elem.itertext()).strip()

                    if full_text and len(full_text) > 10:
                        clause = {
                            'id': clause_elem.get('id', f"clause_{idx}"),
                            'number': idx,
                            'tag': 'clause',
                            'path': f"/clauses/clause[{idx}]",
                            'xpath': f"/clauses/clause[{idx}]",  # Use path instead of getpath
                            'title': title,
                            'text': full_text[:2000],
                            'type': clause_elem.get('type', self._determine_clause_type(title, full_text)),
                            'level': 0,
                            'attributes': dict(clause_elem.attrib),
                            'children_count': len(list(clause_elem))
                        }
                        clauses.append(clause)
                        logger.info(f"✓ Extracted clause {idx}: {title[:50]}")

                if len(clauses) > 0:
                    logger.info(f"✅ Successfully extracted {len(clauses)} clauses from DocumentParser format")
                    return clauses[:50]  # Limit to 50

            # FALLBACK: если нет <clauses>, берём все элементы с текстом
            logger.info("No <clauses> found, trying generic element extraction...")
            all_elements = list(tree.iter())
            logger.info(f"Found {len(all_elements)} total XML elements")

            clause_counter = 1
            for elem in all_elements:
                full_text = ''.join(elem.itertext()).strip()

                # Берём элементы с текстом длиннее 10 символов
                if full_text and len(full_text) > 10:
                    # Пропускаем элементы, чей текст полностью совпадает с родителем
                    parent = elem.getparent()
                    if parent is not None:
                        parent_text = ''.join(parent.itertext()).strip()
                        if full_text == parent_text:
                            continue

                    clause = {
                        'id': f"clause_{clause_counter}",
                        'number': clause_counter,
                        'tag': elem.tag,
                        'path': f"/{elem.tag}",
                        'xpath': f"/{elem.tag}",  # Use path instead of getpath
                        'title': self._extract_clause_title(elem.tag, full_text),
                        'text': full_text[:2000],
                        'type': self._determine_clause_type(elem.tag, full_text),
                        'level': 0,
                        'attributes': dict(elem.attrib),
                        'children_count': len(list(elem))
                    }
                    clauses.append(clause)
                    clause_counter += 1

            return clauses[:50]  # Ограничиваем до 50 пунктов для разумного времени анализа

        except Exception as e:
            logger.error(f"Alternative extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _determine_clause_type(self, tag: str, text: str) -> str:
        """Определяет тип пункта договора"""
        tag_lower = tag.lower()
        text_lower = text.lower()

        if any(word in tag_lower for word in ['price', 'payment', 'cost', 'цена', 'оплата', 'стоимость']):
            return 'financial'
        elif any(word in tag_lower for word in ['term', 'deadline', 'срок', 'период']):
            return 'temporal'
        elif any(word in tag_lower for word in ['party', 'сторон', 'контрагент']):
            return 'parties'
        elif any(word in tag_lower for word in ['liability', 'penalty', 'ответственность', 'штраф', 'пеня']):
            return 'liability'
        elif any(word in tag_lower for word in ['dispute', 'arbitration', 'спор', 'арбитраж']):
            return 'dispute'
        elif any(word in tag_lower for word in ['subject', 'предмет', 'объект']):
            return 'subject'
        elif any(word in tag_lower for word in ['termination', 'расторжение']):
            return 'termination'
        else:
            return 'general'

    def _extract_clause_title(self, tag: str, text: str) -> str:
        """Извлекает заголовок пункта"""
        # Берём первые 100 символов или до первой точки
        lines = text.split('\n')
        first_line = lines[0].strip() if lines else text

        if len(first_line) > 80:
            return first_line[:80] + "..."

        return first_line or tag

    def _check_counterparties(
        self, xml_content: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check counterparty information via APIs"""
        try:
            root = parse_xml_safely(xml_content)
            parties = root.findall('.//party')

            results = {}
            for party in parties:
                inn = party.findtext('inn', '').strip()
                name = party.findtext('name', '')

                if inn:
                    logger.info(f"Checking counterparty: {name} (INN: {inn})")
                    check_result = self.counterparty_service.check_counterparty(
                        inn=inn,
                        check_bankruptcy=True
                    )
                    results[name] = check_result

            return results

        except Exception as e:
            logger.error(f"Counterparty check failed: {e}")
            return {}

    def _get_rag_context(
        self, xml_content: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get RAG context (analogues + precedents + legal norms) + contract summary"""
        try:
            # Извлекаем базовую информацию о договоре из XML
            from lxml import etree
            tree = parse_xml_safely(xml_content)

            # Извлекаем стороны
            parties = []
            for party in tree.findall('.//party'):
                parties.append({
                    'name': party.findtext('name', 'Не указано'),
                    'role': party.get('role', 'unknown'),
                    'inn': party.findtext('inn', '')
                })

            # Извлекаем тип договора из тега или метаданных
            contract_type = metadata.get('contract_type', 'unknown')
            if contract_type == 'unknown':
                # Пытаемся определить из содержимого
                root_tag = tree.tag if hasattr(tree, 'tag') else 'contract'
                contract_type = root_tag.replace('_', ' ').replace('contract', 'договор')

            # Извлекаем предмет договора
            subject = metadata.get('subject', '')
            if not subject:
                # Ищем в first paragraph или description
                desc_elem = tree.find('.//description')
                if desc_elem is not None and desc_elem.text:
                    subject = desc_elem.text[:200]
                else:
                    subject = "Не указан явно"

            contract_summary = {
                'type': contract_type,
                'parties': parties,
                'subject': subject,
                'party_count': len(parties)
            }

            # Search RAG if available
            rag_results = []
            rag_context = ""

            if self.rag_system:
                query = f"Договор {contract_type}: {subject}"
                rag_results = self.rag_system.search(
                    query=query,
                    n_results=10,
                    filter_metadata={'type': ['analogue', 'precedent', 'legal_norm']}
                )
                rag_context = "\n\n".join([
                    f"[{r['metadata'].get('type', 'unknown')}] {r['text']}"
                    for r in rag_results
                ])

            return {
                'sources': rag_results,
                'context': rag_context,
                'contract_summary': contract_summary
            }

        except Exception as e:
            logger.error(f"RAG context retrieval failed: {e}")
            # Возвращаем минимальный контекст
            return {
                'sources': [],
                'context': '',
                'contract_summary': {
                    'type': metadata.get('contract_type', 'неизвестный'),
                    'parties': [],
                    'subject': metadata.get('subject', 'не указан')
                }
            }


    def _analyze_clauses_batch(
        self, clauses: List[Dict[str, Any]], rag_context: Dict[str, Any], batch_size: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Батч-анализ нескольких пунктов договора за один LLM вызов
        Экономит токены на system prompt

        Args:
            clauses: Список пунктов для анализа
            rag_context: Контекст из RAG
            batch_size: Сколько пунктов анализировать за раз (оптимально 10-15 для gpt-4o-mini)

        Returns:
            Список результатов анализа
        """
        all_analyses = []

        # Извлекаем контекст договора из RAG
        contract_summary = rag_context.get('contract_summary', {})
        contract_type = contract_summary.get('type', 'неизвестный')
        parties = contract_summary.get('parties', [])
        subject = contract_summary.get('subject', 'не указан')

        # Разбиваем на батчи
        for i in range(0, len(clauses), batch_size):
            batch = clauses[i:i + batch_size]

            logger.info(f"Analyzing batch {i//batch_size + 1}: clauses {i+1}-{i+len(batch)}")

            # Формируем промпт для батча
            clauses_text = ""
            for idx, clause in enumerate(batch, 1):
                clauses_text += f"""
[ПУНКТ {clause['number']}]
Заголовок: {clause['title']}
Текст: {clause['text'][:300]}{'...' if len(clause['text']) > 300 else ''}
---
"""

            prompt = f"""Ты - опытный юрист-эксперт по договорному праву РФ.

КОНТЕКСТ ДОГОВОРА:
- Тип договора: {contract_type}
- Стороны: {', '.join([p.get('name', '') for p in parties]) if parties else 'не указаны'}
- Предмет: {subject}

ЗАДАЧА: Проанализируй {len(batch)} пунктов договора как профессиональный юрист.

{clauses_text}

Для КАЖДОГО пункта проведи детальную юридическую экспертизу и верни JSON в массиве:
[
  {{
    "clause_number": <номер пункта>,
    "clarity_score": <0-10, где 10 - идеально чёткая формулировка>,
    "legal_compliance": {{
      "score": <0-10, где 10 - полное соответствие ГК РФ>,
      "issues": ["конкретная проблема со ссылкой на статью ГК РФ"],
      "relevant_laws": ["ст. 421 ГК РФ - свобода договора"]
    }},
    "risks": [
      {{
        "risk_type": "legal|financial|operational|reputational",
        "severity": "high|medium|low",
        "probability": "high|medium|low",
        "title": "Краткое название риска",
        "description": "Подробное описание риска и его последствий",
        "consequences": "Конкретные последствия для вашей компании"
      }}
    ],
    "recommendations": [
      {{
        "priority": "critical|high|medium|low",
        "category": "legal_compliance|risk_mitigation|financial_optimization|clarity_improvement",
        "title": "Краткое название рекомендации",
        "description": "Конкретная рекомендация с обоснованием",
        "reasoning": "Почему это важно",
        "expected_benefit": "Ожидаемая польза от внедрения"
      }}
    ],
    "ambiguities": ["Конкретная двусмысленность в формулировке"],
    "missing_elements": ["Отсутствующий элемент, обязательный по ГК РФ"]
  }}
]

ТРЕБОВАНИЯ К АНАЛИЗУ:
1. **ВАЖНО:** Не ставь оценки 0/10 или 1/10 без КРАЙНЕ веской причины. Минимальная оценка для обычного текста - 3/10. Оценка 0/10 допустима ТОЛЬКО если:
   - Текст полностью отсутствует или нечитаем
   - Пункт содержит прямое нарушение закона
   - Формулировка абсолютно непригодна для использования
2. Оценивай реальный текст по существу, а не формально
3. В legal_compliance указывай конкретные статьи ГК РФ (ст. 309, 310, 330, 421, 431, 450, 451, 702, 708 и др.)
4. В risks описывай РЕАЛЬНЫЕ юридические риски с конкретными последствиями
5. В recommendations давай КОНКРЕТНЫЕ применимые советы, не общие фразы
6. Если пункт действительно проблемный - укажи это с детальным обоснованием"""

            try:
                # Используем быструю модель для первого уровня
                logger.info(f"🔍 DEBUG: Using model = {self.llm.model}, provider = {self.llm.provider}")
                logger.info(f"🔍 DEBUG: Prompt length = {len(prompt)} characters (batch of {len(batch)} clauses)")
                response = self.llm.call(
                    prompt=prompt,
                    system_prompt="""Ты - ведущий эксперт по договорному праву РФ с 15-летним опытом.

ТВОЯ РОЛЬ: Анализируй договоры как профессиональный юрист, выявляя РЕАЛЬНЫЕ риски и давая КОНКРЕТНЫЕ рекомендации.

КРИТИЧЕСКИ ВАЖНО:
1. Отвечай СТРОГО в формате JSON массива
2. Проводи РЕАЛЬНУЮ юридическую экспертизу, не формальную
3. Ссылайся на конкретные статьи ГК РФ (ст. 309, 310, 330, 421, 431, 450, 451 и др.)
4. Оценки давай по реальному качеству формулировок, не ставь 0/10 без причины
5. Риски описывай с последствиями и вероятностью
6. Рекомендации должны быть КОНКРЕТНЫМИ и ПРИМЕНИМЫМИ

Твой анализ будет использован юристами компании для принятия решений!""",
                    response_format="json",
                    temperature=0.2,
                    max_tokens=settings.llm_test_max_tokens if settings.llm_test_mode else settings.llm_max_tokens
                )

                # Parse response
                batch_analyses = response if isinstance(response, list) else []

                # Валидация и исправление оценок 0/10
                for analysis in batch_analyses:
                    # Исправляем оценку чёткости если 0
                    if analysis.get('clarity_score', 0) == 0:
                        logger.warning(f"Clause {analysis.get('clause_number')} has clarity_score=0, setting to 3 (needs review)")
                        analysis['clarity_score'] = 3

                    # Исправляем оценку соответствия если 0
                    if isinstance(analysis.get('legal_compliance'), dict):
                        if analysis['legal_compliance'].get('score', 0) == 0:
                            logger.warning(f"Clause {analysis.get('clause_number')} has legal_compliance=0, setting to 3 (needs review)")
                            analysis['legal_compliance']['score'] = 3
                            if not analysis['legal_compliance'].get('issues'):
                                analysis['legal_compliance']['issues'] = ['Требуется дополнительная правовая экспертиза']

                if not batch_analyses:
                    logger.warning(f"Batch analysis returned empty/invalid response, falling back to individual analysis")
                    # Fallback: analyze individually
                    for clause in batch:
                        try:
                            analysis = self._analyze_clause_detailed(clause, rag_context)
                            all_analyses.append(analysis)
                        except Exception as e:
                            logger.error(f"Individual analysis failed for clause {clause['number']}: {e}")
                            all_analyses.append(self._get_fallback_analysis(clause))
                else:
                    # Add xpath from original clauses
                    for analysis in batch_analyses:
                        clause_num = analysis.get('clause_number')
                        # Find matching clause
                        for clause in batch:
                            if clause['number'] == clause_num:
                                analysis['clause_xpath'] = clause['xpath']
                                analysis['clause_title'] = clause['title']
                                break
                        all_analyses.append(analysis)

                logger.info(f"✓ Batch {i//batch_size + 1} analyzed: {len(batch_analyses)} clauses")

            except Exception as e:
                logger.error(f"Batch analysis failed: {e}, falling back to individual analysis")
                # Fallback: analyze individually
                for clause in batch:
                    try:
                        analysis = self._analyze_clause_detailed(clause, rag_context)
                        all_analyses.append(analysis)
                    except Exception as e2:
                        logger.error(f"Individual analysis failed for clause {clause['number']}: {e2}")
                        all_analyses.append(self._get_fallback_analysis(clause))

        return all_analyses

    def analyze_deep(self, clause_ids: list, contract_id: str, xml_content: str, rag_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Глубокий анализ конкретных пунктов с использованием gpt-4o (Уровень 2)
        
        Args:
            clause_ids: Список ID пунктов для глубокого анализа
            contract_id: ID договора
            xml_content: XML контент договора
            rag_context: Контекст из RAG
            
        Returns:
            Список детальных анализов пунктов с прецедентами и рекомендациями
        """
        from config.settings import settings
        from ..services.llm_gateway import LLMGateway
        
        logger.info(f"Starting DEEP analysis (Level 2) for {len(clause_ids)} clauses with {settings.llm_deep_model}")
        
        # Create deep LLM with gpt-4o
        deep_llm = LLMGateway(model=settings.llm_deep_model)
        
        # Extract clauses
        all_clauses = self._extract_contract_clauses(xml_content)
        selected_clauses = [c for c in all_clauses if c['id'] in clause_ids or c['number'] in clause_ids]
        
        if not selected_clauses:
            logger.warning(f"No clauses found for deep analysis with ids: {clause_ids}")
            return []
        
        deep_analyses = []
        
        for clause in selected_clauses:
            logger.info(f"Deep analyzing clause {clause['number']}: {clause['title'][:60]}")
            
            # Detailed prompt for deep analysis
            prompt = f"""Выполни ГЛУБОКИЙ юридический анализ пункта договора.

ПУНКТ №{clause['number']}: {clause['title']}
ТЕКСТ:
{clause['text']}

КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ:
{rag_context.get('context', '')[:1000]}

Проведи детальную экспертизу:

1. ЮРИДИЧЕСКИЙ АНАЛИЗ:
   - Соответствие ГК РФ, специальным законам
   - Ссылки на конкретные статьи законов
   - Выявление юридических коллизий
   - Анализ исполнимости через суд

2. РИСКИ С ПРЕЦЕДЕНТАМИ:
   - Конкретные судебные дела (номера, даты, суды)
   - Статистика споров по аналогичным пунктам
   - Финансовые последствия (диапазоны сумм)
   - Вероятность возникновения спора (%)

3. АЛЬТЕРНАТИВНЫЕ ФОРМУЛИРОВКИ:
   - 2-3 варианта улучшенных формулировок
   - Обоснование каждого варианта
   - Ссылки на best practices

4. РЕКОМЕНДАЦИИ ЭКСПЕРТОВ:
   - Позиция ВС РФ по аналогичным вопросам
   - Мнения ведущих юристов
   - Отраслевые стандарты

Верни JSON:
{{
  "clause_number": {clause['number']},
  "deep_legal_analysis": {{
    "compliance_score": 0-10,
    "relevant_laws": [
      {{
        "law": "ГК РФ",
        "article": "ст. 421",
        "relevance": "объяснение применимости",
        "compliance_status": "compliant|non_compliant|unclear"
      }}
    ],
    "legal_conflicts": ["конфликт 1", "конфликт 2"],
    "enforceability_score": 0-10,
    "enforceability_notes": "анализ исполнимости"
  }},
  "risks_with_precedents": [
    {{
      "risk_type": "тип",
      "severity": "critical|high|medium|low",
      "probability_percent": 0-100,
      "description": "детальное описание",
      "financial_impact_range": "от X до Y рублей",
      "precedents": [
        {{
          "case_number": "номер дела",
          "court": "суд",
          "date": "дата",
          "outcome": "исход",
          "relevance": "почему релевантно"
        }}
      ],
      "mitigation": "как минимизировать"
    }}
  ],
  "alternative_formulations": [
    {{
      "variant_number": 1,
      "formulation": "текст формулировки",
      "advantages": ["преимущество 1", "преимущество 2"],
      "legal_basis": "обоснование",
      "best_practice_reference": "ссылка на практику"
    }}
  ],
  "expert_recommendations": [
    {{
      "source": "ВС РФ / эксперт",
      "recommendation": "рекомендация",
      "citation": "ссылка на источник"
    }}
  ],
  "overall_risk_score": 0-100,
  "priority": "critical|high|medium|low",
  "summary": "краткое резюме глубокого анализа"
}}"""

            try:
                response = deep_llm.call(
                    prompt=prompt,
                    system_prompt="Ты ведущий эксперт по договорному праву РФ. Проводишь детальную экспертизу на уровне старшего партнёра юридической фирмы. Используешь конкретные ссылки на законы, судебную практику и прецеденты.",
                    response_format="json",
                    temperature=0.3,
                    max_tokens=settings.llm_max_tokens,
                    use_cache=True,
                    db_session=self.db
                )
                
                response['clause_id'] = clause['id']
                response['clause_xpath'] = clause['xpath']
                response['clause_title'] = clause['title']
                response['analysis_level'] = 'deep'
                response['model_used'] = settings.llm_deep_model
                
                deep_analyses.append(response)
                logger.info(f"✓ Deep analysis complete for clause {clause['number']}: {response.get('overall_risk_score', 'N/A')}/100 risk score")
                
            except Exception as e:
                logger.error(f"Deep analysis failed for clause {clause['number']}: {e}")
                # Fallback
                deep_analyses.append({
                    'clause_number': clause['number'],
                    'clause_id': clause['id'],
                    'error': str(e),
                    'analysis_level': 'deep',
                    'summary': 'Глубокий анализ не удался из-за ошибки'
                })
        
        logger.info(f"Deep analysis complete: {len(deep_analyses)} clauses analyzed with {settings.llm_deep_model}")
        return deep_analyses

    def _analyze_clause_detailed(
        self, clause: Dict[str, Any], rag_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Детальный LLM-анализ отдельного пункта договора
        Returns detailed analysis including risks, issues, recommendations
        """
        try:
            # Сокращённый промпт для избежания переполнения
            prompt = f"""Проанализируй пункт договора:

ПУНКТ №{clause['number']}: {clause['title']}
ТЕКСТ: {clause['text']}

Оцени:
1. Чёткость формулировки (0-10)
2. Правовое соответствие (0-10)
3. Риски (тип, серьёзность, описание)
4. Рекомендации по улучшению
5. Двусмысленности
6. Отсутствующие элементы

JSON формат:
{{
  "clause_id": "{clause['id']}",
  "clarity_score": 0-10,
  "clarity_assessment": "подробная оценка чёткости формулировки",
  "legal_compliance": {{
    "score": 0-10,
    "issues": ["проблема 1", "проблема 2"],
    "relevant_laws": ["ГК РФ ст. XXX", "закон Y"]
  }},
  "risks": [
    {{
      "risk_type": "financial|legal|operational|reputational",
      "severity": "critical|significant|minor",
      "probability": "high|medium|low",
      "title": "краткое название риска",
      "description": "ПОДРОБНОЕ описание риска",
      "consequences": "возможные последствия",
      "affected_party": "кто пострадает"
    }}
  ],
  "ambiguities": ["двусмысленность 1", "двусмысленность 2"],
  "missing_elements": ["что отсутствует в пункте"],
  "recommendations": [
    {{
      "priority": "critical|high|medium|low",
      "recommendation": "что сделать",
      "reasoning": "почему это важно",
      "suggested_text": "предлагаемая формулировка (если применимо)"
    }}
  ],
  "precedents": ["судебная практика"],
  "overall_assessment": "общая оценка",
  "improvement_priority": "critical|high|medium|low"
}}"""

            logger.info(f"Analyzing clause {clause['number']}: {clause['title'][:50]}")

            # Try with JSON format first
            try:
                response = self.llm.call(
                    prompt=prompt,
                    system_prompt=self.get_system_prompt(),
                    response_format="json",
                    temperature=0.2
                )

                # Parse JSON response (already parsed if response_format='json')
                analysis = response if isinstance(response, dict) else json.loads(response)

            except (json.JSONDecodeError, ValueError) as e:
                # Fallback: try with text format and parse manually
                logger.warning(f"JSON format failed for clause {clause['number']}, trying text format: {e}")

                try:
                    response = self.llm.call(
                        prompt=prompt + "\n\nВерни ТОЛЬКО JSON, без дополнительного текста.",
                        system_prompt=self.get_system_prompt(),
                        response_format="text",
                        temperature=0.2
                    )

                    # Try to extract JSON from response
                    import re
                    json_match = re.search(r'\{.*\}', response, re.DOTALL)
                    if json_match:
                        analysis = json.loads(json_match.group(0))
                    else:
                        logger.error(f"No JSON found in text response for clause {clause['number']}")
                        return self._get_fallback_analysis(clause)

                except Exception as e2:
                    logger.error(f"Text format also failed for clause {clause['number']}: {e2}")
                    return self._get_fallback_analysis(clause)

            analysis['clause_number'] = clause['number']
            analysis['clause_xpath'] = clause['xpath']

            logger.info(f"✓ Clause {clause['number']} analyzed: {len(analysis.get('risks', []))} risks, {len(analysis.get('recommendations', []))} recommendations")

            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response for clause {clause['number']}: {e}")
            return self._get_fallback_analysis(clause)
        except Exception as e:
            logger.error(f"Clause analysis failed for {clause['number']}: {e}")
            return self._get_fallback_analysis(clause)

    def _get_fallback_analysis(self, clause: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback analysis if LLM fails"""
        return {
            'clause_id': clause['id'],
            'clause_number': clause['number'],
            'clause_xpath': clause['xpath'],
            'clarity_score': 5,
            'clarity_assessment': 'Анализ не выполнен из-за ошибки',
            'legal_compliance': {'score': 5, 'issues': [], 'relevant_laws': []},
            'risks': [],
            'ambiguities': [],
            'missing_elements': [],
            'recommendations': [],
            'precedents': [],
            'overall_assessment': 'Требуется повторный анализ',
            'improvement_priority': 'medium'
        }

    def _identify_risks(
        self,
        xml_content: str,
        structure: Dict[str, Any],
        rag_context: Dict[str, Any],
        counterparty_data: Optional[Dict[str, Any]]
    ) -> List[ContractRisk]:
        """Identify contract risks using detailed clause-by-clause LLM analysis"""
        logger.info("🔍 DEBUG: _identify_risks called (NEW method with batching)")
        try:
            logger.info("Starting detailed clause-by-clause risk identification...")

            # Извлекаем все пункты договора с помощью ClauseExtractor
            clauses = self.clause_extractor.extract_clauses(xml_content)
            logger.info(f"Extracted {len(clauses)} clauses for analysis")

            if not clauses:
                logger.warning("No clauses extracted, falling back to legacy method")
                return self._identify_risks_legacy(xml_content, structure, rag_context, counterparty_data)

            # BATCH ANALYSIS - анализируем пунктами по batch_size за раз
            # Ограничиваем количество пунктов в тестовом режиме
            from config.settings import settings
            max_clauses = settings.llm_test_max_clauses if settings.llm_test_mode else len(clauses)
            batch_size = settings.llm_batch_size

            logger.info(f"Will analyze {min(len(clauses), max_clauses)} clauses in batches of {batch_size}")

            # Используем RiskAnalyzer для батч-анализа
            logger.info(f"🔍 DEBUG: Starting batch analysis for {len(clauses[:max_clauses])} clauses")
            all_clause_analyses = self.risk_analyzer.analyze_clauses_batch(
                clauses[:max_clauses],
                rag_context,
                batch_size=batch_size
            )
            logger.info(f"🔍 DEBUG: Batch analysis returned {len(all_clause_analyses)} results")

            # Извлекаем риски из анализов с помощью RiskAnalyzer
            logger.info(f"🔍 DEBUG: Extracting risks from {len(all_clause_analyses)} clause analyses")
            all_risks = self.risk_analyzer.identify_risks(all_clause_analyses)

            # Сохраняем детальные анализы пунктов для отображения в UI
            if all_clause_analyses:
                self._store_clause_analyses(all_clause_analyses)
                logger.info(f"Detailed analysis complete: {len(all_risks)} risks from {len(all_clause_analyses)} clauses")
            else:
                logger.warning("No clauses were successfully analyzed, using legacy method")
                return self._identify_risks_legacy(xml_content, structure, rag_context, counterparty_data)

            return all_risks

        except Exception as e:
            logger.error(f"Detailed risk identification failed: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to legacy method
            return self._identify_risks_legacy(xml_content, structure, rag_context, counterparty_data)

    def _store_clause_analyses(self, analyses: List[Dict[str, Any]]):
        """Store detailed clause analyses for UI display"""
        # Сохраняем в памяти для передачи в результат
        if not hasattr(self, '_clause_analyses'):
            self._clause_analyses = []
        self._clause_analyses = analyses

    def _identify_risks_legacy(
        self,
        xml_content: str,
        structure: Dict[str, Any],
        rag_context: Dict[str, Any],
        counterparty_data: Optional[Dict[str, Any]]
    ) -> List[ContractRisk]:
        logger.info("⚠️ DEBUG: _identify_risks_legacy called (OLD method, NO batching, EXPENSIVE!)")
        """Legacy risk identification method (fallback)"""
        try:
            # Prepare prompt
            prompt = self._build_risk_identification_prompt(
                xml_content, structure, rag_context, counterparty_data
            )

            # Call LLM
            response = self.llm.call(
                prompt=prompt,
                system_prompt=self.get_system_prompt(),
                response_format="json",
                temperature=0.3
            )

            # Parse JSON response
            risks_data = response if isinstance(response, dict) else json.loads(response)

            # Convert to ContractRisk objects
            risks = []
            for risk_dict in risks_data.get('risks', []):
                risk = ContractRisk(
                    risk_type=risk_dict.get('risk_type', 'legal'),
                    severity=risk_dict.get('severity', 'minor'),
                    probability=risk_dict.get('probability'),
                    title=risk_dict.get('title', ''),
                    description=risk_dict.get('description', ''),
                    consequences=risk_dict.get('consequences'),
                    xpath_location=risk_dict.get('xpath_location'),
                    section_name=risk_dict.get('section_name'),
                    rag_sources=risk_dict.get('rag_sources', [])
                )
                risks.append(risk)

            return risks

        except Exception as e:
            logger.error(f"Legacy risk identification failed: {e}")
            return []

    def _build_risk_identification_prompt(
        self,
        xml_content: str,
        structure: Dict[str, Any],
        rag_context: Dict[str, Any],
        counterparty_data: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for risk identification"""
        prompt = "Analyze this contract and identify ALL risks.\n\n"
        prompt += "CONTRACT XML:\n"
        prompt += xml_content[:5000]
        prompt += "\n\n"

        prompt += "CONTRACT STRUCTURE:\n"
        prompt += json.dumps(structure, ensure_ascii=False, indent=2)
        prompt += "\n\n"

        if rag_context.get('context'):
            prompt += "RELEVANT LEGAL CONTEXT (from RAG):\n"
            prompt += rag_context['context'][:3000]
            prompt += "\n\n"

        if counterparty_data:
            prompt += "COUNTERPARTY CHECK RESULTS:\n"
            prompt += json.dumps(counterparty_data, ensure_ascii=False, indent=2)
            prompt += "\n\n"

        prompt += """Identify ALL risks in these categories:
- financial (price, payment, penalties)
- legal (compliance, validity, enforceability)
- operational (execution, delivery, quality)
- reputational (brand, relationships)

For each risk, provide:
{
  "risks": [
    {
      "risk_type": "financial|legal|operational|reputational",
      "severity": "critical|significant|minor",
      "probability": "high|medium|low",
      "title": "Short title",
      "description": "Detailed description",
      "consequences": "Qualitative consequences (no monetary)",
      "xpath_location": "XPath to problem section",
      "section_name": "Section name",
      "rag_sources": ["Source 1", "Source 2"]
    }
  ]
}

Return ONLY valid JSON, no additional text."""

        return prompt

    def _generate_recommendations(
        self,
        xml_content: str,
        structure: Dict[str, Any],
        risks: List[ContractRisk],
        rag_context: Dict[str, Any]
    ) -> List[ContractRecommendation]:
        """Generate recommendations based on risks"""
        try:
            prompt = "Based on identified risks, generate recommendations.\n\n"

            prompt += "IDENTIFIED RISKS:\n"
            risks_summary = [
                {
                    'id': i,
                    'type': r.risk_type,
                    'severity': r.severity,
                    'title': r.title,
                    'description': r.description
                }
                for i, r in enumerate(risks)
            ]
            prompt += json.dumps(risks_summary, ensure_ascii=False, indent=2)
            prompt += "\n\n"

            if rag_context.get('context'):
                prompt += "LEGAL CONTEXT:\n"
                prompt += rag_context['context'][:2000]
                prompt += "\n\n"

            prompt += """Generate recommendations for each risk.

Return JSON:
{
  "recommendations": [
    {
      "category": "legal_compliance|risk_mitigation|financial_optimization|etc",
      "priority": "critical|high|medium|low",
      "title": "Short title",
      "description": "What to do",
      "reasoning": "Why this recommendation",
      "expected_benefit": "Expected outcome",
      "related_risk_id": 0,
      "implementation_complexity": "easy|medium|hard"
    }
  ]
}

Return ONLY valid JSON."""

            response = self.llm.call(
                prompt=prompt,
                system_prompt=self.get_system_prompt(),
                response_format="json",
                temperature=0.3
            )

            recommendations_data = response if isinstance(response, dict) else json.loads(response)

            recommendations = []
            for rec_dict in recommendations_data.get('recommendations', []):
                recommendation = ContractRecommendation(
                    category=rec_dict.get('category', 'general'),
                    priority=rec_dict.get('priority', 'medium'),
                    title=rec_dict.get('title', ''),
                    description=rec_dict.get('description', ''),
                    reasoning=rec_dict.get('reasoning'),
                    expected_benefit=rec_dict.get('expected_benefit'),
                    implementation_complexity=rec_dict.get('implementation_complexity')
                )
                recommendations.append(recommendation)

            return recommendations

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            return []

    def _generate_suggested_changes(
        self,
        xml_content: str,
        structure: Dict[str, Any],
        risks: List[ContractRisk],
        recommendations: List[ContractRecommendation],
        rag_context: Dict[str, Any]
    ) -> List[ContractSuggestedChange]:
        """Generate automatic suggested changes via LLM"""
        try:
            prompt = "Generate specific text changes to fix identified risks.\n\n"

            prompt += "RISKS:\n"
            prompt += json.dumps([
                {'id': i, 'title': r.title, 'description': r.description, 'xpath': r.xpath_location}
                for i, r in enumerate(risks)
            ], ensure_ascii=False, indent=2)
            prompt += "\n\n"

            prompt += "CONTRACT SECTIONS:\n"
            prompt += json.dumps(structure.get('sections', [])[:20], ensure_ascii=False, indent=2)
            prompt += "\n\n"

            if rag_context.get('context'):
                prompt += "LEGAL REFERENCES:\n"
                prompt += rag_context['context'][:2000]
                prompt += "\n\n"

            prompt += """For each risk that can be fixed by changing contract text, provide:

{
  "changes": [
    {
      "xpath_location": "XPath to section",
      "section_name": "Section name",
      "original_text": "Current problematic text",
      "suggested_text": "Improved version",
      "change_type": "addition|modification|deletion|clarification",
      "issue": "What's the problem",
      "reasoning": "Why this change fixes it",
      "legal_basis": "Reference to law/article if applicable",
      "related_risk_id": 0
    }
  ]
}

Return ONLY valid JSON."""

            response = self.llm.call(
                prompt=prompt,
                system_prompt=self.get_system_prompt(),
                response_format="json",
                temperature=0.4
            )

            changes_data = response if isinstance(response, dict) else json.loads(response)

            changes = []
            for change_dict in changes_data.get('changes', []):
                change = ContractSuggestedChange(
                    xpath_location=change_dict.get('xpath_location', ''),
                    section_name=change_dict.get('section_name'),
                    original_text=change_dict.get('original_text', ''),
                    suggested_text=change_dict.get('suggested_text', ''),
                    change_type=change_dict.get('change_type'),
                    issue=change_dict.get('issue', ''),
                    reasoning=change_dict.get('reasoning', ''),
                    legal_basis=change_dict.get('legal_basis'),
                    status='pending'
                )
                changes.append(change)

            return changes

        except Exception as e:
            logger.error(f"Suggested changes generation failed: {e}")
            return []

    def _generate_annotations(
        self,
        risks: List[ContractRisk],
        recommendations: List[ContractRecommendation],
        suggested_changes: List[ContractSuggestedChange]
    ) -> List[ContractAnnotation]:
        """Generate annotations for document sections"""
        annotations = []

        for risk in risks:
            if risk.xpath_location:
                annotation = ContractAnnotation(
                    xpath_location=risk.xpath_location,
                    section_name=risk.section_name,
                    annotation_type='risk' if risk.severity == 'critical' else 'warning',
                    content=f"{risk.title}: {risk.description}",
                    highlight_color='red' if risk.severity == 'critical' else 'yellow'
                )
                annotations.append(annotation)

        for change in suggested_changes:
            if change.xpath_location:
                annotation = ContractAnnotation(
                    xpath_location=change.xpath_location,
                    section_name=change.section_name,
                    annotation_type='suggestion',
                    content=f"Предложение: {change.issue}",
                    highlight_color='yellow'
                )
                annotations.append(annotation)

        return annotations

    def _predict_disputes(
        self,
        xml_content: str,
        risks: List[ContractRisk],
        rag_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Predict dispute probability using LLM"""
        try:
            prompt = "Predict the probability of disputes arising from this contract.\n\n"

            prompt += "IDENTIFIED RISKS:\n"
            prompt += json.dumps([
                {'type': r.risk_type, 'severity': r.severity, 'title': r.title}
                for r in risks
            ], ensure_ascii=False, indent=2)
            prompt += "\n\n"

            if rag_context.get('context'):
                prompt += "PRECEDENTS:\n"
                prompt += rag_context['context'][:1500]
                prompt += "\n\n"

            prompt += """Analyze dispute probability.

Return JSON:
{
  "overall_score": 0-100,
  "level": "low|medium|high|critical",
  "reasoning": "Why this score",
  "dispute_prone_clauses": [
    {
      "clause": "Clause description",
      "reason": "Why disputes may arise",
      "probability": "low|medium|high"
    }
  ]
}

Return ONLY valid JSON."""

            response = self.llm.call(
                prompt=prompt,
                system_prompt=self.get_system_prompt(),
                response_format="json",
                temperature=0.3
            )

            return response if isinstance(response, dict) else json.loads(response)

        except Exception as e:
            logger.error(f"Dispute prediction failed: {e}")
            return {
                'overall_score': 50,
                'level': 'medium',
                'reasoning': 'Analysis failed',
                'dispute_prone_clauses': []
            }

    def _compare_with_templates(
        self, xml_content: str, contract_type: Optional[str]
    ) -> Dict[str, Any]:
        """Compare contract with templates"""
        if not contract_type:
            return {'compared': False, 'reason': 'No contract type specified'}

        try:
            template = self.template_manager.get_template(contract_type)

            if not template:
                return {'compared': False, 'reason': f'No template for type {contract_type}'}

            root = parse_xml_safely(xml_content)
            template_root = etree.fromstring(template.xml_content.encode('utf-8'))

            contract_tags = set([elem.tag for elem in root.iter()])
            template_tags = set([elem.tag for elem in template_root.iter()])

            missing_sections = template_tags - contract_tags
            extra_sections = contract_tags - template_tags

            return {
                'compared': True,
                'template_name': template.name,
                'template_version': template.version,
                'missing_sections': list(missing_sections),
                'extra_sections': list(extra_sections),
                'match_percentage': len(contract_tags & template_tags) / len(template_tags) * 100 if template_tags else 0
            }

        except Exception as e:
            logger.error(f"Template comparison failed: {e}")
            return {'compared': False, 'reason': str(e)}

    def _determine_next_action(
        self, risks: List[ContractRisk], dispute_prediction: Dict[str, Any]
    ) -> str:
        """Determine next action based on analysis results"""
        has_critical = any(r.severity == 'critical' for r in risks)
        high_dispute_risk = dispute_prediction.get('level') in ['high', 'critical']

        if has_critical or high_dispute_risk:
            return 'review_queue'

        return 'export'

    def _save_risks(self, analysis_id: str, contract_id: str, risks: List[ContractRisk]):
        """Save risks to database"""
        for risk in risks:
            risk.analysis_id = analysis_id
            risk.contract_id = contract_id
            self.db.add(risk)
        self.db.commit()

    def _save_recommendations(
        self, analysis_id: str, contract_id: str, recommendations: List[ContractRecommendation]
    ):
        """Save recommendations to database"""
        for rec in recommendations:
            rec.analysis_id = analysis_id
            rec.contract_id = contract_id
            self.db.add(rec)
        self.db.commit()

    def _save_suggested_changes(
        self, analysis_id: str, contract_id: str, changes: List[ContractSuggestedChange]
    ):
        """Save suggested changes to database"""
        for change in changes:
            change.analysis_id = analysis_id
            change.contract_id = contract_id
            self.db.add(change)
        self.db.commit()

    def _save_annotations(
        self, analysis_id: str, contract_id: str, annotations: List[ContractAnnotation]
    ):
        """Save annotations to database"""
        for annotation in annotations:
            annotation.analysis_id = analysis_id
            annotation.contract_id = contract_id
            self.db.add(annotation)
        self.db.commit()

    def _risk_to_dict(self, risk: ContractRisk) -> Dict[str, Any]:
        """Convert ContractRisk to dict"""
        return {
            'id': risk.id,
            'risk_type': risk.risk_type,
            'severity': risk.severity,
            'probability': risk.probability,
            'title': risk.title,
            'description': risk.description,
            'consequences': risk.consequences,
            'xpath_location': risk.xpath_location,
            'section_name': risk.section_name
        }

    def _recommendation_to_dict(self, rec: ContractRecommendation) -> Dict[str, Any]:
        """Convert ContractRecommendation to dict"""
        return {
            'id': rec.id,
            'category': rec.category,
            'priority': rec.priority,
            'title': rec.title,
            'description': rec.description,
            'reasoning': rec.reasoning,
            'expected_benefit': rec.expected_benefit,
            'implementation_complexity': rec.implementation_complexity
        }

    def _change_to_dict(self, change: ContractSuggestedChange) -> Dict[str, Any]:
        """Convert ContractSuggestedChange to dict"""
        return {
            'id': change.id,
            'xpath_location': change.xpath_location,
            'section_name': change.section_name,
            'original_text': change.original_text,
            'suggested_text': change.suggested_text,
            'change_type': change.change_type,
            'issue': change.issue,
            'reasoning': change.reasoning,
            'legal_basis': change.legal_basis,
            'status': change.status
        }

    def _annotation_to_dict(self, annotation: ContractAnnotation) -> Dict[str, Any]:
        """Convert ContractAnnotation to dict"""
        return {
            'id': annotation.id,
            'xpath_location': annotation.xpath_location,
            'section_name': annotation.section_name,
            'annotation_type': annotation.annotation_type,
            'content': annotation.content,
            'highlight_color': annotation.highlight_color
        }


__all__ = ["ContractAnalyzerAgent"]
