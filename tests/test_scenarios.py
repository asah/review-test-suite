"""Integration tests that invoke the skill via `claude -p`.

Marked with @pytest.mark.integration -- these are SLOW (~30-90s each).

Run explicitly:     pytest -m integration
Skip in fast CI:    pytest -m "not integration"
"""

import subprocess

import pytest

from tests.conftest import run_skill
from tests.fixtures.repo_builders import (
    build_no_prior_review,
    build_quality_issues_repo,
    build_threshold_met,
)

pytestmark = pytest.mark.integration


def assert_mentions(output: str, keyword: str, label: str = "keyword"):
    """Assert that the keyword appears somewhere in the output (case-insensitive)."""
    assert keyword.lower() in output.lower(), (
        f"Expected {label} '{keyword}' not found in output.\n"
        f"Output (first 500 chars): {output[:500]}"
    )


def assert_mentions_file(output: str, filename: str):
    assert filename in output, (
        f"Expected mention of file '{filename}' in output.\n"
        f"Output (first 500 chars): {output[:500]}"
    )


class TestTriggerDetectsNoPriorReview:
    """Scenario 1: No prior [test-suite-review] marker in history."""

    def test_recommends_running(self, make_test_repo):
        repo = make_test_repo("no_prior_review")
        build_no_prior_review(repo)
        output = run_skill(repo)
        assert_mentions(output, "no prior review", "trigger message")


class TestTriggerDetectsThresholdMet:
    """Scenario 2: 25 commits since last review — above 20 threshold."""

    def test_detects_threshold_met(self, make_test_repo):
        repo = make_test_repo("threshold_met")
        build_threshold_met(repo)
        output = run_skill(repo)
        assert_mentions(output, "threshold", "trigger message")


class TestQualityIssueDetection:
    """Scenario 3: Repo with known quality anti-patterns."""

    def test_detects_quality_issues(self, make_test_repo):
        repo = make_test_repo("quality_issues")
        meta = build_quality_issues_repo(repo)
        output = run_skill(repo, timeout=180)

        # Should flag bloom filter references (dead code)
        assert_mentions(output, "bloom", "dead code detection")

    def test_flags_missing_explain(self, make_test_repo):
        repo = make_test_repo("missing_explain")
        meta = build_quality_issues_repo(repo)
        output = run_skill(repo, timeout=180)

        assert_mentions(output, "EXPLAIN", "missing EXPLAIN coverage")

    def test_flags_exception_swallowing(self, make_test_repo):
        repo = make_test_repo("exception_swallow")
        meta = build_quality_issues_repo(repo)
        output = run_skill(repo, timeout=180)

        assert_mentions(output, "exception", "exception swallowing")
