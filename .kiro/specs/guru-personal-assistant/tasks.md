# Implementation Plan: GURU Personal Assistant

## Overview

This implementation plan converts the GURU design into a series of incremental development tasks following a **Zero-Defect Progression Policy** and **Human-Grade Code Standards**. GURU SHALL be built only as a production system with comprehensive testing, zero warnings, and realistic security guarantees.

## Human-Grade Code Standards (MANDATORY)

**All code in GURU MUST meet senior security engineer audit standards:**

### Forbidden AI Coding Artifacts (STRICT BAN)
❌ **Generic Function Names:** `process_data()`, `handle_request()`, `do_action()`  
✅ **Domain-Specific Names:** `verify_authority_transition()`, `enforce_intrusion_lock_policy()`

❌ **Over-Abstracted Helpers:** `Manager`, `Controller`, `Service`  
✅ **Explicit Purpose:** `AuthorityStateMachine`, `IntrusionResponseEngine`, `SignedCommandVerifier`

❌ **AI-Style Defensive Noise:** `except Exception: pass`  
✅ **Explicit Error Handling:** `except SignatureVerificationError as e: self.audit_logger.log_security_violation(e)`

### Human Code Requirements
- **Explicit Intent:** Every function must clearly answer what invariant it enforces or what security boundary it protects
- **Real Domain Concepts:** Named after actual security/automation concepts, not generic helpers
- **Long-term Maintainable:** Structured for 20+ years of maintenance by human engineers
- **Audit-Ready:** Written as if every line will be reviewed by security auditors

### Code Review Heuristic (MANDATORY)
Every file MUST pass: *"Would a senior systems engineer believe this was written by another senior engineer — without knowing AI exists?"*

## Zero-Defect Progression Policy (MANDATORY)

**Definition of "Clean" - ALL must be true before proceeding:**
- Zero runtime errors
- Zero test failures  
- Zero warnings (Python, Kotlin, linter, deprecation)
- Zero known vulnerabilities (critical/high)
- Zero authority or security violations
- All required tests pass (unit, property-based, integration, security, negative)
- Audit logging intact and verified

**Security Freeze Rule:** After Task 6, authority logic, intrusion detection, and audit logging are frozen. Changes allowed only if they strengthen security and pass all tests.

## LLM Trust Boundary (Critical)

**LLMs are advisory only, never authoritative**

- LLM only produces structured intent
- Intent must pass: AuthorityState check + SignedCommandVerifier + Skill sandbox policy  
- LLMs cannot directly execute any system functions
- All LLM outputs are validated and sanitized before processing
- LLM isolation breach triggers immediate authority revocation

## Core Security Invariants (Non-Negotiable)

These invariants MUST be preserved throughout all implementation phases:

1. **Authority Enforcement:** Commands SHALL NOT execute unless AuthorityState == ARMED
2. **State Transition Security:** AuthorityState SHALL NOT transition without cryptographic proof
3. **Biometric Cooldown:** Voice re-arming SHALL NOT bypass biometric failure cooldown periods
4. **Audit Integrity:** Audit logs SHALL be append-only and cryptographically verifiable
5. **Skill Isolation:** Skills SHALL NOT access filesystem or network unless explicitly granted
6. **LLM Trust Boundary:** LLMs are advisory only, never authoritative - they produce intents that must pass authority checks
7. **Fail Closed Policy:** System SHALL disable automation on any integrity verification failure
8. **Cryptographic Verification:** All commands must pass SignedCommandVerifier before execution
9. **Sandbox Enforcement:** All skill execution must occur within process isolation boundaries

## Core Philosophy (Guiding Principle)

**"GURU treats authority as sacred and convenience as optional."**

This single principle anchors all design decisions: when security conflicts with usability, security wins. When authority verification conflicts with speed, verification wins. When audit logging conflicts with performance, logging wins.

## Root of Trust (Architectural Foundation)

**The AuthorityStateMachine is the root of trust for all execution decisions.**

