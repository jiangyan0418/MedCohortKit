"""Transparent two-group summaries and independent-sample comparisons.

All analysis choices are explicit. Missing values are omitted separately for
each variable and their denominators are reported. The default continuous test
is Welch's t test; normality tests are never used to choose an analysis.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


_TABLE_COLUMNS = [
    "variable", "level", "overall", "group_1", "group_2",
    "missing_overall", "missing_group_1", "missing_group_2",
]
_COMPARISON_COLUMNS = [
    "variable", "kind", "group_1", "group_2", "n1", "n2", "test",
    "estimate", "ci_low", "ci_high", "p_value", "p_adjusted", "notes",
]


def _names(values: Any, argument: str) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, (list, tuple)) or any(
        not isinstance(value, str) or not value.strip() for value in values
    ):
        raise ValueError(f"{argument} must be a list of nonblank column names.")
    if len(set(values)) != len(values):
        raise ValueError(f"{argument} contains duplicate column names.")
    return list(values)


def _check_labels(series: pd.Series, name: str, allow_missing: bool) -> None:
    if not allow_missing and series.isna().any():
        raise ValueError(f"Column {name!r} contains missing values.")
    for value in series.dropna():
        try:
            hash(value)
        except TypeError as exc:
            raise ValueError(f"Column {name!r} must contain scalar labels.") from exc
        if isinstance(value, str) and not value.strip():
            raise ValueError(
                f"Column {name!r} contains a blank label; encode missing values explicitly."
            )
        if isinstance(value, (int, float, complex, np.number)) and not np.isfinite(value):
            raise ValueError(f"Column {name!r} contains an infinite label.")


def _prepare(
    data: pd.DataFrame,
    group: str,
    continuous: list[str],
    categorical: list[str],
    group_order: list | None,
) -> tuple[pd.DataFrame, list[str], list[str], list]:
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("data must be a nonempty pandas DataFrame.")
    if not data.columns.is_unique:
        raise ValueError("Data contains duplicate column names.")
    continuous = _names(continuous, "continuous")
    categorical = _names(categorical, "categorical")
    if not continuous and not categorical:
        raise ValueError("Specify at least one continuous or categorical variable.")
    if set(continuous) & set(categorical):
        raise ValueError("A variable cannot be both continuous and categorical.")
    if not isinstance(group, str) or not group.strip():
        raise ValueError("group must be a nonblank column name.")
    if group in continuous + categorical:
        raise ValueError("The grouping column cannot also be an analysis variable.")
    required = [group] + continuous + categorical
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing!r}.")
    frame = data.loc[:, required].copy()
    _check_labels(frame[group], group, allow_missing=False)
    observed = list(pd.unique(frame[group]))
    if len(observed) != 2:
        raise ValueError("Exactly two observed groups are required.")
    if group_order is None:
        labels = observed
    else:
        if not isinstance(group_order, (list, tuple)) or len(group_order) != 2:
            raise ValueError("group_order must list exactly the two observed group labels.")
        try:
            valid = len(set(group_order)) == 2 and set(group_order) == set(observed)
        except TypeError:
            valid = False
        if not valid:
            raise ValueError("group_order must list exactly the two observed group labels.")
        labels = list(group_order)
    for name in continuous:
        series = frame[name]
        if (
            pd.api.types.is_bool_dtype(series)
            or pd.api.types.is_datetime64_any_dtype(series)
            or pd.api.types.is_timedelta64_dtype(series)
        ):
            raise ValueError(f"Continuous column {name!r} must contain numeric measurements.")
        try:
            numeric = pd.to_numeric(series, errors="raise")
            if np.iscomplexobj(numeric.to_numpy()):
                raise ValueError("complex values are not measurements")
            values = numeric.to_numpy(dtype=float, na_value=np.nan)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Continuous column {name!r} contains nonnumeric values. "
                "Correct the data or explicitly encode missing values."
            ) from exc
        if (pd.isna(values) & series.notna().to_numpy()).any():
            raise ValueError(
                f"Continuous column {name!r} contains values that would be silently converted to missing."
            )
        if np.isinf(values).any():
            raise ValueError(f"Continuous column {name!r} contains infinite values.")
        # Conversion is deliberate and strict: invalid strings are never silently
        # changed into missing observations.
        frame[name] = values
    for name in categorical:
        _check_labels(frame[name], name, allow_missing=True)
    return frame, continuous, categorical, labels


def _category_levels(series: pd.Series) -> list:
    """Use stable natural order when possible, with a deterministic mixed-type fallback."""
    levels = list(pd.unique(series.dropna()))
    try:
        return sorted(levels)
    except TypeError:
        return sorted(levels, key=lambda value: (type(value).__name__, str(value)))


def _number(value: float) -> str:
    return f"{value:.2f}" if np.isfinite(value) else "NA"


def _continuous_summary(series: pd.Series, style: str) -> str:
    values = series.dropna().to_numpy(dtype=float)
    if len(values) == 0:
        return "NA; n=0"
    if style == "mean (SD)":
        sd = values.std(ddof=1) if len(values) > 1 else np.nan
        text = f"{_number(values.mean())} ({_number(sd)})"
    else:
        q1, median, q3 = np.quantile(values, [0.25, 0.5, 0.75])
        text = f"{_number(median)} [{_number(q1)}, {_number(q3)}]"
    return f"{text}; n={len(values)}"


def _categorical_summary(series: pd.Series, level: Any) -> str:
    denominator = int(series.notna().sum())
    count = int((series == level).sum()) if level is not None else 0
    if denominator == 0:
        return "0/0 (NA)"
    return f"{count}/{denominator} ({100 * count / denominator:.1f}%)"


def table_one(
    data: pd.DataFrame,
    group: str,
    continuous: list[str],
    categorical: list[str],
    group_order: list | None = None,
) -> pd.DataFrame:
    """Return a descriptive, two-group Table 1 without hypothesis tests.

    Continuous rows report both mean (sample SD) and median [Q1, Q3], with
    variable-specific nonmissing n. Categorical percentages use nonmissing
    observations in that column as their denominator. Quartiles use NumPy's
    default linear interpolation. Counts refer to rows, not distinct patients.

    ``group_order=[reference, comparison]`` is recommended; if omitted, labels
    follow first appearance. ``result.attrs['group_labels']`` preserves labels.
    """
    frame, continuous, categorical, labels = _prepare(
        data, group, continuous, categorical, group_order
    )
    subsets = [frame, frame.loc[frame[group] == labels[0]], frame.loc[frame[group] == labels[1]]]
    rows = [{
        "variable": "N (rows)", "level": "",
        "overall": str(len(subsets[0])), "group_1": str(len(subsets[1])),
        "group_2": str(len(subsets[2])), "missing_overall": 0,
        "missing_group_1": 0, "missing_group_2": 0,
    }]
    for name in continuous + categorical:
        missing_counts = [int(part[name].isna().sum()) for part in subsets]
        common = {
            "variable": name, "missing_overall": missing_counts[0],
            "missing_group_1": missing_counts[1], "missing_group_2": missing_counts[2],
        }
        if name in continuous:
            levels = ["mean (SD)", "median [Q1, Q3]"]
            for style in levels:
                summaries = [_continuous_summary(part[name], style) for part in subsets]
                rows.append({**common, "level": style, "overall": summaries[0],
                             "group_1": summaries[1], "group_2": summaries[2]})
        else:
            levels = _category_levels(frame[name])
            for level in levels or [None]:
                summaries = [_categorical_summary(part[name], level) for part in subsets]
                rows.append({**common, "level": str(level) if level is not None else "(all missing)",
                             "overall": summaries[0], "group_1": summaries[1],
                             "group_2": summaries[2]})
    result = pd.DataFrame(rows, columns=_TABLE_COLUMNS)
    result.attrs["group_labels"] = labels
    result.attrs["notes"] = [
        "Counts describe rows, not necessarily independent patients.",
        "Continuous summaries use variable-wise nonmissing observations; SD is the sample SD (ddof=1).",
        "Categorical cells are count/nonmissing denominator (percentage). Missing values are shown separately.",
        "This descriptive table contains no hypothesis tests. Group order is recorded in group_labels.",
    ]
    return result


def _continuous_comparison(x1: np.ndarray, x2: np.ndarray, method: str) -> dict:
    output = {"estimate": np.nan, "ci_low": np.nan, "ci_high": np.nan, "p_value": np.nan}
    n1, n2 = len(x1), len(x2)
    if method == "welch":
        output["test"] = "Welch t-test (two-sided)"
        output["notes"] = "Estimate is mean(group_2) - mean(group_1); unadjusted 95% Welch CI."
        if not n1 or not n2:
            output["notes"] += " Test omitted: one group has no nonmissing observations."
            return output
        output["estimate"] = float(x2.mean() - x1.mean())
        if min(n1, n2) < 2:
            output["notes"] += " Test and CI omitted: each group needs at least two observations."
            return output
        v1, v2 = float(x1.var(ddof=1)), float(x2.var(ddof=1))
        if not np.isfinite([v1, v2]).all():
            raise ValueError("Numeric scale caused variance overflow; rescale measurements before analysis.")
        if v1 + v2 == 0:
            output["notes"] += " Test and CI omitted: both sample variances are zero."
            return output
        if v1 == 0 or v2 == 0:
            output["notes"] += " One group has zero sample variance."
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Precision loss occurred.*", category=RuntimeWarning)
            test = stats.ttest_ind(x2, x1, equal_var=False, alternative="two-sided")
        interval = test.confidence_interval(confidence_level=0.95)
        output.update(p_value=float(test.pvalue), ci_low=float(interval.low), ci_high=float(interval.high))
    else:
        output["test"] = "Mann-Whitney U (two-sided, asymptotic)"
        output["notes"] = (
            "Estimate is rank-biserial correlation: P(group_2 > group_1) - P(group_2 < group_1). "
            "Tie-corrected normal approximation with continuity correction; no effect CI is implemented. "
            "This is a distributional comparison, not generally a test of equal medians."
        )
        if not n1 or not n2:
            output["notes"] += " Test omitted: one group has no nonmissing observations."
            return output
        test = stats.mannwhitneyu(x2, x1, alternative="two-sided", method="asymptotic", use_continuity=True)
        output.update(estimate=float(2 * test.statistic / (n1 * n2) - 1), p_value=float(test.pvalue))
        if min(n1, n2) < 10:
            output["notes"] += " Small group: the asymptotic p-value may be inaccurate; consider a prespecified exact/permutation analysis."
    return output


def _categorical_comparison(series1: pd.Series, series2: pd.Series, levels: list) -> dict:
    output = {"test": "Not performed", "estimate": np.nan, "ci_low": np.nan,
              "ci_high": np.nan, "p_value": np.nan, "notes": ""}
    if not series1.notna().any() or not series2.notna().any():
        output["notes"] = "Test omitted: one group has no nonmissing observations."
        return output
    if len(levels) < 2:
        output["notes"] = "Test omitted: fewer than two observed categories."
        return output
    counts = np.asarray([[int((series == level).sum()) for level in levels]
                         for series in [series1, series2]], dtype=int)
    if len(levels) == 2:
        # Row order is comparison, reference; column order is event, non-event.
        # This makes the odds ratio event odds in group_2 / event odds in group_1.
        table = counts[::-1, ::-1]
        test = stats.fisher_exact(table, alternative="two-sided")
        odds = stats.contingency.odds_ratio(table, kind="conditional")
        interval = odds.confidence_interval(confidence_level=0.95)
        output.update(test="Fisher exact (two-sided)", estimate=float(odds.statistic),
                      ci_low=float(interval.low), ci_high=float(interval.high), p_value=float(test.pvalue))
        output["notes"] = (
            f"Conditional odds ratio for group_2 versus group_1; event={levels[1]!r}, "
            f"reference category={levels[0]!r}; unadjusted 95% exact conditional CI. "
            "Category ordering is natural sort (mixed types use type/name sort); read the event label before interpreting."
        )
    else:
        test = stats.chi2_contingency(counts, correction=False)
        minimum = float(test.expected_freq.min())
        if minimum < 5:
            output["notes"] = (
                f"Sparse 2x{len(levels)} table: minimum expected cell count={minimum:.3g} < 5. "
                "Pearson chi-square p-value omitted; an exact/permutation method is needed."
            )
        else:
            output.update(test="Pearson chi-square", p_value=float(test.pvalue))
            output["notes"] = (
                f"Global association test across {len(levels)} categories; all expected counts >= 5. "
                "No single odds ratio or confidence interval is defined for this result."
            )
    return output


def compare_groups(
    data: pd.DataFrame,
    group: str,
    continuous: list[str],
    categorical: list[str],
    group_order: list | None = None,
    subject_col: str | None = None,
    continuous_test: str = "welch",
    adjust_method: str | None = "fdr_bh",
) -> pd.DataFrame:
    """Compare exactly two independent groups with explicit effect directions.

    ``continuous_test`` is ``'welch'`` or ``'mannwhitney'``. Binary categories use
    Fisher's two-sided exact test and the conditional odds ratio with exact CI.
    Larger tables are tested only if every expected cell count is at least five.

    Supply ``subject_col`` whenever rows represent patients. Repeated or missing
    IDs are rejected: independent tests do not account for bilateral knees or
    repeated follow-up. Without IDs, independence cannot be checked.

    ``adjust_method='fdr_bh'`` adjusts all finite p-values returned by this call
    as one family. This assumes independent tests or suitable positive
    dependence. ``'fdr_by'`` allows arbitrary dependence, and ``'none'``/None
    disables adjustment. Confidence intervals are not multiplicity-adjusted.
    """
    if continuous_test not in {"welch", "mannwhitney"}:
        raise ValueError("continuous_test must be 'welch' or 'mannwhitney'.")
    if adjust_method not in {"fdr_bh", "fdr_by", "none", None}:
        raise ValueError("adjust_method must be 'fdr_bh', 'fdr_by', 'none', or None.")
    frame, continuous, categorical, labels = _prepare(data, group, continuous, categorical, group_order)
    if subject_col is not None:
        if not isinstance(subject_col, str) or subject_col not in data.columns:
            raise ValueError("subject_col must name an existing patient/subject ID column.")
        _check_labels(data[subject_col], subject_col, allow_missing=False)
        if data[subject_col].duplicated().any():
            raise ValueError(
                "Repeated subject IDs detected. Independent-group tests are invalid for repeated/bilateral "
                "observations; use a prespecified patient-level analysis or a cluster-aware regression."
            )
    parts = [frame.loc[frame[group] == label] for label in labels]
    rows = []
    for name in continuous + categorical:
        first, second = parts[0][name], parts[1][name]
        if name in continuous:
            comparison = _continuous_comparison(first.dropna().to_numpy(dtype=float),
                                                second.dropna().to_numpy(dtype=float), continuous_test)
        else:
            comparison = _categorical_comparison(first, second, _category_levels(frame[name]))
        missing1, missing2 = int(first.isna().sum()), int(second.isna().sum())
        comparison["notes"] += f" Missing excluded by variable: group_1={missing1}, group_2={missing2}."
        rows.append({"variable": name, "kind": "continuous" if name in continuous else "categorical",
                     "group_1": labels[0], "group_2": labels[1], "n1": int(first.notna().sum()),
                     "n2": int(second.notna().sum()), "p_adjusted": np.nan, **comparison})
    result = pd.DataFrame(rows, columns=_COMPARISON_COLUMNS)
    finite = np.isfinite(result["p_value"].to_numpy(dtype=float))
    if finite.any():
        raw = result.loc[finite, "p_value"].to_numpy(dtype=float)
        adjusted = (stats.false_discovery_control(raw, method="bh" if adjust_method == "fdr_bh" else "by")
                    if adjust_method in {"fdr_bh", "fdr_by"} else raw.copy())
        result.loc[finite, "p_adjusted"] = adjusted
    result.attrs["group_labels"] = labels
    result.attrs["adjust_method"] = adjust_method or "none"
    result.attrs["adjustment_family_size"] = int(finite.sum())
    result.attrs["notes"] = [
        "Independent observations are required; independence cannot be established without design information.",
        "Subject IDs were checked for uniqueness." if subject_col else "No subject ID provided: repeated observations could not be checked.",
        "Missing values are excluded separately for each variable; missingness can bias inference.",
        f"Multiplicity adjustment: {adjust_method or 'none'} across the {int(finite.sum())} finite p-values in this call.",
        "Benjamini-Hochberg requires independent or suitably positively dependent tests; Benjamini-Yekutieli allows arbitrary dependence.",
        "All tests are two-sided. Confidence intervals are 95% and are not multiplicity-adjusted.",
    ]
    return result
