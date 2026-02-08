"""Tests for graph format converters."""

import pytest
from pyccwebgraph.converters import DiscoveryResult, to_networkx


@pytest.fixture
def sample_result():
    nodes = [
        {"domain": "news-agg.com", "connections": 3, "percentage": 100.0},
        {"domain": "blog-site.org", "connections": 2, "percentage": 66.67},
    ]
    edges = [
        ("news-agg.com", "cnn.com"),
        ("news-agg.com", "bbc.com"),
        ("news-agg.com", "nyt.com"),
        ("blog-site.org", "cnn.com"),
        ("blog-site.org", "bbc.com"),
    ]
    seeds = ["cnn.com", "bbc.com", "nyt.com"]
    return DiscoveryResult(nodes=nodes, edges=edges, seeds=seeds)


class TestDiscoveryResult:
    def test_dict_access(self, sample_result):
        assert len(sample_result["nodes"]) == 2
        assert len(sample_result["edges"]) == 5
        assert sample_result["seeds"] == ["cnn.com", "bbc.com", "nyt.com"]

    def test_len(self, sample_result):
        assert len(sample_result) == 2

    def test_repr(self, sample_result):
        r = repr(sample_result)
        assert "2 nodes" in r
        assert "5 edges" in r

    def test_invalid_key(self, sample_result):
        with pytest.raises(KeyError):
            sample_result["invalid"]

    def test_empty_result(self):
        result = DiscoveryResult(nodes=[], edges=[], seeds=[])
        assert len(result) == 0
        assert result["nodes"] == []


class TestNetworkXConverter:
    def test_basic_conversion(self, sample_result):
        nx = pytest.importorskip("networkx")
        G = sample_result.networkx()
        assert isinstance(G, nx.DiGraph)
        # 2 discovered + 3 seeds = 5 nodes
        assert G.number_of_nodes() == 5
        assert G.number_of_edges() == 5

    def test_seed_attributes(self, sample_result):
        pytest.importorskip("networkx")
        G = sample_result.networkx()
        assert G.nodes["cnn.com"]["is_seed"] is True
        assert G.nodes["news-agg.com"]["is_seed"] is False

    def test_node_attributes(self, sample_result):
        pytest.importorskip("networkx")
        G = sample_result.networkx()
        assert G.nodes["news-agg.com"]["connections"] == 3

    def test_standalone_function(self, sample_result):
        nx = pytest.importorskip("networkx")
        G = to_networkx(
            sample_result.nodes, sample_result.edges, sample_result.seeds
        )
        assert isinstance(G, nx.DiGraph)
        assert G.number_of_nodes() == 5


class TestDataFrameConverter:
    def test_to_dataframe(self, sample_result):
        pd = pytest.importorskip("pandas")
        df = sample_result.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["domain", "connections", "percentage"]
        assert len(df) == 2
