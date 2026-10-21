# Contributing to MedCohortKit

Contributions are welcome through reproducible issues and pull requests. This is an early-stage project; a clear correction to one statistical or usability problem is more useful than an unreviewable expansion of scope.

## Set up a development environment

From the repository root, using Python 3.10 or later:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On macOS/Linux, use `python3 -m venv .venv` and `.venv/bin/python` in place of the Windows interpreter path. Tests use the Python standard-library `unittest` runner.

## Report a problem

Include the package and dependency versions, exact command or minimal Python call, a small synthetic dataset, configuration, observed result, and expected behavior. For a numerical disagreement, identify the comparison implementation and its options: effect direction, missingness handling, covariance estimator, confidence level, and ICC definition can all change the answer.

Do not post patient-level records, confidential research data, access tokens, or identifying output. Reproduce data-dependent problems with synthetic values that retain the relevant structure, such as repeated patient IDs, ties, missingness, or a zero cell.

## Change a statistical method

- Explain the research design and estimand the method supports.
- Cite the primary method or official library documentation.
- Make assumptions, effect direction, reference categories, and missingness treatment explicit.
- Add an independently established numerical reference or a meaningful property check. Tests that merely repeat the implementation's formula are insufficient on their own.
- Include cases where computation should fail or produce an explicitly omitted result.
- Record changed behavior in `CHANGELOG.md` and update `docs/methods.md`.

Preserve negative ICC estimates and legitimate infinite exact odds-ratio limits where defined. Do not silently coerce invalid numeric values to missingness, switch statistical tests using a normality p-value, remove inconvenient outliers, or treat repeated observations as independent.

## Keep changes reviewable

Use a focused branch and a small pull request describing the problem, changed behavior, and validation. Include only files relevant to the change. Generated reports from real datasets do not belong in the source repository. Update both README languages when usage changes.

AI assistance may be used for code or documentation. Contributors remain responsible for checking the resulting logic, sources, tests, and descriptions. Do not present generated prose as evidence of statistical validation or observed project adoption.

## License

By submitting a contribution, you agree that it may be distributed under the project's MIT license. Ensure any included material can be shared under compatible terms, and retain required attribution for third-party code.