All automation, input simulation, skill execution, and system operations derive their legitimacy from the AuthorityStateMachine. No component may bypass or override authority decisions. This establishes a single, unambiguous source of truth for all security decisions.

## No Silent Downgrade Rule (Critical)

**Any failure to enforce a security invariant MUST result in Safe Halt, never degraded operation.**

GURU never operates in "best effort" mode when security is compromised. There is no graceful degradation that weakens security boundaries. All security failures trigger immediate system halt with explicit user notification.

## Threat → Control Mapping (Security Coverage Matrix)

This matrix provides auditors with instant visibility into security coverage:

| **Threat** | **Primary Control** | **Secondary Control** | **Detection** |
|------------|--------------------|--------------------|---------------|
| Voice spoofing | Speaker verification + confidence thresholds | Biometric cooldown periods | Intrusion detection → workstation lock |
| Voice replay attacks | Temporal context validation | Background audio detection | Failed attempts → security log |
| Biometric spoofing | Windows Hello liveness detection | Multi-factor requirement | Immediate workstation lock |
| Authority bypass | AuthorityStateMachine enforcement | Atomic state transitions | Critical security violation log |
| Privilege escalation | Least-privilege access controls | Component isolation boundaries | Authority revocation |
| Command replay | SignedCommandVerifier + nonce | Timestamp validation | Communication channel reset |
| Skill sandbox escape | Process isolation + resource limits | Permission boundary enforcement | Immediate skill termination |
| Audit log tampering | Append-only signed logs | Cryptographic integrity verification | Complete system halt |
| LLM prompt injection | Structured intent validation | Authority gate routing | Output sanitization |
| Component compromise | Health monitoring + failure detection | Inter-component authentication | Safe system shutdown |
| Cryptographic attacks | Modern algorithms (ECDSA-P256, AES-256) | Hardware security integration | Algorithm monitoring |
| Physical access | OS-level security compliance | Device encryption | Physical security monitoring |
| Network interception | TLS 1.3 + certificate pinning | Device fingerprinting | Secure disconnection |
| Memory corruption | Memory protection + bounds checking | Component restart isolation | Immediate authority revocation |
| Race conditions | Atomic operations + thread safety | State transition validation | Concurrent access logging |

**Coverage Principle:** Every identified threat has a primary control, secondary control, and detection mechanism. No single point of failure exists in the security architecture.

## Safe Halt Policy (Critical)

**Fail Closed, Never Fail Open**

Automation SHALL be immediately disabled on:
- Audit log failure or corruption
- Authority state corruption or verification failure  
- Cryptographic verification failure
- Internal integrity check failure
- Sandbox escape detection

**Safe Halt Procedure:**
1. Immediately transition to LOCKED_LISTEN_ONLY state
2. Disable all automation capabilities
3. Log security event with maximum severity
4. Require manual verification before any restoration

## Module Boundary Enforcement (Architectural Constraints)

**"Who Can Change What" Rules:**

- **ONLY** AuthorityStateMachine can modify AuthorityState variables
- **ONLY** AuditLogger can write to audit logs
- **ONLY** SkillRunner can execute skills within sandboxes
- **ONLY** CryptographicEngine can perform cryptographic operations
- **ONLY** BiometricVerifier can interact with OS biometric APIs

**Cross-Module Communication Rules:**
- No direct cross-module writes without verification
- All inter-module communication must be authenticated
- Module interfaces are read-only except through designated APIs
- Violation of boundary rules triggers immediate system halt

## Tasks

### Phase 1: Foundation and Build System
**Phase Philosophy:** Establish secure foundation without any automation capabilities
**Phase Non-Goals:** No automation execution, no user interaction, no network communication

- [x] 1. Set up monorepo structure and build system
  - Create root directory structure with desktop-agent/, phone-agent/, shared/, memory/, skills/, agents/, infra/ci/
  - Set up .gitignore, LICENSE, and root README.md
  - Initialize package.json for workspace management
  - **Testing Required:** Directory structure validation, build system verification
  - **Security Tests:** File permission validation, secure defaults
  - **Negative Tests:** Invalid directory structures, permission failures
  - _Requirements: 15.1_

