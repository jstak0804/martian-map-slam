# Refactoring review — 2026-11-15

## Scope and result

Applied the requested ECC code-reviewer, build-error-resolver, security-review, refactor-cleaner and continuous-learning-v2 guidance, plus the existing TDD workflow. This was a scoped self-review, not an independent agent audit.

- Consolidated 28 ordered source fragments into 17 modules. Renamed the UI controller to `map_ui.js`, named rotation integration `map_orientation.js`, colocated geographic/context declarations with consumers, and removed empty bridge files.
- Verified concatenated JavaScript equality before deleting the fragments. Generated demo HTML is byte-equivalent after newline normalization to pre-refactor commit `844d52f`; no visual or calculation change is intended.
- Separated manifest loading, compressed-asset reading, rendering and output writing in the builder. Removed duplicate asset decoding and duplicate output-writing logic.
- Added rejection of malformed/duplicate module names, paths outside the source directory, missing/repeated script slots and unresolved placeholders. Inline JSON now escapes `<` so JSON strings cannot terminate their script element. Inputs are validated before either demo output is overwritten.

## TDD and build evidence

`test_builder_validation.py`: five failures observed before the fix, then five passes. RED commit `affba28`; GREEN commit `b2655c5`. Cases cover duplicate modules, path traversal, missing script slot, unresolved placeholder, and script-closing JSON strings with value round-trip preservation.

`test_build.py` verifies repeatable builds. Five Node regression scripts pass. The coordinate test now expands the actual committed JSON asset and checks inverse consistency for all three regions. Consolidation exposed a test-loader assumption about that declaration; it was fixed without changing runtime behavior.

Run the new validation with `python tests/map_app/test_builder_validation.py`, followed by the existing commands in PLAN.md. Browser workflow evidence remains under `reports/map-app-validation/`.

## Security review boundary

The application is an offline HTML demo: no account service, database, payment, authentication token or server API is introduced. Those server-oriented checklist items are not applicable. Reviewed dynamic destination labels use `textContent` or `uiEscape`; static icon HTML is not user input. The telemetry file path writes into a textarea and a `textContent` label, not executable HTML.

The builder consumes trusted repository JavaScript and prebuilt text assets; validation does not sandbox arbitrary repository code. Escaping applies to inline JSON placeholders, not an assertion that every imported asset is safe. Existing local telemetry import has no file-size cap and can stall on oversized input. A complete upload/resource-exhaustion audit, CSP retrofit, historical secret scan and whole-repository dependency audit were not performed.

No critical/high finding was identified in the changed code after fixes. Full application coverage remains unmeasured; no 80% coverage claim. Shared closure state still exists and is documented as later maintainability work.

## Continuous learning

Recorded a manual, project-scoped local instinct about preserving assembled code and loading real assets in fragment tests. No conversation logs were exported, no global rule was promoted, and no background observer was enabled. Native Windows background-observer limitations in the skill remain applicable.
