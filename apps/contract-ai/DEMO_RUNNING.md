# Contract AI demo server: legacy note

Этот файл сохранен только как историческая пометка. Он больше не описывает поддерживаемый режим запуска.

## Текущее правило

- `start_demo.py` не должен использоваться по умолчанию.
- Скрипт запускается только при явном `CONTRACT_AI_ALLOW_INSECURE_DEMO=1`.
- Режим предназначен только для изолированной локальной демонстрации, когда допустим урезанный insecure-контур.

## Что использовать вместо него

- `README.md` — обзор подсистемы
- `QUICKSTART_LOCAL.md` — безопасный локальный запуск
- `DOCKER_SETUP.md` — контейнерный запуск
- `TESTING_GUIDE.md` — ручные проверки

## Почему файл оставлен

Чтобы не терять исторический контекст появления demo-сервера и явно показать, что старые инструкции с “demo server running”, ослабленной auth-моделью и публичными URL больше не являются актуальными.
  ]
}
```

### Interactive API Docs
Open in browser: **http://localhost:8000/docs**

- Try endpoints directly from UI
- See request/response schemas
- Download OpenAPI spec

---

## 📞 Support

For issues or questions:
- Check logs: `tail -f logs/demo_server.log`
- Review .env configuration
- Ensure port 8000 is not in use
- Check Python version: `python3 --version` (requires 3.11+)

---

**Demo Server Started:** $(date)
**Process ID:** 17418
**Status:** ✅ RUNNING
