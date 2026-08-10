import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "scripts" / "figure_assets.py"
RENDER = ROOT / "scripts" / "render_study.py"
INTEGRITY = ROOT / "scripts" / "artifact_integrity.py"
ARTIFACT = ROOT / "scripts" / "artifact_state.py"


class InfrastructureHardeningTests(unittest.TestCase):
    def setUp(self):
        self.slug = "zz-infra-" + uuid.uuid4().hex[:8]
        self.course = ROOT / "materias" / self.slug
        (self.course / "academico").mkdir(parents=True)
        (self.course / "conocimiento").mkdir()
        (self.course / "assets" / "figures").mkdir(parents=True)
        (self.course / "resumenes" / "_source").mkdir(parents=True)
        (self.course / "academico" / "academic.json").write_text(json.dumps({
            "identity": {"subject": "Infra Test"},
            "units": [{"id": "U1", "name": "Unidad 1: Conceptos básicos"}],
        }), encoding="utf-8")
        (self.course / "conocimiento" / "concepts.json").write_text(json.dumps({
            "version": 2,
            "concepts": {"x": {"id": "x", "name": "X", "unit": "U1", "unit_id": "unidad-1"}},
        }), encoding="utf-8")
        (self.course / "conocimiento" / "figures.json").write_text(json.dumps({"version": 2, "figures": {}}), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.course, ignore_errors=True)

    def run_cli(self, script, *args, check=True):
        return subprocess.run([sys.executable, str(script), *args], cwd=ROOT, text=True, capture_output=True, check=check)

    def test_visual_preflight_never_fails_when_optional_dependency_is_missing(self):
        cp = self.run_cli(FIG, "preflight")
        payload = json.loads(cp.stdout)
        self.assertIn("pdf_visuals", payload)
        self.assertIn("pymupdf", payload)
        if not payload["pdf_visuals"]:
            self.assertIn("requirements-visual.txt", payload["install"])

    def test_derived_registration_namespaces_id_resolves_unit_and_refuses_collision(self):
        asset = self.course / "assets" / "figures" / "derived-diagram.svg"
        asset.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
        cp = self.run_cli(
            FIG, "register-derived", "--course", self.slug,
            "--id", "diagram", "--unit", "Unidad 1", "--asset", "assets/figures/derived-diagram.svg",
            "--description", "Diagrama derivado", "--based-on", "concept:x",
        )
        payload = json.loads(cp.stdout)
        self.assertEqual(payload["key"], "derived:diagram")
        record = payload["record"]
        self.assertEqual(record["unit_id"], "unidad-1")
        self.assertEqual(record["origin"], "derived")
        self.assertEqual(record["based_on"], ["concept:x"])

        again = self.run_cli(
            FIG, "register-derived", "--course", self.slug,
            "--id", "diagram", "--unit", "U1", "--asset", "assets/figures/derived-diagram.svg",
            "--description", "No overwrite", "--based-on", "concept:x", check=False,
        )
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("refusing overwrite", again.stderr + again.stdout)

    def test_integrity_gate_counts_registered_figures_by_stable_unit_id(self):
        asset = self.course / "assets" / "figures" / "derived-diagram.svg"
        asset.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
        self.run_cli(
            FIG, "register-derived", "--course", self.slug,
            "--id", "diagram", "--unit", "U1", "--asset", "assets/figures/derived-diagram.svg",
            "--description", "Diagrama derivado", "--based-on", "concept:x",
        )
        md = self.course / "resumenes" / "_source" / "unidad-1-resumen.md"
        html = self.course / "resumenes" / "unidad-1-resumen.html"
        md.write_text("# Unidad 1: Conceptos básicos\n\n![Diagrama](../../assets/figures/derived-diagram.svg \"Diagrama\")\n", encoding="utf-8")
        self.run_cli(RENDER, str(md), str(html), "--kind", "summary", "--course", "Infra Test", "--scope", "Unidad 1", "--check")
        cp = self.run_cli(
            INTEGRITY, "--course", self.slug, "--markdown", str(md), "--html", str(html),
            "--scope", "Unidad 1", "--type", "summary",
        )
        payload = json.loads(cp.stdout)
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["unit_id"], "unidad-1")
        self.assertEqual(payload["used_figure_count"], 1)
        self.assertEqual(payload["scoped_figure_count"], 1)

        # Artifact fingerprint must see the same unit even when the academic id is U1.
        cp = self.run_cli(ARTIFACT, "mark", "--course", str(self.course), "--file", "resumenes/unidad-1-resumen.html", "--type", "summary", "--scope", "Unidad 1")
        marked = json.loads(cp.stdout)
        self.assertEqual(marked["figure_count"], 1)



    def test_source_figures_may_have_null_assets_without_false_collisions(self):
        registry = {
            "version": 2,
            "figures": {
                "u1-source-a": {
                    "id": "u1-source-a", "unit": "U1", "origin": "source",
                    "source_file": "oficiales/a.pdf", "asset": None
                },
                "u1-source-b": {
                    "id": "u1-source-b", "unit": "U1", "origin": "source",
                    "source_file": "oficiales/b.pdf", "asset": None
                },
            },
        }
        (self.course / "conocimiento" / "figures.json").write_text(json.dumps(registry), encoding="utf-8")
        cp = self.run_cli(FIG, "verify", "--course", self.slug)
        payload = json.loads(cp.stdout)
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["issues"], [])

    def test_migration_succeeds_with_pending_source_assets_and_legacy_derived_figures(self):
        asset = self.course / "assets" / "figures" / "legacy.svg"
        asset.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
        registry = {
            "version": 1,
            "figures": {
                "u1-source-a": {
                    "id": "u1-source-a", "unit": "U1", "origin": "source",
                    "source_file": "oficiales/a.pdf", "asset": None
                },
                "u1-source-b": {
                    "id": "u1-source-b", "unit": "U1", "origin": "source",
                    "source_file": "oficiales/b.pdf", "asset": None
                },
                "u1-legacy": {
                    "id": "u1-legacy", "unit": "U1", "concepts": ["X"],
                    "asset": "assets/figures/legacy.svg", "origin": "derived",
                    "description": "legacy"
                },
            },
        }
        (self.course / "conocimiento" / "figures.json").write_text(json.dumps(registry), encoding="utf-8")
        cp = self.run_cli(FIG, "migrate-registry", "--course", self.slug)
        payload = json.loads(cp.stdout)
        self.assertTrue(payload["ok"], payload)
        migrated = json.loads((self.course / "conocimiento" / "figures.json").read_text(encoding="utf-8"))
        self.assertIn("derived:u1-legacy", migrated["figures"])
        self.assertIsNone(migrated["figures"]["u1-source-a"]["asset"])
        verify = self.run_cli(FIG, "verify", "--course", self.slug)
        self.assertTrue(json.loads(verify.stdout)["ok"], verify.stdout)

    def test_derived_figure_without_asset_is_still_an_error(self):
        registry = {
            "version": 2,
            "figures": {
                "derived:no-asset": {
                    "id": "derived:no-asset", "unit": "U1", "unit_id": "unidad-1",
                    "origin": "derived", "based_on": ["concept:X"], "asset": None
                }
            },
        }
        (self.course / "conocimiento" / "figures.json").write_text(json.dumps(registry), encoding="utf-8")
        cp = self.run_cli(FIG, "verify", "--course", self.slug, check=False)
        self.assertNotEqual(cp.returncode, 0)
        payload = json.loads(cp.stdout)
        self.assertIn("derived-asset-missing", [x["reason"] for x in payload["issues"]])

    def test_legacy_derived_registry_migrates_without_reprocessing_sources(self):
        asset = self.course / "assets" / "figures" / "legacy.svg"
        asset.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
        registry = {
            "version": 1,
            "figures": {
                "u1-legacy": {
                    "id": "u1-legacy", "unit": "U1", "concepts": ["X"],
                    "asset": "assets/figures/legacy.svg", "origin": "derived",
                    "description": "legacy"
                }
            }
        }
        (self.course / "conocimiento" / "figures.json").write_text(json.dumps(registry), encoding="utf-8")
        cp = self.run_cli(FIG, "migrate-registry", "--course", self.slug)
        payload = json.loads(cp.stdout)
        self.assertTrue(payload["changed"])
        migrated = json.loads((self.course / "conocimiento" / "figures.json").read_text(encoding="utf-8"))
        self.assertIn("derived:u1-legacy", migrated["figures"])
        item = migrated["figures"]["derived:u1-legacy"]
        self.assertEqual(item["unit_id"], "unidad-1")
        self.assertEqual(item["based_on"], ["concept:X"])


if __name__ == "__main__":
    unittest.main()
