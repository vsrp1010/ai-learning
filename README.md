# AI Learning — Kubernetes Troubleshooting Agent

A hands-on AI engineering project built during a 2-week AI learning sprint.

The primary capstone is a **Kubernetes troubleshooting agent** that uses:

* MCP for tool integration
* Multiple LLM providers
* Local open-weight models via Ollama
* Multi-step agent/tool-calling workflows
* Automated evaluation
* FastAPI
* Docker

The Weather MCP server is included as a simple MCP example. The main application is the Kubernetes troubleshooting agent.

---

## Architecture

```text
                         ┌─────────────────────┐
                         │     FastAPI API      │
                         │      :8080           │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │     AI Agent         │
                         │                     │
                         │ Provider abstraction │
                         │ Tool routing         │
                         │ Agent loop           │
                         └───────┬───────┬─────┘
                                 │       │
                         MCP     │       │     MCP
                                 ▼       ▼
                       ┌────────────┐ ┌──────────────┐
                       │  Weather   │ │ Kubernetes   │
                       │ MCP :8000  │ │ MCP :8001    │
                       └────────────┘ └──────────────┘

                         LLM Providers
                       ┌──────┬──────┬──────┐
                       │ Groq │Gemini│Ollama│
                       └──────┴──────┴──────┘
```

---

# 1. Prerequisites

The project uses:

* macOS
* Python 3.13+
* `uv`
* Docker Desktop
* Ollama (only required for local-model testing)

Check versions:

```bash
python3 --version
uv --version
docker --version
```

If using Ollama:

```bash
ollama --version
```

---

# 2. Project Setup

Clone the repository and enter the project:

```bash
git clone <repository-url>
cd ai-learning
```

Create/sync the virtual environment:

```bash
uv sync
```

Run commands through the project environment with:

```bash
uv run ...
```

---

# 3. Environment Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Example configuration:

```dotenv
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b

GROQ_API_KEY=
GEMINI_API_KEY=

WEATHER_MCP_URL=http://127.0.0.1:8000/mcp
KUBERNETES_MCP_URL=http://127.0.0.1:8001/mcp

AGENT_MAX_ITERATIONS=10
TOOL_TIMEOUT=10
TOOL_MAX_RETRIES=2

LOG_LEVEL=INFO
```

Do not commit `.env`.

Check Git status:

```bash
git status
```

---

# 4. Run Weather MCP Server

The Weather MCP server uses Streamable HTTP.

Start it:

```bash
uv run python src/ai_learning/weather_server.py
```

Expected:

```text
Uvicorn running on http://127.0.0.1:8000
```

Leave this terminal running.

## Basic HTTP check

A plain GET is expected to return a protocol error because MCP Streamable HTTP requires an MCP session:

```bash
curl -i http://127.0.0.1:8000/mcp
```

A response such as:

```text
HTTP/1.1 400 Bad Request
```

with:

```json
{
  "error": {
    "message": "Bad Request: Missing session ID"
  }
}
```

is normal and confirms the endpoint is reachable.

Do not use a simple HTTP GET as an MCP functional test.

---

# 5. Run Kubernetes MCP Server

Start the Kubernetes MCP server in another terminal.

Use the project's Kubernetes MCP server command/source as configured in the repository.

The server should listen on:

```text
http://127.0.0.1:8001/mcp
```

Verify that it is running before starting the agent.

---

# 6. Inspect MCP Servers

The project includes an MCP inspection client.

Run:

```bash
uv run python src/ai_learning/mcp_inspect_client.py
```

This is useful for verifying MCP capabilities such as:

* tools
* resources
* prompts
* schemas
* server capabilities

The Kubernetes MCP should expose tools including:

```text
get_pod_status
get_pods_for_deployment
get_pod_logs
restart_deployment
diagnose_pod
```

Resources include:

```text
k8s://deployments
k8s://cluster-config
```

---

# 7. Run the Agent Directly

With both MCP servers running:

```bash
uv run python src/ai_learning/multi_mcp_agent.py
```

The agent should discover and display namespaced tools similar to:

```text
weather.get_weather
weather.get_time
kubernetes.get_pod_status
kubernetes.get_pods_for_deployment
kubernetes.get_pod_logs
kubernetes.restart_deployment
kubernetes.diagnose_pod
```

It should also display the mapping from namespaced model-facing tools to their MCP server/tool.

Example:

```text
kubernetes.get_pod_logs → KUBERNETES:get_pod_logs
```

---

# 8. Run the FastAPI Agent Locally

