from __future__ import annotations

import ast
import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from study_mcp import service


class StudyMCPTests(unittest.TestCase):
    def setUp(self):
        self.slug = "zz-mcp-" + uuid.uuid4().hex[:8]
        self.course = ROOT / "materias" / self.slug
        for sub in ["academico", "conocimiento", "progreso", "fuentes", "assets/figures", ".study", "notas", "preguntas", "resumenes/_source", "simulacros"]:
            (self.course / sub).mkdir(parents=True, exist_ok=True)
        (self.course / "academico" / "academic.json").write_text(json.dumps({
            "version": 1,
            "identity": {"subject": "MCP Test"},
            "units": [{"id": "U1", "name": "Unidad 1: Base"}, {"id": "U2", "name": "Unidad 2: Siguiente"}],
            "assessments": [{"id": "p1", "type": "parcial", "name": "Parcial 1", "scope": [{"kind": "unit", "ref": "U1", "status": "confirmed", "evidence": "fixture"}]}],
            "rules": [{"id": "r1", "text": "Regla global"}],
            "conflicts": [],
            "open_questions": [],
        }, ensure_ascii=False), encoding="utf-8")
        (self.course / "conocimiento" / "concepts.json").write_text(json.dumps({
            "version": 2,
            "concepts": {
                "base": {"id": "base", "name": "Base", "unit": "U1", "unit_id": "unidad-1"},
                "next": {"id": "next", "name": "Next", "unit": "U2", "unit_id": "unidad-2", "prerequisites": ["Base"]},
            },
        }), encoding="utf-8")
        (self.course / "conocimiento" / "figures.json").write_text(json.dumps({
            "version": 2,
            "figures": {
                "u1-source": {"id": "u1-source", "unit": "U1", "unit_id": "unidad-1", "origin": "source", "asset": None}
            },
        }), encoding="utf-8")
        (self.course / "progreso" / "progress.json").write_text(json.dumps({
            "version": 2,
            "concepts": {
                "base": {"id": "base", "name": "Base", "mastery": 0.4, "attempts": 1},
                "next": {"id": "next", "name": "Next", "mastery": 0.0, "attempts": 0},
            },
        }), encoding="utf-8")
        (self.course / "contexto.md").write_text("# MCP Test\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.course, ignore_errors=True)

    def test_unit_context_is_coarse_grained_and_stable(self):
        data = service.get_unit_context(self.slug, "Unidad 1")
        self.assertEqual(data["unit"]["unit_id"], "unidad-1")
        self.assertIn("base", data["concepts"])
        self.assertNotIn("next", data["concepts"])
        self.assertIn("u1-source", data["figures"])
        self.assertEqual(data["progress"]["base"]["mastery"], 0.4)
        self.assertEqual(data["academic_constraints"]["rules"][0]["id"], "r1")

    def test_mcp_derived_figure_write_delegates_to_collision_safe_core(self):
        asset = self.course / "assets" / "figures" / "derived.svg"
        asset.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
        result = service.register_derived_figure(
            self.slug, "mapa", "U1", "assets/figures/derived.svg", "Mapa", ["concept:base"], concepts=["Base"]
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["key"], "derived:mapa")
        registry = json.loads((self.course / "conocimiento" / "figures.json").read_text(encoding="utf-8"))
        self.assertEqual(registry["figures"]["derived:mapa"]["unit_id"], "unidad-1")
        with self.assertRaises(service.StudyMCPError):
            service.register_derived_figure(
                self.slug, "mapa", "U1", "assets/figures/derived.svg", "Otra", ["concept:base"]
            )

    def test_configs_are_local_stdio_and_no_port_is_configured(self):
        claude = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        row = claude["mcpServers"]["university-study"]
        self.assertEqual(row["type"], "stdio")
        self.assertEqual(row["command"], "python")
        self.assertEqual(row["args"], ["scripts/venv_exec.py", "study.py", "mcp", "serve"])
        self.assertNotIn("url", row)
        codex = (ROOT / ".codex" / "config.toml").read_text(encoding="utf-8")
        self.assertIn("[mcp_servers.university-study]", codex)
        self.assertIn('command = "python"', codex)
        self.assertIn('args = ["scripts/venv_exec.py", "study.py", "mcp", "serve"]', codex)
        self.assertNotIn("http", codex.lower())

    def test_server_exposes_only_curated_tools_and_resources(self):
        tree = ast.parse((ROOT / "study_mcp" / "server.py").read_text(encoding="utf-8"))
        tools = set()
        resources = set()
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in node.decorator_list:
                if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute) and isinstance(deco.func.value, ast.Name) and deco.func.value.id == "mcp":
                    if deco.func.attr == "tool":
                        tools.add(node.name)
                    if deco.func.attr == "resource" and deco.args and isinstance(deco.args[0], ast.Constant):
                        resources.add(deco.args[0].value)
        self.assertEqual(tools, {
            "study_list_courses", "study_material_changes", "study_get_course_context", "study_get_unit_context",
            "study_get_progress", "study_list_figures", "study_verify_figures", "study_register_derived_figure",
            "study_list_artifacts", "study_validate_artifact", "study_mark_artifact", "study_validate_course",
        })
        self.assertEqual(len(resources), 4)
        self.assertFalse(any(x in tools for x in {"delete_file", "reset_course", "write_json", "publish_arbitrary"}))

    def test_mcp_preflight_is_machine_readable_even_without_optional_sdk(self):
        cp = subprocess.run(
            [sys.executable, str(ROOT / "study.py"), "mcp", "preflight", "--json"],
            cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", check=True,
        )
        payload = json.loads(cp.stdout)
        self.assertEqual(payload["transport"], "stdio")
        self.assertIn("available", payload)
        if not payload["available"]:
            self.assertIn("requirements-mcp.txt", payload["install"])

    def test_mcp_requirement_is_pinned_to_legacy_compatible_major(self):
        req = (ROOT / "requirements-mcp.txt").read_text(encoding="utf-8")
        self.assertIn("mcp>=1.28,<2", req)

    def test_artifact_tools_use_in_process_core(self):
        md = self.course / "resumenes" / "_source" / "unidad-1-resumen.md"
        html = self.course / "resumenes" / "unidad-1-resumen.html"
        md.write_text("# Resumen\n\nContenido.\n", encoding="utf-8")
        html.write_text("<!doctype html><html><body><h1>Resumen</h1><p>Contenido.</p></body></html>", encoding="utf-8")

        listed = service.list_artifacts(self.slug)
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["artifacts"][0]["file"], "resumenes/unidad-1-resumen.html")
        self.assertTrue(listed["artifacts"][0]["stale"])

        integrity = service.validate_artifact(self.slug, str(md), str(html), "Unidad 1", "summary")
        self.assertTrue(integrity["ok"], integrity)

        marked = service.mark_artifact(self.slug, "resumenes/unidad-1-resumen.html", "summary", "Unidad 1")
        self.assertFalse(marked["stale"], marked)

        listed_after = service.list_artifacts(self.slug)
        self.assertEqual(listed_after["count"], 1)
        self.assertFalse(listed_after["artifacts"][0]["stale"], listed_after)

        validated = service.validate_course(self.slug)
        self.assertTrue(validated["ok"], validated)

    def test_service_never_spawns_child_python_processes(self):
        source = (ROOT / "study_mcp" / "service.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertNotIn("subprocess", imports)
        self.assertNotIn("subprocess.run", source)
        self.assertNotIn("Popen(", source)
        self.assertNotIn("def _run(", source)

    def test_stdio_e2e_curated_tools_return_without_hanging(self):
        if importlib.util.find_spec("mcp") is None:
            self.skipTest("MCP SDK not installed; install requirements-mcp.txt to run stdio E2E")

        published_md = self.course / "resumenes" / "_source" / "unidad-1-resumen.md"
        published_html = self.course / "resumenes" / "unidad-1-resumen.html"
        published_md.write_text("# MCP E2E\n\nContenido de prueba.\n", encoding="utf-8")
        published_html.write_text("<!doctype html><html><body><h1>MCP E2E</h1><p>Contenido de prueba.</p></body></html>", encoding="utf-8")
        derived_asset = self.course / "assets" / "figures" / "e2e.svg"
        derived_asset.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")

        async def run_e2e():
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(ROOT / "study.py"), "mcp", "serve"],
                env=env,
            )

            async def call(session, name, arguments):
                result = await asyncio.wait_for(session.call_tool(name, arguments=arguments), timeout=10)
                is_error = getattr(result, "isError", getattr(result, "is_error", False))
                self.assertFalse(is_error, f"MCP tool returned error: {name}: {result}")
                structured = getattr(result, "structuredContent", getattr(result, "structured_content", None))
                if structured is not None:
                    return structured
                for block in getattr(result, "content", []):
                    text = getattr(block, "text", None)
                    if text:
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            continue
                return result

            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await asyncio.wait_for(session.initialize(), timeout=10)
                    listed = await asyncio.wait_for(session.list_tools(), timeout=10)
                    tool_names = {tool.name for tool in listed.tools}
                    expected = {
                        "study_list_courses", "study_material_changes", "study_get_course_context", "study_get_unit_context",
                        "study_get_progress", "study_list_figures", "study_verify_figures", "study_register_derived_figure",
                        "study_list_artifacts", "study_validate_artifact", "study_mark_artifact", "study_validate_course",
                    }
                    self.assertEqual(tool_names, expected)

                    await call(session, "study_list_courses", {})
                    await call(session, "study_material_changes", {"course": self.slug})
                    await call(session, "study_get_course_context", {"course": self.slug})
                    unit = await call(session, "study_get_unit_context", {"course": self.slug, "unit": "Unidad 1"})
                    self.assertEqual(unit["unit"]["unit_id"], "unidad-1")
                    await call(session, "study_get_progress", {"course": self.slug, "unit": "Unidad 1"})
                    await call(session, "study_list_figures", {"course": self.slug, "unit": "Unidad 1"})
                    verified = await call(session, "study_verify_figures", {"course": self.slug})
                    self.assertTrue(verified["ok"])

                    registered = await call(session, "study_register_derived_figure", {
                        "course": self.slug,
                        "figure_id": "e2e-map",
                        "unit": "Unidad 1",
                        "asset": "assets/figures/e2e.svg",
                        "description": "E2E map",
                        "based_on": ["concept:base"],
                        "concepts": ["Base"],
                    })
                    self.assertTrue(registered["ok"])

                    artifacts = await call(session, "study_list_artifacts", {"course": self.slug})
                    self.assertIn("artifacts", artifacts)
                    integrity = await call(session, "study_validate_artifact", {
                        "course": self.slug,
                        "markdown": str(published_md),
                        "html": str(published_html),
                        "scope": "Unidad 1",
                        "artifact_type": "summary",
                    })
                    self.assertTrue(integrity["ok"], integrity)
                    marked = await call(session, "study_mark_artifact", {
                        "course": self.slug,
                        "file": "resumenes/unidad-1-resumen.html",
                        "artifact_type": "summary",
                        "scope": "Unidad 1",
                    })
                    self.assertFalse(marked["stale"], marked)
                    validated = await call(session, "study_validate_course", {"course": self.slug})
                    self.assertTrue(validated["ok"], validated)

        asyncio.run(asyncio.wait_for(run_e2e(), timeout=35))


if __name__ == "__main__":
    unittest.main()
