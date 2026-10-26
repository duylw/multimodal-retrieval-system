---
name: feature-documentation-guide
description: >-
  Use this skill whenever documenting a newly completed feature, pipeline stage, or CLI tool.
  Standardizes simple, clear, concise usage documentation covering feature summary, CLI execution
  commands, argument tables, inputs/outputs, and gotchas.
---

# Feature Documentation & CLI Usage Guide Runbook

This skill defines the standardized structure and rules for writing user and CLI usage guides after completing any feature or executable pipeline module in the **Multimodal Video Moment Retrieval** project.

Core objective: **Simple - Visual - Clear - Immediately Actionable**.

---

## 1. Documentation Principles

1. **Storage Location:**
   * Every major feature or executable CLI tool must have a corresponding usage guide saved at:
     `docs/guides/<feature-name>.md` (e.g., `docs/guides/shot-keyframe-inspector.md`, `docs/guides/shot-detection-and-keyframes.md`).
2. **Language Protocol:**
   * 100% English documentation across all sections, tables, code snippets, and comments.
3. **No Icons / Emojis:**
   * Strictly adhere to project conventions. Use text badges: `[INFO]`, `[OK]`, `[WARNING]`, `[ERROR]`, `[TIP]`.
4. **No LaTeX & No Mermaid:**
   * Use clean Markdown tables or ASCII art to illustrate user interfaces and workflows.
5. **Clickable File Links:**
   * All file paths and directory references must use clickable Markdown links formatted as `file:///...`.
6. **Executable CLI Examples:**
   * All terminal commands must use `uv run python -m ...` with concrete, copy-pasteable examples.

---

## 2. Standard Guide Template

Each guide document in `docs/guides/<feature-name>.md` must adhere to these 5 core sections:

```markdown
# User Guide: [Feature / Module Name]

## 1. Feature Overview
* **What it does:** Explain in 2-3 concise, accessible sentences without overly academic jargon.
* **When to use:** Specify which pipeline stage uses this (Offline Indexing, Online Retrieval, or Debugging).
* **Value provided:** What problem it solves (e.g., shot inspection, moment retrieval, memory optimization).

---

## 2. Quick Start CLI
Provide the simplest default CLI execution command:
```powershell
uv run python -m <module_path> [basic_args]
```
Concrete example with expected console output:
```powershell
uv run python -m src.ui.debug_server
# [INFO] Starting Debug Server at http://127.0.0.1:8000
```

---

## 3. CLI Arguments & Configuration Parameters
Detail all flags, arguments, and options:

| Parameter Name | Short Flag | Data Type | Default Value | Required | Description |
|---|---|---|---|---|---|
| `--video-id` | `-v` | `str` | `None` | Yes | Target video ID to process (e.g. `L13_V001`) |
| `--threshold` | `-t` | `float` | `27.0` | No | Scene detection content threshold |
| `--port` | `-p` | `int` | `8000` | No | Web server TCP listening port |

---

## 4. Inputs & Outputs
* **Inputs:**
  * Source video: `data/raw_videos/{video_id}.mp4`
  * Database: `data/metadata.db`
  * Configuration: `configs/default_config.yaml`
* **Outputs:**
  * Image files: `data/keyframes/{video_id}/*.jpg`
  * SQLite tables: Records inserted into `shots`, `keyframes`, `checkpoints`.

---

## 5. Technical Notes & Troubleshooting
* **Hardware Constraints:** Specific VRAM, RAM, and CPU usage (guarantee under 4GB VRAM on GTX 1650).
* **Resume Capability:** How the tool behaves if re-run (e.g., skips completed checkpoints automatically).
* **Common Issues & Fixes:**
  * Issue 1: Port conflict -> How to change port via environment variable or CLI argument.
  * Issue 2: Missing video file -> Verify directory structure in `data/raw_videos/`.
```

---

## 3. Workflow Upon Task Completion

Whenever a task or feature implementation is completed:
1. Identify the primary executable entrypoint or CLI module.
2. Create `docs/guides/<feature-name>.md` following the template above.
3. Test-run the CLI command examples to ensure they execute without syntax errors.
4. Add reference links in [TRACKING.md](file:///d:/UIT/TX/doan/TRACKING.md) and [PROJECT_OVERVIEW.md](file:///d:/UIT/TX/doan/PROJECT_OVERVIEW.md).
