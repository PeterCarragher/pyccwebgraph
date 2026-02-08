# pyccwebgraph: Python Interface to CommonCrawl Webgraph

[![PyPI version](https://badge.fury.io/py/pyccwebgraph.svg)](https://pypi.org/project/pyccwebgraph/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Discover related domains using link topology from CommonCrawl's webgraph.

### Installation

**Prerequisites:**
- Python 3.8+
- Java 17+ ([install instructions](https://www.java.com/en/download/help/linux_install.html))
- ~30GB disk space for webgraph data

```bash
pip install pyccwebgraph
```

**First use downloads graph data:**
```python
from pyccwebgraph import CCWebgraph, get_available_versions

# List available versions
versions = get_available_versions()
print(versions[:3])  # ['cc-main-2024-nov-dec-jan', 'cc-main-2024-feb-apr-may', ...]

webgraph = CCWebgraph.setup(
    webgraph_dir="/data/my-webgraph",
    version="cc-main-2024-feb-apr-may"
)

# Find domains that link TO seeds (backlinks)
results = webgraph.discover_backlinks(
    seeds=["cnn.com", "bbc.com", "nytimes.com"],
    min_connections=3  # Must link to all seeds
)

print(f"Found {len(results['nodes'])} domains")
print(f"Top result: {results['nodes'][0]}")
# {'domain': 'news-aggregator.com', 'connections': 15, 'percentage': 50.0}
```

### Working with NetworkX

```python
# Get results as NetworkX graph
G = webgraph.discover_backlinks(
    seeds=["cnn.com", "bbc.com"],
    min_connections=2,
    format='networkx'  # Returns nx.DiGraph
)

# Run standard NetworkX algorithms
import networkx as nx

# Centrality analysis
pr = nx.pagerank(G)
bc = nx.betweenness_centrality(G)

# Community detection
from cdlib import algorithms
communities = algorithms.louvain(G)

# Visualization
from pyvis.network import Network
net = Network(notebook=True)
net.from_nx(G)
net.show("network.html")
```

### Performance: Large Graphs with NetworKit

For large discovered subgraphs (>100K nodes), use NetworKit instead of NetworkX:

```python
# Discover large subgraph
G_nk, name_map = webgraph.discover_backlinks(
    seeds=seed_list,
    min_connections=2,
    format='networkit'  # Returns NetworKit graph
)
```

### CC-Webgraph mapping

```python
# Check if domain exists in graph
vid = webgraph.domain_to_id("example.com")
if vid is not None:
    print(f"Found at vertex ID {vid}")

# Get all domains this domain links to
outlinks = webgraph.get_successors("cnn.com")
print(f"CNN links to {len(outlinks)} domains")

# Get all domains linking to this domain  
backlinks = webgraph.get_predecessors("cnn.com")
print(f"{len(backlinks)} domains link to CNN")

# Validate seeds before discovery
found, missing = webgraph.validate_seeds(["cnn.com", "fake-site.xyz"])
print(f"Found: {found}")
print(f"Missing: {missing}")
```

---

## Links

- **Interactive demo:** https://github.com/PeterCarragher/NetNeighbors
- **PyPI:** https://pypi.org/project/pyccwebgraph/
- **Documentation:** https://pyccwebgraph.readthedocs.io/
- **Research Papers for webgraph-based discovery:** 
  - [ACM TIST 2025](https://dl.acm.org/doi/pdf/10.1145/3670410)
  - [ICWSM 2024](https://arxiv.org/abs/2401.02379)
- **CommonCrawl Webgraphs:** https://commoncrawl.org/web-graphs
- **cc-webgraph:** https://github.com/commoncrawl/cc-webgraph

