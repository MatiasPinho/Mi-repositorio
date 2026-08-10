# Study MCP — local stdio

El MCP es una interfaz local y opcional sobre el mismo core determinístico que usa `study.py`.
No reemplaza pipelines, skills ni archivos canónicos. Claude Code y Codex llaman herramientas MCP;
el servidor llama funciones determinísticas del core dentro del mismo proceso; no lanza subprocesses Python.

## Instalar

```powershell
python -m pip install -r requirements-mcp.txt
python study.py mcp preflight
```

La release incluye `.mcp.json` para Claude Code y `.codex/config.toml` para Codex.
Ambos lanzan `python study.py mcp serve` por `stdio`; `study.py` carga el adapter `study_mcp/` y no se abre ningún puerto.

## Tools V1

Lectura:
- `study_list_courses`
- `study_material_changes`
- `study_list_units`
- `study_get_course_context`
- `study_get_unit_context`
- `study_get_progress`
- `study_list_figures`
- `study_verify_figures`
- `study_list_artifacts`
- `study_validate_artifact`
- `study_validate_course`

Escritura segura:
- `study_register_derived_figure` — usa el helper collision-safe de `figure_assets.py`; no sobrescribe IDs/assets.
- `study_mark_artifact` — usa directamente el helper de `artifact_state.py`.

## Resources

- `study://courses`
- `study://course/{course}/academic`
- `study://course/{course}/units`
- `study://course/{course}/unit/{unit}/context`
- `study://course/{course}/progress`

## Política de uso

Cuando el MCP está disponible, los agentes deben preferirlo para leer contexto canónico y para las
operaciones expuestas arriba. `study_get_unit_context` devuelve también las
rutas canónicas de la unidad, y las lecturas agregadas nunca cambian su
propiedad. El filesystem sigue disponible para escribir handoffs, drafts, SVGs y
otros archivos que todavía no tienen una operación MCP. Si el MCP no está conectado, los pipelines
siguen funcionando mediante `study.py` y `scripts/` sin degradación funcional.

No se exponen herramientas de borrado, reset, edición arbitraria de JSON ni publicación libre en V1.


## Diseño de compatibilidad

`requirements-mcp.txt` fija la línea MCP Python SDK 1.x. El adapter está separado del core para que una futura actualización del protocolo afecte sólo esta capa y no obligue a migrar `academic.json`, los registros por unidad ni los pipelines.

## Test stdio end-to-end

Con el SDK MCP instalado, la suite levanta un servidor real por `stdio`, negocia una sesión de cliente, lista las 13 tools V4 y ejecuta cada una con timeout:

```powershell
python -m unittest tests.test_mcp.StudyMCPTests.test_stdio_e2e_curated_tools_return_without_hanging -v
```

Si `mcp` no está instalado, ese único test se marca como `skipped`; los tests del core in-process siguen ejecutándose. La lista exacta de tools se valida dinámicamente para incluir las operaciones V4.