Start the API:

```bash
uv run uvicorn ai_learning.api:app --host 127.0.0.1 --port 8080
```

Expected:

```text
Uvicorn running on http://127.0.0.1:8080
```

Both MCP servers must already be running.

---

# 9. Test Health

In another terminal:

```bash
curl http://127.0.0.1:8080/health
```

Expected:

```json
{"status":"ok"}
```

---

# 10. Test Readiness

```bash
curl http://127.0.0.1:8080/ready
```

Expected:

```json
{"status":"ready"}
```

Readiness verifies that the application has completed its startup requirements, including MCP connectivity.

---

# 11. Test Kubernetes Troubleshooting

Example:

```bash
curl -X POST http://127.0.0.1:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message":"Investigate the payments deployment. Identify any unhealthy pods, diagnose the problem, and use the pod logs to determine the likely root cause. Give me a concise summary of the evidence and recommended next steps. Do not restart anything unless I explicitly ask you to."
  }'
```

A successful response contains:

```json
{
  "answer": "...",
  "iterations": 5,
  "tools_used": [
    "kubernetes.get_pods_for_deployment",
    "kubernetes.get_pod_status",
    "kubernetes.get_pod_status",
    "kubernetes.get_pod_logs"
  ],
  "error": null
}
```

The simulated payments scenario currently contains:

```text
payments-xyz123
    Running
    healthy

payments-xyz456
    CrashLoopBackOff
    8 restarts
```

The failing pod's logs contain:

```text
ERROR: connection refused: postgres.production.svc:5432
```

The expected behavior is that the agent:

1. Finds the deployment's pods
2. Identifies the unhealthy pod
3. Checks its status
4. Retrieves logs
5. Determines the likely root cause
6. Provides evidence
7. Recommends next steps
8. Does NOT restart anything without explicit authorization

---

# 12. Run Evaluations

The evaluation framework is in:

```text
src/ai_learning/evaluation/
```

Run the evaluation suite:

```bash
uv run python src/ai_learning/evaluation/runner.py
```

The evaluator checks things such as:

* tool selection
* expected facts
* final answer correctness
* no-tool cases
* multi-tool cases
* iterations
* latency
* provider/model behavior

A successful suite reports PASS results.

The project has previously been verified with:

```text
Local Qwen: 6/6 PASS
Groq:       6/6 PASS
```

Incorrect tool selection and incorrect answers should produce failures rather than false positives.

---

# 13. Test Different LLM Providers

Provider selection is controlled through `.env`.

## Groq

```dotenv
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b
GROQ_API_KEY=<your-key>
```

Then run the agent/API normally.

---

## Gemini

Set:

```dotenv
LLM_PROVIDER=gemini
LLM_MODEL=<configured-gemini-model>
GEMINI_API_KEY=<your-key>
```

Then run:

```bash
uv run python src/ai_learning/multi_mcp_agent.py
```

or the FastAPI service.

---

## Ollama / Local Model

Start Ollama:

```bash
ollama serve
```

Verify:

```bash
ollama list
```

The project has been tested with:

```text
Qwen 3 4B instruct
```

If the model is not already available:

```bash
ollama pull qwen3:4b
```

Configure:

```dotenv
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:4b
```

Then run:

```bash
uv run python src/ai_learning/multi_mcp_agent.py
```

---

# 14. Docker Build

Build the agent image:

```bash
docker build --progress=plain -t ai-learning-agent:dev .
```

List the image:

```bash
docker images ai-learning-agent
```

The image is currently based on Python 3.13 slim and installs the project using `uv`.

---

# 15. Run the Agent in Docker

The MCP servers currently run on the host.

Docker reaches host services using:

```text
host.docker.internal
```

Run:

```bash
docker run --rm \
  --name ai-learning-agent \
  -p 8080:8080 \
  --env-file .env \
  -e WEATHER_MCP_URL=http://host.docker.internal:8000/mcp \
  -e KUBERNETES_MCP_URL=http://host.docker.internal:8001/mcp \
  ai-learning-agent:dev
```

The MCP servers must already be running on the host.

---

# 16. Test the Dockerized API

Health:

```bash
curl http://127.0.0.1:8080/health
```

Expected:

```json
{"status":"ok"}
```

Readiness:

```bash
curl http://127.0.0.1:8080/ready
```

Expected:

```json
{"status":"ready"}
```

Kubernetes troubleshooting:

