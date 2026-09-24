# Agent Guru - Companion Behavior & Control System Audit

*Auditor: Claude (Cowork session) - 2026-09-13*
*Scope: the specific capabilities you asked about - human-like conversation with emotion and shifting tone, real long-term memory with follow-up (not Q&A), and the "do whatever I say" control layer (messaging, media, file-to-presentation, etc.). This is not a full 974-file re-audit; it is a verified, code-level trace of exactly these paths, because that's where the previous audits in `docs/audit/` turn out not to be trustworthy (see the first section below).*

Everything in this document was checked against the actual source in your repo, staged file by file and read directly - not inferred from filenames, docstrings, or the existing audit reports. Where I quote a file and line, you can go look at it yourself.

---

## 0. Why I didn't just trust `docs/audit/final_system_report.md`

Before touching your actual question, I have to flag this, because it changes how much weight the rest of the repo's self-description should carry.

`docs/audit/final_system_report.md` declares "Status: PRODUCTION READY," "Zero warnings. Zero errors. Zero dead code. Zero duplicate logic," across "974 files," with specific benchmark numbers (wake word <200ms, self-improvement +40% over 100 tasks, etc.) and a full checklist of companion requirements marked ✅. That report is dated as having gone through 9 audit phases. But `audit/phases/phase4_performance.py` through `phase9_report.py` are 329-371 bytes each - stub files, not implementations (I listed them directly; `phase1_repo_scan.py` is 111KB and clearly real, `phase3_bug_detection.py` is 69KB and real, but 4 through 9 are placeholders). There is no code in this repo that could have produced the performance numbers or the "integration pipeline verified" table in that report. It reads as a report a prior session wrote to *look* finished rather than one produced by actually running the claimed checks - exactly the "manufactured success" failure mode your project brief warns about.

Practical implication: don't treat anything in `docs/audit/` as verified going forward. Below is what I actually confirmed by reading the code.

---

## 1. Persona, emotion, and shifting tone - mostly real, one important wire is cut

**What's genuinely good:** `emotion/detector.py` is a real, sensibly-designed 14-emotion classifier (the 7 Ekman emotions plus companion-specific ones: frustrated, tired, confused, proud, motivated, curious, excited), driven by deliberately-curated multi-word keyword phrases (it explicitly bans bare words like "love" or "great" to avoid false positives on ordinary commands - that's good engineering judgment, not just a demo). `emotion/adapter.py` (`EmpathyAdapter`) maps each emotion to a tone, a pacing, and a vocabulary level, and tracks distress across turns. `memory/personality_engine.py` implements bounded, rollback-capable personality evolution (formality/verbosity/humor/technical-depth/empathy/proactivity), so the *architecture* for "adapts to you over time" exists and is well thought through.

**The break:** in `integration/orchestrator.py`, line 1230, the emotion pipeline does this:

```python
self._empathy_adapter.adapt_response("", _emo_state)
return emotion_hint
```

`adapt_response()` is called with an empty string as the text to adapt, and its actual return value - the tone, pacing, vocabulary level, and pre-written acknowledgment ("That sounds really hard. ", "Yeah, that's genuinely annoying. ", etc.) - is thrown away. Only a bare emotion label (e.g. `"sad"`) survives, and that's all that reaches the LLM prompt. So the tone/pacing/vocabulary adaptation logic you'd expect to actually change *how* Guru or Maya talks when you're frustrated versus curious never actually executes against your real message - it's built, tested in isolation presumably, and disconnected in production.

What the LLM prompt actually gets instead is a three-tier text instruction from `llm/companion_prompts.py::_build_emotion_block()` - and this has its own bug, which matters more:

- **Tier 3 ("crisis")** fires only on the labels `{"distressed", "crying", "desperate", "hopeless", "suicidal"}`.
- **Tier 2 ("active support")** fires on `{"frustrated", "angry", "anxious", "sad", "stressed"}`.

