# Wake-word training on the A100: runbook

Everything needed is in the data folder (`agent_guru_wakeword_data`, 30.25 GiB, 638 files).
Nothing is downloaded on the day. Commands below assume bash on the cluster's login node
and a SLURM scheduler; the plain `python run.py` form works on any Linux GPU machine.

First-run models are not expected to be final. The aim of the day is a pipeline that
produces models and a benchmark report, after which a retrain that only changes training
settings costs about an hour (see "Tuning and retraining").

## 0. Requirements on the cluster

| Need | Minimum | Check |
|---|---|---|
| NVIDIA driver, default set (torch 2.11.0, CUDA 12.6 wheels) | 525.60 | `nvidia-smi` (top line) |
| NVIDIA driver, fallback set (torch 2.7.1, CUDA 11.8 wheels) | 450.80 | same |
| glibc (the shipped CPython 3.13 and manylinux_2_28 wheels) | 2.28 | `ldd --version` |
| Disk for the data folder | 31 GiB | `df -h $SCRATCH` |
| Disk for one full work folder | not yet measured at full scale; the dry run uses under 1 GiB | `du -sh $WORK` after the dry run |
| Job: GPU, CPUs, memory | 1 GPU, 16 CPUs, 48 GB | edit `#SBATCH` lines in `code/slurm_run.sh` |

No CUDA toolkit, module, root, conda or network is needed: CUDA libraries come as pip
wheels from the data folder, Python is the standalone build in `env/python/`.

## 1. Copy and verify (before the day if possible)

```bash
rsync -a --info=progress2 agent_guru_wakeword_data/ $SCRATCH/agent_guru_wakeword_data/
export DATA=$SCRATCH/agent_guru_wakeword_data
python3 $DATA/code/verify.py --data $DATA          # any python3 >= 3.8; hashes 30 GiB
```

Expected: `OK: the data folder is complete`. Hashing took 30 s on the laptop's SSD; on a
network filesystem expect a few minutes. Exit 1 lists every missing, short or corrupt
file: copy those again (rsync again is enough) and re-verify.

## 2. Install the environment (once; not yet timed on Linux)

```bash
srun --gres=gpu:1 --cpus-per-task=4 --mem=16G --time=00:30:00 \
    bash $DATA/code/install_linux.sh $HOME/agent_guru_env
export VENV=$HOME/agent_guru_env/venv
```

Run it inside a GPU job: the last step multiplies a matrix on the GPU and exits 1 if none
is visible. Expected last lines: `python 3.13.16 | torch 2.11.0+cu126 | CUDA available True`,
`GPU NVIDIA A100-SXM4-40GB` (or 80GB), `compute capability 8.0`, `GPU matmul ok: True`.

If torch reports no CUDA, or a driver-too-old error, and `nvidia-smi` shows a driver
below 525.60: delete `$HOME/agent_guru_env` and install the fallback set:
`TORCH_SET=linux-cu118 bash $DATA/code/install_linux.sh $HOME/agent_guru_env`.

Both sets were resolved offline by pip's own resolver against Linux markers before the
data folder was written (`code/check_wheelhouse.py`); an install failure on the day is a
cluster difference (glibc, filesystem), not a missing wheel. Paste the error.

## 3. Dry run first (about 12 min on the laptop, should be less on the A100)

```bash
export WORK=$SCRATCH/agent_guru_dry
sbatch --time=00:45:00 $DATA/code/slurm_run.sh --scale 0.01
```

Read `$WORK/out/REPORT.md`. The models are tiny and are expected to detect nothing; the
dry run checks the pipeline. It is good when all of these hold:

| In the report | Expected | If not |
|---|---|---|
| Scorer self-test | Guru 14/14, Maya woken as Guru 14/14, false wakes > 0 | The run stops on its own. Do not trust any benchmark; send `run.log`. |
| Feature check, vs ordinary speech | 0.95 or more (laptop: 0.98) | Clips or features are broken: send the report and `run.log`. Training longer will not help. |
| Export checks in `run.log` | `opset 13, ir 7, no side file, matches torch ... within 1e-07`-ish | The run stops on its own at the failing model. |
| Parler: precision | `bfloat16` on the A100 | Pass `--parler-dtype bfloat16`. |
| Parler: batch probe | s/clip falling as batch grows; chosen batch 64 to 512 | Fine if lower; the full run uses the chosen batch. Write down the s/clip. |
| Parler per-text table: empty | English under 2%, Hindi under 10% (laptop bf16: 0.3% and 5.2%) | More than double those: check precision is bf16. |
| Machine line | `job_cpus` equals the job's CPUs, `job_ram_free_gib` under the job's memory | Feature workers are sized from these; if they show the whole node, pass `--workers 15`. |
| Svarah split | 115 speakers, 81 train, 34 bench | The Svarah files differ from the ones prepared: re-verify. |