### Phase 2: Core Security Infrastructure
**Phase Philosophy:** Build unbreachable security foundation before any functionality
**Phase Non-Goals:** No automation execution, no LLM integration, no user commands

- [x] 2. Implement Authority State Machine foundation
  - [x] 2.1 Create AuthorityState enum and core state management
    - Define AuthorityState enum (LOCKED_LISTEN_ONLY, IDENTITY_VERIFICATION, ARMED, INTRUSION_DETECTED)
    - Implement state transition validation and logging
    - Create thread-safe state management with atomic operations
    - **Testing Required:** State transition validation, thread safety, logging accuracy
    - **Security Tests:** State bypass attempts, race condition exploitation
    - **Negative Tests:** Invalid transitions, corrupted state, concurrent access
    - _Requirements: 23.1, 25.1_

  - [x] 2.2 Implement Windows Hello biometric integration
    - Integrate with Windows Hello APIs for face and fingerprint authentication
    - Create biometric provider abstraction for different authentication methods
    - Add biometric confidence scoring and validation thresholds
    - **Testing Required:** Biometric provider functionality, confidence validation
    - **Security Tests:** Biometric spoofing protection, confidence manipulation
    - **Negative Tests:** Provider failures, low confidence, corrupted biometric data
    - _Requirements: 23.4, 25.4, 25.5_

  - [x] 2.3 Write property test for authority state enforcement
    - **Property 1: Authority State Enforcement**
    - **Validates: Requirements 3.1, 3.2, 24.4, 24.5**
    - **Testing Required:** All state combinations, transition invariants
    - **Security Tests:** Authority bypass attempts, privilege escalation
    - **Negative Tests:** Unauthorized state changes, corrupted state data

### Phase 3: Cryptographic Communication Layer
**Phase Philosophy:** Establish cryptographically secure device communication
**Phase Non-Goals:** No automation execution, no voice processing, no skills

- [x] 3. Implement secure device pairing and command channel
  - [x] 3.1 Create QR code pairing initiation system
    - Implement QR code generation with embedded pairing tokens and device fingerprints
    - Create QR code scanning functionality for Android agent
    - Add pairing token validation and expiration handling
    - **Testing Required:** QR generation accuracy, scanning reliability, token validation
    - **Security Tests:** QR code tampering, token replay, expiration bypass
    - **Negative Tests:** Corrupted QR codes, invalid tokens, expired sessions
    - _Requirements: 1.1, 1.2_

  - [x] 3.2 Implement asymmetric cryptographic key exchange
    - Create ECDSA-P256 key pair generation
    - Implement secure key exchange protocol with mutual authentication
    - Add key fingerprint binding to device identities
    - **Testing Required:** Key generation strength, exchange protocol correctness, fingerprint binding
    - **Security Tests:** Key compromise scenarios, exchange interception, fingerprint spoofing
    - **Negative Tests:** Weak keys, corrupted exchange, invalid fingerprints
    - _Requirements: 1.3, 2.1_

  - [x] 3.3 Write property test for command authentication
    - **Property 2: Command Authentication**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
    - **Testing Required:** All command types, signature algorithms, replay scenarios
    - **Security Tests:** Cryptographic attacks, protocol violations
    - **Negative Tests:** Malformed commands, invalid signatures, replay attempts

### Phase 4: Voice Processing and Identity Verification
**Phase Philosophy:** Enable secure voice-based identity verification only
**Phase Non-Goals:** No automation execution, no input simulation, no system control

