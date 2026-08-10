# Complete local setup

The normal study environment is installed once and then reused by every action. A complete setup includes the Python runtime dependencies, MCP support, PDF/figure support, Pillow, Playwright and the Playwright Chromium browser.

## Windows: one step

From the repository root, run:

```text
INSTALAR-STUDY.bat
```

The installer:

1. finds Python 3.10+ (`py -3` or `python`);
2. upgrades pip;
3. installs `requirements.txt`;
4. installs Playwright Chromium;
5. runs `pip check`;
6. launches the environment preflight, including a real headless Chromium launch.

After that, normal use starts with:

```text
INICIAR-STUDY.bat
```

`INICIAR-STUDY.bat` performs the same preflight before opening the menu. If the environment is incomplete it stops immediately and asks for `INSTALAR-STUDY.bat`; it does not allow a long `/resumen` run to discover the missing browser at the end.

## Cross-platform/manual installation

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m pip check
python scripts/setup_env.py check
```

`requirements.txt` is the complete environment entrypoint and includes the focused capability files:

```text
requirements-mcp.txt
requirements-visual.txt
requirements-design.txt
```

The focused files remain useful for maintenance, but a normal user installation should use the root `requirements.txt`.

## Preflight

Human-readable check:

```bash
python scripts/setup_env.py check
```

Machine-readable check:

```bash
python scripts/setup_env.py check --json
```

The preflight verifies:

- Python >= 3.10;
- compatible MCP 1.x;
- PyMuPDF;
- Pillow;
- Playwright Python package;
- a Chromium binary that can actually launch headlessly;
- therefore, whether browser visual audit is ready.

Importing Playwright alone is deliberately insufficient because its Chromium binary is installed separately.

## Visual publication contract

Rendered `summary`, `guide` and `rapid-review` artifacts require two different gates:

1. **integrity gate** — paths, alt text, captions, figure registry, provenance and unit scope;
2. **browser visual gate** — Chromium renders desktop/tablet/mobile/print views and `visual_audit.py` checks objective layout/readability conditions.

The staged pipeline cannot finish unless `visual-audit/audit.json` reports `ok: true` and the required desktop/mobile screenshots exist. The agent must inspect rendered screenshots before claiming visual PASS.

If Chromium or Playwright is missing, that is an environment failure. It must not be converted into `SKIPPED` while still publishing or reporting that visual review passed.

## CI parity

GitHub Actions uses the same setup sequence:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
python scripts/setup_env.py check --json
```

The release suite also contains a browser smoke test that renders a synthetic study document and runs the real visual audit on Windows and Ubuntu.
