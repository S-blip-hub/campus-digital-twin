"""Campus digital twin: spatial layers, agent-based weekday simulation and analytics."""

from .layers import LAYER_NAMES, build_layers, load_network, places_table, write_layers
from .model import Agent, CampusTwin

__all__ = ["Agent", "CampusTwin", "LAYER_NAMES", "build_layers", "load_network", "places_table", "write_layers"]
__version__ = "1.0.0"
