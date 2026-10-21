# Statistical methods and interpretation

This document describes the implemented v0.1.0 behavior. It is an analysis specification for this software, not a recommendation that every clinical study should use these methods. The source modules and returned metadata are authoritative for an individual run.

## Data structure and validation

Table 1 and group comparisons require exactly two observed groups. `group_order=[reference, comparison]` fixes direction; the Python API otherwise uses first appearance. Explicit order is recommended for reproducible interpretation. Missing group labels, duplicate column names, invalid numeric values, and infinite measurements are rejected. Numeric strings are parsed strictly; arbitrary text is not silently changed into missingness.

The CLI requires `subject_id`. It identifies the person or independent subject, not the observation. Bilateral knees need a shared patient identifier and can have separate knee identifiers. The package cannot infer independence from a unique ID alone: a user must supply the correct experimental unit.

The Python API exposes `subject_col` in comparisons, regression, and ICC. Omitting it disables duplicate-subject checks and leaves the independence assumption to the caller.

CSV records must contain the same number of fields as the header; extra or missing fields are rejected before pandas can infer an unintended index. XLSX uses the first worksheet. Excel error cells and formulas without cached results cause an error; recalculate and save the workbook or export verified values. Empty cells and the exact strings `NA` and `NaN` are treated as missing by the file reader.

## Descriptive table

`table_one` returns two continuous-variable rows: mean (sample standard deviation, denominator n−1) and median [25th, 75th percentiles]. Quartiles use NumPy's default linear interpolation. Each cell includes its nonmissing n. Categorical summaries use `count / nonmissing observations (percentage)` within the relevant group. Missing counts are reported separately.

The first row reports observation counts. A 176-knee dataset from 160 patients has 176 observations, not 176 patients. Repeated observations are allowed for description, but the summary remains observation-weighted. No p-values are added to Table 1.

## Independent two-group comparisons

`compare_groups` requires independent observations. If a supplied subject ID repeats anywhere in the input, it raises an error rather than treating those observations as independent. Missing values are removed separately for each variable; the returned n1 and n2 are variable-specific. All implemented tests are two-sided.

### Welch mean comparison

With `continuous_test="welch"`, SciPy's `ttest_ind(..., equal_var=False)` calculates a two-sided Welch t test. The estimate is

\[
\Delta = \overline{x}_{2}-\overline{x}_{1},
\]

with the corresponding unadjusted 95% Welch confidence interval. This method does not assume equal population variances. Each group needs at least two nonmissing observations for inference. If both sample variances are zero, the estimate may be displayed but the test and interval are omitted with a note. No normality pretest switches between methods. [SciPy reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html)

### Mann–Whitney comparison

With `continuous_test="mannwhitney"`, the software uses the tie-corrected asymptotic Mann–Whitney U procedure with continuity correction. The effect is rank-biserial correlation,

\[
r_{rb}=\frac{2U_2}{n_1n_2}-1,
\]

or the empirical probability of group 2 exceeding group 1 minus the probability of group 2 being smaller. Ties contribute neither direction. No confidence interval for this effect is implemented. This is a distributional comparison; interpreting it as a test of equal medians requires additional assumptions. The output notes when a small group makes the approximation questionable. Exact and permutation alternatives are outside this release. [SciPy reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html)

### Categorical variables

Binary variables use a two-sided Fisher exact p-value. The reported effect is the **conditional** maximum-likelihood odds ratio, with an exact conditional 95% interval, from `scipy.stats.contingency.odds_ratio(kind="conditional")`. It is not necessarily identical to the sample cross-product odds ratio returned as the statistic of `fisher_exact`.

Categories use natural sorting where possible, with deterministic type/name sorting for mixed labels. The second category is the event. The odds ratio compares event odds in group 2 with those in group 1. Read the event and reference labels in `notes`; for a clinically meaningful event definition, encode categories deliberately. Zero cells can yield zero or infinite odds-ratio estimates or interval bounds; these are mathematically possible and are not repaired by adding a pseudocount.

For 2×K tables with K > 2, Pearson's chi-square test is used without continuity correction only if **all** expected cell counts are at least 5. Otherwise the p-value is omitted with an explanation. This conservative implementation rule is not a claim that 5 is a universal validity boundary. A prespecified exact or permutation analysis is needed for sparse larger tables and is not implemented here.

References: [Fisher exact test](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html), [conditional odds ratio](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.contingency.odds_ratio.html).

### Multiplicity

All finite group-comparison p-values returned by one call form one adjustment family. `fdr_bh` uses Benjamini–Hochberg and assumes independence or appropriate positive dependence. `fdr_by` uses Benjamini–Yekutieli and permits arbitrary dependence. `none` explicitly disables adjustment. The family size and method are recorded; omitted tests remain missing. These adjustments do not include regression coefficients or ICC results, and they do not adjust confidence intervals. The researcher must define the scientific hypothesis family before inspecting results. [SciPy reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.false_discovery_control.html)

## Linear regression

`fit_linear` fits an ordinary least-squares model for a continuous outcome, with an intercept and explicitly listed predictors. Categorical predictors use dummy variables, with the first level under deterministic string/type ordering as reference. References and model terms are saved. Formula text is not executed. There is no stepwise selection, outcome screening, or automatic transformation.

Rows missing any outcome or predictor are removed together. The metadata records input, used and dropped counts and missingness by variable. Subject IDs must be present on otherwise complete rows. Constant outcomes, constant predictors, rank-deficient designs, inadequate residual sample size, effectively zero residual variation, and degenerate uncertainty estimates are rejected. The minimum sample-size check is a computational guard, not a study-design or power criterion.

