"""Regression reference comparisons and meaningful invalid-design checks."""

import unittest

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from medcohortkit.models import fit_linear


class LinearModelTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(7701)
        x = rng.normal(size=80)
        z = rng.normal(size=80)
        self.data = pd.DataFrame({"y": 3 + 2 * x - z + rng.normal(scale=1 + abs(x)), "x": x, "z": z})
        self.data["id"] = np.arange(80)

    def test_hc3_matches_statsmodels_and_t_reference(self):
        answer = fit_linear(self.data, "y", ["x", "z"], subject_col="id")
        expected = sm.OLS(self.data.y, sm.add_constant(self.data[["x", "z"]])).fit().get_robustcov_results("HC3", use_t=True)
        got = answer["coefficients"]
        np.testing.assert_allclose(got.estimate, expected.params, rtol=1e-12)
        np.testing.assert_allclose(got.std_error, expected.bse, rtol=1e-12)
        np.testing.assert_allclose(got[["ci_low", "ci_high"]], expected.conf_int(), rtol=1e-12)
        np.testing.assert_allclose(got.p_value, 2 * stats.t.sf(abs(got.estimate / got.std_error), 77), rtol=1e-12)
        self.assertEqual(answer["metadata"]["covariance"], "HC3")
        self.assertEqual(answer["metadata"]["inference_df"], 77)

    def test_clusters_match_corrected_statsmodels_and_group_df(self):
        self.data["id"] = np.repeat(np.arange(40), 2)
        answer = fit_linear(self.data, "y", ["x", "z"], subject_col="id")
        expected = sm.OLS(self.data.y, sm.add_constant(self.data[["x", "z"]])).fit().get_robustcov_results(
            "cluster", groups=self.data.id, use_correction=True, df_correction=True, use_t=True
        )
        np.testing.assert_allclose(answer["coefficients"].std_error, expected.bse, rtol=1e-12)
        np.testing.assert_allclose(answer["coefficients"].p_value, expected.pvalues, rtol=1e-12)
        self.assertEqual(answer["metadata"]["inference_df"], 39)
        self.assertEqual(answer["metadata"]["n_clusters"], 40)

    def test_complete_cases_log_and_do_not_drop_unneeded_columns(self):
        self.data.loc[0, "y"] = np.nan
        self.data.loc[1, "x"] = np.nan
        self.data["unused"] = np.nan
        answer = fit_linear(self.data, "y", ["x", "z"], subject_col="id")
        self.assertEqual(answer["metadata"]["n_used"], 78)
        self.assertEqual(answer["metadata"]["n_dropped"], 2)

    def test_categorical_reference_is_explicit(self):
        self.data["sex"] = ["M", "F"] * 40
        result = fit_linear(self.data, "y", ["x", "sex"], categorical=["sex"], subject_col="id")
        self.assertEqual(result["metadata"]["categorical_reference"], {"sex": "F"})
        self.assertIn("sex[M]", result["coefficients"].term.tolist())

    def test_invalid_numeric_and_infinite_not_silently_dropped(self):
        for bad in ["oops", "", np.inf]:
            frame = self.data.astype({"x": object})
            frame.loc[0, "x"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                fit_linear(frame, "y", ["x", "z"])

    def test_rank_deficient_design_rejected(self):
        self.data["twox"] = 2 * self.data.x
        with self.assertRaisesRegex(ValueError, "rank deficient"):
            fit_linear(self.data, "y", ["x", "twox"])

    def test_extreme_predictor_units_cannot_silently_drop_intercept(self):
        x = np.linspace(1.0, 3.0, 80)
        y = 3 + 2 * x + np.random.default_rng(123).normal(0, 0.3, 80)
        regular = fit_linear(pd.DataFrame({"x": x, "y": y}), "y", ["x"])
        self.assertEqual(regular["metadata"]["inference_df"], 78)
        self.assertGreater(regular["metadata"]["r_squared"], 0.9)
        # This is full rank after standardization, but the raw statsmodels
        # pseudoinverse drops the intercept. It must fail before reporting.
        with self.assertRaisesRegex(ValueError, "lost numerical rank.*Rescale"):
            fit_linear(pd.DataFrame({"x": x * 1e15, "y": y}), "y", ["x"])

    def test_id_required_on_otherwise_complete_rows(self):
        self.data.loc[0, "id"] = np.nan
        with self.assertRaisesRegex(ValueError, "Subject IDs"):
            fit_linear(self.data, "y", ["x", "z"], subject_col="id")

    def test_too_few_clusters_rejected(self):
        self.data["id"] = np.repeat(["a", "b"], 40)
        with self.assertRaisesRegex(ValueError, "at least 3"):
            fit_linear(self.data, "y", ["x", "z"], subject_col="id")

    def test_duplicate_input_index_does_not_change_results(self):
        expected = fit_linear(self.data, "y", ["x", "z"])["coefficients"]
        self.data.index = [0] * 80
        actual = fit_linear(self.data, "y", ["x", "z"])["coefficients"]
        pd.testing.assert_frame_equal(expected, actual)

    def test_constant_outcome_and_outcome_predictor_rejected(self):
        with self.assertRaisesRegex(ValueError, "cannot also"):
            fit_linear(self.data, "y", ["y"])
        self.data["y"] = 5.0
        with self.assertRaisesRegex(ValueError, "constant"):
            fit_linear(self.data, "y", ["x", "z"])


if __name__ == "__main__":
    unittest.main()
