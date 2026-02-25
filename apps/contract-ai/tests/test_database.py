"""
Тестирование Database моделей и репозиториев
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from src.models import init_db, SessionLocal, User, Template, Contract
from src.models.repositories import UserRepository, TemplateRepository, ContractRepository

def test_database():
    """Тестирует работу с базой данных"""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ DATABASE")
    print("=" * 60)

    # Тест 1: Инициализация БД
    print("\n1. Инициализация базы данных...")
    try:
        init_db()
        print("   ✓ База данных инициализирована")
        print("   ✓ Таблицы созданы")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        return False

    # Тест 2: Создание сессии
    print("\n2. Создание сессии...")
    try:
        db = SessionLocal()
        print("   ✓ Сессия создана")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        return False

    # Тест 3: Проверка репозиториев
    print("\n3. Проверка репозиториев...")
    try:
        user_repo = UserRepository(db)
        template_repo = TemplateRepository(db)
        contract_repo = ContractRepository(db)
        print("   ✓ UserRepository")
        print("   ✓ TemplateRepository")
        print("   ✓ ContractRepository")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        db.close()
        return False

    # Тест 4: Создание тестового пользователя
    print("\n4. Создание тестового пользователя...")
    try:
        # Проверяем, нет ли уже пользователя
        existing = user_repo.get_by_email("test@example.com")
        if existing:
            print("   ℹ Пользователь уже существует")
            user = existing
        else:
            user = user_repo.create(
                email="test@example.com",
                name="Test User",
                role="admin"
            )
            print(f"   ✓ Пользователь создан: {user.email}")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        db.close()
        return False

    # Тест 5: Получение пользователя
    print("\n5. Получение пользователя по email...")
    try:
        found_user = user_repo.get_by_email("test@example.com")
        if found_user:
            print(f"   ✓ Найден: {found_user.name} ({found_user.role})")
        else:
            print("   ✗ Пользователь не найден")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        db.close()
        return False

    # Тест 6: Создание тестового шаблона
    print("\n6. Создание тестового шаблона...")
    try:
        existing_template = template_repo.get_latest_version("supply")
        if existing_template:
            print("   ℹ Шаблон уже существует")
        else:
            template = template_repo.create(
                name="Договор поставки (тест)",
                contract_type="supply",
                xml_content="<contract></contract>",
                version="1.0",
                created_by=user.id
            )
            print(f"   ✓ Шаблон создан: {template.name} v{template.version}")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        db.close()
        return False

    # Тест 7: Получение шаблонов
    print("\n7. Получение активных шаблонов...")
    try:
        templates = template_repo.get_active_templates()
        print(f"   ✓ Найдено шаблонов: {len(templates)}")
        for t in templates:
            print(f"     - {t.name} ({t.contract_type}, v{t.version})")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        db.close()
        return False

    # Тест 8: Статистика
    print("\n8. Статистика базы данных...")
    try:
        user_count = db.query(User).count()
        template_count = db.query(Template).count()
        contract_count = db.query(Contract).count()
        print(f"   - Пользователей: {user_count}")
        print(f"   - Шаблонов: {template_count}")
        print(f"   - Договоров: {contract_count}")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        db.close()
        return False

    # Закрываем сессию
    db.close()

    print("\n" + "=" * 60)
    print("✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    print("=" * 60)
    print("\nБаза данных: contract_ai.db")
    print("Модели: User, Template, Contract, AnalysisResult,")
    print("        ReviewTask, LegalDocument, ExportLog")

    return True


if __name__ == "__main__":
    success = test_database()
    sys.exit(0 if success else 1)
