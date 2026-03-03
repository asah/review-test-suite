"""Tests for the trigger detection logic -- no LLM calls, pure bash.

These tests verify the 'When to run' bash script from SKILL.md by
executing it directly against synthetic git repos.
"""

import subprocess
from pathlib import Path

from tests.fixtures.repo_builders import (
    build_below_threshold,
    build_no_prior_review,
    build_threshold_met,
)

TRIGGER_SCRIPT = """\
LAST=$(git log --oneline --all | grep -i "\\[test-suite-review\\]" | head -1 | awk '{print $1}')

if [ -z "$LAST" ]; then
  echo "NO PRIOR REVIEW — recommend running"
else
  CHANGES=$(git log ${LAST}..HEAD --oneline -- 'sql/*.sql' 'smol*.c' 'smol*.h' 'expected/*.out' | wc -l | tr -d ' ')
  echo "Commits since last review: $CHANGES"
  [ "$CHANGES" -ge 20 ] && echo "THRESHOLD MET — recommend running" || echo "below threshold ($CHANGES/20)"
fi
"""


def run_trigger(repo_dir: Path) -> str:
    """Run the trigger detection script in the given repo."""
    result = subprocess.run(
        ["bash", "-c", TRIGGER_SCRIPT],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()


class TestNoPriorReview:
    """No [test-suite-review] marker in git history."""

    def test_detects_no_prior_review(self, make_test_repo):
        repo = make_test_repo("trigger_no_review")
        build_no_prior_review(repo)
        output = run_trigger(repo)
        assert "NO PRIOR REVIEW" in output
        assert "recommend running" in output


class TestThresholdMet:
    """25 commits since last review — above 20 threshold."""

    def test_detects_threshold_met(self, make_test_repo):
        repo = make_test_repo("trigger_threshold_met")
        build_threshold_met(repo)
        output = run_trigger(repo)
        assert "THRESHOLD MET" in output
        assert "recommend running" in output

    def test_counts_commits_correctly(self, make_test_repo):
        repo = make_test_repo("trigger_count")
        build_threshold_met(repo)
        output = run_trigger(repo)
        assert "Commits since last review: 25" in output


class TestBelowThreshold:
    """Only 3 commits since last review — below 20 threshold."""

    def test_reports_below_threshold(self, make_test_repo):
        repo = make_test_repo("trigger_below")
        build_below_threshold(repo)
        output = run_trigger(repo)
        assert "below threshold" in output

    def test_shows_commit_count(self, make_test_repo):
        repo = make_test_repo("trigger_count_below")
        build_below_threshold(repo)
        output = run_trigger(repo)
        assert "Commits since last review: 3" in output
        assert "3/20" in output
