FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PORT=7860

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY data ./data

RUN pip install --no-cache-dir ".[studio]"

EXPOSE 7860

CMD ["uvicorn", "taas.studio.api:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers"]
