# PyCCWebgraph Python Library - Technical Design Specification

**Version:** 1.0  
**Date:** February 2026  
**Target:** Python 3.8+  
**JVM:** Java 17+

---

## 1. Project Overview

### 1.1 Purpose

PyCCWebgraph provides a Python interface to CommonCrawl's webgraph data for network analysis and domain discovery. It bridges the gap between Java-based WebGraph tools and Python data science workflows, enabling researchers to leverage billion-edge web graphs without requiring JVM expertise.

### 1.2 Goals

- **Ease of use**: `pip install pyccwebgraph` → immediate access to 93M+ domain webgraph
- **Performance**: Leverage Java WebGraph's compressed graph format for memory efficiency
- **Flexibility**: Support multiple output formats (NetworkX, NetworKit, igraph, raw edges)
- **Research-ready**: Enable domain discovery, centrality analysis, community detection on webgraph data

### 1.3 Non-Goals

- Full WebGraph API exposure (focus on discovery + conversion to Python graph libraries)
- Real-time crawling or content analysis (topology only)
- Host-level graphs (domain-level only, for memory constraints)

---

## 2. Architecture

### 2.1 System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    User's Python Environment                 │
│                                                              │
│  ┌────────────────┐         ┌──────────────────┐           │
│  │  User Script   │────────>│ GraphBridge API  │           │
│  │  or Notebook   │         │  (graph_bridge.py)│           │
│  └────────────────┘         └──────────────────┘           │
│                                      │                       │
│                                      v                       │
│                             ┌─────────────────┐             │
│                             │   Converters     │             │
│                             │ (converters.py)  │             │
│                             └─────────────────┘             │
│                                      │                       │
│                                      │ py4j socket           │
└──────────────────────────────────────┼─────────────────────┘
                                       │
                                       v
┌──────────────────────────────────────────────────────────────┐
│                      JVM Process (Java 17)                    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           cc-webgraph JAR (bundled)                   │   │
│  │  - Graph loading (BVGraph.loadMapped)                 │   │
│  │  - Graph traversal (successors, predecessors)         │   │
│  │  - Domain mapping (ImmutableExternalPrefixMap)        │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                   │
│                           v                                   │
│              ┌─────────────────────────┐                     │
│              │  WebGraph Data (mmap)   │                     │
│              │  - domain.graph (~4GB)  │                     │
│              │  - domain-t.graph (~4GB)│                     │
│              │  - domain.offsets       │                     │
│              └─────────────────────────┘                     │
└───────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

**Discovery Query Flow:**
```
1. User calls: bridge.discover_backlinks(seeds, min_connections=5, format='networkx')
2. GraphBridge validates seeds against graph (domain name → vertex ID)
3. For each seed vertex:
   - Call graph.predecessors(seed_id) via py4j
   - Collect neighbor IDs
4. Count connections per neighbor, filter by threshold
5. Convert vertex IDs back to domain names
6. Build edge list: [(neighbor_domain, seed_domain), ...]
7. Pass to converter: to_networkx(edges, nodes)
8. Return NetworkX DiGraph
```

**First-Time Setup Flow:**
```
1. User imports: from pyccwebgraph import GraphBridge
2. User calls: bridge = GraphBridge.setup()
3. System checks:
   - Java 17+ installed? (Error if missing with install instructions)
   - Bundled JAR present? (Should be in package)
   - Webgraph data exists? (If not, offer download)
   - Offset files built? (If not, build them)
4. Launch JVM via py4j with bundled JAR on classpath
5. Load graph into memory (memory-mapped, ~5 seconds)
6. Return bridge instance ready for queries
```

### 2.3 File Structure

```
pyccwebgraph/                    # PyPI package root
├── README.md                          # User guide
├── LICENSE                            # MIT
├── setup.py                           # Package metadata
├── pyproject.toml                     # Modern Python packaging
├── requirements.txt                   # Core dependencies
├── requirements-dev.txt               # Testing, docs
│
├── src/                      # Main package
│   ├── __init__.py                    # Package exports
│   ├── graph_bridge.py                # Core API (GraphBridge class)
│   ├── converters.py                  # Graph format conversions
│   ├── setup_utils.py                 # Setup validation and helpers
│   ├── download.py                    # Webgraph download utilities
│   │
│   └── jars/                          # Bundled JARs
│       ├── cc-webgraph-0.1-SNAPSHOT.jar
│       └── DiscoveryTool.class
│
├── examples/                          # Tutorial notebooks
│   ├── 01_getting_started.ipynb
│   ├── 02_graph_formats.ipynb
│   ├── 03_community_detection.ipynb
│   ├── 04_centrality_analysis.ipynb
│   └── 05_graph_embeddings.ipynb
│
├── docs/                              # Documentation
│   ├── design_choices.md
│   ├── api_reference.md
│   └── performance_guide.md
│
└── tests/                             # Unit tests
    ├── test_bridge.py
    ├── test_converters.py
    └── test_setup.py
```

