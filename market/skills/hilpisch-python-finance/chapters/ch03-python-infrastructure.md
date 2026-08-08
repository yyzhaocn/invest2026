# Chapter 3: Python Infrastructure

## Core Idea
A minimal, reproducible baseline — current Python 3, shell, venv + pip, lightweight editors, notebooks (JupyterLab/Colab) — that ports cleanly from laptop to Docker to cloud, without heavy IDEs.

## Frameworks Introduced
- **Environment-outside-project pattern**: keep code in version-controlled/cloud-synced dirs; keep `.venv/` **outside** synced folders (e.g. `~/venvs/py4fi3rd/`), and document recreation via `requirements.txt`.
  - When to use: Dropbox/OneDrive/iCloud-synced projects, shared machines, team repos.
  - Why: large hidden folders waste sync bandwidth; per-project envs recreate cleaner than restoring someone else's.
- **`python -m pip` convention**: always call pip through the active interpreter (`python -m pip install ...`) to avoid installing into the wrong environment.

## Key Concepts
- **venv**: standard-library virtual environments — sufficient for most finance workflows.
- **requirements.txt**: the rebuild contract; anyone can recreate the env.
- **Python ≥ 3.10/3.11 required**: book assumes current Python 3 (3.11+ tested; ≥3.10 for syntax/library features).
- **Colab-ready notebooks**: book notebooks avoid IDE-specific dependencies.

## Mental Models
- Use X when Y: *use `venv` when* you need isolation without extra tooling; *use `uv`/`poetry`/Docker when* the team already standardizes on them.
- Think of infrastructure as *a reproducibility contract*, not personal preference: the shell + requirements.txt define what "works" means.

## Anti-patterns
- **`.venv/` inside synced folders**: wasted bandwidth/storage, accidental inclusion in backups.
- **Trusting the system Python**: often outdated or reserved for OS components — use an interpreter you control.
- **`pip install` without `python -m`**: can target the wrong interpreter on machines with multiple Pythons.

## Code Examples
```bash
# Create and activate a venv (macOS/Linux)
python3 -m venv .venv/
source .venv/bin/activate

# Install core scientific stack inside the active env
python -m pip install numpy pandas matplotlib

# Deactivate
deactivate
```
```powershell
# PowerShell (Windows)
py -3 -m venv .venv/
.venv\Scripts\Activate.ps1
python -m pip install numpy pandas matplotlib
```
- **What it demonstrates**: cross-platform reproducible env creation.

## Reference Tables
| Task | macOS/Linux | Windows PowerShell |
|---|---|---|
| Print dir | `pwd` | `Get-Location` |
| List | `ls` | `Get-ChildItem` |
| Change dir | `cd path` | `Set-Location path` |
| Check Python | `python3 --version` | `py -3 --version` |
| Create env | `python3 -m venv .venv/` | `py -3 -m venv .venv/` |
| Activate | `source .venv/bin/activate` | `.venv\Scripts\Activate.ps1` |
| Install | `python -m pip install ...` | `python -m pip install ...` |

## Worked Example
Book setup: on a corporate/managed machine, check with IT for an approved Python distribution/container/cloud notebook *before* installing; otherwise install python.org/Homebrew Python → `python3 -m venv .venv/` → activate → `python -m pip install numpy pandas matplotlib` → verify with `python -c "import numpy, pandas; print(numpy.__version__)"`.

## Key Takeaways
1. Reproducibility beats convenience: document env creation, don't store envs.
2. Keep environments outside cloud-synced directories.
3. Always install via `python -m pip` in the active env.
4. Shell fluency (pwd/ls/cd + running scripts) is the portable baseline.

## Connects To
- **Ch 4-8**: the data structures and libraries you just installed
- **Ch 11**: performance tooling builds on this baseline
