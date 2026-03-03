"""Shared fixtures for all tests."""

import os
import subprocess
from pathlib import Path

import frontmatter
import pytest

SKILL_MD_PATH = Path(__file__).resolve().parent.parent / "SKILL.md"


# ─── Schema fixtures ───────────────────────────────────────────────────

@pytest.fixture(scope="session")
def skill():
    """Parse SKILL.md once for the entire test session."""
    return frontmatter.load(str(SKILL_MD_PATH))


@pytest.fixture(scope="session")
def skill_metadata(skill):
    """The YAML frontmatter as a dict."""
    return skill.metadata


@pytest.fixture(scope="session")
def skill_body(skill):
    """The markdown body (everything after the closing ---)."""
    return skill.content


# ─── Integration test helpers ──────────────────────────────────────────

@pytest.fixture
def make_test_repo(tmp_path):
    """Factory fixture: creates a git repo in a unique temp directory."""
    counter = [0]

    def _make(name=None):
        counter[0] += 1
        dirname = name or f"repo_{counter[0]}"
        repo_dir = tmp_path / dirname
        repo_dir.mkdir()
        subprocess.run(
            ["git", "init"], cwd=repo_dir, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo_dir, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo_dir, check=True, capture_output=True,
        )
        return repo_dir

    return _make


def build_prompt_from_skill() -> str:
    """Read SKILL.md and return the body as the prompt."""
    skill = frontmatter.load(str(SKILL_MD_PATH))
    return skill.content


def run_skill(repo_dir: Path, timeout: int = 120) -> str:
    """Invoke the skill via `claude -p` in the given repo directory."""
    prompt = build_prompt_from_skill()
    env = {**os.environ}
    # Allow nested claude invocation in CI / dev sessions
    env.pop("CLAUDE_CODE", None)
    env.pop("CLAUDECODE", None)

    result = subprocess.run(
        [
            "claude", "-p",
            "--allowedTools", "Read", "Glob", "Grep",
            "Bash(*)", "Task",
        ],
        input=prompt,
        cwd=repo_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude -p failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result.stdout
