[CmdletBinding()]
param(
    [string]$Source = (Get-Location).Path,
    [string]$Repository = "https://github.com/MatiasPinho/Mi-repositorio.git",
    [string]$Target = "",
    [string]$Branch = "dev"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

$Source = (Resolve-Path $Source).Path
if (-not (Test-Path (Join-Path $Source "study.py"))) {
    throw "No encuentro study.py en '$Source'. Ejecutá este script desde la raíz de University Study System o pasá -Source."
}
if (-not (Test-Path (Join-Path $Source "VERSION"))) {
    throw "No encuentro VERSION en '$Source'."
}

$version = (Get-Content (Join-Path $Source "VERSION") -Raw).Trim()
Write-Step "Fuente detectada: $Source (V$version)"

$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
    throw "Git no está instalado o no está en PATH. Instalá Git for Windows y volvé a ejecutar el script."
}

if ([string]::IsNullOrWhiteSpace($Target)) {
    $parent = Split-Path $Source -Parent
    $Target = Join-Path $parent "university-study-git"
}
$Target = [System.IO.Path]::GetFullPath($Target)

if (Test-Path $Target) {
    throw "El destino ya existe: $Target. Renombralo/eliminalo o pasá otro -Target. No voy a sobrescribirlo."
}

Write-Step "Clonando el repositorio en $Target"
& git clone $Repository $Target
if ($LASTEXITCODE -ne 0) { throw "git clone falló." }

Push-Location $Target
try {
    Write-Step "Preparando rama $Branch"
    & git fetch origin
    if ($LASTEXITCODE -ne 0) { throw "git fetch falló." }

    & git show-ref --verify --quiet "refs/remotes/origin/$Branch"
    if ($LASTEXITCODE -eq 0) {
        & git checkout -B $Branch "origin/$Branch"
    } else {
        & git checkout -B $Branch
    }
    if ($LASTEXITCODE -ne 0) { throw "No pude preparar la rama $Branch." }

    Write-Step "Copiando el engine completo y las materias locales"
    $excludeDirs = @(".git", ".venv", "venv", "__pycache__", "visual-tests")
    $excludeFiles = @("*.pyc", "*.pyo", "*.zip")

    $robocopyArgs = @($Source, $Target, "/E", "/R:1", "/W:1", "/NFL", "/NDL", "/NJH", "/NJS", "/NP")
    foreach ($d in $excludeDirs) { $robocopyArgs += @("/XD", (Join-Path $Source $d)) }
    foreach ($f in $excludeFiles) { $robocopyArgs += @("/XF", $f) }
    & robocopy @robocopyArgs | Out-Host
    $rc = $LASTEXITCODE
    if ($rc -ge 8) { throw "robocopy falló con código $rc." }

    Write-Step "Instalando reglas de privacidad y CI"
    $gitignore = @'
__pycache__/
*.pyc
*.pyo
.venv/
venv/
.DS_Store
*.zip

# Private academic data stays local. Keep only the public template.
materias/*
!materias/_plantilla/
!materias/_plantilla/**

# Ephemeral pipeline state and visual-test output
**/.study/runs/
visual-tests/

# Local editor / OS noise
.vscode/
.idea/
'@
    Set-Content -Path ".gitignore" -Value $gitignore -Encoding UTF8

    New-Item -ItemType Directory -Force -Path ".github/workflows" | Out-Null
    $ci = @'
name: University Study CI

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  release-tests:
    name: ${{ matrix.os }} · Python 3.11
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]

    steps:
      - name: Checkout
        uses: actions/checkout@v6

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install test/runtime dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements-mcp.txt -r requirements-visual.txt
          python -m pip check

      - name: MCP preflight
        run: python study.py mcp preflight --json

      - name: Verify generated agent assets
        run: python scripts/sync_agent_assets.py verify

      - name: Run release suite
        run: python tests/run_release_tests.py
'@
    Set-Content -Path ".github/workflows/ci.yml" -Value $ci -Encoding UTF8

    New-Item -ItemType Directory -Force -Path "docs" | Out-Null
    $devDoc = @'
# Development workflow

GitHub is the source of truth for the University Study engine. Personal courses stay local and are ignored by Git.

- `main`: stable engine.
- `dev`: integration branch used for iteration and CI.
- CI runs the release suite on Windows and Linux with Python 3.11.
- `materias/*` remains local except `materias/_plantilla/**`.
- Paid/model evals are intentionally separate from deterministic CI.

After bootstrap, normal engine updates are `git pull`; no ZIP migration is required.
'@
    Set-Content -Path "docs/development.md" -Value $devDoc -Encoding UTF8

    # Keep the bootstrap itself in the engine for reproducibility.
    $self = $MyInvocation.MyCommand.Path
    if ($self -and (Test-Path $self)) {
        New-Item -ItemType Directory -Force -Path "scripts" | Out-Null
        Copy-Item $self "scripts/bootstrap-github.ps1" -Force
    }

    Write-Step "Comprobando que una materia privada quede ignorada"
    $privateCourses = Get-ChildItem "materias" -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne "_plantilla" }
    if ($privateCourses) {
        $probe = Join-Path $privateCourses[0].FullName "contexto.md"
        if (Test-Path $probe) {
            & git check-ignore --quiet $probe
            if ($LASTEXITCODE -ne 0) {
                throw "Protección de privacidad falló: $probe no está siendo ignorado por Git. Abortando antes de git add."
            }
            Write-Host "OK: $($privateCourses[0].Name) está ignorada." -ForegroundColor Green
        }
    }

    Write-Step "Ejecutando la suite local antes de subir"
    & python tests/run_release_tests.py
    if ($LASTEXITCODE -ne 0) { throw "La suite local falló. No se hizo commit ni push." }

    Write-Step "Preparando commit del engine"
    & git add -A
    if ($LASTEXITCODE -ne 0) { throw "git add falló." }

    # Hard privacy guard: no private course may be staged.
    $staged = @(& git diff --cached --name-only)
    $privateStaged = @($staged | Where-Object { $_ -match '^materias/' -and $_ -notmatch '^materias/_plantilla/' })
    if ($privateStaged.Count -gt 0) {
        & git reset | Out-Null
        throw "Abortado: se intentaron stagear archivos privados: $($privateStaged -join ', ')"
    }

    if (-not (& git config user.name)) {
        & git config user.name "MatiasPinho"
    }
    if (-not (& git config user.email)) {
        & git config user.email "101824576+MatiasPinho@users.noreply.github.com"
    }

    & git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "No hay cambios para subir." -ForegroundColor Yellow
    } else {
        & git commit -m "Make repository executable and add cross-platform CI"
        if ($LASTEXITCODE -ne 0) { throw "git commit falló." }
    }

    Write-Step "Subiendo $Branch a GitHub"
    & git push -u origin $Branch
    if ($LASTEXITCODE -ne 0) {
        throw "git push falló. Si Git pide autenticación, completala con Git Credential Manager/GitHub y ejecutá de nuevo el script."
    }

    Write-Host "`nLISTO" -ForegroundColor Green
    Write-Host "Working clone: $Target"
    Write-Host "Branch: $Branch"
    Write-Host "Tus materias privadas fueron copiadas localmente pero no se subieron."
    Write-Host "GitHub Actions debería arrancar automáticamente para la rama $Branch."
} finally {
    Pop-Location
}
