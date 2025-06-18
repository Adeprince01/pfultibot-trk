"""Analytics and KPI calculations for recorded calls."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd


def compute_basic_metrics(calls: List[Dict[str, Any]]) -> pd.DataFrame:  # noqa: D401
    """Return a DataFrame with summary metrics for the given calls.

    Args:
        calls: List of call dictionaries retrieved from storage.

    Returns:
        A ``pandas.DataFrame`` containing aggregated statistics such as average
        gain and win rate.
    """
    df = pd.DataFrame(calls)
    # TODO: Implement full set of KPIs; placeholder computations for now.
    summary = {
        "avg_x_gain": df["x_gain"].mean() if "x_gain" in df else None,
        "count": len(df),
    }
    return pd.DataFrame([summary])
