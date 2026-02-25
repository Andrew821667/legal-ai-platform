"""
AI Brain - интеграция с OpenAI GPT + RAG
"""
import logging
from typing import List, Dict, Optional, AsyncGenerator
import json
from openai import OpenAI
from config import Config
config = Config()
import prompts
import database
import knowledge_engine

logger = logging.getLogger(__name__)


class AIBrain:
    """Класс для работы с OpenAI API"""

    def __init__(self):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.OPENAI_MODEL
        self.max_tokens = config.MAX_TOKENS
        self.temperature = config.TEMPERATURE

    async def generate_response_stream(self, conversation_history: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """
        Генерация ответа с потоковой передачей (streaming) от OpenAI

        Args:
            conversation_history: История диалога в формате [{"role": "user"/"assistant", "message": "..."}]

        Yields:
            Части ответа ассистента по мере их генерации
        """
        try:
            # Преобразуем историю в формат OpenAI
            messages = [{"role": "system", "content": prompts.SYSTEM_PROMPT}]

            # Ограничиваем контекст последними 20 сообщениями для избежания обрывов
            limited_history = conversation_history[-20:] if len(conversation_history) > 20 else conversation_history
            
            for msg in limited_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg.get("content") or msg.get("message")
                })

            logger.debug(f"Sending streaming request to OpenAI with {len(messages)} messages")

            # Запрос к OpenAI с включенным streaming
            # ВАЖНО: max_completion_tokens = лимит ТОЛЬКО на ответ (не включает prompt и историю!)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_completion_tokens=config.MAX_COMPLETION_TOKENS,
                temperature=self.temperature,
                stream=True  # Включаем потоковую передачу!
            )

            # Отдаем части ответа по мере их поступления
            finish_reason = None
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

                # Проверяем причину завершения
                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason

            # Логируем причину завершения
            if finish_reason == "length":
                logger.warning("⚠️ Response was truncated due to max_tokens limit!")
            elif finish_reason == "stop":
                logger.info("✓ Streaming response completed normally (stop)")
            else:
                logger.info(f"Streaming response completed (finish_reason: {finish_reason})")

        except Exception as e:
            logger.error(f"Error generating streaming response: {e}")
            yield "Извините, произошла ошибка при обработке вашего запроса. Попробуйте еще раз или свяжитесь с нашей командой напрямую."

    def generate_response(self, conversation_history: List[Dict[str, str]]) -> str:
        """
        Генерация ответа на основе истории диалога + RAG

        Args:
            conversation_history: История диалога в формате [{"role": "user"/"assistant", "message": "..."}]

        Returns:
            Ответ ассистента
        """
        try:
            # Преобразуем историю в формат OpenAI
            messages = [{"role": "system", "content": prompts.SYSTEM_PROMPT}]

            # Ограничиваем контекст последними 20 сообщениями для избежания обрывов
            limited_history = conversation_history[-20:] if len(conversation_history) > 20 else conversation_history
            
            # === RAG: ИЩЕМ ПОХОЖИЕ УСПЕШНЫЕ ДИАЛОГИ ===
            rag_context = ""
            try:
                # Получаем последнее сообщение клиента
                last_user_message = next(
                    (msg['message'] for msg in reversed(limited_history) if msg['role'] == 'user'),
                    None
                )
                
                if last_user_message and len(last_user_message) > 10:
                    # Получаем успешные диалоги из БД
                    successful_convos = database.db.get_successful_conversations(limit=30)
                    
                    if successful_convos:
                        # Ищем похожие через семантический поиск
                        similar = knowledge_engine.knowledge_engine.find_similar_conversations(
                            query=last_user_message,
                            conversations=successful_convos,
                            top_k=2,  # Топ-2 похожих примера
                            min_similarity=0.6  # Минимальное сходство 60%
                        )
                        
                        if similar:
                            # Форматируем примеры для промпта
                            rag_context = knowledge_engine.knowledge_engine.format_similar_examples_for_prompt(similar)
                            logger.info(f"📚 RAG: Found {len(similar)} similar conversations, adding to context")
            
            except Exception as e:
                logger.warning(f"RAG search failed (non-critical): {e}")
                # Продолжаем без RAG если что-то пошло не так
            
            # ДОБАВЛЯЕМ RAG КОНТЕКСТ ЕСЛИ НАШЛИ
            if rag_context:
                messages.append({
                    "role": "system",
                    "content": rag_context
                })
            
            # Добавляем историю диалога
            for msg in limited_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg.get("content") or msg.get("message")
                })

            logger.debug(f"Sending request to OpenAI with {len(messages)} messages (RAG: {bool(rag_context)})")

            # Запрос к OpenAI
            # ВАЖНО: max_completion_tokens = лимит ТОЛЬКО на ответ (не включает prompt!)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_completion_tokens=config.MAX_COMPLETION_TOKENS,
                temperature=self.temperature
            )

            assistant_message = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason

            # Предупреждение если ответ обрезан
            if finish_reason == "length":
                logger.warning(f"⚠️ Response truncated! ({len(assistant_message)} chars, finish_reason: length)")
            else:
                logger.info(f"Received response from OpenAI: {len(assistant_message)} chars (finish_reason: {finish_reason}, RAG: {bool(rag_context)})")

            return assistant_message

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Извините, произошла ошибка при обработке вашего запроса. Попробуйте еще раз или свяжитесь с Андреем напрямую."

    def extract_lead_data(self, conversation_history: List[Dict[str, str]]) -> Optional[Dict]:
        """
        Извлечение данных лида из истории диалога

        Args:
            conversation_history: История диалога

        Returns:
            Словарь с данными лида или None в случае ошибки
        """
        try:
            # Формируем контекст диалога
            conversation_text = "\n".join([
                f"{msg['role']}: {msg['message']}"
                for msg in conversation_history
            ])

            messages = [
                {"role": "system", "content": prompts.EXTRACT_DATA_PROMPT},
                {"role": "user", "content": f"Диалог:\n{conversation_text}"}
            ]

            logger.debug("Extracting lead data from conversation")

            # Запрос к OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500,
                temperature=0.3  # Низкая температура для более точного извлечения
            )

            response_text = response.choices[0].message.content
            logger.debug(f"Received extraction response: {response_text[:100]}")

            # Парсим JSON ответ
            # Убираем возможные markdown блоки
            response_text = response_text.strip()
            if response_text.startswith("```"):
                # Убираем markdown обертку
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            lead_data = json.loads(response_text)
            
            # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ для отладки
            logger.info(f"✅ Lead data extracted: temperature={lead_data.get('lead_temperature')}")
            logger.info(f"📊 Service: category={lead_data.get('service_category')}, need={lead_data.get('specific_need')}")
            logger.info(f"🔍 Full lead data: {json.dumps(lead_data, ensure_ascii=False)}")

            return lead_data

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON response: {e}, response: {response_text}")
            return None
        except Exception as e:
            logger.error(f"Error extracting lead data: {e}")
            return None

    def check_handoff_trigger(self, user_message: str) -> bool:
        """
        Проверка триггеров передачи админу

        Args:
            user_message: Сообщение пользователя

        Returns:
            True если нужно передать админу
        """
        message_lower = user_message.lower()

        for trigger in prompts.HANDOFF_TRIGGERS:
            if trigger.lower() in message_lower:
                logger.info(f"Handoff trigger detected: {trigger}")
                return True

        return False

    def should_offer_lead_magnet(self, lead_data: Optional[Dict]) -> bool:
        """
        Определение нужно ли предложить lead magnet

        Args:
            lead_data: Данные лида

        Returns:
            True если нужно предложить lead magnet
        """
        if not lead_data:
            return False

        # Предлагаем lead magnet если:
        # 1. Есть боль
        # 2. Есть хотя бы один контакт (email или phone) ИЛИ
        # 3. Лид теплый или горячий

        has_pain = lead_data.get('pain_point') and len(lead_data.get('pain_point', '')) > 10
        has_contact = lead_data.get('email') or lead_data.get('phone')
        temperature = lead_data.get('lead_temperature', 'cold')

        should_offer = has_pain and (has_contact or temperature in ['warm', 'hot'])

        logger.debug(f"Should offer lead magnet: {should_offer} (pain={has_pain}, contact={has_contact}, temp={temperature})")

        return should_offer


# Создание глобального экземпляра
ai_brain = AIBrain()


if __name__ == '__main__':
    # Тестирование
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Testing AIBrain...")

    # Тест генерации ответа
    test_conversation = [
        {"role": "user", "message": "Здравствуйте, интересует автоматизация договоров"}
    ]

    response = ai_brain.generate_response(test_conversation)
    print(f"\nResponse: {response[:200]}...")

    # Тест извлечения данных
    test_conversation_full = [
        {"role": "user", "message": "Здравствуйте, интересует автоматизация договоров"},
        {"role": "assistant", "message": "Здравствуйте! Расскажите подробнее о вашей команде"},
        {"role": "user", "message": "У нас 5 юристов, около 50 договоров в месяц"},
        {"role": "assistant", "message": "Понятно. Какая основная проблема?"},
        {"role": "user", "message": "Не успеваем проверять все, иногда пропускаем важные моменты. Бюджет до 500 тысяч. Мой email: ivan@company.ru"}
    ]

    lead_data = ai_brain.extract_lead_data(test_conversation_full)
    print(f"\nExtracted lead data: {json.dumps(lead_data, indent=2, ensure_ascii=False)}")
