from __future__ import annotations

import html
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats


QUARTILE_ALGORITHM = "linear（待 SPSS 对照验证）"
CORRELATION_INFERENCE_MIN_N = 10


@dataclass(frozen=True)
class CorrelationResult:
    method: str
    x_field: str
    y_field: str
    n: int
    coefficient: float
    p_value: float | None
    p_value_reason: str | None
    sampling_design: str
    warnings: tuple[str, ...]
    pair_data: pd.DataFrame


@dataclass(frozen=True)
class ReliabilityResult:
    alpha: float
    standardized_alpha: float
    n_complete: int
    item_count: int
    items: tuple[str, ...]
    reverse_items: tuple[str, ...]
    score_min: float
    score_max: float
    sampling_design: str
    item_statistics: pd.DataFrame
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OrdinalDescriptiveResult:
    summary: pd.DataFrame
    frequencies: pd.DataFrame


def numeric_descriptives(frame: pd.DataFrame, fields: list[str]) -> pd.DataFrame:
    rows = []
    for field in fields:
        numeric = pd.to_numeric(frame[field], errors="coerce")
        valid = numeric.dropna()
        n = int(valid.count())
        std = float(valid.std(ddof=1)) if n >= 2 else np.nan
        quantiles = valid.quantile([0.25, 0.5, 0.75]) if n >= 1 else None
        rows.append(
            {
                "字段": field,
                "有效数": n,
                "缺失数": int(numeric.isna().sum()),
                "均值": float(valid.mean()) if n else np.nan,
                "标准差": std,
                "中位数": float(quantiles.loc[0.5]) if quantiles is not None else np.nan,
                "Q1": float(quantiles.loc[0.25]) if quantiles is not None else np.nan,
                "Q3": float(quantiles.loc[0.75]) if quantiles is not None else np.nan,
                "最小值": float(valid.min()) if n else np.nan,
                "最大值": float(valid.max()) if n else np.nan,
                "四分位算法": QUARTILE_ALGORITHM,
            }
        )
    return pd.DataFrame(rows)


def categorical_frequencies(frame: pd.DataFrame, field: str) -> pd.DataFrame:
    valid = frame[field].dropna()
    counts = valid.value_counts(dropna=True).rename_axis("类别").reset_index(name="频数")
    counts["有效百分比"] = counts["频数"] / max(len(valid), 1)
    return counts


def ordinal_descriptives(frame: pd.DataFrame, fields: list[str]) -> OrdinalDescriptiveResult:
    summary_rows = []
    frequency_rows = []
    for field in fields:
        numeric = pd.to_numeric(frame[field], errors="coerce")
        numeric = numeric.replace([np.inf, -np.inf], np.nan)
        valid = numeric.dropna()
        quantiles = valid.quantile([0.25, 0.5, 0.75]) if not valid.empty else None
        q1 = float(quantiles.loc[0.25]) if quantiles is not None else np.nan
        median = float(quantiles.loc[0.5]) if quantiles is not None else np.nan
        q3 = float(quantiles.loc[0.75]) if quantiles is not None else np.nan
        summary_rows.append(
            {
                "字段": field,
                "有效数": int(valid.count()),
                "缺失数": int(numeric.isna().sum()),
                "中位数": median,
                "Q1": q1,
                "Q3": q3,
                "IQR": q3 - q1 if np.isfinite(q1) and np.isfinite(q3) else np.nan,
                "四分位算法": QUARTILE_ALGORITHM,
            }
        )
        if not valid.empty:
            counts = valid.value_counts().sort_index()
            for category, count in counts.items():
                frequency_rows.append(
                    {
                        "字段": field,
                        "取值": category,
                        "频数": int(count),
                        "有效百分比": int(count) / len(valid),
                    }
                )
    return OrdinalDescriptiveResult(
        summary=pd.DataFrame(summary_rows),
        frequencies=pd.DataFrame(
            frequency_rows,
            columns=["字段", "取值", "频数", "有效百分比"],
        ),
    )


