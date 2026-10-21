"""Reproducible artificial datasets; no patient records are included."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .io import template_config


def synthetic_cohort(seed: int = 20261022, bilateral: bool = False) -> pd.DataFrame:
    """Simulate 160 subjects, with 16 additional knees if bilateral=True."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(160):
        age = float(np.clip(rng.normal(65, 7), 45, 85))
        bmi = float(np.clip(rng.normal(26, 3), 18, 38))
        sex = "Female" if rng.random() < 0.6 else "Male"
        group = "Intervention" if rng.random() < 0.5 else "Control"
        person_effect = rng.normal(0, 2.8)
        latent_angle = rng.normal(28, 5)
        # Both calls generate the same first-knee records. Second-knee generation
        # always occurs, and inclusion alone depends on the bilateral flag.
        for knee in range(2):
            baseline = float(np.clip(rng.normal(24, 6), 5, 43))
            angle = latent_angle + rng.normal(0, 0.6)
            outcome = float(np.clip(15 + 0.65 * baseline + 1.5 * (group == "Intervention")
                                   - 0.1 * (age - 65) - 0.25 * (bmi - 26)
                                   + person_effect + rng.normal(0, 2.2), 0, 48))
            row = {"patient_id": f"SYN-{i + 1:03d}", "knee_id": f"SYN-{i + 1:03d}-{knee + 1}",
                   "group": group, "age": round(age, 2), "bmi": round(bmi, 2), "sex": sex,
                   "oks_pre": round(baseline, 2), "oks_post": round(outcome, 2),
                   "alpha_rater1": round(angle + rng.normal(0, 1), 3),
                   "alpha_rater2": round(angle + 0.3 + rng.normal(0, 1), 3)}
            if i in {13, 87}:
                row["bmi"] = np.nan
            if i == 6 and knee == 0:
                row["oks_post"] = np.nan
            if i == 37:
                row["alpha_rater2"] = np.nan
            if i == 52:
                row["sex"] = np.nan
            if knee == 0 or (bilateral and i % 10 == 0):
                rows.append(row)
    return pd.DataFrame(rows)


def demo_config(bilateral: bool = False, seed: int = 20261022) -> dict:
    config = template_config()
    config["title"] = "SYNTHETIC EXAMPLE — " + ("bilateral knee cohort" if bilateral else "independent patient cohort")
    config["comparisons"]["enabled"] = not bilateral
    if not bilateral:
        config["icc"] = {"raters": ["alpha_rater1", "alpha_rater2"], "subject_id": "patient_id",
                         "n_boot": 2000, "seed": seed}
    return config
