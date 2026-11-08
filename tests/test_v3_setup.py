import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class TestAppFiles(unittest.TestCase):

    def test_app_compiles(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        compile(source, "app.py", "exec")

    def test_all_six_features_present(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        for title in (
            "Hurricane simulator",
            "Robot inspections",
            "Restoration AI",
            "Grid digital twin",
            "Community impact",
            "the Anthill"
        ):
            self.assertIn(title, app)

    def test_readable_theme(self):
        config = (
            ROOT / ".streamlit/config.toml"
        ).read_text(encoding="utf-8")

        self.assertIn("#F3FAFF", config)
        self.assertIn("#071724", config)

if __name__ == "__main__":
    unittest.main()