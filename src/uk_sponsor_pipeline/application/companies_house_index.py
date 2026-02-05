"""Token index generation for Companies House clean rows."""

from __future__ import annotations

import string
from collections.abc import Iterable

from ..domain.organisation_identity import normalise_org_name
from ..types import CompaniesHouseCleanRow


def bucket_for_token(token: str) -> str:
    if not token:
        return "_"
    first = token[0].lower()
    if first in string.ascii_lowercase:
        return first
    if first.isdigit():
        return "0-9"
    return "_"


def tokenise_company_name(name: str) -> list[str]:
    normalised = normalise_org_name(name)
    if not normalised:
        return []
    tokens = [token for token in normalised.split() if len(token) >= 2]
    return sorted(set(tokens))


def build_token_index(
    rows: Iterable[CompaniesHouseCleanRow],
) -> dict[str, list[tuple[str, str]]]:
    buckets: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        tokens = tokenise_company_name(row["company_name"])
        for token in tokens:
            bucket = bucket_for_token(token)
            buckets.setdefault(bucket, []).append((token, row["company_number"]))
    return buckets
