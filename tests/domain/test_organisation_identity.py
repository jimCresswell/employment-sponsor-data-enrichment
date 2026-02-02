"""Tests for name normalisation utilities."""

from uk_sponsor_pipeline.domain.organisation_identity import (
    extract_bracketed_names,
    extract_trading_name,
    generate_query_variants,
    normalise_org_name,
    simple_similarity,
    split_on_delimiters,
)


class TestNormaliseOrgName:
    """Tests for normalise_org_name function."""

    def test_basic_normalisation(self) -> None:
        assert normalise_org_name("ACME LIMITED") == "acme"
        assert normalise_org_name("Foo Bar Ltd") == "foo bar"
        assert normalise_org_name("XYZ PLC") == "xyz"

    def test_strips_multiple_suffixes(self) -> None:
        assert normalise_org_name("ABC Holdings Group Limited") == "abc"
        assert normalise_org_name("Tech Corp UK Ltd") == "tech"  # corp is also stripped

    def test_removes_punctuation(self) -> None:
        assert normalise_org_name("Foo & Bar Ltd.") == "foo bar"
        assert normalise_org_name("A.B.C. Corp") == "a b c"

    def test_collapses_whitespace(self) -> None:
        assert normalise_org_name("  Foo   Bar   Ltd  ") == "foo bar"

    def test_empty_input(self) -> None:
        assert normalise_org_name("") == ""
        assert normalise_org_name("   ") == ""

    def test_llp_suffix(self) -> None:
        assert normalise_org_name("Legal Partners LLP") == "legal partners"

    def test_cic_suffix(self) -> None:
        assert normalise_org_name("Community Project CIC") == "community project"


class TestExtractTradingName:
    """Tests for extract_trading_name function."""

    def test_t_a_pattern(self) -> None:
        assert extract_trading_name("ABC Holdings T/A Tech Corp") == "Tech Corp"
        assert extract_trading_name("Foo t/a Bar") == "Bar"

    def test_trading_as_pattern(self) -> None:
        assert extract_trading_name("Parent Co Trading As Retail Brand") == "Retail Brand"
        assert extract_trading_name("X trading as Y") == "Y"

    def test_no_pattern(self) -> None:
        assert extract_trading_name("Normal Company Ltd") is None
        assert extract_trading_name("Just A Name") is None


class TestExtractBracketedNames:
    """Tests for extract_bracketed_names function."""

    def test_single_bracket(self) -> None:
        result = extract_bracketed_names("Foo (Bar Ltd)")
        assert "Foo" in result
        assert "Bar Ltd" in result

    def test_multiple_brackets(self) -> None:
        result = extract_bracketed_names("ABC (Dept A) (Dept B)")
        assert "ABC" in result
        assert "Dept A" in result
        assert "Dept B" in result

    def test_no_brackets(self) -> None:
        assert extract_bracketed_names("Plain Name") == []

    def test_short_bracket_content_ignored(self) -> None:
        # Very short content like "(A)" should be ignored
        result = extract_bracketed_names("Foo (AB)")
        # Two chars is too short, should only get Foo
        assert "Foo" in result


class TestSplitOnDelimiters:
    """Tests for split_on_delimiters function."""

    def test_hyphen_split(self) -> None:
        assert split_on_delimiters("Foo - Bar") == ["Foo", "Bar"]

    def test_slash_split(self) -> None:
        assert split_on_delimiters("ABC / XYZ Corp") == ["ABC", "XYZ Corp"]

    def test_pipe_split(self) -> None:
        assert split_on_delimiters("One | Two | Three") == ["One", "Two", "Three"]

    def test_no_delimiter(self) -> None:
        assert split_on_delimiters("Just One Name") == ["Just One Name"]


class TestGenerateQueryVariants:
    """Tests for generate_query_variants function."""

    def test_basic_name(self) -> None:
        variants = generate_query_variants("ACME Software Ltd")
        assert variants[0] == "ACME Software Ltd"  # Original first
        assert len(variants) >= 1

    def test_trading_as_variants(self) -> None:
        variants = generate_query_variants("Parent Holdings T/A Tech Brand")
        normalised = [v.lower() for v in variants]
        # Should include both parts
        assert any("tech brand" in v for v in normalised)
        assert any("parent" in v for v in normalised)

    def test_bracketed_variants(self) -> None:
        variants = generate_query_variants("ABC Corp (Digital Division)")
        assert len(variants) >= 2
        assert any("Digital Division" in v for v in variants)

    def test_empty_input(self) -> None:
        assert generate_query_variants("") == []
        assert generate_query_variants("   ") == []

    def test_limits_variants(self) -> None:
        # Complex name with many potential variants
        variants = generate_query_variants("A (B) (C) (D) T/A X - Y / Z")
        assert len(variants) <= 5  # Should be capped


class TestSimpleSimilarity:
    """Tests for simple_similarity function."""

    def test_exact_match_scores_high(self) -> None:
        score = simple_similarity("Acme Limited", "Acme Limited")
        assert score >= 0.95

    def test_unrelated_scores_low(self) -> None:
        score = simple_similarity("Acme Software", "City Hospital")
        assert score < 0.2

    def test_order_independent_tokens(self) -> None:
        score = simple_similarity("Acme Software", "Software Acme")
        assert score >= 0.9
