//! # Formal Verification Module
//!
//! Complete formal verification engine with TLA+ integration, model checking,
//! proof generation, invariant validation, and temporal logic verification.
//!
//! This module implements mathematical correctness guarantees through formal methods,
//! providing civilization-scale software verification for 20+ years of operational lifetime.

pub mod tla_plus_engine;
pub mod model_checker;
pub mod proof_generator;
pub mod invariant_validator;
pub mod temporal_logic_verifier;
pub mod types;
pub mod property_tests;

pub use tla_plus_engine::TlaPlusEngine;
pub use model_checker::ModelChecker;
pub use proof_generator::ProofGenerator;
pub use invariant_validator::InvariantValidator;
pub use temporal_logic_verifier::TemporalLogicVerifier;
pub use types::*;
