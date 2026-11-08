---
name: clean-code-patterns
description: >-
  Use this skill whenever authoring, reviewing, refactoring, or optimizing Python code across
  engines, runners, search algorithms, and utilities. Enforces strict static typing, standardized
  docstrings, single-responsibility functions, guard clauses, domain-specific design patterns
  (Strategy, Router/Factory, Pipeline, Context Manager), zero-raw-print logging, and defensive error handling.
---

# Clean Code & Design Patterns Runbook

This skill establishes micro-level programming standards, clean code principles, and architectural design patterns for the **Multimodal Video Moment Retrieval** system. All code authored in [src/](file:///d:/UIT/TX/doan/src) must strictly adhere to these guidelines.

---

## 1. Core Engineering Principles

Every Python module in this project must uphold five foundational principles:

1. **Single Responsibility Principle (SRP):** Each function, method, and class must have exactly one reason to change and do one thing with high cohesion.
2. **Flat is Better Than Nested (Guard Clauses):** Eliminate deeply nested `if/else` structures (> 2 levels) by returning early.
3. **Explicit Over Implicit:** Prefer explicit typed dataclasses and parameters over arbitrary unstructured dictionaries (`dict[str, Any]`).
4. **Defensive Resource Management:** Always release hardware resources (GPU VRAM, file descriptors, SQLite connections) via context managers (`with`) and explicit finalizers.
5. **The Zero-Raw-`print()` Rule:** All runtime information, diagnostics, and errors must be recorded through `loguru.logger` using standardized text badges (`[INFO]`, `[OK]`, `[WARNING]`, `[ERROR]`).

---

## 2. Strict Static Typing & Schema Definition

### 2.1 Function & Method Signatures
* **100% Type Annotation:** Every function parameter and return value must have explicit type annotations.
* Use Python's standard `typing` module (`Optional`, `Union`, `List`, `Dict`, `Tuple`, `Set`, `Generator`, `Callable`, `Any`).

```python
# [POOR] Untyped, ambiguous signature
def compute_rrf(results, top_k=100, weights=None):
    ...

# [CLEAN] Fully typed signature with explicit types and defaults
from typing import Dict, List, Optional, Tuple

def compute_rrf(
    ranked_lists: List[List[Tuple[str, float]]],
    top_k: int = 100,
    weights: Optional[List[float]] = None
) -> List[Tuple[str, float]]:
    ...
```

### 2.2 Domain Models via Dataclasses
* Define all structured data transfer objects (DTOs) in [src/common/types.py](file:///d:/UIT/TX/doan/src/common/types.py) using `@dataclass`.
* Do not pass ad-hoc unstructured dictionaries across layer boundaries.

```python
# [CLEAN] Strongly-typed domain record
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class CandidateMoment:
    video_id: str
    start_sec: float
    end_sec: float
    score: float
    matched_cues: List[str] = field(default_factory=list)
    keyframe_id: Optional[str] = None
```

---

## 3. Standardized Documentation & Docstrings

Every public module, class, method, and function must include a clear docstring following the Google / Sphinx docstring format:

```python
def search_hybrid(
    visual_queries: List[str],
    ocr_queries: List[str],
    top_k: int = 25
) -> List[CandidateMoment]:
    """
    Executes multimodal hybrid retrieval by fusing SigLIP2 visual embeddings
    and SQLite FTS5 text scores across temporal sliding windows.

    Args:
        visual_queries: List of natural language English visual descriptions.
        ocr_queries: List of on-screen Vietnamese or alphanumeric text tokens.
        top_k: Maximum number of fused candidate moments to return.

    Returns:
        A list of CandidateMoment instances sorted by fused score in descending order.

    Raises:
        ValueError: If both visual_queries and ocr_queries are empty.
        FileNotFoundError: If the visual FAISS index or metadata database is missing.
    """
```

---

## 4. Function Cleanliness & Guard Clauses

### 4.1 Length & Complexity Limits
* **Maximum Function Length:** Functions should not exceed **40 lines** (excluding docstrings). If a function grows longer, decompose it into private helper methods (`_helper()`).
* **Maximum Nesting Depth:** Keep cyclomatic complexity low. Never exceed **2 levels of indentation** inside a function body.

### 4.2 Guard Clauses (Early Return Pattern)
* Handle edge cases, invalid inputs, and failure conditions at the very top of the function to keep the happy path completely unindented.

```python
# [POOR] Arrow anti-pattern with deep indentation
def process_keyframe(kf, video_path):
    if kf is not None:
        if Path(video_path).exists():
            if kf.blur_score > 100.0:
                # Actual business logic buried 4 levels deep
                return extract_features(kf)
            else:
                return None
        else:
            raise FileNotFoundError("Video missing")
    return None

# [CLEAN] Guard clauses flatten execution
def process_keyframe(kf: Optional[KeyframeRecord], video_path: Path) -> Optional[np.ndarray]:
    if kf is None:
        return None
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if kf.blur_score <= 100.0:
        return None

    # Happy path sits at root indentation
    return extract_features(kf)
```

---

## 5. Logging & Defensive Exception Handling

### 5.1 Standardized Logging Badges
Always import `from loguru import logger`. Prepend logs with standard text badges:

```python
logger.info(f"[INFO] Initializing visual search with query: '{query}'")
logger.info(f"[OK] Visual index loaded successfully: {total_vectors} vectors.")
logger.warning(f"[WARNING] Keyframe image missing at {path}; falling back to center frame.")
logger.error(f"[ERROR] Failed to connect to SQLite database at {db_path}: {err}")
```

### 5.2 Explicit Exception Handling
* **Never use bare `except:` or catch generic `except Exception:` without re-raising or logging traceback.**
* Catch specific exceptions (`sqlite3.OperationalError`, `requests.RequestException`, `FileNotFoundError`).
* Always clean up hardware state in `finally:` blocks.

```python
# [CLEAN] Specific catch with context cleanup
try:
    results = index.search(query_vec, top_k=top_k)
except FileNotFoundError as e:
    logger.error(f"[ERROR] Index file not found: {e}")
    raise
except Exception as e:
    logger.exception(f"[ERROR] Unexpected failure during vector search: {e}")
    raise RuntimeError(f"Vector search failed: {e}") from e
finally:
    # Ensure memory cleanup
    del query_vec
```

---

## 6. Domain-Specific Design Patterns for Retrieval

### 6.1 Strategy Pattern (Score Fusion & Ranking)
Decouple scoring algorithms behind a common abstract strategy interface in [src/retrieval/score_fusion.py](file:///d:/UIT/TX/doan/src/retrieval/score_fusion.py), allowing swapping or ablation of fusion techniques without rewriting the search engine:

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple

class FusionStrategy(ABC):
    """Abstract strategy for combining multi-channel retrieval scores."""

    @abstractmethod
    def fuse(
        self,
        ranked_channels: Dict[str, List[Tuple[str, float]]],
        weights: Dict[str, float]
    ) -> List[Tuple[str, float]]:
        """Combine per-channel ranked lists into a single ranked list."""
        pass


class ReciprocalRankFusionStrategy(FusionStrategy):
    """Computes Reciprocal Rank Fusion (RRF) with constant k=60."""

    def __init__(self, k: int = 60):
        self.k = k

    def fuse(
        self,
        ranked_channels: Dict[str, List[Tuple[str, float]]],
        weights: Dict[str, float]
    ) -> List[Tuple[str, float]]:
        scores: Dict[str, float] = {}
        for channel, items in ranked_channels.items():
            w = weights.get(channel, 1.0)
            for rank, (doc_id, _) in enumerate(items, start=1):
                scores[doc_id] = scores.get(doc_id, 0.0) + (w / (self.k + rank))
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

### 6.2 Router / Factory Pattern (Query Decomposition)
Route multi-condition queries into specialized worker pipelines without bloated conditional statements in [src/retrieval/query_parser.py](file:///d:/UIT/TX/doan/src/retrieval/query_parser.py):

```python
@dataclass
class ParsedQuery:
    visual_cues: List[str] = field(default_factory=list)
    ocr_cues: List[str] = field(default_factory=list)
    is_sequential: bool = False
    sequence_stages: List[List[str]] = field(default_factory=list)


class QueryRouter:
    """Dispatches raw user input to appropriate modality branches."""

    @staticmethod
    def parse(raw_text: str) -> ParsedQuery:
        cleaned = raw_text.strip()
        if not cleaned:
            return ParsedQuery()

        # Check for sequence operator
        if ">>" in cleaned:
            stages = [s.strip() for s in cleaned.split(">>") if s.strip()]
            return ParsedQuery(is_sequential=True, sequence_stages=[[s] for s in stages])

        # Decompose prefixes
        visuals, ocrs = [], []
        parts = [p.strip() for p in cleaned.split("|") if p.strip()]
        for p in parts:
            if p.lower().startswith("ocr:"):
                ocrs.append(p[4:].strip().strip('"'))
            elif p.lower().startswith("v:"):
                visuals.append(p[2:].strip())
            else:
                visuals.append(p)

        return ParsedQuery(visual_cues=visuals, ocr_cues=ocrs)
```

### 6.3 Context Manager Pattern (Resource Protection)
Wrap database connections and GPU memory management in safe context managers:

```python
# [CLEAN] Context manager for safe SQLite transactions
from contextlib import contextmanager

class MetadataDB:
    @contextmanager
    def transaction(self):
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
```

---

## 7. Code Smells & Anti-Patterns Checklist

Before committing any code in [src/](file:///d:/UIT/TX/doan/src), verify against this quality checklist:

| Anti-Pattern | Description | Clean Code Resolution |
|---|---|---|
| **Raw `print()` statements** | Using `print()` instead of logging. | Replace with `logger.info()`, `logger.warning()`, or `logger.error()`. |
| **Magic Numbers** | Hardcoded constants (e.g. `60`, `0.4`, `1500`). | Extract to named constants at top of module or in [configs/default_config.yaml](file:///d:/UIT/TX/doan/configs/default_config.yaml). |
| **Arrow Code** | Deeply nested `if/for/try` indentation (> 2 levels). | Refactor with Guard Clauses and early returns. |
| **God Functions** | Functions exceeding 50 lines doing multiple unrelated tasks. | Split into smaller, single-purpose private helper functions. |
| **Silent Failures** | Using `except: pass` or ignoring exceptions. | Log the error badge `[ERROR]` and handle or re-raise explicitly. |
| **Raw String Path Manipulation** | Concatenating paths with `+ "/" +`. | Always use `pathlib.Path` objects and the `/` operator. |
| **Leaked VRAM** | Leaving PyTorch CUDA tensors in GPU memory after search. | Call `safe_unload()` and run `gc.collect()` + `torch.cuda.empty_cache()`. |
