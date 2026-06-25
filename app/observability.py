import asyncio
import atexit
import io
import logging
import logging.handlers
import math
import struct
import sys
import time
from queue import Queue

logger = logging.getLogger(__name__)


def setup_observability(app) -> None:
    from app.config import get_settings

    settings = get_settings()
    _setup_logging(settings)
    _setup_loki(settings)
    _setup_tempo(app, settings)
    _setup_mimir(app, settings)
    _setup_pyroscope(settings)


# ── Structured JSON logging (stdout) ──────────────────────────────────────────

def _setup_logging(settings) -> None:
    if not settings.json_logs:
        return
    try:
        from pythonjsonlogger import jsonlogger

        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    except ImportError:
        logger.warning("python-json-logger not installed; structured JSON logs disabled")


# ── Loki ──────────────────────────────────────────────────────────────────────

def _setup_loki(settings) -> None:
    if not settings.loki_url:
        return
    try:
        import logging_loki

        class _SilentLokiHandler(logging_loki.LokiHandler):
            def handleError(self, record):
                pass  # drop silently when Loki is unreachable

        loki_handler = _SilentLokiHandler(
            url=settings.loki_url,  # full URL including path
            tags={"app": "yt-dlp-backend", "env": settings.environment},
            version="1",
        )
        queue: Queue = Queue(-1)
        queue_handler = logging.handlers.QueueHandler(queue)
        listener = logging.handlers.QueueListener(queue, loki_handler, respect_handler_level=True)
        listener.start()
        atexit.register(listener.stop)

        logging.getLogger().addHandler(queue_handler)
        logger.info("Loki log shipping enabled", extra={"loki_url": settings.loki_url})
    except ImportError:
        logger.warning("python-logging-loki not installed; Loki integration disabled")


# ── Tempo (OpenTelemetry traces) ──────────────────────────────────────────────

def _setup_tempo(app, settings) -> None:
    if not settings.otel_endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        resource = Resource.create({
            SERVICE_NAME: "yt-dlp-backend",
            "deployment.environment": settings.environment,
        })
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)
            )
        )
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()
        logger.info("OTel tracing → Tempo enabled", extra={"otel_endpoint": settings.otel_endpoint})
    except ImportError as exc:
        logger.warning("OpenTelemetry packages not installed; Tempo integration disabled: %s", exc)


# ── Mimir (Prometheus metrics + remote write) ─────────────────────────────────

def _setup_mimir(app, settings) -> None:
    if not settings.mimir_url:
        return
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            excluded_handlers=["/metrics", "/docs", "/redoc", "/openapi.json", "/"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
        logger.info(
            "Prometheus /metrics + remote write → Mimir enabled",
            extra={"mimir_url": settings.mimir_url},
        )
    except ImportError:
        logger.warning(
            "prometheus-fastapi-instrumentator not installed; Mimir metrics disabled"
        )


# ── Mimir remote write helpers ────────────────────────────────────────────────

def _pb_varint(n: int) -> bytes:
    buf = []
    while n > 0x7F:
        buf.append((n & 0x7F) | 0x80)
        n >>= 7
    buf.append(n)
    return bytes(buf)

def _pb_len(field: int, data: bytes) -> bytes:
    return _pb_varint((field << 3) | 2) + _pb_varint(len(data)) + data

def _pb_str(field: int, s: str) -> bytes:
    return _pb_len(field, s.encode())

def _pb_double(field: int, v: float) -> bytes:
    return _pb_varint((field << 3) | 1) + struct.pack("<d", v)

def _pb_int64(field: int, v: int) -> bytes:
    return _pb_varint((field << 3) | 0) + _pb_varint(v)


def _build_remote_write_payload(environment: str) -> bytes:
    """Collect current Prometheus metrics and encode as a snappy-compressed remote write protobuf."""
    import snappy
    from prometheus_client import REGISTRY, generate_latest
    from prometheus_client.parser import text_fd_to_metric_families

    now_ms = int(time.time() * 1000)
    text = generate_latest(REGISTRY).decode()
    write_request = b""

    for family in text_fd_to_metric_families(io.StringIO(text)):
        for sample in family.samples:
            if math.isnan(sample.value):
                continue
            labels = {"__name__": sample.name, "env": environment, **sample.labels}
            ts = b""
            for k, v in sorted(labels.items()):
                ts += _pb_len(1, _pb_str(1, k) + _pb_str(2, v))
            ts += _pb_len(2, _pb_double(1, sample.value) + _pb_int64(2, now_ms))
            write_request += _pb_len(1, ts)

    return snappy.compress(write_request)


async def remote_write_loop(mimir_url: str, environment: str, interval: int = 15) -> None:
    """Background task: push metrics to Mimir every `interval` seconds."""
    import httpx

    logger.info("Mimir remote write loop started", extra={"interval_s": interval})
    while True:
        await asyncio.sleep(interval)
        try:
            payload = await asyncio.get_running_loop().run_in_executor(
                None, _build_remote_write_payload, environment
            )
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    mimir_url,
                    content=payload,
                    headers={
                        "Content-Type": "application/x-protobuf",
                        "Content-Encoding": "snappy",
                        "X-Prometheus-Remote-Write-Version": "0.1.0",
                    },
                    timeout=10.0,
                )
            if resp.status_code not in (200, 204):
                logger.warning(
                    "Mimir remote write non-2xx",
                    extra={"status": resp.status_code, "body": resp.text[:200]},
                )
        except Exception as exc:
            logger.warning("Mimir remote write failed: %s", exc)


# ── Pyroscope (continuous profiling) ─────────────────────────────────────────

def _setup_pyroscope(settings) -> None:
    if not settings.pyroscope_url:
        return
    try:
        import pyroscope

        pyroscope.configure(
            application_name="yt-dlp-backend",
            server_address=settings.pyroscope_url,
            tags={"environment": settings.environment},
        )
        logger.info(
            "Pyroscope profiling enabled", extra={"pyroscope_url": settings.pyroscope_url}
        )
    except ImportError:
        logger.warning("pyroscope-io not installed; Pyroscope integration disabled")
