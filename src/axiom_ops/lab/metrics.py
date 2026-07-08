from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


FAULT_MODES = ("none", "latency", "error_rate", "unavailable")


class LabMetrics:
    def __init__(self, service_name: str) -> None:
        self.service_name = service_name
        self.registry = CollectorRegistry()
        self.http_requests = Counter(
            "axiomops_lab_http_requests_total",
            "HTTP requests handled by a lab service.",
            ("service", "method", "path", "status"),
            registry=self.registry,
        )
        self.http_duration = Histogram(
            "axiomops_lab_http_request_duration_seconds",
            "HTTP request duration in a lab service.",
            ("service", "path"),
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
            registry=self.registry,
        )
        self.downstream_requests = Counter(
            "axiomops_lab_downstream_requests_total",
            "Calls from a lab service to a downstream dependency.",
            ("service", "target", "status"),
            registry=self.registry,
        )
        self.fault_mode = Gauge(
            "axiomops_lab_fault_mode",
            "Currently selected deterministic fault mode.",
            ("service", "mode"),
            registry=self.registry,
        )
        self.set_fault_mode("none")

    def set_fault_mode(self, selected_mode: str) -> None:
        for mode in FAULT_MODES:
            self.fault_mode.labels(service=self.service_name, mode=mode).set(
                1 if mode == selected_mode else 0
            )
