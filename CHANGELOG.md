# Changelog

## 0.1.0 — Initial alpha

### Added

- Two-group descriptive tables with nonmissing denominators and missing counts.
- Welch and asymptotic Mann–Whitney comparisons with explicit effect direction.
- Binary Fisher exact tests and conditional odds ratios, plus a sparse-table guard for larger categorical comparisons.
- Benjamini–Hochberg and Benjamini–Yekutieli adjustment options.
- Complete-case OLS with HC3 or patient-clustered covariance and recorded inference choices.
- ICC(A,1) and ICC(A,k) with reproducible subject-row percentile bootstrap intervals conditional on the observed raters.
- CLI configuration, synthetic demos, HTML reports, CSV exports, coefficient plots, and audit metadata.
- Numerical reference and edge-case tests, English/Chinese documentation, and MIT license.

### Scope

The initial release has no model/API integration. ICC intervals do not resample raters. Paired tests, logistic regression, survival analysis, mixed models, imputation, and automatic model selection are not implemented. This release does not assert clinical validation or established adoption.
