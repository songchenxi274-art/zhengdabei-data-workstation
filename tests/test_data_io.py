from __future__ import annotations

import sys
import unittest
from io import BytesIO
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_desk.data_io import (
    DataConfigurationError,
    assess_quality,
    list_excel_sheets,
    load_csv,
    load_xlsx,
    prepare_analysis_frame,
)
from research_desk.models import VariableType, infer_schema


class DataInputTests(unittest.TestCase):
    def test_csv_loading_and_quality_summary(self):
        data = "score,group\n1,A\n2,A\n2,B\n,C\n".encode("utf-8")
        loaded = load_csv(data, "sample.csv", "utf-8", None)
        self.assertEqual(loaded.frame.shape, (4, 2))
        quality = assess_quality(loaded.frame)
        self.assertEqual(quality.rows, 4)
        self.assertEqual(quality.columns, 2)
        self.assertEqual(quality.duplicate_rows, 0)
        missing = quality.missing_by_field.set_index("字段").loc["score", "缺失数"]
        self.assertEqual(missing, 1)

    def test_xlsx_sheet_listing_and_loading(self):
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            pd.DataFrame({"x": [1, 2]}).to_excel(writer, sheet_name="Data", index=False)
            pd.DataFrame({"y": [3]}).to_excel(writer, sheet_name="Metadata", index=False)
        data = buffer.getvalue()
        self.assertEqual(list_excel_sheets(data), ["Data", "Metadata"])
        loaded = load_xlsx(data, "sample.xlsx", "Data")
        self.assertEqual(list(loaded.frame.columns), ["x"])
        self.assertEqual(loaded.sheet_name, "Data")

    def test_csv_preserves_na_like_literals_and_only_blanks_become_missing(self):
        data = (
            "value,group\n"
            "NA,A\n"
            "NULL,A\n"
            "N/A,A\n"
            "nan,A\n"
            ",A\n"
            "99,A\n"
            "-1,A\n"
        ).encode("utf-8")
        frame = load_csv(data, "literal.csv", "utf-8", ",").frame
        self.assertEqual(
            frame["value"].astype("string").tolist()[:4],
            ["NA", "NULL", "N/A", "nan"],
        )
        self.assertTrue(pd.isna(frame["value"].iloc[4]))
        self.assertEqual(frame["value"].iloc[5], "99")
        self.assertEqual(frame["value"].iloc[6], "-1")

    def test_single_column_csv_with_auto_delimiter_keeps_header(self):
        frame = load_csv(b"value\n1\n2\n", "single.csv", "utf-8", None).frame
        self.assertEqual(list(frame.columns), ["value"])
        self.assertEqual(frame["value"].tolist(), [1, 2])

    def test_duplicate_stripped_column_names_are_made_unique(self):
        loaded = load_csv(b"a, a\n1,2\n3,4\n", "dup.csv", "utf-8", ",")
        self.assertEqual(list(loaded.frame.columns), ["a", "a__2"])
        self.assertEqual(infer_schema(loaded.frame)["a__2"].value, "numeric")

    def test_missing_codes_and_invalid_numeric_conversion_require_confirmation(self):
        frame = pd.DataFrame({"score": ["1", "99", "bad", "3"]})
        schema = {"score": VariableType.NUMERIC}
        with self.assertRaises(DataConfigurationError) as context:
            prepare_analysis_frame(frame, schema)
        self.assertEqual(
            int(context.exception.conversion_report["转换失败数"].sum()),
            1,
        )

        prepared = prepare_analysis_frame(
            frame,
            schema,
            {"score": ["99"]},
            allow_invalid_as_missing=True,
        )
        self.assertEqual(int(prepared.frame["score"].notna().sum()), 2)
        self.assertEqual(prepared.frame["score"].tolist()[0], 1.0)
        self.assertTrue(pd.isna(prepared.frame["score"].iloc[1]))


if __name__ == "__main__":
    unittest.main()
