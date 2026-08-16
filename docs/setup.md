# Complete local setup

The normal study environment is installed once and then reused by every action. It lives in a repository-local `.venv`, so unrelated packages from the user's global Python installation cannot break Carpeta.

A complete setup includes the Python runtime dependencies, MCP support, PDF/figure support, Pillow, Playwright, the Playwright Chromium browser and a machine-local OpenCode MCP configuration.

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
6. runs `pip check` and the full environment preflight;
7. generates the local `opencode.json` with the correct Windows venv path for `university-study`.

Global Python packages are deliberately ignored.

After that, normal use starts with:

```text
INICIAR-STUDY.bat
```

`INICIAR-STUDY.bat` always uses `.venv\Scripts\python.exe`. It performs the same preflight before opening the menu. If `.venv` is absent or incomplete it stops immediately and asks for `INSTALAR-STUDY.bat`.

## Linux: one step

From the repository root, run:

```bash
bash INSTALAR-STUDY.sh
```

The Linux installer mirrors the Windows setup:

1. finds `python3` or `python` with Python 3.10+;
2. creates `.venv` at `.venv/bin/python`;
3. installs the complete dependency set inside the venv;
4. installs Playwright Chromium;
5. runs `pip check` and the full environment preflight;
6. generates the local `opencode.json` with the Linux venv interpreter and enables the `university-study` MCP server.

After that, normal use starts with:

```bash
bash INICIAR-STUDY.sh
```

No global `python` alias is required after installation: OpenCode is configured to launch the repository-local `.venv/bin/python` directly.

## OpenCode MCP configuration

`opencode.json` is generated locally because the venv interpreter path is platform-specific:

- Windows: `.venv/Scripts/python.exe`
- Linux/POSIX: `./.venv/bin/python`

The generated project config registers `university-study` as a local stdio MCP server and runs:

```text
<venv-python> study.py mcp serve
```

The file is intentionally ignored by Git. `scripts/configure_opencode.py` preserves other settings already present in a valid `opencode.json` and only creates or updates the `mcp.university-study` entry.

To verify the OpenCode connection after setup:

```bash
opencode mcp list
```

OpenCode should show `university-study` as connected. OpenCode starts and owns the stdio server process; it should not be kept running manually in another terminal.

## Agent/MCP execution

Claude Code and Codex can still use the portable standard-library shim:

```text
python scripts/venv_exec.py study.py mcp serve
```

The shim immediately re-executes the requested command with the repository-local `.venv` Python. This keeps MCP and dependency-heavy pipeline commands isolated from global packages.

For direct project commands in pipeline instructions, use the same pattern when a host `python` command exists:

```text
python scripts/venv_exec.py study.py status programacion-i
python scripts/venv_exec.py scripts/visual_audit.py archivo.html --out salida
```

On Linux, commands can also invoke the venv directly:

```bash
./.venv/bin/python study.py status programacion-i
```

## Cross-platform/manual installation

If the platform installers cannot be used, create the project venv first and use its interpreter. On Linux:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m playwright install chromium
./.venv/bin/python -m pip check
./.venv/bin/python scripts/setup_env.py check
./.venv/bin/python scripts/configure_opencode.py
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
