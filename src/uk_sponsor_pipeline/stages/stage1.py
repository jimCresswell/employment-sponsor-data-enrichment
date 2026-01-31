from __future__ import annotations

from pathlib import Path

import pandas as pd


def run_stage1(
    raw_dir: str | Path = "data/raw",
    out_path: str | Path = "data/interim/stage1_skilled_worker_A_rated_aggregated_by_org.csv",
) -> Path:
    """Stage 1: filter to Skilled Worker + A-rated and aggregate to org level."""
    raw_dir = Path(raw_dir)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # pick most recent csv in raw_dir
    candidates = sorted(raw_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError(f"No raw CSV found in {raw_dir}. Run `uk-sponsor download` first.")

    in_path = candidates[0]
    df = pd.read_csv(in_path, dtype=str).fillna("")
    df.columns = [c.strip() for c in df.columns]
    for col in ["Organisation Name", "Town/City", "County", "Type & Rating", "Route"]:
        df[col] = df[col].astype(str).str.strip()

    mask = (df["Route"] == "Skilled Worker") & df["Type & Rating"].str.contains("A rating", case=False, na=False)
    f = df.loc[mask, ["Organisation Name", "Town/City", "County", "Type & Rating", "Route"]].copy()

    agg = (
        f.groupby("Organisation Name", sort=True, as_index=False)
        .agg({"Town/City": "unique", "County": "unique", "Type & Rating": "unique", "Route": "unique"})
    )

    def arr_to_str(a) -> str:
        vals = [x for x in list(a) if isinstance(x, str) and x.strip() and x.lower() != "nan"]
        seen = set()
        out = []
        for v in vals:
            if v not in seen:
                seen.add(v)
                out.append(v)
        if not out:
            return ""
        return out[0] if len(out) == 1 else " | ".join(out)

    for col in ["Town/City", "County", "Type & Rating", "Route"]:
        agg[col] = agg[col].apply(arr_to_str)

    agg.insert(1, "has_multiple_towns", agg["Town/City"].str.contains(r"\|", regex=True, na=False))
    agg.insert(2, "has_multiple_counties", agg["County"].str.contains(r"\|", regex=True, na=False))

    agg.to_csv(out_path, index=False)
    return out_path
