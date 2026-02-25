#!/bin/bash
# Скрипт создания ярлыков на рабочем столе для macOS

echo "🔧 Создание ярлыков на рабочем столе..."
echo "================================================"

# Определяем путь к рабочему столу
DESKTOP="$HOME/Desktop"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Проверяем существование рабочего стола
if [ ! -d "$DESKTOP" ]; then
    echo "❌ ОШИБКА: Рабочий стол не найден по пути $DESKTOP"
    exit 1
fi

echo "📂 Проект: $PROJECT_DIR"
echo "🖥️ Рабочий стол: $DESKTOP"
echo ""

# Создаем AppleScript для запуска
cat > "$DESKTOP/Запустить Contract AI.command" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="PROJECT_PATH_PLACEHOLDER"

cd "$PROJECT_DIR"
./start_admin_panel.command
EOF

# Заменяем плейсхолдер на реальный путь
sed -i '' "s|PROJECT_PATH_PLACEHOLDER|$PROJECT_DIR|g" "$DESKTOP/Запустить Contract AI.command"

# Делаем исполняемым
chmod +x "$DESKTOP/Запустить Contract AI.command"

echo "✅ Создан: Запустить Contract AI.command"

# Создаем AppleScript для остановки
cat > "$DESKTOP/Остановить Contract AI.command" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="PROJECT_PATH_PLACEHOLDER"

cd "$PROJECT_DIR"
./stop_admin_panel.command
EOF

# Заменяем плейсхолдер на реальный путь
sed -i '' "s|PROJECT_PATH_PLACEHOLDER|$PROJECT_DIR|g" "$DESKTOP/Остановить Contract AI.command"

# Делаем исполняемым
chmod +x "$DESKTOP/Остановить Contract AI.command"

echo "✅ Создан: Остановить Contract AI.command"
echo ""
echo "================================================"
echo "✅ ГОТОВО! На рабочем столе созданы 2 кнопки:"
echo "   🚀 Запустить Contract AI.command"
echo "   ⏹️ Остановить Contract AI.command"
echo ""
echo "💡 ВАЖНО:"
echo "   При первом запуске macOS попросит разрешение"
echo "   на выполнение скрипта. Нажмите 'Открыть'."
echo ""
echo "   Если кнопки не работают:"
echo "   1. Откройте Системные настройки → Конфиденциальность"
echo "   2. Разрешите запуск для файлов .command"
echo "================================================"
