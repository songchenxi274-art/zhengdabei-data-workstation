from __future__ import annotations

import csv
from dataclasses import dataclass
from io import BytesIO, StringIO

import pandas as pd

from research_desk.models import VariableType


@dataclass(frozen=True)
class LoadedTable:
    frame: pd.DataFrame
    source_name: str
    sheet_name: str | None = None
    column_changes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class PreparedData:
    frame: pd.DataFrame
    conversion_report: pd.DataFrame


@dataclass(frozen=True)
class DataQualityReport:
    rows: int
    columns: int
    duplicate_rows: int
    missing_by_field: pd.DataFrame
    constant_fields: tuple[str, ...]


class DataConfigurationError(ValueError):
    def __init__(self, message: str, conversion_report: pd.DataFrame):
        super().__init__(message)
        self.conversion_report = conversion_report


def list_excel_sheets(data: bytes) -> list[str]:
    with pd.ExcelFile(BytesIO(data), engine="openpyxl") as workbook:
        return [str(name) for name in workbook.sheet_names]


def load_csv(data: bytes, source_name: str, encoding: str, delimiter: str | None) -> LoadedTable:
    text = data.decode(encoding)
    if delimiter is None:
        sample = text[:8192]
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","

    frame = pd.read_csv(
        StringIO(text),
        sep=delimiter,
        keep_default_na=False,
        na_values=[],
    )
    frame, changes = _normalize_columns(_blank_to_missing(frame))
    return LoadedTable(frame=frame, source_name=source_name, column_changes=changes)


def load_xlsx(data: bytes, source_name: str, sheet_name: str) -> LoadedTable:
    frame = pd.read_excel(
        BytesIO(data),
        sheet_name=sheet_name,
        engine="openpyxl",
        keep_default_na=False,
        na_values=[],
    )
    frame, changes = _normalize_columns(_blank_to_missing(frame))
    return LoadedTable(
        frame=frame,
        source_name=source_name,
        sheet_name=sheet_name,
        column_changes=changes,
    )


def prepare_analysis_frame(
    frame: pd.DataFrame,
    schema: dict[str, VariableType],
    missing_codes: dict[str, list[str]] | None = None,
    allow_invalid_as_missing: bool = False,
) -> PreparedData:
    missing_codes = missing_codes or {}
    prepared = frame.copy()
    conversion_rows = []

    for field in prepared.columns:
        source = prepared[field]
        declared_codes = [code.strip() for code in missing_codes.get(str(field), []) if code.strip()]
        if declared_codes:
            string_mask = source.astype("string").str.strip().isin(declared_codes)
            numeric_codes = []
            for code in declared_codes:
                try:
                    numeric_codes.append(float(code))
                except ValueError:
                    continue
            numeric_mask = (
                pd.to_numeric(source, errors="coerce").isin(numeric_codes)
                if numeric_codes
                else pd.Series(False, index=source.index)
            )
            source = source.mask(string_mask | numeric_mask)

        variable_type = schema.get(str(field), VariableType.UNKNOWN)
        converted = source
        expected_type = None
        if variable_type in {VariableType.NUMERIC, VariableType.ORDINAL}:
            expected_type = variable_type.value
            converted = pd.to_numeric(source, errors="coerce")
        elif variable_type is VariableType.DATE:
            expected_type = variable_type.value
            converted = pd.to_datetime(source, errors="coerce")

        invalid_count = 0
        if expected_type is not None:
            invalid_count = int((source.notna() & converted.isna()).sum())
            conversion_rows.append(
                {
                    "字段": str(field),
                    "目标类型": expected_type,
                    "转换失败数": invalid_count,
                }
            )
        prepared[field] = converted

    conversion_report = pd.DataFrame(
        conversion_rows,
        columns=["字段", "目标类型", "转换失败数"],
    )
    invalid_total = int(conversion_report["转换失败数"].sum()) if not conversion_report.empty else 0
    if invalid_total and not allow_invalid_as_missing:
        raise DataConfigurationError(
            f"有 {invalid_total} 个值无法转换为指定类型。请检查数据，或明确确认将其作为缺失值处理。",
            conversion_report,
        )
    return PreparedData(frame=prepared, conversion_report=conversion_report)


def assess_quality(frame: pd.DataFrame) -> DataQualityReport:
    missing_rows = []
    constant_fields = []
    for column in frame.columns:
        series = frame[column]
        missing_count = int(series.isna().sum())
        missing_rows.append(
            {
                "字段": str(column),
                "缺失数": missing_count,
                "缺失比例": missing_count / max(len(frame), 1),
            }
        )
        if series.dropna().nunique(dropna=True) <= 1:
            constant_fields.append(str(column))

    missing = pd.DataFrame(missing_rows)
    return DataQualityReport(
        rows=len(frame),
        columns=len(frame.columns),
        duplicate_rows=int(frame.duplicated().sum()),
        missing_by_field=missing,
        constant_fields=tuple(constant_fields),
    )


def _normalize_columns(frame: pd.DataFrame) -> tuple[pd.DataFrame, tuple[tuple[str, str], ...]]:
    normalized = frame.copy()
    normalized_names = []
    used = set()
    changes = []
    for original in normalized.columns:
        original_name = str(original)
        base = original_name.strip() or "unnamed"
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}__{suffix}"
            suffix += 1
        used.add(candidate)
        normalized_names.append(candidate)
        if candidate != original_name:
            changes.append((original_name, candidate))
    normalized.columns = normalized_names
    return normalized, tuple(changes)


def _blank_to_missing(frame: pd.DataFrame) -> pd.DataFrame:
    cleaned = frame.copy()
    for column in cleaned.columns:
        if not pd.api.types.is_numeric_dtype(cleaned[column]):
            cleaned[column] = cleaned[column].replace(r"^\s*$", pd.NA, regex=True)
    return cleaned
