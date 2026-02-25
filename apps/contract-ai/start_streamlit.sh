#!/bin/bash
# Скрипт для запуска Streamlit

cd /Users/andrew/Contract-AI-System-

# Проверить, не запущен ли уже
if pgrep -f "streamlit run app.py" > /dev/null; then
    echo "Streamlit уже работает"
    echo "URL: http://localhost:8501"
    exit 0
fi

# Запустить Streamlit
/Users/andrew/Library/Python/3.13/bin/streamlit run app.py --server.headless=true > streamlit.log 2>&1 &

sleep 3

# Проверить статус
if pgrep -f "streamlit run app.py" > /dev/null; then
    echo "✅ Streamlit успешно запущен!"
    echo "🌐 URL: http://localhost:8501"
    echo "📊 PID: $(pgrep -f 'streamlit run app.py')"
else
    echo "❌ Ошибка запуска Streamlit"
    echo "Смотрите логи: streamlit.log"
    exit 1
fi
