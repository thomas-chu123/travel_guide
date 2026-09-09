FROM python:3.13-slim AS development

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY app ./app
COPY worker ./worker
COPY scripts ./scripts
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[translation]" \
    && python scripts/translate_supabase_content.py --install-models

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
