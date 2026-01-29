---------------- MODULE TASK_01_CRYPTO_IDENTITY ----------------
EXTENDS Naturals, Sequences

CONSTANTS KeySpace, MaxMessages

VARIABLES 
    secretKey,
    publicKey,
    state,
    signatures

States == {"Uninitialized", "Generated", "Revoked"}

TypeOK == 
    /\ state \in States
    /\ secretKey \in KeySpace \cup {0}
    /\ publicKey \in KeySpace \cup {0}
    /\ signatures \subseteq KeySpace \X KeySpace

Init ==
    /\ state = "Uninitialized"
    /\ secretKey = 0
    /\ publicKey = 0
    /\ signatures = {}

Generate(k) ==
    /\ state = "Uninitialized"
    /\ k \in KeySpace
    /\ secretKey' = k
    /\ publicKey' = k (* Simplified mapping sk->pk *)
    /\ state' = "Generated"
    /\ signatures' = signatures

Sign(m) ==
    /\ state = "Generated"
    /\ m \in KeySpace
    /\ signatures' = signatures \cup {<<m, secretKey>>}
    /\ UNCHANGED <<secretKey, publicKey, state>>

Revoke ==
    /\ state = "Generated"
    /\ state' = "Revoked"
    /\ secretKey' = 0 (* Key destruction *)
    /\ UNCHANGED <<publicKey, signatures>> (* PK and Sigs remain valid verification-wise? Or revoked? *)

Next ==
    \/ \E k \in KeySpace : Generate(k)
    \/ \E m \in KeySpace : Sign(m)
    \/ Revoke

(* Safety: If revoked, secret key must be zeroed *)
RevocationSafety == (state = "Revoked") => (secretKey = 0)

================================================================
