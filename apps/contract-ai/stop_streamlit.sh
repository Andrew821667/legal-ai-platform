#!/bin/bash
# Скрипт для остановки Streamlit

echo "Остановка Streamlit..."

# Найти процесс
PID=$(pgrep -f "streamlit run app.py")

if [ -z "$PID" ]; then
    echo "❌ Streamlit не запущен"
    exit 0
fi

echo "📊 Найден процесс: PID $PID"

# Остановить
pkill -f "streamlit run app.py"

sleep 2

# Проверить
if pgrep -f "streamlit run app.py" > /dev/null; then
    echo "⚠️  Процесс не остановился, принудительная остановка..."
    pkill -9 -f "streamlit run app.py"
    sleep 1
fi

# Финальная проверка
if pgrep -f "streamlit run app.py" > /dev/null; then
    echo "❌ Не удалось остановить Streamlit"
    exit 1
else
    echo "✅ Streamlit успешно остановлен"
    exit 0
fi
