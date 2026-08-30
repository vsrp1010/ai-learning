from pydantic import BaseModel

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

import asyncio


mcp = MCPServer("Kubernetes Simulator")


class PodStatus(BaseModel):
    name: str
    namespace: str
    deployment: str
    phase: str
    ready: bool
    restart_count: int
    node: str


class DeploymentRestartResult(BaseModel):
    deployment: str
    namespace: str
    status: str
    restarted_pods: list[str]


class PodDiagnosis(BaseModel):
    pod_name: str
    healthy: bool
    diagnosis: str
    recommendations: list[str]


class DeploymentPods(BaseModel):
    deployment: str
    namespace: str
    pods: list[str]


class PodLogs(BaseModel):
    pod_name: str
    container: str
    logs: str
    error: bool


@mcp.tool(
    description="Get the current status of a Kubernetes pod.",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
    structured_output=True,
)
def get_pod_status(pod_name: str) -> PodStatus:
    pod = pods.get(pod_name)

    if pod is None:
        raise ValueError(f"Pod '{pod_name}' not found")

    return PodStatus(
        name=pod_name,
        **pod,
    )


@mcp.tool(
    description="List the pods belonging to a Kubernetes deployment.",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
    structured_output=True,
)
def get_pods_for_deployment(
    deployment_name: str,
) -> DeploymentPods:
    deployment = deployments.get(deployment_name)

    if deployment is None:
        raise ValueError(
            f"Deployment '{deployment_name}' not found"
        )

    pod_names = [
        pod_name
        for pod_name, pod in pods.items()
        if pod["deployment"] == deployment_name
    ]

    return DeploymentPods(
        deployment=deployment_name,
        namespace=deployment["namespace"],
        pods=pod_names,
    )


@mcp.tool(
    description="Get the recent logs from a Kubernetes pod.",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
    structured_output=True,
)
def get_pod_logs(pod_name: str) -> PodLogs:
    pod = pods.get(pod_name)

    if pod is None:
        raise ValueError(f"Pod '{pod_name}' not found")

    pod_log = logs.get(pod_name)

    if pod_log is None:
        return PodLogs(
            pod_name=pod_name,
            container=pod["deployment"],
            logs="No logs available.",
            error=False,
        )

    return PodLogs(
        pod_name=pod_name,
        container=pod["deployment"],
        logs=pod_log["logs"],
        error=pod_log["error"],
    )


@mcp.tool(
    description="Restart all pods belonging to a Kubernetes deployment.",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    ),
    structured_output=True,
)
def restart_deployment(
    deployment_name: str,
) -> DeploymentRestartResult:
    deployment = deployments.get(deployment_name)

    if deployment is None:
        raise ValueError(
            f"Deployment '{deployment_name}' not found"
        )

    restarted_pods = []

    for pod_name, pod in pods.items():
        if pod["deployment"] == deployment_name:
            pod["restart_count"] += 1
            pod["phase"] = "Running"
            pod["ready"] = True
            restarted_pods.append(pod_name)

    deployment["available_replicas"] = deployment["desired_replicas"]

    return DeploymentRestartResult(
        deployment=deployment_name,
        namespace=deployment["namespace"],
        status="restarted",
        restarted_pods=restarted_pods,
    )


@mcp.tool(
    description="Diagnose the health of a Kubernetes pod and provide recommendations.",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
    structured_output=True,
)
def diagnose_pod(pod_name: str) -> PodDiagnosis:
    pod = pods.get(pod_name)

    if pod is None:
        raise ValueError(f"Pod '{pod_name}' not found")

    if pod["phase"] == "Running" and pod["ready"]:
        return PodDiagnosis(
            pod_name=pod_name,
            healthy=True,
            diagnosis="Pod is healthy and ready.",
            recommendations=[],
        )

    recommendations = []

    if pod["phase"] == "CrashLoopBackOff":
        recommendations.append("Inspect the container logs.")
        recommendations.append(
            "Check the container configuration and dependencies."
        )

    if pod["restart_count"] > 5:
        recommendations.append(
            "Investigate the high restart count."
        )

    if not pod["ready"]:
        recommendations.append(
            "Check why the pod readiness condition is failing."
        )

    return PodDiagnosis(
        pod_name=pod_name,
        healthy=False,
        diagnosis=(
            f"Pod is unhealthy: "
            f"phase={pod['phase']}, "
            f"ready={pod['ready']}."
        ),
        recommendations=recommendations,
    )


