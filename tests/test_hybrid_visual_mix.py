from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from pathlib import Path
from unittest import mock

from scripts import illustration_figure, visual_plan_hybrid

ROOT = Path(__file__).resolve().parents[1]


def _fake_provider(_spec: dict):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (320, 240), "white")
    ImageDraw.Draw(image).rectangle((100, 60, 220, 180), fill=(70, 70, 70))
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue(), {
        "provider": "test-provider",
        "model": "test-image-model",
        "seed": 123,
        "prompt_sha256": "a" * 64,
    }


def _flow_spec() -> dict:
    return {
        "schema_version": 1,
        "id": "instruction-flow",
        "title": "Flujo de instrucción",
        "kind": "flow",
        "visual_treatment": "reinterpret",
        "role": "essential",
        "description": "Flujo determinista de dos pasos.",
        "alt": "Paso A seguido por paso B.",
        "caption": "El orden exacto se conserva en el diagrama.",
        "based_on": ["concept:flow"],
        "concepts": ["flow"],
        "learner_focus": ["Seguir el orden A a B"],
        "layout": {"direction": "left-to-right", "background": "transparent"},
        "nodes": [
            {
                "id": "a", "label": "Paso A", "shape": "process", "tone": "primary",
                "rank": 0, "order": 0, "based_on": ["concept:flow"],
            },
            {
                "id": "b", "label": "Paso B", "shape": "process", "tone": "connection",
                "rank": 1, "order": 0, "based_on": ["concept:flow"],
            },
        ],
        "edges": [{"from": "a", "to": "b", "based_on": ["concept:flow"]}],
        "groups": [],
    }


def _illustration_spec() -> dict:
    return {
        "schema_version": 1,
        "id": "cpu-package",
        "subject": "generic computer microprocessor package",
        "view": "top-down",
        "must_show": ["square integrated-circuit package", "visible pins around the package"],
        "alt": "Dibujo a lápiz de un microprocesador visto desde arriba.",
        "caption": "Representación física simplificada de un microprocesador.",
        "based_on": ["concept:cpu"],
    }


class HybridVisualMixTests(unittest.TestCase):
    def setUp(self):
        self.slug = "zz-hybrid-mix-" + uuid.uuid4().hex[:8]
        self.course = ROOT / "materias" / self.slug
        (self.course / "academico").mkdir(parents=True)
        (self.course / "conocimiento").mkdir()
        (self.course / "assets" / "figures").mkdir(parents=True)
        (self.course / "academico" / "academic.json").write_text(json.dumps({
            "identity": {"subject": "Hybrid Mix"},
            "units": [{"id": "U1", "name": "Unidad 1"}],
        }), encoding="utf-8")
        (self.course / "conocimiento" / "concepts.json").write_text(json.dumps({
            "version": 2,
            "concepts": {
                "flow": {"id": "flow", "name": "Flow", "unit": "U1", "unit_id": "unidad-1"},
                "cpu": {"id": "cpu", "name": "CPU", "unit": "U1", "unit_id": "unidad-1"},
            },
        }), encoding="utf-8")
        (self.course / "conocimiento" / "figures.json").write_text(
            json.dumps({"version": 2, "figures": {}}), encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.course, ignore_errors=True)

    def test_one_plan_materializes_exact_diagram_and_optional_illustration(self):
        run = self.course / ".study" / "runs" / "mixed"
        sketches = run / "02-sketches"
        sketches.mkdir(parents=True)
        (sketches / "instruction-flow.json").write_text(
            json.dumps(_flow_spec(), ensure_ascii=False), encoding="utf-8"
        )
        plan = {
            "visuals": [
                {
                    "concept_id": "flow",
                    "need": "visual_required",
                    "visual_treatment": "reinterpret",
                    "visual_medium": "diagram",
                    "derived_figure_id": "derived:instruction-flow",
                    "sketch_spec": "02-sketches/instruction-flow.json",
                    "based_on": ["concept:flow"],
                    "reason": "El orden exacto se aprende mejor como flujo.",
                },
                {
                    "concept_id": "cpu",
                    "need": "visual_helpful",
                    "visual_treatment": "reinterpret",
                    "visual_medium": "illustration",
                    "derived_figure_id": "derived:cpu-package",
                    "based_on": ["concept:cpu"],
                    "reason": "La forma física ayuda al reconocimiento.",
                    "illustration": _illustration_spec(),
                },
            ]
        }
        plan_path = run / "02-plan.json"
        plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

        with mock.patch.object(illustration_figure, "_cloudflare", side_effect=_fake_provider):
            report = visual_plan_hybrid.materialize_plan(self.course, "U1", plan_path)

        self.assertTrue(report["ok"], report)
        self.assertEqual(len(report["entries"]), 2)
        by_medium = {row["visual_medium"]: row for row in report["entries"]}
        self.assertEqual(by_medium["diagram"]["derived_figure_id"], "derived:instruction-flow")
        self.assertTrue(by_medium["diagram"]["asset"].endswith(".svg"))
        self.assertEqual(by_medium["illustration"]["derived_figure_id"], "derived:cpu-package")
        self.assertTrue(by_medium["illustration"]["asset"].endswith(".illustration.svg"))


if __name__ == "__main__":
    unittest.main()
