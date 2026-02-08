"""
Graph format converters for pyccwebgraph.

Converts discovery results (node lists + edge lists) into
NetworkX, NetworKit, igraph, or pandas formats.
"""

from typing import Dict, List, Optional, Tuple


class DiscoveryResult:
    """
    Result of a discovery query.

    Provides dict-like access to raw results and conversion methods
    for popular graph libraries.

    Attributes:
        nodes: List of dicts with keys 'domain', 'connections', 'percentage'.
               Sorted by connections descending.
        edges: List of (source, target) domain name tuples.
        seeds: List of seed domain names used in the query.
    """

    def __init__(
        self,
        nodes: List[Dict],
        edges: List[Tuple[str, str]],
        seeds: List[str],
    ):
        self.nodes = nodes
        self.edges = edges
        self.seeds = seeds

    def __getitem__(self, key):
        """Dict-like access: result['nodes'], result['edges'], result['seeds']."""
        if key == "nodes":
            return self.nodes
        elif key == "edges":
            return self.edges
        elif key == "seeds":
            return self.seeds
        raise KeyError(key)

    def __len__(self):
        return len(self.nodes)

    def __repr__(self):
        return (
            f"DiscoveryResult({len(self.nodes)} nodes, "
            f"{len(self.edges)} edges, {len(self.seeds)} seeds)"
        )

    def networkx(self):
        """
        Convert to NetworkX DiGraph.

        Requires: pip install networkx

        Returns:
            nx.DiGraph with domain names as node labels.
            Seed nodes have attribute is_seed=True.
            Discovered nodes have attributes: connections, percentage.
        """
        return to_networkx(self.nodes, self.edges, self.seeds)

    def networkit(self):
        """
        Convert to NetworKit graph.

        Requires: pip install networkit

        Returns:
            Tuple of (nk.Graph, name_map) where name_map is
            {domain_name: node_id}.
        """
        return to_networkit(self.nodes, self.edges, self.seeds)

    def igraph(self):
        """
        Convert to igraph Graph.

        Requires: pip install python-igraph

        Returns:
            ig.Graph with domain names as vertex 'name' attribute.
        """
        return to_igraph(self.nodes, self.edges, self.seeds)

    def to_dataframe(self):
        """
        Convert node data to pandas DataFrame.

        Requires: pip install pandas

        Returns:
            DataFrame with columns: domain, connections, percentage.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for to_dataframe(). "
                "Install with: pip install pyccwebgraph[pandas]"
            )
        return pd.DataFrame(self.nodes)


def to_networkx(
    nodes: List[Dict],
    edges: List[Tuple[str, str]],
    seeds: Optional[List[str]] = None,
):
    """
    Convert discovery results to a NetworkX DiGraph.

    Args:
        nodes: List of node dicts with 'domain', 'connections', 'percentage'.
        edges: List of (source, target) domain name tuples.
        seeds: Optional list of seed domains (marked with is_seed=True).

    Returns:
        nx.DiGraph
    """
    try:
        import networkx as nx
    except ImportError:
        raise ImportError(
            "NetworkX is required for networkx output. "
            "Install with: pip install pyccwebgraph[networkx]"
        )

    G = nx.DiGraph()
    seed_set = set(seeds) if seeds else set()

    # Add seed nodes
    for seed in seed_set:
        G.add_node(seed, is_seed=True)

    # Add discovered nodes with attributes
    for node in nodes:
        G.add_node(
            node["domain"],
            connections=node["connections"],
            percentage=node["percentage"],
            is_seed=node["domain"] in seed_set,
        )

    # Add edges
    G.add_edges_from(edges)

    return G


def to_networkit(
    nodes: List[Dict],
    edges: List[Tuple[str, str]],
    seeds: Optional[List[str]] = None,
) -> tuple:
    """
    Convert discovery results to a NetworKit graph.

    Args:
        nodes: List of node dicts.
        edges: List of (source, target) domain name tuples.
        seeds: Optional list of seed domains.

    Returns:
        Tuple of (nk.Graph, name_map) where name_map maps domain -> node_id.
    """
    try:
        import networkit as nk
    except ImportError:
        raise ImportError(
            "NetworKit is required for networkit output. "
            "Install with: pip install pyccwebgraph[networkit]"
        )

    # Build name -> id mapping
    all_domains = set()
    for node in nodes:
        all_domains.add(node["domain"])
    if seeds:
        all_domains.update(seeds)
    for src, tgt in edges:
        all_domains.add(src)
        all_domains.add(tgt)

    name_map = {domain: i for i, domain in enumerate(sorted(all_domains))}

    G = nk.Graph(len(name_map), directed=True)
    for src, tgt in edges:
        G.addEdge(name_map[src], name_map[tgt])

    return G, name_map


def to_igraph(
    nodes: List[Dict],
    edges: List[Tuple[str, str]],
    seeds: Optional[List[str]] = None,
):
    """
    Convert discovery results to an igraph Graph.

    Args:
        nodes: List of node dicts.
        edges: List of (source, target) domain name tuples.
        seeds: Optional list of seed domains.

    Returns:
        ig.Graph with vertex 'name' attributes.
    """
    try:
        import igraph as ig
    except ImportError:
        raise ImportError(
            "igraph is required for igraph output. "
            "Install with: pip install pyccwebgraph[igraph]"
        )

    # Collect all unique domain names
    all_domains = set()
    for node in nodes:
        all_domains.add(node["domain"])
    if seeds:
        all_domains.update(seeds)
    for src, tgt in edges:
        all_domains.add(src)
        all_domains.add(tgt)

    domain_list = sorted(all_domains)
    name_to_idx = {d: i for i, d in enumerate(domain_list)}

    G = ig.Graph(n=len(domain_list), directed=True)
    G.vs["name"] = domain_list

    # Mark seeds
    seed_set = set(seeds) if seeds else set()
    G.vs["is_seed"] = [d in seed_set for d in domain_list]

    # Add connection data for discovered nodes
    node_lookup = {n["domain"]: n for n in nodes}
    G.vs["connections"] = [
        node_lookup.get(d, {}).get("connections", 0) for d in domain_list
    ]

    # Add edges
    edge_list = [(name_to_idx[s], name_to_idx[t]) for s, t in edges]
    G.add_edges(edge_list)

    return G