Detection 0% at every threshold and "No operating threshold" are normal for the dry run.

## 4. The full run

```bash
export WORK=$SCRATCH/agent_guru_hey
bash $DATA/code/submit_chain.sh 3 --models hey
```

This queues three jobs that run one after another; each resumes where the previous one
stopped (a time limit loses only the step in progress). A finished run makes later jobs
exit within a minute. Then the second experiment, in its own work folder:

```bash
export WORK=$SCRATCH/agent_guru_bare
bash $DATA/code/submit_chain.sh 3 --models bare
```

Watch progress with `tail -f $WORK/run.log`; stage starts are lines with `==`.

### Expected time

Measured on the laptop (RTX 2050, 12 CPUs), per full run of two models:

| Stage | Laptop, measured rate | Full-scale count | Laptop estimate |
|---|---|---|---|
| Parler generation | 0.334 s/clip at batch 16 | 11,400 clips plus about 5% regenerated | 67 min |
| train.py clip generation (Piper) | 0.04 s/clip | about 16,800 clips per model | 22 min |
| Augmentation and features | 20 ms/clip on 7 workers | 24,000 clips per model | 16 min |
| Training | 19.6 ms/step plus about 7 min | 50,000 steps per model | 46 min |
| Benchmark | 861 s measured, one CPU core | 3.4 h of Svarah held-out audio and 16 min of speech | 14.4 min |

The A100 has not been measured. Parler dominates: multiply the dry run's chosen-batch
s/clip by 12,000 for the Parler time. Training steps on the A100 are expected to take
well under the laptop's 19.6 ms, but batch assembly is CPU work, so with 16 CPUs a total
of 1.5 to 3 hours for one model set is the planning figure, not a promise. Each job's
4-hour limit is enough for any single stage; the chain of three covers the whole run.

## 5. What to bring back

`$WORK/out/` holds `REPORT.md`, `report.json` and `agent_guru_wakewords_<set>.zip` (the two
ONNX models plus the report). Copy the `out/` folder and `run.log` of each work folder.

## 6. When a number is wrong

| Symptom | Likely cause | Action |
|---|---|---|
| Job ends with `failed with exit status` | the step's own error, printed above that line | Resubmit the same command once (it resumes). If it fails at the same place, send `run.log`. |
| Killed by the scheduler (`TIME LIMIT`, `OUT_OF_MEMORY`) | limit too small for one step | Time: raise `--time`. Memory: raise `--mem` or pass `--workers 8`. Resubmit. |
| `CUDA out of memory` in Parler | another process on the GPU | `--parler-batch 64`, resubmit. |
| Parler empty rate high for one text | that text, not the run | Recorded in the report; kept clips are still valid. |
| Real models: detection on your takes far below the TTS sets | the voice mix leans on TTS | Tuning item, not a failure: see below. |
| False wakes per hour high on Svarah but not on speech | accent coverage | Tuning item. |

## 7. Tuning and retraining

Generation and features are the slow part and do not change when training settings
change. To retrain only, edit the settings in `code/run.py` (steps, negative weighting) or
add negative phrases, then delete the training and benchmark markers and resubmit:

```bash
rm $WORK/state/*_train_model.done $WORK/state/train.done $WORK/state/benchmark.done
bash $DATA/code/submit_chain.sh 1 --models hey
```

That repeats only training (about 25 min a model on the laptop) and the benchmark. New
negative phrases also need their clips: delete `*_generate_clips.done`, `*_features.done`
and the model's `negative_*` folders and `negative_features_*.npy` as well.

What is expected to need tuning after the first run: the operating threshold (the report
picks it), steps and negative weighting (if false wakes per hour are above 0.5), the
custom negative phrases (add what the false wakes were), and the Parler, Hindi and
recorded-take shares of the training positives (if your takes score lower than TTS).

## 8. Proving resume on the cluster (optional, 25 min)

```bash
$VENV/bin/python $DATA/code/kill_test.py --data $DATA --work $SCRATCH/agent_guru_kill \
    --reference $SCRATCH/agent_guru_dry
```

Kills the dry run during Parler, clip generation, features, training and the benchmark
(SIGTERM then SIGKILL after 30 s, as SLURM does at a time limit), resumes each time, and
compares the result with the clean dry run. Exit 0 and `"problems": []` is a pass.
