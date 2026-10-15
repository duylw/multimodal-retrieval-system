---
name: vram-safe-embedding
description: >-
  Use this skill whenever executing, optimizing, or implementing feature extraction, visual
  embeddings (SigLIP2), speech transcription (faster-whisper), or audio models on hardware-constrained
  GPUs (specifically NVIDIA GeForce GTX 1650 with 4GB VRAM). Enforces sequential staging, safe batching,
  fallback triggers, and memory cleanup.
---

# VRAM-Safe Embedding & GPU Pipeline Runbook

This skill defines strict execution procedures to prevent Out-Of-Memory (OOM) errors and hardware lockups on an NVIDIA GeForce GTX 1650 (4GB VRAM).

---

## 1. Sequential Staging Protocol (Rule of Staging)

Never load or execute two deep learning models simultaneously on the GPU. All offline video processing must execute in isolated sequential stages:

```
Stage 1: Shot Detection & Keyframe Extraction (CPU / NVDEC)
   --> Output: Keyframe JPEG images saved to data/keyframes/{video_id}/
   --> Status: Video decoded and frames flushed to disk.

Stage 2: Visual Embedding Extraction (GPU: SigLIP2)
   --> Model: SigLIP2-so400m-patch14-384 (or fallback Base) in FP16.
   --> Output: Keyframe vectors and shot-level pooled vectors saved to disk.
   --> Action: Delete SigLIP2 model and call gc.collect() + torch.cuda.empty_cache().

Stage 3: Speech-to-Text Transcription (GPU: faster-whisper)
   --> Input: Extracted 16kHz WAV audio.
   --> Filter: Run Silero-VAD first to skip silent chunks.
   --> Model: faster-whisper large-v3-turbo with compute_type="int8".
   --> Output: Structured text segments with start/end timestamps saved to SQLite.
   --> Action: Delete temporary WAV file immediately and release GPU memory.

Stage 4: Text & OCR Processing (CPU Multiprocessing)
   --> Run PaddleOCR and text embedding (bge-m3) on CPU.
```

---

## 2. SigLIP2 Execution Guidelines & Fallback Triggers

### A. Precision & Batch Sizing
* Precision: Always use `torch.float16`. Never use `torch.float32` on GPU.
* Primary Model: `google/siglip2-so400m-patch14-384`.
  * Safe Batch Size: `batch_size = 4` (Maximum `batch_size = 8`).
  * If processing single frames, use `torch.inference_mode()` with `torch.cuda.amp.autocast()`.

### B. Fallback Triggers
Measure extraction speed on the first 100 keyframes:
* If VRAM usage exceeds 3.2GB (leaving < 800MB buffer for OS and CUDA runtime):
  -> Immediately fallback to `google/siglip2-base-patch16-256`.
* If processing speed drops below 4 frames per second:
  -> Immediately fallback to `google/siglip2-base-patch16-256` or `google/siglip-base-patch16-224`.
* The Base model occupies under 400MB VRAM in FP16 and achieves 25-40 FPS on GTX 1650.

---

## 3. GPU Memory Cleanup Pattern

Always wrap inference loops in a `try...finally` block to ensure memory release:

```python
import gc
import torch

def safe_unload_model(model):
    """Releases GPU memory occupied by PyTorch models."""
    try:
        del model
    except Exception:
        pass
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
```

---

## 4. Disk & Audio Management

* Temporary Audio: When extracting audio for Whisper, save to `data/audio_temp/{video_id}.wav`.
* Deletion: Call `os.remove(wav_path)` immediately after transcription completes.
* Threshold: The `data/` folder must never exceed 30GB of intermediate artifacts.
