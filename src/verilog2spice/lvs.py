"""LVS verification module using Netgen for netlist comparison."""

from __future__ import annotations

import logging
import os
import re
import subprocess  # nosec B404
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def extract_spice_statistics(spice_file: Path) -> dict[str, int | dict[str, int]]:
    """Extract statistics from a SPICE netlist file.

    Args:
        spice_file: Path to SPICE netlist file

    Returns:
        Dictionary containing statistics about the netlist
    """
    stats: dict[str, int | dict[str, int]] = {
        "file_size_bytes": 0,
        "total_lines": 0,
        "subcircuit_definitions": 0,
        "subcircuit_instances": 0,
        "mosfet_instances": 0,
        "unique_cell_types": {},
        "comment_lines": 0,
        "model_definitions": 0,
        "total_netlist_lines": 0,
    }

    if not spice_file.exists():
        return stats

    try:
        content = spice_file.read_text(encoding="utf-8")
        stats["file_size_bytes"] = len(content)
        lines = content.split("\n")
        stats["total_lines"] = len(lines)

        # Count subcircuit definitions (.SUBCKT)
        subcircuit_pattern = re.compile(
            r"^\.SUBCKT\s+\w+", re.IGNORECASE | re.MULTILINE
        )
        stats["subcircuit_definitions"] = len(subcircuit_pattern.findall(content))

        # Count subcircuit instances (lines starting with X, ignoring comments)
        # Extract cell types from instances - cell type is the last token on the line
        instance_pattern = re.compile(
            r"^\s*X[^\s]+\s+(.+)$", re.IGNORECASE | re.MULTILINE
        )
        instance_lines = instance_pattern.findall(content)
        stats["subcircuit_instances"] = len(instance_lines)

        # Extract cell types - the last token in each instance line is the cell type
        cell_types_list = []
        for instance_line in instance_lines:
            parts = instance_line.strip().split()
            if parts:  # If there are tokens, the last one is the cell type
                cell_types_list.append(parts[-1])
        stats["unique_cell_types"] = dict(Counter(cell_types_list))

        # Count MOSFET instances (lines starting with M, ignoring comments)
        mosfet_pattern = re.compile(r"^\s*M\d+\s+", re.IGNORECASE | re.MULTILINE)
        stats["mosfet_instances"] = len(mosfet_pattern.findall(content))

        # Count comment lines
        stats["comment_lines"] = sum(
            1 for line in lines if line.strip().startswith("*")
        )

        # Count model definitions
        model_pattern = re.compile(r"^\.MODEL\s+", re.IGNORECASE | re.MULTILINE)
        stats["model_definitions"] = len(model_pattern.findall(content))

        # Count actual netlist lines (non-comment, non-empty)
        stats["total_netlist_lines"] = sum(
            1
            for line in lines
            if line.strip()
            and not line.strip().startswith("*")
            and not line.strip().startswith(".")
        )

    except (OSError, IOError, UnicodeDecodeError) as e:
        logger.debug(f"Error extracting statistics from {spice_file}: {e}")

    return stats


class LVSResult:
    """LVS comparison result.

    Attributes:
        matched: True if netlists match, False otherwise
        output: Netgen output text
        errors: List of error messages
        warnings: List of warning messages
    """

    def __init__(
        self,
        matched: bool,
        output: str = "",
        errors: Optional[list[str]] = None,
        warnings: Optional[list[str]] = None,
    ) -> None:
        """Initialize LVSResult.

        Args:
            matched: True if netlists match
            output: Netgen output text
            errors: List of error messages
            warnings: List of warning messages
        """
        self.matched = matched
        self.output = output
        self.errors = errors or []
        self.warnings = warnings or []


