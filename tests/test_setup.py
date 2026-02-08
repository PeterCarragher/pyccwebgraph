"""Tests for setup utilities."""

import os
import pytest
from pyccwebgraph.setup_utils import (
    check_java,
    check_webgraph_data,
    get_required_files,
    check_offsets,
    DEFAULT_VERSION,
)


class TestCheckJava:
    def test_returns_tuple(self):
        ok, msg = check_java()
        assert isinstance(ok, bool)
        assert isinstance(msg, str)

    def test_high_version_fails(self):
        ok, msg = check_java(min_version=999)
        assert not ok


class TestGetRequiredFiles:
    def test_file_count(self):
        files = get_required_files("cc-main-2024-feb-apr-may")
        assert len(files) == 6

    def test_version_in_filenames(self):
        version = "cc-main-2024-feb-apr-may"
        files = get_required_files(version)
        for f in files:
            assert f.startswith(version)


class TestCheckWebgraphData:
    def test_missing_dir(self, tmp_path):
        ok, missing = check_webgraph_data(str(tmp_path), DEFAULT_VERSION)
        assert not ok
        assert len(missing) == 6

    def test_all_present(self, tmp_path):
        version = DEFAULT_VERSION
        for f in get_required_files(version):
            (tmp_path / f).touch()
        ok, missing = check_webgraph_data(str(tmp_path), version)
        assert ok
        assert missing == []


class TestCheckOffsets:
    def test_missing(self, tmp_path):
        ok, missing = check_offsets(str(tmp_path), DEFAULT_VERSION)
        assert not ok
        assert len(missing) == 2

    def test_present(self, tmp_path):
        version = DEFAULT_VERSION
        (tmp_path / f"{version}-domain.offsets").touch()
        (tmp_path / f"{version}-domain-t.offsets").touch()
        ok, missing = check_offsets(str(tmp_path), version)
        assert ok
