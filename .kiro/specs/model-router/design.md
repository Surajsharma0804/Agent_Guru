# Design Document: Model Router

## Overview

The Model Router is an intelligent model selection system that dynamically chooses optimal language models for tasks based on cost, performance, and learned patterns. The system implements a multi-layered architecture with a model registry, task analyzer, adaptive selector, cost tracker, performance monitor, fallback manager, and learning engine. The design emphasizes cost minimization while maintaining quality through continuous learning from historical performance data.

The system starts with heuristic-based selection rules and evolves to use machine learning-informed decisions as it accumulates performance data. It supports heterogeneous model providers (local Ollama, OpenAI, Anthropic, Google) and implements sophisticated fallback strategies to ensure high availability.

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                      Model Router System                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   Task       │      │   Model      │      │   Model      │  │
│  │  Analyzer    │─────▶│  Selector    │─────▶│  Registry    │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│         │                      │                      │          │
│         │                      │                      │          │
│         ▼                      ▼                      ▼          │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │  Learning    │◀─────│ Performance  │      │    Cost      │  │
│  │   Engine     │      │   Monitor    │      │   Tracker    │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│         │                      │                      │          │
│         └──────────────────────┼──────────────────────┘          │
│                                ▼                                 │
│                        ┌──────────────┐                          │
│                        │   Fallback   │                          │
│                        │   Manager    │                          │
│                        └──────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │     LLM Runtime        │
                    │  (Ollama, OpenAI,      │
                    │   Anthropic, Google)   │
                    └────────────────────────┘
```

### Data Flow

1. **Task Submission**: Agent Orchestration submits task with requirements
2. **Task Analysis**: Task Analyzer extracts features (type, complexity, domain, constraints)
3. **Model Selection**: Model Selector queries registry, applies learning weights, selects optimal model
4. **Execution**: Selected model identifier returned to LLM Runtime
5. **Performance Recording**: Performance Monitor records outcome (success, latency, quality)
6. **Cost Recording**: Cost Tracker records actual token usage and cost
7. **Learning Update**: Learning Engine updates model weights based on performance
8. **Fallback (if needed)**: Fallback Manager retries with alternative models on failure

## Components and Interfaces

### Model Registry

**Purpose**: Maintains catalog of available models with capabilities, costs, and metadata.

**Data Model**:
```typescript
interface ModelMetadata {
  id: string;
  name: string;
  provider: 'ollama' | 'openai' | 'anthropic' | 'google';
  capabilities: Set<ModelCapability>;
  costPerInputToken: number;
  costPerOutputToken: number;
  maxTokens: number;
  averageLatency: number;
  isAvailable: boolean;
  registeredAt: timestamp;
  lastUpdated: timestamp;
}

enum ModelCapability {
  CODE_GENERATION,
  REASONING,
  DATA_ANALYSIS,
  CREATIVE_WRITING,
  CONVERSATION,
  VISION,
  FUNCTION_CALLING,
  LONG_CONTEXT
}
```

**Operations**:
- `registerModel(metadata: ModelMetadata): void`
- `updateModel(id: string, updates: Partial<ModelMetadata>): void`
- `queryModels(filter: ModelFilter): ModelMetadata[]`
- `getModel(id: string): ModelMetadata | null`
- `markUnavailable(id: string): void`

**Storage**: Persistent storage with in-memory cache for fast queries.

### Task Analyzer

**Purpose**: Analyzes incoming tasks to extract requirements and constraints.

**Data Model**:
```typescript
interface TaskSpecification {
  content: string;
  explicitModelId?: string;
  maxLatency?: number;
  maxCost?: number;
  requiredCapabilities?: Set<ModelCapability>;
  metadata?: Record<string, any>;
}

interface TaskAnalysis {
  taskType: TaskType;
  complexity: 'low' | 'medium' | 'high';
  domain: string;
  estimatedInputTokens: number;
  estimatedOutputTokens: number;
  requiredCapabilities: Set<ModelCapability>;
  latencyConstraint?: number;
  costConstraint?: number;
}