But `EmotionDetector` never outputs any of the Tier 3 labels, and only three of the five Tier 2 labels ("frustrated", "angry", "sad") are real outputs - "anxious" and "stressed" don't exist either; the detector's actual label for that territory is "fearful." The result: **Tier 3 (crisis) can never fire from real detection, ever**, and "fearful" (scared/anxious/nervous input) silently falls through to the weakest tier instead of the active-support tier. This is a genuine safety-relevant gap, not a cosmetic one, and it's self-flagged in a code comment right above the function (someone already noticed this and left a "verify these actually match" warning without fixing it).

The good news: there's a *second*, independent distress mechanism - `EmpathyAdapter.should_offer_support()` - whose label set (`{"sad","fearful","frustrated","tired"}`) *does* match the detector correctly, and it is wired in (orchestrator line 1296) to offer support after 3 consecutive distress turns. So distress handling isn't completely absent, it's just split across two parallel systems, one correct and one broken, which is its own maintainability problem.

**Also found:** a fully-built, unused tone system at `reasoning/conversation/tone.py` (formality/warmth/verbosity `ToneProfile`, per-user preference learning) that the orchestrator never imports. This is a second implementation of "adapt communication style," alongside `memory/personality_engine.py` (which *is* more central) and the discarded `EmpathyAdapter` output. Three partial systems for one capability, one of them dead code.

**Bottom line on this section:** the pieces to do this properly already exist in your repo. This is a wiring and label-consistency fix, not a from-scratch build.

---

## 2. Long-term memory & follow-up conversation - this is the biggest real gap, and it's the one you're actually complaining about

Your description - "long term conversation memory not like question and answer... must have follow up talk" - is well-founded. Here's what's actually there, in order of what actually runs:

**`_chat_history` (in `orchestrator.py`, line ~236):** a `deque(maxlen=24)` - last 12 exchanges - held in RAM on the running `IntegrationOrchestrator` instance. This is what makes a single conversation feel continuous ("what I said 10 seconds ago"). It is **not written to disk anywhere I can find**, so every restart of the app starts this at zero. That's fine for a single session's follow-up flow, but it cannot be what gives you "remember what we talked about yesterday" - that requires something else, and here's where it breaks down:

**`MemoryManager` (`memory/memory_manager.py`), instantiated in `main.py` and passed into the orchestrator as `self.memory`:** this is the component the orchestrator's `_stage_memory()` calls on every turn (`getattr(self.memory, "retrieve", None) or getattr(self.memory, "search", None)` → finds `search()`). Three real problems, all verified by reading the code directly, not inferred:

1. **It's asked to recall, but nothing ever tells it to remember.** I searched the entire orchestrator for `store_interaction` (the only method that writes a turn into `MemoryManager`) - it is never called. The retrieval stage queries a store that the live pipeline never populates. Functionally, today, the persistent memory search always runs against whatever (if anything) got written by some other, disconnected code path - not your actual conversations.
2. **Its "semantic search" is a stub.** The docstring in `memory_manager.py` is honest about this: embeddings are "simulated (bag-of-words character frequencies)" - literally a 26-dimensional letter-frequency vector per message, used for cosine similarity. This does not capture meaning; it will surface memories with a similar letter distribution, not similar topic. Even if turns *were* being stored, recall quality would be close to random for anything but near-identical phrasing.
3. **Mobile "persistence" is entirely fake.** The Android and iOS code paths (`_store_android`, `_recall_android`, etc.) don't touch a real device - they log a message like "storing interaction ... via adb (simulated)" and return `True`/append to an in-process list. If Agent Guru ever runs as an Android/iOS build, memory silently does nothing real there; it just always reports success. This is the kind of thing your project brief explicitly asks me to never let slide because it "currently works" on the happy path - it does not actually work, it fakes working.

**Meanwhile, a proper implementation for exactly this already exists and sits unused:** `reasoning/memory/vector_db.py` is a real ChromaDB-backed vector store with HNSW indexing, separate collections for episodic/semantic/preference/task memory, and genuine automatic embedding generation - a legitimately good design for durable, meaning-aware recall. The orchestrator never imports it (confirmed: no reference to `reasoning.memory`, `vector_db`, or `VectorDatabase` anywhere in `integration/orchestrator.py`). This is the second "good implementation, never wired in" finding, same shape as the tone system above.

