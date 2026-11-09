# Contributing to Agent Guru

Thanks for looking. This is a real project used daily - not a demo, not a showcase repo. Every contribution makes it better for anyone running a voice assistant on their own hardware.

---

## What kind of project is this?

Agent Guru is a voice AI assistant that runs entirely locally. You say "Hey Guru", it listens with faster-whisper, reasons with a local Ollama model, and speaks back through Kokoro TTS. No cloud, no subscription, no data leaves the machine.

The codebase is Python 3.11-3.13, async throughout, with a 7,904-test suite that runs on every push across all three Python versions. CI is green. Every change needs a test.

If you are looking for a weekend project where nobody checks your work, this is not it. If you want to ship code that runs in a real voice pipeline and have your name on something built properly, welcome.

---

## Before your first contribution

**Read these two files first. They are short and they are the rules.**

- [`AGENTS.md`](AGENTS.md) - commit rules, one-file-per-commit, message format, what is forbidden
- [`pytest.ini`](pytest.ini) - test configuration, markers, timeouts

The short version of `AGENTS.md`:
- Commit one file at a time, in dependency order
- Every commit message explains what was wrong before, what it cost the user, and what changed now
- Never use an em dash or en dash anywhere (code, comments, commit messages)
- Never add AI attribution lines to commits

---

## Setting up

You need Python 3.11, 3.12 or 3.13, a microphone and speakers, and [Ollama](https://ollama.com). GPU is not required - CPU works, just slower.

```bash
# Clone and enter
git clone https://github.com/Surajsharma0804/Agent_Guru.git
cd Agent_Guru

# Virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

# PyTorch - CPU build (avoids a 2 GB CUDA download on a GPU-less machine)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Everything else
pip install -e ".[test]"

# Pull the model Guru uses by default
ollama pull gemma4
```

Confirm the suite collects and passes:

```bash
pytest --collect-only -q   # should show ~7,904 tests
pytest                     # should pass, takes 5 to 40 minutes depending on hardware
```

If `pytest --collect-only` exits with a collection error, that is the first thing to fix before changing anything else.

---

## How to find something to work on

**Good first issues** are labelled `good first issue` in the [issue tracker](https://github.com/Surajsharma0804/Agent_Guru/issues). They are real bugs and real improvements, not invented busywork.

Areas where help is most needed right now:

| Area | What is needed | Skill |
|------|---------------|-------|
| Wake word | Train a custom "Hey Guru" model that false-triggers less than once per hour on everyday background sound | Python, ONNX, openWakeWord |
| Desktop UI | The backend is a local HTTP server. The frontend (HTML/CSS/JS) is partly built | Frontend, Python |
| macOS / Linux testing | CI runs monthly; daily feedback on real hardware would catch regressions faster | Any OS knowledge |
| Flaky tests | A handful of timing-sensitive tests fail under load. Each needs a root-cause fix, not a wider timeout | Python, asyncio |
| New tools | Weather, calendar notes and timers work. Contacts, music control and smart home are not wired in | Python |
| Documentation | The architecture docs are accurate but long. A one-page "how a turn works" diagram would help | Writing, diagrams |

---

## The standard for a change

Every change must include:

1. **A test** that proves the new behaviour or the fixed bug.
2. **A before-and-after measurement** when the change is about speed or correctness. Run the relevant benchmark or eval script, record the numbers, put them in the commit message. Do not write "this should be faster" - measure it.
3. **A commit message** that explains what was wrong before (concrete cost to the user), what it does now, and why this way.

If you fixed a bug, the process in `AGENTS.md` applies:
1. Show the bug. Run the test or the script and record the wrong output.
2. Fix it.
3. Write the regression test.
4. Revert the fix and confirm the test fails. Restore the fix.
5. Commit.

A test that passes against the broken code proves nothing. This check takes two minutes and is not optional.

---

## Running the tests

```bash
# Full suite (slow on CPU - real Kokoro TTS tests are excluded by default)
pytest

# Just one file
pytest Agent_Guru/platform/tests/test_reminders_kept.py -v

# Just one test
pytest Agent_Guru/platform/tests/test_reminders_kept.py::test_a_reminder_is_kept_on_disk_until_it_fires -v

# With coverage
pytest --cov=Agent_Guru --cov-report=term-missing

# Lint (only the error class - this blocks CI)
ruff check . --select F,E9,PLE

# Security scan
bandit -r Agent_Guru -c pyproject.toml -f screen
```

The real TTS tests (marked `real_tts`) synthesize speech hundreds of times. They are excluded from the default run. Run them with `pytest -m real_tts` only if you are changing the TTS pipeline.

---

## Code style

- Formatting: [black](https://black.readthedocs.io/) (`black .`). The CI lint job runs in advisory mode, not blocking, because 195 files are not yet formatted. Do format any file you touch.
- Lint: [ruff](https://docs.astral.sh/ruff/) with `--select F,E9,PLE` as a hard gate. The full rule set (`ruff check .`) produces advisory output on every CI run so the backlog is visible.
- Type hints: mypy strict is advisory. The error count is published on every run. It can only go down.
- Comments: explain why, not what. When fixing a bug, say what the old code did and what it cost - so nobody reintroduces it.
- No em dashes, no en dashes, anywhere. Use `-`.

---

## Project structure

```
Agent_Guru/
  genesis/        Installer and setup UI (Ollama, Python runtime, model)
  integration/    Orchestrator - ties STT, LLM, TTS and tools together
  platform/       Platform features: reminders, timers, app control, contacts
  reasoning/      LLM interaction, tool calling, memory, intent
  security/       Policy engine, auth, secret store, audit log
  speech/         Wake word, STT (faster-whisper), TTS (Kokoro), audio I/O
  utils/          Shared utilities: settings, service lifecycle, commands
  vision/         Face recognition and camera (optional, GPU)

scripts/          Evaluation and benchmark scripts
docs/             Architecture and developer notes
```

The rule: a module in `speech/` does not import from `integration/`. The dependency goes speech -> utils, platform -> utils, integration -> speech + platform + reasoning. If you need to cross that boundary, ask first.

---

## Submitting a change

This project has one committer and works directly on `main`. There are no branches, no pull requests (unless you are a first-time external contributor sending a PR from a fork). Commit one file at a time, push each commit immediately, and keep the tree green at every step.

External contributors: fork the repo, make your change with the same one-file-per-commit discipline, and open a pull request. The commit message format in `AGENTS.md` applies to your commits too.

---

## What we will not merge

- Changes that break an existing test without a documented reason
- Tests with absolute timing assertions (`time.sleep(0.1)`, `ticks > 20`, hard deadlines) - use events and signals instead
- Code that calls a real network endpoint, opens a real file from the developer's machine, or starts a real model from inside a test
- Comments that restate the code ("increment the counter")
- Em dashes or en dashes anywhere

---

## Questions

Open an issue. If it is a question about the architecture or a design decision, label it `question`. If you have spotted a bug, label it `bug` and include the wrong output and the Python version.

---

## Who built this

Suraj Sharma - voice AI enthusiast, solo developer. I use this assistant every day. It is not finished. I would rather show real gaps than fake a demo, and I am genuinely looking for people who want to build it with me.

GitHub: [@Surajsharma0804](https://github.com/Surajsharma0804)
