from __future__ import annotations

from enum import Enum

import pandas as pd


class VariableType(str, Enum):
    NUMERIC = "numeric"
    ORDINAL = "ordinal"
    CATEGORICAL = "categorical"
    TEXT = "text"
    DATE = "date"
    UNKNOWN = "unknown"


VARIABLE_TYPE_LABELS = {
    VariableType.NUMERIC: "连续数值",
    VariableType.ORDINAL: "有序变量",
    VariableType.CATEGORICAL: "分类变量",
    VariableType.TEXT: "文本",
    VariableType.DATE: "日期",
    VariableType.UNKNOWN: "未确定",
}


class SamplingDesign(str, Enum):
    UNDECLARED = "undeclared"
    ORDINARY = "ordinary"
    COMPLEX = "complex"
    UNCERTAIN = "uncertain"

    @property
    def allows_inference(self) -> bool:
        return self is SamplingDesign.ORDINARY

    @property
    def label(self) -> str:
        return {
            SamplingDesign.UNDECLARED: "尚未声明",
            SamplingDesign.ORDINARY: "普通未加权独立观测",
            SamplingDesign.COMPLEX: "复杂抽样",
            SamplingDesign.UNCERTAIN: "不确定",
        }[self]


def infer_variable_type(series: pd.Series) -> VariableType:
    if pd.api.types.is_bool_dtype(series):
        return VariableType.CATEGORICAL
    if pd.api.types.is_numeric_dtype(series):
        return VariableType.NUMERIC
    if pd.api.types.is_datetime64_any_dtype(series):
        return VariableType.DATE

    non_null = series.dropna()
    if non_null.empty:
        return VariableType.UNKNOWN

    unique_count = int(non_null.nunique(dropna=True))
    unique_ratio = unique_count / max(len(non_null), 1)
    if unique_count <= 20 or unique_ratio <= 0.2:
        return VariableType.CATEGORICAL
    return VariableType.TEXT


def infer_schema(frame: pd.DataFrame) -> dict[str, VariableType]:
    return {str(column): infer_variable_type(frame[column]) for column in frame.columns}
