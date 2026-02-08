"""
CCWebgraph - Python interface to CommonCrawl webgraph via py4j.

Provides high-performance access to the 93M domain, 1.6B edge
CommonCrawl webgraph for domain discovery and network analysis.

Domain names are accepted and returned in normal format (e.g. "cnn.com").
The CommonCrawl reversed notation (e.g. "com.cnn") is handled internally.
"""

import os
import atexit
from typing import Dict, List, Optional, Tuple, Union

from .setup_utils import (
    DEFAULT_DATA_DIR,
    DEFAULT_VERSION,
    check_java,
    check_offsets,
    check_webgraph_data,
    find_jar,
)
from .converters import DiscoveryResult

try:
    from py4j.java_gateway import JavaGateway, GatewayParameters, launch_gateway
    HAS_PY4J = True
except ImportError:
    HAS_PY4J = False


def _reverse_domain(domain: str) -> str:
    """Convert normal domain to CommonCrawl reversed notation.

    Example: "www.cnn.com" -> "com.cnn.www"
    """
    return ".".join(reversed(domain.split(".")))


def _unreverse_domain(rev_domain: str) -> str:
    """Convert CommonCrawl reversed notation back to normal domain.

    Example: "com.cnn.www" -> "www.cnn.com"
    """
    return ".".join(reversed(rev_domain.split(".")))


