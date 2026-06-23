from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parents[4] / "company_autocomplete_component" / "dist"
_company_autocomplete = components.declare_component(
    "company_autocomplete",
    path=str(_COMPONENT_DIR),
)


def company_autocomplete(*, query: str, results: list[dict[str, Any]], has_more: bool, key: str = "company_autocomplete") -> Any:
    return _company_autocomplete(query=query, results=results, has_more=has_more, key=key, default=None)
