"""
Prometheus metrics for the agent runtime.
Exposed on /metrics (mounted in app.main) and scraped by the factory Prometheus.
"""
from prometheus_client import Counter, Histogram

AGENT_EXECUTIONS = Counter(
    "factory_agent_executions_total",
    "Number of agent task executions",
    ["agent_id", "status"],
)

AGENT_DURATION = Histogram(
    "factory_agent_duration_seconds",
    "Agent task execution duration in seconds",
    ["agent_id"],
    buckets=(1, 2, 5, 10, 20, 30, 60, 120, 300),
)

AGENT_TOKENS = Counter(
    "factory_agent_tokens_total",
    "LLM tokens consumed by agents",
    ["agent_id", "type"],
)

AGENT_REWORKS = Counter(
    "factory_agent_reworks_total",
    "Number of rework requests emitted by review/QA agents",
    ["agent_id"],
)
