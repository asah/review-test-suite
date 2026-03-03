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


def _check_claude_available() -> str | None:
    """Return None if claude CLI is usable, or a skip reason string."""
    try:
        result = subprocess.run(
            ["claude", "-p", "--allowedTools", "Bash(echo test)"],
            input="Reply with exactly: HEALTH_OK",
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            stdout = result.stdout.strip()
            if "Credit balance" in stdout:
                return "Anthropic API credit balance too low"
            if "Not logged in" in stdout or "login" in stdout.lower():
                return "Claude CLI not logged in"
            return f"Claude CLI not usable: {stdout}"
        return None
    except FileNotFoundError:
        return "Claude CLI not installed"
    except subprocess.TimeoutExpired:
        return "Claude CLI health check timed out"


# Cache the check result for the session
_claude_skip_reason: str | None | bool = False  # False = not checked yet


def get_claude_skip_reason() -> str | None:
    """Check once per session whether claude CLI is available."""
    global _claude_skip_reason
    if _claude_skip_reason is False:
        _claude_skip_reason = _check_claude_available()
    return _claude_skip_reason


def run_claude_prompt(prompt: str, repo_dir: Path, timeout: int = 120) -> str:
    """Invoke claude -p with a custom prompt. Skips if CLI not available."""
    skip_reason = get_claude_skip_reason()
    if skip_reason:
        pytest.skip(skip_reason)

    env = {**os.environ}
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
