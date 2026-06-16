import atexit
import logging
import logging.handlers
import sys
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
            url=f"{settings.loki_url}/loki/api/v1/push",
            tags={"app": "yt-dlp-backend", "env": settings.environment},
            version="1",
        )
        # Wrap in QueueHandler so Loki HTTP calls don't block the event loop.
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
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        resource = Resource.create({
            SERVICE_NAME: "yt-dlp-backend",
            "deployment.environment": settings.environment,
        })
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=f"{settings.otel_endpoint}/v1/traces")
            )
        )
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()
        logger.info("OTel tracing → Tempo enabled", extra={"otel_endpoint": settings.otel_endpoint})
    except ImportError as exc:
        logger.warning("OpenTelemetry packages not installed; Tempo integration disabled: %s", exc)


# ── Mimir (Prometheus metrics) ────────────────────────────────────────────────

def _setup_mimir(app, settings) -> None:
    if not settings.prometheus_enabled:
        return
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            excluded_handlers=["/metrics", "/docs", "/redoc", "/openapi.json", "/"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
        logger.info("Prometheus metrics endpoint enabled at /metrics")
    except ImportError:
        logger.warning(
            "prometheus-fastapi-instrumentator not installed; Mimir metrics disabled"
        )


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
