# Validation record for v0.1.0

Initial release checks were run on 2026-10-22 (Asia/Shanghai date), using Python 3.12.14 on Linux.

## Completed checks

- **44 automated tests passed** with `python -m unittest discover -s tests -v`.
- Welch estimates and intervals, Fisher conditional odds-ratio orientation, dense contingency tables, and FDR results were compared with upstream SciPy implementations.
- HC3 and cluster-robust estimates and standard errors were compared with separately constructed statsmodels fits. Cluster inference degrees of freedom were checked against the retained patient count minus one.
- ICC points were checked against a hand-calculated example: ICC(A,1) = 16/19 and ICC(A,2) = 32/35. Tests also cover perfect agreement, negative estimates, systematic rater shifts, missing ratings, and reproducible bootstrap intervals.
- End-to-end runs were completed for both the independent and bilateral synthetic cohorts. Input hashes, sample counts, covariance selection, report escaping, and output-file handling were verified.
- Regression tests cover malformed CSV field counts, duplicated headers, Excel error cells, uncached formulas, invalid numeric text, repeated patient IDs, rank-deficient designs, and numerical rank loss from extreme units.
- Local editable installation, source distribution, and wheel builds were checked. The repository includes a GitHub Actions workflow for Python 3.10 and 3.12; its current remote status is shown by GitHub.

## Direct dependency versions used

| Package | Tested version |
| --- | --- |
| NumPy | 2.3.5 |
| pandas | 2.2.3 |
| SciPy | 1.17.0 |
| statsmodels | 0.14.6 |
| matplotlib | 3.10.8 |
| openpyxl (Excel extra) | 3.1.5 |

Each generated `audit.json` records the statistical and plotting dependency versions for that run. These tests establish behavior on the checked cases; they are not independent clinical validation or a guarantee for arbitrary study designs.

The initial release was developed with AI assistance. A separate review pass found and corrected CSV column shifts, Excel error-to-missing conversion, and numerical regression rank loss before publication. Reproducible external numerical reviews are welcome.
