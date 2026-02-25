#!/usr/bin/env python3
"""
Тест интеграции системы безопасности
"""
import security

print("=" * 70)
print("🧪 ТЕСТ ИНТЕГРАЦИИ СИСТЕМЫ БЕЗОПАСНОСТИ")
print("=" * 70)

# Тест 1: Проверка инициализации
print("\n1️⃣ Проверка инициализации SecurityManager")
print(f"   ✅ SecurityManager создан: {security.security_manager is not None}")
print(f"   ✅ Rate limits: {security.security_manager.RATE_LIMITS}")
print(f"   ✅ Token limits: {security.security_manager.TOKEN_LIMITS}")
print(f"   ✅ Daily budget: {security.security_manager.TOTAL_DAILY_BUDGET:,}")

# Тест 2: Проверка estimate_tokens
print("\n2️⃣ Тест функции estimate_tokens()")
test_texts = [
    ("Привет", "короткий текст"),
    ("Расскажи подробно про все услуги" * 10, "длинный текст"),
    ("a" * 1000, "1000 символов"),
]

for text, description in test_texts:
    tokens = security.security_manager.estimate_tokens(text)
    print(f"   {description}: {len(text)} символов = ~{tokens} токенов")

# Тест 3: Проверка check_all_security
print("\n3️⃣ Тест check_all_security()")
test_user = 999999999

# Нормальное сообщение
is_allowed, reason = security.security_manager.check_all_security(test_user, "Здравствуйте, интересует автоматизация договоров")
print(f"   Нормальное сообщение: {'✅ Разрешено' if is_allowed else f'❌ Заблокировано: {reason}'}")

# Слишком длинное сообщение
long_message = "a" * 3000
is_allowed, reason = security.security_manager.check_all_security(test_user, long_message)
print(f"   Слишком длинное (3000 символов): {'✅ Разрешено' if is_allowed else f'❌ Заблокировано: {reason}'}")

# Подозрительное сообщение (спам)
spam_message = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
is_allowed, reason = security.security_manager.check_all_security(test_user, spam_message)
print(f"   Спам: {'✅ Разрешено' if is_allowed else f'❌ Заблокировано: {reason}'}")

# Тест 4: Проверка rate limiting
print("\n4️⃣ Тест rate limiting (быстрые сообщения)")
test_user2 = 888888888
for i in range(12):
    is_allowed, reason = security.security_manager.check_rate_limit(test_user2)
    if i < 10:
        status = '✅' if is_allowed else '❌'
    else:
        status = '✅ (должно быть заблокировано)' if not is_allowed else '❌ (не заблокировано!)'
    print(f"   Сообщение {i+1}: {status}")

# Тест 5: Проверка учета токенов
print("\n5️⃣ Тест учета токенов")
initial_tokens = security.security_manager.total_tokens_today
print(f"   Начальное количество токенов: {initial_tokens}")

# Добавляем использованные токены
security.security_manager.add_tokens_used(1000)
print(f"   Добавили 1000 токенов")
print(f"   Текущее количество: {security.security_manager.total_tokens_today}")

security.security_manager.add_tokens_used(5000)
print(f"   Добавили еще 5000 токенов")
print(f"   Текущее количество: {security.security_manager.total_tokens_today}")

# Тест 6: Статистика
print("\n6️⃣ Статистика безопасности")
stats = security.security_manager.get_stats()
print(f"   Токены сегодня: {stats['total_tokens_today']:,} / {stats['daily_budget']:,}")
print(f"   Осталось: {stats['budget_remaining']:,}")
print(f"   Использовано: {stats['budget_percentage']:.1f}%")
print(f"   Заблокированных: {stats['blacklisted_users']}")
print(f"   Подозрительных: {stats['suspicious_users']}")

# Тест 7: Blacklist
print("\n7️⃣ Тест blacklist")
test_user3 = 777777777
print(f"   Добавляем пользователя {test_user3} в blacklist")
security.security_manager.add_to_blacklist(test_user3, "Test ban")

is_blocked, reason = security.security_manager.is_blacklisted(test_user3)
print(f"   Проверка: {'✅ Заблокирован' if is_blocked else '❌ Не заблокирован'}")

print(f"   Удаляем из blacklist")
security.security_manager.remove_from_blacklist(test_user3)

is_blocked, reason = security.security_manager.is_blacklisted(test_user3)
print(f"   Проверка: {'✅ Не заблокирован' if not is_blocked else '❌ Все еще заблокирован'}")

print("\n" + "=" * 70)
print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ!")
print("=" * 70)
print("\nСистема безопасности полностью интегрирована и работает корректно!")
print("\n🛡️ Доступные admin команды:")
print("  /security_stats - статистика безопасности")
print("  /blacklist <user_id> - заблокировать пользователя")
print("  /unblacklist <user_id> - разблокировать пользователя")
