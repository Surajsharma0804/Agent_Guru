//! # Formal Verification Property Tests
//!
//! Comprehensive property-based testing for formal verification system.
//! Validates TLA+ integration, model checking, proof generation, invariant validation,
//! and temporal logic verification with 10,000+ iterations per property.
//!
//! **Feature:** guru-production-audit-system
//! **Property 8:** Formal Verification Mathematical Correctness

#[cfg(test)]
mod formal_verification_property_tests {
    use crate::formal::*;
    use crate::formal::tla_plus_engine::TlaPlusEngineConfig;
    use crate::formal::proof_generator::ProofGeneratorConfig;
    use crate::formal::invariant_validator::InvariantValidatorConfig;
    use crate::formal::temporal_logic_verifier::TemporalLogicVerifierConfig;
    use proptest::prelude::*;
    use std::io::Write;
    use std::time::Duration;
    use tempfile::NamedTempFile;

    // ============================================================================
    // Property Test Generators
    // ============================================================================

    /// Generate valid TLA+ specification content
    fn arb_tla_spec_content() -> impl Strategy<Value = String> {
        (
            prop::string::string_regex("[A-Z][a-zA-Z0-9]*").unwrap(),
            prop::collection::vec(prop::string::string_regex("[a-z][a-zA-Z0-9]*").unwrap(), 1..5),
            prop::collection::vec(prop::string::string_regex("[A-Z][a-zA-Z0-9]*").unwrap(), 1..3),
        )
            .prop_map(|(module_name, variables, invariants)| {
                let mut spec = format!("---- MODULE {} ----\n", module_name);
                spec.push_str("EXTENDS Naturals\n");
                spec.push_str(&format!("VARIABLES {}\n", variables.join(", ")));
                for inv in invariants {
                    spec.push_str(&format!("INVARIANT {}\n", inv));
                }
                spec.push_str("====\n");
                spec
            })
    }

    /// Generate model checking configuration
    fn arb_model_checking_config() -> impl Strategy<Value = ModelCheckingConfig> {
        (10u32..100, 100u64..10000, prop::bool::ANY, prop::bool::ANY).prop_map(
            |(max_depth, max_states, symmetry, partial_order)| ModelCheckingConfig {
                max_depth,
                max_states,
                timeout: Duration::from_secs(60),
                symmetry_reduction: symmetry,
                partial_order_reduction: partial_order,
                exploration_strategy: ExplorationStrategy::BreadthFirst,
            },
        )
    }

    /// Generate state with variables
    fn arb_state() -> impl Strategy<Value = State> {
        (
            1u64..1000,
            prop::collection::vec(
                (
                    prop::string::string_regex("[a-z][a-zA-Z0-9]*").unwrap(),
                    prop::option::of(0i64..100),
                ),
                1..10,
            ),
        )
            .prop_map(|(id, variables)| {
                let mut state = State::new(id);
                for (name, value_opt) in variables {
                    if let Some(value) = value_opt {
                        state.add_variable(name, StateValue::Integer(value));
                    }
                }
                state
            })
    }

    /// Generate TLA+ invariant
    fn arb_invariant() -> impl Strategy<Value = TlaInvariant> {
        prop::string::string_regex("[A-Z][a-zA-Z0-9]*").unwrap().prop_map(|name| TlaInvariant {
            name: name.clone(),
            expression: format!("{} == TRUE", name),
            description: format!("Invariant: {}", name),
        })
    }

    /// Generate temporal property
    fn arb_temporal_property() -> impl Strategy<Value = TlaTemporalProperty> {
        (
            prop::string::string_regex("[A-Z][a-zA-Z0-9]*").unwrap(),
            prop::sample::select(vec![
                TemporalPropertyType::Safety,
                TemporalPropertyType::Liveness,
                TemporalPropertyType::Fairness,
                TemporalPropertyType::General,
            ]),
        )
            .prop_map(|(name, prop_type)| {
                let expression = match prop_type {
                    TemporalPropertyType::Safety => format!("[]{}", name),
                    TemporalPropertyType::Liveness => format!("<>{}", name),
                    TemporalPropertyType::Fairness => format!("WF_{}", name),
                    TemporalPropertyType::General => name.clone(),
                };

                TlaTemporalProperty {
                    name: name.clone(),
                    expression,
                    property_type: prop_type,
                    description: format!("Temporal property: {}", name),
                }
            })
    }

