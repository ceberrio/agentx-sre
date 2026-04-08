FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic

EXPOSE 8000

# Run as a non-root system user (SEC-MN-010).
# UID 10001 is above the 1000 range reserved for regular users and avoids
# conflicts with host UIDs that might be mapped into the container.
RUN adduser --system --uid 10001 --no-create-home app \
    && chown -R app /app
USER app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
