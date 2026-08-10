# Runtime Safety and Publication Contract

This protocol protects staged study runs (`resumen`, `guia`, `repaso`) from two classes of failure discovered with real course material: repairing the engine during a study action, and publishing a copy that differs from the validated render.

## 1. The study engine is immutable during a run

`pipeline_run.py start` records a SHA-256 snapshot of the checked-in engine surface in `manifest.json -> engine_snapshot`.

Protected surfaces include:

- `scripts/`
- `pipelines/`
- `rules/`
- `config/`
- `contracts/`
- `core/`
- `design/`
- `study_mcp/`
- `tests/`
- root runtime/setup files such as `study.py`, `unit_identity.py`, requirements files, MCP configs and Windows launch/install BATs.

Python cache files are ignored.

At validation/finish time the snapshot is recomputed. Added, removed or changed engine files produce deterministic errors such as:

```text
engine-added:scripts/local_fix.py
engine-removed:rules/evaluation/example.md
engine-modified:scripts/visual_audit.py
```

A staged study action must not repair these files and then continue. If an engine capability fails, report `ENGINE FAILURE`, fix the engine in a separate development branch/PR, and rerun the study action from a fresh run.

Run-local scratch code remains allowed under `<run-dir>/scratch/`. Persistent ad-hoc scripts in the course tree are separately rejected by the existing course-script snapshot.

## 2. Browser audit must prove images actually loaded

A full-page screenshot can look blank below the initial viewport when Chromium has not triggered `loading="lazy"` images. Therefore `visual_audit.py` does not treat the presence of `<img>` elements or valid paths as sufficient evidence.

Before capturing each viewport the auditor:

1. changes document images to eager loading;
2. scrolls through the complete document to trigger viewport-based loading;
3. waits for `load` / `error` completion;
4. awaits `HTMLImageElement.decode()` when available;
5. records `complete`, `naturalWidth` and `naturalHeight` for every image;
6. fails the viewport when any image has not resolved to non-zero natural dimensions.

The report exposes `images`, `loadedImages` and `image_states` per viewport. A successful visual audit therefore means the figures were not merely referenced; they were actually decoded by Chromium before the screenshot.

## 3. Publication is byte-for-byte verified

After academic review, render integrity and browser visual audit pass, the staged pipeline publishes through:

```bash
python scripts/venv_exec.py scripts/publish_artifact.py \
  --markdown <accepted-md> \
  --html <run-dir>/09-rendered.html \
  --dest-markdown <published-source.md> \
  --dest-html <published.html> \
  --report <run-dir>/11-publication.json
```

The publisher:

1. reads the already validated Markdown and HTML bytes;
2. stages each destination in a temporary file located in the destination directory;
3. verifies the staged SHA-256 before replacement;
4. replaces destinations with `os.replace`;
5. verifies destination SHA-256 and byte count again;
6. restores the previous published files if the pair cannot complete successfully;
7. writes `11-publication.json` only after successful verification.

The publication report contains, for Markdown and HTML:

```json
{
  "role": "html",
  "source": ".../09-rendered.html",
  "destination": ".../resumenes/unidad-1-resumen.html",
  "source_sha256": "...",
  "destination_sha256": "...",
  "bytes": 12345
}
```

`pipeline_run.py finish` rejects missing publication evidence, destinations outside the course `resumenes/` tree, wrong source files, missing files, size mismatch, or any source/destination hash mismatch.

## 4. Order of operations

```text
academic review
  ↓
accepted Markdown
  ↓
render candidate
  ↓
integrity gate
  ↓
Chromium visual gate
  ├─ all lazy images decoded
  └─ screenshots inspected
  ↓
atomic verified publication
  ↓
11-publication.json
  ↓
artifact fingerprint registration
  ↓
pipeline finish
  ├─ publication hashes match
  └─ engine snapshot unchanged
```

A failure at any gate blocks a truthful PASS claim. In particular, an agent must not publish first and then repair the published copy with an editor/copy tool; it must rerun the verified publication step from the validated run artifact.

## Regression tests

The release suite includes regressions for:

- six lazy images positioned far below the initial mobile viewport all decoding before capture;
- corrupted published HTML being rejected by hash verification;
- engine mutation being rejected by the run snapshot;
- large HTML replacement completing without truncation or temporary-file leakage.
