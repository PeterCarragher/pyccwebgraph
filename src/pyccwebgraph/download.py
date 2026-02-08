"""
Download utilities for CommonCrawl webgraph data.

Handles downloading graph files, building offset files,
and listing available webgraph versions.
"""

import os
import subprocess
import urllib.request
from typing import List, Optional

from .setup_utils import get_required_files, find_jar

try:
    from tqdm.auto import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


# Known webgraph versions (newest first)
KNOWN_VERSIONS = [
    "cc-main-2024-nov-dec-jan",
    "cc-main-2024-feb-apr-may",
    "cc-main-2023-nov-dec-jan",
    "cc-main-2023-may-jun-jul",
    "cc-main-2022-nov-dec-jan",
]


def get_available_versions() -> List[str]:
    """
    Return list of known CommonCrawl webgraph versions (newest first).

    Returns:
        List of version strings.
    """
    return list(KNOWN_VERSIONS)


def download_with_progress(url: str, dest_path: str) -> None:
    """Download a file with progress bar if tqdm is available."""
    if os.path.exists(dest_path):
        size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        print(f"  Already exists: {os.path.basename(dest_path)} ({size_mb:.1f} MB)")
        return

    print(f"  Downloading: {os.path.basename(dest_path)}")

    if HAS_TQDM:
        def progress_hook(pbar):
            def update(_, block_size, total_size):
                if total_size > 0:
                    pbar.total = total_size
                    pbar.update(block_size)
            return update

        with tqdm(unit="B", unit_scale=True, unit_divisor=1024) as pbar:
            urllib.request.urlretrieve(url, dest_path,
                                       reporthook=progress_hook(pbar))
    else:
        urllib.request.urlretrieve(url, dest_path)

    print(f"  Downloaded: {os.path.basename(dest_path)}")


def build_offsets(
    webgraph_dir: str,
    version: str,
    jar_path: Optional[str] = None,
) -> None:
    """
    Build .offsets files required by WebGraph for random access.

    Args:
        webgraph_dir: Directory containing the graph files.
        version: Webgraph version string.
        jar_path: Path to cc-webgraph JAR. If None, auto-detects.
    """
    if jar_path is None:
        jar_path = find_jar()

    graphs = [
        f"{version}-domain",
        f"{version}-domain-t",
    ]

    for graph_name in graphs:
        graph_base = os.path.join(webgraph_dir, graph_name)
        offsets_file = f"{graph_base}.offsets"

        if os.path.exists(offsets_file):
            print(f"  Offsets already exist: {graph_name}.offsets")
            continue

        print(f"  Building offsets for {graph_name}...")

        cmd = [
            "java",
            "-cp", jar_path,
            "it.unimi.dsi.webgraph.BVGraph",
            "-O",
            "-L",
            graph_base,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                stderr = result.stderr.strip()
                raise RuntimeError(
                    f"Failed to build offsets for {graph_name}: {stderr}"
                )

            if os.path.exists(offsets_file):
                print(f"  Built {graph_name}.offsets")
            else:
                print(f"  Warning: command succeeded but {graph_name}.offsets not found")

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Timeout building offsets for {graph_name}")


def download_webgraph(
    webgraph_dir: str,
    version: str,
    jar_path: Optional[str] = None,
) -> None:
    """
    Download CommonCrawl webgraph files and build offsets.

    Args:
        webgraph_dir: Directory to download files to.
        version: Webgraph version string.
        jar_path: Path to cc-webgraph JAR for building offsets.
    """
    base_url = (
        f"https://data.commoncrawl.org/projects/hyperlinkgraph/{version}/domain"
    )
    files = get_required_files(version)

    os.makedirs(webgraph_dir, exist_ok=True)

    print(f"Downloading CommonCrawl webgraph: {version}")
    print(f"Destination: {webgraph_dir}")
    print("=" * 60)

    for filename in files:
        url = f"{base_url}/{filename}"
        dest = os.path.join(webgraph_dir, filename)
        download_with_progress(url, dest)

    print("=" * 60)
    print("All graph files downloaded!")

    print("\nBuilding offset files (required for graph queries)...")
    build_offsets(webgraph_dir, version, jar_path)

    print("\nWebgraph ready for use!")
