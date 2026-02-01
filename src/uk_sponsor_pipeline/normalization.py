"""Name normalization utilities for organization name matching.

This module provides functions to normalize organization names for matching
and deduplication while preserving the original names for audit trails.
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
class NormalizedName:
    """Result of name normalization."""

    raw: str
    normalized: str
    variants: list[str]  # Alternative query names


def normalize_org_name(name: str) -> str:
    """Normalize organization name for matching.

    Transformations:
    1. Lowercase
    2. Remove punctuation except alphanumeric and whitespace
    3. Strip company suffixes (Ltd, PLC, etc.)
    4. Collapse whitespace
    5. Strip leading/trailing whitespace

    Args:
        name: Raw organization name

    Returns:
        Normalized name for matching
    """
    if not name:
        return ""

    s = name.lower().strip()

    # Remove punctuation (keep alphanumeric and spaces)
    s = re.sub(r"[^\w\s]", " ", s)

    # Remove company suffixes (word boundaries)
    for suffix in COMPANY_SUFFIXES:
        # Match suffix at word boundary
        pattern = rf"\b{re.escape(suffix)}\b"
        s = re.sub(pattern, " ", s, flags=re.IGNORECASE)

    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()

    return s


def extract_trading_name(name: str) -> str | None:
    """Extract trading name from "X T/A Y" or "X trading as Y" pattern.

    Args:
        name: Organization name possibly containing trading as pattern

    Returns:
        The trading name (Y) if pattern found, else None
    """
    for pattern in TRADING_AS_PATTERNS:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            # Return everything after the pattern
            after = name[match.end() :].strip()
            if after:
                return after
    return None


def extract_bracketed_names(name: str) -> list[str]:
    """Extract names from brackets.

    Examples:
        "Foo (Bar Ltd)" → ["Foo", "Bar Ltd"]
        "ABC Holdings (XYZ Corp)" → ["ABC Holdings", "XYZ Corp"]

    Args:
        name: Organization name possibly containing brackets

    Returns:
        List of extracted names (may be empty)
    """
    names: list[str] = []

    # Find all bracketed content
    brackets = re.findall(r"\(([^)]+)\)", name)
    for bracket in brackets:
        cleaned = bracket.strip()
        if cleaned and len(cleaned) > 2:
            names.append(cleaned)

    # Also get the name without brackets
    without_brackets = re.sub(r"\([^)]*\)", "", name).strip()
    if without_brackets and without_brackets != name.strip():
        names.insert(0, without_brackets)

    return names


def split_on_delimiters(name: str) -> list[str]:
    """Split name on common delimiters.

    Examples:
        "Foo - Bar" → ["Foo", "Bar"]
        "ABC / XYZ Corp" → ["ABC", "XYZ Corp"]

    Args:
        name: Organization name with possible delimiters

    Returns:
        List of split parts (may have 1 element if no delimiters)
    """
    # Split on " - " or " / " or " | "
    parts = re.split(r"\s+[-/|]\s+", name)
    return [p.strip() for p in parts if p.strip()]


def generate_query_variants(name: str) -> list[str]:
    """Generate search query variants for Companies House API.

    Strategy:
    1. Original name
    2. Trading name (if "T/A" pattern found)
    3. Bracketed names extracted
    4. Delimiter-split parts
    5. Normalized versions of above

    Args:
        name: Raw organization name

    Returns:
        List of query variants, deduplicated, original first
    """
    if not name or not name.strip():
        return []

    variants: list[str] = [name.strip()]
    seen_normalized: set[str] = {normalize_org_name(name)}

    def add_variant(v: str) -> None:
        v = v.strip()
        if not v:
            return
        norm = normalize_org_name(v)
        if norm and norm not in seen_normalized:
            variants.append(v)
            seen_normalized.add(norm)

    # Trading name
    trading = extract_trading_name(name)
    if trading:
        add_variant(trading)
        # Also add the part before "T/A"
        for pattern in TRADING_AS_PATTERNS:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                before = name[: match.start()].strip()
                if before:
                    add_variant(before)
                break

    # Bracketed names
    for bracketed in extract_bracketed_names(name):
        add_variant(bracketed)

    # Delimiter splits
    for part in split_on_delimiters(name):
        if part != name.strip():
            add_variant(part)

    return variants[:5]  # Limit to 5 variants max
