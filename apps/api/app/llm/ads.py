"""Explanation-Summary Divergence Score (ADS) calculation (M6).

ADS = 1 - Jaccard(cited_drivers, SHAP top-3 positive feature names); above 0.5 sets escalated.
"""
import logging
from collections.abc import Iterable

logger = logging.getLogger(__name__)


def compute_ads(
    cited_drivers: Iterable[str],
    shap_top_positive_features: Iterable[str],
) -> float:
    """Return ADS = 1 - |A ∩ B| / |A ∪ B| in [0.0, 1.0]."""
    set_a = {str(x).strip() for x in cited_drivers if str(x).strip()}
    set_b = {str(x).strip() for x in list(shap_top_positive_features)[:3] if str(x).strip()}
    union = set_a | set_b
    if not union:
        return 0.0
    intersection = set_a & set_b
    jaccard = len(intersection) / len(union)
    return round(1.0 - jaccard, 4)


def ads_triggers_escalation(ads: float) -> bool:
    """ADS > 0.5 routes the case to human escalation."""
    return ads > 0.5
