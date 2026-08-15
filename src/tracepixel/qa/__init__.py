"""Deterministic pixel-QA fact surfaces."""

from tracepixel.qa.color import (
    COLOR_QA_SCHEMA_V1,
    MAX_COLOR_POLICY_COLORS_V1,
    ColorCountFactsV1,
    ColorQaConfigurationError,
    ColorQaV1,
    MaximumColorCheckV1,
    PaletteMembershipCheckV1,
    TransparentRgbCheckV1,
    TransparentRgbFactsV1,
    TransparentRgbPolicyV1,
    analyze_color,
)
from tracepixel.qa.structural import (
    STRUCTURAL_QA_SCHEMA_V1,
    AlphaFactsV1,
    BoundsV1,
    DimensionsV1,
    EdgeContactV1,
    MarginsV1,
    StructuralFactsV1,
    analyze_structural,
)

__all__ = [
    "COLOR_QA_SCHEMA_V1",
    "MAX_COLOR_POLICY_COLORS_V1",
    "ColorCountFactsV1",
    "ColorQaConfigurationError",
    "ColorQaV1",
    "MaximumColorCheckV1",
    "PaletteMembershipCheckV1",
    "TransparentRgbCheckV1",
    "TransparentRgbFactsV1",
    "TransparentRgbPolicyV1",
    "analyze_color",
    "STRUCTURAL_QA_SCHEMA_V1",
    "AlphaFactsV1",
    "BoundsV1",
    "DimensionsV1",
    "EdgeContactV1",
    "MarginsV1",
    "StructuralFactsV1",
    "analyze_structural",
]
