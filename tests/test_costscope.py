import csv
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from cost_model import Cost, totals, percent, import_costs, export_csv, analyze
from app import CostScope, SAMPLE, create_report


class ModelTests(unittest.TestCase):
    def test_calculation_and_rounding(self):
        records = [Cost("A", "X", "100.005", "120"), Cost("B", "Y", 50, 40)]
        self.assertEqual(records[0].estimated, Decimal("100.01"))
        self.assertEqual(totals(records)[:3], (Decimal("150.01"), Decimal("160"), Decimal("9.99")))
        self.assertEqual(percent(Cost("X", "Y", 100, 120).percentage), "+20.00%")
        self.assertEqual(Cost("X", "Y", 100, 80).variance, Decimal("-20.00"))

    def test_zero_estimate(self):
        self.assertIsNone(Cost("A", "X", 0, 100).percentage)
        self.assertIsNone(totals([])[3])
        self.assertEqual(percent(None), "N/A")

    def test_validation(self):
        for amount in ("NaN", "Infinity", "-1", "abc", "1000000000001"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                Cost("A", "X", amount, 10)
        with self.assertRaises(ValueError):
            Cost("", "X", 1, 2)

    def test_csv_validation_and_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text(" actual ,item,estimated,category\n12,A,10,X\n", encoding="utf-8")
            self.assertEqual(import_costs(path)[0].variance, Decimal("2"))
            path.write_text("item,category,estimated,actual\nA,X,10,12\nB,X,wrong,9\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Row 3"):
                import_costs(path)
            path.write_text("item,category,estimated,actual,actual\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                import_costs(path)

    def test_excel(self):
        import openpyxl
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.xlsx"
            workbook = openpyxl.Workbook()
            workbook.active.append(["item", "category", "estimated", "actual"])
            workbook.active.append(["Hardware", "IT", 100, 130])
            workbook.save(path)
            workbook.close()
            self.assertEqual(import_costs(path)[0].variance, Decimal("30"))

    def test_export(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.csv"
            export_csv(path, [Cost("=1+1", "IT", 100, 120)])
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(rows[1][0], "'=1+1")
            self.assertEqual(rows[1][-2:], ["20.00", "+20.00%"])

    def test_ai(self):
        records = [Cost(*row) for row in SAMPLE]
        summary, flags = analyze(records)
        self.assertIn("Isolation Forest", summary)
        self.assertIn(7, flags)
        self.assertEqual(flags, analyze(records)[1])
        self.assertIn("at least 6", analyze(records[:2])[0])

    def test_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.pdf"
            records = [Cost(*row) for row in SAMPLE]
            create_report(path, records, analyze(records)[0])
            self.assertTrue(path.read_bytes().startswith(b"%PDF"))
            self.assertGreater(path.stat().st_size, 10000)


class DesktopTests(unittest.TestCase):
    def test_add_edit_delete_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            app = CostScope(data_file=path)
            app.withdraw()
            try:
                for key, value in dict(item="Test", category="QA", estimated="100", actual="120").items():
                    app.inputs[key].set(value)
                app.add()
                self.assertEqual(len(app.records), 1)
                app.table.selection_set("0")
                app.edit()
                app.inputs["actual"].set("80")
                app.add()
                self.assertEqual(app.records[0].variance, Decimal("-20"))
                app.records = []
                app.load()
                self.assertEqual(app.records[0].actual, Decimal("80"))
                app.refresh()
                app.table.selection_set("0")
                with patch("app.messagebox.askyesno", return_value=True):
                    app.delete()
                self.assertEqual(app.records, [])
                self.assertEqual(path.read_text().strip(), "[]")
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