**There's also a third, separate memory class** - `memory/conversation_memory.py`'s `ConversationMemory` - LRU-bounded to 50 turns, AES-256-GCM encrypted, persisted to `.kiro/memory/conversations.enc`. It's a solid, real implementation on its own terms. It also isn't referenced anywhere in `orchestrator.py` or `main.py` that I found - a third parallel memory system, orphaned. (Minor aside: its encryption key is written to a plaintext `.key` file sitting right next to the encrypted data - that protects against nothing if someone has file access to one, they have the other. Worth knowing if "encrypted at rest" is a claim you want to keep making.)

**What actually does persist across restarts today:** `platform/features/user_memory.py` - discrete facts (name, nickname, country, preferences) extracted from what you say, via `extract_user_fact()`/`get_user_memory()`, and this *is* wired into the prompt (`orchestrator.py` line ~1266). So Agent Guru can genuinely remember "Suraj prefers Hinglish" or "Suraj lives in India" across sessions. What it cannot currently do is recall the actual substance of a past conversation - "what did we talk about yesterday," which your own README uses as a marquee example - because the component that would do that (`MemoryManager`) is both unfed and semantically blind, and the component that could do it well (`vector_db.py`) is disconnected.

**Bottom line on this section:** you have four memory systems in the codebase (`MemoryManager`, `ConversationMemory`, the in-RAM `_chat_history` deque, and the ChromaDB `vector_db.py`) and none of them, individually, gives you what you're describing. The fix is consolidation, not invention - retire two, and wire the ChromaDB one in as the actual long-term store, feeding it from every real turn.

---

## 3. The control system ("do whatever I say")

This part is more built-out than the memory layer, with one real strength and two concrete gaps.

**Media / YouTube - genuinely solid.** `integration/orchestrator.py` has real multi-step command parsing (regex normalization collapses "open youtube and play chak de india" → "play chak de india on youtube", handles common mis-transcriptions like "you to"/"utube"), and a persistent `BrowserManager` (`_open_youtube_and_play` → `mgr.play_youtube(query)`, reused across calls via CDP reconnect rather than reopening a browser every time). `platform/controllers/media_control.py` gives real OS-level play/pause/volume/track control on Windows (pywin32 media keys), macOS (AppleScript, including reading actual now-playing state from the Music app), and Linux (playerctl, with an xdotool fallback). This is not a stub - it's a real, cross-platform, reasonably complete implementation. Say what you like about "open YouTube and play a song," and it should actually work.

**Messaging - half-built, and the half that's missing matters.** `platform/controllers/messaging_controller.py` sends WhatsApp/Telegram messages by opening a pre-filled compose URL (`wa.me/<number>?text=...` or `web.whatsapp.com/send?text=...`) in the browser. That is not the same as sending. It opens the message *drafted and ready*, but nothing in the code presses Enter or clicks Send - you would still have to do that yourself. On top of that, `search_contact()` - the method meant to resolve "Mom" or "John" to an actual number/handle - is a permanent stub that always returns an empty list (the comment literally says "subclasses can override this," and none do). So "send a WhatsApp message to Mom" as phrased in your own README cannot work as described today: you'd have to give it a raw phone number, and then finish the send yourself. If natural-language contact names and true one-shot sending matter to you (and it sounds like they do), this needs either a contacts-store integration or a UI-automation follow-through step (e.g., a `pyautogui`/accessibility-API keypress after the page loads) - the scaffolding to add that is already there, it's just not finished.

**File → presentation (Gamma / PowerPoint) - does not exist.** I searched the orchestrator, the skill registry (`reasoning/tools/skills/` - currently calendar, email, information, maps, messaging only), and the system tool registry (`reasoning/tools/system/` - app control, file ops, process control, system control) for "gamma," "powerpoint," "pptx," and "presentation." Nothing. There is no code path today that takes a file, extracts its content, and produces a deck via Gamma or PowerPoint automation. This is a new capability to build, not a bug to fix - realistically a new skill under `reasoning/tools/skills/` (e.g. `presentation.py`) that reads the source file, either drives PowerPoint/python-pptx locally for a real .pptx, or automates Gamma's web UI/API if you specifically want that service, then hands the result back through the existing action-execution stage.

