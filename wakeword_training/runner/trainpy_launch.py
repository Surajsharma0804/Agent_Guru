"""Run openWakeWord's train.py with the Python 3.13 compatibility module loaded first.

    python trainpy_launch.py <openwakeword source dir> <train.py arguments...>

The run happens in a fresh interpreter (train.py is a script, and the runner keeps its own
process for generation), and that interpreter needs colab313_compat before train.py imports
speechbrain and torchaudio. Loading it here, rather than through a .pth file in
site-packages, means nothing is written into the Python installation, which on a cluster
may not be ours to write.

The interpreter leaves without its normal teardown once train.py has returned. On Windows
with CUDA torch, `train.py --generate_clips` finished all four of its generation passes,
printed "Done", and then the process died on the way out (exit 0xC0000409, a native abort),
so a completed step was reported as failed. Every file train.py writes is closed by then;
skipping the teardown loses nothing. An exception from train.py still exits nonzero, after
its traceback is printed.
"""
import os
import runpy
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # PYTHONPATH from run.py also has the compat dir
import colab313_compat  # noqa: E402,F401

src = Path(sys.argv[1])
sys.path.insert(0, str(src))
train = src / "openwakeword" / "train.py"
sys.argv = [str(train), *sys.argv[2:]]
code = 0
try:
    runpy.run_path(str(train), run_name="__main__")
except SystemExit as e:
    code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
except BaseException:
    traceback.print_exc()
    code = 1
sys.stdout.flush()
sys.stderr.flush()
if os.name == "nt":
    # os._exit alone was not enough: on Windows it still runs ExitProcess, which calls every
    # loaded DLL's detach handler, and one of them aborted ("Fatal Python error: Aborted" at the
    # os._exit line, measured with -X faulthandler; likely the second onnxruntime that
    # piper-phonemize-fix bundles next to onnxruntime 1.30). TerminateProcess skips detach.
    import ctypes
    k32 = ctypes.windll.kernel32
    # Declared types: undeclared, ctypes cut GetCurrentProcess's 64-bit pseudo-handle to 32 bits,
    # TerminateProcess failed on the invalid handle and returned, and the abort still happened.
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    k32.TerminateProcess(k32.GetCurrentProcess(), code)
os._exit(code)
