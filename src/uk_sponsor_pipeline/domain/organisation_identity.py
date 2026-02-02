"""Organisation identity and name normalisation utilities.

Usage example:
    from uk_sponsor_pipeline.domain.organisation_identity import (
        generate_query_variants,
        normalise_org_name,
        simple_similarity,
    )

    query_variants = generate_query_variants("Acme Ltd")
    score = simple_similarity("Acme Ltd", "Acme Limited")
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Company suffixes to strip (order matters: longer first)
COMPANY_SUFFIXES = (
    "private limited company",
    "public limited company",
    "limited liability partnership",
    "community interest company",
    "limited",
    "ltd",
    "plc",
    "llp",
    "cic",
    "incorporated",
    "inc",
    "corporation",
    "corp",
    "company",
    "co",
    "group",
    "holdings",
    "uk",
    "international",
    "intl",
)

# Patterns that indicate trading name
TRADING_AS_PATTERNS = (
    r"\bt/a\b",
    r"\btrading\s+as\b",
    r"\bt\.a\.\b",
    r"\bdba\b",  # doing business as
)


@dataclass
class NormalisedName:
    """Result of name normalisation."""

    raw: str
    normalised: str
    variants: list[str]  # Alternative query names


def normalise_org_name(name: str) -> str:
    """Normalise organisation name for matching.

    Transformations:
    1. Lowercase
    2. Remove punctuation except alphanumeric and whitespace
    3. Strip company suffixes (Ltd, PLC, etc.)
    4. Collapse whitespace
    5. Strip leading/trailing whitespace

    Args:
        name: Raw organisation name

    Returns:
        Normalised name for matching
    """
    if not name:
        return ""

    s = name.lower().strip()

    # Remove punctuation (keep alphanumeric and spaces)
    s = re.sub(r"[^\w\s]", " ", s)

    # Remove company suffixes (word boundaries)
    for suffix in COMPANY_SUFFIXES:
        pattern = rf"\b{re.escape(suffix)}\b"
        s = re.sub(pattern, " ", s, flags=re.IGNORECASE)

    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()

    return s


def extract_trading_name(name: str) -> str | None:
    """Extract trading name from "X T/A Y" or "X trading as Y" pattern."""
    for pattern in TRADING_AS_PATTERNS:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            after = name[match.end() :].strip()
            if after:
                return after
    return None


def extract_bracketed_names(name: str) -> list[str]:
    """Extract names from brackets."""
    names: list[str] = []
    brackets = re.findall(r"\(([^)]+)\)", name)
    for bracket in brackets:
        cleaned = bracket.strip()
        if cleaned and len(cleaned) > 2:
            names.append(cleaned)

    without_brackets = re.sub(r"\([^)]*\)", "", name).strip()
    if without_brackets and without_brackets != name.strip():
        names.insert(0, without_brackets)

    return names


def split_on_delimiters(name: str) -> list[str]:
    """Split name on common delimiters."""
    parts = re.split(r"\s+[-/|]\s+", name)
    return [p.strip() for p in parts if p.strip()]


def generate_query_variants(name: str) -> list[str]:
    """Generate search query variants for Companies House API."""
    if not name or not name.strip():
        return []

    variants: list[str] = [name.strip()]
    seen_normalised: set[str] = {normalise_org_name(name)}

    def add_variant(v: str) -> None:
        v = v.strip()
        if not v:
            return
        norm = normalise_org_name(v)
        if norm and norm not in seen_normalised:
            variants.append(v)
            seen_normalised.add(norm)

    trading = extract_trading_name(name)
    if trading:
        add_variant(trading)
        for pattern in TRADING_AS_PATTERNS:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                before = name[: match.start()].strip()
                if before:
                    add_variant(before)
                break

    for bracketed in extract_bracketed_names(name):
        add_variant(bracketed)

    for part in split_on_delimiters(name):
        if part != name.strip():
            add_variant(part)

    return variants[:5]


def _token_sort_key(name: str) -> str:
    toks = normalise_org_name(name).split()
    toks.sort()
    return " ".join(toks)


def simple_similarity(a: str, b: str) -> float:
    """Calculate name similarity using Jaccard + character overlap."""
    a0, b0 = _token_sort_key(a), _token_sort_key(b)
    if not a0 or not b0:
        return 0.0

    set_a, set_b = set(a0.split()), set(b0.split())
    jacc = len(set_a & set_b) / max(1, len(set_a | set_b))

    common = sum(min(a0.count(ch), b0.count(ch)) for ch in set(a0))
    denom = max(len(a0), len(b0))
    char_overlap = common / denom if denom else 0.0

    return 0.6 * jacc + 0.4 * char_overlap
