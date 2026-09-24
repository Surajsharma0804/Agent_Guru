"""Comprehensive test suite for Agent Guru spec alignment modules."""
import sys
import pathlib
import tempfile

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}: {detail}")


print("=" * 60)
print("AGENT GURU - COMPREHENSIVE VERIFICATION")
print("=" * 60)

# --- 1. Reaction Rules ---
print("\n--- Reaction Rules ---")
from Agent_Guru.platform.features.reaction_rules import extract_teaching_intent, ReactionRuleStore

t1 = extract_teaching_intent("jab main bolu thak gaya tu bolna aaram kar le bhai")
test("Hindi teaching (anchor+connector)", t1 is not None and "thak gaya" in t1[0].lower())

t2 = extract_teaching_intent("when I say good morning you say rise and shine")
test("English teaching (anchor+connector)", t2 is not None and "good morning" in t2[0].lower())

t3 = extract_teaching_intent("bol de usko")
test("Bare connector rejected", t3 is None)

t4 = extract_teaching_intent("open Chrome")
test("Non-teaching phrase rejected", t4 is None)

store = ReactionRuleStore(path=pathlib.Path(tempfile.mktemp(suffix=".json")))
ok, msg = store.add_rule("thak gaya", "aaram kar le bhai")
test("add_rule succeeds", ok, msg)

result = store.match("thak gaya")
test("Exact match works", result == "aaram kar le bhai", str(result))

result2 = store.match("bro thak gaya yaar")
test("Substring match works", result2 == "aaram kar le bhai", str(result2))

result3 = store.match("hello there")
test("Non-match returns None", result3 is None)

# --- 2. User Memory ---
print("\n--- User Memory ---")
from Agent_Guru.platform.features.user_memory import extract_user_fact, UserMemory

f1 = extract_user_fact("call me Chotu")
test("Nickname: call me -> nickname", f1 == ("nickname", "Chotu"), str(f1))

f2 = extract_user_fact("my name is Suraj")
test("Name: my name is -> name", f2 == ("name", "Suraj"), str(f2))

f3 = extract_user_fact("talk to me in English only")
test("Code mixing: English only", f3 == ("code_mixing", "english"), str(f3))

f4 = extract_user_fact("hinglish mein baat kar")
test("Code mixing: Hinglish (Hindi phrased)", f4 is not None and f4[0] == "code_mixing", str(f4))

f4b = extract_user_fact("talk in hinglish")
test("Code mixing: Hinglish (English phrased)", f4b == ("code_mixing", "hinglish"), str(f4b))

f5 = extract_user_fact("remember that my exam is on Monday")
test("Remember custom fact", f5 is not None and f5[0].startswith("custom_fact_"), str(f5))

f6 = extract_user_fact("forget that my exam is on Monday")
test("Forget command", f6 is not None and f6[0] == "__forget__", str(f6))

f7 = extract_user_fact("I live in Delhi")
test("Location extraction", f7 == ("location", "Delhi"), str(f7))

f8 = extract_user_fact("I am 22 years old")
test("Age extraction", f8 == ("age", "22"), str(f8))

f9 = extract_user_fact("my hobby is coding")
test("Hobby extraction", f9 == ("hobbies", "coding"), str(f9))

# Pinned keys
mem = UserMemory(path=pathlib.Path(tempfile.mktemp(suffix=".json")))
mem.set("name", "Suraj")
mem.set("nickname", "Chotu")
test("Pinned key: name persists", mem.get("name") == "Suraj")
test("Pinned key: nickname persists", mem.get("nickname") == "Chotu")

# --- 3. Confirmation ---
print("\n--- Confirmation ---")
from Agent_Guru.platform.features.confirmation import is_destructive_action

test("delete_file is destructive", is_destructive_action("delete_file"))
test("shutdown is destructive", is_destructive_action("shutdown"))
test("restart is destructive", is_destructive_action("restart"))
test("open_app is NOT destructive", not is_destructive_action("open_app"))
test("play_music is NOT destructive", not is_destructive_action("play_music"))

# --- 4. Speaker Verifier ---
print("\n--- Speaker Verifier ---")
from Agent_Guru.speech.biometric.speaker_verifier import SpeakerVerifier

v = SpeakerVerifier(profile_path=pathlib.Path(tempfile.mktemp(suffix=".npz")))
test("Not enrolled by default", not v.is_enrolled())
r = v.verify(None)
test("Default mode is full (no enrollment)", r.mode == "full")

# --- 5. Filler Response ---
print("\n--- Filler Response ---")
from Agent_Guru.speech.filler_response import FillerResponseCache

fc = FillerResponseCache()
test("FillerResponseCache instantiates", fc is not None)
test("Not initialized by default", not fc._initialized)

# --- 6. Companion Prompts ---
print("\n--- Companion Prompts ---")
from Agent_Guru.llm.companion_prompts import (
    build_companion_prompt,
    build_crisis_block,
    detect_crisis_language,
)

p1 = build_companion_prompt("guru", nickname="Chotu", code_mixing="english")
test("Nickname injected", "Chotu" in p1)
test("English override injected", "PURE ENGLISH" in p1)

p2 = build_companion_prompt("guru", code_mixing="hinglish")
test("Hinglish default (no override)", "PURE ENGLISH" not in p2)
test("Hinglish section in base prompt", "HINGLISH" in p2)

p3 = build_companion_prompt("maya", emotion_hint="frustrated")
test("Emotion hint injected", "frustrated" in p3.lower())
test("Maya personality used", "Maya" in p3)

# These two checks used to call build_companion_prompt(emotion_hint="suicidal")
# and look for the crisis text in the result. That stopped passing when
# companion_prompts 2.2.0 removed the per-turn crisis tier -- correctly, since
# it keyed off emotion labels ("suicidal", "hopeless") that EmotionDetector
# never emits, so it could not fire in production no matter what this check
# said. The behaviour has not been dropped; it moved to a check on the
# TRANSCRIPT, which is what a user in crisis actually gives you. The
# assertions are therefore made against the real path rather than deleted,
# and they are stronger than before: they now exercise something that can
# genuinely happen on turn one.
test("Crisis language detected from the transcript",
     detect_crisis_language("I want to kill myself"))
test("Crisis detection covers Hinglish (this product's default register)",
     detect_crisis_language("mujhe marna chahta hoon"))
test("Ordinary commands do not trigger it",
     not detect_crisis_language("kill the process on port 8080"))
p4 = build_crisis_block("IN")
test("Crisis emotion triggers deep support", "CRITICAL EMOTION" in p4)
test("Crisis response present", "DEEPLY present" in p4 or "distress" in p4)
test("Crisis response names a real helpline", "KIRAN" in p4)

p5 = build_companion_prompt("guru")
test("Anti-manipulation guardrails", "ETHICS" in p5)
test("Forbidden phrases warning", "I missed you" in p5)

# --- 7. Orchestrator ---
print("\n--- Orchestrator Structure ---")
from Agent_Guru.integration.orchestrator import IntegrationOrchestrator
import inspect

test("IntegrationOrchestrator exists", inspect.isclass(IntegrationOrchestrator))
test("run_pipeline method", hasattr(IntegrationOrchestrator, "run_pipeline"))
test("_execute_single_action", hasattr(IntegrationOrchestrator, "_execute_single_action"))

# --- Summary ---
print()
print("=" * 60)
total = passed + failed
if failed == 0:
    print(f"ALL {total} TESTS PASSED")
else:
    print(f"{passed}/{total} PASSED, {failed} FAILED")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
