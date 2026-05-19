# TASK-plan-power-fall-ratio-real-subrows Review

## Reviewer result

passed=true

## Blocking issues

None.

## Reviewer notes

- Implementation satisfies the clarified requirement: `落档比例预估` is expanded into actual `el-table` rows, not just line breaks inside one cell.
- `rowspan` behavior is correct: the `落档比例预估` column stays one row per segment; all other columns are merged vertically by the original business row.
- Frontend remains display-only; it does not calculate power, CTM, prediction ratio, or probability values.
- Excel export does not leak display metadata keys because it only iterates visible `table.columns`; it also applies `worksheet['!merges']` for the irregular merged structure.
- No token/secret restoration found. Token strings in tests are negative guard assertions.

## Non-blocking suggestions

- Static tests are acceptable for current project style, but a future component/DOM test or workbook roundtrip test would give stronger confidence for actual row count, rowspan, merges, and metadata exclusion.
- `splitFallRatioEstimateLines` could defensively preserve a row if a malformed value contains only separators; current backend normal output is non-empty, so this is not blocking.
