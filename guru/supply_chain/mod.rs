// Copyright 2026 AGENT_GURU Contributors
// SPDX-License-Identifier: Apache-2.0

//! # Supply Chain Security and Attestation
//!
//! This module provides production-grade supply chain security capabilities
//! for the AGENT_GURU system. It implements comprehensive SBOM generation,
//! cryptographic attestation verification, and complete supply chain integrity
//! validation with mathematical guarantees.

pub mod attestation;
pub mod property_tests;

pub use attestation::{
    SbomGenerator, SoftwareBillOfMaterials, SoftwareComponent, ComponentId,
    LicenseInfo, VulnerabilityInfo, AttestationError, AttestationResult,
};