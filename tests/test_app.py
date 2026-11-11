from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_desk.models import SamplingDesign, VariableType


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["LOCALAPPDATA"] = str(ROOT / "work" / "apptest-localappdata")

    def build_app(self) -> AppTest:
        frame = pd.DataFrame(
            {
                "x": list(range(20)),
                "y": [value * 2 + (index % 3) for index, value in enumerate(range(20))],
            }
        )
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
        app.session_state["frame"] = frame
        app.session_state["analysis_frame"] = frame.copy()
        app.session_state["source_name"] = "synthetic.csv"
        app.session_state["schema"] = {
            "x": VariableType.NUMERIC,
            "y": VariableType.NUMERIC,
        }
        app.session_state["sampling_design"] = SamplingDesign.ORDINARY
        app.session_state["sampling_selector"] = "普通未加权独立观测"
        app.run()
        self.assertFalse(app.exception)
        return app

    def test_complex_sampling_clears_previous_p_value(self):
        app = self.build_app()
        [button for button in app.button if button.label == "计算相关"][0].click()
        app.run()
        self.assertFalse(app.exception)
        self.assertIn("p 值", [metric.label for metric in app.metric])

        app.selectbox(key="sampling_selector").select("复杂抽样").run()
        self.assertFalse(app.exception)
        self.assertNotIn("p 值", [metric.label for metric in app.metric])

    def test_application_tabs_render_without_exception(self):
        app = self.build_app()
        self.assertEqual(len(app.tabs), 6)
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
