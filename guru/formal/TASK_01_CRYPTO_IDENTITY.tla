---------------- MODULE TASK_01_CRYPTO_IDENTITY ----------------
EXTENDS Naturals, Sequences

CONSTANTS KeySpace, MaxMessages

VARIABLES 
    secretKey,
    publicKey,
    state,
    signatures,
    memoryState (* Models memory content for security *)

States == {"Uninitialized", "Generated", "Revoked"}

TypeOK == 
    /\ state \in States
    /\ secretKey \in KeySpace \cup {0}
    /\ publicKey \in KeySpace \cup {0}
    /\ signatures \subseteq KeySpace \X KeySpace
    /\ memoryState \in {"Clean", "Sensitive", "Zeroized"}

Init ==
    /\ state = "Uninitialized"
    /\ secretKey = 0
    /\ publicKey = 0
    /\ signatures = {}
    /\ memoryState = "Clean"

Generate(k) ==
    /\ state = "Uninitialized"
    /\ k \in KeySpace
    /\ secretKey' = k
    /\ publicKey' = k 
    /\ state' = "Generated"
    /\ memoryState' = "Sensitive"
    /\ signatures' = signatures

Sign(m) ==
    /\ state = "Generated"
    /\ memoryState = "Sensitive" (* Must have key in memory *)
    /\ m \in KeySpace
    /\ signatures' = signatures \cup {<<m, secretKey>>}
    /\ UNCHANGED <<secretKey, publicKey, state, memoryState>>

Revoke ==
    /\ state = "Generated"
    /\ state' = "Revoked"
    /\ secretKey' = 0
    /\ memoryState' = "Zeroized" (* Explicit Zeroize *)
    /\ UNCHANGED <<publicKey, signatures>>

Next ==
    \/ \E k \in KeySpace : Generate(k)
    \/ \E m \in KeySpace : Sign(m)
    \/ Revoke

(* Safety: If revoked, secret key must be zeroed *)
RevocationSafety == (state = "Revoked") => (secretKey = 0)

(* Memory Safety: Sensitive memory must eventually be zeroized after use (simplified as Revoke) *)
MemorySecure == (state = "Revoked") => (memoryState = "Zeroized")

================================================================
