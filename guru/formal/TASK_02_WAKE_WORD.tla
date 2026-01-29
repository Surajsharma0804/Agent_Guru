---------------- MODULE TASK_02_WAKE_WORD ----------------
EXTENDS Naturals, Sequences

CONSTANTS AudioFrames, Threshold

VARIABLES 
    state,
    audioBuffer,
    predictionBuffer,
    detectionCount

States == {"Listening", "Detected", "Verified", "Suppressed"}

TypeOK == 
    /\ state \in States
    /\ audioBuffer \in Seq(AudioFrames)
    /\ predictionBuffer \in Seq(Nat)
    /\ detectionCount \in Nat

Init ==
    /\ state = "Listening"
    /\ audioBuffer = <<>>
    /\ predictionBuffer = <<>>
    /\ detectionCount = 0

ReceiveAudio(frame) ==
    /\ state = "Listening"
    /\ frame \in AudioFrames
    /\ audioBuffer' = Append(audioBuffer, frame)
    /\ UNCHANGED <<state, predictionBuffer, detectionCount>>

ProcessFrame(score) ==
    /\ state = "Listening"
    /\ score \in Nat
    /\ predictionBuffer' = Append(predictionBuffer, score)
    /\ IF score >= Threshold
       THEN state' = "Detected" /\ detectionCount' = detectionCount + 1
       ELSE UNCHANGED <<state, detectionCount>>
    /\ UNCHANGED audioBuffer

Verify ==
    /\ state = "Detected"
    /\ state' = "Verified"
    /\ UNCHANGED <<audioBuffer, predictionBuffer, detectionCount>>

Suppress ==
    /\ state = "Detected"
    /\ state' = "Suppressed"
    /\ UNCHANGED <<audioBuffer, predictionBuffer, detectionCount>>

Reset ==
    /\ state \in {"Verified", "Suppressed"}
    /\ state' = "Listening"
    /\ UNCHANGED <<audioBuffer, predictionBuffer, detectionCount>>

Next ==
    \/ \E f \in AudioFrames : ReceiveAudio(f)
    \/ \E s \in Nat : ProcessFrame(s)
    \/ Verify
    \/ Suppress
    \/ Reset

(* Safety: Detection count should be monotonic *)
DetectionMonotonic == detectionCount' >= detectionCount

================================================================
