"""Distributed tracing configuration using OpenTelemetry."""

from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.zipkin.json import ZipkinExporter
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider, sampling
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Span, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


class TracingConfig:
    """Configuration for distributed tracing."""

    def __init__(
        self,
        service_name: str = "agent-guru-reasoning",
        service_version: str = "0.1.0",
        exporter_type: str = "jaeger",  # jaeger, zipkin, console
        jaeger_endpoint: str | None = None,
        zipkin_endpoint: str | None = None,
        sample_rate_success: float = 0.1,  # 10% sampling for successful requests
        sample_rate_error: float = 1.0,  # 100% sampling for errors
    ) -> None:
        """Initialize tracing configuration.

        Args:
            service_name: Name of the service
            service_version: Version of the service
            exporter_type: Type of exporter (jaeger, zipkin, console)
            jaeger_endpoint: Jaeger collector endpoint
            zipkin_endpoint: Zipkin collector endpoint
            sample_rate_success: Sampling rate for successful traces (0.0-1.0)
            sample_rate_error: Sampling rate for error traces (0.0-1.0)

        """
        self.service_name = service_name
        self.service_version = service_version
        self.exporter_type = exporter_type
        self.jaeger_endpoint = jaeger_endpoint or "http://localhost:14268/api/traces"
        self.zipkin_endpoint = zipkin_endpoint or "http://localhost:9411/api/v2/spans"
        self.sample_rate_success = sample_rate_success
        self.sample_rate_error = sample_rate_error


def configure_tracing(config: TracingConfig) -> trace.Tracer:
    """Configure OpenTelemetry distributed tracing.

    Args:
        config: Tracing configuration

    Returns:
        Configured tracer instance

    """
    # Create resource with service information
    resource = Resource(
        attributes={
            SERVICE_NAME: config.service_name,
            SERVICE_VERSION: config.service_version,
        },
    )

    # Create sampler with error-aware sampling
    sampler = ErrorAwareSampler(
        success_rate=config.sample_rate_success,
        error_rate=config.sample_rate_error,
    )

    # Create tracer provider
    provider = TracerProvider(
        resource=resource,
        sampler=sampler,
    )

    # Configure exporter
    if config.exporter_type == "jaeger":
        exporter = JaegerExporter(
            collector_endpoint=config.jaeger_endpoint,
        )
    elif config.exporter_type == "zipkin":
        exporter = ZipkinExporter(
            endpoint=config.zipkin_endpoint,
        )
    else:  # console
        exporter = ConsoleSpanExporter()

    # Add span processor
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # Set global tracer provider
    trace.set_tracer_provider(provider)

    # Return tracer
    return trace.get_tracer(__name__)


class ErrorAwareSampler(sampling.Sampler):
    """Custom sampler that samples all errors and a percentage of successes."""

    def __init__(self, success_rate: float = 0.1, error_rate: float = 1.0) -> None:
        """Initialize error-aware sampler.

        Args:
            success_rate: Sampling rate for successful traces
            error_rate: Sampling rate for error traces

        """
        self.success_sampler = sampling.TraceIdRatioBased(success_rate)
        self.error_sampler = sampling.TraceIdRatioBased(error_rate)

    def should_sample(
        self,
        parent_context,  # noqa: ANN001
        trace_id,  # noqa: ANN001
        name,  # noqa: ANN001
        kind=None,  # noqa: ANN001
        attributes=None,  # noqa: ANN001
        links=None,  # noqa: ANN001
        trace_state=None,  # noqa: ANN001
    ):
        """Determine if a span should be sampled.

        Returns:
            Sampling decision

        """
        # Check if this is an error span
        if attributes and attributes.get("error", False):
            return self.error_sampler.should_sample(
                parent_context,
                trace_id,
                name,
                kind,
                attributes,
                links,
                trace_state,
            )

        # Default to success sampling rate
        return self.success_sampler.should_sample(
            parent_context,
            trace_id,
            name,
            kind,
            attributes,
            links,
            trace_state,
        )

    def get_description(self) -> str:
        """Get sampler description."""
        return "ErrorAwareSampler"


class TracingManager:
    """Manager for distributed tracing operations."""

    def __init__(self, tracer: trace.Tracer) -> None:
        """Initialize tracing manager.

        Args:
            tracer: OpenTelemetry tracer instance

        """
        self.tracer = tracer
        self.propagator = TraceContextTextMapPropagator()

    @contextmanager
    def start_span(
        self,
        name: str,
        attributes: dict | None = None,
        set_status_on_exception: bool = True,
    ):
        """Start a new span with context manager.

        Args:
            name: Span name
            attributes: Optional span attributes
            set_status_on_exception: Whether to set error status on exception

        Yields:
            Span instance

        """
        with self.tracer.start_as_current_span(
            name,
            attributes=attributes or {},
            set_status_on_exception=set_status_on_exception,
        ) as span:
            yield span

    def add_event(self, span: Span, name: str, attributes: dict | None = None) -> None:
        """Add an event to a span.

        Args:
            span: Span to add event to
            name: Event name
            attributes: Optional event attributes

        """
        span.add_event(name, attributes=attributes or {})

    def set_attribute(self, span: Span, key: str, value) -> None:  # noqa: ANN001
        """Set an attribute on a span.

        Args:
            span: Span to set attribute on
            key: Attribute key
            value: Attribute value

        """
        span.set_attribute(key, value)

    def set_error(self, span: Span, error: Exception) -> None:
        """Mark span as error and record exception.

        Args:
            span: Span to mark as error
            error: Exception that occurred

        """
        span.set_status(Status(StatusCode.ERROR, str(error)))
        span.record_exception(error)
        span.set_attribute("error", True)

    def inject_context(self, carrier: dict) -> None:
        """Inject trace context into carrier for propagation.

        Args:
            carrier: Dictionary to inject context into

        """
        self.propagator.inject(carrier)

    def extract_context(self, carrier: dict):
        """Extract trace context from carrier.

        Args:
            carrier: Dictionary to extract context from

        Returns:
            Extracted context

        """
        return self.propagator.extract(carrier)

    def get_current_span(self) -> Span | None:
        """Get the current active span.

        Returns:
            Current span or None

        """
        return trace.get_current_span()

    def get_trace_id(self) -> str | None:
        """Get the current trace ID.

        Returns:
            Trace ID as hex string or None

        """
        span = self.get_current_span()
        if span and span.get_span_context().is_valid:
            return format(span.get_span_context().trace_id, "032x")
        return None

    def get_span_id(self) -> str | None:
        """Get the current span ID.

        Returns:
            Span ID as hex string or None

        """
        span = self.get_current_span()
        if span and span.get_span_context().is_valid:
            return format(span.get_span_context().span_id, "016x")
        return None


# Global tracing manager instance
_tracing_manager: TracingManager | None = None


def get_tracing_manager() -> TracingManager | None:
    """Get the global tracing manager instance.

    Returns:
        TracingManager instance or None if not configured

    """
    return _tracing_manager


def initialize_tracing(config: TracingConfig) -> TracingManager:
    """Initialize global tracing manager.

    Args:
        config: Tracing configuration

    Returns:
        Initialized TracingManager

    """
    global _tracing_manager
    tracer = configure_tracing(config)
    _tracing_manager = TracingManager(tracer)
    return _tracing_manager


def reset_tracing() -> None:
    """Reset global tracing manager (useful for testing)."""
    global _tracing_manager
    _tracing_manager = None
