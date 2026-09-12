"""Competition-engine integration with explicit lifecycle ownership."""

from .api_loader import load_competition_api
from .lifecycle import SearchInputs, SearchSession, SearchSessionError

__all__ = ["SearchInputs", "SearchSession", "SearchSessionError", "load_competition_api"]
