# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.10-slim AS builder

WORKDIR /build

# Build deps for asyncpg, bcrypt, and python-snappy C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libsnappy-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.10-slim

# libsnappy1v5 is the only runtime system dep (python-snappy links against it)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libsnappy1v5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -r -u 1001 -s /bin/false app

WORKDIR /app

# Copy installed Python packages from the builder
COPY --from=builder /install /usr/local

# Copy application code only (no .env, no __pycache__)
COPY --chown=app:app main.py .
COPY --chown=app:app app/ app/

USER app

EXPOSE 8000

# Uses the /api/health endpoint — no curl needed
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 -c \
        "import urllib.request, sys; \
         r = urllib.request.urlopen('http://localhost:8000/api/health', timeout=4); \
         sys.exit(0 if r.status == 200 else 1)"

# --proxy-headers: trust X-Forwarded-For from the ingress (required for rate limiting)
# --forwarded-allow-ips *: accept forwarded IPs from any upstream (K8s SNAT)
CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
