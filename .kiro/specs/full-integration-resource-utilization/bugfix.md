# Bugfix Requirements Document

## Introduction

Agent Guru fails to run with all subsystems integrated and active simultaneously. When launched, the system does not wire together all components (speech, vision, LLM, platform, agents, memory, reasoning, deployment, security, policy, avatar) into a unified pipeline, and does not fully utilize available hardware resources (GPU, CPU, memory) across those subsystems concurrently. The result is a system that either runs in isolation per subsystem, falls back to CPU-only processing, or leaves GPU and memory capacity idle during active processing — failing to meet the performance targets the architecture was designed around.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the Agent Guru application is started THEN the system initializes subsystems independently without wiring them into a unified integration pipeline

1.2 WHEN a voice command is issued THEN the system fails to route the request through all required subsystems (wake word → STT → LLM → intent → action → TTS) in a connected end-to-end flow

1.3 WHEN GPU hardware is available THEN the system does not allocate GPU resources to speech (Whisper), vision (InsightFace/ONNX), and LLM inference simultaneously, leaving GPU utilization below the >80% target during active processing

1.4 WHEN multiple subsystems are active THEN the system does not coordinate shared GPU memory allocation across PyTorch, ONNX Runtime, and faster-whisper, causing resource contention or idle capacity

1.5 WHEN the background service starts THEN the system does not launch all subsystems (speech engine, vision engine, memory system, policy engine, security, avatar) concurrently as a coordinated always-on service

1.6 WHEN a face recognition event occurs alongside a voice command THEN the system does not process both vision and speech pipelines in parallel, serializing work that should run concurrently

1.7 WHEN the LLM generates a response THEN the system does not feed context from the memory system and reasoning engine simultaneously, missing available context that should inform the response

### Expected Behavior (Correct)

2.1 WHEN the Agent Guru application is started THEN the system SHALL initialize all subsystems and wire them into a single unified integration pipeline with defined data flow between components

2.2 WHEN a voice command is issued THEN the system SHALL route the request through the complete pipeline: wake word detection → STT → memory context retrieval → LLM reasoning → intent recognition → policy check → action execution → TTS response

2.3 WHEN GPU hardware is available THEN the system SHALL allocate GPU resources across speech, vision, and LLM subsystems concurrently, achieving >80% GPU utilization during active processing

2.4 WHEN multiple subsystems require GPU memory THEN the system SHALL coordinate shared GPU memory allocation using a resource pool so that PyTorch, ONNX Runtime, and faster-whisper coexist without contention

2.5 WHEN the background service starts THEN the system SHALL launch all subsystems concurrently as async tasks and maintain them as a coordinated always-on service that responds to "Hey Guru" or "Hey Maya"

2.6 WHEN a face recognition event occurs alongside a voice command THEN the system SHALL process vision and speech pipelines in parallel using asyncio concurrency, completing both within their respective latency targets

2.7 WHEN the LLM generates a response THEN the system SHALL supply context retrieved from the memory system and output from the reasoning engine as part of the same inference call

### Unchanged Behavior (Regression Prevention)

3.1 WHEN no GPU is available THEN the system SHALL CONTINUE TO fall back to CPU-only processing for all subsystems without crashing

3.2 WHEN a single subsystem is tested in isolation THEN the system SHALL CONTINUE TO pass its existing unit and property-based tests without modification

3.3 WHEN the wake word "Hey Guru" is detected THEN the system SHALL CONTINUE TO activate the Guru personality and route to the male voice TTS pipeline

3.4 WHEN the wake word "Hey Maya" is detected THEN the system SHALL CONTINUE TO activate the Maya personality and route to the female voice TTS pipeline

3.5 WHEN biometric authentication is required THEN the system SHALL CONTINUE TO enforce multi-factor verification (face + voice) before executing privileged commands

3.6 WHEN the policy engine denies a command THEN the system SHALL CONTINUE TO block execution and return an appropriate voice response without bypassing the policy check

3.7 WHEN the system is in sleep mode THEN the system SHALL CONTINUE TO consume less than 5% battery per hour on mobile and less than 15% CPU on desktop, with only wake word detection active

3.8 WHEN an API key is not configured THEN the system SHALL CONTINUE TO prompt the user through the onboarding flow rather than silently failing or crashing
