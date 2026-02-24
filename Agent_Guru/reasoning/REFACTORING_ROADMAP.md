# Core Reasoning Engine - Refactoring Roadmap

**Status:** Phase 1 Complete (Foundation)  
**Date:** 2024-02-22  
**Next Session:** Continue with Phase 2

---

## ✅ COMPLETED: Phase 1 - Foundation (This Session)

### 1. Complete System Audit
- ✅ Created `AUDIT_REPORT.md` with comprehensive analysis
- ✅ Identified all duplication, dead code, and architectural issues
- ✅ Built dependency graph
- ✅ Documented removal justifications

### 2. Core Module Creation
- ✅ Created `core_reasoning/` package structure
- ✅ Created `error_handling.py` - Structured exception framework
- ✅ Created `task_schema.py` - Strict typed data contracts
- ✅ Created `__init__.py` - Clean package exports

### 3. Documentation
- ✅ Audit report with findings and recommendations
- ✅ This roadmap for continued implementation

---

## ⏳ TODO: Phase 2 - Core Modules (Next Session)

### Priority 1: LLM Layer
**Files to Create:**
1. `core_reasoning/prompt_manager.py`
   - Centralize all prompts from scattered locations
   - Implement prompt versioning
   - Add prompt injection protection
   - Support A/B testing framework
   - **Sources to merge:**
     - `reasoning/llm/prompts.py`
     - Inline prompts in `engine.py`
     - Inline prompts in various modules

2. `core_reasoning/llm_interface.py`
   - Unified LLM abstraction layer
   - Support local (Ollama) and cloud (OpenAI, Gemini, Claude) providers
   - Enforce structured JSON output
   - Retry with exponential backoff
   - JSON repair for malformed responses
   - Track token usage, latency, failure rate
   - **Sources to merge:**
     - `reasoning/llm/client.py`
     - `reasoning/llm/reasoning.py`
     - LLM calls in `engine.py`

### Priority 2: Planning Layer
**Files to Create:**
3. `core_reasoning/planner.py`
   - Convert TaskIntent → TaskPlan
   - Support single-step and multi-step plans
   - Assign deterministic execution order
   - Estimate complexity scores
   - Output structured TaskPlan objects
   - **Sources to merge:**
     - `reasoning/llm/reasoning.py` (ReasoningPlanGenerator)
     - Planning logic from `engine.py`

### Priority 3: Validation & Safety
**Files to Create:**
4. `core_reasoning/confidence_engine.py`
   - Combine multi-dimensional confidence scores
   - Trigger clarification if below threshold
   - Prevent unsafe low-confidence execution
   - **Sources to merge:**
     - Confidence logic from `engine.py`
     - Confidence scoring from various modules

5. `core_reasoning/execution_validator.py`
   - Validate tool existence
   - Validate required parameters
   - Validate execution structure
   - Reject inconsistent plans
   - **New module** - extract validation from multiple places

### Priority 4: Observability
**Files to Create:**
6. `core_reasoning/performance_monitor.py`
   - Track LLM latency, planning time, orchestration time
   - Monitor memory usage
   - Provide profiling hooks
   - Detect abnormal spikes
   - Structured logging (no print debugging)
   - **Sources to merge:**
     - `reasoning/latency/` directory
     - Metrics from `engine.py`
     - Performance tracking scattered across modules

---

## ⏳ TODO: Phase 3 - Orchestrator (Session 3)

### Main Orchestrator
**Files to Create:**
7. `core_reasoning/orchestrator.py`
   - **THE MAIN PIPELINE CONTROLLER**
   - Accept TaskInput
   - Call memory hook if present
   - Invoke llm_interface
   - Parse to task_schema
   - Validate schema
   - Call planner
   - Call tool_selector
   - Run confidence_engine
   - Run safety_gate
   - Validate via execution_validator
   - Return TaskResult
   - **MUST NOT contain:**
     - Prompt strings
     - Tool logic
     - LLM-specific logic
   - **Pure orchestration only**
   - **Replaces:** `engine.py` and `pipeline.py`

---

## ⏳ TODO: Phase 4 - Refactor Existing (Session 4)

### Existing Modules to Refactor
8. `core_reasoning/tool_selector.py`
   - Copy from `reasoning/tools/selector.py`
   - Remove duplication
   - Integrate with new error_handling
   - Integrate with new task_schema
   - Clean up, optimize

9. `core_reasoning/safety_gate.py`
   - Copy from `reasoning/safety/gate.py`
   - Integrate with new error_handling
   - Integrate with new task_schema
   - Clean up, optimize

---

## ⏳ TODO: Phase 5 - Integration & Migration (Session 5)

### Integration Tasks
1. **Update imports across codebase**
   - Replace old imports with new core_reasoning imports
   - Update all references to old modules

2. **Migrate existing functionality**
   - Move utility scripts to `scripts/` directory
   - Merge duplicate model directories
   - Consolidate scattered logic

3. **Update tests**
   - Update test imports
   - Add tests for new modules
   - Ensure >85% coverage

4. **Deprecate old modules**
   - Mark old modules as deprecated
   - Add migration warnings
   - Plan removal timeline

---

## ⏳ TODO: Phase 6 - Testing & Optimization (Session 6)

### Testing
1. **Unit Tests**
   - Test each module independently
   - Target >85% coverage
   - Property-based tests for correctness

2. **Integration Tests**
   - Test full pipeline end-to-end
   - Test error handling paths
   - Test fallback mechanisms

