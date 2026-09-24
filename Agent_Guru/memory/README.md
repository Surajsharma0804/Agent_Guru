# Agent Guru - Memory System

The Memory System is the Intelligence Layer's persistent knowledge store. It provides:

- **Knowledge Graph** - temporal entity/relationship storage with semantic querying
- **Preference Learning** - Bayesian confidence updates with temporal decay
- **Experience Repository** - causal trace storage with similarity search
- **Personality Evolution** - bounded parameter updates with rollback
- **Deduplication Engine** - semantic similarity merge
- **Verifier Integration** - mandatory pre-storage verification
- **GitHub Sync** - async README-only sync with exponential backoff
- **Metrics Engine** - time-series tracking with alerting
- **Adversarial Robustness** - conflict preservation, poisoning detection, tamper detection
- **Security** - AES-256-GCM encryption, RBAC, GDPR deletion, redaction
- **WAL** - write-ahead logging and crash recovery

## Quick Start

```python
from Agent_Guru.memory.config import load_config
from Agent_Guru.memory.knowledge_graph import KnowledgeGraph
from Agent_Guru.memory.models import Entity

cfg = load_config(env="dev")
graph = KnowledgeGraph()

entity = Entity(type="person", attributes={"name": "Alice"})
await graph.add_entity(entity)
result = await graph.get_entity(entity.id)
```

## Configuration

Set `MEMORY_ENV=dev|staging|prod` and override via environment variables:

| Variable | Default | Description |
|---|---|---|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection |
| `REDIS_HOST` | `localhost` | Redis host |
| `GITHUB_TOKEN` | `` | GitHub API token |
| `GITHUB_REPO_URL` | `` | Repository URL |

## Running Tests

```bash
# All memory tests
pytest Agent_Guru/memory/tests/ -q

# Property-based tests only
pytest Agent_Guru/memory/tests/ -m property -q

# Integration tests
pytest Agent_Guru/memory/tests/test_integration.py -q
```

## Docker

```bash
# Start all dependencies + memory service
docker-compose -f Agent_Guru/memory/docker-compose.yml up

# Initialize databases
python -m Agent_Guru.memory.scripts.init_db
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Integration Layer (GoalManager, SelfImprovement,   │
│                     ModelRouter)                    │
├─────────────────────────────────────────────────────┤
│  Core Engines (KnowledgeGraph, Preferences,         │
│                Experiences, Personality)            │
├─────────────────────────────────────────────────────┤
│  Cross-Cutting (Verifier, Deduplication, Metrics,   │
│                 Adversarial, Security, WAL, Sync)   │
└─────────────────────────────────────────────────────┘
```

## Correctness Properties

64 correctness properties validated via Hypothesis property-based testing. Key properties:

| # | Property | Module |
|---|---|---|
| 1 | Verified Information Storage Completeness | models |
| 2 | Temporal Versioning on Conflict | knowledge_graph |
| 3 | Referential Integrity Invariant | knowledge_graph |
| 4 | Concurrent Update Serialization | knowledge_graph |
| 6 | Semantic Deduplication | deduplication |
| 8 | Preference Signal Extraction | preference_engine |
| 15 | Complete Trace Storage | experience_repository |
| 23 | Consistency-Bounded Parameter Changes | personality_engine |
| 28 | Mandatory Pre-Storage Verification | verifier_integration |
| 44 | README-Only File Constraint | github_sync |
| 45 | Exponential Backoff Retry | github_sync |
| 47 | Persistent Sync Queue | github_sync |
| 52 | Comprehensive Metrics Tracking | metrics_engine |
| 54 | Metric Degradation Alerts | metrics_engine |
| 57 | Conflict Preservation | adversarial |
| 58 | Data Poisoning Detection | adversarial |
| 64 | Tamper Detection | adversarial |
