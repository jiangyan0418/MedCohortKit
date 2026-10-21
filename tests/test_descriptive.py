"""Numerical reference and misuse-prevention checks for two-group analyses."""

import unittest

import numpy as np
import pandas as pd
from scipy import stats

from medcohortkit.descriptive import compare_groups, table_one


class DescriptiveTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({
            "group": ["A"] * 5 + ["B"] * 6,
            "patient": list(range(11)),
            "age": [52, 57, 62, 64, np.nan, 48, 54, 70, 72, 74, 77],
            "sex": ["F", "M", "M", None, "F", "F", "M", "M", "F", "F", "M"],
        })

    def test_welch_matches_scipy_and_direction(self):
        result = compare_groups(self.data, "group", ["age"], [], ["A", "B"], "patient")
        row = result.iloc[0]
        first = self.data.loc[self.data.group == "A", "age"].dropna().to_numpy()
        second = self.data.loc[self.data.group == "B", "age"].to_numpy()
        expected = stats.ttest_ind(second, first, equal_var=False)
        ci = expected.confidence_interval()
        self.assertAlmostEqual(row.estimate, second.mean() - first.mean())
        self.assertAlmostEqual(row.p_value, expected.pvalue)
        self.assertAlmostEqual(row.ci_low, ci.low)
        self.assertAlmostEqual(row.ci_high, ci.high)
        self.assertEqual((row.n1, row.n2), (4, 6))
        reverse = compare_groups(self.data, "group", ["age"], [], ["B", "A"]).iloc[0]
        self.assertAlmostEqual(reverse.estimate, -row.estimate)
        self.assertAlmostEqual(reverse.ci_low, -row.ci_high)

    def test_table_missing_denominators_and_rows(self):
        result = table_one(self.data, "group", ["age"], ["sex"], ["A", "B"])
        female = result.loc[(result.variable == "sex") & (result.level == "F")].iloc[0]
        self.assertEqual(female.group_1, "2/4 (50.0%)")
        self.assertEqual(female.group_2, "3/6 (50.0%)")
        self.assertEqual(female.missing_group_1, 1)
        age = result.loc[(result.variable == "age") & (result.level == "mean (SD)")].iloc[0]
        self.assertTrue(age.group_1.endswith("n=4"))
        self.assertEqual(age.missing_overall, 1)
        self.assertEqual(result.attrs["group_labels"], ["A", "B"])
        self.assertEqual(result.iloc[0].overall, "11")

    def test_fisher_conditional_or_known_orientation(self):
        data = pd.DataFrame({"group": ["A"] * 6 + ["B"] * 10,
                             "event": ["No"] * 5 + ["Yes"] + ["No"] * 2 + ["Yes"] * 8})
        row = compare_groups(data, "group", [], ["event"], ["A", "B"]).iloc[0]
        expected = stats.contingency.odds_ratio([[8, 2], [1, 5]], kind="conditional")
        self.assertAlmostEqual(row.p_value, 0.034965034965034975)
        self.assertAlmostEqual(row.estimate, expected.statistic)
        self.assertAlmostEqual(row.ci_low, expected.confidence_interval().low)
        self.assertIn("event='Yes'", row.notes)
        self.assertGreater(row.estimate, 1)

    def test_fisher_zero_cell_is_not_silently_corrected(self):
        data = pd.DataFrame({"g": [0] * 6 + [1] * 6, "e": [0] * 6 + [0] * 2 + [1] * 4})
        row = compare_groups(data, "g", [], ["e"], [0, 1]).iloc[0]
        self.assertTrue(np.isinf(row.estimate))
        self.assertTrue(np.isinf(row.ci_high))
        self.assertTrue(np.isfinite(row.p_value))

    def test_sparse_multi_category_is_not_tested(self):
        data = pd.DataFrame({"g": [0, 0, 0, 1, 1, 1], "cat": ["a", "b", "c", "a", "b", "c"]})
        row = compare_groups(data, "g", [], ["cat"]).iloc[0]
        self.assertTrue(np.isnan(row.p_value))
        self.assertTrue(np.isnan(row.p_adjusted))
        self.assertIn("Sparse 2x3", row.notes)

    def test_dense_multi_category_matches_reference(self):
        counts = [[10, 10, 20], [20, 20, 20]]
        groups, cats = [], []
        for g, row in enumerate(counts):
            for category, count in enumerate(row):
                groups.extend([g] * count)
                cats.extend([category] * count)
        data = pd.DataFrame({"g": groups, "c": cats})
        result = compare_groups(data, "g", [], ["c"]).iloc[0]
        self.assertAlmostEqual(result.p_value, 0.24935220877729619)
        self.assertEqual(result.test, "Pearson chi-square")

    def test_rank_biserial_direction_and_ties(self):
        data = pd.DataFrame({"g": ["A"] * 4 + ["B"] * 4,
                             "v": [1, 2, 2, 3, 2, 3, 4, 4]})
        row = compare_groups(data, "g", ["v"], [], ["A", "B"], continuous_test="mannwhitney").iloc[0]
        first, second = np.array([1, 2, 2, 3]), np.array([2, 3, 4, 4])
        direct_effect = np.sign(second[:, None] - first[None, :]).mean()
        self.assertAlmostEqual(row.estimate, direct_effect)
        self.assertGreater(row.estimate, 0)
        expected = stats.mannwhitneyu(second, first, method="asymptotic", alternative="two-sided")
        self.assertAlmostEqual(row.p_value, expected.pvalue)
        self.assertIn("not generally a test of equal medians", row.notes)

    def test_adjustment_excludes_unavailable_tests(self):
        data = self.data.assign(other=[2, 3, 4, 5, 6, 8, 7, 6, 9, 12, 11], constant=1)
        result = compare_groups(data, "group", ["age", "other", "constant"], ["sex"])
        finite = result.p_value.notna()
        expected = stats.false_discovery_control(result.loc[finite, "p_value"].to_numpy())
        np.testing.assert_allclose(result.loc[finite, "p_adjusted"], expected)
        self.assertTrue(result.loc[~finite, "p_adjusted"].isna().all())
        self.assertEqual(result.attrs["adjustment_family_size"], 3)

    def test_repeat_subjects_rejected(self):
        repeated = self.data.copy()
        repeated.loc[1, "patient"] = repeated.loc[0, "patient"]
        with self.assertRaisesRegex(ValueError, "Repeated subject IDs"):
            compare_groups(repeated, "group", ["age"], [], subject_col="patient")

    def test_missing_subject_rejected(self):
        missing = self.data.copy()
        missing.loc[0, "patient"] = np.nan
        with self.assertRaisesRegex(ValueError, "contains missing"):
            compare_groups(missing, "group", ["age"], [], subject_col="patient")

    def test_bad_numeric_and_infinite_values_rejected(self):
        for value in ["unknown", "", np.inf, -np.inf, 1 + 2j]:
            with self.subTest(value=value):
                data = self.data.copy()
                data["age"] = data.age.astype(object)
                data.loc[0, "age"] = value
                with self.assertRaises(ValueError):
                    compare_groups(data, "group", ["age"], [])

    def test_bad_grouping_and_column_requests_rejected(self):
        with self.assertRaisesRegex(ValueError, "two observed group labels"):
            table_one(self.data, "group", ["age"], [], ["A", "C"])
        with self.assertRaisesRegex(ValueError, "at least one"):
            table_one(self.data, "group", [], [])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            table_one(self.data, "group", ["age", "age"], [])
        duplicated = pd.concat([self.data, self.data[["age"]]], axis=1)
        with self.assertRaisesRegex(ValueError, "duplicate column"):
            table_one(duplicated, "group", ["age"], [])
        missing_group = self.data.copy()
        missing_group.loc[0, "group"] = None
        with self.assertRaisesRegex(ValueError, "contains missing"):
            table_one(missing_group, "group", ["age"], [])

    def test_all_missing_variable_is_explicit(self):
        data = self.data.assign(missing=np.nan)
        result = compare_groups(data, "group", ["missing"], [])
        self.assertTrue(np.isnan(result.iloc[0].p_value))
        self.assertEqual(result.iloc[0].n1, 0)
        table = table_one(data, "group", [], ["missing"])
        self.assertIn("(all missing)", table.level.to_list())
        self.assertEqual(table.iloc[1].overall, "0/0 (NA)")

    def test_input_is_not_mutated_and_no_adjustment_supported(self):
        before = self.data.copy(deep=True)
        result = compare_groups(self.data, "group", ["age"], ["sex"], adjust_method="none")
        pd.testing.assert_frame_equal(self.data, before)
        np.testing.assert_allclose(result.p_value, result.p_adjusted)


if __name__ == "__main__":
    unittest.main()
