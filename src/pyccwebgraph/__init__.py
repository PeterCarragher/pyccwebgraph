"""
pyccwebgraph - Python interface to CommonCrawl's 93M domain webgraph.

Quick start::

    from pyccwebgraph import CCWebgraph

    webgraph = CCWebgraph.setup()
    results = webgraph.discover_backlinks(
        seeds=["cnn.com", "bbc.com"],
        min_connections=5,
    )
"""

from .ccwebgraph import CCWebgraph
from .converters import DiscoveryResult
from .download import get_available_versions

__all__ = ["CCWebgraph", "DiscoveryResult", "get_available_versions"]
__version__ = "0.1.0"
