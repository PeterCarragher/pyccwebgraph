"""Tests for CCWebgraph class.

Note: Full integration tests require a running JVM with webgraph data.
These tests cover initialization logic and error handling.
"""

import pytest
from unittest.mock import patch, MagicMock
from pyccwebgraph.ccwebgraph import CCWebgraph


class TestCCWebgraphInit:
    def test_missing_py4j_raises(self):
        with patch("pyccwebgraph.ccwebgraph.HAS_PY4J", False):
            with pytest.raises(ImportError, match="py4j"):
                CCWebgraph("/tmp/data", jar_path="/fake/jar")

    def test_init_sets_attributes(self, tmp_path):
        jar = tmp_path / "test.jar"
        jar.touch()
        with patch("pyccwebgraph.ccwebgraph.find_jar", return_value=str(jar)):
            wg = CCWebgraph(str(tmp_path), version="test-version")
        assert wg.webgraph_dir == str(tmp_path)
        assert wg.version == "test-version"
        assert wg.graph is None

    def test_ensure_loaded_raises(self, tmp_path):
        jar = tmp_path / "test.jar"
        jar.touch()
        with patch("pyccwebgraph.ccwebgraph.find_jar", return_value=str(jar)):
            wg = CCWebgraph(str(tmp_path))
        with pytest.raises(RuntimeError, match="not loaded"):
            wg._ensure_loaded()


class TestSetupClassmethod:
    def test_no_java_raises(self):
        with patch(
            "pyccwebgraph.ccwebgraph.check_java",
            return_value=(False, "Java not found"),
        ):
            with pytest.raises(RuntimeError, match="Java not found"):
                CCWebgraph.setup(webgraph_dir="/tmp", auto_download=False)

    def test_missing_data_no_download_raises(self, tmp_path):
        with patch(
            "pyccwebgraph.ccwebgraph.check_java",
            return_value=(True, "Java 17"),
        ), patch(
            "pyccwebgraph.ccwebgraph.find_jar",
            return_value="/fake/jar",
        ):
            with pytest.raises(FileNotFoundError, match="missing"):
                CCWebgraph.setup(
                    webgraph_dir=str(tmp_path), auto_download=False
                )
