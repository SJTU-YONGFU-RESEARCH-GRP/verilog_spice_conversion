"""Synthesis module for converting RTL to gate-level netlist using Yosys."""

from __future__ import annotations

import json
import logging
import subprocess  # nosec B404
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class Netlist:
    """Gate-level netlist representation.

    Attributes:
        modules: Dictionary of modules in the netlist
        top_module: Name of the top-level module
        json_data: Raw Yosys JSON data
    """

    def __init__(
        self,
        modules: Optional[Dict[str, Any]] = None,
        top_module: Optional[str] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize Netlist.

        Args:
            modules: Dictionary of modules
            top_module: Top-level module name
            json_data: Raw Yosys JSON data
        """
        self.modules = modules or {}
        self.top_module = top_module
        self.json_data = json_data or {}


def check_yosys() -> bool:
    """Check if Yosys is available.

    Returns:
        True if Yosys is available, False otherwise
    """
    try:
        result = subprocess.run(  # nosec B603, B607
            ["yosys", "-V"],
            capture_output=True,
            check=False,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def synthesize(
    verilog_files: List[str],
    top_module: str,
    script: Optional[str] = None,
    optimize: bool = True,
    output_dir: Optional[str] = None,
    include_paths: Optional[List[str]] = None,
    defines: Optional[Dict[str, str]] = None,
) -> Netlist:
    """Synthesize Verilog RTL to gate-level netlist using Yosys.

    Args:
        verilog_files: List of Verilog file paths
        top_module: Top-level module name
        script: Optional custom Yosys synthesis script path
        optimize: Whether to enable optimization
        output_dir: Optional output directory for temporary files
        include_paths: Optional list of include paths
        defines: Optional dictionary of preprocessor defines

    Returns:
        Netlist object containing gate-level representation

    Raises:
        RuntimeError: If synthesis fails or Yosys is not available
    """
    logger.info(f"Synthesizing design with top module: {top_module}")

    # Check if Yosys is available
    if not check_yosys():
        raise RuntimeError(
            "Yosys is required but not found. "
            "Please install Yosys: sudo apt-get install yosys (Linux) or brew install yosys (macOS)"
        )

    # Use custom script or default
    if script and Path(script).exists():
        script_path = script
        logger.info(f"Using custom synthesis script: {script_path}")
        # Extract output path from script or use default
        if output_dir:
            netlist_path = Path(output_dir) / "netlist.json"
        else:
            netlist_path = Path(tempfile.gettempdir()) / "netlist.json"
    else:
        script_path, netlist_path = create_default_synthesis_script(
            verilog_files,
            top_module,
            optimize,
            output_dir,
            include_paths,
            defines,
        )

    # Run Yosys
    try:
        run_yosys(script_path)

        # Read and parse JSON output
        if not netlist_path.exists():
            raise RuntimeError(f"Yosys JSON output file not found: {netlist_path}")

        with open(netlist_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)

        netlist = parse_yosys_json(json_data, top_module)
        logger.info("Synthesis completed successfully")
        return netlist

    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
    ) as e:
        logger.error(f"Synthesis failed: {e}")
        raise RuntimeError(f"Synthesis failed: {e}") from e


def create_default_synthesis_script(
    verilog_files: List[str],
    top_module: str,
    optimize: bool,
    output_dir: Optional[str],
    include_paths: Optional[List[str]] = None,
    defines: Optional[Dict[str, str]] = None,
) -> tuple[str, Path]:
    """Create a default Yosys synthesis script.

    Args:
        verilog_files: List of Verilog file paths
        top_module: Top-level module name
        optimize: Whether to enable optimization
        output_dir: Optional output directory
        include_paths: Optional list of include paths
        defines: Optional dictionary of preprocessor defines

    Returns:
        Tuple of (script_path, netlist_json_path)
    """
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = Path(tempfile.gettempdir())

    script_path = output_path / "synthesis.ys"
    netlist_path = output_path / "netlist.json"

    # Build read_verilog command with includes and defines
    read_cmd_parts = ["read_verilog"]

    # Add include paths
    if include_paths:
        for inc_path in include_paths:
            read_cmd_parts.append(f"-I{inc_path}")

    # Add defines
    if defines:
        for name, value in defines.items():
            read_cmd_parts.append(f"-D{name}={value}")

    # Add Verilog files
    read_cmd_parts.extend(verilog_files)
    read_cmd = " ".join(read_cmd_parts)

    # Build optimization commands
    opt_cmds = ""
    if optimize:
        opt_cmds = """
proc; opt; fsm; opt; memory; opt
techmap; opt
"""

    script_content = f"""# Yosys synthesis script
{read_cmd}
hierarchy -check -top {top_module}
{opt_cmds}
write_json "{netlist_path}"
"""

    script_path.write_text(script_content)
    logger.debug(f"Created synthesis script: {script_path}")

    return str(script_path), netlist_path


def run_yosys(script_path: str) -> None:
    """Run Yosys with the given script.

    Args:
        script_path: Path to Yosys script

    Raises:
        RuntimeError: If Yosys execution fails
    """
    logger.debug(f"Running Yosys with script: {script_path}")

    try:
        result = subprocess.run(  # nosec B603, B607
            ["yosys", "-s", script_path],
            capture_output=True,
            text=True,
            check=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            raise RuntimeError(f"Yosys failed: {result.stderr}")

        logger.debug("Yosys execution completed")
        if result.stderr:
            logger.debug(f"Yosys warnings: {result.stderr}")

    except subprocess.TimeoutExpired:
        raise RuntimeError("Yosys execution timed out")
    except FileNotFoundError:
        raise RuntimeError("Yosys not found in PATH")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Yosys execution failed: {e.stderr}")


def parse_yosys_json(json_data: Dict[str, Any], top_module: str) -> Netlist:
    """Parse Yosys JSON output into Netlist object.

    Args:
        json_data: Yosys JSON data structure
        top_module: Top-level module name

    Returns:
        Netlist object
    """
    logger.debug("Parsing Yosys JSON output")

    modules = json_data.get("modules", {})

    # Find the actual top module name (may have escaped backslash)
    actual_top = None
    for mod_name in modules.keys():
        if mod_name.lstrip("\\") == top_module or mod_name == top_module:
            actual_top = mod_name
            break

    if not actual_top:
        # Use first module if top not found
        actual_top = list(modules.keys())[0] if modules else top_module
        logger.warning(
            f"Top module '{top_module}' not found in JSON, using '{actual_top}'"
        )

    return Netlist(
        modules=modules,
        top_module=actual_top,
        json_data=json_data,
    )