3. **Performance Tests**
   - Verify latency targets (<1.5s)
   - Verify throughput (1000+ req/s)
   - Verify memory usage (<2GB)

### Optimization
1. **Profile critical paths**
   - Identify bottlenecks
   - Optimize hot paths
   - Reduce memory allocations

2. **Implement caching**
   - LLM response caching
   - Prompt template caching
   - Model output caching

3. **Parallel execution**
   - Run independent stages concurrently
   - Batch similar requests
   - Optimize async/await usage

---

## 📋 REMOVAL CHECKLIST (After Migration Complete)

### Files to Remove (With Verification)
```
❌ Agent_Guru/reasoning/engine.py
   Status: ⏳ Pending - Replace with orchestrator.py
   Dependencies: 15+ modules (all must be updated)
   
❌ Agent_Guru/reasoning/pipeline.py
   Status: ⏳ Pending - Merge into orchestrator.py
   Dependencies: Tests only
   
❌ Agent_Guru/reasoning/data/ (directory)
   Status: ⏳ Pending - Merge with models/
   Dependencies: Verify all imports
```

### Files to Move (Not Remove)
```
→ scripts/
  ├── check_gpu.py
  ├── cleanup_model_checkpoints.py
  ├── convert_to_onnx.py
  ├── evaluate_models.py
  ├── optimize_models.py
  ├── profile_components.py
  ├── profile_pipeline.py
  ├── train_all.py
  ├── train_intent_classifier.py
  └── train_ner_model.py
```

---

## 🎯 SUCCESS CRITERIA

### Must Achieve Before Production
- [ ] All core modules implemented (11 modules)
- [ ] Zero code duplication (< 3%)
- [ ] Latency < 1.5s (95th percentile)
- [ ] Test coverage > 85%
- [ ] No circular dependencies
- [ ] No global mutable state
- [ ] Structured error handling throughout
- [ ] Complete type hints (mypy strict)
- [ ] Performance monitoring integrated
- [ ] All old modules deprecated/removed

### Performance Targets
- [ ] Orchestration overhead < 400ms
- [ ] LLM latency < 2s
- [ ] Tool selection < 50ms
- [ ] Safety validation < 20ms
- [ ] Memory usage < 2GB active
- [ ] Throughput > 1000 req/s

### Code Quality Targets
- [ ] No files > 500 lines
- [ ] No functions > 60 lines
- [ ] Cyclomatic complexity < 10
- [ ] No broad except blocks
- [ ] No magic numbers
- [ ] No hardcoded config

---

## 📊 PROGRESS TRACKING

### Phase 1: Foundation ✅ COMPLETE
- [x] System audit
- [x] error_handling.py
- [x] task_schema.py
- [x] Package structure

### Phase 2: Core Modules ⏳ NEXT
- [ ] prompt_manager.py
- [ ] llm_interface.py
- [ ] planner.py
- [ ] confidence_engine.py
- [ ] execution_validator.py
- [ ] performance_monitor.py

### Phase 3: Orchestrator ⏳ PENDING
- [ ] orchestrator.py

### Phase 4: Refactor Existing ⏳ PENDING
- [ ] tool_selector.py
- [ ] safety_gate.py

### Phase 5: Integration ⏳ PENDING
- [ ] Update imports
- [ ] Migrate functionality
- [ ] Update tests
- [ ] Deprecate old modules

### Phase 6: Testing & Optimization ⏳ PENDING
- [ ] Unit tests
- [ ] Integration tests
- [ ] Performance tests
- [ ] Optimization

---

## 🚀 NEXT SESSION COMMANDS

### Start Phase 2 with:
```bash
# 1. Create prompt_manager.py
# 2. Create llm_interface.py
# 3. Create planner.py
# 4. Create confidence_engine.py
# 5. Create execution_validator.py
# 6. Create performance_monitor.py
```

### Key Focus Areas:
1. **Centralize prompts** - No more scattered prompt strings
2. **Unified LLM interface** - Single point of LLM access
3. **Structured planning** - TaskIntent → TaskPlan conversion
4. **Confidence scoring** - Multi-dimensional confidence
5. **Pre-execution validation** - Catch errors before execution
6. **Observability** - Track everything

---

## 📝 NOTES FOR NEXT SESSION

### Critical Reminders:
1. **NO duplication** - Always check if logic exists before creating
2. **NO deletion without verification** - Verify zero references first
3. **Strict typing** - Complete type hints everywhere
4. **Structured errors** - Use error_handling.py exceptions
5. **Immutable schemas** - Use task_schema.py data contracts

### Architecture Principles:
1. **Separation of concerns** - Each module has ONE responsibility
2. **Dependency inversion** - Depend on abstractions, not concretions
3. **Fail-safe** - Graceful degradation, never crash
4. **Observable** - Log everything with structured logging
5. **Deterministic** - Same input → same output (no randomness in orchestration)

### Performance Principles:
1. **Profile first** - Don't optimize without data
2. **Cache aggressively** - But with proper eviction
3. **Async everything** - No blocking I/O
4. **Batch when possible** - Reduce overhead
5. **Monitor always** - Track latency, memory, throughput

---

**END OF ROADMAP**

**Current Status:** Foundation complete, ready for Phase 2  
**Estimated Remaining Work:** 5-6 sessions  
**Risk Level:** MEDIUM (good progress, clear path forward)
