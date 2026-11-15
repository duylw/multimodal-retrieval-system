---
name: command-execution-safety
description: >-
  Use this skill whenever generating, validating, or executing shell commands, scripts,
  and background processes under auto-accept or unattended execution modes. Enforces strict
  non-destructive command guardrails, prohibited command blacklists, safe PowerShell/Git/uv
  alternatives, pre-flight safety checklists, resource quotas, and crash recovery procedures.
---

# Command Execution Safety & Auto-Accept Guardrails Runbook

This skill establishes strict operational safeguards and execution policies for the AI assistant when executing shell commands via `run_command` in the **Multimodal Video Moment Retrieval** repository, especially when the user has enabled automatic command approval ("auto-accept").

---

## 1. Core Safety Principles

1. **Non-Destructive Default:**
   Commands must never alter or destroy state irreversibly without prior verification. Safe inspection (`Get-ChildItem`, `git status`, `git diff`) must always precede state-mutating actions.
2. **Explicit Target Specificity:**
   Wildcard deletions (`*`, `*.*`) or recursive directory sweeps (`Remove-Item -Recurse -Force`, `rmdir /s /q`) are strictly forbidden. Every target file or resource must be specified explicitly with its full or relative path.
3. **Hardware & Resource Discipline:**
   The workspace operates under tight hardware constraints (NVIDIA GeForce GTX 1650 4GB VRAM, 16GB RAM). Commands must never trigger unconstrained batch loops, concurrent model initializations, or infinite background tasks that could exhaust system resources.
4. **Environment Isolation:**
   All commands must execute within the repository root `d:\UIT\TX\doan`. Never access, modify, or delete files outside this project tree, system directories, or Windows OS registry.
5. **Reversibility & Rollback Preparedness:**
   Before modifying databases, configuration files, or critical outputs, ensure a clean backup or rollback state exists.

---

## 2. Strictly Prohibited Commands (The Blacklist)

The following commands and patterns are **STRICTLY PROHIBITED** under auto-accept. If a task appears to require any of these, the assistant must STOP and explain the risk to the user rather than executing:

| Category | Prohibited Commands & Patterns | Reason & Risk |
|---|---|---|
| **Bulk Deletion** | `rmdir /s /q`, `del /s /q *`, `Remove-Item -Recurse -Force <dir>`, `rm -rf` | Irreversible loss of source code, datasets, or keyframes. |
| **Disk & OS System** | `format`, `diskpart`, `chkdsk /f`, `reg delete`, `Set-ItemProperty HKLM:` | Severe system damage, drive wiping, OS registry corruption. |
| **Dangerous Git Operations** | `git push --force`, `git push -f`, `git reset --hard`, `git clean -fdx`, `git checkout -- .`, `git restore .` | Destroys uncommitted code, rewrites shared history, wipes untracked files. |
| **Branch Deletion** | `git branch -D <branch>` | Destroys branch history without verifying merge status. |
| **Indiscriminate Staging** | `git add .`, `git add -A`, `git commit -a` | Risks committing heavy binary videos, databases, or cache files into Git. |
| **Global Package Managers** | `pip install ...`, `conda install ...`, `pip install -r requirements.txt` | Pollutes host environment; violates the project rule enforcing `uv`. |
| **Arbitrary Remote Code Execution** | `curl ... | iex`, `Invoke-Expression (Invoke-WebRequest ...)`, downloading and piping scripts directly to shell | Severe security vulnerability; executes untrusted external code. |
| **Host Process Killing** | `taskkill /f /im explorer.exe`, `Stop-Process` on critical system processes | Crashes user OS session or background system services. |

---

## 3. Protected Project Assets

The following directories and files contain heavy compute investments or core logic and must **NEVER** be deleted, truncated, or overwritten blindly:

