"""
Тестирование Template Manager
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from src.services.template_manager import TemplateManager
from src.models import init_db, SessionLocal


def create_test_template():
    """Создаёт тестовый XML шаблон"""
    print("Создание тестового XML шаблона...")

    template_xml = """<?xml version="1.0" encoding="UTF-8"?>
<contract>
  <metadata>
    <contract_id>{{ contract_id }}</contract_id>
    <title>{{ contract_title }}</title>
    <contract_number>{{ contract_number }}</contract_number>
    <date>{{ contract_date }}</date>
    <version>1.0</version>
    <format>template</format>
  </metadata>
  <parties>
    <party role="supplier">
      <name>{{ supplier_name }}</name>
      <inn>{{ supplier_inn }}</inn>
      <director>{{ supplier_director }}</director>
    </party>
    <party role="buyer">
      <name>{{ buyer_name }}</name>
      <inn>{{ buyer_inn }}</inn>
      <director>{{ buyer_director }}</director>
    </party>
  </parties>
  <terms>
    <financial>
      <total_amount>{{ total_amount }}</total_amount>
      <currency>{{ currency }}</currency>
      <payment_terms>{{ payment_terms }}</payment_terms>
    </financial>
    <dates>
      <delivery_date>{{ delivery_date }}</delivery_date>
      <signature_date>{{ signature_date }}</signature_date>
    </dates>
  </terms>
  <clauses>
    <clause id="1" type="preamble">
      <title>Преамбула</title>
      <content>
        <paragraph>{{ contract_title }}</paragraph>
        <paragraph>{{ supplier_name }}, ИНН {{ supplier_inn }}, именуемое в дальнейшем "Поставщик", в лице {{ supplier_director }}, действующего на основании Устава, с одной стороны, и {{ buyer_name }}, ИНН {{ buyer_inn }}, именуемое в дальнейшем "Покупатель", в лице {{ buyer_director }}, действующего на основании Устава, с другой стороны, заключили настоящий договор о нижеследующем:</paragraph>
      </content>
    </clause>
    <clause id="2" type="subject">
      <title>1. Предмет договора</title>
      <content>
        <paragraph>1.1. Поставщик обязуется поставить, а Покупатель принять и оплатить товар в количестве и ассортименте согласно Спецификации (Приложение №1).</paragraph>
        <paragraph>1.2. Наименование товара: {{ product_name }}.</paragraph>
      </content>
    </clause>
    <clause id="3" type="financial">
      <title>2. Цена и порядок расчётов</title>
      <content>
        <paragraph>2.1. Общая стоимость товара составляет {{ total_amount }} {{ currency }}.</paragraph>
        <paragraph>2.2. Оплата производится в следующем порядке: {{ payment_terms }}.</paragraph>
      </content>
    </clause>
    <clause id="4" type="terms">
      <title>3. Сроки поставки</title>
      <content>
        <paragraph>3.1. Поставка товара осуществляется до {{ delivery_date }}.</paragraph>
      </content>
    </clause>
    <clause id="5" type="liability">
      <title>4. Ответственность сторон</title>
      <content>
        <paragraph>4.1. За нарушение сроков поставки Поставщик уплачивает пени в размере {{ penalty_rate }}% от стоимости товара за каждый день просрочки.</paragraph>
      </content>
    </clause>
  </clauses>
  <tables>
    <table id="1">
      <row>
        <cell>№</cell>
        <cell>Наименование</cell>
        <cell>Количество</cell>
        <cell>Цена</cell>
      </row>
    </table>
  </tables>
