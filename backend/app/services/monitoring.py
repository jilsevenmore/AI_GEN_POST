"""Monitoring, metrics, and observability."""
import time
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Single metric data point."""
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class HealthCheck:
    """Health check result."""
    name: str
    status: str  # healthy, degraded, unhealthy
    message: str = ""
    latency_ms: float = 0
    details: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """Thread-safe metrics collector with Prometheus-compatible output."""
    
    def __init__(self):
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()
    
    def increment(self, name: str, value: float = 1.0, labels: Dict[str, str] = None):
        """Increment a counter."""
        key = self._make_key(name, labels)
        with self._lock:
            self._counters[key] += value
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge value."""
        key = self._make_key(name, labels)
        with self._lock:
            self._gauges[key] = value
    
    def observe(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a histogram observation."""
        key = self._make_key(name, labels)
        with self._lock:
            self._histograms[key].append(value)
            # Keep only last 1000 observations
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-1000:]
    
    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics in Prometheus format."""
        with self._lock:
            result = {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    k: {
                        "count": len(v),
                        "sum": sum(v),
                        "min": min(v) if v else 0,
                        "max": max(v) if v else 0,
                        "avg": sum(v) / len(v) if v else 0,
                        "p50": self._percentile(v, 50),
                        "p95": self._percentile(v, 95),
                        "p99": self._percentile(v, 99),
                    }
                    for k, v in self._histograms.items()
                }
            }
            return result
    
    def _percentile(self, values: list, percentile: int) -> float:
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def reset(self):
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


# Global metrics instance
_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    return _metrics


# Decorator for timing functions
def timed(metric_name: str, labels: Dict[str, str] = None):
    """Decorator to time function execution."""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                _metrics.increment(f"{metric_name}_success", labels=labels)
                return result
            except Exception as e:
                _metrics.increment(f"{metric_name}_error", labels={**(labels or {}), "error": type(e).__name__})
                raise
            finally:
                duration = (time.perf_counter() - start) * 1000  # ms
                _metrics.observe(f"{metric_name}_duration_ms", duration, labels=labels)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                _metrics.increment(f"{metric_name}_success", labels=labels)
                return result
            except Exception as e:
                _metrics.increment(f"{metric_name}_error", labels={**(labels or {}), "error": type(e).__name__})
                raise
            finally:
                duration = (time.perf_counter() - start) * 1000
                _metrics.observe(f"{metric_name}_duration_ms", duration, labels=labels)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


class HealthChecker:
    """Manages health checks for the application."""
    
    def __init__(self):
        self._checks: Dict[str, Callable] = {}
    
    def register(self, name: str, check_func: Callable[[], HealthCheck]):
        """Register a health check."""
        self._checks[name] = check_func
    
    async def run_all(self) -> Dict[str, HealthCheck]:
        """Run all health checks."""
        results = {}
        for name, check_func in self._checks.items():
            try:
                start = time.perf_counter()
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()
                result.latency_ms = (time.perf_counter() - start) * 1000
                results[name] = result
            except Exception as e:
                results[name] = HealthCheck(
                    name=name,
                    status="unhealthy",
                    message=str(e),
                    latency_ms=(time.perf_counter() - start) * 1000,
                )
        return results
    
    def get_overall_status(self, results: Dict[str, HealthCheck]) -> str:
        """Determine overall health status."""
        if not results:
            return "unknown"
        statuses = [r.status for r in results.values()]
        if "unhealthy" in statuses:
            return "unhealthy"
        if "degraded" in statuses:
            return "degraded"
        return "healthy"


# Global health checker
_health_checker = HealthChecker()


def get_health_checker() -> HealthChecker:
    return _health_checker


# Structured logging setup
def setup_structured_logging():
    """Configure structured JSON logging."""
    import json
    import sys
    
    class JSONFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
            
            # Add extra fields
            for key, value in record.__dict__.items():
                if key not in ["name", "msg", "args", "created", "filename", "funcName",
                              "levelname", "levelno", "lineno", "module", "msecs",
                              "message", "name", "pathname", "process", "processName",
                              "relativeCreated", "thread", "threadName", "exc_info",
                              "exc_text", "stack_info"]:
                    log_data[key] = value
            
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)
            
            return json.dumps(log_data, default=str)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)


# Request ID middleware helper
class RequestContext:
    """Thread-local request context for logging."""
    
    _local = threading.local()
    
    @classmethod
    def set_request_id(cls, request_id: str):
        cls._local.request_id = request_id
    
    @classmethod
    def get_request_id(cls) -> Optional[str]:
        return getattr(cls._local, "request_id", None)
    
    @classmethod
    def clear(cls):
        if hasattr(cls._local, "request_id"):
            del cls._local.request_id


# Spending tracker
class SpendingTracker:
    """Track AI spending across providers."""
    
    def __init__(self):
        self._spending: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def record_spend(self, provider: str, model: str, amount_usd: float):
        key = f"{provider}/{model}"
        with self._lock:
            self._spending[key] += amount_usd
    
    def get_spending(self, provider: str = None, model: str = None) -> float:
        with self._lock:
            if provider and model:
                return self._spending.get(f"{provider}/{model}", 0)
            elif provider:
                return sum(v for k, v in self._spending.items() if k.startswith(f"{provider}/"))
            return sum(self._spending.values())
    
    def get_all_spending(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._spending)
    
    def reset(self):
        with self._lock:
            self._spending.clear()


# Global instances
_spending_tracker = SpendingTracker()


def get_spending_tracker() -> SpendingTracker:
    return _spending_tracker


# Alert manager
@dataclass
class AlertRule:
    name: str
    condition: Callable[[], bool]
    severity: str  # warning, critical
    message: str
    cooldown_seconds: int = 300


class AlertManager:
    """Manage alerts with cooldown."""
    
    def __init__(self):
        self._rules: List[AlertRule] = []
        self._last_fired: Dict[str, float] = {}
        self._lock = threading.Lock()
    
    def add_rule(self, rule: AlertRule):
        self._rules.append(rule)
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """Check all alert rules, return triggered alerts."""
        triggered = []
        now = time.time()
        
        with self._lock:
            for rule in self._rules:
                last_fired = self._last_fired.get(rule.name, 0)
                if now - last_fired < rule.cooldown_seconds:
                    continue
                
                try:
                    if rule.condition():
                        self._last_fired[rule.name] = now
                        triggered.append({
                            "name": rule.name,
                            "severity": rule.severity,
                            "message": rule.message,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                except Exception as e:
                    logger.error(f"Alert rule {rule.name} failed: {e}")
        
        return triggered


# Global alert manager
_alert_manager = AlertManager()


def get_alert_manager() -> AlertManager:
    return _alert_manager