* [data/raw_videos/](file:///d:/UIT/TX/doan/data/raw_videos): Raw video dataset files (expensive to download or obtain).
* [data/keyframes/](file:///d:/UIT/TX/doan/data/keyframes): Extracted keyframes (requires significant CPU/disk decoding time).
* [data/features/](file:///d:/UIT/TX/doan/data/features): Visual SigLIP2 feature embeddings (requires GPU compute hours).
* [data/metadata.db](file:///d:/UIT/TX/doan/data/metadata.db): SQLite relational database containing shots, keyframes, transcripts, and OCR text.
* [data/indices/](file:///d:/UIT/TX/doan/data/indices): Search indexes (FAISS visual indices, SQLite FTS5 indices).
* [.git/](file:///d:/UIT/TX/doan/.git): Git version control repository database.
* [configs/default_config.yaml](file:///d:/UIT/TX/doan/configs/default_config.yaml): Base project configuration (edit via targeted tools, never overwrite blindly).

---

## 4. Safe Command Alternatives Runbook

Always replace hazardous commands with their safe, defensive equivalents in PowerShell and Git:

### 4.1 Safe File Management

* **Unsafe Pattern:** `Remove-Item -Recurse -Force data/keyframes/`
  **Safe Alternative:** Clean specific video subfolder or inspect contents first:
  ```powershell
  # Check target contents before deletion
  Get-ChildItem -Path "data/keyframes/{video_id}"
  # Remove only the target video subfolder explicitly
  Remove-Item -Path "data/keyframes/{video_id}" -Recurse
  ```

* **Unsafe Pattern:** `del /q *`
  **Safe Alternative:** Delete explicitly named ephemeral file:
  ```powershell
  # Remove single intermediate audio file
  if (Test-Path "data/temp_audio.wav") { Remove-Item -Path "data/temp_audio.wav" }
  ```

### 4.2 Safe Git Operations

* **Unsafe Pattern:** `git clean -fdx`
  **Safe Alternative:** Dry-run inspection first:
  ```powershell
  git clean -ndx
  ```

* **Unsafe Pattern:** `git reset --hard HEAD`
  **Safe Alternative:** Stash changes safely with a descriptive message:
  ```powershell
  git stash push -m "[SAFEGUARD] Temporary stash before task checkpoint"
  ```

* **Unsafe Pattern:** `git add .`
  **Safe Alternative:** Stage only specific modified source files:
  ```powershell
  git add src/retrieval/score_fusion.py tests/test_score_fusion.py
  ```

### 4.3 Safe Package Management

* **Unsafe Pattern:** `pip install package_name`
  **Safe Alternative:** Use `uv` within project virtual environment:
  ```powershell
  uv add package_name
  # Or run scripts directly:
  uv run python -m src.runners.run_extraction --video-id test_video
  ```

---

## 5. Execution Pre-Flight Checklist

Before calling `run_command`, the assistant must mentally verify the following 5-point checklist:

```
[Pre-Flight Command Safety Checklist]
├── 1. Working Directory Check: Is the command executing inside d:\UIT\TX\doan?
├── 2. Blacklist Scan: Does the command contain prohibited patterns (force git, bulk rm, pip, format)?
├── 3. Target Specificity: Are file paths targeted explicitly rather than using wildcards (*)?
├── 4. Hardware Impact: Does this launch heavy GPU inference? If so, is VRAM clear and batch size <= 8?
└── 5. Tool Summary: Is toolSummary descriptive and accurate (e.g. "Run test suite", not generic "Run command")?
```

---

## 6. Hardware & GPU Safety Guardrails

Under auto-accept, automated execution of deep learning models must adhere to strict hardware boundaries:

1. **Single-Video Verification First:**
   Never launch extraction over the entire dataset ([data/raw_videos/](file:///d:/UIT/TX/doan/data/raw_videos)) without first validating the command on a single video:
   ```powershell
   # [STEP 1] Validate on 1 sample video
   uv run python -m src.runners.run_extraction --video-id video_sample_01
   
   # [STEP 2] Check results and database records
   uv run python -c "import sqlite3; conn = sqlite3.connect('data/metadata.db'); print(conn.execute('SELECT COUNT(*) FROM shots').fetchone())"
   ```
2. **GPU Memory Inspection:**
   Before running heavy GPU models (SigLIP2, Whisper), verify GPU status if needed:
   ```powershell
   nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader
   ```
3. **Sequential Staging Enforcement:**
   Ensure previous model processes have terminated before starting the next pipeline stage.

---

## 7. Failure Handling & Recovery Protocol

When a command returns a non-zero exit code or fails:
1. **Never Chain Risky Fixes Blindly:** Do not execute blanket resets or delete entire directories hoping to fix a broken state.
2. **Inspect Error Output:** Read the stderr/stdout to diagnose root causes (missing module, schema mismatch, missing file).
3. **Isolate Affected Items:** If a video fails during a batch run, mark it failed in SQLite and proceed without corrupting healthy records.
4. **Report Transparently:** Summarize the exact error message and the proposed remedy to the user.
