# PAAIM API. Python 3.11 rather than the 3.9 this was developed against — the
# code is 3.9-compatible and 3.11 is meaningfully faster on the orchestration
# path, which is the slowest part of the product.
FROM python:3.11-slim

WORKDIR /app

# Build deps for bcrypt/pydantic wheels, removed again in the same layer.
RUN apt-get update && apt-get install -y --no-install-recommends gcc curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# SQLite, tenant vocabularies/mappings/monitors and the durable bus log all
# live here. Mounted as a volume so a rebuild does not wipe the demo.
ENV PAAIM_TENANT_STATE_DIR=/data/tenant_state \
    PAAIM_VOCAB_DIR=/data/tenant_state \
    DATABASE_URL=sqlite+aiosqlite:////data/paaim.db \
    BUS_DATA_DIR=/data/data_bus \
    PYTHONUNBUFFERED=1
RUN mkdir -p /data/tenant_state /data/data_bus

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s \
  CMD curl -fs http://localhost:8000/health || exit 1

# No --reload: it drops the in-memory watchers on every file touch.
CMD ["uvicorn", "paaim.main:app", "--host", "0.0.0.0", "--port", "8000"]
