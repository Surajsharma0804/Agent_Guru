// Copyright 2026 AGENT_GURU Contributors
// SPDX-License-Identifier: Apache-2.0

//! # Build System and Provenance Tracking
//!
//! This module provides production-grade build system integration and provenance
//! tracking for the AGENT_GURU system. It implements comprehensive build
//! attestation, reproducible build verification, and complete supply chain
//! integrity validation.

pub mod provenance;
pub mod property_tests;

pub use provenance::{
    ProvenanceVerifier, ProvenanceGenerator, BuildProvenance, BuildArtifact,
    ArtifactRule, ProvenanceError, ProvenanceResult,
};