"""Auditable ordinary least-squares models with explicit covariance choices.

No formula is evaluated. Categorical columns are encoded with a declared,
deterministically selected reference category. Numeric estimates are computed
by statsmodels; this module validates the design and records analysis choices.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm


def _numeric(series: pd.Series, name: str) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series) or pd.api.types.is_timedelta64_dtype(series):
        raise ValueError(f"{name!r} must contain numeric measurements, not dates or durations.")
    if pd.api.types.is_complex_dtype(series):
        raise ValueError(f"{name!r} must contain real numbers.")
    try:
        out = pd.to_numeric(series, errors="raise")
        if pd.api.types.is_complex_dtype(out):
            raise ValueError("complex values")
        out = pd.Series(out.to_numpy(dtype=float, na_value=np.nan), index=series.index)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name!r} contains invalid numeric values.") from exc
    if (out.isna() & series.notna()).any():
        raise ValueError(f"{name!r} contains values that would be silently converted to missing.")
    if not np.isfinite(out.dropna().to_numpy()).all():
        raise ValueError(f"{name!r} contains infinite numeric values.")
    return out


def _names(values: list[str], label: str) -> list[str]:
    if not isinstance(values, (list, tuple)) or any(not isinstance(x, str) or not x for x in values):
        raise ValueError(f"{label} must be a list of nonempty column names.")
    if len(set(values)) != len(values):
        raise ValueError(f"{label} contains duplicate names.")
    return list(values)


def fit_linear(
    data: pd.DataFrame,
    outcome: str,
    predictors: list[str],
    categorical: list[str] | None = None,
    subject_col: str | None = None,
) -> dict:
    """Fit a complete-case linear model for a continuous outcome.

    HC3 standard errors and t inference are used for independent observations.
    Repeated subject IDs switch to one-way cluster-robust standard errors with
    a finite-sample covariance correction and t inference with G - 1 degrees
    of freedom. This adjusts uncertainty; it is not a mixed-effects model and
    does not remove confounding or change observation weighting.

    ``categorical`` is a subset of ``predictors``. Reference levels are sorted
    by their string representation and recorded in metadata. Supply subject
    IDs whenever observations may come from the same person.
    """
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("data must be a nonempty pandas DataFrame.")
    if not data.columns.is_unique:
        raise ValueError("Duplicate column names are not supported.")
    if not isinstance(outcome, str) or not outcome:
        raise ValueError("outcome must be a nonempty column name.")
    predictors = _names(predictors, "predictors")
    categorical = _names([] if categorical is None else categorical, "categorical")
    if not predictors:
        raise ValueError("At least one predictor is required.")
    if outcome in predictors:
        raise ValueError("The outcome cannot also be a predictor.")
    if not set(categorical).issubset(predictors):
        raise ValueError("Every categorical column must also be listed in predictors.")
    if subject_col is not None and (not isinstance(subject_col, str) or not subject_col):
        raise ValueError("subject_col must be a nonempty column name or None.")
    if subject_col in [outcome, *predictors]:
        raise ValueError("The subject identifier cannot also be an outcome or predictor.")
    required = [outcome, *predictors] + ([] if subject_col is None else [subject_col])
    absent = [x for x in required if x not in data.columns]
    if absent:
        raise ValueError(f"Missing columns: {absent}.")

    # A fresh row index avoids accidental alignment when the input index repeats.
    work = data.loc[:, required].copy().reset_index(drop=True)
    for name in [outcome, *[x for x in predictors if x not in categorical]]:
        work[name] = _numeric(work[name], name)
    for name in categorical:
        observed = work[name].dropna()
        if observed.map(lambda x: isinstance(x, (float, np.floating)) and not np.isfinite(x)).any():
            raise ValueError(f"Categorical column {name!r} contains infinite values.")
        if observed.map(lambda x: isinstance(x, str) and not x.strip()).any():
            raise ValueError(f"Categorical column {name!r} contains blank labels; encode missing values explicitly.")

    analysis_cols = [outcome, *predictors]
    missing_by_column = {name: int(work[name].isna().sum()) for name in analysis_cols}
    complete = work.dropna(subset=analysis_cols).copy()
    if complete.empty:
        raise ValueError("No complete outcome/predictor observations remain.")
    if subject_col is not None:
        ids = complete[subject_col]
        if ids.isna().any() or ids.map(lambda x: isinstance(x, str) and not x.strip()).any():
            raise ValueError("Subject IDs are missing on otherwise complete analysis rows.")
        if ids.map(lambda x: isinstance(x, (float, np.floating)) and not np.isfinite(x)).any():
            raise ValueError("Subject IDs contain infinite values.")
    if complete[outcome].nunique() < 2:
        raise ValueError("The outcome is constant after complete-case selection.")

    design = pd.DataFrame({"Intercept": np.ones(len(complete))}, index=complete.index)
    references: dict[str, str] = {}
    for name in predictors:
        if complete[name].nunique() < 2:
            raise ValueError(f"Predictor {name!r} is constant after complete-case selection.")
        if name in categorical:
            levels = sorted(pd.unique(complete[name]), key=lambda x: (str(x), type(x).__name__))
            labels = [str(x) for x in levels]
            if len(set(labels)) != len(labels):
                raise ValueError(f"Categorical column {name!r} has ambiguous mixed-type labels.")
            references[name] = labels[0]
            for value, label in zip(levels[1:], labels[1:]):
                term = f"{name}[{label}]"
                if term in design.columns or term in [x for x in predictors if x not in categorical]:
                    raise ValueError(f"Encoded term name {term!r} collides with another predictor.")
                design[term] = (complete[name] == value).astype(float)
        else:
            if name in design.columns:
                raise ValueError(f"Predictor name {name!r} collides with an encoded model term.")
            design[name] = complete[name].astype(float)
    n, p = design.shape
    if n <= p + 1:
        raise ValueError(f"Too few complete observations ({n}) for {p} model parameters; require n > p + 1.")
    # Rank is checked after column scaling so units alone do not imply collinearity.
    scaled = design.to_numpy(dtype=float).copy()
    for j in range(1, p):
        scaled[:, j] = (scaled[:, j] - scaled[:, j].mean()) / scaled[:, j].std()
    if not np.isfinite(scaled).all() or np.linalg.matrix_rank(scaled) < p:
        raise ValueError("The model design is rank deficient; remove redundant predictors.")

    notes = [
        "Complete-case analysis; missing data were not imputed.",
        "Coefficients describe associations. Covariance correction does not resolve confounding or model misspecification.",
        "Inspect linearity, influential observations, and residuals before scientific interpretation.",
    ]
    n_clusters = None
    repeated = False
    if subject_col is not None:
        n_clusters = int(complete[subject_col].nunique())
        repeated = n_clusters < n
    else:
        notes.append("No subject identifier supplied: independence is assumed and cannot be verified.")

    basic = sm.OLS(complete[outcome].to_numpy(dtype=float), design, missing="raise").fit()
    # A design can be algebraically full rank after scaling yet lose columns
    # in the raw pseudoinverse when predictor units differ by many orders of
    # magnitude. Do not report finite but incorrect coefficients in that case.
    if basic.model.rank != p:
        raise ValueError(
            "The fitted design lost numerical rank in its original units. "
            "Rescale or center the numeric predictors and rerun the analysis."
        )
    residual_scale = float(np.max(np.abs(basic.resid)))
    outcome_scale = max(float(complete[outcome].std()), np.finfo(float).tiny)
    if residual_scale <= 1e-12 * outcome_scale:
        raise ValueError("Residual variance is effectively zero; inferential statistics are not meaningful.")
    if repeated:
        if n_clusters < 3:
            raise ValueError("Cluster-robust inference requires at least 3 observed subject clusters; more are usually needed.")
        groups, _ = pd.factorize(complete[subject_col], sort=False)
        robust = basic.get_robustcov_results(
            cov_type="cluster", groups=groups, use_correction=True, df_correction=True, use_t=True
        )
        covariance = "cluster"
        if n_clusters < 30:
            notes.append(
                f"Only {n_clusters} subject clusters: cluster-robust confidence intervals and p-values may be unreliable. "
                "30 is a caution threshold, not a guarantee of adequacy."
            )
        if n_clusters <= p:
            notes.append("The number of clusters is no greater than the number of parameters; robust covariance may be singular.")
        notes.append("Rows retain equal OLS weights; subjects contributing more rows receive more weight.")
    else:
        leverage = basic.get_influence().hat_matrix_diag
        if np.any(leverage >= 1 - 1e-12):
            raise ValueError("An observation has unit leverage; HC3 standard errors are undefined.")
        robust = basic.get_robustcov_results(cov_type="HC3", use_t=True)
        covariance = "HC3"

    intervals = np.asarray(robust.conf_int(alpha=0.05))
    values = np.column_stack([robust.params, robust.bse, intervals, robust.pvalues])
    if not np.isfinite(values).all():
        raise ValueError("The fitted model produced nonfinite coefficients or uncertainty estimates.")
    if np.any(np.asarray(robust.bse) <= 0):
        raise ValueError("A coefficient has zero estimated standard error; robust inference is degenerate.")
    coefficients = pd.DataFrame(
        {
            "term": list(design.columns),
            "estimate": np.asarray(robust.params),
            "std_error": np.asarray(robust.bse),
            "ci_low": intervals[:, 0],
            "ci_high": intervals[:, 1],
            "p_value": np.asarray(robust.pvalues),
        }
    )
    return {
        "coefficients": coefficients,
        "metadata": {
            "n_input": int(len(data)),
            "n_used": int(n),
            "n_dropped": int(len(data) - n),
            "missing_by_column": missing_by_column,
            "outcome": outcome,
            "predictors": predictors,
            "categorical": categorical,
            "categorical_reference": references,
            "terms": list(design.columns),
            "covariance": covariance,
            "n_clusters": n_clusters,
            "subject_col": subject_col,
            "repeated_subjects": repeated,
            "inference": "Student t",
            "inference_df": float(getattr(robust, "df_resid_inference", robust.df_resid)),
            "confidence_level": 0.95,
            "cluster_small_sample_correction": bool(repeated),
            "r_squared": float(basic.rsquared),
            "adjusted_r_squared": float(basic.rsquared_adj),
            "condition_number_scaled": float(np.linalg.cond(scaled)),
            "notes": notes,
        },
    }