</contract>
"""

    # Сохраняем шаблон
    template_file = 'data/templates/supply_template_v1.xml'
    os.makedirs('data/templates', exist_ok=True)

    with open(template_file, 'w', encoding='utf-8') as f:
        f.write(template_xml)

    print(f"   ✓ Тестовый шаблон создан: {template_file}")
    return template_file


def test_template_manager():
    """Тестирует Template Manager"""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ TEMPLATE MANAGER")
    print("=" * 60)

    # Инициализация БД
    print("\n1. Инициализация базы данных...")
    try:
        init_db()
        db = SessionLocal()
        print("   ✓ БД инициализирована")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        return False

    # Тест 1: Создание Template Manager
    print("\n2. Инициализация Template Manager...")
    try:
        manager = TemplateManager(db_session=db)
        print("   ✓ Template Manager создан")
        print(f"   - Директория шаблонов: {manager.templates_dir}")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        db.close()
        return False

    # Тест 2: Создание тестового шаблона
    print("\n3. Создание тестового XML шаблона...")
    try:
        template_file = create_test_template()
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        db.close()
        return False

    # Тест 3: Загрузка шаблона в БД
    print("\n4. Загрузка шаблона в базу данных...")
    try:
        template = manager.load_template_from_file(
            file_path=template_file,
            contract_type="supply",
            name="Договор поставки (шаблон v1)",
            version="1.0"
        )
        print(f"   ✓ Шаблон загружен")
        print(f"   - ID: {template.id}")
        print(f"   - Название: {template.name}")
        print(f"   - Тип: {template.contract_type}")
        print(f"   - Версия: {template.version}")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return False

    # Тест 4: Получение шаблона
    print("\n5. Получение шаблона из БД...")
    try:
        retrieved_template = manager.get_template("supply")
        if retrieved_template:
            print(f"   ✓ Шаблон получен: {retrieved_template.name}")
        else:
            print("   ✗ Шаблон не найден")
            db.close()
            return False
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        db.close()
        return False

    # Тест 5: Извлечение переменных
    print("\n6. Извлечение переменных из шаблона...")
    try:
        variables = manager.get_template_variables(template.id)
        print(f"   ✓ Найдено переменных: {len(variables)}")
        print(f"   - Переменные: {', '.join(variables[:10])}")
        if len(variables) > 10:
            print(f"     ... и ещё {len(variables) - 10}")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        db.close()
        return False

    # Тест 6: Заполнение шаблона данными
    print("\n7. Заполнение шаблона данными...")
    try:
        test_data = {
            'contract_id': 'CONTRACT-2025-001',
            'contract_title': 'ДОГОВОР ПОСТАВКИ №001-2025',
            'contract_number': '001-2025',
            'contract_date': '15.01.2025',
            'supplier_name': 'ООО "АгроПоставка"',
            'supplier_inn': '7701234567',
            'supplier_director': 'Генерального директора Иванова И.И.',
            'buyer_name': 'ООО "ХлебКомбинат"',
            'buyer_inn': '7707654321',
            'buyer_director': 'директора Петрова П.П.',
            'total_amount': '2 500 000 рублей',
            'currency': 'RUB',
            'payment_terms': '50% предоплата, остальное в течение 10 дней после поставки',
            'delivery_date': '31.03.2025',
            'signature_date': '15.01.2025',
            'product_name': 'Пшеница продовольственная 3 класс',
            'penalty_rate': '0.1'
        }

        filled_xml = manager.fill_template(template.id, test_data)
        print("   ✓ Шаблон заполнен")
        print(f"   - Размер XML: {len(filled_xml)} символов")

        # Проверяем, что переменные заменились
        if '{{' not in filled_xml:
            print("   ✓ Все переменные заменены")
        else:
            print("   ⚠ Остались незаполненные переменные")

    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return False

    # Тест 7: Валидация заполненного XML
    print("\n8. Валидация заполненного XML...")
    try:
        is_valid = manager.validate_xml(filled_xml)
        if is_valid:
            print("   ✓ Заполненный XML валиден")
        else:
            print("   ✗ Заполненный XML не валиден")
            db.close()
            return False
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        db.close()
        return False

    # Тест 8: Экспорт в DOCX
    print("\n9. Экспорт в DOCX...")
    try:
        output_file = 'tests/fixtures/filled_contract.docx'
        os.makedirs('tests/fixtures', exist_ok=True)

        manager.export_to_docx(filled_xml, output_file)
        print(f"   ✓ DOCX создан: {output_file}")

        # Проверяем что файл создан
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"   - Размер файла: {file_size} байт")
        else:
            print("   ✗ Файл не создан")
            db.close()
            return False

    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return False

    # Тест 9: Создание новой версии
    print("\n10. Создание новой версии шаблона...")
    try:
        new_template = manager.create_version(
            base_template_id=template.id,
            new_version="1.1"
        )
        print(f"   ✓ Версия 1.1 создана")
        print(f"   - ID: {new_template.id}")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        db.close()
        return False

    # Тест 10: Список шаблонов
    print("\n11. Получение списка шаблонов...")
    try:
        templates = manager.list_templates(contract_type="supply")
        print(f"   ✓ Найдено шаблонов типа 'supply': {len(templates)}")
        for t in templates:
            print(f"     - {t.name} (v{t.version})")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        db.close()
        return False

    # Тест 11: Превью заполненного XML
    print("\n12. Превью заполненного XML (первые 800 символов):")
    print("-" * 60)
    print(filled_xml[:800])
    print("-" * 60)

    db.close()

    print("\n" + "=" * 60)
    print("✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    print("=" * 60)
    print("\nФайлы созданы:")
    print(f"  - Шаблон XML: {template_file}")
    print(f"  - Заполненный DOCX: tests/fixtures/filled_contract.docx")
    print(f"\nВ БД создано: {len(templates)} шаблонов")

    return True


if __name__ == "__main__":
    success = test_template_manager()
    sys.exit(0 if success else 1)