- [ ] 4. Implement voice processing and speaker verification
  - [ ] 4.1 Integrate whisper.cpp for local speech-to-text
    - Set up whisper.cpp Python bindings and model loading
    - Implement audio preprocessing and noise reduction
    - Create voice command processing pipeline with confidence scoring
    - **Testing Required:** Speech recognition accuracy, model loading, preprocessing effectiveness
    - **Security Tests:** Audio injection attacks, model tampering, confidence manipulation
    - **Negative Tests:** Corrupted audio, missing models, preprocessing failures
    - _Requirements: 9.1, 21.3_

  - [ ] 4.2 Create voice fingerprint and speaker identification
    - Implement voice pattern analysis using spectral features
    - Create speaker enrollment and verification system
    - Add voice confidence threshold validation and calibration
    - **Testing Required:** Speaker identification accuracy, enrollment reliability, threshold effectiveness
    - **Security Tests:** Voice spoofing attacks, replay detection, threshold bypass
    - **Negative Tests:** Unrecognized speakers, corrupted patterns, calibration failures
    - _Requirements: 4.4, 4.7_

  - [ ] 4.3 Write property test for voice re-arming security
    - **Property 3: Voice Re-arming Security**
    - **Validates: Requirements 4.1, 4.3, 4.4, 4.5, 4.7, 4.8**
    - **Testing Required:** Voice verification across conditions, phrase security
    - **Security Tests:** Voice cloning, replay attacks, phrase leakage
    - **Negative Tests:** Unauthorized speakers, corrupted audio, phrase extraction

### Phase 5: Intrusion Detection and Response
**Phase Philosophy:** Implement active security monitoring and response
**Phase Non-Goals:** No automation execution, no user commands, no skills

- [ ] 5. Implement intrusion detection and automatic workstation locking
  - [ ] 5.1 Create biometric verification failure detection
    - Implement failed verification attempt tracking and analysis
    - Add failure pattern recognition and anomaly detection
    - Create verification failure rate monitoring and thresholds
    - **Testing Required:** Failure detection accuracy, pattern recognition, threshold effectiveness
    - **Security Tests:** Detection evasion, pattern manipulation, threshold bypass
    - **Negative Tests:** False positives, detection corruption, threshold failures
    - _Requirements: 26.1, 26.2, 26.3_

  - [ ] 5.2 Implement automatic workstation locking system
    - Create Windows API integration for workstation locking (LockWorkStation)
    - Add immediate lock trigger without user confirmation or delay
    - Implement lock action logging with high severity context
    - **Testing Required:** Lock mechanism reliability, trigger responsiveness, logging accuracy
    - **Security Tests:** Lock bypass attempts, trigger manipulation, logging corruption
    - **Negative Tests:** Lock failures, trigger corruption, logging issues
    - _Requirements: 26.5, 26.6, 26.7_

  - [ ] 5.3 Write property test for intrusion detection response
    - **Property 4: Intrusion Detection Response**
    - **Validates: Requirements 26.1, 26.2, 26.3, 26.4, 26.5, 26.6**
    - **Testing Required:** All intrusion scenarios, response timing, lock reliability
    - **Security Tests:** Detection evasion, response delays, lock bypass
    - **Negative Tests:** False alarms, response failures, corrupted detection

### Phase 6: SECURITY CHECKPOINT
**Phase Philosophy:** Validate all security systems before enabling automation
**Phase Non-Goals:** No new features, no automation execution

- [ ] 6. **SECURITY CHECKPOINT** - Ensure core security systems pass all tests
  - **MANDATORY VALIDATION:** All security components must be production-ready
  - **SECURITY FREEZE ACTIVATED:** Authority, intrusion, and audit logic frozen after this point
  - Ensure all tests pass, ask the user if questions arise.

### Phase 7: Input Simulation Engine (Authority-Gated)
**Phase Philosophy:** Enable controlled automation with strict authority enforcement
**Phase Non-Goals:** No LLM integration, no complex skills, no autonomous operation

