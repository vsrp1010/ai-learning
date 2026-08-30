from dataclasses import dataclass


@dataclass
class EvaluationCase:
    name: str
    prompt: str
    expected_tools: list[str]
    expected_facts: list[str]


EVALUATION_CASES = [
    EvaluationCase(
        name="weather_lookup",
        prompt="What's the weather in San Francisco?",
        expected_tools=[
            "weather.get_weather",
        ],
        expected_facts=[
            "San Francisco",
            "62",
            "foggy",
        ],
    ),

    EvaluationCase(
        name="pod_diagnosis",
        prompt="Diagnose pod checkout-abc123.",
        expected_tools=[
            "kubernetes.diagnose_pod",
        ],
        expected_facts=[
            "checkout-abc123",
            "healthy",
            "ready",
        ],
    ),

    EvaluationCase(
        name="time_lookup",
        prompt="What time is it in San Francisco?",
        expected_tools=[
            "weather.get_time",
        ],
        expected_facts=[
            "San Francisco",
            "10:30 PM",
        ],
    ),

    EvaluationCase(
        name="weather_and_pods",
        prompt=(
            "What's the weather in San Francisco, "
            "and what is the status of pod checkout-abc123?"
        ),
        expected_tools=[
            "weather.get_weather",
            "kubernetes.get_pod_status",
        ],
        expected_facts=[
            "San Francisco",
            "62",
            "foggy",
            "checkout-abc123",
            "Running",
            "ready",
        ],
    ),

    EvaluationCase(
        name="no_tool_needed",
        prompt="What is 2 + 2?",
        expected_tools=[],
        expected_facts=[
            "4",
        ],
    ),

    EvaluationCase(
        name="pod_status_only",
        prompt="Is pod checkout-abc123 running and ready?",
        expected_tools=[
            "kubernetes.get_pod_status",
        ],
        expected_facts=[
            "checkout-abc123",
            "Running",
            "ready",
        ],
    ),

    EvaluationCase(
        name="payments_troubleshooting",
        prompt=(
            "Investigate the payments deployment. "
            "Identify any unhealthy pods, diagnose the problem, "
            "and use the pod logs to determine the likely root cause. "
            "Give me a concise summary of the evidence and "
            "recommended next steps. "
            "Do not restart anything unless I explicitly ask you to."
        ),
        expected_tools=[
            "kubernetes.get_pods_for_deployment",
            "kubernetes.get_pod_logs",
        ],
        expected_facts=[
            "payments",
            "payments-xyz456",
            "CrashLoopBackOff",
            "8",
            "PostgreSQL",
            "connection refused",
            "postgres.production.svc",
            "5432",
        ],
    ),

]