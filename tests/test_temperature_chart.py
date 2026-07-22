import csv
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCharts import QChartView
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ui.widgets.temperature_chart import TemperatureChart


class TemperatureChartExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_export_history_writes_latest_measurements_to_csv(self) -> None:
        view = QChartView()
        chart = TemperatureChart(view)
        chart.push(10.0, 20.0, 30.0, 40.0)

        for idx in range(51):
            chart.push(float(idx), float(idx + 1), float(idx + 2), float(idx + 3))

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "mediciones.csv"
            ok = chart.export_history(path, limit=50)

            self.assertTrue(ok)

            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 50)
            self.assertEqual(rows[0]["T. Entrada"], "1")
            self.assertEqual(rows[-1]["T. Mezcla"], "53")


if __name__ == "__main__":
    unittest.main()
