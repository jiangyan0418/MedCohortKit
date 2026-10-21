"""Absolute-agreement ICC estimates with reproducible subject bootstrap CIs."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _icc_points(values: np.ndarray) -> np.ndarray:
    """Two-way absolute-agreement ANOVA estimators, without truncating negatives."""
    n, k = values.shape
    scale = np.max(np.abs(values))
    if not np.isfinite(scale) or scale == 0:
        return np.array([np.nan, np.nan])
    values = values / scale
    grand = values.mean()
    subjects = values.mean(axis=1)
    raters = values.mean(axis=0)
    ms_subject = k * np.square(subjects - grand).sum() / (n - 1)
    ms_rater = n * np.square(raters - grand).sum() / (k - 1)
    residual = values - subjects[:, None] - raters[None, :] + grand
    ms_error = np.square(residual).sum() / ((n - 1) * (k - 1))
    numerator = ms_subject - ms_error
    denominators = np.array(
        [ms_subject + (k - 1) * ms_error + k * (ms_rater - ms_error) / n,
         ms_subject + (ms_rater - ms_error) / n]
    )
    if np.any(denominators <= 0):
        return np.array([np.nan, np.nan])
    return numerator / denominators


def icc_absolute(
    data: pd.DataFrame,
    raters: list[str],
    subject_col: str | None = None,
    n_boot: int = 2000,
    seed: int = 20261022,
) -> dict:
    """Return ICC(A,1), ICC(A,k), and approximate 95% percentile intervals.

    Each row must represent one independent subject/target measured by the
    same raters. Complete rows of ratings are resampled together. The interval
    describes subject-sampling uncertainty conditional on these raters; it
    does not resample raters and is not the analytic F-based random-rater CI.
    This implementation uses absolute-agreement point estimators equivalent
    to ICC(2,1)/ICC(2,k). Select the random/mixed rater interpretation based on
    the actual design, not the software label.

    Missing ratings are removed listwise and counted. Negative ICC estimates
    are preserved. Nonpositive denominators are treated as undefined, rather
    than reporting an uninterpretable average-measure ICC above one.
    """
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("data must be a nonempty pandas DataFrame.")
    if not data.columns.is_unique:
        raise ValueError("Duplicate column names are not supported.")
    if not isinstance(raters, (list, tuple)) or any(not isinstance(x, str) or not x for x in raters):
        raise ValueError("raters must be a list of nonempty column names.")
    raters = list(raters)
    if len(raters) < 2 or len(set(raters)) != len(raters):
        raise ValueError("Provide at least two distinct rater columns.")
    if subject_col is not None and (not isinstance(subject_col, str) or not subject_col):
        raise ValueError("subject_col must be a nonempty column name or None.")
    if subject_col in raters:
        raise ValueError("The subject identifier cannot also be a rater column.")
    required = raters + ([] if subject_col is None else [subject_col])
    absent = [x for x in required if x not in data.columns]
    if absent:
        raise ValueError(f"Missing columns: {absent}.")
    if isinstance(n_boot, bool) or not isinstance(n_boot, (int, np.integer)) or n_boot < 200:
        raise ValueError("n_boot must be an integer of at least 200; 2000 or more is recommended.")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError("seed must be a nonnegative integer.")

    work = data.loc[:, required].copy().reset_index(drop=True)
    for name in raters:
        series = work[name]
        if (pd.api.types.is_datetime64_any_dtype(series) or pd.api.types.is_timedelta64_dtype(series)
                or pd.api.types.is_complex_dtype(series)):
            raise ValueError(f"Rater column {name!r} must contain real numeric measurements.")
        try:
            numeric = pd.to_numeric(series, errors="raise")
            if pd.api.types.is_complex_dtype(numeric):
                raise ValueError("complex values")
            numeric = pd.Series(numeric.to_numpy(dtype=float, na_value=np.nan), index=series.index)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Rater column {name!r} contains invalid numeric values.") from exc
        if (numeric.isna() & series.notna()).any():
            raise ValueError(f"Rater column {name!r} contains values that would be silently converted to missing.")
        if not np.isfinite(numeric.dropna().to_numpy()).all():
            raise ValueError(f"Rater column {name!r} contains infinite numeric values.")
        work[name] = numeric
    if subject_col is not None:
        ids = work[subject_col]
        if ids.isna().any() or ids.map(lambda x: isinstance(x, str) and not x.strip()).any():
            raise ValueError("Subject IDs must be nonmissing.")
        if ids.map(lambda x: isinstance(x, (float, np.floating)) and not np.isfinite(x)).any():
            raise ValueError("Subject IDs contain infinite values.")
        if ids.duplicated().any():
            raise ValueError("ICC requires one independent target per row; duplicate subject IDs were found.")
    complete = work.dropna(subset=raters)
    n, k = len(complete), len(raters)
    if n < 3:
        raise ValueError("At least three complete subjects are required for ICC.")
    values = complete[raters].to_numpy(dtype=float)
    estimates = _icc_points(values)
    if not np.isfinite(estimates).all():
        raise ValueError("ICC is undefined: zero variance or a nonpositive estimated variance denominator.")

    rng = np.random.default_rng(int(seed))
    bootstrap = np.empty((int(n_boot), 2))
    for i in range(int(n_boot)):
        sample = values[rng.integers(0, n, size=n)]
        bootstrap[i] = _icc_points(sample)
    valid = np.isfinite(bootstrap).all(axis=1)
    used = int(valid.sum())
    discarded = int(n_boot - used)
    if used < max(100, int(0.8 * n_boot)):
        raise ValueError(
            f"Too many undefined bootstrap replicates ({discarded}/{n_boot}); "
            "an ICC percentile interval would be unstable for these data."
        )
    intervals = np.quantile(bootstrap[valid], [0.025, 0.975], axis=0)
    notes = [
        "Absolute-agreement ANOVA point estimators equivalent to ICC(2,1) and ICC(2,k).",
        "95% percentile bootstrap resamples complete subject rows with replacement, holding raters fixed.",
        "Intervals are conditional on the observed raters, not analytic F-based intervals for random-rater generalization.",
        "Listwise deletion of incomplete ratings; no imputation.",
        "Subjects must be independent. Single and average-measure ICC answer different reliability questions.",
    ]
    if subject_col is None:
        notes.append("No subject identifier supplied: duplicate-target detection was unavailable.")
    if n < 30:
        notes.append("Fewer than 30 complete subjects: bootstrap intervals may be unstable; this threshold is a caution, not a rule.")
    if n_boot < 2000:
        notes.append("Fewer than 2000 bootstrap draws were requested; Monte Carlo uncertainty may be appreciable.")
    if discarded:
        notes.append(
            f"Discarded {discarded}/{n_boot} bootstrap replicates with undefined/nonpositive variance denominators. "
            "The reported interval uses the remaining replicates and may be distorted near degeneracy."
        )
    return {
        "estimates": pd.DataFrame({
            "type": ["ICC(A,1)", "ICC(A,k)"],
            "icc": estimates,
            "ci_low": intervals[0],
            "ci_high": intervals[1],
            "n_subjects": [n, n],
            "n_raters": [k, k],
        }),
        "metadata": {
            "n_input": int(len(data)),
            "n_used": int(n),
            "n_dropped": int(len(data) - n),
            "raters": raters,
            "subject_col": subject_col,
            "n_raters": int(k),
            "n_boot": int(n_boot),
            "bootstrap_used": used,
            "bootstrap_discarded": discarded,
            "seed": int(seed),
            "confidence_level": 0.95,
            "ci_method": "subject-row percentile bootstrap; conditional on observed raters",
            "notes": notes,
        },
    }