- [ ] 7. Implement voice-driven input simulation engine
  - [ ] 7.1 Create Windows API keyboard input simulation
    - Implement SendInput API integration for keyboard simulation
    - Add key combination support (Ctrl+C, Alt+Tab, Windows+R, etc.)
    - Create input validation and sanitization for security
    - **Testing Required:** Input accuracy, key combination reliability, validation effectiveness
    - **Security Tests:** Input injection attacks, validation bypass, API abuse
    - **Negative Tests:** Invalid inputs, corrupted combinations, validation failures
    - _Requirements: 17.1, 17.2_

  - [ ] 7.2 Write property test for input simulation fidelity
    - **Property 5: Input Simulation Fidelity**
    - **Validates: Requirements 17.3, 17.7, 17.10**
    - **Testing Required:** Text fidelity, input determinism, authority enforcement
    - **Security Tests:** Input manipulation, authority bypass, injection attacks
    - **Negative Tests:** Corrupted input, unauthorized access, API failures

### Phase 8: Memory and Data Management
**Phase Philosophy:** Add contextual intelligence with privacy protection
**Phase Non-Goals:** No external data sharing, no cloud synchronization

- [ ] 8. Implement memory service with MIRIX architecture
  - [ ] 8.1 Create SQLite database foundation and schema
    - Set up SQLite database with optimized schema for six memory types
    - Implement database connection pooling and transaction management
    - Create database migration system and version control
    - **Testing Required:** Schema validation, connection reliability, migration accuracy
    - **Security Tests:** SQL injection prevention, connection security, migration tampering
    - **Negative Tests:** Schema corruption, connection failures, migration errors
    - _Requirements: 14.1, 14.3_

  - [ ] 8.2 Write property test for privacy protection
    - **Property 6: Privacy Protection**
    - **Validates: Requirements 5.2, 5.3, 5.5**
    - **Testing Required:** Data encryption, local processing, deletion completeness
    - **Security Tests:** Data exfiltration attempts, encryption bypass, recovery attacks
    - **Negative Tests:** Corrupted encryption, failed deletion, external leakage

### Phase 9: Skill System and Sandboxing
**Phase Philosophy:** Enable extensible automation with strict isolation
**Phase Non-Goals:** No network access for skills, no filesystem access by default

- [ ] 9. Implement skill system with comprehensive sandboxing
  - [ ] 9.1 Create process isolation sandbox infrastructure
    - Implement Docker-based or process-level skill isolation
    - Create resource limitation and monitoring (CPU, memory, disk, network)
    - Add sandbox escape detection and prevention mechanisms
    - **Testing Required:** Isolation effectiveness, resource limiting, escape detection
    - **Security Tests:** Sandbox escape attempts, resource abuse, isolation bypass
    - **Negative Tests:** Isolation failures, resource corruption, detection evasion
    - _Requirements: 6.1_

  - [ ] 9.2 Write property test for skill sandboxing
    - **Property 7: Skill Sandboxing**
    - **Validates: Requirements 6.1, 6.3, 6.5**
    - **Testing Required:** Sandbox integrity, permission boundaries, resource isolation
    - **Security Tests:** Escape attempts, privilege escalation, resource abuse
    - **Negative Tests:** Corrupted sandbox, invalid permissions, resource exhaustion

### Phase 10: LLM Integration (Advisory Only)
**Phase Philosophy:** Add AI assistance with strict isolation boundaries
**Phase Non-Goals:** No direct LLM execution, no autonomous LLM actions

- [ ] 10. Implement LLM adapter with multi-provider support
  - [ ] 10.1 Create LLM abstraction layer and provider interface
    - Implement common LLM provider interface with standardized methods
    - Create provider registration and discovery system
    - Add provider capability detection and feature mapping
    - **Testing Required:** Interface consistency, registration reliability, capability detection
    - **Security Tests:** Provider spoofing, registration manipulation, capability bypass
    - **Negative Tests:** Interface corruption, registration failures, detection errors
    - _Requirements: 8.1_

  - [ ] 10.2 Write property test for LLM isolation
    - **Property 8: LLM Isolation**
    - **Validates: Requirements 17.9**
    - **Testing Required:** Isolation completeness, intent validation, authority routing
    - **Security Tests:** Isolation bypass, direct execution prevention, authority circumvention
    - **Negative Tests:** Corrupted isolation, invalid intents, routing failures
    - **Critical Invariant:** LLMs are advisory only, never authoritative - all intents must pass authority gates

