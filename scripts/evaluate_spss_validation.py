from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from research_desk.analysis import (
    calculate_correlation,
    calculate_reliability,
    numeric_descriptives,
)
from research_desk.models import SamplingDesign


OUTPUT = ROOT / "work" / "spss_validation"


def main() -> None:
    data = OUTPUT / "data"
    descriptive = pd.read_csv(data / "descriptive.csv")
    descriptive_result = numeric_descriptives(descriptive, ["score", "outcome"])

    correlation = pd.read_csv(data / "correlation.csv")
    pearson = calculate_correlation(
        correlation,
        "x",
        "y",
        "pearson",
        SamplingDesign.ORDINARY,
    )
    spearman = calculate_correlation(
        correlation,
        "x",
        "y",
        "spearman",
        SamplingDesign.ORDINARY,
    )

    reliability3 = pd.read_csv(data / "reliability3.csv")
    alpha3 = calculate_reliability(
        reliability3,
        ["q1", "q2", "q3"],
        ["q2"],
        1,
        5,
        SamplingDesign.ORDINARY,
    )
    reliability2 = pd.read_csv(data / "reliability2.csv")
    alpha2 = calculate_reliability(
        reliability2,
        ["q1", "q2"],
        ["q2"],
        1,
        5,
        SamplingDesign.ORDINARY,
    )

    result = {
        "descriptive": descriptive_result.to_dict(orient="records"),
        "pearson": {
            "n": pearson.n,
            "coefficient": pearson.coefficient,
            "p_value": pearson.p_value,
        },
        "spearman": {
            "n": spearman.n,
            "coefficient": spearman.coefficient,
            "p_value": spearman.p_value,
        },
        "reliability_3": {
            "n_complete": alpha3.n_complete,
            "alpha": alpha3.alpha,
            "standardized_alpha": alpha3.standardized_alpha,
            "items": alpha3.item_statistics.to_dict(orient="records"),
        },
        "reliability_2": {
            "n_complete": alpha2.n_complete,
            "alpha": alpha2.alpha,
            "standardized_alpha": alpha2.standardized_alpha,
        },
        "quartile_algorithm": "linear (pending SPSS validation)",
    }
    path = OUTPUT / "app_expected.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
