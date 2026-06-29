"""Tests for per-pass prompt overrides (issue #429).

An empty override must leave a prompt byte-identical (the working defaults are
untouched); a set override is appended, or substituted at an {override}
placeholder when a customized prompt provides one.
"""
from utils.prompt import (
    format_override_block, apply_override, OVERRIDE_HEADER,
)


class TestFormatOverrideBlock:
    def test_empty_returns_empty(self):
        assert format_override_block("") == ""
        assert format_override_block(None) == ""
        assert format_override_block("   \n  ") == ""

    def test_set_wraps_with_header(self):
        assert format_override_block("Keep the news roundup.") == \
            OVERRIDE_HEADER + "Keep the news roundup."


class TestApplyOverride:
    def test_empty_block_is_byte_identical(self):
        prompt = "Analyze this transcript.\n\nOUTPUT FORMAT: ...{sponsor_database}"
        assert apply_override(prompt, "") == prompt

    def test_appends_when_no_placeholder(self):
        prompt = "Analyze this transcript."
        block = format_override_block("Be stricter on intros.")
        assert apply_override(prompt, block) == prompt + block

    def test_substitutes_at_placeholder(self):
        prompt = "Rules.\n{override}\nOutput: []"
        block = format_override_block("Keep cooking-segment sponsors.")
        out = apply_override(prompt, block)
        assert "{override}" not in out
        assert block.strip() in out
        assert out.startswith("Rules.")
        assert out.endswith("Output: []")

    def test_default_prompt_unchanged_end_to_end(self):
        # Mirrors the runtime: render the (untouched) default, then apply an empty
        # override -> identical to the default. Proves "no behavior change".
        from utils.constants import DEFAULT_SYSTEM_PROMPT
        rendered = DEFAULT_SYSTEM_PROMPT  # sponsors substitution is orthogonal
        assert apply_override(rendered, format_override_block("")) == rendered
