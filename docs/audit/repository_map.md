# Agent Guru — Repository Map

> Generated: 2026-06-13 | Source: Full automated scan
> **972 Python files | 337,627 lines of code | 33 top-level modules**

## Repository Root

| File/Dir | Type | Size | Purpose |
|----------|------|------|---------|
| `main.py` | Entry | 648 lines | Primary entry point — wires all subsystems via IntegrationOrchestrator |
| `Guru_Demo.py` | Demo | 1,402 lines | Standalone demo script |
| `fix_pipeline.py` | **DEAD** | 53 lines | One-time fix script — already executed, 0 references |
| `test_execute.py` | Test | 96 lines | Root-level test file |
| `pyproject.toml` | Config | — | Project metadata, build config |
| `requirements.txt` | Deps | — | Primary dependencies |
| `requirements-cpu.txt` | Deps | — | CPU-only variant |
| `requirements-docker.txt` | Deps | — | Docker variant |
| `requirements-reasoning.txt` | Deps | — | Reasoning module deps |
| `requirements-torch.txt` | Deps | — | PyTorch deps |
| `Dockerfile` | Deploy | — | Container build |
| `docker-compose.yml` | Deploy | — | Multi-container orchestration |
| `.env` | **SECURITY** | 928 bytes | Environment variables — **NOT IN .gitignore** |
| `.env.example` | Config | — | Template for .env |
| `s -ExecutionPolicy...` | **GARBAGE** | 17,735 bytes | Accidental file from PowerShell — must delete |

## Core Modules (Agent_Guru/)

| Module | Files | Lines | Purpose | Status |
|--------|-------|-------|---------|--------|
| **integration** | 3 | 2,380 | Pipeline orchestrator (8-stage), GPU pool | ✅ CRITICAL PATH |
| **llm** | 29 | 5,919 | LLM runtime, providers, companion prompts, model router | ✅ CRITICAL PATH |
| **speech** | 99 | 31,900 | STT (Whisper), TTS, wake word, audio capture, mobile | ✅ CRITICAL PATH |
| **platform** | 129 | 61,988 | OS control, features, intent, browser, permissions | ✅ CRITICAL PATH |
| **emotion** | 3 | 334 | Emotion detection (14 emotions), empathy adapter | ✅ ACTIVE |
| **memory** | 18 | 4,639 | Conversation memory, personality engine, preferences | ✅ ACTIVE |
| **reasoning** | 345 | 133,614 | Reasoning engine, tools, verification, safety | ✅ LARGEST MODULE |
| **core** | 9 | 1,929 | AgentGuru service, config, lifecycle | ✅ ACTIVE |
| **security** | 24 | 4,893 | Voice auth, crypto, audit logging, trust | ✅ ACTIVE |
| **vision** | 65 | 15,003 | Face detection/recognition, liveness, tracking | ✅ ACTIVE |
| **self_improvement** | 69 | 38,439 | Meta-learning, stability, prompt evolution | ⚠️ REVIEW |
| **policy** | 15 | 3,387 | Policy engine, RBAC, models | ✅ ACTIVE |
| **agents** | 31 | 8,079 | Multi-agent orchestration | ⚠️ REVIEW |
| **goal_manager** | 15 | 4,266 | Goal planning, tracking | ⚠️ REVIEW |
| **deployment** | 16 | 3,472 | Deploy scripts, configs | ✅ INFRASTRUCTURE |
| **verifier** | 14 | 2,814 | Fact verification | ✅ ACTIVE |
| **avatar** | 23 | 4,426 | Visual avatar system | ⚠️ REVIEW |
| **sdk** | 9 | 1,212 | Public SDK/API | ✅ ACTIVE |
| **agent_orchestration** | 6 | 1,758 | Agent coordination | ⚠️ REVIEW |
| **health** | 4 | 442 | Health checks | ✅ ACTIVE |
| **skills** | 4 | 374 | Skill registry | ✅ ACTIVE |
| **iot** | 4 | 422 | IoT device control | ✅ ACTIVE |
| **explainability** | 3 | 342 | XAI explanations | ✅ ACTIVE |
| **resilience** | 3 | 226 | Circuit breakers, retries | ✅ ACTIVE |
| **sync** | 3 | 245 | Data sync | ✅ ACTIVE |
| **proactive** | 3 | 207 | Proactive suggestions | ✅ ACTIVE |
| **context** | 3 | 191 | Context aggregation | ✅ ACTIVE |
| **translation** | 3 | 189 | Language translation | ✅ ACTIVE |
| **learning** | 3 | 172 | Online learning | ✅ ACTIVE |
| **fusion** | 3 | 125 | Multimodal fusion | ✅ ACTIVE |
| **training** | 2 | 66 | Model training | ⚠️ MINIMAL |
| **utils** | 2 | 65 | Shared utilities | ⚠️ MINIMAL |

## Support Directories

| Directory | Purpose |
|-----------|---------|
| `scripts/` | Automation scripts |
| `stubs/` | Type stubs for mypy |
| `models/` | Model weights/configs |
| `assets/` | Static assets |
| `audit/` | Audit tooling |
| `docs/` | Documentation |
| `installer/` | Platform installers |
| `grafana/` | Monitoring dashboards |
| `prometheus/` | Metrics collection |
| `helm/` | Kubernetes Helm charts |
| `k8s/` | Kubernetes manifests |
| `terraform/` | Infrastructure as code |
| `DEMO_FILES/` | Demo resources |
| `.guru/` | Agent Guru internal config |
| `.github/` | GitHub Actions CI/CD |