def check_netgen() -> bool:
    """Check if Netgen LVS tool is available in PATH.

    Note: There are two different tools named "netgen":
    1. Netgen mesh generator (often installed by default) - NOT what we need
    2. Netgen LVS tool (part of Magic VLSI) - This is what we need

    Returns:
        True if Netgen LVS tool is found, False otherwise
    """
    try:
        # First try netgen-lvs (the actual LVS tool)
        # Note: netgen-lvs doesn't support -help, but we can check if it exists
        # Use -batch mode only (no -noconsole flag for version 1.5.133)
        result = subprocess.run(  # nosec B603, B607
            ["netgen-lvs", "-batch"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            input="exit\n",
        )
        output = (result.stdout + result.stderr).lower()
        # Netgen LVS shows "Running NetGen Console" or version info
        if "netgen" in output and (
            "console" in output or "1.5" in output or "lvs" in output
        ):
            return True
        # Also check if command exists (even if it fails, if it's netgen-lvs it's the right tool)
        if "invalid command" in output or "netgen" in output:
            return True

        # Try regular netgen - but check if it's the LVS tool, not mesh generator
        result = subprocess.run(  # nosec B603, B607
            ["netgen", "-batch", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        output = (result.stdout + result.stderr).lower()
        # Mesh generator mentions "Vienna University" or "mesh"
        # LVS tool would mention "magic" or "lvs" or have different output
        if "vienna" in output or "mesh" in output:
            logger.warning(
                "Found Netgen mesh generator, but Netgen LVS tool is required for netlist comparison"
            )
            return False
        if result.returncode == 0 or "netgen" in output:
            return True

        # Try alternative command
        result = subprocess.run(  # nosec B603, B607
            ["netgen", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def verify_spice_vs_spice(
    spice_file1: str | Path,
    spice_file2: str | Path,
    tolerance: float = 0.01,
    netgen_timeout: int = 120,
    report_file: Optional[str | Path] = None,
) -> LVSResult:
    """Compare two SPICE netlists using Netgen.

    Args:
        spice_file1: Path to first SPICE netlist
        spice_file2: Path to second SPICE netlist
        tolerance: Matching tolerance for comparison (not always used by Netgen)
        netgen_timeout: Timeout in seconds for Netgen execution
        report_file: Optional path to save detailed LVS report

    Returns:
        LVSResult object with comparison results

    Raises:
        FileNotFoundError: If Netgen is not found
        ValueError: If netlist files don't exist
    """
    if not check_netgen():
        raise FileNotFoundError(
            "Netgen not found - LVS verification requires Netgen. "
            "Install with: apt-get install netgen (Linux) or brew install netgen (macOS)"
        )

    spice_path1 = Path(spice_file1)
    spice_path2 = Path(spice_file2)

    if not spice_path1.exists():
        raise ValueError(f"SPICE netlist not found: {spice_file1}")
    if not spice_path2.exists():
        raise ValueError(f"SPICE netlist not found: {spice_file2}")

    logger.info(f"Comparing SPICE netlists: {spice_path1.name} vs {spice_path2.name}")

    # Create Netgen TCL script for LVS comparison
    # Note: Netgen LVS command syntax: lvs "file1" "file2" "output"
    # The output file will contain detailed comparison results
    lvs_output_file_path = str(spice_path1) + ".lvs"
    script_content = f"""# Netgen LVS comparison script
# Generated automatically for netlist verification

# Read and compare netlists
puts "=== Starting LVS Comparison ==="
puts "File 1: {spice_path1}"
puts "File 2: {spice_path2}"
puts "Output file: {lvs_output_file_path}"

# Run LVS comparison
# The lvs command loads both netlists and sets up the comparison
lvs "{spice_path1}" "{spice_path2}" "{lvs_output_file_path}"

# Run the actual comparison
puts "Running LVS comparison..."
run

puts "=== LVS Comparison Complete ==="
puts "Results written to: {lvs_output_file_path}"
exit
"""

    # Write temporary script
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".tcl",
        prefix="netgen_lvs_",
        delete=False,
    ) as script_file:
        script_file.write(script_content)
        script_path = Path(script_file.name)

    try:
        # Run Netgen in batch mode
        # Create a clean environment without NETGENDIR to avoid GUI library issues
        env = os.environ.copy()
        env.pop("NETGENDIR", None)  # Remove NETGENDIR if set

        logger.debug(f"Running Netgen with script: {script_path}")
        # Try netgen-lvs first (if available), otherwise fall back to netgen
        netgen_cmd = "netgen-lvs"
        try:
            # Test if netgen-lvs exists (it doesn't support -help, so just check if command exists)
            test_result = subprocess.run(  # nosec B603, B607
                ["which", netgen_cmd], capture_output=True, check=False, timeout=5
            )
            if test_result.returncode != 0:
                netgen_cmd = (
                    "netgen"  # Fall back to regular netgen (might be mesh generator)
                )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            netgen_cmd = "netgen"  # Fall back to regular netgen

        # Run Netgen LVS in batch mode
        # Note: Netgen LVS 1.5.133 doesn't support -source flag
        # Instead, we pass the script content via stdin
        with open(script_path, "r", encoding="utf-8") as script_file:
            script_content_input = script_file.read()

        result = subprocess.run(  # nosec B603
            [netgen_cmd, "-batch"],
            input=script_content_input,
            capture_output=True,
            text=True,
            timeout=netgen_timeout,
            cwd=spice_path1.parent,
            env=env,
        )

        # Check if we got the mesh generator error
        output_check = (result.stdout + result.stderr).lower()
        if "libgui.so" in output_check or "vienna" in output_check:
            logger.warning(
                "Netgen mesh generator detected instead of Netgen LVS tool. "
                "LVS verification requires Netgen LVS (install with: apt-get install netgen-lvs)."
            )

        output = result.stdout + result.stderr

        # Log the full output for debugging
        logger.debug(f"Netgen return code: {result.returncode}")
        logger.debug(f"Netgen stdout length: {len(result.stdout)} characters")
        logger.debug(f"Netgen stderr length: {len(result.stderr)} characters")
        if len(output) > 500:
            logger.debug(f"Netgen output (first 500 chars): {output[:500]}")
        else:
            logger.debug(f"Netgen full output: {output}")

        # Parse Netgen LVS output for comparison results
        # Netgen LVS typically outputs results in the .lvs file and/or to stdout
        # Look for success/failure indicators in the output

        # Parse output for match/mismatch
        # Netgen typically outputs "Netlists match" or "Netlists are equivalent" on success
        # And "Netlists do not match" or error messages on failure
        output_lower = output.lower()
        matched = (
            "netlists match" in output_lower
            or "netlists are equivalent" in output_lower
            or "comparison successful" in output_lower
            or (
                result.returncode == 0
                and "error" not in output_lower
                and "failed" not in output_lower
            )
        )

        # Extract errors and warnings
        errors: list[str] = []
        warnings: list[str] = []

        # Filter out benign Netgen warnings that don't affect functionality
        benign_warnings = [
            "netgen command 'global' use fully-qualified name",
            "use fully-qualified name '::netgen::global'",
        ]

        lines = output.split("\n")
        for line in lines:
            line_lower = line.lower()
            line_stripped = line.strip()
            if not line_stripped:
                continue
            if "error" in line_lower:
                errors.append(line_stripped)
            elif "warning" in line_lower:
                # Filter out benign warnings
                is_benign = any(bw.lower() in line_lower for bw in benign_warnings)
                if not is_benign:
                    warnings.append(line_stripped)
            elif "mismatch" in line_lower or "failed" in line_lower:
                if (
                    "netlists do not match" in line_lower
                    or "comparison failed" in line_lower
                ):
                    errors.append(line_stripped)

        # Check for Netgen LVS output file (.lvs file) which contains detailed comparison results
        # The script creates output as "{spice_path1}.lvs", so we append .lvs to the full path
        lvs_output_file = Path(str(spice_path1) + ".lvs")
        lvs_output_content = ""
        lvs_statistics = ""

        logger.debug(f"Checking for LVS output file: {lvs_output_file}")
        logger.debug(f"LVS output file exists: {lvs_output_file.exists()}")

        if lvs_output_file.exists():
            try:
                lvs_output_content = lvs_output_file.read_text(encoding="utf-8")
                # Check the .lvs file for match indicators
                lvs_content_lower = lvs_output_content.lower()

                # Extract key statistics and information from the .lvs file
                lines = lvs_output_content.split("\n")
                stats_lines = []
                keywords = [
                    "device",
                    "node",
                    "net",
                    "subcircuit",
                    "match",
                    "equivalent",
                    "mismatch",
                    "circuit",
                    "result",
                    "comparison",
                    "summary",
                ]
                for i, line in enumerate(lines):
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    line_lower = line_stripped.lower()
                    # Look for key sections: device counts, node counts, match indicators, etc.
                    if any(keyword in line_lower for keyword in keywords):
                        stats_lines.append(line_stripped)
                        # Also include a few lines of context for important sections
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            if next_line and not next_line.startswith("#"):
                                stats_lines.append(next_line)

                if stats_lines:
                    lvs_statistics = "\n".join(
                        stats_lines[:100]
                    )  # Limit to first 100 lines of statistics

                # Check for match indicators in the .lvs file
                if "match" in lvs_content_lower or "equivalent" in lvs_content_lower:
                    # If stdout doesn't clearly indicate match, but .lvs file does, trust the file
                    if not matched and (
                        "match" in lvs_content_lower
                        or "equivalent" in lvs_content_lower
                    ):
                        matched = True
            except (OSError, IOError, UnicodeDecodeError) as e:
                logger.warning(f"Could not read LVS output file {lvs_output_file}: {e}")
        else:
            logger.debug(f"LVS output file not found: {lvs_output_file}")
            # If the .lvs file doesn't exist, Netgen might have put all output in stdout
            # In that case, use the stdout content as the detailed output
            if (
                output and len(output.strip()) > 50
            ):  # Only if there's substantial output
                logger.debug(
                    "Using Netgen stdout as detailed output (no .lvs file found)"
                )
                lvs_output_content = output

        # Extract statistics from both netlists
        stats1 = extract_spice_statistics(spice_path1)
        stats2 = extract_spice_statistics(spice_path2)

        if matched:
            logger.info("LVS comparison: Netlists match!")
        else:
            logger.warning("LVS comparison: Netlists do not match or comparison failed")
            if errors:
                logger.warning(f"Errors: {errors}")

        # Save report if requested
        if report_file:
            report_path = Path(report_file)
            report_path.parent.mkdir(parents=True, exist_ok=True)

            # Extract and type-narrow values before building report
            cell_types_1_raw = stats1.get("unique_cell_types", {})
            cell_types_1: dict[str, int] = (
                cell_types_1_raw if isinstance(cell_types_1_raw, dict) else {}
            )
            cell_types_2_raw = stats2.get("unique_cell_types", {})
            cell_types_2: dict[str, int] = (
                cell_types_2_raw if isinstance(cell_types_2_raw, dict) else {}
            )
            instances_1_raw = stats1.get("subcircuit_instances", 0)
            instances_1: int = instances_1_raw if isinstance(instances_1_raw, int) else 0
            instances_2_raw = stats2.get("subcircuit_instances", 0)
            instances_2: int = instances_2_raw if isinstance(instances_2_raw, int) else 0
            size_1_raw = stats1.get("file_size_bytes", 0)
            size_1: int = size_1_raw if isinstance(size_1_raw, int) else 0
            size_2_raw = stats2.get("file_size_bytes", 0)
            size_2: int = size_2_raw if isinstance(size_2_raw, int) else 0

            report_content = f"""LVS Comparison Report
{"=" * 80}
Generated: {spice_path1.name} vs {spice_path2.name}
Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Files Compared:
  File 1: {spice_path1}
  File 2: {spice_path2}

Result: {"MATCH" if matched else "MISMATCH"}
{"=" * 80}

Netlist Statistics:
{"=" * 80}
File 1 ({spice_path1.name}):
  File size: {stats1.get("file_size_bytes", 0):,} bytes
  Total lines: {stats1.get("total_lines", 0):,}
  Subcircuit definitions: {stats1.get("subcircuit_definitions", 0)}
  Subcircuit instances: {stats1.get("subcircuit_instances", 0)}
  MOSFET instances: {stats1.get("mosfet_instances", 0)}
  Model definitions: {stats1.get("model_definitions", 0)}
  Netlist lines: {stats1.get("total_netlist_lines", 0):,}
  Cell types: {len(cell_types_1)} unique types
  Cell type breakdown:
"""
            # Add cell type breakdown for file 1
            if cell_types_1:
                for cell_type, count in sorted(
                    cell_types_1.items(), key=lambda x: x[1], reverse=True
                ):
                    report_content += f"    {cell_type}: {count}\n"
            else:
                report_content += "    (none)\n"

            report_content += f"""
File 2 ({spice_path2.name}):
  File size: {stats2.get("file_size_bytes", 0):,} bytes
  Total lines: {stats2.get("total_lines", 0):,}
  Subcircuit definitions: {stats2.get("subcircuit_definitions", 0)}
  Subcircuit instances: {stats2.get("subcircuit_instances", 0)}
  MOSFET instances: {stats2.get("mosfet_instances", 0)}
  Model definitions: {stats2.get("model_definitions", 0)}
  Netlist lines: {stats2.get("total_netlist_lines", 0):,}
  Cell types: {len(cell_types_2)} unique types
  Cell type breakdown:
"""
            # Add cell type breakdown for file 2
            if cell_types_2:
                for cell_type, count in sorted(
                    cell_types_2.items(), key=lambda x: x[1], reverse=True
                ):
                    report_content += f"    {cell_type}: {count}\n"
            else:
                report_content += "    (none)\n"

            report_content += f"""
Comparison Summary:
  Instance count difference: {abs(instances_1 - instances_2)}
  File size difference: {abs(size_1 - size_2):,} bytes
  {"=" * 80}

Netgen Output (stdout/stderr):
{output if output.strip() else "(No output captured)"}
{"=" * 80}

Note: If the output above is minimal, Netgen may be writing detailed results to a file.
      Check the output directory for additional .lvs or .out files.
{"=" * 80}
"""
            # Include detailed output - either from .lvs file or from stdout
            if lvs_output_content:
                if lvs_output_file.exists():
                    # Content came from .lvs file
                    report_content += f"""
Detailed LVS Output File ({lvs_output_file.name}):
{"=" * 80}
{lvs_output_content}
{"=" * 80}

"""
                    # Also include a summary of key statistics if we extracted them
                    if lvs_statistics:
                        report_content += f"""
Key Statistics Summary (extracted from above):
{"=" * 80}
{lvs_statistics}
{"=" * 80}

"""
                else:
                    # Content came from stdout (no .lvs file was created)
                    report_content += f"""
Detailed Netgen Output (from stdout/stderr):
{"=" * 80}
{lvs_output_content}
{"=" * 80}

Note: Netgen did not create a separate .lvs output file. All output shown above.
{"=" * 80}

"""
            elif lvs_output_file.exists():
                report_content += f"""
Note: LVS output file exists ({lvs_output_file.name}) but could not be read or is empty.
{"=" * 80}

"""
            if errors:
                report_content += f"Errors ({len(errors)}):\n"
                for error in errors:
                    report_content += f"  - {error}\n"
                report_content += "\n"

            if warnings:
                report_content += f"Warnings ({len(warnings)}):\n"
                for warning in warnings:
                    report_content += f"  - {warning}\n"
                report_content += "\n"

            report_path.write_text(report_content, encoding="utf-8")
            logger.info(f"LVS report saved to: {report_path}")

        return LVSResult(
            matched=matched,
            output=output,
            errors=errors,
            warnings=warnings,
        )

    except subprocess.TimeoutExpired:
        logger.error(f"Netgen comparison timed out after {netgen_timeout} seconds")
        return LVSResult(
            matched=False,
            output="",
            errors=[f"Netgen comparison timed out after {netgen_timeout} seconds"],
        )
    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
    ) as e:
        logger.exception(f"Error running Netgen comparison: {e}")
        return LVSResult(
            matched=False,
            output=str(e),
            errors=[f"Error running Netgen: {e}"],
        )
    finally:
        # Clean up script file
        try:
            if script_path.exists():
                script_path.unlink()
        except (OSError, IOError) as e:
            logger.warning(f"Failed to clean up temporary script file: {e}")


def verify_conversion(
    verilog_file: str | Path,
    spice_file: str | Path,
    output_dir: str | Path,
    cell_library_path: Optional[str | Path] = None,
    top_module: Optional[str] = None,
) -> LVSResult:
    """Verify converted SPICE netlist by comparing with reference generated from Verilog.

    This creates a reference SPICE netlist from the original Verilog and compares it
    with the converted SPICE netlist. Note: This is a simplified verification that
    assumes both netlists are generated from the same source with compatible settings.

    Args:
        verilog_file: Path to original Verilog file
        spice_file: Path to converted SPICE netlist
        output_dir: Directory for temporary reference files
        cell_library_path: Optional path to cell library for reference generation
        top_module: Optional top module name

    Returns:
        LVSResult object with comparison results

    Note:
        This is a placeholder implementation. A full implementation would:
        1. Generate reference SPICE from Verilog using Yosys + tool
        2. Compare reference vs converted SPICE using verify_spice_vs_spice()

        For now, this serves as a framework for future enhancement.
    """
    logger.warning(
        "Verilog vs SPICE verification is not fully implemented yet. "
        "Use SPICE vs SPICE comparison for now."
    )

    # Note: Full implementation would require:
    # 1. Using Yosys to generate a reference netlist from Verilog
    # 2. Converting that to SPICE format compatible with Netgen
    # 3. Comparing using verify_spice_vs_spice()
    # This is a future enhancement that requires additional tooling integration.

    return LVSResult(
        matched=False,
        output="",
        errors=["Verilog vs SPICE verification not yet implemented"],
        warnings=["Use SPICE vs SPICE comparison instead"],
    )


def compare_flattening_levels(
    logic_spice: str | Path,
    transistor_spice: str | Path,
    tolerance: float = 0.01,
    report_file: Optional[str | Path] = None,
) -> Tuple[bool, LVSResult]:
    """Compare logic-level and transistor-level flattened netlists.

    Args:
        logic_spice: Path to logic-level SPICE netlist
        transistor_spice: Path to transistor-level SPICE netlist
        tolerance: Matching tolerance for comparison
        report_file: Optional path to save detailed LVS report

    Returns:
        Tuple of (success, LVSResult)
    """
    logger.info("Comparing logic-level vs transistor-level netlists")

    try:
        result = verify_spice_vs_spice(
            logic_spice, transistor_spice, tolerance, report_file=report_file
        )
        return result.matched, result
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        logger.error(f"Error comparing flattening levels: {e}")
        return False, LVSResult(
            matched=False,
            output="",
            errors=[str(e)],
        )