def calculate_correlation(
    frame: pd.DataFrame,
    x_field: str,
    y_field: str,
    method: str,
    sampling_design,
) -> CorrelationResult:
    if method not in {"pearson", "spearman"}:
        raise ValueError("只支持 Pearson 或 Spearman 相关。")

    pair = frame[[x_field, y_field]].copy()
    pair[x_field] = pd.to_numeric(pair[x_field], errors="coerce")
    pair[y_field] = pd.to_numeric(pair[y_field], errors="coerce")
    pair = pair.replace([np.inf, -np.inf], pd.NA)
    pair = pair.dropna(how="any").reset_index(drop=True)
    n = len(pair)
    if n < 3:
        raise ValueError("两两有效样本少于 3 个，不显示相关系数。")
    if pair[x_field].nunique() < 2 or pair[y_field].nunique() < 2:
        raise ValueError("变量没有变异，相关系数不可定义。")

    warnings: list[str] = []
    if n < CORRELATION_INFERENCE_MIN_N:
        warnings.append("两两样本少于 10，不显示 p 值或显著性结论；该数字是产品界面策略。")
    for field in (x_field, y_field):
        outlier_count = _iqr_outlier_count(pair[field])
        if outlier_count:
            warnings.append(f"{field} 检出 {outlier_count} 个 IQR 异常值，不会自动删除。")

    if method == "pearson":
        coefficient = float(pair[x_field].corr(pair[y_field], method="pearson"))
        p_value, reason = _infer_significance(
            lambda: float(stats.pearsonr(pair[x_field], pair[y_field]).pvalue),
            n,
            sampling_design,
        )
        warnings.append("Pearson 推断近似要求双变量正态性；应结合散点图检查线性关系。")
    else:
        ranks = pair.rank(method="average")
        coefficient = float(ranks[x_field].corr(ranks[y_field], method="pearson"))
        p_value, reason = _spearman_t_approximation(coefficient, n, sampling_design)
        if pair[x_field].duplicated().any() or pair[y_field].duplicated().any():
            warnings.append("存在并列值，Spearman 使用平均秩和近似 p 值。")

    if not sampling_design.allows_inference:
        warnings.append(
            f"抽样设计为“{getattr(sampling_design, 'label', sampling_design)}”，正式总体推断已禁用。"
        )
    warnings.append("相关不等于因果；单个相关结果未进行多重比较校正。")
    return CorrelationResult(
        method=method,
        x_field=x_field,
        y_field=y_field,
        n=n,
        coefficient=coefficient,
        p_value=p_value,
        p_value_reason=reason,
        sampling_design=getattr(sampling_design, "value", str(sampling_design)),
        warnings=tuple(dict.fromkeys(warnings)),
        pair_data=pair,
    )


def calculate_reliability(
    frame: pd.DataFrame,
    items: list[str],
    reverse_items: list[str],
    score_min: float,
    score_max: float,
    sampling_design,
) -> ReliabilityResult:
    if len(items) < 2:
        raise ValueError("信度分析至少需要两个题项。")
    if score_max <= score_min:
        raise ValueError("题项最大值必须大于最小值。")
    if not set(reverse_items).issubset(items):
        raise ValueError("反向题必须包含在参与分析的题项中。")

    numeric = frame[items].apply(pd.to_numeric, errors="coerce")
    numeric = numeric.replace([np.inf, -np.inf], pd.NA)
    out_of_range = (numeric.lt(score_min) | numeric.gt(score_max)).sum().sum()
    numeric = numeric.mask(numeric.lt(score_min) | numeric.gt(score_max))
    complete = numeric.dropna(how="any").copy()
    n_complete = len(complete)
    if n_complete < 2:
        raise ValueError("完整观测少于 2 个，样本方差不可计算。")

    for item in reverse_items:
        complete[item] = score_min + score_max - complete[item]

    variances = complete.var(ddof=1)
    constant_items = [str(item) for item, value in variances.items() if not np.isfinite(value) or value <= 0]
    if constant_items:
        raise ValueError(f"以下题项没有变异，信度指标不可用：{', '.join(constant_items)}")

    total = complete.sum(axis=1)
    total_variance = float(total.var(ddof=1))
    if not np.isfinite(total_variance) or total_variance <= 0:
        raise ValueError("总分方差为零，Cronbach's α 不可定义。")

    k = len(items)
    alpha = (k / (k - 1)) * (1 - float(variances.sum()) / total_variance)
    correlation_matrix = complete.corr(method="pearson")
    inter_item = [
        float(correlation_matrix.loc[left, right])
        for left, right in combinations(items, 2)
    ]
    mean_inter_item = float(np.mean(inter_item)) if inter_item else np.nan
    denominator = 1 + (k - 1) * mean_inter_item
    standardized_alpha = (
        float(k * mean_inter_item / denominator)
        if np.isfinite(mean_inter_item) and denominator > 0
        else np.nan
    )

    item_rows = []
    if k >= 3:
        for item in items:
            rest_total = complete.drop(columns=[item]).sum(axis=1)
            rest_total_variance = float(rest_total.var(ddof=1))
            citc = (
                float(complete[item].corr(rest_total, method="pearson"))
                if rest_total_variance > 0
                else "不适用"
            )
            remaining = complete.drop(columns=[item])
            remaining_variances = remaining.var(ddof=1)
            remaining_total_variance = float(remaining.sum(axis=1).var(ddof=1))
            deleted_alpha = (
                ((k - 1) / (k - 2))
                * (1 - float(remaining_variances.sum()) / remaining_total_variance)
                if remaining_total_variance > 0 and (remaining_variances > 0).all()
                else "不适用"
            )
            item_rows.append(
                {
                    "题项": item,
                    "CITC": citc,
                    "删除题项后的 α": (
                        float(deleted_alpha) if deleted_alpha != "不适用" else deleted_alpha
                    ),
                }
            )

    warnings = []
    if n_complete == 2:
        warnings.append("仅有两个完整观测值，估计极不稳定，不提供信度质量结论。")
    elif n_complete < 30:
        warnings.append("完整样本较小，信度估计可能不稳定。")
    if out_of_range:
        warnings.append(f"有 {int(out_of_range)} 个题项值超出设定范围，已按缺失处理。")
    if k == 2:
        warnings.append("两题量表只依赖单个协方差关系，不能据此宣称单维性或稳定信度。")
    valid_citc = [row["CITC"] for row in item_rows if isinstance(row["CITC"], float)]
    if item_rows and (not valid_citc or not any(value > 0 for value in valid_citc)):
        warnings.append("CITC 不适用或非正，需要人工复核题项与总分结构。")
    if any(value == "不适用" for row in item_rows for value in row.values()):
        warnings.append("部分单题统计量不可定义，已标记为“不适用”。")
    if not sampling_design.allows_inference:
        warnings.append("当前抽样声明不允许把信度结果外推为总体结论。")
    warnings.append("传统 α 不自动证明单维性；Likert 有序数据的序数 α 尚未纳入 MVP。")

    return ReliabilityResult(
        alpha=float(alpha),
        standardized_alpha=standardized_alpha,
        n_complete=n_complete,
        item_count=k,
        items=tuple(items),
        reverse_items=tuple(reverse_items),
        score_min=float(score_min),
        score_max=float(score_max),
        sampling_design=getattr(sampling_design, "value", str(sampling_design)),
        item_statistics=pd.DataFrame(item_rows),
        warnings=tuple(warnings),
    )