### Independent rows

If retained subject IDs are unique, OLS coefficients use HC3 heteroscedasticity-robust standard errors and Student t inference with residual degrees of freedom. HC3 addresses heteroscedasticity in the covariance estimate; the mean model still needs appropriate specification.

### Repeated rows within patients

If retained subject IDs repeat, the model uses one-way patient-clustered standard errors with the statsmodels finite-sample covariance correction and Student t inference based on G−1 degrees of freedom, where G is the number of observed patient clusters. Fewer than three clusters causes an error; fewer than 30 produces a caution note. Neither threshold guarantees reliable inference. Clusters should be independent of one another.

The fitted coefficients remain ordinary least-squares coefficients, and each row retains equal weight. A person contributing two knees has twice the row weight of a person contributing one knee. Cluster correction does not fit a random effect, fix confounding, or change that weighting. Clinical interpretation still requires assessment of linearity, residuals, influential observations, and the study's adjustment strategy. The package does not automate those scientific judgments.

The returned coefficient intervals are 95% intervals and p-values are unadjusted. Metadata include covariance type, cluster count, inference degrees of freedom, complete-case counts, reference levels, R², and method notes. See the [statsmodels covariance API](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.RegressionResults.get_robustcov_results.html).

## Measurement reliability

`icc_absolute` expects a wide matrix: each row is one **independent target**, and each rater column measures that same target. Every retained row must have all rater measurements. At least two raters and three complete targets are required. These lower bounds make a calculation possible; they do not establish adequate precision.

The absolute-agreement point estimators use two-way ANOVA mean squares. Let n be the target count, k the rater count, MSs the target mean square, MSr the rater mean square, and MSe the residual mean square:

\[
ICC(A,1)=\frac{MS_s-MS_e}{MS_s+(k-1)MS_e+\frac{k}{n}(MS_r-MS_e)},
\]

\[
ICC(A,k)=\frac{MS_s-MS_e}{MS_s+\frac{1}{n}(MS_r-MS_e)}.
\]

These point formulas correspond to ICC(2,1) and ICC(2,k) under the two-way random-raters absolute-agreement model. Whether raters are sampled from a larger population or are a specific fixed set must come from the study design. The software label does not make that choice for the researcher. A systematic difference between raters can reduce absolute agreement even if their correlation is high.

- **ICC(A,1):** reliability of one rater's single measurement under the specified model.
- **ICC(A,k):** reliability of the average of the k rater measurements.

The k in the second result is the number of supplied rater columns, not the patient count. Negative estimates are retained. Nonpositive estimated variance denominators are treated as undefined. Perfect agreement among varying target values is allowed; data with no identifiable variance are rejected.

### What the bootstrap interval represents

The program resamples complete target rows with replacement and keeps each row's rater measurements together. It uses a fixed seed by default, 2,000 draws, and the 2.5th/97.5th percentiles of valid replicates. The metadata records requested, retained, and undefined replicate counts. An analysis fails if too many replicates are undefined; discarding a small number is reported and can still distort intervals near degenerate cases.

**The interval quantifies target-sampling uncertainty conditional on the observed raters.** Raters are not resampled. It is not an analytic F-based interval for generalization to a population of random raters, and it must not be reported as one. These bootstrap intervals can be unstable in small samples. This is a deliberate limitation of the initial implementation.

Two knees from the same person are correlated targets. Assigning distinct knee IDs only prevents duplicate-key detection; it does not satisfy row independence. For this release, use a prespecified independent target sample, such as a clearly justified one-target-per-person design, or a separately implemented method that accounts for the clustering. The demo's ICC data use one observation per patient.

Example optional configuration, for an appropriate independent target dataset:

```json
"icc": {
  "raters": ["alpha_rater1", "alpha_rater2"],
  "subject_id": "patient_id",
  "n_boot": 2000,
  "seed": 20261022
}
```

Python usage:

```python
reliability = icc_absolute(
    independent_measurements,
    raters=["alpha_rater1", "alpha_rater2"],
    subject_col="patient_id", n_boot=2000, seed=20261022
)
```

State the measurement design, ICC model, agreement definition, single/average measurement type, and interval method in a manuscript. The software does not apply a universal pass/fail ICC threshold.

Method sources: Shrout and Fleiss, *Intraclass correlations: Uses in assessing rater reliability*, [doi:10.1037/0033-2909.86.2.420](https://doi.org/10.1037/0033-2909.86.2.420); McGraw and Wong, *Forming inferences about some intraclass correlation coefficients*, [doi:10.1037/1082-989X.1.1.30](https://doi.org/10.1037/1082-989X.1.1.30). For selecting and reporting the model, see [Koo and Li (2016)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4913118/). The conditional bootstrap described above is the implementation's own interval choice, not a claim that those papers prescribe it.

## Reproducibility and unsupported analyses

Keep the original data, analysis JSON, outputs, software version, and dependency versions together in the study's controlled workspace. Preserve any prespecified exclusions and transformations outside the tool. An audit record documents a computation; it does not prove that the research design was valid or that inputs were correct.

The initial release does not implement imputation, paired tests, longitudinal mixed models, logistic regression, survival analysis, causal inference, automated model diagnosis, automatic covariate selection, or AI interpretation. It does not alter data to obtain significance. Planned features are listed separately in [roadmap.md](roadmap.md).