class CCWebgraph:
    """
    Python interface to CommonCrawl's domain webgraph.

    The graph is loaded once into JVM memory via py4j. After the initial
    load (~5 seconds), all queries are nearly instant.

    All public methods accept and return domains in normal format
    (e.g. "cnn.com"). The CommonCrawl reversed notation is handled
    transparently.

    Quick start::

        from pyccwebgraph import CCWebgraph

        webgraph = CCWebgraph.setup()
        results = webgraph.discover_backlinks(
            seeds=["cnn.com", "bbc.com"],
            min_connections=5,
        )

    For lower-level control, use the constructor directly::

        wg = CCWebgraph(webgraph_dir="/data/webgraph", version="cc-main-2024-feb-apr-may")
        wg.load_graph()
    """

    # ------------------------------------------------------------------ #
    #  Construction & Setup
    # ------------------------------------------------------------------ #

    def __init__(
        self,
        webgraph_dir: str,
        version: str = DEFAULT_VERSION,
        jar_path: Optional[str] = None,
    ):
        """
        Initialize CCWebgraph (does not load graph yet — call load_graph()).

        Args:
            webgraph_dir: Directory containing webgraph files.
            version: Webgraph version string.
            jar_path: Path to cc-webgraph JAR. If None, auto-detects.
        """
        if not HAS_PY4J:
            raise ImportError(
                "py4j is required for CCWebgraph. "
                "Install with: pip install py4j"
            )

        self.webgraph_dir = webgraph_dir
        self.version = version
        self.graph_base = os.path.join(webgraph_dir, f"{version}-domain")
        self.jar_path = find_jar(jar_path)

        self.gateway = None
        self.graph = None
        self._port = None

    @classmethod
    def setup(
        cls,
        webgraph_dir: Optional[str] = None,
        version: str = DEFAULT_VERSION,
        jar_path: Optional[str] = None,
        auto_download: bool = True,
    ) -> "CCWebgraph":
        """
        Initialize with automatic setup and verification.

        This is the recommended way to create a CCWebgraph instance.
        It checks Java, locates the JAR, downloads data if needed,
        builds offsets, and loads the graph.

        Args:
            webgraph_dir: Directory containing webgraph files.
                         If None, uses ~/.pyccwebgraph/data
            version: Webgraph version string.
            jar_path: Path to cc-webgraph JAR.
                     If None, auto-detects.
            auto_download: If True and data missing, download automatically.
                          If False and data missing, raise FileNotFoundError.

        Returns:
            CCWebgraph instance with loaded graph.

        Raises:
            RuntimeError: If Java not found or version < 17.
            FileNotFoundError: If data missing and auto_download=False.
        """
        # 1. Check Java
        java_ok, java_msg = check_java()
        if not java_ok:
            raise RuntimeError(java_msg)
        print(f"Java: {java_msg}")

        # 2. Resolve paths
        if webgraph_dir is None:
            webgraph_dir = DEFAULT_DATA_DIR
        os.makedirs(webgraph_dir, exist_ok=True)

        # 3. Find JAR
        resolved_jar = find_jar(jar_path)
        print(f"JAR: {resolved_jar}")

        # 4. Check webgraph data
        data_ok, missing = check_webgraph_data(webgraph_dir, version)
        if not data_ok:
            if auto_download:
                from .download import download_webgraph
                print(f"\nDownloading webgraph to {webgraph_dir}...")
                download_webgraph(webgraph_dir, version, resolved_jar)
            else:
                raise FileNotFoundError(
                    f"Webgraph data missing in {webgraph_dir}. "
                    f"Missing files: {missing}\n"
                    f"Set auto_download=True or download manually."
                )

        # 5. Check offsets
        offsets_ok, missing_offsets = check_offsets(webgraph_dir, version)
        if not offsets_ok:
            from .download import build_offsets
            print("Building offset files...")
            build_offsets(webgraph_dir, version, resolved_jar)

        # 6. Create instance and load graph
        instance = cls(webgraph_dir, version, resolved_jar)
        instance.load_graph()
        return instance

    # ------------------------------------------------------------------ #
    #  Graph Lifecycle
    # ------------------------------------------------------------------ #

    def load_graph(self) -> None:
        """
        Start JVM and load the graph into memory.

        Takes ~5 seconds on first call. After loading, all queries are
        nearly instant. The graph uses memory-mapped I/O so it doesn't
        consume JVM heap.
        """
        if self.graph is not None:
            return  # Already loaded

        if not os.path.exists(self.jar_path):
            raise FileNotFoundError(
                f"cc-webgraph JAR not found at {self.jar_path}"
            )

        print("Starting JVM with cc-webgraph...")

        self._port = launch_gateway(
            classpath=self.jar_path,
            die_on_exit=True,
            redirect_stdout=None,
            redirect_stderr=None,
        )

        self.gateway = JavaGateway(
            gateway_parameters=GatewayParameters(port=self._port)
        )

        atexit.register(self.shutdown)

        print(f"Loading graph: {self.graph_base}")

        Graph = self.gateway.jvm.org.commoncrawl.webgraph.explore.Graph
        self.graph = Graph(self.graph_base)

        print("Graph loaded!")

    def shutdown(self) -> None:
        """Shutdown the JVM connection."""
        if self.gateway is not None:
            try:
                self.gateway.shutdown()
            except Exception:
                pass
            self.gateway = None
            self.graph = None

    def _ensure_loaded(self) -> None:
        """Ensure graph is loaded."""
        if self.graph is None:
            raise RuntimeError(
                "Graph not loaded. Call load_graph() or use CCWebgraph.setup()."
            )

    # ------------------------------------------------------------------ #
    #  Internal Helpers
    # ------------------------------------------------------------------ #

    def _java_int_array_to_list(self, java_array) -> List[int]:
        """
        Convert Java int[] to Python list via a single IPC call.

        Uses Arrays.toString() in Java and string parsing in Python
        to avoid N separate array element accesses over the socket.
        """
        s = str(self.gateway.jvm.java.util.Arrays.toString(java_array))
        if s == "[]":
            return []
        return [int(x) for x in s[1:-1].split(", ")]

    def _java_long_array_to_list(self, java_array) -> List[int]:
        """Convert Java long[] to Python list via a single IPC call."""
        s = str(self.gateway.jvm.java.util.Arrays.toString(java_array))
        if s == "[]":
            return []
        return [int(x) for x in s[1:-1].split(", ")]

    @staticmethod
    def _to_rev(domain: str) -> str:
        """Normalize and reverse a domain for graph lookup."""
        return _reverse_domain(domain.strip().lower())

    @staticmethod
    def _from_rev(label: str) -> str:
        """Unreverse a graph label to normal domain format."""
        return _unreverse_domain(label)

    def _lookup_id(self, domain: str) -> int:
        """Look up vertex ID for a normal-format domain. Returns -1 if missing."""
        return self.graph.vertexLabelToId(self._to_rev(domain))

    def _lookup_label(self, vid: int) -> Optional[str]:
        """Look up normal-format domain for a vertex ID."""
        label = self.graph.vertexIdToLabel(vid)
        if label is None:
            return None
        return self._from_rev(label)

    # ------------------------------------------------------------------ #
    #  Domain <-> ID Mapping
    # ------------------------------------------------------------------ #

    def domain_to_id(self, domain: str) -> Optional[int]:
        """
        Convert a domain name to its graph vertex ID.

        Args:
            domain: Domain name (e.g. "cnn.com").

        Returns:
            Vertex ID, or None if domain not in graph.
        """
        self._ensure_loaded()
        vid = self._lookup_id(domain)
        return int(vid) if vid >= 0 else None

    def id_to_domain(self, vid: int) -> Optional[str]:
        """
        Convert a graph vertex ID to its domain name.

        Args:
            vid: Vertex ID.

        Returns:
            Domain name in normal format, or None if ID is invalid.
        """
        self._ensure_loaded()
        return self._lookup_label(vid)

    def validate_seeds(
        self, seed_domains: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        Check which seed domains exist in the graph.

        Args:
            seed_domains: List of domain names (normal format).

        Returns:
            Tuple of (found_domains, missing_domains) in normal format.
        """
        self._ensure_loaded()
        found = []
        missing = []
        for domain in seed_domains:
            clean = domain.strip().lower()
            vid = self._lookup_id(clean)
            if vid >= 0:
                found.append(clean)
            else:
                missing.append(clean)
        return found, missing

    # ------------------------------------------------------------------ #
    #  Low-Level Graph Access
    # ------------------------------------------------------------------ #

    def get_predecessors(self, domain: str) -> List[str]:
        """
        Get all domains that link TO this domain (backlinks).

        Args:
            domain: Target domain name (e.g. "cnn.com").

        Returns:
            List of domain names in normal format.
        """
        self._ensure_loaded()
        vid = self._lookup_id(domain)
        if vid < 0:
            return []

        pred_ids = self.graph.predecessors(vid)
        results = []
        for i in range(len(pred_ids)):
            label = self._lookup_label(int(pred_ids[i]))
            if label is not None:
                results.append(label)
        return results

    def get_successors(self, domain: str) -> List[str]:
        """
        Get all domains that this domain links TO (outlinks).

        Args:
            domain: Source domain name (e.g. "cnn.com").

        Returns:
            List of domain names in normal format.
        """
        self._ensure_loaded()
        vid = self._lookup_id(domain)
        if vid < 0:
            return []

        succ_ids = self.graph.successors(vid)
        results = []
        for i in range(len(succ_ids)):
            label = self._lookup_label(int(succ_ids[i]))
            if label is not None:
                results.append(label)
        return results

    def shared_predecessors(
        self, domains: List[str], min_shared: Optional[int] = None
    ) -> List[str]:
        """
        Find domains that link to multiple given domains.

        Uses Java-side filtering for performance.

        Args:
            domains: List of target domain names (normal format).
            min_shared: Minimum number of targets a predecessor must link to.
                       Defaults to len(domains) (intersection).

        Returns:
            List of predecessor domain names in normal format.
        """
        self._ensure_loaded()
        ids = self._domains_to_java_ids(domains)
        if ids is None:
            return []

        if min_shared is None:
            min_shared = len(domains)

        result_ids = self.graph.sharedPredecessors(ids, min_shared, len(domains))
        return self._resolve_long_array(result_ids)

    def shared_successors(
        self, domains: List[str], min_shared: Optional[int] = None
    ) -> List[str]:
        """
        Find domains that multiple given domains link to.

        Uses Java-side filtering for performance.

        Args:
            domains: List of source domain names (normal format).
            min_shared: Minimum number of sources that must link to a successor.
                       Defaults to len(domains) (intersection).

        Returns:
            List of successor domain names in normal format.
        """
        self._ensure_loaded()
        ids = self._domains_to_java_ids(domains)
        if ids is None:
            return []

        if min_shared is None:
            min_shared = len(domains)

        result_ids = self.graph.sharedSuccessors(ids, min_shared, len(domains))
        return self._resolve_long_array(result_ids)

    def _domains_to_java_ids(self, domains: List[str]):
        """Convert normal-format domain list to Java long[] for shared* methods."""
        py_ids = []
        for d in domains:
            vid = self._lookup_id(d)
            if vid >= 0:
                py_ids.append(int(vid))
        if not py_ids:
            return None

        java_ids = self.gateway.new_array(self.gateway.jvm.long, len(py_ids))
        for i, vid in enumerate(py_ids):
            java_ids[i] = vid
        return java_ids

    def _resolve_long_array(self, java_array) -> List[str]:
        """Convert Java long[] result IDs to normal-format domain name list."""
        id_list = self._java_long_array_to_list(java_array)
        results = []
        for vid in id_list:
            label = self._lookup_label(vid)
            if label is not None:
                results.append(label)
        return results

    # ------------------------------------------------------------------ #
    #  Discovery
    # ------------------------------------------------------------------ #

    def discover(
        self,
        seed_domains: List[str],
        min_connections: int = 1,
        direction: str = "backlinks",
        format: str = "edges",
    ) -> Union[DiscoveryResult, object]:
        """
        Discover domains connected to seed domains.

        For each seed, finds neighbors and counts how many seeds each
        neighbor is connected to. Neighbors below the min_connections
        threshold are filtered out.

        Args:
            seed_domains: List of seed domain names (normal format, e.g. "cnn.com").
            min_connections: Minimum seed connections required.
            direction: "backlinks" (who links TO seeds) or
                      "outlinks" (who seeds link TO).
            format: Output format. One of:
                - 'edges' (default): Returns DiscoveryResult with .nodes
                  and .edges, plus .networkx()/.networkit()/.igraph() converters.
                - 'networkx': Returns nx.DiGraph directly.
                - 'networkit': Returns (nk.Graph, name_map) directly.
                - 'igraph': Returns ig.Graph directly.

        Returns:
            DiscoveryResult (format='edges') or graph object for other formats.
            All domain names in normal format.
        """
        self._ensure_loaded()

        # Validate seeds (convert to reversed internally)
        valid_seeds = []  # normal format
        seed_ids = []
        for domain in seed_domains:
            clean = domain.strip().lower()
            vid = self._lookup_id(clean)
            if vid >= 0:
                valid_seeds.append(clean)
                seed_ids.append(int(vid))

        if not seed_ids:
            print("No valid seed domains found in graph.")
            return DiscoveryResult(nodes=[], edges=[], seeds=[])

        print(f"Processing {len(seed_ids)} seed domains...")
        seed_id_set = set(seed_ids)
        seed_id_to_domain = dict(zip(seed_ids, valid_seeds))

        # Count connections and track which seeds connect to each neighbor
        neighbor_counts: Dict[int, int] = {}
        neighbor_seed_ids: Dict[int, List[int]] = {}

        for i, seed_id in enumerate(seed_ids):
            if direction == "backlinks":
                java_neighbors = self.graph.predecessors(seed_id)
            else:
                java_neighbors = self.graph.successors(seed_id)

            neighbors = self._java_int_array_to_list(java_neighbors)

            for nid in neighbors:
                if nid not in seed_id_set:
                    neighbor_counts[nid] = neighbor_counts.get(nid, 0) + 1
                    if nid not in neighbor_seed_ids:
                        neighbor_seed_ids[nid] = []
                    neighbor_seed_ids[nid].append(seed_id)

            if (i + 1) % 100 == 0 or i == len(seed_ids) - 1:
                print(f"\rProcessed {i + 1}/{len(seed_ids)} seeds...", end="")

        print()
        print(f"Found {len(neighbor_counts):,} unique neighbor domains")

        # Filter and build results (unreverse all domain names)
        nodes = []
        edges = []
        num_seeds = len(seed_ids)

        for nid, count in neighbor_counts.items():
            if count < min_connections:
                continue
            domain = self._lookup_label(nid)
            if not domain:
                continue

            nodes.append({
                "domain": domain,
                "connections": count,
                "percentage": round(count * 100.0 / num_seeds, 2),
            })

            # Build edges from this neighbor to/from its connected seeds
            for sid in neighbor_seed_ids[nid]:
                seed_domain = seed_id_to_domain[sid]
                if direction == "backlinks":
                    edges.append((domain, seed_domain))
                else:
                    edges.append((seed_domain, domain))

        nodes.sort(key=lambda x: x["connections"], reverse=True)
        print(f"Found {len(nodes):,} domains with >= {min_connections} connections")

        result = DiscoveryResult(nodes=nodes, edges=edges, seeds=valid_seeds)

        if format == "networkx":
            return result.networkx()
        elif format == "networkit":
            return result.networkit()
        elif format == "igraph":
            return result.igraph()
        return result

    def discover_backlinks(
        self,
        seeds: List[str],
        min_connections: int = 1,
        format: str = "edges",
    ) -> Union[DiscoveryResult, object]:
        """
        Discover domains that link TO the seed domains.

        Args:
            seeds: List of seed domain names (e.g. ["cnn.com", "bbc.com"]).
            min_connections: Minimum seed connections required.
            format: Output format ('edges', 'networkx', 'networkit', 'igraph').

        Returns:
            DiscoveryResult or graph object depending on format.
        """
        return self.discover(seeds, min_connections, "backlinks", format)

    def discover_outlinks(
        self,
        seeds: List[str],
        min_connections: int = 1,
        format: str = "edges",
    ) -> Union[DiscoveryResult, object]:
        """
        Discover domains that the seed domains link TO.

        Args:
            seeds: List of seed domain names (e.g. ["cnn.com", "bbc.com"]).
            min_connections: Minimum seed connections required.
            format: Output format ('edges', 'networkx', 'networkit', 'igraph').

        Returns:
            DiscoveryResult or graph object depending on format.
        """
        return self.discover(seeds, min_connections, "outlinks", format)

    def shared_outlinks(
        self,
        seeds: List[str],
        min_connections: int = 1,
    ) -> DiscoveryResult:
        """
        Find domains that multiple seeds link to, using Java-side filtering.

        Faster than discover_outlinks() but does not return connection counts.

        Args:
            seeds: List of seed domain names.
            min_connections: Minimum seeds that must link to a domain.

        Returns:
            DiscoveryResult (connection counts will be 0).
        """
        domains = self.shared_successors(seeds, min_shared=min_connections)
        seed_set = set(s.strip().lower() for s in seeds)
        domains = [d for d in domains if d not in seed_set]
        nodes = [{"domain": d, "connections": 0, "percentage": 0.0}
                 for d in domains]
        edges = [(s, d) for d in domains for s in seed_set]
        return DiscoveryResult(nodes=nodes, edges=edges, seeds=list(seed_set))

    def shared_backlinks(
        self,
        seeds: List[str],
        min_connections: int = 1,
    ) -> DiscoveryResult:
        """
        Find domains that link to multiple seeds, using Java-side filtering.

        Faster than discover_backlinks() but does not return connection counts.

        Args:
            seeds: List of seed domain names.
            min_connections: Minimum seeds a domain must link to.

        Returns:
            DiscoveryResult (connection counts will be 0).
        """
        domains = self.shared_predecessors(seeds, min_shared=min_connections)
        seed_set = set(s.strip().lower() for s in seeds)
        domains = [d for d in domains if d not in seed_set]
        nodes = [{"domain": d, "connections": 0, "percentage": 0.0}
                 for d in domains]
        edges = [(d, s) for d in domains for s in seed_set]
        return DiscoveryResult(nodes=nodes, edges=edges, seeds=list(seed_set))
