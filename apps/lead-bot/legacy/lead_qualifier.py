"""
Lead Qualifier - логика квалификации лидов
"""
import logging
from typing import Dict, Optional
import utils
import database

logger = logging.getLogger(__name__)


class LeadQualifier:
    """Класс для квалификации лидов"""

    def __init__(self, db: database.Database):
        self.db = db

    def process_lead_data(self, user_id: int, extracted_data: Dict) -> Optional[int]:
        """
        Обработка и сохранение данных лида

        Args:
            user_id: ID пользователя в БД
            extracted_data: Извлеченные данные из диалога

        Returns:
            ID лида или None
        """
        try:
            # Подготовка данных для сохранения
            lead_data = {}

            # Контактные данные
            if extracted_data.get('name'):
                lead_data['name'] = extracted_data['name']

            if extracted_data.get('email'):
                if utils.validate_email(extracted_data['email']):
                    lead_data['email'] = extracted_data['email']
                else:
                    logger.warning(f"Invalid email: {extracted_data['email']}")

            if extracted_data.get('phone'):
                if utils.validate_phone(extracted_data['phone']):
                    lead_data['phone'] = utils.format_phone(extracted_data['phone'])
                else:
                    logger.warning(f"Invalid phone: {extracted_data['phone']}")

            if extracted_data.get('company'):
                lead_data['company'] = extracted_data['company']

            # Квалификационные данные
            if extracted_data.get('team_size'):
                lead_data['team_size'] = extracted_data['team_size']

            if extracted_data.get('contracts_per_month'):
                lead_data['contracts_per_month'] = extracted_data['contracts_per_month']

            if extracted_data.get('pain_point'):
                lead_data['pain_point'] = extracted_data['pain_point']

            if extracted_data.get('budget'):
                lead_data['budget'] = extracted_data['budget']

            if extracted_data.get('urgency'):
                lead_data['urgency'] = extracted_data['urgency']

            if extracted_data.get('industry'):
                lead_data['industry'] = extracted_data['industry']

            # Температура лида
            if extracted_data.get('lead_temperature'):
                lead_data['temperature'] = extracted_data['lead_temperature']

            # Интересующая услуга
            if extracted_data.get('interested_service'):
                lead_data['notes'] = f"Интересует: {extracted_data['interested_service']}"

            # Сохраняем или обновляем лид
            lead_id = self.db.create_or_update_lead(user_id, lead_data)

            logger.info(f"Lead data processed for user {user_id}, lead_id={lead_id}")
            return lead_id

        except Exception as e:
            logger.error(f"Error processing lead data: {e}")
            return None

    def update_lead_magnet(self, lead_id: int, magnet_type: str):
        """
        Обновление информации о lead magnet

        Args:
            lead_id: ID лида
            magnet_type: Тип lead magnet (consultation, checklist, demo_analysis)
        """
        try:
            lead = self.db.get_lead_by_id(lead_id)
            if lead:
                self.db.create_or_update_lead(lead['user_id'], {
                    'lead_magnet_type': magnet_type,
                    'lead_magnet_delivered': False
                })
                logger.info(f"Lead magnet updated for lead {lead_id}: {magnet_type}")

        except Exception as e:
            logger.error(f"Error updating lead magnet: {e}")

    def mark_lead_magnet_delivered(self, lead_id: int):
        """
        Отметка о доставке lead magnet

        Args:
            lead_id: ID лида
        """
        try:
            lead = self.db.get_lead_by_id(lead_id)
            if lead:
                self.db.create_or_update_lead(lead['user_id'], {
                    'lead_magnet_delivered': True
                })
                logger.info(f"Lead magnet marked as delivered for lead {lead_id}")

        except Exception as e:
            logger.error(f"Error marking lead magnet as delivered: {e}")

    def is_hot_lead(self, lead_id: int) -> bool:
        """
        Проверка является ли лид горячим

        Args:
            lead_id: ID лида

        Returns:
            True если лид горячий
        """
        try:
            lead = self.db.get_lead_by_user_id(lead_id)
            if not lead:
                return False

            return utils.is_hot_lead(lead)

        except Exception as e:
            logger.error(f"Error checking if lead is hot: {e}")
            return False

    def should_notify_admin(self, lead_id: int, notification_type: str = 'hot_lead') -> bool:
        """
        Определение нужно ли уведомлять админа

        Args:
            lead_id: ID лида
            notification_type: Тип уведомления

        Returns:
            True если нужно уведомить
        """
        try:
            lead = self.db.get_lead_by_user_id(lead_id)
            if not lead:
                return False

            if notification_type == 'hot_lead':
                return utils.is_hot_lead(lead)

            elif notification_type == 'qualified':
                # Лид квалифицирован если есть контакты и боль
                has_contact = bool(lead.get('email') or lead.get('phone'))
                has_pain = bool(lead.get('pain_point'))
                return has_contact and has_pain

            elif notification_type == 'handoff_request':
                # Всегда уведомляем при явном запросе
                return True

            elif notification_type == 'lead_magnet_requested':
                # Уведомляем когда запрошен lead magnet
                return bool(lead.get('lead_magnet_type'))

            return False

        except Exception as e:
            logger.error(f"Error checking if should notify admin: {e}")
            return False

    def get_lead_summary(self, lead_id: int) -> Optional[str]:
        """
        Получение краткой информации о лиде

        Args:
            lead_id: ID лида

        Returns:
            Текстовое описание лида
        """
        try:
            lead = self.db.get_lead_by_user_id(lead_id)
            if not lead:
                return None

            # Используем функцию форматирования из utils
            # Но сначала нужно получить данные пользователя
            user = self.db.get_user_by_telegram_id(lead['telegram_id'])
            if not user:
                return None

            summary = utils.format_lead_notification(lead, user)
            return summary

        except Exception as e:
            logger.error(f"Error getting lead summary: {e}")
            return None

    def get_qualification_status(self, lead_id: int) -> Dict:
        """
        Получение статуса квалификации лида

        Args:
            lead_id: ID лида

        Returns:
            Словарь со статусом квалификации
        """
        try:
            lead = self.db.get_lead_by_user_id(lead_id)
            if not lead:
                return {
                    'qualified': False,
                    'completeness': 0,
                    'missing_fields': []
                }

            # Проверяем обязательные поля
            required_fields = ['name', 'email', 'phone', 'pain_point', 'budget']
            optional_fields = ['company', 'team_size', 'contracts_per_month', 'urgency', 'industry']

            filled_required = 0
            missing_fields = []

            for field in required_fields:
                if lead.get(field):
                    filled_required += 1
                else:
                    missing_fields.append(field)

            # Считаем процент заполнения (обязательные поля важнее)
            total_fields = len(required_fields) + len(optional_fields)
            filled_optional = sum(1 for f in optional_fields if lead.get(f))
            filled_total = filled_required + filled_optional

            completeness = int((filled_total / total_fields) * 100)

            # Квалифицирован если есть хотя бы имя, контакт и боль
            has_name = bool(lead.get('name'))
            has_contact = bool(lead.get('email') or lead.get('phone'))
            has_pain = bool(lead.get('pain_point'))

            qualified = has_name and has_contact and has_pain

            return {
                'qualified': qualified,
                'completeness': completeness,
                'missing_fields': missing_fields,
                'has_name': has_name,
                'has_contact': has_contact,
                'has_pain': has_pain
            }

        except Exception as e:
            logger.error(f"Error getting qualification status: {e}")
            return {
                'qualified': False,
                'completeness': 0,
                'missing_fields': []
            }


# Создание глобального экземпляра
lead_qualifier = LeadQualifier(database.db)


if __name__ == '__main__':
    # Тестирование
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Testing LeadQualifier...")

    # Тест обработки данных лида
    test_data = {
        'name': 'Иван Иванов',
        'email': 'ivan@company.ru',
        'phone': '+79991234567',
        'company': 'ООО Компания',
        'team_size': '4-10',
        'contracts_per_month': '30-50',
        'pain_point': 'Не успеваем проверять все договоры',
        'budget': '300-500K',
        'urgency': 'high',
        'industry': 'IT',
        'lead_temperature': 'hot',
        'interested_service': 'Автоматизация договоров'
    }

    print(f"Test data: {test_data}")
    print("Test completed!")
