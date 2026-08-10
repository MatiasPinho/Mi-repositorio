# Complete local setup

The normal study environment is installed once and then reused by every action. It lives in a repository-local `.venv`, so unrelated packages from the user's global Python installation cannot break the study system.

A complete setup includes the Python runtime dependencies, MCP support, PDF/figure support, Pillow, Playwright and the Playwright Chromium browser.

## Windows: one step

From the repository root, run:

```text
INSTALAR-STUDY.bat
```

The installer:

1. finds a base Python 3.10+ (`py -3` or `python`);
2. creates `.venv` if it does not exist;
3. upgrades pip **inside `.venv`**;
4. installs `requirements.txt` **inside `.venv`**;
5. installs Playwright Chromium using the venv interpreter;
6. runs `pip check` inside the isolated environment;
7. launches the environment preflight, including a real headless Chromium launch.

Global Python packages are deliberately ignored. A conflict such as an unrelated global FastAPI/Starlette installation must not affect University Study System.

After that, normal use starts with:

```text
INICIAR-STUDY.bat
```

`INICIAR-STUDY.bat` always uses `.venv\Scripts\python.exe`. It performs the same preflight before opening the menu. If `.venv` is absent or incomplete it stops immediately and asks for `INSTALAR-STUDY.bat`.

## Agent/MCP execution

Claude Code and Codex MCP configs invoke the standard-library shim:

```text
python scripts/venv_exec.py study.py mcp serve
```

The shim immediately re-executes the requested command with the repository-local `.venv` Python. This keeps MCP and dependency-heavy pipeline commands isolated even when the host shell's `python` points to a global installation.

For direct project commands in pipeline instructions, use the same pattern:

```text
python scripts/venv_exec.py study.py status programacion-i
python scripts/venv_exec.py scripts/visual_audit.py archivo.html --out salida
```

## Cross-platform/manual installation

Create the project venv first:

```bash
python -m venv .venv
```

Then use its interpreter. The portable shim resolves `.venv/Scripts/python.exe` on Windows and `.venv/bin/python` on POSIX:

```bash
python scripts/venv_exec.py -m pip install --upgrade pip
python scripts/venv_exec.py -m pip install -r requirements.txt
python scripts/venv_exec.py -m playwright install chromium
python scripts/venv_exec.py -m pip check
python scripts/venv_exec.py scripts/setup_env.py check
```

`requirements.txt` is the complete environment entrypoint and includes:

```text
requirements-mcp.txt
requirements-visual.txt
requirements-design.txt
```

The focused files remain useful for maintenance, but normal installation should use the root `requirements.txt` inside `.venv`.

## Preflight

Human-readable check:

```bash
python scripts/venv_exec.py scripts/setup_env.py check
```

Machine-readable check:

```bash
python scripts/venv_exec.py scripts/setup_env.py check --json
```

The preflight verifies:

- Python >= 3.10;
- execution from this repository's `.venv`;
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

GitHub Actions creates the same isolated `.venv` on both Windows and Ubuntu:

```bash
python -m venv .venv
python scripts/venv_exec.py -m pip install -r requirements.txt
python scripts/venv_exec.py -m playwright install chromium
python scripts/venv_exec.py -m pip check
python scripts/venv_exec.py scripts/setup_env.py check --json
```

The release suite also contains a browser smoke test that renders a synthetic study document and runs the real visual audit on Windows and Ubuntu.
