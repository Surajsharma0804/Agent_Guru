# Core Reasoning Engine - In-Place Refactoring Plan

**Approach:** Fix existing structure, NO new directories
**Goal:** Eliminate duplication, consolidate scattered logic

---

## ✅ PHASE 1: Consolidate Error Handling (KEEP existing error/)

### Current State:
- ✅ `error/error_manager.py` - GOOD, keep as-is
- ✅ `error/recovery.py` - Keep
- ✅ `error/fallback.py` - Keep
- ✅ `error/degradation.py` - Keep

### Actions:
1. ✅ Keep existing `error/` directory structure
2. ❌ Remove duplicate error classes from:
   - `tools/skills/sandbox_executor.py` → Use error_manager
   - `tools/skills/loader.py` → Use error_manager
   - `tools/parameter_extractor.py` → Use error_manager
   - `task_generator/task_decomposer.py` → Use error_manager
   - `llm/output_parser.py` → Use error_manager
   - `execution/executor.py` → Use error_manager

---

## ✅ PHASE 2: Merge Duplicate Model Directories

### Current State:
- `reasoning/data/` - Contains data models
- `reasoning/models/` - Contains data models
- **DUPLICATION DETECTED**

### Actions:
1. Audit both directories
2. Merge into single `models/` directory
3. Update all imports
4. Remove `data/` directory

---

## ✅ PHASE 3: Refactor engine.py (600+ lines → ~300 lines)

### Current Issues:
- Mixed responsibilities (orchestration + caching + metrics + LLM)
- 15+ direct imports
- Global mutable state

### Actions:
1. **Extract caching logic** → Create `utils/response_cache.py`
2. **Extract metrics** → Enhance `latency/tracker.py`
3. **Extract LLM calls** → Use existing `llm/` modules
4. **Keep orchestration** → Simplify engine.py to pure orchestration

---

## ✅ PHASE 4: Consolidate LLM Logic

### Current State:
- `llm/reasoning.py` - Plan generation
- `llm/client.py` - LLM client
- `llm/prompts.py` - Prompts
- `engine.py` - Also has LLM calls

### Actions:
1. ✅ Keep existing `llm/` structure
2. ❌ Remove LLM calls from `engine.py`
3. ✅ Use `llm/reasoning.py` for all plan generation
4. ✅ Centralize prompts in `llm/prompts.py`

---

## ✅ PHASE 5: Clean Up Utility Scripts

### Current State:
- Training scripts in main package
- Profiling scripts in main package
- Utility scripts mixed with core code

### Actions:
1. Create `scripts/` directory at reasoning level
2. Move all utility scripts:
   - `check_gpu.py`
   - `cleanup_model_checkpoints.py`
   - `convert_to_onnx.py`
   - `evaluate_models.py`
   - `optimize_models.py`
   - `profile_components.py`
   - `profile_pipeline.py`
   - `train_all.py`
   - `train_intent_classifier.py`
   - `train_ner_model.py`

---

## ✅ PHASE 6: Remove Dead Code

### Files to Verify and Potentially Remove:
1. `pipeline.py` - Check if used, might be duplicate of engine.py
2. Unused test files
3. Commented-out code blocks

---

## 🎯 SUCCESS METRICS

### Before:
- engine.py: 600+ lines
- Duplicate error classes: 10+
- Duplicate model directories: 2
- Scattered LLM calls: 5+ locations
- Utility scripts in main package: 10+

### After:
- engine.py: ~300 lines (pure orchestration)
- Centralized error handling: 1 location
- Single models directory: 1
- LLM calls: Only in llm/ directory
- Utility scripts: In scripts/ directory

---

## 📋 DETAILED TASK LIST

### Task 1: Consolidate Error Classes
- [ ] Update `tools/skills/sandbox_executor.py` to use ErrorManager
- [ ] Update `tools/skills/loader.py` to use ErrorManager
- [ ] Update `tools/parameter_extractor.py` to use ErrorManager
- [ ] Update `task_generator/task_decomposer.py` to use ErrorManager
- [ ] Update `llm/output_parser.py` to use ErrorManager
- [ ] Update `execution/executor.py` to use ErrorManager

### Task 2: Merge Model Directories
- [ ] List all files in `data/`
- [ ] List all files in `models/`
- [ ] Identify duplicates
- [ ] Merge into `models/`
- [ ] Update imports
- [ ] Remove `data/` directory

### Task 3: Extract from engine.py
- [ ] Create `utils/response_cache.py`
- [ ] Move caching logic
- [ ] Update engine.py to use cache module
- [ ] Remove inline caching code

### Task 4: Move Utility Scripts
- [ ] Create `scripts/` directory
- [ ] Move all utility scripts
- [ ] Update any references
- [ ] Add README in scripts/

### Task 5: Refactor engine.py
- [ ] Remove LLM calls (use llm/reasoning.py)
- [ ] Remove inline prompts (use llm/prompts.py)
- [ ] Simplify to pure orchestration
- [ ] Add clear comments for each stage

### Task 6: Update Tests
- [ ] Update test imports
- [ ] Fix broken tests
- [ ] Add missing tests
- [ ] Verify coverage

---

## 🚀 EXECUTION ORDER

1. **Start with error consolidation** (safest, clear benefit)
2. **Merge model directories** (clear duplication)
3. **Move utility scripts** (easy, no risk)
4. **Extract from engine.py** (requires careful refactoring)
5. **Update tests** (verify everything works)

---

**NEXT STEP:** Start with Task 1 - Consolidate Error Classes
