"""
RAG (Retrieval-Augmented Generation) Engine
Извлекает релевантные примеры успешных диалогов для улучшения ответов бота
"""

import logging
import json
import numpy as np
from typing import List, Dict, Optional, Tuple
from openai import OpenAI
from config import Config

config = Config()

logger = logging.getLogger(__name__)


class KnowledgeEngine:
    """Движок для семантического поиска похожих диалогов"""
    
    def __init__(self):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.embedding_model = "text-embedding-3-small"  # Дешёвая и быстрая модель
        logger.info("KnowledgeEngine initialized")
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Получение эмбеддинга текста
        
        Args:
            text: Текст для эмбеддинга
            
        Returns:
            Вектор эмбеддинга
        """
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return []
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Вычисление косинусного сходства между двумя векторами
        
        Args:
            vec1: Первый вектор
            vec2: Второй вектор
            
        Returns:
            Косинусное сходство (0-1)
        """
        if not vec1 or not vec2:
            return 0.0
        
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)
        
        # Нормализация и скалярное произведение
        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def find_similar_conversations(
        self, 
        query: str, 
        conversations: List[Dict],
        top_k: int = 3,
        min_similarity: float = 0.5
    ) -> List[Tuple[Dict, float]]:
        """
        Поиск похожих диалогов по семантическому сходству
        
        Args:
            query: Запрос клиента
            conversations: Список диалогов для поиска
            top_k: Количество топ результатов
            min_similarity: Минимальное сходство (0-1)
            
        Returns:
            Список кортежей (диалог, сходство) отсортированный по релевантности
        """
        if not conversations:
            logger.debug("No conversations provided for similarity search")
            return []
        
        # Получаем эмбеддинг запроса
        query_embedding = self.get_embedding(query)
        
        if not query_embedding:
            logger.error("Failed to get query embedding")
            return []
        
        # Вычисляем сходство с каждым диалогом
        similarities = []
        
        for conv in conversations:
            # Формируем текст диалога для эмбеддинга
            conv_text = self._format_conversation_for_embedding(conv)
            conv_embedding = self.get_embedding(conv_text)
            
            if conv_embedding:
                similarity = self.cosine_similarity(query_embedding, conv_embedding)
                
                if similarity >= min_similarity:
                    similarities.append((conv, similarity))
        
        # Сортируем по убыванию сходства
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Возвращаем топ-K
        top_results = similarities[:top_k]
        
        logger.info(f"Found {len(top_results)} similar conversations (from {len(conversations)} total)")
        for i, (_, sim) in enumerate(top_results, 1):
            logger.debug(f"  #{i}: similarity={sim:.3f}")
        
        return top_results
    
    def _format_conversation_for_embedding(self, conv: Dict) -> str:
        """
        Форматирование диалога в текст для эмбеддинга
        
        Args:
            conv: Словарь с данными диалога
            
        Returns:
            Форматированный текст
        """
        # Если это полный диалог с сообщениями
        if 'messages' in conv:
            messages = conv['messages']
            text_parts = []
            
            for msg in messages[:10]:  # Берём первые 10 сообщений
                role = "Клиент" if msg.get('role') == 'user' else "Бот"
                text_parts.append(f"{role}: {msg.get('message', '')}")
            
            text = "\n".join(text_parts)
        
        # Если это краткие данные лида
        elif 'pain_point' in conv or 'service_category' in conv:
            parts = []
            
            if conv.get('service_category'):
                parts.append(f"Тематика: {conv['service_category']}")
            if conv.get('specific_need'):
                parts.append(f"Потребность: {conv['specific_need']}")
            if conv.get('pain_point'):
                parts.append(f"Боль: {conv['pain_point']}")
            if conv.get('industry'):
                parts.append(f"Отрасль: {conv['industry']}")
            
            text = " | ".join(parts)
        
        # Иначе просто берём все значения
        else:
            text = " ".join(str(v) for v in conv.values() if v)
        
        return text[:1000]  # Ограничиваем длину
    
    def format_similar_examples_for_prompt(
        self, 
        similar_results: List[Tuple[Dict, float]]
    ) -> str:
        """
        Форматирование похожих примеров для добавления в промпт
        
        Args:
            similar_results: Результаты поиска [(диалог, сходство), ...]
            
        Returns:
            Форматированный текст для промпта
        """
        if not similar_results:
            return ""
        
        examples = []
        
        for i, (conv, similarity) in enumerate(similar_results, 1):
            example_parts = [f"📝 ПРИМЕР {i} (релевантность: {similarity:.1%}):"]
            
            # Добавляем данные лида если есть
            if conv.get('service_category'):
                example_parts.append(f"  • Тематика: {conv['service_category']}")
            if conv.get('specific_need'):
                example_parts.append(f"  • Потребность: {conv['specific_need']}")
            if conv.get('pain_point'):
                example_parts.append(f"  • Боль клиента: {conv['pain_point']}")
            if conv.get('temperature'):
                temp_emoji = {'hot': '🔥', 'warm': '♨️', 'cold': '❄️'}.get(conv['temperature'], '')
                example_parts.append(f"  • Результат: {temp_emoji} {conv['temperature'].upper()} лид")
            
            # Добавляем фрагмент диалога если есть
            if conv.get('messages'):
                example_parts.append("  • Фрагмент диалога:")
                for msg in conv['messages'][:4]:  # Первые 4 сообщения
                    role = "Клиент" if msg.get('role') == 'user' else "Бот"
                    message = msg.get('message', '')[:150]  # Обрезаем длинные сообщения
                    example_parts.append(f"    {role}: {message}")
            
            examples.append("\n".join(example_parts))
        
        header = """
═══════════════════════════════════════════════════════════════
УСПЕШНЫЕ ПРИМЕРЫ ИЗ БАЗЫ ЗНАНИЙ (похожие запросы):
═══════════════════════════════════════════════════════════════
"""
        
        footer = """
═══════════════════════════════════════════════════════════════
ИНСТРУКЦИЯ: Используй эти примеры как reference паттернов успешной
квалификации. НЕ копируй дословно - адаптируй под текущего клиента,
но следуй проверенному подходу к выявлению потребностей.
═══════════════════════════════════════════════════════════════
"""
        
        return header + "\n\n".join(examples) + "\n" + footer


# Глобальный экземпляр
knowledge_engine = KnowledgeEngine()


if __name__ == '__main__':
    # Тестирование
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Testing KnowledgeEngine...")
    
    # Тест эмбеддинга
    test_text = "Интересует автоматизация договоров"
    embedding = knowledge_engine.get_embedding(test_text)
    print(f"Embedding length: {len(embedding)}")
    
    # Тест сходства
    test_convos = [
        {
            'service_category': 'Договорная работа',
            'pain_point': 'Не успеваем проверять договоры',
            'temperature': 'warm'
        },
        {
            'service_category': 'Судебная работа',
            'pain_point': 'Проигрываем дела',
            'temperature': 'hot'
        }
    ]
    
    similar = knowledge_engine.find_similar_conversations(
        query="Нужна помощь с анализом контрактов",
        conversations=test_convos,
        top_k=2
    )
    
    print(f"\nFound {len(similar)} similar conversations")
    formatted = knowledge_engine.format_similar_examples_for_prompt(similar)
    print("\nFormatted output:")
    print(formatted)