```bash
curl -X POST http://127.0.0.1:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message":"Investigate the payments deployment. Identify any unhealthy pods, diagnose the problem, and use the pod logs to determine the likely root cause. Give me a concise summary of the evidence and recommended next steps. Do not restart anything unless I explicitly ask you to."
  }'
```

---

# 17. Docker Connectivity Test

If the container cannot reach a host MCP server, first verify basic connectivity from a container.

For example:

```bash
docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  python:3.13-slim \
  python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:8000/mcp').status)"
```

Important:

A `400` or `406` response from `/mcp` does not necessarily mean networking is broken.

MCP Streamable HTTP expects MCP protocol requests rather than a normal browser-style HTTP GET.

The important distinction is:

```text
Connection failure
    ↓
network/Docker problem

HTTP 400/406 from MCP endpoint
    ↓
endpoint is reachable; request may simply not be a valid MCP request
```

---

# 18. Useful Docker Commands

List running containers:

```bash
docker ps
```

List all containers:

```bash
docker ps -a
```

View logs:

```bash
docker logs ai-learning-agent
```

Follow logs:

```bash
docker logs -f ai-learning-agent
```

Stop a running container:

```bash
docker stop ai-learning-agent
```

Remove a stopped container:

```bash
docker rm ai-learning-agent
```

Remove the image:

```bash
docker rmi ai-learning-agent:dev
```

---

# 19. Useful Local Development Commands

Run the agent:

```bash
uv run python src/ai_learning/multi_mcp_agent.py
```

Run the MCP inspection client:

```bash
uv run python src/ai_learning/mcp_inspect_client.py
```

Run the Weather MCP server:

```bash
uv run python src/ai_learning/weather_server.py
```

Run FastAPI:

```bash
uv run uvicorn ai_learning.api:app --host 127.0.0.1 --port 8080
```

Run evaluations:

```bash
uv run python src/ai_learning/evaluation/runner.py
```

Synchronize dependencies:

```bash
uv sync
```

Check locked dependencies:

```bash
uv lock --check
```

---

# 20. Logging

The log level is controlled through:

```dotenv
LOG_LEVEL=INFO
```

For more verbose troubleshooting:

```bash
LOG_LEVEL=DEBUG uv run python src/ai_learning/multi_mcp_agent.py
```

Useful information in the logs includes:

* MCP connections
* agent iterations
* requested tools
* tool execution
* MCP errors
* provider calls
* failures

---

# 21. Configuration

Current configuration:

```dotenv
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b

GROQ_API_KEY=
GEMINI_API_KEY=

WEATHER_MCP_URL=http://127.0.0.1:8000/mcp
KUBERNETES_MCP_URL=http://127.0.0.1:8001/mcp

AGENT_MAX_ITERATIONS=10
TOOL_TIMEOUT=10
TOOL_MAX_RETRIES=2

LOG_LEVEL=INFO
```

For Docker, override MCP URLs:

```text
WEATHER_MCP_URL=http://host.docker.internal:8000/mcp
KUBERNETES_MCP_URL=http://host.docker.internal:8001/mcp
```

---

# 22. Typical Development Workflow

For normal local development:

### Terminal 1 — Weather MCP

```bash
uv run python src/ai_learning/weather_server.py
```

### Terminal 2 — Kubernetes MCP

```bash
# Start the Kubernetes MCP server
```

### Terminal 3 — FastAPI

```bash
uv run uvicorn ai_learning.api:app --host 127.0.0.1 --port 8080
```

### Terminal 4 — Test

```bash
curl http://127.0.0.1:8080/health
```

```bash
curl http://127.0.0.1:8080/ready
```

Then run a troubleshooting request:

```bash
curl -X POST http://127.0.0.1:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Investigate the payments deployment. Identify unhealthy pods, diagnose the problem using pod logs, and recommend next steps. Do not restart anything unless I explicitly ask you to."}'
```

---

# 23. Production-Like Docker Workflow

### Start MCP servers on host

Weather:

```bash
uv run python src/ai_learning/weather_server.py
```

Kubernetes:

```bash
# Start Kubernetes MCP server
```

### Build agent

```bash
docker build --progress=plain -t ai-learning-agent:dev .
```

### Start agent

```bash
docker run --rm \
  --name ai-learning-agent \
  -p 8080:8080 \
  --env-file .env \
  -e WEATHER_MCP_URL=http://host.docker.internal:8000/mcp \
  -e KUBERNETES_MCP_URL=http://host.docker.internal:8001/mcp \
  ai-learning-agent:dev
```

### Verify

