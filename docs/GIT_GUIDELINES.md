# Git Workflow & Team Collaboration Guidelines

This document establishes the standardized Git workflow and collaboration rules for the **Multimodal Video Moment Retrieval** graduation thesis project.

---

## 1. Core Principles

1. **Never Commit Heavy Data to Git:**
   * No raw videos (`.mp4`, `.mkv`, `.avi`).
   * No keyframe images (`.jpg`, `.png`).
   * No databases (`.db`, `.sqlite`) or index files (`.index`).
   * No model weights (`.pt`, `.bin`, `.safetensors`, `.onnx`).
   * All binary patterns are protected via [.gitignore](file:///d:/UIT/TX/doan/.gitignore).
2. **Always Inspect Status Before Staging:**
   * Run `git status` prior to staging to ensure no untracked data or cache artifacts are included.
3. **Atomic Commits:**
   * Each commit must address a single logical change (e.g., implement a specific filter function, update a dataclass).
   * Do not bundle unrelated changes across multiple modules into vague messages like *"update code"* or *"fix bug"*.
4. **No Emojis / Icons:**
   * Strictly avoid emojis in commit messages, code, logs, and documentation. Use clean Conventional Commits.
5. **Language Rule:**
   * 100% of all commit messages and repository documentation must be written in English.

---

## 2. Branching Strategy

Recommended branching model for the thesis team:

```
main (Production-ready, stable, passing evaluation harness)
 │
 ├── feat/task-00-eval (Environment & ground truth benchmark)
 ├── feat/task-01-shots (Shot detection & adaptive keyframes)
 ├── feat/task-01b-debug-ui (Interactive debug inspector)
 ├── feat/task-02-visual (SigLIP2 embedding & FAISS indexing)
 ├── feat/task-03-speech (Whisper ASR transcription)
 ├── feat/task-04-ocr (PaddleOCR text extraction)
 ├── feat/task-05-fusion (Temporal fusion & sliding window)
 └── fix/vram-leak-siglip (Bug fixes & optimizations)
```

### Branch Naming Conventions:
* Feature branch: `feat/task-XX-<short-name>` (e.g. `feat/task-01-shots`, `feat/task-02-visual`)
* Bug fix branch: `fix/<issue-name>` (e.g. `fix/sqlite-lock`, `fix/empty-audio-crash`)
* Documentation: `docs/<topic>` (e.g. `docs/project-overview`, `docs/tracking-update`)

---

## 3. Conventional Commits Specification

All commit messages must be written in English adhering to the standard format:

```
<type>(<scope>): <concise description in imperative mood>

[Optional body: technical rationale, trade-offs, or issue references]
```

### A. Allowed Types:
* `feat`: New feature, pipeline stage, or user interface module.
* `fix`: Bug fix, logic correction, memory leak resolution.
* `refactor`: Code restructuring without modifying behavior.
* `perf`: Performance improvements (faster FPS, reduced VRAM).
* `test`: Adding or modifying test scripts or ground truth benchmarks.
* `docs`: Documentation updates (markdown, guides, comments).
* `chore`: Build config, dependencies via `pyproject.toml`, `.gitignore`.

### B. Standard Scopes:
* `shots`: Shot boundary detection and video segmentation.
* `keyframes`: Keyframe extraction, blur filtering, deduplication.
* `visual`: SigLIP2 embeddings and visual indexing.
* `speech`: Whisper transcription and ASR processing.
* `ocr`: PaddleOCR detection and SQLite FTS5 search.
* `fusion`: Temporal alignment, RRF score fusion, sliding window.
* `ui`: Web application, streaming server, player timeline.
* `eval`: Scientific evaluation, Recall@K, MRR, ground truth.
* `config`: YAML parameters and Configuration Manager.

### C. Good vs Bad Examples:

* **Good:**
  * `feat(shots): implement adaptive keyframe selection with laplacian variance`
  * `feat(visual): add siglip2 batch extraction with fp16 vram safety`
  * `fix(speech): remove temporary wav files after whisper transcription`
  * `refactor(indexer): standardize base indexer interface for faiss`
  * `perf(ocr): add edge density pre-filter to skip non-text frames`
  * `docs(agents): update hardware constraints and git guidelines`

* **Bad (Avoid):**
  * `fix bug` *(Vague, uninformative)*
  * `update code hom nay` *(Contains non-English words, lacks scope)*
  * `add feature and fixed some files` *(Combines disparate tasks)*
  * `:rocket: deploy app` *(Contains emoji)*

---

## 4. Daily Collaboration Scenarios

### Scenario 1: Starting a New Task
1. Switch to `main` and pull latest changes:
   ```powershell
   git checkout main
   git pull origin main
   ```
2. Create and switch to a task feature branch:
   ```powershell
   git checkout -b feat/task-02-visual
   ```

### Scenario 2: Committing Completed Work
1. Check modified files:
   ```powershell
   git status
   ```
2. Test code locally to ensure zero runtime errors.
3. Stage relevant files:
   ```powershell
   git add src/extractors/visual.py configs/default_config.yaml
   ```
4. Commit following Conventional Commits:
   ```powershell
   git commit -m "feat(visual): implement siglip2 embedding extractor with fp16 batching"
   ```

### Scenario 3: Pushing Branch & Creating a Pull Request
1. Push branch to remote:
   ```powershell
   git push origin feat/task-02-visual
   ```
2. Open a Pull Request on GitHub for peer review:
   * Title: `[Task 02] Implement SigLIP2 Visual Extraction & FAISS Index`
   * Description: Tested on 344 keyframes, verified VRAM under 3.2 GB.
3. Merge into `main` after review and verification.

### Scenario 4: Resolving Merge Conflicts
If concurrent edits produce conflicts:
1. Git highlights conflicting lines with `<<<<<<< HEAD` and `>>>>>>>`.
2. Inspect and resolve conflicts cooperatively.
3. Stage resolved files and commit:
   ```powershell
   git add <resolved_file>
   git commit -m "fix(merge): resolve conflict in score_fusion.py"
   ```

---

## 5. Git Command Cheat Sheet

| Command | Description |
|---|---|
| `git status` | Check working tree status (always run before staging) |
| `git diff` | Inspect line-by-line code modifications |
| `git branch -a` | List all local and remote branches |
| `git checkout -b <branch>` | Create and switch to a new branch |
| `git checkout <branch>` | Switch to an existing branch |
| `git pull origin main` | Fetch and merge upstream changes from main |
| `git push origin <branch>` | Push local branch commits to remote |
| `git log -n 5 --oneline` | View compact summary of recent 5 commits |