### Phase 11: Audit and Compliance Systems
**Phase Philosophy:** Ensure complete transparency and auditability
**Phase Non-Goals:** No external audit sharing, no automatic compliance reporting

- [ ] 11. Implement comprehensive audit logging system
  - [ ] 11.1 Create cryptographically signed audit log foundation
    - Implement append-only log structure with cryptographic signatures
    - Create log entry schema with timestamps, context, and integrity fields
    - Add signature generation and verification using HMAC-SHA256
    - **Testing Required:** Log structure integrity, signature generation, verification accuracy
    - **Security Tests:** Log tampering attempts, signature forgery, integrity attacks
    - **Negative Tests:** Corrupted logs, invalid signatures, verification failures
    - _Requirements: 11.1, 11.2_

  - [ ] 11.2 Write property test for audit completeness
    - **Property 9: Audit Completeness**
    - **Validates: Requirements 1.6, 3.4, 17.8, 23.7, 25.9**
    - **Testing Required:** Event coverage, data integrity, completeness verification
    - **Security Tests:** Event evasion, log manipulation, integrity attacks
    - **Negative Tests:** Missing events, corrupted logs, incomplete coverage

### Phase 12: Mobile Agent Integration
**Phase Philosophy:** Extend secure control to mobile platform
**Phase Non-Goals:** No mobile-only features, no mobile data storage

- [ ] 12. Implement Android phone agent with secure communication
  - [ ] 12.1 Create Android project foundation with Jetpack Compose
    - Set up Android project structure with Kotlin and Jetpack Compose
    - Implement material design UI components and navigation
    - Add Android permissions handling and runtime permission requests
    - **Testing Required:** Project setup, UI functionality, permission handling
    - **Security Tests:** Permission bypass, UI injection, navigation manipulation
    - **Negative Tests:** Setup failures, UI corruption, permission errors
    - _Requirements: 1.1_

### Phase 13: Failure Handling and Recovery
**Phase Philosophy:** Ensure graceful degradation under all failure conditions
**Phase Non-Goals:** No automatic recovery, no silent failure handling

- [ ] 13. Implement comprehensive failure handling and safe degradation
  - [ ] 13.1 Create component failure detection system
    - Implement health monitoring for all core components
    - Add failure detection with immediate notification and logging
    - Create component dependency mapping and cascade failure prevention
    - **Testing Required:** Detection accuracy, notification reliability, cascade prevention
    - **Security Tests:** Detection evasion, notification manipulation, cascade exploitation
    - **Negative Tests:** Detection failures, notification corruption, cascade issues
    - _Requirements: 21.1_

  - [ ] 13.2 Write property test for failure safety
    - **Property 10: Failure Safety**
    - **Validates: Requirements 21.1, 21.2, 21.4**
    - **Testing Required:** All failure scenarios, safety guarantees, recovery mechanisms
    - **Security Tests:** Failure exploitation, safety bypass, recovery attacks
    - **Negative Tests:** Unsafe failures, corrupted recovery, degradation vulnerabilities

### Phase 14: User Interface and System Integration
**Phase Philosophy:** Provide transparent system control and monitoring
**Phase Non-Goals:** No complex UI features, no entertainment functions

- [ ] 14. Implement system tray interface and desktop integration
  - [ ] 14.1 Create Tauri-based system tray application
    - Set up Tauri project with Rust backend and web frontend
    - Implement system tray icon with context menu and status indicators
    - Add tray application lifecycle management and auto-startup
    - **Testing Required:** Tray functionality, menu reliability, lifecycle management
    - **Security Tests:** Tray injection, menu manipulation, lifecycle tampering
    - **Negative Tests:** Tray failures, menu corruption, lifecycle errors
    - _Requirements: 3.5_