enum TaskType {
  CODE_GENERATION,
  CODE_REVIEW,
  REASONING,
  DATA_ANALYSIS,
  CREATIVE_WRITING,
  CONVERSATION,
  SUMMARIZATION,
  TRANSLATION
}
```

**Operations**:
- `analyzeTask(spec: TaskSpecification): TaskAnalysis`
- `classifyTaskType(content: string): TaskType`
- `estimateComplexity(content: string, taskType: TaskType): 'low' | 'medium' | 'high'`
- `estimateTokens(content: string): {input: number, output: number}`

**Algorithm**:
1. Parse task content for keywords and patterns
2. Classify into task type using pattern matching and heuristics
3. Estimate complexity based on content length, structure, and task type
4. Extract or infer required capabilities
5. Estimate token counts using tokenizer
6. Merge explicit constraints from task specification

### Model Selector

**Purpose**: Chooses optimal model based on task analysis and learned performance data.

**Data Model**:
```typescript
interface SelectionCriteria {
  taskAnalysis: TaskAnalysis;
  preferLocal: boolean;
  explorationRate: number;
}

interface SelectionResult {
  modelId: string;
  reasoning: string;
  estimatedCost: number;
  estimatedLatency: number;
  confidence: number;
  fallbackModels: string[];
}

interface ModelScore {
  modelId: string;
  score: number;
  costScore: number;
  performanceScore: number;
  capabilityMatch: number;
}
```

**Operations**:
- `selectModel(criteria: SelectionCriteria): SelectionResult`
- `scoreModels(candidates: ModelMetadata[], analysis: TaskAnalysis): ModelScore[]`
- `applyLearningWeights(scores: ModelScore[], taskType: TaskType): ModelScore[]`
- `selectWithExploration(scores: ModelScore[], explorationRate: number): string`

**Selection Algorithm**:
```
function selectModel(criteria):
  1. Query registry for models with required capabilities
  2. Filter by availability and constraints (latency, cost)
  3. For each candidate model:
     a. Calculate cost score (lower cost = higher score)
     b. Calculate performance score from historical data
     c. Calculate capability match score
     d. Combine scores: total = w1*cost + w2*performance + w3*capability
  4. Apply learning weights from Learning Engine
  5. Sort by total score descending
  6. With probability (1 - explorationRate): select top model
  7. With probability explorationRate: select randomly from top 3
  8. Generate fallback list from remaining top models
  9. Return selection result with reasoning
```

**Cost Score Calculation**:
```
costScore(model, task) = 1 / (1 + estimatedCost(model, task))
where estimatedCost = (inputTokens * costPerInputToken) + 
                      (outputTokens * costPerOutputToken)
```

**Performance Score Calculation**:
```
performanceScore(model, taskType) = 
  (successRate * 0.6) + 
  (1 / normalizedLatency * 0.3) +
  (qualityScore * 0.1)
```

### Cost Tracker

**Purpose**: Monitors and records spending per model and task type.

**Data Model**:
```typescript
interface CostRecord {
  id: string;
  modelId: string;
  taskType: TaskType;
  inputTokens: number;
  outputTokens: number;
  cost: number;
  timestamp: timestamp;
}

interface CostSummary {
  totalCost: number;
  costByModel: Map<string, number>;
  costByTaskType: Map<TaskType, number>;
  period: {start: timestamp, end: timestamp};
}

interface BudgetAlert {
  threshold: number;
  currentSpend: number;
  period: string;
  triggeredAt: timestamp;
}
```

**Operations**:
- `recordCost(record: CostRecord): void`
- `getCostSummary(period: TimePeriod): CostSummary`
- `projectCost(period: TimePeriod): number`
- `checkBudgetThresholds(): BudgetAlert[]`
- `calculateSavings(baseline: string): number`

**Storage**: Time-series database for efficient aggregation queries.

### Performance Monitor

**Purpose**: Tracks model performance metrics for learning and analysis.

**Data Model**:
```typescript
interface PerformanceRecord {
  id: string;
  modelId: string;
  taskType: TaskType;
  success: boolean;
  latency: number;
  qualityScore?: number;
  failureReason?: string;
  timestamp: timestamp;
}

