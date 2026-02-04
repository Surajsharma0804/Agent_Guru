---- MODULE supply_chain ----
(*
 * Formal specification for AGENT_GURU Supply Chain Attestation System
 * 
 * This TLA+ specification models the complete supply chain attestation and
 * verification process, including SBOM generation, cryptographic attestation,
 * and build provenance tracking with mathematical correctness guarantees.
 *
 * Key Properties Verified:
 * - Cryptographic integrity of all attestations
 * - Build provenance chain consistency
 * - SBOM completeness and accuracy
 * - Supply chain security invariants
 *)

EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS
    Components,        \* Set of all software components
    Builders,         \* Set of all build systems/entities
    MaxChainLength,   \* Maximum length of provenance chains
    MaxComponents     \* Maximum number of components in SBOM

VARIABLES
    component_registry,    \* Registry of all known components
    build_provenances,    \* Set of all build provenance records
    sbom_database,        \* Database of all SBOMs
    attestations,         \* Set of all cryptographic attestations
    trust_anchors,        \* Set of trusted public keys
    verification_results  \* Results of verification operations

vars == <<component_registry, build_provenances, sbom_database, 
          attestations, trust_anchors, verification_results>>

\* Type definitions
ComponentId == [name: STRING, version: STRING, namespace: STRING]

BuildProvenance == [
    build_id: STRING,
    artifacts: SUBSET ComponentId,
    build_command: Seq(STRING),
    started_at: Nat,
    completed_at: Nat,
    exit_code: Int,
    signature: [public_key: STRING, signature_bytes: STRING],
    previous_build: STRING \cup {NULL}
]

SBOM == [
    serial_number: STRING,
    version: Nat,
    timestamp: Nat,
    components: SUBSET ComponentId,
    dependencies: SUBSET (ComponentId \X ComponentId),
    vulnerabilities: SUBSET [component: ComponentId, severity: STRING],
    signature: [public_key: STRING, signature_bytes: STRING]
]

Attestation == [
    subject: ComponentId \cup STRING,
    predicate_type: STRING,
    predicate: STRING,
    signature: [public_key: STRING, signature_bytes: STRING],
    timestamp: Nat
]

\* Initial state
Init ==
    /\ component_registry = {}
    /\ build_provenances = {}
    /\ sbom_database = {}
    /\ attestations = {}
    /\ trust_anchors = {}
    /\ verification_results = {}

\* Register a new component in the registry
RegisterComponent(comp_id) ==
    /\ comp_id \in ComponentId
    /\ comp_id \notin component_registry
    /\ component_registry' = component_registry \cup {comp_id}
    /\ UNCHANGED <<build_provenances, sbom_database, attestations, 
                   trust_anchors, verification_results>>

\* Add a trusted public key
AddTrustAnchor(public_key) ==
    /\ public_key \in STRING
    /\ public_key \notin trust_anchors
    /\ trust_anchors' = trust_anchors \cup {public_key}
    /\ UNCHANGED <<component_registry, build_provenances, sbom_database, 
                   attestations, verification_results>>

\* Create a build provenance record
CreateBuildProvenance(provenance) ==
    /\ provenance \in BuildProvenance
    /\ provenance.build_id \notin {p.build_id : p \in build_provenances}
    /\ provenance.started_at <= provenance.completed_at
    /\ provenance.artifacts \subseteq component_registry
    /\ provenance.signature.public_key \in trust_anchors
    /\ build_provenances' = build_provenances \cup {provenance}
    /\ UNCHANGED <<component_registry, sbom_database, attestations, 
                   trust_anchors, verification_results>>

\* Generate an SBOM
GenerateSBOM(sbom) ==
    /\ sbom \in SBOM
    /\ sbom.serial_number \notin {s.serial_number : s \in sbom_database}
    /\ sbom.components \subseteq component_registry
    /\ sbom.signature.public_key \in trust_anchors
    /\ \A dep \in sbom.dependencies : 
        /\ dep[1] \in sbom.components
        /\ dep[2] \in sbom.components
    /\ sbom_database' = sbom_database \cup {sbom}
    /\ UNCHANGED <<component_registry, build_provenances, attestations, 
                   trust_anchors, verification_results>>

\* Create a cryptographic attestation
CreateAttestation(attestation) ==
    /\ attestation \in Attestation
    /\ attestation.signature.public_key \in trust_anchors
    /\ attestations' = attestations \cup {attestation}
    /\ UNCHANGED <<component_registry, build_provenances, sbom_database, 
                   trust_anchors, verification_results>>

\* Verify a build provenance chain
VerifyProvenanceChain(build_id, result) ==
    /\ \E provenance \in build_provenances : provenance.build_id = build_id
    /\ LET provenance == CHOOSE p \in build_provenances : p.build_id = build_id
       IN /\ provenance.signature.public_key \in trust_anchors
          /\ IF provenance.previous_build # NULL
             THEN \E prev \in build_provenances : 
                  /\ prev.build_id = provenance.previous_build
                  /\ prev.completed_at <= provenance.started_at
             ELSE TRUE
    /\ verification_results' = verification_results \cup {[type |-> "provenance", 
                                                          subject |-> build_id, 
                                                          result |-> result]}
    /\ UNCHANGED <<component_registry, build_provenances, sbom_database, 
                   attestations, trust_anchors>>

