from __future__ import annotations

import csv
import io
import unicodedata

import pandas as pd


FORMULA_PREFIXES = ("=", "+", "-", "@")
DISALLOWED_CONTROL_EXCEPTIONS = {"\t", "\r", "\n"}


class UnsafeCsvValueError(ValueError):
    pass


def dataframe_to_safe_csv(frame: pd.DataFrame, fields: list[str] | None = None) -> str:
    selected = frame[fields].copy() if fields else frame.copy()
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow([_safe_csv_cell(str(column), is_header=True) for column in selected.columns])
    for row in selected.itertuples(index=False, name=None):
        writer.writerow([_safe_csv_cell(value) for value in row])
    return output.getvalue()


def _safe_csv_cell(value, is_header: bool = False) -> str:
    if pd.isna(value):
        return ""
    if not is_header and isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)

    text = str(value)
    index = 0
    while index < len(text):
        character = text[index]
        if character.isspace() or unicodedata.category(character) in {"Cc", "Cf"}:
            index += 1
            continue
        break

    is_formula_risk = index < len(text) and text[index] in FORMULA_PREFIXES
    remaining = text[index:] if is_formula_risk else text
    for character in remaining:
        if (
            unicodedata.category(character) in {"Cc", "Cf"}
            and character not in DISALLOWED_CONTROL_EXCEPTIONS
        ):
            raise UnsafeCsvValueError("单元格包含无法安全导出的控制字符。")

    if is_formula_risk:
        return "'" + text
    return text
