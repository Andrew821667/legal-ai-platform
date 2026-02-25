# Интеграция с системами ЭДО (Электронный Документооборот)

## Обзор

Модуль `disagreement_export_service.py` включает функциональность для экспорта документов в системы электронного документооборота (ЭДО).

Поддерживаемые системы:
- **Диадок** (Diadoc) - https://www.diadoc.ru/
- **СБИС** (SBIS) - https://sbis.ru/
- **Контур.Диадок** (Kontur) - https://www.kontur.ru/

## Текущее состояние

На данный момент функция `export_to_edo()` является **заглушкой (stub)** с симуляцией отправки документов.

Для реальной интеграции требуется:

1. Регистрация в выбранной системе ЭДО
2. Получение API ключей и сертификатов
3. Установка дополнительных библиотек
4. Реализация методов аутентификации и отправки

## Требования для продакшн-интеграции

### 1. Диадок (Diadoc)

**Библиотеки:**
```bash
pip install diadocsdk-python
```

**Необходимые данные:**
- API ключ
- Сертификат электронной подписи (ЭЦП)
- ID организации в Диадок
- Thumbprint сертификата

**Пример реализации:**
```python
from diadocsdk import Diadoc

def send_to_diadoc(self, file_path: str, recipient_inn: str) -> str:
    """Send document to Diadoc"""
    # Initialize Diadoc client
    client = Diadoc(
        api_url='https://diadoc-api.kontur.ru',
        api_key=self.config['diadoc_api_key']
    )

    # Authenticate
    auth_token = client.authenticate(
        thumbprint=self.config['cert_thumbprint'],
        login=self.config['diadoc_login'],
        password=self.config['diadoc_password']
    )

    # Read file
    with open(file_path, 'rb') as f:
        file_content = f.read()

    # Create message
    message = client.create_message(
        from_box_id=self.config['diadoc_box_id'],
        to_inn=recipient_inn,
        documents=[{
            'filename': os.path.basename(file_path),
            'content': file_content,
            'type': 'Nonformalized'
        }]
    )

    # Send
    result = client.send_message(auth_token, message)

    return result.message_id
```

**Документация:**
- API Reference: https://api-docs.diadoc.ru/
- SDK GitHub: https://github.com/diadoc/diadocsdk-python

### 2. СБИС (SBIS)

**Библиотеки:**
```bash
pip install sbis-api-python  # Требует ключ доступа
```

**Необходимые данные:**
- API токен
- ID организации
- Сертификат ЭЦП
- Endpoint URL

**Пример реализации:**
```python
import requests
import base64

def send_to_sbis(self, file_path: str, recipient_id: str) -> str:
    """Send document to SBIS"""
    # API endpoint
    url = 'https://api.sbis.ru/edo/document/send'

    # Headers
    headers = {
        'Authorization': f'Bearer {self.config["sbis_api_token"]}',
        'Content-Type': 'application/json'
    }

    # Read and encode file
    with open(file_path, 'rb') as f:
        file_content = base64.b64encode(f.read()).decode('utf-8')

    # Prepare payload
    payload = {
        'sender_id': self.config['sbis_org_id'],
        'recipient_id': recipient_id,
        'document': {
            'type': 'Unformalized',
            'filename': os.path.basename(file_path),
            'content': file_content,
            'signature': self._sign_document(file_path)  # ЭЦП
        }
    }

    # Send request
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()

    result = response.json()
    return result['document_id']

def _sign_document(self, file_path: str) -> str:
    """Sign document with electronic signature"""
    # Requires cryptopro or similar library
    # This is a placeholder
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    # Load private key
    with open(self.config['cert_path'], 'rb') as f:
        private_key = load_private_key(f.read())

    # Sign file
    with open(file_path, 'rb') as f:
        signature = private_key.sign(
            f.read(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

    return base64.b64encode(signature).decode('utf-8')
```

**Документация:**
- API Reference: https://help.sbis.ru/edo/api
- Техподдержка: edo@tensor.ru

### 3. Контур.Диадок (Kontur)

**Библиотеки:**
```bash
pip install kontur-edo-client
```

**Необходимые данные:**
- API ключ
- Идентификатор ящика (box ID)
- Сертификат ЭЦП
- INN контрагента

**Пример реализации:**
```python
from kontur_edo import KonturClient

def send_to_kontur(self, file_path: str, recipient_inn: str) -> str:
    """Send document to Kontur EDO"""
    # Initialize client
    client = KonturClient(
        api_key=self.config['kontur_api_key'],
        box_id=self.config['kontur_box_id'],
        cert_path=self.config['kontur_cert_path']
    )

    # Upload document
    document_id = client.upload_document(
        file_path=file_path,
        document_type='Nonformalized',
        recipient_inn=recipient_inn
    )

    # Sign document
    client.sign_document(document_id)

    # Send
    result = client.send_document(document_id)

    return result['document_id']
```

