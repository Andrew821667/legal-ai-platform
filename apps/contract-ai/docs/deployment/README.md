# Deployment Guide

Complete guide for deploying Contract-AI-System in various environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Development Deployment](#development-deployment)
- [Production Deployment](#production-deployment)
  - [Docker Deployment](#docker-deployment)
  - [Kubernetes Deployment](#kubernetes-deployment)
  - [Traditional Server Deployment](#traditional-server-deployment)
- [Configuration](#configuration)
- [Database Setup](#database-setup)
- [External Services](#external-services)
- [Performance Optimization](#performance-optimization)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Minimum:**
- CPU: 2 cores
- RAM: 4 GB
- Disk: 20 GB
- OS: Linux (Ubuntu 20.04+), macOS, Windows 10+

**Recommended (Production):**
- CPU: 4+ cores
- RAM: 8+ GB
- Disk: 50+ GB SSD
- OS: Linux (Ubuntu 22.04 LTS)

### Software Dependencies

- **Python:** 3.9+
- **PostgreSQL:** 13+ (or SQLite for development)
- **Redis:** 6.0+ (optional, for caching)
- **Tesseract OCR:** 4.0+ (optional, for OCR)
- **Docker:** 20.10+ (optional, for containerized deployment)
- **Kubernetes:** 1.20+ (optional, for orchestrated deployment)

---

## Development Deployment

### Quick Start

1. **Clone Repository:**

```bash
git clone https://github.com/Andrew821667/Contract-AI-System-.git
cd Contract-AI-System-
```

2. **Create Virtual Environment:**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install Dependencies:**

```bash
pip install -r requirements.txt

# Optional: OCR support
sudo apt-get install tesseract-ocr tesseract-ocr-rus
pip install pytesseract pdf2image
```

4. **Configure Environment:**

```bash
cp .env.example .env
nano .env  # Edit configuration
```

Required `.env` settings:

```bash
# Database
DATABASE_URL=sqlite:///./contracts.db

# LLM APIs
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional: Redis
REDIS_URL=redis://localhost:6379/0

# Optional: FNS API
FNS_API_KEY=your_fns_api_key
USE_DADATA=true
DADATA_API_KEY=your_dadata_api_key
```

5. **Initialize Database:**

```bash
# Run migrations
alembic upgrade head

# Or create tables directly
python -c "from src.models.database import init_db; init_db()"

# Apply performance indexes
psql -U postgres -d contracts -f database/performance_indexes.sql
```

6. **Run Development Server:**

```bash
# FastAPI server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Or use the development script
python run_dev.py
```

7. **Verify Installation:**

```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy"}

curl http://localhost:8000/docs
# Opens API documentation
```

---

## Production Deployment

### Docker Deployment

#### Single Container

1. **Create Dockerfile:**

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-rus \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

2. **Build and Run:**

```bash
# Build image
docker build -t contract-ai-system:latest .

# Run container
docker run -d \
  --name contract-ai \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@db:5432/contracts \
  -e OPENAI_API_KEY=your_key \
  -e REDIS_URL=redis://redis:6379/0 \
  -v /path/to/uploads:/app/uploads \
  contract-ai-system:latest
```

#### Docker Compose (Recommended)

1. **Create `docker-compose.yml`:**

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/contracts
      - REDIS_URL=redis://redis:6379/0
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    depends_on:
      - db
      - redis
    restart: unless-stopped

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=contracts
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
      - ./database/performance_indexes.sql:/docker-entrypoint-initdb.d/02-indexes.sql
    ports:
      - "5432:5432"
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - app
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

2. **Create `nginx.conf`:**

```nginx
events {
    worker_connections 1024;
}

http {
    upstream app {
        server app:8000;
    }

    server {
        listen 80;
        server_name your-domain.com;

        # Redirect to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        # SSL configuration
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;

        # File upload size
        client_max_body_size 100M;

        # Proxy settings
        location / {
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Timeouts for long-running analysis
            proxy_read_timeout 300s;
            proxy_connect_timeout 75s;
        }

        # WebSocket support
        location /ws {
            proxy_pass http://app;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
```

3. **Deploy:**

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

---

### Kubernetes Deployment

#### Prerequisites

- Kubernetes cluster (GKE, EKS, AKS, or self-hosted)
- kubectl configured
- Helm 3+ (optional)

#### Deployment Manifests

1. **Create Namespace:**

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: contract-ai
```

2. **ConfigMap:**

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: contract-ai-config
  namespace: contract-ai
data:
  DATABASE_URL: "postgresql://postgres:password@postgres:5432/contracts"
  REDIS_URL: "redis://redis:6379/0"
  LOG_LEVEL: "INFO"
```

3. **Secrets:**

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: contract-ai-secrets
  namespace: contract-ai
type: Opaque
stringData:
  OPENAI_API_KEY: "your_openai_api_key"
  ANTHROPIC_API_KEY: "your_anthropic_api_key"
  DADATA_API_KEY: "your_dadata_api_key"
```

4. **PostgreSQL Deployment:**

```yaml
# postgres-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: contract-ai
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: "contracts"
        - name: POSTGRES_USER
          value: "postgres"
        - name: POSTGRES_PASSWORD
          value: "password"
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: contract-ai
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: contract-ai
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
```

5. **Redis Deployment:**

```yaml
# redis-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: contract-ai
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: contract-ai
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

6. **Application Deployment:**

```yaml
# app-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: contract-ai-app
  namespace: contract-ai
spec:
  replicas: 3
  selector:
    matchLabels:
      app: contract-ai-app
  template:
    metadata:
      labels:
        app: contract-ai-app
    spec:
      containers:
      - name: app
        image: contract-ai-system:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: contract-ai-config
        - secretRef:
            name: contract-ai-secrets
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: contract-ai-app
  namespace: contract-ai
spec:
  selector:
    app: contract-ai-app
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

7. **Ingress:**

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: contract-ai-ingress
  namespace: contract-ai
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - contract-ai.your-domain.com
    secretName: contract-ai-tls
  rules:
  - host: contract-ai.your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: contract-ai-app
            port:
              number: 80
```

8. **Deploy to Kubernetes:**

```bash
# Apply all manifests
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secrets.yaml
kubectl apply -f postgres-deployment.yaml
kubectl apply -f redis-deployment.yaml
kubectl apply -f app-deployment.yaml
kubectl apply -f ingress.yaml

# Check status
kubectl get pods -n contract-ai
kubectl get svc -n contract-ai
kubectl logs -f deployment/contract-ai-app -n contract-ai

# Scale application
kubectl scale deployment contract-ai-app --replicas=5 -n contract-ai
```

---

### Traditional Server Deployment

#### Ubuntu 22.04 LTS

1. **Install Dependencies:**

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip

# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Install Redis
sudo apt install -y redis-server

# Install Tesseract OCR
sudo apt install -y tesseract-ocr tesseract-ocr-rus

# Install Nginx
sudo apt install -y nginx
```

2. **Configure PostgreSQL:**

```bash
# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE contracts;
CREATE USER contract_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE contracts TO contract_user;
\q
EOF

# Apply schema
psql -U contract_user -d contracts -f database/schema.sql
psql -U contract_user -d contracts -f database/performance_indexes.sql
```

3. **Setup Application:**

```bash
# Create application directory
sudo mkdir -p /opt/contract-ai
sudo chown $USER:$USER /opt/contract-ai
cd /opt/contract-ai

# Clone repository
git clone https://github.com/Andrew821667/Contract-AI-System-.git .

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install gunicorn
```

4. **Configure Environment:**

```bash
# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql://contract_user:secure_password@localhost:5432/contracts
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
LOG_LEVEL=INFO
EOF
```

5. **Create Systemd Service:**

```bash
# Create service file
sudo cat > /etc/systemd/system/contract-ai.service << EOF
[Unit]
Description=Contract AI System
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=$USER
Group=$USER
WorkingDirectory=/opt/contract-ai
Environment="PATH=/opt/contract-ai/venv/bin"
ExecStart=/opt/contract-ai/venv/bin/gunicorn \\
    --workers 4 \\
    --worker-class uvicorn.workers.UvicornWorker \\
    --bind 127.0.0.1:8000 \\
    --timeout 300 \\
    --access-logfile /var/log/contract-ai/access.log \\
    --error-logfile /var/log/contract-ai/error.log \\
    src.main:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create log directory
sudo mkdir -p /var/log/contract-ai
sudo chown $USER:$USER /var/log/contract-ai

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable contract-ai
sudo systemctl start contract-ai
sudo systemctl status contract-ai
```

6. **Configure Nginx:**

```bash
# Create Nginx configuration
sudo cat > /etc/nginx/sites-available/contract-ai << EOF
upstream contract_ai {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 100M;

    location / {
        proxy_pass http://contract_ai;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/contract-ai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

7. **Setup SSL with Let's Encrypt:**

```bash
# Install certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is set up automatically
sudo certbot renew --dry-run
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `REDIS_URL` | No | None | Redis connection string (caching) |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `ANTHROPIC_API_KEY` | No | - | Anthropic API key |
| `FNS_API_KEY` | No | - | FNS/Dadata API key |
| `USE_DADATA` | No | false | Use Dadata.ru for company info |
| `LOG_LEVEL` | No | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `MAX_UPLOAD_SIZE` | No | 100MB | Maximum file upload size |
| `ENABLE_OCR` | No | true | Enable OCR for scanned documents |
| `TESSERACT_PATH` | No | auto | Path to Tesseract binary |

### Application Configuration

Edit `src/config.py`:

```python
class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # LLM
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    DEFAULT_MODEL: str = "gpt-4"

    # Cache
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 3600  # 1 hour

    # Performance
    BATCH_SIZE: int = 15
    MAX_WORKERS: int = 4

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
```

---

## Database Setup

### PostgreSQL (Production)

```bash
# Initialize database
createdb contracts

# Run migrations
alembic upgrade head

# Apply indexes
psql -d contracts -f database/performance_indexes.sql

# Verify
psql -d contracts -c "\dt"
```

### SQLite (Development)

```bash
# Auto-creates database on first run
python -c "from src.models.database import init_db; init_db()"
```

### Backups

```bash
# PostgreSQL backup
pg_dump -U postgres contracts > backup_$(date +%Y%m%d).sql

# Restore
psql -U postgres contracts < backup_20250115.sql

# Automated daily backups (cron)
0 2 * * * /usr/bin/pg_dump -U postgres contracts | gzip > /backups/contracts_$(date +\%Y\%m\%d).sql.gz
```

---

## External Services

### Redis (Caching)

**Installation:**

```bash
# Ubuntu
sudo apt install redis-server

# macOS
brew install redis

# Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

**Configuration:**

Edit `/etc/redis/redis.conf`:

```conf
# Memory limit
maxmemory 1gb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000
```

### Tesseract OCR

**Installation:**

```bash
# Ubuntu
sudo apt install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng

# macOS
brew install tesseract tesseract-lang

# Verify
tesseract --version
tesseract --list-langs
```

---

## Performance Optimization

### Application Tuning

1. **Worker Processes:**

```bash
# Gunicorn workers = (2 × CPU cores) + 1
gunicorn --workers 9 --worker-class uvicorn.workers.UvicornWorker src.main:app
```

2. **Connection Pooling:**

```python
# src/models/database.py
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True
)
```

3. **Redis Configuration:**

```bash
# Increase Redis connections
redis-cli CONFIG SET maxclients 10000
```

### Database Optimization

```sql
-- Regular maintenance
VACUUM ANALYZE;

-- Reindex
REINDEX DATABASE contracts;

-- Check index usage
SELECT * FROM pg_stat_user_indexes WHERE idx_scan = 0;
```

### Caching Strategy

```python
# Enable multi-layer caching
cache = CacheService(
    redis_url="redis://localhost:6379/0",
    max_size=10000,
    default_ttl=3600
)

# Cache expensive operations
@cache.cached(ttl=600, key_prefix="fns")
def get_company_info(inn: str):
    return fns_client.get_company_info(inn)
```

---

## Monitoring

### Health Checks

```bash
# Application health
curl http://localhost:8000/health

# Database health
psql -U postgres -d contracts -c "SELECT 1;"

# Redis health
redis-cli ping
```

### Logging

```python
# Configure logging
import logging
from loguru import logger

logger.add(
    "/var/log/contract-ai/app.log",
    rotation="500 MB",
    retention="10 days",
    level="INFO"
)
```

### Metrics (Prometheus)

```python
# Add prometheus_client
from prometheus_client import Counter, Histogram

request_count = Counter('http_requests_total', 'Total requests')
request_duration = Histogram('http_request_duration_seconds', 'Request duration')
```

### Application Monitoring

```bash
# System resources
htop
iotop
nethogs

# Application logs
tail -f /var/log/contract-ai/access.log
tail -f /var/log/contract-ai/error.log

# PostgreSQL logs
tail -f /var/log/postgresql/postgresql-15-main.log
```

---

## Troubleshooting

### Common Issues

**Issue: Database connection fails**

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection string
psql "postgresql://user:pass@localhost:5432/contracts"

# Check firewall
sudo ufw allow 5432/tcp
```

**Issue: Redis connection fails**

```bash
# Check Redis is running
sudo systemctl status redis

# Test connection
redis-cli ping

# Check logs
sudo journalctl -u redis -f
```

**Issue: OCR not working**

```bash
# Check Tesseract installation
tesseract --version
tesseract --list-langs

# Install missing languages
sudo apt install tesseract-ocr-rus
```

**Issue: High memory usage**

```bash
# Check worker count (reduce if needed)
ps aux | grep gunicorn | wc -l

# Monitor memory
free -h
vmstat 1

# Adjust worker count
gunicorn --workers 4 ...  # Reduce workers
```

**Issue: Slow performance**

```bash
# Check database query performance
psql -d contracts -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# Check Redis cache hit rate
redis-cli info stats | grep hit_rate

# Check application logs for slow requests
grep -E "duration=[0-9]{4,}" /var/log/contract-ai/access.log
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with debug
uvicorn src.main:app --reload --log-level debug
```

---

## Security Checklist

- [ ] Use strong database passwords
- [ ] Enable SSL/TLS for all connections
- [ ] Keep API keys in secrets (never in code)
- [ ] Enable firewall (ufw/iptables)
- [ ] Regular security updates (`apt update && apt upgrade`)
- [ ] Use non-root user for application
- [ ] Enable HTTPS with valid certificate
- [ ] Set up rate limiting
- [ ] Regular backups
- [ ] Monitor logs for suspicious activity

---

## Maintenance

### Regular Tasks

**Daily:**
- Monitor logs for errors
- Check disk space
- Verify backups

**Weekly:**
- Review performance metrics
- Update dependencies
- Check security alerts

**Monthly:**
- Database VACUUM ANALYZE
- Review and optimize slow queries
- Update documentation

### Updates

```bash
# Update application
cd /opt/contract-ai
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart contract-ai

# Update system packages
sudo apt update && sudo apt upgrade -y
sudo systemctl reboot
```

---

For more information, see:
- [API Documentation](../api/README.md)
- [Architecture Documentation](../architecture/README.md)
- [Performance Optimization Guide](../performance/llm_batching_optimization.md)
