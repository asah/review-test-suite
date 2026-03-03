"""Schema/lint tests for SKILL.md -- no LLM calls, purely structural."""

import re


class TestFrontmatter:
    """Validate the YAML frontmatter block."""

    def test_has_name(self, skill_metadata):
        assert "name" in skill_metadata
        assert isinstance(skill_metadata["name"], str)
        assert len(skill_metadata["name"]) > 0

    def test_name_is_kebab_case(self, skill_metadata):
        name = skill_metadata["name"]
        assert re.match(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", name), (
            f"Skill name '{name}' is not kebab-case"
        )

    def test_has_description(self, skill_metadata):
        assert "description" in skill_metadata
        assert isinstance(skill_metadata["description"], str)
        assert len(skill_metadata["description"]) >= 10

    def test_has_version(self, skill_metadata):
        assert "version" in skill_metadata
        assert re.match(r"^\d+\.\d+\.\d+$", skill_metadata["version"]), (
            f"Version '{skill_metadata['version']}' is not semver"
        )

    def test_has_tools(self, skill_metadata):
        assert "tools" in skill_metadata
        assert isinstance(skill_metadata["tools"], str)
        assert len(skill_metadata["tools"]) > 0


class TestToolsField:
    """Validate the tools declared in frontmatter."""

    def test_includes_bash(self, skill_metadata):
        tools = skill_metadata["tools"]
        assert "Bash" in tools

    def test_includes_read(self, skill_metadata):
        tools = skill_metadata["tools"]
        assert "Read" in tools

    def test_includes_task(self, skill_metadata):
        """Skill dispatches parallel agents, so Task tool is required."""
        tools = skill_metadata["tools"]
        assert "Task" in tools

    def test_includes_grep(self, skill_metadata):
        tools = skill_metadata["tools"]
        assert "Grep" in tools

    def test_includes_glob(self, skill_metadata):
        tools = skill_metadata["tools"]
        assert "Glob" in tools


class TestTriggerSection:
    """Validate the 'When to run' trigger detection section."""

    def test_has_when_to_run(self, skill_body):
        assert "## When to run" in skill_body

    def test_has_trigger_script(self, skill_body):
        assert "git log" in skill_body
        assert "test-suite-review" in skill_body

    def test_has_threshold(self, skill_body):
        assert "20" in skill_body, "Should define the 20-commit threshold"

    def test_has_recommend_running(self, skill_body):
        assert "recommend running" in skill_body.lower()

    def test_has_review_marker(self, skill_body):
        assert "[test-suite-review]" in skill_body


class TestReviewSection:
    """Validate the main review workflow sections."""

    def test_has_prework(self, skill_body):
        assert "### Pre-work" in skill_body

    def test_has_dispatch(self, skill_body):
        assert "### Dispatch" in skill_body

    def test_has_synthesis(self, skill_body):
        assert "### Synthesis" in skill_body

    def test_has_invariant_checks(self, skill_body):
        assert "### Quick invariant checks" in skill_body

    def test_has_quality_bar(self, skill_body):
        assert "### Quality bar" in skill_body


class TestAgentDispatch:
    """Validate the 7 parallel agents table."""

    def test_has_seven_agents(self, skill_body):
        """The dispatch table should define exactly 7 agents."""
        rows = re.findall(r"^\|\s*(\d+)\s*\|", skill_body, re.MULTILINE)
        agent_numbers = [int(r) for r in rows]
        assert agent_numbers == [1, 2, 3, 4, 5, 6, 7], (
            f"Expected agents 1-7, found: {agent_numbers}"
        )

    def test_agents_have_file_patterns(self, skill_body):
        """Each agent row should reference sql file patterns."""
        # Match table rows with agent number and content
        rows = re.findall(
            r"^\|\s*\d+\s*\|[^|]+\|([^|]+)\|",
            skill_body,
            re.MULTILINE,
        )
        for row in rows:
            assert "sql" in row.lower() or "spec" in row.lower(), (
                f"Agent row should reference SQL or spec files: {row}"
            )

    def test_agent_review_questions(self, skill_body):
        """Each agent should answer specific quality questions."""
        questions = [
            "Dead code",
            "Tautological",
            "EXPLAIN coverage",
            "Dataset oversizing",
            "Exception-swallowing",
            "Hardcoded values",
            "TODO tests",
        ]
        for q in questions:
            assert q in skill_body, f"Missing agent review question: {q}"


class TestSynthesisOutput:
    """Validate the expected synthesis report structure."""

    def test_has_final_report_path(self, skill_body):
        assert "docs/test_review/FINAL_REPORT.md" in skill_body

    def test_has_status_table(self, skill_body):
        assert "Critical" in skill_body
        assert "High" in skill_body
        assert "Moderate" in skill_body

    def test_has_performance_wins(self, skill_body):
        assert "Performance wins" in skill_body

    def test_has_coverage_gaps(self, skill_body):
        assert "Coverage gaps" in skill_body


class TestQualityBar:
    """Validate the quality criteria definitions."""

    def test_defines_good_test(self, skill_body):
        assert "Good test" in skill_body
        assert "EXPLAIN" in skill_body
        assert "schema isolation" in skill_body

    def test_defines_bad_test(self, skill_body):
        assert "Bad test" in skill_body
        assert "exception-swallowing" in skill_body.lower()


class TestOverallStructure:
    """High-level structural checks."""

    def test_skill_md_not_empty(self, skill):
        assert len(skill.content) > 100

    def test_has_bash_code_blocks(self, skill_body):
        blocks = re.findall(r"```bash", skill_body)
        assert len(blocks) >= 3, (
            f"Expected at least 3 bash code blocks, found {len(blocks)}"
        )

    def test_has_markdown_table(self, skill_body):
        assert "|---|" in skill_body or "| --- |" in skill_body

    def test_has_section_hierarchy(self, skill_body):
        h2_sections = re.findall(r"^## ", skill_body, re.MULTILINE)
        h3_sections = re.findall(r"^### ", skill_body, re.MULTILINE)
        assert len(h2_sections) >= 2, "Should have at least 2 H2 sections"
        assert len(h3_sections) >= 4, "Should have at least 4 H3 sections"