```bash
curl http://127.0.0.1:8080/health
```

```bash
curl http://127.0.0.1:8080/ready
```

### Exercise the capstone

```bash
curl -X POST http://127.0.0.1:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Investigate the payments deployment. Identify any unhealthy pods, diagnose the problem, inspect logs, determine the likely root cause, and recommend remediation. Do not restart anything unless I explicitly ask you to."}'
```

---

# 24. Troubleshooting Checklist

## Agent fails during startup

Check:

```bash
docker ps
```

Verify both MCP servers are running.

For local execution:

```bash
curl -i http://127.0.0.1:8000/mcp
curl -i http://127.0.0.1:8001/mcp
```

For Docker, verify the container can resolve the host:

```bash
docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  python:3.13-slim \
  python -c "import socket; print(socket.gethostbyname('host.docker.internal'))"
```

Then verify the MCP endpoints are reachable from the container.

---

## `/health` works but `/ready` fails

This usually indicates an application startup/dependency problem.

Check:

* MCP server availability
* MCP URLs
* provider configuration
* API credentials
* application logs

---

## MCP returns HTTP 400/406

Do not immediately assume networking is broken.

MCP Streamable HTTP endpoints expect MCP protocol traffic.

A normal:

```bash
curl http://127.0.0.1:8000/mcp
```

is not a valid MCP client request.

---

## Agent reaches the wrong tool

Run:

```bash
uv run python src/ai_learning/multi_mcp_agent.py
```

Inspect:

```text
UNIFIED TOOLS FOR LLM
TOOL ROUTING
```

Confirm the namespaced tool maps to the expected MCP server/tool.

---

## Agent stops after too many iterations

Check:

```dotenv
AGENT_MAX_ITERATIONS=10
```

Increase only when the task genuinely requires more steps.

Do not use a large iteration limit to hide an agent-loop problem.

---

## Provider errors

Check the selected provider:

```dotenv
LLM_PROVIDER=groq
```

Check the model:

```dotenv
LLM_MODEL=...
```

Check the required API key is present.

Never commit API keys to Git.

---

# 25. Important Project Files

```text
src/ai_learning/
├── api.py
├── config.py
├── multi_mcp_agent.py
├── weather_server.py
├── evaluation/
│   ├── cases.py
│   └── runner.py
└── providers/
    ├── base.py
    ├── factory.py
    ├── groq.py
    ├── gemini.py
    └── local.py
```

Other important files:

```text
Dockerfile
.env
.env.example
.gitignore
pyproject.toml
uv.lock
```

---

# 26. Current Capstone Scenario

The current simulated scenario is a payments deployment.

Healthy:

```text
payments-xyz123
Running
0 restarts
```

Unhealthy:

```text
payments-xyz456
CrashLoopBackOff
8 restarts
```

Evidence:

```text
ERROR: connection refused: postgres.production.svc:5432
```

Expected agent reasoning:

```text
Deployment
    ↓
Pods
    ↓
Identify unhealthy pod
    ↓
Inspect pod status
    ↓
Inspect logs
    ↓
Evidence
    ↓
Root-cause hypothesis
    ↓
Recommended remediation
```

The agent should distinguish **investigation** from **remediation**.

A request such as:

```text
Investigate the payments deployment.
Do not restart anything.
```

must not invoke:

```text
kubernetes.restart_deployment
```

---

# 27. Development Philosophy

The project intentionally prioritizes:

```text
BUILD
  ↓
RUN
  ↓
UNDERSTAND
  ↓
EVALUATE
```

During the 2-week sprint:

* prioritize working end-to-end capabilities
* avoid unnecessary abstraction
* avoid polishing toy examples
* test behavior by actually running the system
* use the Kubernetes troubleshooting agent as the primary demonstration
* add deeper architecture/theory after the core system works

The next major areas are:

1. Tool safety and explicit approval
2. Realistic Kubernetes troubleshooting scenarios
3. Reliability/failure handling
4. Kubernetes-focused evaluation
5. Istio troubleshooting capabilities
6. Production-oriented deployment and demonstration
7. Model/provider comparison

---

# 28. Dependency Baseline

Current baseline:

```text
Python >= 3.13
FastAPI >= 0.141.1
MCP SDK = 2.0.0
OpenAI >= 3.3.1
python-dotenv >= 1.2.3
uvicorn >= 0.52.4
```

The exact resolved versions are recorded in:

```text
uv.lock
```

When changing MCP, model-provider, or deployment APIs, verify current official documentation before making changes.
