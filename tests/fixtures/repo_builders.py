"""Functions that build test git repos for integration scenarios.

Each function takes a repo_dir (Path to an already-initialized git repo)
and populates it with commits and optionally uncommitted changes.
Returns a metadata dict so tests can assert against it.
"""

import subprocess
import textwrap
from pathlib import Path


def _run(cmd: str, cwd: Path) -> str:
    result = subprocess.run(
        cmd, shell=True, cwd=cwd,
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _commit(cwd: Path, msg: str) -> str:
    _run("git add -A", cwd)
    _run(f'git commit -m "{msg}"', cwd)
    return _run("git rev-parse --short HEAD", cwd)


# ─── Scenario 1: No prior review — should recommend running ───────────

def build_no_prior_review(repo_dir: Path) -> dict:
    """Create a repo with SQL test files but no [test-suite-review] marker.
    The skill should detect NO PRIOR REVIEW and recommend running."""

    sql_dir = repo_dir / "sql"
    sql_dir.mkdir()
    expected_dir = repo_dir / "expected"
    expected_dir.mkdir()

    # Create initial SQL test files
    (sql_dir / "smol_core.sql").write_text(textwrap.dedent("""\
        -- Core access method tests
        CREATE EXTENSION IF NOT EXISTS smol;
        CREATE TABLE test_core (id int, val text) USING smol;
        INSERT INTO test_core SELECT g, 'row_' || g FROM generate_series(1, 100) g;
        EXPLAIN (COSTS OFF) SELECT * FROM test_core WHERE id = 42;
        SELECT * FROM test_core WHERE id = 42;
    """))

    (sql_dir / "smol_coverage_basic.sql").write_text(textwrap.dedent("""\
        -- Coverage tests: basic operations
        CREATE EXTENSION IF NOT EXISTS smol;
        CREATE TABLE test_cov (a int, b text) USING smol;
        INSERT INTO test_cov VALUES (1, 'hello'), (2, 'world');
        SELECT count(*) FROM test_cov;
    """))

    (expected_dir / "smol_core.out").write_text("id | val\\n42 | row_42\\n")
    (expected_dir / "smol_coverage_basic.out").write_text("count\\n2\\n")

    # Create a parallel schedule file
    (repo_dir / "parallel_schedule_base").write_text(
        "smol_core\\nsmol_coverage_basic\\n"
    )

    _commit(repo_dir, "Initial: add core and coverage SQL tests")

    # Add more commits to make it realistic
    for i in range(3):
        (sql_dir / f"smol_agg_{i}.sql").write_text(
            f"-- Aggregate test {i}\\nSELECT sum(id) FROM test_core;\\n"
        )
        _commit(repo_dir, f"Add aggregate test {i}")

    return {
        "expected_trigger": "NO PRIOR REVIEW",
        "has_sql_files": True,
        "has_expected_files": True,
    }


# ─── Scenario 2: Threshold met — many changes since last review ───────

def build_threshold_met(repo_dir: Path) -> dict:
    """Create a repo with a past [test-suite-review] marker and 20+ commits
    since, touching sql/*.sql files. Should recommend running."""

    sql_dir = repo_dir / "sql"
    sql_dir.mkdir()

    (sql_dir / "smol_core.sql").write_text("SELECT 1;\\n")
    review_hash = _commit(repo_dir, "Initial tests [test-suite-review]")

    # Make 25 commits touching SQL files
    for i in range(25):
        (sql_dir / f"smol_test_{i}.sql").write_text(
            f"-- Test {i}\\nSELECT {i};\\n"
        )
        _commit(repo_dir, f"Add test {i}")

    return {
        "expected_trigger": "THRESHOLD MET",
        "review_commit": review_hash,
        "commits_since": 25,
    }


# ─── Scenario 3: Below threshold — few changes since review ───────────

def build_below_threshold(repo_dir: Path) -> dict:
    """Create a repo with a recent [test-suite-review] marker and only
    a few commits since. Should report below threshold."""

    sql_dir = repo_dir / "sql"
    sql_dir.mkdir()

    (sql_dir / "smol_core.sql").write_text("SELECT 1;\\n")
    _commit(repo_dir, "Initial tests")

    # Add review marker
    (sql_dir / "smol_review.sql").write_text("SELECT 'reviewed';\\n")
    review_hash = _commit(repo_dir, "Post-review cleanup [test-suite-review]")

    # Only 3 commits since review
    for i in range(3):
        (sql_dir / f"smol_minor_{i}.sql").write_text(
            f"-- Minor fix {i}\\nSELECT {i};\\n"
        )
        _commit(repo_dir, f"Minor fix {i}")

    return {
        "expected_trigger": "below threshold",
        "review_commit": review_hash,
        "commits_since": 3,
    }


# ─── Scenario 4: Quality issues repo for full review ──────────────────

def build_quality_issues_repo(repo_dir: Path) -> dict:
    """Create a repo with SQL test files containing known quality
    anti-patterns that the review should flag."""

    sql_dir = repo_dir / "sql"
    sql_dir.mkdir()
    expected_dir = repo_dir / "expected"
    expected_dir.mkdir()
    docs_dir = repo_dir / "docs" / "test_review"
    docs_dir.mkdir(parents=True)

    # File with missing EXPLAIN — bad: doesn't verify index usage
    (sql_dir / "smol_coverage_missing_explain.sql").write_text(textwrap.dedent("""\
        -- Coverage test: missing EXPLAIN
        CREATE EXTENSION IF NOT EXISTS smol;
        CREATE TABLE test_no_explain (id int, val text) USING smol;
        INSERT INTO test_no_explain SELECT g, 'val' || g FROM generate_series(1, 100) g;
        -- BUG: no EXPLAIN — cannot verify acceleration is actually used
        SELECT * FROM test_no_explain WHERE id = 50;
        SELECT count(*) FROM test_no_explain;
    """))

    # File with exception swallowing — bad: hides real failures
    (sql_dir / "smol_coverage_error_swallow.sql").write_text(textwrap.dedent("""\
        -- Coverage test: exception swallowing
        CREATE EXTENSION IF NOT EXISTS smol;
        DO $$
        BEGIN
            -- This swallows ALL errors including real bugs
            BEGIN
                PERFORM 1/0;
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'caught error (expected)';
            END;
        END $$;
    """))

    # File with oversized dataset — bad: 100K rows when 100 suffices
    (sql_dir / "smol_agg_oversized.sql").write_text(textwrap.dedent("""\
        -- Aggregate test: oversized dataset
        CREATE EXTENSION IF NOT EXISTS smol;
        CREATE TABLE test_big (id int, val float) USING smol;
        -- BAD: 100000 rows when the test only needs multi-level tree
        INSERT INTO test_big SELECT g, random() FROM generate_series(1, 100000) g;
        SELECT sum(val), avg(val) FROM test_big;
    """))

    # File referencing removed bloom filter feature — dead code
    (sql_dir / "smol_coverage_bloom.sql").write_text(textwrap.dedent("""\
        -- Coverage test: references removed bloom filter feature
        CREATE EXTENSION IF NOT EXISTS smol;
        SET smol.bloom_enabled = true;
        SET smol.bloom_nhash = 3;
        CREATE TABLE test_bloom (id int) USING smol;
        INSERT INTO test_bloom SELECT g FROM generate_series(1, 100) g;
        SELECT * FROM test_bloom WHERE id = 42;
    """))

    # Good test for comparison
    (sql_dir / "smol_scan.sql").write_text(textwrap.dedent("""\
        -- Scan test: properly structured
        CREATE EXTENSION IF NOT EXISTS smol;
        SET search_path = test_scan, public;
        CREATE SCHEMA IF NOT EXISTS test_scan;
        CREATE TABLE test_scan.t (id int, val text) USING smol;
        INSERT INTO test_scan.t SELECT g, 'row_' || g FROM generate_series(1, 100) g;
        EXPLAIN (COSTS OFF) SELECT * FROM test_scan.t WHERE id = 42;
        SELECT * FROM test_scan.t WHERE id = 42;
        DROP SCHEMA test_scan CASCADE;
    """))

    # Create expected output files
    (expected_dir / "smol_coverage_missing_explain.out").write_text(
        "id | val\\n50 | val50\\n"
    )
    (expected_dir / "smol_scan.out").write_text(
        "QUERY PLAN\\nIndex Scan\\nid | val\\n42 | row_42\\n"
    )

    # Large expected output (bloat indicator)
    (expected_dir / "smol_agg_oversized.out").write_text("x\\n" * 5000)

    (repo_dir / "parallel_schedule_base").write_text(
        "smol_coverage_missing_explain\\n"
        "smol_coverage_error_swallow\\n"
        "smol_agg_oversized\\n"
        "smol_coverage_bloom\\n"
        "smol_scan\\n"
    )

    _commit(repo_dir, "Initial: test files with known quality issues")

    return {
        "issues": {
            "missing_explain": "smol_coverage_missing_explain.sql",
            "exception_swallowing": "smol_coverage_error_swallow.sql",
            "dataset_oversizing": "smol_agg_oversized.sql",
            "dead_code_bloom": "smol_coverage_bloom.sql",
        },
        "good_test": "smol_scan.sql",
    }