def create_static_scatter_svg(
    pair_data: pd.DataFrame,
    x_field: str,
    y_field: str,
    width: int = 720,
    height: int = 360,
) -> str:
    x = pd.to_numeric(pair_data[x_field], errors="coerce")
    y = pd.to_numeric(pair_data[y_field], errors="coerce")
    valid = pd.DataFrame({"x": x, "y": y}).dropna()
    if valid.empty:
        raise ValueError("没有可用于散点图的数据。")

    left, right, top, bottom = 60, 20, 24, 50
    plot_width = width - left - right
    plot_height = height - top - bottom
    x_min, x_max = float(valid["x"].min()), float(valid["x"].max())
    y_min, y_max = float(valid["y"].min()), float(valid["y"].max())
    x_span = x_max - x_min or 1.0
    y_span = y_max - y_min or 1.0

    points = []
    for row in valid.itertuples(index=False):
        px = left + ((float(row.x) - x_min) / x_span) * plot_width
        py = top + plot_height - ((float(row.y) - y_min) / y_span) * plot_height
        points.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="3.5" />')

    safe_x = html.escape(x_field)
    safe_y = html.escape(y_field)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{safe_x} 与 {safe_y} 散点图">'
        f'<rect width="100%" height="100%" fill="#ffffff" />'
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#374151" />'
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" '
        f'y2="{top + plot_height}" stroke="#374151" />'
        f'<g fill="#0f766e" fill-opacity="0.72">{"".join(points)}</g>'
        f'<text x="{left}" y="{height - 14}" font-size="12" fill="#374151">{safe_x}</text>'
        f'<text x="8" y="{top + 12}" font-size="12" fill="#374151">{safe_y}</text>'
        "</svg>"
    )


def _infer_significance(
    calculate_p,
    n: int,
    sampling_design,
) -> tuple[float | None, str | None]:
    if not sampling_design.allows_inference:
        return None, "当前抽样声明不允许正式总体推断。"
    if n < CORRELATION_INFERENCE_MIN_N:
        return None, "两两有效样本少于 10，按产品界面策略不显示 p 值。"
    return calculate_p(), None


def _spearman_t_approximation(
    coefficient: float,
    n: int,
    sampling_design,
) -> tuple[float | None, str | None]:
    if not sampling_design.allows_inference:
        return None, "当前抽样声明不允许正式总体推断。"
    if n < CORRELATION_INFERENCE_MIN_N:
        return None, "两两有效样本少于 10，按产品界面策略不显示 p 值。"
    if abs(coefficient) >= 1:
        return None, "相关系数为 ±1 时 t 近似不可定义。"
    t_value = coefficient * np.sqrt((n - 2) / (1 - coefficient**2))
    return float(2 * stats.t.sf(abs(t_value), df=n - 2)), None


def _iqr_outlier_count(series: pd.Series) -> int:
    valid = pd.to_numeric(series, errors="coerce").dropna()
    if len(valid) < 4:
        return 0
    q1, q3 = valid.quantile([0.25, 0.75])
    iqr = q3 - q1
    if iqr == 0:
        return 0
    return int(((valid < q1 - 1.5 * iqr) | (valid > q3 + 1.5 * iqr)).sum())
