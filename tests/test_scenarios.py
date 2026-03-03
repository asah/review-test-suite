"""Integration tests that invoke the skill via `claude -p`.

Marked with @pytest.mark.integration -- these are SLOW (~30-90s each).

Run explicitly:     pytest -m integration
Skip in fast CI:    pytest -m "not integration"

These tests use focused prompts (not the full 7-agent SKILL.md) to keep
runtime under 2 minutes per test.
"""

import pytest

from tests.conftest import run_claude_prompt
from tests.fixtures.repo_builders import build_quality_issues_repo

pytestmark = pytest.mark.integration

# Focused prompt that reviews a handful of SQL files for quality issues.
# Much faster than the full 7-agent dispatch from SKILL.md.
QUALITY_REVIEW_PROMPT = """\
You are reviewing SQL test files for a columnar storage engine called "smol".
Read the SQL files in the sql/ directory and check for these quality issues:

1. **Missing EXPLAIN**: Tests that don't use EXPLAIN to verify the smol
   access method is actually being used. Without EXPLAIN, the test passes
   whether or not acceleration works.
2. **Exception swallowing**: Use of `EXCEPTION WHEN OTHERS` that hides
   real failures.
3. **Dataset oversizing**: Tables with 100K+ rows when a few hundred
   would suffice. Use `smol.test_max_internal_fanout=4` for multi-level
   tree tests instead.
4. **Dead code / removed features**: References to bloom filter GUCs
   (`bloom_enabled`, `bloom_filters`, `bloom_nhash`) which were removed.

For each issue found, report:
- The file name
- The specific problem
- A one-line fix suggestion

End with a summary count of issues by category.
"""


def assert_mentions(output: str, keyword: str, label: str = "keyword"):
    """Assert keyword appears in output (case-insensitive)."""
    assert keyword.lower() in output.lower(), (
        f"Expected {label} '{keyword}' not found in output.\n"
        f"Output (first 500 chars): {output[:500]}"
    )


class TestQualityIssueDetection:
    """Run a focused quality review prompt against a repo with known
    anti-patterns. Single LLM call, checks multiple assertions."""

    def test_detects_quality_issues(self, make_test_repo):
        repo = make_test_repo("quality_issues")
        build_quality_issues_repo(repo)
        output = run_claude_prompt(QUALITY_REVIEW_PROMPT, repo, timeout=180)

        # Should flag bloom filter references (dead code)
        assert_mentions(output, "bloom", "dead code detection")
        # Should mention EXPLAIN coverage gaps
        assert_mentions(output, "EXPLAIN", "missing EXPLAIN coverage")
        # Should flag exception-swallowing patterns
        assert_mentions(output, "exception", "exception swallowing")