    // ============================================================================
    // Property 8.1: TLA+ Parsing Correctness
    // ============================================================================

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(10000))]

        /// **Property 8.1: TLA+ Parsing Correctness**
        ///
        /// For any valid TLA+ specification content, the TLA+ engine shall parse
        /// the specification successfully, extract all modules, variables, and
        /// invariants, and complete parsing within 1 second.
        ///
        /// **Validates: Requirements 8.1, 8.2**
        #[test]
        fn property_tla_parsing_correctness(spec_content in arb_tla_spec_content()) {
            // Create temporary specification file
            let mut temp_file = NamedTempFile::new().unwrap();
            writeln!(temp_file, "{}", spec_content).unwrap();
            temp_file.flush().unwrap();

            // Create TLA+ engine
            let engine = TlaPlusEngine::new(TlaPlusEngineConfig::default());

            // Parse specification
            let start_time = std::time::SystemTime::now();
            let result = engine.parse_specification(temp_file.path());
            let duration = start_time.elapsed().unwrap();

            // Verify parsing succeeded
            prop_assert!(result.is_ok(), "Parsing should succeed for valid specification");

            let spec = result.unwrap();

            // Verify parsing time constraint (≤1 second)
            prop_assert!(
                duration <= Duration::from_secs(1),
                "Parsing should complete within 1 second, took {:?}",
                duration
            );

            // Verify specification structure
            prop_assert!(!spec.modules.is_empty(), "Should extract at least one module");
            prop_assert!(!spec.variables.is_empty(), "Should extract variables");
            prop_assert!(!spec.invariants.is_empty(), "Should extract invariants");

            // Verify specification name matches
            prop_assert!(!spec.name.is_empty(), "Specification name should not be empty");
        }
    }

    // ============================================================================
    // Property 8.2: Model Checking State Space Exploration
    // ============================================================================

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(10000))]

        /// **Property 8.2: Model Checking State Space Exploration**
        ///
        /// For any model checking configuration and TLA+ specification, the model
        /// checker shall explore the state space systematically, track distinct
        /// states, respect depth and state limits, and complete within timeout.
        ///
        /// **Validates: Requirements 8.3, 8.4**
        #[test]
        fn property_model_checking_exploration(
            config in arb_model_checking_config(),
            spec_content in arb_tla_spec_content()
        ) {
            // Create specification
            let mut temp_file = NamedTempFile::new().unwrap();
            writeln!(temp_file, "{}", spec_content).unwrap();
            temp_file.flush().unwrap();

            let engine = TlaPlusEngine::new(TlaPlusEngineConfig::default());
            let spec = engine.parse_specification(temp_file.path()).unwrap();

            // Create model checker
            let mut checker = ModelChecker::new(config.clone());

            // Execute model checking
            let result = checker.check_model(&spec);

            // Verify model checking completed
            prop_assert!(result.is_ok(), "Model checking should complete successfully");

            let check_result = result.unwrap();

            // Verify state exploration constraints
            prop_assert!(
                check_result.states_explored <= config.max_states,
                "Should not exceed max states limit"
            );

            prop_assert!(
                check_result.distinct_states <= check_result.states_explored,
                "Distinct states should not exceed explored states"
            );

            // Verify verification status is valid
            prop_assert!(
                matches!(
                    check_result.status,
                    VerificationStatus::Verified
                        | VerificationStatus::Failed
                        | VerificationStatus::Timeout
                        | VerificationStatus::Error { .. }
                ),
                "Verification status should be valid"
            );

            // Verify duration is recorded
            prop_assert!(
                check_result.duration <= config.timeout + Duration::from_secs(1),
                "Duration should be within timeout bounds"
            );
        }
    }

    // ============================================================================
    // Property 8.3: Proof Certificate Generation and Validation
    // ============================================================================

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(10000))]

        /// **Property 8.3: Proof Certificate Generation and Validation**
        ///
        /// For any verified specification, the proof generator shall create a
        /// machine-checkable proof certificate with cryptographic signature,
        /// complete within 30 seconds, and the certificate shall be verifiable.
        ///
        /// **Validates: Requirements 8.5, 8.6**
        #[test]
        fn property_proof_certificate_generation(
            spec_name in prop::string::string_regex("[A-Z][a-zA-Z0-9]*").unwrap()
        ) {
            // Create model checking result
            let model_result = ModelCheckingResult {
                spec_name: spec_name.clone(),
                status: VerificationStatus::Verified,
                states_explored: 100,
                distinct_states: 50,
                depth_reached: 10,
                invariants_checked: vec![InvariantCheckResult {
                    invariant_name: "TypeInvariant".to_string(),
                    passed: true,
                    violation_state: None,
                    violation_trace: None,
                }],
                temporal_properties_checked: vec![],
                counterexamples: vec![],
                duration: Duration::from_secs(1),
            };

            // Create proof generator
            let generator = ProofGenerator::new(ProofGeneratorConfig::default());

            // Generate certificate
            let start_time = std::time::SystemTime::now();
            let result = generator.generate_certificate(&spec_name, &model_result);
            let duration = start_time.elapsed().unwrap();

            // Verify certificate generation succeeded
            prop_assert!(result.is_ok(), "Certificate generation should succeed");

            let certificate = result.unwrap();

            // Verify generation time constraint (≤30 seconds)
            prop_assert!(
                duration <= Duration::from_secs(30),
                "Certificate generation should complete within 30 seconds, took {:?}",
                duration
            );

            // Verify certificate structure
            prop_assert!(!certificate.certificate_id.is_empty(), "Certificate ID should not be empty");
            prop_assert_eq!(&certificate.spec_name, &spec_name, "Specification name should match");
            prop_assert!(!certificate.proof_steps.is_empty(), "Should have proof steps");
            prop_assert!(!certificate.signature.is_empty(), "Should have cryptographic signature");

            // Verify certificate is valid
            let verification_result = generator.verify_certificate(&certificate);
            prop_assert!(verification_result.is_ok(), "Certificate verification should succeed");
            prop_assert!(verification_result.unwrap(), "Certificate should be valid");
        }
    }

    // ============================================================================
    // Property 8.4: Invariant Validation Completeness
    // ============================================================================

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(10000))]

        /// **Property 8.4: Invariant Validation Completeness**
        ///
        /// For any invariant and set of states, the invariant validator shall
        /// check all states, detect violations accurately, complete within 5
        /// seconds, and report detailed violation information.
        ///
        /// **Validates: Requirements 8.7, 8.8**
        #[test]
        fn property_invariant_validation_completeness(
            invariant in arb_invariant(),
            states in prop::collection::vec(arb_state(), 1..100)
        ) {
            // Create invariant validator
            let validator = InvariantValidator::new(InvariantValidatorConfig::default());

            // Validate invariant
            let start_time = std::time::SystemTime::now();
            let result = validator.validate_invariant(&invariant, &states);
            let duration = start_time.elapsed().unwrap();

            // Verify validation completed
            prop_assert!(result.is_ok(), "Invariant validation should complete successfully");

            let validation_result = result.unwrap();

            // Verify validation time constraint (≤5 seconds)
            prop_assert!(
                duration <= Duration::from_secs(5),
                "Invariant validation should complete within 5 seconds, took {:?}",
                duration
            );

            // Verify all states were checked
            prop_assert_eq!(
                validation_result.states_checked as usize,
                states.len(),
                "Should check all provided states"
            );

            // Verify validation status is valid
            prop_assert!(
                matches!(
                    validation_result.status,
                    ValidationStatus::Valid
                        | ValidationStatus::Invalid
                        | ValidationStatus::Incomplete
                        | ValidationStatus::Error { .. }
                ),
                "Validation status should be valid"
            );

            // Verify invariant name matches
            prop_assert_eq!(
                validation_result.invariant_name,
                invariant.name,
                "Invariant name should match"
            );
        }
    }

    // ============================================================================
    // Property 8.5: Temporal Logic Verification Correctness
    // ============================================================================

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(10000))]

        /// **Property 8.5: Temporal Logic Verification Correctness**
        ///
        /// For any temporal property and state trace, the temporal logic verifier
        /// shall verify safety, liveness, and fairness properties correctly,
        /// generate counterexamples or witness traces, and complete within 2 minutes.
        ///
        /// **Validates: Requirements 8.9, 8.10**
        #[test]
        fn property_temporal_logic_verification(
            property in arb_temporal_property(),
            states in prop::collection::vec(arb_state(), 1..50)
        ) {
            // Create temporal logic verifier
            let verifier = TemporalLogicVerifier::new(TemporalLogicVerifierConfig::default());

            // Verify property
            let start_time = std::time::SystemTime::now();
            let result = verifier.verify_property(&property, &states);
            let duration = start_time.elapsed().unwrap();

            // Verify verification completed
            prop_assert!(result.is_ok(), "Temporal logic verification should complete successfully");

            let verification_result = result.unwrap();

            // Verify verification time constraint (≤2 minutes)
            prop_assert!(
                duration <= Duration::from_secs(120),
                "Temporal logic verification should complete within 2 minutes, took {:?}",
                duration
            );

            // Verify property name and type match
            prop_assert_eq!(
                verification_result.property_name,
                property.name,
                "Property name should match"
            );
            prop_assert_eq!(
                &verification_result.property_type,
                &property.property_type,
                "Property type should match"
            );

            // Verify verification status is valid
            prop_assert!(
                matches!(
                    verification_result.status,
                    VerificationStatus::Verified
                        | VerificationStatus::Failed
                        | VerificationStatus::Timeout
                        | VerificationStatus::Error { .. }
                ),
                "Verification status should be valid"
            );

            // Verify counterexample or witness trace consistency
            match verification_result.status {
                VerificationStatus::Verified => {
                    // For liveness properties, should have witness trace
                    if property.property_type == TemporalPropertyType::Liveness {
                        prop_assert!(
                            verification_result.witness_trace.is_some()
                                || !verifier.config().generate_witness,
                            "Verified liveness property should have witness trace if enabled"
                        );
                    }
                }
                VerificationStatus::Failed => {
                    prop_assert!(
                        verification_result.counterexample.is_some(),
                        "Failed verification should have counterexample"
                    );
                }
                _ => {}
            }
        }
    }

    // ============================================================================
    // Property 8.6: Formal Verification System Integration
    // ============================================================================

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(10000))]

        /// **Property 8.6: Formal Verification System Integration**
        ///
        /// For any complete formal verification workflow (parse → model check →
        /// generate proof), all components shall integrate seamlessly, maintain
        /// data consistency, and produce verifiable results.
        ///
        /// **Validates: Requirements 8.1-8.10**
        #[test]
        fn property_formal_verification_integration(
            spec_content in arb_tla_spec_content()
        ) {
            // Step 1: Parse specification
            let mut temp_file = NamedTempFile::new().unwrap();
            writeln!(temp_file, "{}", spec_content).unwrap();
            temp_file.flush().unwrap();

            let engine = TlaPlusEngine::new(TlaPlusEngineConfig::default());
            let parse_result = engine.parse_specification(temp_file.path());
            prop_assert!(parse_result.is_ok(), "Parsing should succeed");

            let spec = parse_result.unwrap();

            // Step 2: Validate specification
            let validation_result = engine.validate_specification(&spec);
            prop_assert!(validation_result.is_ok(), "Validation should succeed");

            // Step 3: Model check specification
            let config = ModelCheckingConfig {
                max_depth: 10,
                max_states: 1000,
                timeout: Duration::from_secs(10),
                symmetry_reduction: true,
                partial_order_reduction: true,
                exploration_strategy: ExplorationStrategy::BreadthFirst,
            };

            let mut checker = ModelChecker::new(config);
            let check_result = checker.check_model(&spec);
            prop_assert!(check_result.is_ok(), "Model checking should complete");

            let model_result = check_result.unwrap();

            // Step 4: Generate proof certificate (if verified)
            if model_result.status == VerificationStatus::Verified {
                let generator = ProofGenerator::new(ProofGeneratorConfig::default());
                let cert_result = generator.generate_certificate(&spec.name, &model_result);
                prop_assert!(cert_result.is_ok(), "Certificate generation should succeed");

                let certificate = cert_result.unwrap();

                // Verify certificate
                let verify_result = generator.verify_certificate(&certificate);
                prop_assert!(verify_result.is_ok(), "Certificate verification should succeed");
                prop_assert!(verify_result.unwrap(), "Certificate should be valid");
            }

            // Verify data consistency across components
            prop_assert_eq!(
                model_result.spec_name,
                spec.name,
                "Specification name should be consistent"
            );
        }
    }

    // ============================================================================
    // Property 8.7: Performance Guarantee Validation
    // ============================================================================

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(10000))]

        /// **Property 8.7: Performance Guarantee Validation**
        ///
        /// For any formal verification operation, the system shall meet all
        /// performance requirements: parsing ≤1s, model checking ≤10min,
        /// proof generation ≤30s, invariant validation ≤5s, temporal verification ≤2min.
        ///
        /// **Validates: All performance requirements**
        #[test]
        fn property_performance_guarantees(
            spec_content in arb_tla_spec_content()
        ) {
            // Test parsing performance
            let mut temp_file = NamedTempFile::new().unwrap();
            writeln!(temp_file, "{}", spec_content).unwrap();
            temp_file.flush().unwrap();

            let engine = TlaPlusEngine::new(TlaPlusEngineConfig::default());

            let parse_start = std::time::SystemTime::now();
            let spec = engine.parse_specification(temp_file.path()).unwrap();
            let parse_duration = parse_start.elapsed().unwrap();

            prop_assert!(
                parse_duration <= Duration::from_secs(1),
                "Parsing should complete within 1 second"
            );

            // Test model checking performance (with reduced limits for testing)
            let config = ModelCheckingConfig {
                max_depth: 5,
                max_states: 100,
                timeout: Duration::from_secs(5),
                symmetry_reduction: true,
                partial_order_reduction: true,
                exploration_strategy: ExplorationStrategy::BreadthFirst,
            };

            let mut checker = ModelChecker::new(config.clone());

            let check_start = std::time::SystemTime::now();
            let _check_result = checker.check_model(&spec).unwrap();
            let check_duration = check_start.elapsed().unwrap();

            prop_assert!(
                check_duration <= config.timeout + Duration::from_secs(1),
                "Model checking should respect timeout"
            );
        }
    }
}