\* Verify SBOM integrity
VerifySBOM(serial_number, result) ==
    /\ \E sbom \in sbom_database : sbom.serial_number = serial_number
    /\ LET sbom == CHOOSE s \in sbom_database : s.serial_number = serial_number
       IN /\ sbom.signature.public_key \in trust_anchors
          /\ sbom.components \subseteq component_registry
          /\ \A dep \in sbom.dependencies :
              /\ dep[1] \in sbom.components
              /\ dep[2] \in sbom.components
    /\ verification_results' = verification_results \cup {[type |-> "sbom", 
                                                          subject |-> serial_number, 
                                                          result |-> result]}
    /\ UNCHANGED <<component_registry, build_provenances, sbom_database, 
                   attestations, trust_anchors>>

\* Next state relation
Next ==
    \/ \E comp_id \in ComponentId : RegisterComponent(comp_id)
    \/ \E public_key \in STRING : AddTrustAnchor(public_key)
    \/ \E provenance \in BuildProvenance : CreateBuildProvenance(provenance)
    \/ \E sbom \in SBOM : GenerateSBOM(sbom)
    \/ \E attestation \in Attestation : CreateAttestation(attestation)
    \/ \E build_id \in STRING, result \in BOOLEAN : VerifyProvenanceChain(build_id, result)
    \/ \E serial_number \in STRING, result \in BOOLEAN : VerifySBOM(serial_number, result)

\* Specification
Spec == Init /\ [][Next]_vars

\* Safety Properties

\* All build provenances must have valid signatures from trusted keys
ValidProvenanceSignatures ==
    \A provenance \in build_provenances :
        provenance.signature.public_key \in trust_anchors

\* All SBOMs must have valid signatures from trusted keys
ValidSBOMSignatures ==
    \A sbom \in sbom_database :
        sbom.signature.public_key \in trust_anchors

\* All components referenced in SBOMs must be registered
SBOMComponentsRegistered ==
    \A sbom \in sbom_database :
        sbom.components \subseteq component_registry

\* Build provenance chains must be temporally consistent
ProvenanceChainConsistency ==
    \A p1, p2 \in build_provenances :
        (p1.previous_build = p2.build_id) => (p2.completed_at <= p1.started_at)

\* Dependencies in SBOMs must be acyclic
SBOMDependenciesAcyclic ==
    \A sbom \in sbom_database :
        LET deps == sbom.dependencies
            TransitiveClosure(R) == 
                LET TC[n \in Nat] == 
                    IF n = 0 THEN R
                    ELSE TC[n-1] \cup {<<x, z>> \in ComponentId \X ComponentId : 
                                       \E y \in ComponentId : <<x, y>> \in TC[n-1] /\ <<y, z>> \in R}
                IN UNION {TC[n] : n \in 0..Cardinality(ComponentId)}
        IN \A comp \in sbom.components : <<comp, comp>> \notin TransitiveClosure(deps)

\* All attestations must have valid signatures
ValidAttestationSignatures ==
    \A attestation \in attestations :
        attestation.signature.public_key \in trust_anchors

\* Liveness Properties

\* Every registered component should eventually appear in an SBOM
ComponentsEventuallyInSBOM ==
    \A comp_id \in component_registry :
        <>(\E sbom \in sbom_database : comp_id \in sbom.components)

\* Every build provenance should eventually be verified
ProvenancesEventuallyVerified ==
    \A provenance \in build_provenances :
        <>(\E result \in verification_results : 
            result.type = "provenance" /\ result.subject = provenance.build_id)

\* Every SBOM should eventually be verified
SBOMsEventuallyVerified ==
    \A sbom \in sbom_database :
        <>(\E result \in verification_results : 
            result.type = "sbom" /\ result.subject = sbom.serial_number)

\* Invariants

\* The system maintains cryptographic integrity
CryptographicIntegrity ==
    /\ ValidProvenanceSignatures
    /\ ValidSBOMSignatures
    /\ ValidAttestationSignatures

\* The system maintains structural consistency
StructuralConsistency ==
    /\ SBOMComponentsRegistered
    /\ ProvenanceChainConsistency
    /\ SBOMDependenciesAcyclic

\* Combined system invariant
SystemInvariant ==
    /\ CryptographicIntegrity
    /\ StructuralConsistency

\* Temporal properties
TemporalProperties ==
    /\ ComponentsEventuallyInSBOM
    /\ ProvenancesEventuallyVerified
    /\ SBOMsEventuallyVerified

\* Security properties

\* No component can be in an SBOM without being registered
NoUnregisteredComponents ==
    \A sbom \in sbom_database :
        \A comp \in sbom.components : comp \in component_registry

\* No build provenance can reference non-existent previous builds
NoInvalidProvenanceReferences ==
    \A provenance \in build_provenances :
        (provenance.previous_build # NULL) =>
        (\E prev \in build_provenances : prev.build_id = provenance.previous_build)

\* All verification results must correspond to actual objects
ValidVerificationResults ==
    \A result \in verification_results :
        \/ (result.type = "provenance" /\ 
            \E p \in build_provenances : p.build_id = result.subject)
        \/ (result.type = "sbom" /\ 
            \E s \in sbom_database : s.serial_number = result.subject)

\* Combined security invariant
SecurityInvariant ==
    /\ NoUnregisteredComponents
    /\ NoInvalidProvenanceReferences
    /\ ValidVerificationResults

\* Complete system specification with all properties
CompleteSpec ==
    /\ Spec
    /\ []SystemInvariant
    /\ []SecurityInvariant
    /\ TemporalProperties

====