---

## 3. API Specification

### 3.1 GraphBridge Class

**Primary interface for graph queries.**

```python
class GraphBridge:
    """
    High-performance bridge to CommonCrawl webgraph using py4j.
    
    The graph is loaded once and kept in JVM memory. Subsequent queries
    are nearly instant.
    """
    
    # ----- Setup Methods -----
    
    @classmethod
    def setup(cls, 
              webgraph_dir: Optional[str] = None,
              version: str = "cc-main-2024-feb-apr-may",
              jar_path: Optional[str] = None,
              auto_download: bool = True) -> 'GraphBridge':
        """
        Initialize bridge with automatic setup and verification.
        
        Args:
            webgraph_dir: Directory containing webgraph files.
                         If None, uses ~/.ccwebgraph/data
            version: Webgraph version string
            jar_path: Path to cc-webgraph JAR.
                     If None, uses bundled JAR.
                     If 'latest', builds from GitHub.
            auto_download: If True and data missing, download automatically.
                          If False and data missing, raise error.
        
        Returns:
            GraphBridge instance with loaded graph
        
        Raises:
            RuntimeError: If Java not found or version < 17
            FileNotFoundError: If webgraph data missing and auto_download=False
        
        Example:
            >>> bridge = GraphBridge.setup()
            Downloading webgraph to ~/.ccwebgraph/data...
            Building offset files...
            Loading graph...
            ✓ Graph loaded! 93,912,345 nodes
        """
        pass
```

[Continue with full API specification including all methods...]

---

## 4. Implementation Details

[Full implementation details for graph loading, discovery algorithm, converters...]

---

## 5-13. [Remaining sections: Package Configuration, Testing, Documentation, Deployment, Performance, Dependencies, Error Handling, Maintenance]

**END OF TECHNICAL SPECIFICATION**


## 🏗️ Design Choices: Why Py4J Instead of Jython?

pyccwebgraph uses **Py4J** to bridge Python and Java, rather than alternatives like **Jython** or **py-web-graph**. Here's why:

### The Problem with Jython

**py-web-graph** (the existing Python WebGraph interface) uses **Jython 2.7**, which:
- ❌ Runs Python 2 code on the JVM (Python 2 is EOL since 2020)
- ❌ Has **no Python 3 support** and no active development
- ❌ Can't use CPython libraries (NumPy, pandas, NetworkX, etc.)
- ❌ Offers XML-RPC fallback for CPython, but this adds HTTP serialization overhead on every graph query

**Example:** Querying successors for 1,000 nodes via XML-RPC requires 1,000 HTTP round-trips on localhost. This is 10-100x slower than Py4J's direct object proxying.

### Why Py4J is Better

**Py4J** maintains a **socket connection** between CPython and a persistent JVM:
- ✅ **Python 3 native** - works with Python 3.8-3.12
- ✅ **Fast**: Binary protocol with direct Java object access
- ✅ **Full ecosystem**: Use NumPy, pandas, NetworkX, etc. natively
- ✅ **Proven**: Used internally by Apache Spark (PySpark)
- ✅ **Memory efficient**: Graph stays in JVM, uses memory-mapped I/O

**Performance comparison (1,000 successor queries):**
- Jython (direct): Fast, but Python 2 only
- XML-RPC (py-web-graph): ~10 seconds (HTTP overhead)
- Py4J (pyccwebgraph): ~0.5 seconds (socket + binary)
- JPype: starts the JVM **inside** the Python process rather than via socket, which eliminates socket overhead. However, crashing the JVM will crash python. Instantiating multiple instances of the JVM for different webgraphs inside the same python process (for dynamic webgraph analysis) may be problematic.


### Other Alternatives

| Approach | Pros | Cons | Status |
|----------|------|------|--------|
| **Py4J** | Fast, Python 3, proven | Socket overhead | ✅ **Chosen** |
| **JPype** | No socket, in-process JVM | Less isolation | Evaluated, not needed |
| **Jython** | Direct Java access | Python 2 only | ❌ Obsolete |
| **py-web-graph** | Existing tool | Jython + slow XML-RPC | ❌ Legacy |
| **JNI bindings** | Maximum performance | Complex, platform-specific | ❌ Overkill |
| **Rust/C++ wrapper** | Native speed | Requires maintaining C++ port | ❌ Not viable |

### Design Philosophy

pyccwebgraph prioritizes **developer experience** and **ecosystem compatibility** over raw performance. By using Py4J and Python 3, we enable researchers to use the full Python data science stack (pandas, NetworkX, scikit-learn, etc.) with minimal friction.

For maximum performance on full-graph operations, researchers should use **cc-webgraph's Java tools directly**. For interactive discovery and Python-based analysis, pyccwebgraph provides the best balance of speed and usability.

---