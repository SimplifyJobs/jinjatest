"""Tests for --jt-cov-fail-under session exit code behavior."""

import pytest

pytest_plugins = ["pytester"]


class TestFailUnderExitCode:
    """Tests for the pytest session exit code relative to fail_under."""

    def test_fail_under_exits_nonzero_when_coverage_below(
        self, pytester: pytest.Pytester
    ) -> None:
        """Test session exits non-zero when coverage is below the floor."""
        pytester.makepyfile(
            """
            from jinjatest import TemplateSpec

            def test_render_single_branch(tmp_path):
                template = tmp_path / "branch.j2"
                template.write_text("{% if show %}yes{% else %}no{% endif %}")
                spec = TemplateSpec.from_file(template)
                rendered = spec.render({"show": True})
                assert "yes" in rendered.text
            """
        )

        result = pytester.runpytest("--jt-cov", "--jt-cov-fail-under=99")

        result.assert_outcomes(passed=1)
        result.stdout.fnmatch_lines("*FAILED: Jinja template coverage*")
        assert result.ret == pytest.ExitCode.TESTS_FAILED

    def test_fail_under_exits_zero_when_coverage_met(
        self, pytester: pytest.Pytester
    ) -> None:
        """Test session exits zero when coverage meets the floor."""
        pytester.makepyfile(
            """
            from jinjatest import TemplateSpec

            def test_render_both_branches(tmp_path):
                template = tmp_path / "branch.j2"
                template.write_text("{% if show %}yes{% else %}no{% endif %}")
                spec = TemplateSpec.from_file(template)
                assert "yes" in spec.render({"show": True}).text
                assert "no" in spec.render({"show": False}).text
            """
        )

        result = pytester.runpytest("--jt-cov", "--jt-cov-fail-under=99")

        result.assert_outcomes(passed=1)
        assert result.ret == pytest.ExitCode.OK