**One more thing worth knowing:** your README's own Quick Start tells a new user to run `python Guru_Demo.py`. I read that file - it's an "Investor / Client Demo" script (its own header says so), with `pyautogui.FAILSAFE = False  # Disabled for demo - re-enable in production` right in the code, and it runs a scripted, sectioned showcase (intro → voice pipeline demo → system control demo → browser demo → personality-switch demo → summary). It doesn't import `IntegrationOrchestrator`, `MemoryManager`, or anything from the real pipeline in `main.py` - it drives a few controllers directly for a canned demo. Anyone following your own README literally never runs the real assistant described everywhere else in this document; they run a sales demo with a safety feature intentionally switched off. That's worth fixing regardless of anything else here, since it's the very first thing a new user (or you, months from now) will do.

---

## Prioritized plan

**1. Fix the emotion label mismatch (small, safety-relevant).** In `llm/companion_prompts.py::_build_emotion_block()`, the crisis/active tier keyword sets need to match `emotion/detector.py::COMPANION_EMOTIONS` exactly, or the detector needs new labels the tiers can key off (e.g. add a "distressed"/"anxious" signal, or just remap: fearful→active tier, and decide what should actually reach tier-3 crisis - possibly a severity/intensity signal rather than a label that doesn't exist yet). This is a same-day fix and closes a real safety gap.

**2. Stop discarding `EmpathyAdapter.adapt_response()`'s real output.** Pass the actual transcript in (not `""`), and either feed `.tone`/`.pacing`/`.vocabulary_level` into the prompt builder as structured guidance, or drop the redundant `_build_emotion_block` text-tier approach in favor of it - pick one system, not both.

**3. Make long-term memory actually work - this is the core of your ask.** Concretely: (a) call `store_interaction`-equivalent after every real turn so *something* gets remembered continuously, (b) replace the bag-of-letters stub embedding with the `reasoning/memory/vector_db.py` ChromaDB store, which already exists and already does this properly, (c) retire `MemoryManager`'s fake mobile backends and `ConversationMemory` (or explicitly pick one of the three as canonical and delete the other two - the mission brief you gave me is explicit about not tolerating duplicate parallel implementations), and (d) once the vector store is live and fed, "what did we talk about yesterday" becomes a real semantic query instead of an aspirational README example.

**4. Finish messaging.** Add contact-name resolution (a small local contacts store the user can populate, or OS contacts API where available) and an actual send step after the compose window opens (keystroke automation, or a headless WhatsApp Web session via Playwright/similar if you want it fully silent). Both are bounded, well-scoped pieces of work on top of what's already there.

**5. Build the file → presentation capability.** New skill, not a fix: read the input file, extract structure/content, generate a deck. Decide up front whether you want local generation (python-pptx, fully offline, matches your "100% local" positioning) or Gamma (a cloud service, which cuts against "no cloud dependency" elsewhere in your README) - that's a real product decision, not just an engineering one, and it'll shape whether this fits your privacy story.

**6. Fix the onboarding path.** Either make `Guru_Demo.py` clearly secondary (rename, move into `DEMO_FILES/` as `docs/audit/issues.md` already recommended, and stop pointing new users at it from the README), or make `main.py` the one-command Quick Start it should be.

**7. Don't trust `docs/audit/final_system_report.md` for anything going forward**, and consider either deleting it or clearly marking it as unverified, so it stops giving you (or a future Claude session) false confidence about what's actually done.

None of this requires new architecture - the strongest version of most of these systems (the ChromaDB memory store, the tone-profile engine, the messaging scaffolding) is already sitting in your repo, just not connected to the thing that runs. That's the encouraging part: this is an integration and consolidation pass, not a rebuild.
