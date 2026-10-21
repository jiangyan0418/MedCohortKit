"""Integration tests for choices that can change scientific interpretation."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from medcohortkit.cli import analyze, main
from medcohortkit.demo import demo_config, synthetic_cohort
from medcohortkit.io import load_config, read_data, validate_config


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def input(self, bilateral=False):
        path = self.root / "data.csv"
        synthetic_cohort(bilateral=bilateral).to_csv(path, index=False)
        return path

    def test_independent_full_run_and_audit(self):
        path = self.input()
        config = demo_config()
        config["icc"]["n_boot"] = 200
        output = self.root / "results"
        audit = analyze(path, config, output)
        self.assertEqual(audit["analyses"]["linear"]["covariance"], "HC3")
        self.assertEqual(audit["input"]["n_rows"], 160)
        self.assertEqual(audit["input"]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        for name in ["report.html", "table1.csv", "comparisons.csv", "regression.csv", "icc.csv", "forest.svg", "audit.json"]:
            self.assertTrue((output / name).is_file(), name)
        stored = json.loads((output / "audit.json").read_text())
        self.assertEqual(stored["config"], config)
        self.assertEqual(stored["analyses"]["icc"]["n_used"], 159)
        self.assertGreater(stored["analyses"]["linear"]["n_dropped"], 0)

    def test_clustered_run_selects_patient_clusters(self):
        config = demo_config(bilateral=True)
        output = self.root / "results"
        audit = analyze(self.input(True), config, output)
        self.assertEqual(audit["input"]["n_rows"], 176)
        self.assertEqual(audit["input"]["n_subjects"], 160)
        model = audit["analyses"]["linear"]
        self.assertEqual(model["covariance"], "cluster")
        self.assertEqual(model["inference_df"], model["n_clusters"] - 1)
        self.assertFalse((output / "comparisons.csv").exists())

    def test_independent_tests_on_repeated_patients_stop_without_output(self):
        config = demo_config(bilateral=True)
        config["comparisons"]["enabled"] = True
        output = self.root / "results"
        with self.assertRaisesRegex(ValueError, "[Rr]epeated|[Dd]uplicate"):
            analyze(self.input(True), config, output)
        self.assertFalse(output.exists())

    def test_knee_ids_do_not_hide_icc_patient_dependence(self):
        config = demo_config(bilateral=True)
        config["icc"] = {"raters": ["alpha_rater1", "alpha_rater2"], "subject_id": "knee_id", "n_boot": 200}
        with self.assertRaisesRegex(ValueError, "Renaming knees"):
            analyze(self.input(True), config, self.root / "results")

    def test_group_labels_and_title_are_html_escaped(self):
        path = self.input()
        frame = pd.read_csv(path)
        frame["group"] = frame["group"].replace({"Control": "<script>alert(1)</script>"})
        frame.to_csv(path, index=False)
        config = demo_config()
        config.pop("icc")
        config.pop("linear")
        config["group_order"][0] = "<script>alert(1)</script>"
        config["title"] = '<img src=x onerror="alert(1)">'
        out = self.root / "results"
        analyze(path, config, out)
        report = (out / "report.html").read_text()
        self.assertNotIn("<script>", report)
        self.assertIn("&lt;script&gt;", report)
        self.assertNotIn('<img src=x onerror=', report)

    def test_input_headers_not_silently_mangled_and_ids_preserved(self):
        path = self.root / "headers.csv"
        path.write_text("id,value,value\n01,2,3\n")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            read_data(path)
        path.write_text("id,value\n001,2\n010,3\n")
        self.assertEqual(read_data(path, "id")["id"].tolist(), ["001", "010"])

    def test_xlsx_first_worksheet(self):
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            self.skipTest("Excel extra not installed")
        path = self.root / "input.xlsx"
        frame = pd.DataFrame({"id": ["001", "002"], "value": [3, 4]})
        frame.to_excel(path, index=False)
        result = read_data(path, "id")
        self.assertEqual(result["id"].tolist(), ["001", "002"])
        self.assertEqual(result["value"].tolist(), [3, 4])

    def test_invalid_or_duplicate_configuration_is_not_guessed(self):
        config = demo_config()
        config["comparisions"] = config.pop("comparisons")
        with self.assertRaisesRegex(ValueError, "Unknown"):
            validate_config(config)
        path = self.root / "analysis.json"
        path.write_text('{"subject_id":"a","subject_id":"b"}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load_config(path)

    def test_csv_wrong_record_width_does_not_shift_columns(self):
        path = self.root / "malformed.csv"
        for record in ["001,0,1,10", "001,0"]:
            path.write_text("id,group,value\n" + record + "\n")
            with self.assertRaisesRegex(ValueError, "fields"):
                read_data(path, "id")

    def test_excel_errors_and_uncalculated_formulas_are_not_missing_data(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("Excel extra not installed")
        path = self.root / "error.xlsx"
        for cell, pattern in [("#DIV/0!", "Excel error cell"), ("=1+1", "no cached result")]:
            book = openpyxl.Workbook()
            book.active.append(["id", "value"])
            book.active.append(["001", cell])
            book.save(path)
            book.close()
            with self.assertRaisesRegex(ValueError, pattern):
                read_data(path, "id")

    def test_existing_output_not_overwritten(self):
        out = self.root / "results"
        out.mkdir()
        old = out / "existing.txt"
        old.write_text("retained")
        with self.assertRaisesRegex(ValueError, "new or empty"):
            analyze(self.input(), demo_config(), out)
        self.assertEqual(old.read_text(), "retained")

    def test_cli_creates_editable_config(self):
        path = self.root / "nested" / "analysis.json"
        self.assertEqual(main(["template", "--out", str(path)]), 0)
        config = load_config(path)
        self.assertFalse(config["comparisons"]["enabled"])
        self.assertEqual(config["subject_id"], "patient_id")


if __name__ == "__main__":
    unittest.main()
