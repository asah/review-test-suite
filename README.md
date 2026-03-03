# review-test-suite

Automatically detect when it's time for a swarm of agents to review and optimize a test suite.

## What it does

A Claude Code skill that periodically grooms the SMOL test suite for quality, correctness, and efficiency. It auto-suggests when enough SQL/C changes have accumulated since the last review.

### Trigger detection

Checks git history for a `[test-suite-review]` marker and counts commits touching test-sensitive files (`sql/*.sql`, `smol*.c`, `smol*.h`, `expected/*.out`). Recommends a review after 20+ qualifying commits.

### Parallel review

Dispatches 7 specialized agents to review different areas of the test suite:

1. **Coverage tests** — `sql/smol_coverage*.sql`
2. **Aggregate acceleration** — `sql/smol_agg*.sql`, `smol_bool*.sql`, `smol_float*.sql`
3. **Core AM** — `sql/smol_rle*.sql`, `smol_scan.sql`, `smol_core.sql`, `smol_types.sql`
4. **Acceleration patterns** — `sql/smol_2col*.sql`, `smol_3col*.sql`, multi-column composites
5. **Edge cases** — `sql/smol_null*.sql`, `smol_zone_maps.sql`, backward scans, inet
6. **Write/MVCC/Delta** — `sql/smol_delta*.sql`, `smol_writes.sql`, vacuum, isolation specs
7. **Meta/Debug/DBA** — `sql/smol_todo*.sql`, `smol_debug*.sql`, verify, btree comparison

Each agent checks for: dead code, tautological tests, missing EXPLAIN coverage, dataset oversizing, exception-swallowing, hardcoded values, and frozen TODO tests.

### Synthesis

Produces a `docs/test_review/FINAL_REPORT.md` with status tables, open issues, performance wins, and coverage gaps.

## Installation

Add to your Claude Code project skills:

```bash
claude mcp add --transport sse review-test-suite https://github.com/asah/review-test-suite
```

Or clone and reference locally in your `.claude/settings.json`.

## Development

```bash
# Install test dependencies
pip install -e ".[test]"

# Run schema/lint tests (fast, no LLM)
pytest tests/test_schema.py -v

# Run integration tests (requires claude CLI + ANTHROPIC_API_KEY)
pytest tests/test_scenarios.py -v --timeout=120
```

## License

MIT