@mcp.resource(
    "k8s://deployments",
    name="list_deployments",
    description="List deployments in the Kubernetes cluster.",
    mime_type="application/json",
)
def list_deployments() -> dict:
    return deployments


@mcp.resource(
    "k8s://cluster-config",
    name="cluster_config",
    description="Get the configuration of the Kubernetes cluster.",
    mime_type="application/json",
)
def cluster_config_resource() -> dict:
    return cluster_config


@mcp.prompt(
    name="deployment_manifest",
    description="Generate a Kubernetes Deployment manifest for an application.",
)
def deployment_manifest(
    application: str,
    image: str,
    replicas: int = 1,
) -> list[dict]:
    return [
        {
            "role": "user",
            "content": (
                f"Generate a Kubernetes Deployment manifest "
                f"for '{application}'.\n"
                f"Use image '{image}' and {replicas} replica(s).\n\n"
                "Include:\n"
                "- Deployment metadata\n"
                "- Replica count\n"
                "- Container image\n"
                "- Container name\n"
                "- A sensible container port\n"
                "- Basic resource requests and limits\n"
                "- Readiness and liveness probes\n\n"
                "Return valid YAML only."
            ),
        }
    ]


# ---------------------------------------------------------------------------
# Simulated underlying Kubernetes state
# ---------------------------------------------------------------------------

cluster_config = {
    "cluster_name": "learning-cluster",
    "provider": "gcp",
    "region": "us-west1",
    "kubernetes_version": "1.32",
}


deployments = {
    "checkout": {
        "namespace": "production",
        "desired_replicas": 3,
        "available_replicas": 3,
        "image": "checkout:v1.4.2",
    },
    "payments": {
        "namespace": "production",
        "desired_replicas": 2,
        "available_replicas": 2,
        "image": "payments:v2.1.0",
    },
}


pods = {
    "checkout-abc123": {
        "namespace": "production",
        "deployment": "checkout",
        "phase": "Running",
        "ready": True,
        "restart_count": 0,
        "node": "worker-01",
    },
    "checkout-def456": {
        "namespace": "production",
        "deployment": "checkout",
        "phase": "Running",
        "ready": True,
        "restart_count": 1,
        "node": "worker-02",
    },
    "checkout-ghi789": {
        "namespace": "production",
        "deployment": "checkout",
        "phase": "Running",
        "ready": True,
        "restart_count": 0,
        "node": "worker-03",
    },
    "payments-xyz123": {
        "namespace": "production",
        "deployment": "payments",
        "phase": "Running",
        "ready": True,
        "restart_count": 0,
        "node": "worker-01",
    },
    "payments-xyz456": {
        "namespace": "production",
        "deployment": "payments",
        "phase": "CrashLoopBackOff",
        "ready": False,
        "restart_count": 8,
        "node": "worker-02",
    },
}


logs = {
    "payments-xyz123": {
        "error": False,
        "logs": (
            "Starting payments service...\n"
            "Configuration loaded successfully.\n"
            "Connected to PostgreSQL.\n"
            "Payments service started successfully."
        ),
    },
    "payments-xyz456": {
        "error": True,
        "logs": (
            "Starting payments service...\n"
            "Loading configuration...\n"
            "Connecting to PostgreSQL...\n"
            "ERROR: connection refused: "
            "postgres.production.svc:5432\n"
            "Application startup failed."
        ),
    },
    "checkout-abc123": {
        "error": False,
        "logs": (
            "Starting checkout service...\n"
            "Configuration loaded successfully.\n"
            "Checkout service started successfully."
        ),
    },
    "checkout-def456": {
        "error": False,
        "logs": (
            "Starting checkout service...\n"
            "Configuration loaded successfully.\n"
            "Checkout service started successfully."
        ),
    },
    "checkout-ghi789": {
        "error": False,
        "logs": (
            "Starting checkout service...\n"
            "Configuration loaded successfully.\n"
            "Checkout service started successfully."
        ),
    },
}


if __name__ == "__main__":
    asyncio.run(
        mcp.run_streamable_http_async(
            host="127.0.0.1",
            port=8001,
        )
    )
