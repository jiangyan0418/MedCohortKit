"""ICC checks against hand-derived ANOVA quantities and design edge cases."""

import unittest

import numpy as np
import pandas as pd

from medcohortkit.reliability import _icc_points, icc_absolute


class ReliabilityTests(unittest.TestCase):
    def test_hand_computed_reference(self):
        # Rows [1,2], [2,2], [3,4], [4,4]: MS_subject=17/6,
        # MS_rater=1/2, MS_error=1/6. ICC(A,1)=16/19; ICC(A,2)=32/35.
        values = np.array([[1, 2], [2, 2], [3, 4], [4, 4]], dtype=float)
        np.testing.assert_allclose(_icc_points(values), [16 / 19, 32 / 35], rtol=1e-12)

    def test_perfect_agreement_and_bootstrap_degeneracy(self):
        frame = pd.DataFrame({"a": [1, 2, 3, 4], "b": [1, 2, 3, 4]})
        result = icc_absolute(frame, ["a", "b"], n_boot=500, seed=17)
        np.testing.assert_allclose(result["estimates"][["icc", "ci_low", "ci_high"]], 1)
        self.assertGreater(result["metadata"]["bootstrap_discarded"], 0)

    def test_systematic_shift_lowers_absolute_agreement(self):
        values = np.column_stack([np.arange(1.0, 21.0), np.arange(1.0, 21.0) + 8])
        single, average = _icc_points(values)
        self.assertGreater(single, 0)
        self.assertLess(single, 1)
        self.assertGreater(average, single)
        # The consistency ICC for this exact additive shift is one.

    def test_negative_estimates_not_clipped(self):
        values = np.array([[1, 3], [2, 1], [3, 2], [4, 1], [2, 4]], dtype=float)
        points = _icc_points(values)
        self.assertTrue(np.isfinite(points).all())
        self.assertLess(points[0], 0)
        self.assertLess(points[1], 0)

    def test_reproducible_ci_and_missingness(self):
        rng = np.random.default_rng(31)
        latent = rng.normal(size=50)
        frame = pd.DataFrame({"a": latent + rng.normal(scale=0.3, size=50),
                              "b": latent + rng.normal(scale=0.3, size=50), "id": np.arange(50)})
        frame.loc[0, "b"] = np.nan
        a = icc_absolute(frame, ["a", "b"], subject_col="id", n_boot=300, seed=11)
        b = icc_absolute(frame, ["a", "b"], subject_col="id", n_boot=300, seed=11)
        pd.testing.assert_frame_equal(a["estimates"], b["estimates"])
        self.assertEqual(a["metadata"]["n_dropped"], 1)
        self.assertIn("conditional", a["metadata"]["ci_method"])

    def test_constant_and_duplicate_subjects_rejected(self):
        with self.assertRaisesRegex(ValueError, "undefined"):
            icc_absolute(pd.DataFrame({"a": [1] * 4, "b": [1] * 4}), ["a", "b"], n_boot=200)
        frame = pd.DataFrame({"a": [1, 2, 3, 4], "b": [1, 2, 3, 4], "id": [1, 1, 2, 3]})
        with self.assertRaisesRegex(ValueError, "duplicate subject"):
            icc_absolute(frame, ["a", "b"], subject_col="id", n_boot=200)

    def test_invalid_values_and_parameters_rejected(self):
        frame = pd.DataFrame({"a": [1, 2, 3, 4], "b": [1, 2, 3, 5]})
        for bad in ["invalid", "", np.inf]:
            broken = frame.astype({"a": object})
            broken.loc[0, "a"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                icc_absolute(broken, ["a", "b"], n_boot=200)
        with self.assertRaisesRegex(ValueError, "at least 200"):
            icc_absolute(frame, ["a", "b"], n_boot=5)
        with self.assertRaisesRegex(ValueError, "three complete"):
            icc_absolute(frame.head(2), ["a", "b"], n_boot=200)


if __name__ == "__main__":
    unittest.main()