### Phase 15: System Integration and Testing
**Phase Philosophy:** Validate complete system integration and interoperability
**Phase Non-Goals:** No performance optimization, no feature additions

- [ ] 15. Implement comprehensive system integration and end-to-end testing
  - [ ] 15.1 Create component integration and communication layer
    - Implement inter-component communication using secure message passing
    - Add component discovery and registration system
    - Create communication health monitoring and failure detection
    - **Testing Required:** Communication reliability, discovery accuracy, health monitoring
    - **Security Tests:** Communication interception, discovery manipulation, monitoring bypass
    - **Negative Tests:** Communication failures, discovery corruption, monitoring errors
    - _Requirements: All requirements integration_

### Phase 16: Deployment and CI/CD
**Phase Philosophy:** Enable reliable, secure deployment and updates
**Phase Non-Goals:** No automatic updates, no telemetry collection

- [ ] 16. Implement CI/CD pipeline and deployment automation
  - [ ] 16.1 Create GitHub Actions CI pipeline foundation
    - Set up GitHub Actions workflows for automated testing and building
    - Implement multi-platform build support (Windows, Android)
    - Add dependency caching and build optimization
    - **Testing Required:** Pipeline reliability, build accuracy, optimization effectiveness
    - **Security Tests:** Pipeline injection, build tampering, cache poisoning
    - **Negative Tests:** Pipeline failures, build corruption, optimization errors
    - _Requirements: 15.1_

### Phase 17: FINAL VALIDATION
**Phase Philosophy:** Ensure complete system meets all production standards
**Phase Non-Goals:** No new features, no scope expansion

- [ ] 17. **FINAL CHECKPOINT** - Ensure all tests pass and system is production-ready
  - **MANDATORY VALIDATION:** Complete system must meet all production standards
  - **ZERO-DEFECT CONFIRMATION:** All quality gates passed, no compromises accepted
  - Ensure all tests pass, ask the user if questions arise.

## MVP Definition (Core Security Foundation)

**Minimum Viable Product includes:**
- Authority State Machine with biometric verification
- Voice re-arming with speaker verification
- Cryptographically signed audit logging
- Basic input simulation with authority gating
- Intrusion detection with workstation locking

**MVP explicitly excludes:**
- Advanced skills (beyond basic input simulation)
- LLM integration (can be added post-MVP)
- Android agent (desktop-only for MVP)
- Advanced memory architecture
- Complex failure recovery

This MVP provides a complete, secure automation foundation that can be extended incrementally while maintaining all security invariants.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The implementation follows a **Zero-Defect Progression Policy**
- All code must meet **Human-Grade Code Standards**
- Security components are frozen after Task 6 (Security Checkpoint)
- The system uses modern cryptographic standards (AES-256, ECDSA-P256, Ed25519)
- All features use current, deployable technology
- No experimental or research-level features are included
- This represents a **production-grade secure personal automation system**

## Explicit Scope Boundaries

**What GURU IS:**
- A secure personal automation system using current technology
- Voice-driven input control with biometric authority verification
- Local-first processing with comprehensive audit logging
- Skill-based automation with sandboxing and permission controls

**What GURU IS NOT:**
- A quantum-resistant system (uses current cryptographic standards)
- A research platform for experimental cryptography
- A nation-state defense system
- A formal verification framework
- A blockchain or distributed ledger system

**Security Guarantees (Bounded, Not Absolute):**
- Defense against personal attackers and malware
- Protection against voice spoofing and replay attacks
- Mitigation of privilege escalation and unauthorized access
- Comprehensive audit logging for forensic analysis
- **NOT guaranteed against:** Nation-state actors, quantum computers, or advanced persistent threats

**Threat Model:**
- Personal attacker with physical access
- Malware on the host system
- Voice spoofing and audio injection
- Privilege escalation attempts
- Malicious skills and unauthorized automation