# BPS Deployment Guide

## Overview

This guide covers deployment options for the Business Planning System (BPS) from development to production environments.

## Environment Requirements

### System Requirements
- **OS**: Linux (Ubuntu 20.04+ recommended), macOS, Windows
- **Python**: 3.11+
- **PostgreSQL**: 13+
- **Memory**: 4GB+ RAM (8GB+ for production)
- **Storage**: 10GB+ available space

### Dependencies
- Django 5.2.5
- PostgreSQL with JSONB support
- Redis (optional, for caching)
- Nginx (production)
- Gunicorn (production)

## Development Setup

### Local Development
```bash
# Clone repository
git clone <repository-url>
cd bps

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database settings

# Setup database
python manage.py migrate
python manage.py createsuperuser

# Load demo data (optional)
python manage.py bps_demo_0clean
python manage.py bps_demo_1master
python manage.py bps_demo_2env
python manage.py bps_demo_3plan --year 2025

# Run development server
python manage.py runserver
```

### Environment Variables
```bash
# .env file
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=bps
DB_USER=bps_user
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432

# Optional
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
```

## Production Deployment

### Docker Deployment

#### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Run application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "bpsproject.wsgi:application"]
```

#### docker-compose.yml
```yaml
version: '3.8'

services:
  db:
    image: postgres:13
    environment:
      POSTGRES_DB: bps
      POSTGRES_USER: bps_user
      POSTGRES_PASSWORD: your-password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEBUG=False
      - DB_HOST=db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - static_volume:/app/static
      - media_volume:/app/media

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - static_volume:/app/static
      - media_volume:/app/media
    depends_on:
      - web

volumes:
  postgres_data:
  static_volume:
  media_volume:
```

### Traditional Server Deployment

#### System Setup (Ubuntu)
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.11 python3.11-venv python3-pip
sudo apt install -y postgresql postgresql-contrib
sudo apt install -y nginx redis-server
sudo apt install -y git curl

# Create application user
sudo useradd --system --shell /bin/bash --home /opt/bps bps
sudo mkdir -p /opt/bps
sudo chown bps:bps /opt/bps
```

#### Application Setup
```bash
# Switch to application user
sudo -u bps -i

# Clone and setup application
cd /opt/bps
git clone <repository-url> .
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with production settings

# Setup database
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

#### Database Setup
```bash
# Create PostgreSQL user and database
sudo -u postgres psql
CREATE DATABASE bps;
CREATE USER bps_user WITH PASSWORD 'secure-password';
GRANT ALL PRIVILEGES ON DATABASE bps TO bps_user;
ALTER USER bps_user CREATEDB;
\q
```

#### Gunicorn Configuration
```bash
# /opt/bps/gunicorn.conf.py
bind = "127.0.0.1:8000"
workers = 3
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2
user = "bps"
group = "bps"
```

#### Systemd Service
```ini
# /etc/systemd/system/bps.service
[Unit]
Description=BPS Django Application
After=network.target postgresql.service

[Service]
Type=notify
User=bps
Group=bps
WorkingDirectory=/opt/bps
Environment=PATH=/opt/bps/venv/bin
ExecStart=/opt/bps/venv/bin/gunicorn --config /opt/bps/gunicorn.conf.py bpsproject.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Nginx Configuration
```nginx
# /etc/nginx/sites-available/bps
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 100M;

    location /static/ {
        alias /opt/bps/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /opt/bps/media/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

#### SSL Configuration (Let's Encrypt)
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## Database Management

### Backup Strategy
```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR="/opt/backups/bps"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Database backup
pg_dump -h localhost -U bps_user bps > $BACKUP_DIR/bps_$DATE.sql

# Compress and clean old backups
gzip $BACKUP_DIR/bps_$DATE.sql
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

### Migration Management
```bash
# Production migration workflow
python manage.py makemigrations --check
python manage.py migrate --plan
python manage.py migrate
```

## Monitoring & Logging

### Application Logging
```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/bps/django.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'bps': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

### Health Checks
```python
# health_check.py
import requests
import sys

def check_health():
    try:
        response = requests.get('http://localhost:8000/admin/', timeout=10)
        if response.status_code == 200:
            print("OK: Application is healthy")
            sys.exit(0)
        else:
            print(f"ERROR: HTTP {response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_health()
```

## Performance Optimization

### Database Optimization
```sql
-- Create indexes for performance
CREATE INDEX CONCURRENTLY idx_planningfact_session_period 
ON bps_planningfact(session_id, period_id);

CREATE INDEX CONCURRENTLY idx_planningfact_extra_dims 
ON bps_planningfact USING GIN(extra_dimensions_json);

-- Analyze tables
ANALYZE bps_planningfact;
```

### Caching Configuration
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
```

## Security Considerations

### Production Security Settings
```python
# settings.py (production)
DEBUG = False
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
```

### Firewall Configuration
```bash
# UFW firewall rules
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
```

## Troubleshooting

### Common Issues

#### Database Connection Issues
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check database connectivity
psql -h localhost -U bps_user -d bps -c "SELECT 1;"
```

#### Static Files Not Loading
```bash
# Collect static files
python manage.py collectstatic --noinput

# Check nginx configuration
sudo nginx -t
sudo systemctl reload nginx
```

#### High Memory Usage
```bash
# Monitor memory usage
htop
free -h

# Check Django processes
ps aux | grep gunicorn
```

### Log Analysis
```bash
# Application logs
tail -f /var/log/bps/django.log

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# System logs
journalctl -u bps.service -f
```

## Maintenance

### Regular Maintenance Tasks
```bash
# Weekly maintenance script
#!/bin/bash

# Update system packages
sudo apt update && sudo apt upgrade -y

# Clean old log files
find /var/log/bps -name "*.log" -mtime +30 -delete

# Vacuum database
sudo -u postgres psql -d bps -c "VACUUM ANALYZE;"

# Restart services
sudo systemctl restart bps
sudo systemctl restart nginx
```

### Scaling Considerations
- **Horizontal Scaling**: Load balancer with multiple application servers
- **Database Scaling**: Read replicas for reporting queries
- **Caching**: Redis cluster for distributed caching
- **CDN**: Static file delivery via CDN
- **Monitoring**: Prometheus + Grafana for metrics