interface PerformanceMetrics {
  modelId: string;
  taskType: TaskType;
  successRate: number;
  averageLatency: number;
  averageQuality: number;
  sampleSize: number;
}
```

**Operations**:
- `recordPerformance(record: PerformanceRecord): void`
- `getMetrics(modelId: string, taskType: TaskType): PerformanceMetrics`
- `compareModels(modelIds: string[], taskType: TaskType): PerformanceMetrics[]`
- `detectDegradation(modelId: string): boolean`

**Metrics Calculation**:
- Success rate: rolling window of last 100 tasks per model per task type
- Average latency: exponential moving average with decay factor 0.9
- Quality score: user feedback or automated evaluation (when available)

### Fallback Manager

**Purpose**: Handles model failures and executes fallback strategies.

**Data Model**:
```typescript
interface FallbackStrategy {
  taskType: TaskType;
  primaryModel: string;
  fallbackSequence: string[];
  maxRetries: number;
}

interface FallbackEvent {
  originalModel: string;
  fallbackModel: string;
  taskType: TaskType;
  reason: string;
  timestamp: timestamp;
}
```

**Operations**:
- `executeFallback(originalModel: string, taskType: TaskType, error: Error): string | null`
- `recordFallbackEvent(event: FallbackEvent): void`
- `updateFallbackStrategy(taskType: TaskType, strategy: FallbackStrategy): void`
- `deprioritizeModel(modelId: string, duration: number): void`

**Fallback Algorithm**:
```
function executeFallback(originalModel, taskType, error):
  1. Get fallback sequence for taskType
  2. Remove originalModel from sequence
  3. For each fallback model in sequence:
     a. Check if model is available
     b. If available, return fallback model
     c. Record fallback event
  4. If all fallbacks exhausted, return null
  5. Update failure statistics for originalModel
```

### Learning Engine

**Purpose**: Learns from historical data to improve model selection over time.

**Data Model**:
```typescript
interface LearningWeights {
  modelId: string;
  taskType: TaskType;
  weight: number;
  confidence: number;
  lastUpdated: timestamp;
}

interface ExplorationConfig {
  baseRate: number;
  decayFactor: number;
  minRate: number;
}
```

**Operations**:
- `updateWeights(modelId: string, taskType: TaskType, outcome: PerformanceRecord): void`
- `getWeights(taskType: TaskType): Map<string, number>`
- `calculateExplorationRate(taskType: TaskType): number`
- `initializeNewModel(modelId: string): void`

**Learning Algorithm**:
```
function updateWeights(modelId, taskType, outcome):
  1. Get current weight for (modelId, taskType)
  2. Calculate reward:
     reward = successBonus - (latency * latencyPenalty) - (cost * costPenalty)
     where successBonus = 1.0 if success else -0.5
  3. Update weight using exponential moving average:
     newWeight = (1 - learningRate) * oldWeight + learningRate * reward
  4. Update confidence based on sample size:
     confidence = min(1.0, sampleSize / minSamplesForConfidence)
  5. Store updated weight and confidence