**Документация:**
- Контур.Диадок API: https://developer.kontur.ru/
- Техподдержка: support@kontur.ru

## Конфигурация

Добавьте в `.env` файл:

```bash
# Diadoc
DIADOC_API_KEY=your_api_key_here
DIADOC_BOX_ID=your_box_id
DIADOC_LOGIN=your_login
DIADOC_PASSWORD=your_password
DIADOC_CERT_THUMBPRINT=cert_thumbprint

# SBIS
SBIS_API_TOKEN=your_api_token
SBIS_ORG_ID=your_organization_id
SBIS_CERT_PATH=/path/to/certificate.pem

# Kontur
KONTUR_API_KEY=your_api_key
KONTUR_BOX_ID=your_box_id
KONTUR_CERT_PATH=/path/to/certificate.pfx
```

## Безопасность

### Требования к хранению сертификатов:

1. **НЕ** храните сертификаты в git
2. Используйте защищённые хранилища (Azure Key Vault, AWS Secrets Manager)
3. Ограничьте доступ к сертификатам на уровне файловой системы
4. Используйте HSM (Hardware Security Module) для критичных операций

### Проверка подписи:

```python
def verify_signature(file_path: str, signature: bytes, cert_path: str) -> bool:
    """Verify document signature"""
    from cryptography.x509 import load_pem_x509_certificate
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import hashes

    # Load certificate
    with open(cert_path, 'rb') as f:
        cert = load_pem_x509_certificate(f.read(), default_backend())

    public_key = cert.public_key()

    # Verify
    with open(file_path, 'rb') as f:
        try:
            public_key.verify(
                signature,
                f.read(),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            return True
        except:
            return False
```

## Тестирование

### Mock для тестов:

```python
class MockEDOClient:
    """Mock EDO client for testing"""

    def send_document(self, file_path: str, recipient: str) -> str:
        """Simulate document sending"""
        import uuid
        doc_id = f"TEST-{uuid.uuid4()}"
        print(f"[MOCK] Sent {file_path} to {recipient}: {doc_id}")
        return doc_id
```

### Использование в тестах:

```python
def test_edo_export(monkeypatch):
    """Test EDO export with mock"""
    mock_client = MockEDOClient()

    service = DisagreementExportService(db_session, config)
    monkeypatch.setattr(service, '_send_to_edo_stub',
                       lambda *args: mock_client.send_document(*args))

    result = service.export_to_edo(
        disagreement_id=1,
        edo_system='diadoc'
    )

    assert result['success'] == True
    assert 'TEST-' in result['edo_document_id']
```

## Статусы документов в ЭДО

Отслеживайте статусы документов:

```python
class EDODocumentStatus(str, Enum):
    DRAFT = 'draft'              # Черновик
    SENT = 'sent'                # Отправлен
    DELIVERED = 'delivered'      # Доставлен
    READ = 'read'                # Прочитан
    SIGNED = 'signed'            # Подписан
    REJECTED = 'rejected'        # Отклонён
    RECALLED = 'recalled'        # Отозван
    ERROR = 'error'              # Ошибка
```

## Обработка ошибок

```python
class EDOError(Exception):
    """Base EDO error"""
    pass

class EDOAuthenticationError(EDOError):
    """Authentication failed"""
    pass

class EDOUploadError(EDOError):
    """Document upload failed"""
    pass

class EDOSignatureError(EDOError):
    """Signature error"""
    pass
```

## Roadmap для полной реализации

1. **Phase 1**: Выбор системы ЭДО и регистрация
2. **Phase 2**: Получение тестового доступа к API
3. **Phase 3**: Установка SDK и библиотек
4. **Phase 4**: Реализация аутентификации
5. **Phase 5**: Реализация отправки документов
6. **Phase 6**: Реализация подписания (ЭЦП)
7. **Phase 7**: Обработка статусов и уведомлений
8. **Phase 8**: Мониторинг и логирование
9. **Phase 9**: Тестирование на prod окружении
10. **Phase 10**: Развёртывание

## Полезные ссылки

- [Законодательство об ЭДО](https://www.consultant.ru/document/cons_doc_LAW_112699/)
- [ФЗ-63 об электронной подписи](http://www.consultant.ru/document/cons_doc_LAW_112509/)
- [ГОСТ Р 34.10-2012](https://www.cryptopro.ru/products/csp/overview) - стандарт ЭЦП
- [Аккредитованные удостоверяющие центры](https://minsvyaz.gov.ru/ru/activity/govservices/2/)

## Поддержка

Для вопросов по интеграции:
- Создайте issue в GitHub
- Напишите в техподдержку выбранной системы ЭДО
- Проконсультируйтесь с юристом по вопросам юридической силы документов
