# Roadmap

This document separates implemented behavior from proposals. Items below are not promises of availability or release dates. Priorities should be driven by reproducible user examples, statistical review, and maintenance capacity.

## v0.1.0: initial scope

- Two-group descriptive tables with explicit nonmissing denominators.
- Prespecified independent-group comparisons and optional FDR adjustment.
- Continuous-outcome OLS with HC3 or patient-clustered uncertainty.
- Absolute-agreement single/average ICC estimates and conditional target-row bootstrap intervals.
- Synthetic clinical examples, local reports, configuration records, and numerical/edge-case tests.
- English and Chinese usage documentation.

## Near-term proposals

1. Add independent reference fixtures for more statistical edge cases, with documented source calculations and dependency-version checks.
2. Improve clarity of missingness and analysis-unit reporting, informed by reproducible user feedback.
3. Evaluate analytic ICC confidence intervals and clustering-aware reliability methods. Each added interval must state which targets and raters it generalizes to.
4. Add optional residual and influence plots without turning diagnostics into automatic model selection.
5. Evaluate paired analyses and logistic regression as separate modules with distinct input contracts and tests.

## Possible AI-assisted maintenance

Codex-assisted issue triage, code review, synthetic test generation, documentation updates, and release checks may help maintain this project. These workflows should use reviewable changes and retain human responsibility for statistical choices. Their existence must not be implied by the current CLI.

An optional bilingual explanation feature is also being considered. A proposed design would accept approved aggregate statistics and public method documentation, keep numerical estimation in deterministic local code, label generated narrative, and require review of the explanation. An evaluation would check numerical fidelity, preservation of uncertainty, missingness statements, and unsupported causal claims.

**v0.1.0 contains no OpenAI API integration, no autonomous interpretation layer, and no API key requirement.** There is no commitment that this proposed feature will ship. A working statistical toolkit is the current deliverable.

## Evidence before broader claims

Software tests, a synthetic demo, external statistical review, real-world usability feedback, and clinical validation are different forms of evidence. Report each only when it has actually occurred. Track real releases, issues, and adoption through the public repository; do not substitute estimated users or generated activity for observed use.
