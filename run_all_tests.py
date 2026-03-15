"""
Quick script to identify all failing tests in the reasoning module.
"""
import subprocess
import sys

test_files = [
    "test_action_models.py",
    "test_comprehensive_edge_cases.py",
    "test_confidence_scorer.py",
    "test_conversation_models.py",
    "test_conversation_serialization.py",
    "test_dataset_generator.py",
    "test_embedding.py",
    "test_engine.py",
    "test_entity_annotator.py",
    "test_error_models.py",
    "test_fast_router.py",
    "test_feedback_models.py",
    "test_feedback_store.py",
    "test_integration_checkpoint.py",
    "test_intent_detection_properties.py",
    "test_intent_engine.py",
    "test_intent_models.py",
    "test_knowledge_models.py",
    "test_knowledge_models_property.py",
    "test_knowledge_privacy_confidence.py",
    "test_knowledge_privacy_properties.py",
    "test_knowledge_synthesizer_handlers.py",
    "test_knowledge_synthesizer_handlers_property.py",
    "test_llm_fallback.py",
    "test_llm_models.py",
    "test_llm_properties.py",
    "test_local_llm_server.py",
    "test_logging_config.py",
    "test_memory_llm_integration.py",
    "test_memory_llm_integration_properties.py",
    "test_memory_models.py",
    "test_memory_pruning.py",
    "test_memory_retriever.py",
    "test_memory_storage_pipeline.py",
    "test_metrics_config.py",
    "test_multi_step_executor.py",
    "test_ner_extractor.py",
    "test_neural_classifier.py",
    "test_ollama_properties.py",
    "test_ollama_server.py",
    "test_online_learner.py",
    "test_output_parser.py",
    "test_pipeline.py",
    "test_reasoning_core.py",
    "test_reasoning_properties.py",
    "test_resource_management.py",
    "test_result_models.py",
    "test_sentry_config.py",
    "test_task_models.py",
    "test_tracing_config.py",
    "test_train_intent_classifier.py",
    "test_vector_db.py",
]

failed_files = []
passed_files = []

for test_file in test_files:
    print(f"\n{'='*60}")
    print(f"Testing: {test_file}")
    print('='*60)
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", 
         f"Agent_Guru/reasoning/tests/{test_file}",
         "-v", "--tb=no", "-q", "--timeout=30"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        failed_files.append(test_file)
        print(f"❌ FAILED: {test_file}")
    else:
        passed_files.append(test_file)
        print(f"✅ PASSED: {test_file}")

print(f"\n\n{'='*60}")
print("SUMMARY")
print('='*60)
print(f"✅ Passed: {len(passed_files)}/{len(test_files)}")
print(f"❌ Failed: {len(failed_files)}/{len(test_files)}")

if failed_files:
    print("\nFailed files:")
    for f in failed_files:
        print(f"  - {f}")
