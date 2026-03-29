# ============================================================
# Dockerfile — User Service (Django)
#
# Multi-stage build for a lean production image.
# Uses SQLite for this POC; swap to PostgreSQL for production.
# ============================================================

FROM python:3.11-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run migrations at build time for SQLite
# (In production with PostgreSQL, migrations run as an init container)
# Run migrations
RUN python manage.py migrate --noinput

# Collect static files (THIS FIXES YOUR ISSUE)
RUN python manage.py collectstatic --noinput

# Expose Django's default port
EXPOSE 8000

# Use gunicorn for production-grade serving
# 4 sync workers — appropriate for a data-management service
CMD ["gunicorn", "user_service.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--log-level", "info", \
     "--access-logfile", "-"]
