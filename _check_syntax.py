import py_compile

files = [
    "Agent_Guru/reasoning/tools/tests/test_intelligence.py",
    "Agent_Guru/platform/windows/tests/test_windows_integration.py",
    "Agent_Guru/speech/tts_manager.py",
    "Agent_Guru/reasoning/tools/system/process_control.py",
    "Agent_Guru/reasoning/tools/skills/sandbox.py",
    "Agent_Guru/reasoning/deployment/rollback_monitor.py",
    "Agent_Guru/reasoning/llm/ollama_server.py",
    "Agent_Guru/reasoning/llm/local_server.py",
]

ok = 0
err = 0
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"OK  {f}")
        ok += 1
    except py_compile.PyCompileError as e:
        print(f"ERR {f}: {e}")
        err += 1

print(f"\n{ok} OK, {err} errors")
