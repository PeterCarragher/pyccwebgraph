"""
Setup utilities for pyccwebgraph.

Handles Java version checking, JAR detection, path resolution,
and environment validation.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple


DEFAULT_DATA_DIR = os.path.join(str(Path.home()), ".pyccwebgraph", "data")
DEFAULT_VERSION = "cc-main-2024-feb-apr-may"


def check_java(min_version: int = 17) -> Tuple[bool, str]:
    """
    Check if Java is installed and meets the minimum version requirement.

    Args:
        min_version: Minimum Java version required (default: 17)

    Returns:
        Tuple of (meets_requirement, version_string_or_error_message)
    """
    java_bin = shutil.which("java")
    if java_bin is None:
        return False, (
            "Java not found. Please install Java 17+:\n"
            "  Ubuntu/Debian: sudo apt install openjdk-17-jdk\n"
            "  macOS:         brew install openjdk@17\n"
            "  Windows:       https://adoptium.net/"
        )

    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Java version is printed to stderr
        output = result.stderr + result.stdout
        match = re.search(r'"(\d+)[\.\d]*"', output)
        if match:
            major = int(match.group(1))
            if major >= min_version:
                return True, f"Java {major}"
            else:
                return False, (
                    f"Java {major} found, but Java {min_version}+ is required.\n"
                    f"Please upgrade your Java installation."
                )
        return False, f"Could not parse Java version from: {output.strip()}"
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"Error checking Java version: {e}"


def find_jar(jar_path: Optional[str] = None) -> str:
    """
    Locate the cc-webgraph JAR file.

    Search order:
    1. Explicit jar_path argument
    2. CC_WEBGRAPH_JAR environment variable
    3. Bundled JAR in package jars/ directory
    4. Common build locations (cc-webgraph/target/)

    Args:
        jar_path: Explicit path to JAR file, or None for auto-detection.

    Returns:
        Path to the JAR file.

    Raises:
        FileNotFoundError: If no JAR can be found.
    """
    # 1. Explicit path
    if jar_path is not None:
        if os.path.exists(jar_path):
            return jar_path
        raise FileNotFoundError(f"JAR not found at specified path: {jar_path}")

    # 2. Environment variable
    env_jar = os.environ.get("CC_WEBGRAPH_JAR")
    if env_jar and os.path.exists(env_jar):
        return env_jar

    # 3. Bundled JAR in package
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    bundled = os.path.join(pkg_dir, "jars",
                           "cc-webgraph-0.1-SNAPSHOT-jar-with-dependencies.jar")
    if os.path.exists(bundled):
        return bundled

    # 4. Common build locations
    jar_name = "cc-webgraph-0.1-SNAPSHOT-jar-with-dependencies.jar"
    search_dirs = [
        # Docker / deployed
        "/app/cc-webgraph.jar",
        # Colab
        "/content/cc-webgraph/target",
        # Relative to CWD
        os.path.join(os.getcwd(), "cc-webgraph", "target"),
        # Parent of CWD
        os.path.join(os.path.dirname(os.getcwd()), "cc-webgraph", "target"),
    ]

    for path in search_dirs:
        if os.path.isfile(path):
            return path
        candidate = os.path.join(path, jar_name)
        if os.path.exists(candidate):
            return candidate

    raise FileNotFoundError(
        "cc-webgraph JAR not found. Options:\n"
        "  1. Set CC_WEBGRAPH_JAR environment variable\n"
        "  2. Pass jar_path to CCWebgraph.setup()\n"
        "  3. Place JAR in package jars/ directory\n"
        "  4. Build from source: git clone https://github.com/commoncrawl/cc-webgraph && "
        "cd cc-webgraph && mvn package -DskipTests"
    )


def check_webgraph_data(webgraph_dir: str, version: str) -> Tuple[bool, list]:
    """
    Check if required webgraph data files exist.

    Args:
        webgraph_dir: Directory containing webgraph files.
        version: Webgraph version string.

    Returns:
        Tuple of (all_present, list_of_missing_files)
    """
    required = get_required_files(version)
    missing = []
    for f in required:
        if not os.path.exists(os.path.join(webgraph_dir, f)):
            missing.append(f)
    return len(missing) == 0, missing


def get_required_files(version: str) -> list:
    """Return list of files required for a given webgraph version."""
    return [
        f"{version}-domain-vertices.txt.gz",
        f"{version}-domain.graph",
        f"{version}-domain.properties",
        f"{version}-domain-t.graph",
        f"{version}-domain-t.properties",
        f"{version}-domain.stats",
    ]


def check_offsets(webgraph_dir: str, version: str) -> Tuple[bool, list]:
    """Check if offset files have been built."""
    offsets = [
        f"{version}-domain.offsets",
        f"{version}-domain-t.offsets",
    ]
    missing = []
    for f in offsets:
        if not os.path.exists(os.path.join(webgraph_dir, f)):
            missing.append(f)
    return len(missing) == 0, missing


def check_ram(min_gb: int = 20) -> bool:
    """Check if sufficient RAM is available."""
    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        return ram_gb >= min_gb
    except ImportError:
        # Can't check without psutil, assume OK
        return True