```

**Exploration Strategy**:
- Start with high exploration rate (0.3) for new task types
- Decay exploration rate as confidence increases
- Maintain minimum exploration rate (0.05) to detect model changes
- Increase exploration temporarily when performance degrades

## Data Models

### Core Entities

**Model**:
- Unique identifier
- Provider and name
- Capability set
- Cost structure (input/output tokens)
- Performance characteristics (latency, max tokens)
- Availability status

**Task**:
- Content and metadata
- Task type classification
- Complexity level
- Token estimates
- Constraints (latency, cost, capabilities)

**Performance History**:
- Model-task type pairs
- Success/failure outcomes
- Latency measurements
- Quality scores
- Timestamps for temporal analysis

**Cost History**:
- Model-task type pairs
- Token usage (input/output)
- Calculated costs
- Timestamps for budget tracking

### Relationships

- Model (1) → (N) Performance Records
- Model (1) → (N) Cost Records
- Task Type (1) → (N) Performance Records
- Task Type (1) → (N) Learning Weights
- Model (1) → (N) Learning Weights

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Model Registry Storage Completeness
*For any* model registered in the Model_Registry, retrieving that model should return all required metadata fields (name, provider, capabilities, cost per token, availability status).
**Validates: Requirements 1.1**

### Property 2: Model Registration Validation
*For any* model metadata with missing required fields, attempting to register it should fail with a validation error, and the registry should remain unchanged.
**Validates: Requirements 1.2**

### Property 3: Historical Data Immutability
*For any* model update or availability change, all historical cost and capability records should remain unchanged and retrievable.
**Validates: Requirements 1.3, 1.5**

### Property 4: Query Result Correctness
*For any* query filter (capability, cost range, provider), all returned models should match the filter criteria, and no models matching the criteria should be excluded.
**Validates: Requirements 1.4**

### Property 5: Task Analysis Completeness
*For any* task specification, the Task_Analyzer should produce an analysis containing all required fields (task type, complexity, domain, token estimates, required capabilities).
**Validates: Requirements 2.1**

### Property 6: Task Analysis Robustness
*For any* task specification with incomplete metadata, the Task_Analyzer should successfully produce a valid analysis without failing.
**Validates: Requirements 2.3**

### Property 7: Token Estimation Bounds
*For any* task content, the estimated token counts should be within 20% of the actual token counts when measured with the target model's tokenizer.
**Validates: Requirements 2.4**

### Property 8: Constraint Preservation
*For any* task specification with explicit constraints (model requirements, latency, cost), those constraints should appear unchanged in the task analysis output.
**Validates: Requirements 2.5**

### Property 9: Cost-Optimal Selection
*For any* set of models meeting task requirements, the selected model should have the lowest cost per estimated token among all capable models.
**Validates: Requirements 3.1**

### Property 10: Capability Filtering
*For any* model selection, the selected model should possess all required capabilities specified in the task analysis.
**Validates: Requirements 3.2**

### Property 11: Performance-Based Tie Breaking
*For any* two models with identical cost and capabilities, the model with higher historical success rate for the task type should be selected more frequently over multiple selections.
**Validates: Requirements 3.3**

### Property 12: Latency Constraint Satisfaction
*For any* task with explicit latency constraints, the selected model's average latency should not exceed the specified maximum.
**Validates: Requirements 3.4**

### Property 13: Graceful Constraint Relaxation
*For any* task with impossible-to-satisfy constraints, the Model_Selector should still return a model selection (not fail), prioritizing the most critical constraints.
**Validates: Requirements 3.5**

### Property 14: Local Model Preference
*For any* selection between a local model and a cloud model with equivalent capabilities and availability, the local model should be selected.
**Validates: Requirements 4.3**

### Property 15: Provider Routing Consistency
*For any* model selection result, the provider specified in the result should match the provider of the selected model in the registry.
**Validates: Requirements 4.4**

### Property 16: Local-to-Cloud Fallback
*For any* task requiring a local model that is unavailable, the fallback model should be a cloud model with equivalent capabilities.
**Validates: Requirements 4.5**

### Property 17: Cost Calculation Accuracy
*For any* completed task, the recorded cost should equal (inputTokens × costPerInputToken + outputTokens × costPerOutputToken) for the model used.
**Validates: Requirements 5.1**

### Property 18: Cost Aggregation Consistency
*For any* time period, the sum of individual cost records should equal the cumulative cost reported in the cost summary.
**Validates: Requirements 5.2**

### Property 19: Cost Projection Reasonableness
*For any* future time period, the projected cost should be within 50% of the cost that would result from extrapolating historical usage patterns.
**Validates: Requirements 5.3**

### Property 20: Budget Alert Triggering
*For any* cost threshold configuration, budget alerts should be emitted if and only if cumulative costs exceed the threshold.
**Validates: Requirements 5.4**

### Property 21: Savings Calculation Correctness
*For any* baseline model and actual model selections, calculated savings should equal (baseline cost - actual cost) summed across all tasks.
**Validates: Requirements 5.5**

### Property 22: Performance Recording Completeness
*For any* completed task, the performance record should contain all required fields (model ID, task type, success status, latency, timestamp).
**Validates: Requirements 6.1**

### Property 23: Success Rate Calculation
*For any* model and task type combination, the reported success rate should equal (number of successes / total attempts) over the measurement window.
**Validates: Requirements 6.2**

### Property 24: Latency Average Calculation
*For any* model, the reported average latency should be within 5% of the arithmetic mean of recorded latencies.
**Validates: Requirements 6.3**

### Property 25: Failure Recording Completeness
*For any* failed task, the performance record should contain both the failure reason and the model ID that was used.
**Validates: Requirements 6.4**

### Property 26: Performance Comparison Completeness
*For any* task type, the performance comparison should include all models that have at least one performance record for that task type.
**Validates: Requirements 6.5**

### Property 27: Fallback Execution
*For any* model failure, the Fallback_Manager should attempt the next model in the fallback sequence before returning an error.
**Validates: Requirements 7.1**

### Property 28: Fallback Priority Ordering
*For any* task type, the fallback sequence should be ordered by model score (descending), excluding the primary model.
**Validates: Requirements 7.2**

### Property 29: Fallback Exhaustion Error
*For any* task where all fallback models fail or are unavailable, the Fallback_Manager should return an error (not crash or hang indefinitely).
**Validates: Requirements 7.3**

### Property 30: Fallback Event Recording
*For any* fallback execution, a corresponding fallback event record should be created with all required fields.
**Validates: Requirements 7.4**

### Property 31: Failure-Based Deprioritization
*For any* model with N consecutive failures (where N exceeds threshold), the model's selection weight should decrease in subsequent selections.
**Validates: Requirements 7.5**

### Property 32: Performance-Based Weight Adjustment
*For any* model with improving performance metrics, the Learning_Engine should increase its selection weight for the relevant task type.
**Validates: Requirements 8.1, 8.2**

### Property 33: Exploration Behavior
*For any* selection with exploration enabled, lower-ranked models should be selected with probability proportional to the exploration rate.
**Validates: Requirements 8.3**

### Property 34: Degradation Detection
*For any* model whose success rate drops by more than 20% over a sliding window, the Learning_Engine should decrease its selection weight.
**Validates: Requirements 8.4**

### Property 35: New Model Initialization
*For any* newly registered model, its initial selection weight should be non-zero and based on the average weight of models with similar capabilities.
**Validates: Requirements 8.5**

### Property 36: Selection Caching
*For any* two identical task specifications submitted within the cache TTL, the second selection should return a cached result without re-executing the selection algorithm.
**Validates: Requirements 9.2**

### Property 37: Latency Warning Logging
*For any* model selection that exceeds the latency threshold, a performance warning should be logged with timing details.
**Validates: Requirements 9.3**

### Property 38: API Contract Compliance
*For any* valid task specification, the selection API should return a result containing a model identifier, estimated cost, estimated latency, and fallback models list.
**Validates: Requirements 10.1**

### Property 39: Configuration Hot Reload
*For any* configuration update, the new configuration should take effect on the next selection without requiring a system restart.
**Validates: Requirements 10.5**

### Property 40: Cost Limit Enforcement
*For any* task type with a configured cost limit, selected models should have estimated costs below the limit, or selection should fail with a cost constraint error.
**Validates: Requirements 11.1**

### Property 41: Provider Preference Enforcement
*For any* configured provider preference, models from preferred providers should be selected more frequently than equivalent models from non-preferred providers.
**Validates: Requirements 11.2**

### Property 42: Fallback Strategy Configuration
*For any* configured fallback strategy for a task type, the Fallback_Manager should use that strategy when fallback is triggered for that task type.
**Validates: Requirements 11.3**

### Property 43: Configuration Validation
*For any* invalid configuration update (e.g., negative cost limits, non-existent model IDs), the update should be rejected and the previous configuration should remain active.
**Validates: Requirements 11.4**

### Property 44: Selection Logging Completeness
*For any* model selection, a log entry should be created containing the selected model, task type, selection reasoning, and timestamp.
**Validates: Requirements 12.1**

### Property 45: Metrics Emission Completeness
*For any* completed selection, metrics should be emitted for selection latency, estimated cost, and the selected model ID.
**Validates: Requirements 12.2**

### Property 46: Failure Trace Completeness
*For any* failed selection, the trace should include the failure reason, attempted models, and the point of failure in the selection process.
**Validates: Requirements 12.3**

### Property 47: Debug Mode Verbosity
*For any* selection executed in debug mode, the logs should contain more detailed information (including score calculations and filter results) than the same selection in normal mode.
**Validates: Requirements 12.4**

## Error Handling

### Error Categories

1. **Validation Errors**:
   - Invalid model metadata (missing required fields)
   - Invalid task specifications (malformed content)
   - Invalid configuration updates (negative values, non-existent references)
   - Action: Reject input, return descriptive error, maintain system state

2. **Resource Errors**:
   - Model unavailable (offline, rate limited)
   - Network failures (timeout, connection refused)
   - Storage failures (database unavailable)
   - Action: Trigger fallback, log error, retry with backoff

3. **Constraint Errors**:
   - No model meets requirements (impossible constraints)
   - Budget exceeded (cost limit reached)
   - Latency exceeded (all models too slow)
   - Action: Relax constraints, select best-effort model, notify caller

4. **System Errors**:
   - Internal logic errors (null pointer, assertion failure)
   - Data corruption (inconsistent state)
   - Resource exhaustion (out of memory)
   - Action: Log error with stack trace, fail fast, alert monitoring

### Error Recovery Strategies

**Fallback Chain**:
```
Primary Model → Fallback 1 → Fallback 2 → Fallback 3 → Error
```

**Retry with Backoff**:
- First retry: immediate
- Second retry: 1 second delay
- Third retry: 5 second delay
- After 3 retries: move to next fallback

**Circuit Breaker**:
- Track failure rate per model
- If failure rate > 50% over 10 requests: open circuit (skip model)
- After 60 seconds: half-open (try one request)
- If success: close circuit (resume normal operation)

**Graceful Degradation**:
- If Learning_Engine fails: fall back to heuristic selection
- If Cost_Tracker fails: continue selection, log warning
- If Performance_Monitor fails: continue selection, log warning

### Error Messages

All errors should include:
- Error code (for programmatic handling)
- Human-readable message
- Context (task ID, model ID, timestamp)
- Suggested action (retry, contact support, adjust constraints)

## Testing Strategy

### Dual Testing Approach

The Model Router requires both unit tests and property-based tests for comprehensive coverage:

**Unit Tests**: Focus on specific examples, edge cases, and integration points
- Specific task classification examples (code vs. conversation)
- Edge cases (empty model registry, zero-cost models)
- Integration with LLM Runtime and Self-Improvement Engine
- Error conditions (network failures, invalid input)

**Property-Based Tests**: Verify universal properties across all inputs
- Generate random model registries, task specifications, and performance histories
- Verify properties hold for all generated inputs
- Minimum 100 iterations per property test
- Each test references its design document property

### Property-Based Testing Configuration

**Testing Library**: Use `fast-check` (TypeScript/JavaScript), `hypothesis` (Python), or `QuickCheck` (Haskell) depending on implementation language.

**Test Configuration**:
- Minimum 100 iterations per property test
- Seed randomization for reproducibility
- Shrinking enabled to find minimal failing cases
- Timeout: 30 seconds per property test

**Test Tagging**: Each property test must include a comment tag:
```
// Feature: model-router, Property 9: Cost-Optimal Selection
// For any set of models meeting task requirements, the selected model
// should have the lowest cost per estimated token among all capable models.
```

**Generator Strategy**:
- Model metadata: random providers, capabilities, costs (0.0001 to 0.1 per token)
- Task specifications: random content (10-1000 tokens), random constraints
- Performance histories: random success rates (0.0 to 1.0), latencies (10ms to 5000ms)
- Edge cases: empty sets, single elements, extreme values

### Critical Properties to Test

**Highest Priority** (must implement):
1. Property 9: Cost-Optimal Selection
2. Property 10: Capability Filtering
3. Property 17: Cost Calculation Accuracy
4. Property 27: Fallback Execution
5. Property 32: Performance-Based Weight Adjustment

**High Priority** (should implement):
6. Property 3: Historical Data Immutability
7. Property 12: Latency Constraint Satisfaction
8. Property 18: Cost Aggregation Consistency
9. Property 31: Failure-Based Deprioritization
10. Property 40: Cost Limit Enforcement

**Medium Priority** (nice to have):
- All remaining properties

### Unit Test Coverage

**Model Registry**:
- Register valid model → success
- Register invalid model → validation error
- Query by capability → returns matching models
- Update model → preserves history

**Task Analyzer**:
- Analyze code generation task → classified as CODE_GENERATION
- Analyze conversation task → classified as CONVERSATION
- Analyze task with missing metadata → infers defaults

**Model Selector**:
- Select from 3 models → chooses cheapest capable model
- Select with latency constraint → respects constraint
- Select with impossible constraints → returns best-effort

**Cost Tracker**:
- Record cost → calculates correctly
- Get summary → aggregates correctly
- Check budget → alerts when exceeded

**Performance Monitor**:
- Record success → updates success rate
- Record failure → updates failure count
- Compare models → returns all models with data

**Fallback Manager**:
- Primary fails → tries fallback
- All fail → returns error
- Record event → creates record

**Learning Engine**:
- Update weights after success → increases weight
- Update weights after failure → decreases weight
- Calculate exploration rate → decreases with confidence

### Integration Testing

**End-to-End Scenarios**:
1. Submit task → select model → record performance → update weights
2. Model fails → fallback → record event → deprioritize model
3. Budget exceeded → alert → enforce cost limits
4. New model added → initialize weights → select occasionally (exploration)

**Performance Testing**:
- Selection latency: measure 95th percentile < 50ms
- Throughput: handle 1000 selections/second
- Memory: stable memory usage over 1 million selections

### Adversarial Testing

**Hardest Possible Scenarios**:
1. **Adversarial Constraints**: Tasks with contradictory requirements (lowest cost + highest capability + lowest latency)
2. **Cascading Failures**: All models fail simultaneously, test fallback exhaustion
3. **Data Corruption**: Inject corrupted performance data, verify graceful handling
4. **Rapid Model Changes**: Models rapidly become available/unavailable, test race conditions
5. **Extreme Scale**: 10,000 models, 100 task types, verify selection remains fast
6. **Learning Instability**: Inject oscillating performance data, verify learning doesn't diverge
7. **Cost Manipulation**: Models with zero or negative costs, verify handling
8. **Capability Mismatch**: All models lack required capability, verify error handling

### Test Execution

**Continuous Integration**:
- Run all unit tests on every commit
- Run property tests on every pull request
- Run integration tests nightly
- Run performance tests weekly

**Test Reporting**:
- Coverage target: 90% line coverage, 80% branch coverage
- Property test failures: report minimal failing case (shrunk)
- Performance test failures: report latency distribution and outliers
