---
name: review-test-suite
description: Periodically groom the SMOL test suite for quality, correctness, and efficiency. Auto-suggests when enough SQL/C changes have accumulated since the last review.
version: 1.0.0
tools: Read, Glob, Grep, Bash, Task
---

# SMOL Test Suite Review

## When to run

**Auto-check at session start** (or run manually with `/project:review-test-suite`):

```bash
# Find last review in git log (liberal match — marker may appear anywhere in msg)
LAST=$(git log --oneline --all | grep -i "\[test-suite-review\]" | head -1 | awk '{print $1}')

if [ -z "$LAST" ]; then
  echo "NO PRIOR REVIEW — recommend running"
else
  # Count commits touching test-sensitive files since last review
  CHANGES=$(git log ${LAST}..HEAD --oneline -- 'sql/*.sql' 'smol*.c' 'smol*.h' 'expected/*.out' | wc -l | tr -d ' ')
  echo "Commits since last review: $CHANGES"
  [ "$CHANGES" -ge 20 ] && echo "THRESHOLD MET — recommend running" || echo "below threshold ($CHANGES/20)"
fi
```

Run the review if output says **RECOMMEND RUNNING**. Otherwise skip.

When the review completes, include `[test-suite-review]` anywhere in the merge/commit message so future threshold checks can find it.

---

## The Review

### Pre-work (serial, ~2 min)

```bash
wc -l sql/smol_*.sql | sort -rn | head -15
grep -c "EXPLAIN" sql/smol_*.sql | sort -rn | head -10
grep -rn "bloom_enabled\|bloom_filters\|bloom_nhash\|build_bloom_filters" sql/smol_*.sql
wc -l expected/smol_*.out | sort -rn | head -10
sort parallel_schedule_base | uniq -d   # duplicate schedule entries
```

Also check `docs/test_review/FINAL_REPORT.md` for known open issues to carry forward.

### Dispatch 7 parallel agents

Each writes `docs/test_review/<N>_<topic>.md`. Full question lists in `docs/test_review/REUSABLE_PROMPT.md`.

| # | Agent | Files |
|---|-------|-------|
| 1 | Coverage tests | `sql/smol_coverage*.sql` |
| 2 | Aggregate acceleration | `sql/smol_agg*.sql`, `smol_bool*.sql`, `smol_float*.sql`, `smol_parallel_agg.sql` |
| 3 | Core AM | `sql/smol_rle*.sql`, `smol_scan.sql`, `smol_core.sql`, `smol_types.sql`, `smol_simd.sql`, `smol_text*.sql` |
| 4 | Acceleration patterns | `sql/smol_2col*.sql`, `smol_3col*.sql`, `smol_agg_composite.sql`, `smol_sublink*.sql`, `smol_minmax_where.sql` |
| 5 | Edge cases | `sql/smol_null*.sql`, `smol_zone_maps.sql`, `smol_backward*.sql`, `smol_inet.sql`, `smol_coverage_error_conditions.sql` |
| 6 | Write/MVCC/Delta | `sql/smol_delta*.sql`, `smol_writes.sql`, `smol_update_visibility.sql`, `smol_vacuum_scenarios.sql`, `specs/*.spec` |
| 7 | Meta/Debug/DBA | `sql/smol_todo*.sql`, `smol_debug*.sql`, `smol_verify.sql`, `smol_compare_with_btree.sql`, `smol_bloat_estimate.sql` |

**Each agent answers:**
- Dead code / removed features referenced?
- Tautological tests (same GUC in both branches of a correctness comparison)?
- EXPLAIN coverage (tests that pass whether accelerated or not)?
- Dataset oversizing (use `smol.test_max_internal_fanout=4` for multi-level trees)?
- Exception-swallowing patterns (`EXCEPTION WHEN OTHERS`)?
- Hardcoded values that break on format changes?
- TODO tests frozen at known-wrong answers?

### Synthesis (after all agents report)

Write `docs/test_review/FINAL_REPORT.md` with:
1. Status table (Critical / High / Moderate — Done vs Open)
2. Top open issues with file:line references
3. Performance wins table (file, current rows, needed rows)
4. Coverage gaps (missing scenarios + risk)

Move completed prior reports to `docs/test_review/completed/`.

### Quick invariant checks

```bash
grep -rn "bloom_enabled\|bloom_filters\|bloom_nhash" sql/smol_*.sql   # should be empty
grep -rn "^cho \|^  cho " sql/smol_*.sql                               # broken \echo
sort parallel_schedule_base | uniq -d                                   # duplicate entries
wc -l expected/smol_*.out | sort -rn | head -5                         # raw dump bloat
```

### Quality bar

Good test: asserts index used (EXPLAIN) + correct value returned + minimal dataset + schema isolation.
Bad test: EXPLAIN-only, no EXPLAIN at all, 100K rows when 1K suffices, exception-swallowing, accelerated vs accelerated comparison, feature removed.
