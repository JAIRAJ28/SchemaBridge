"""Optional OpenTelemetry request traces and metrics via an OTLP collector."""

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_telemetry(app: FastAPI, endpoint: str | None):
    if not endpoint:
        return None

    base = endpoint.rstrip("/")
    resource = Resource.create({SERVICE_NAME: "schemabridge-api"})
    tracer = TracerProvider(resource=resource)
    tracer.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{base}/v1/traces"))
    )
    meter = MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=f"{base}/v1/metrics")
        )],
    )
    trace.set_tracer_provider(tracer)
    metrics.set_meter_provider(meter)
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer,
        meter_provider=meter,
        excluded_urls="/health",
        exclude_spans=["receive", "send"],
    )
    return tracer, meter
