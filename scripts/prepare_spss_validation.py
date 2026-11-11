from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "work" / "spss_validation"
DATA = OUTPUT / "data"
RESULTS = OUTPUT / "results"


def write_csv(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)

    descriptive_rows = [
        [1, 1, 3, "A"],
        [2, 2, 4, "A"],
        [3, 2, 5, "B"],
        [4, 3, 6, "B"],
        [5, 4, 7, "A"],
        [6, 5, 8, "B"],
        [7, 7, 9, "A"],
        [8, 8, 10, "B"],
        [9, 9, 11, "A"],
        [10, 10, 13, "B"],
        [11, 12, 14, "A"],
        [12, 15, 16, "B"],
        [13, 18, 17, "A"],
        [14, 20, 20, "B"],
        [15, 22, 23, "A"],
        [16, 25, 24, "B"],
        [17, 30, 27, "A"],
        [18, 35, 31, "B"],
        [19, 40, "", "A"],
        [20, "", 100, "B"],
    ]
    write_csv(
        DATA / "descriptive.csv",
        ["id", "score", "outcome", "group"],
        descriptive_rows,
    )

    correlation_rows = [
        [1, 1, 2],
        [2, 1, 3],
        [3, 2, 2],
        [4, 3, 4],
        [5, 3, 5],
        [6, 4, 4],
        [7, 5, 6],
        [8, 5, 7],
        [9, 6, 7],
        [10, 7, 8],
        [11, 8, 9],
        [12, 9, 10],
        [13, 10, 12],
        [14, 12, 13],
        [15, 14, 15],
        [16, 16, "",
        ],
        [17, 18, 19],
        [18, 20, 21],
        [19, 25, 42],
        [20, "", 23],
    ]
    write_csv(DATA / "correlation.csv", ["id", "x", "y"], correlation_rows)

    reliability_rows = []
    q1_values = [1, 2, 3, 4, 5, 2, 3, 4, 5, 1, 2, 3, 4, 5, 3, 4, 5, 2, 3, 4, 5, 1, 2, 3, 4, 5, 2, 3, 4, 5]
    q2_raw = [5, 4, 3, 2, 1, 4, 3, 2, 1, 5, 4, 3, 2, 1, 3, 2, 1, 4, 3, 2, 1, 5, 4, 3, 2, 1, 4, 3, 2, 1]
    q3_values = [1, 2, 4, 4, 5, 2, 3, 4, 5, 2, 2, 3, 4, 5, 3, 4, 5, 2, 3, 4, 5, 1, 2, 3, 4, 5, 2, 3, 4, 5]
    for index, (q1, q2, q3) in enumerate(zip(q1_values, q2_raw, q3_values), start=1):
        if index in {7, 19}:
            q3 = ""
        reliability_rows.append([index, q1, q2, q3])
    write_csv(DATA / "reliability3.csv", ["id", "q1", "q2", "q3"], reliability_rows)

    reliability2_rows = [
        [index, q1_values[index - 1], q2_raw[index - 1]]
        for index in range(1, 31)
    ]
    write_csv(DATA / "reliability2.csv", ["id", "q1", "q2"], reliability2_rows)

    syntax = f"""CD '{OUTPUT.as_posix()}'.

GET DATA
  /TYPE=TXT
  /FILE='data/descriptive.csv'
  /ENCODING='UTF8'
  /DELIMITERS=','
  /QUALIFIER='"'
  /ARRANGEMENT=DELIMITED
  /FIRSTCASE=2
  /VARIABLES=
    id F8.0
    score F8.2
    outcome F8.2
    group A1.
DATASET NAME descriptive WINDOW=FRONT.

OMS /DESTINATION FORMAT=HTML OUTFILE='results/descriptive.html'.
FREQUENCIES VARIABLES=score outcome
  /FORMAT=NOTABLE
  /PERCENTILES=25 50 75
  /STATISTICS=MEAN STDDEV MINIMUM MAXIMUM.
OMSEND.

GET DATA
  /TYPE=TXT
  /FILE='data/correlation.csv'
  /ENCODING='UTF8'
  /DELIMITERS=','
  /QUALIFIER='"'
  /ARRANGEMENT=DELIMITED
  /FIRSTCASE=2
  /VARIABLES=
    id F8.0
    x F8.2
    y F8.2.
DATASET NAME correlation WINDOW=FRONT.

OMS /DESTINATION FORMAT=HTML OUTFILE='results/pearson.html'.
CORRELATIONS VARIABLES=x y
  /PRINT=TWOTAIL NOSIG
  /MISSING=PAIRWISE.
OMSEND.

OMS /DESTINATION FORMAT=HTML OUTFILE='results/spearman.html'.
NONPAR CORR VARIABLES=x y
  /PRINT=SPEARMAN TWOTAIL
  /MISSING=PAIRWISE.
OMSEND.

GET DATA
  /TYPE=TXT
  /FILE='data/reliability3.csv'
  /ENCODING='UTF8'
  /DELIMITERS=','
  /QUALIFIER='"'
  /ARRANGEMENT=DELIMITED
  /FIRSTCASE=2
  /VARIABLES=
    id F8.0
    q1 F8.0
    q2 F8.0
    q3 F8.0.
DATASET NAME reliability3 WINDOW=FRONT.
RECODE q2 (1=5) (2=4) (3=3) (4=2) (5=1) INTO q2r.
EXECUTE.
OMS /DESTINATION FORMAT=HTML OUTFILE='results/reliability3.html'.
RELIABILITY
  /VARIABLES=q1 q2r q3
  /SCALE('ALL') ALL
  /MODEL=ALPHA
  /STATISTICS=DESCRIPTIVE SCALE CORR
  /SUMMARY=TOTAL.
OMSEND.

GET DATA
  /TYPE=TXT
  /FILE='data/reliability2.csv'
  /ENCODING='UTF8'
  /DELIMITERS=','
  /QUALIFIER='"'
  /ARRANGEMENT=DELIMITED
  /FIRSTCASE=2
  /VARIABLES=
    id F8.0
    q1 F8.0
    q2 F8.0.
DATASET NAME reliability2 WINDOW=FRONT.
RECODE q2 (1=5) (2=4) (3=3) (4=2) (5=1) INTO q2r.
EXECUTE.
OMS /DESTINATION FORMAT=HTML OUTFILE='results/reliability2.html'.
RELIABILITY
  /VARIABLES=q1 q2r
  /SCALE('ALL') ALL
  /MODEL=ALPHA
  /SUMMARY=TOTAL.
OMSEND.
"""
    (OUTPUT / "run_spss_validation.sps").write_text(syntax, encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
