FROM python:3.12-slim AS base

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src

ARG EXTRAS=test,studio,probe,mcp,edge
RUN pip install --no-cache-dir ".[${EXTRAS}]"

RUN useradd -r -u 10001 taas && mkdir -p /data && chown taas /data
USER taas
VOLUME /data
ENV TAAS_DATA_DIR=/data

# SERVICE selects which app to run: studio | broker | proxy
ARG SERVICE=studio
ENV SERVICE=${SERVICE}
EXPOSE 8000 8001 8002
# studio -> taas.studio.api / broker -> taas.broker.api / proxy -> taas.proxy.service
CMD sh -c 'case "$SERVICE" in \
  studio) MOD=taas.studio.api:app ;; \
  broker) MOD=taas.broker.api:app ;; \
  proxy)  MOD=taas.proxy.service:app ;; \
  *) echo "unknown SERVICE=$SERVICE" >&2; exit 1 ;; esac; \
  exec python -m uvicorn "$MOD" --host 0.0.0.0 --port "${PORT:-8000}"'
