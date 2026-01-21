"""Command-line interface for Verilog to SPICE conversion."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn

from .formatter import (
    format_flattened,
    format_hierarchical,
    load_cell_library_content,
    validate_spice,
)
from .lvs import check_netgen, compare_flattening_levels, verify_spice_vs_spice
from .mapper import load_cell_library
from .parser import get_top_module, parse_yosys_json
from .spice_generator import generate_netlist
from .synthesizer import synthesize

if TYPE_CHECKING:
    pass

console = Console()


def setup_logging(verbose: bool, quiet: bool, log_file: Optional[str] = None) -> None:
    """Setup logging configuration.

    Args:
        verbose: Enable verbose logging
        quiet: Enable quiet mode (errors only)
        log_file: Optional log file path
    """
    log_level = logging.DEBUG if verbose else (logging.ERROR if quiet else logging.INFO)

    handlers: List[logging.Handler] = [
        RichHandler(console=console, rich_tracebacks=True)
    ]

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers,
    )


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from file.

    Args:
        config_path: Path to configuration file

    Returns:
        Dictionary of configuration values

    Raises:
        FileNotFoundError: If config file is not found
    """
    import json

    if not Path(config_path).exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Convert Verilog RTL to SPICE netlists",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Input arguments
    parser.add_argument(
        "verilog_files",
        nargs="+",
        help="Verilog source files",
    )

    parser.add_argument(
        "-t",
        "--top",
        type=str,
        help="Top-level module name",
    )

    parser.add_argument(
        "-I",
        "--include",
        action="append",
        dest="include_paths",
        default=[],
        help="Include/search path (can be repeated)",
    )

    parser.add_argument(
        "-D",
        "--define",
        action="append",
        dest="defines",
        default=[],
        help="Preprocessor define (name=value, can be repeated)",
    )

    # Output arguments
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output SPICE netlist file",
    )

    parser.add_argument(
        "-O",
        "--output-dir",
        type=str,
        default="./output",
        help="Output directory",
    )

    parser.add_argument(
        "--hierarchical",
        "--hier",
        action="store_true",
        dest="hierarchical",
        help="Generate hierarchical netlist (default)",
    )

    parser.add_argument(
        "--flattened",
        "--flat",
        action="store_true",
        dest="flattened",
        help="Generate flattened netlist",
    )

    parser.add_argument(
        "--both",
        action="store_true",
        help="Generate both hierarchical and flattened netlists",
    )

    parser.add_argument(
        "--flatten-level",
        type=str,
        choices=["logic", "transistor"],
        default="logic",
        help="Flattening level: 'logic' (gate-level, default) or 'transistor' (PMOS/NMOS level). Only used with --flattened.",
    )

    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run LVS verification using Netgen (requires Netgen installed)",
    )

    parser.add_argument(
        "--verify-reference",
        type=str,
        help="Reference netlist file for verification (SPICE format)",
    )

    parser.add_argument(
        "--verify-flatten-levels",
        action="store_true",
        help="Compare logic-level and transistor-level flattened netlists (requires both to be generated)",
    )

    # Synthesis arguments
    parser.add_argument(
        "--synthesis-script",
        type=str,
        help="Custom Yosys synthesis script",
    )

    parser.add_argument(
        "--constraint",
        type=str,
        help="Timing/area constraints file",
    )

    parser.add_argument(
        "--optimize",
        action="store_true",
        default=True,
        help="Enable optimization (default)",
    )

    parser.add_argument(
        "--no-optimize",
        action="store_false",
        dest="optimize",
        help="Disable optimization",
    )

    # Technology arguments
    parser.add_argument(
        "--cell-library",
        type=str,
        help="Path to cell library SPICE file",
    )

    parser.add_argument(
        "--cell-metadata",
        type=str,
        help="Path to cell metadata JSON file",
    )

    parser.add_argument(
        "--tech",
        type=str,
        help="Technology name",
    )

    # Logging arguments
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Quiet mode (errors only)",
    )

    parser.add_argument(
        "--log",
        type=str,
        help="Log file path",
    )

    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary files",
    )

    # Other arguments
    parser.add_argument(
        "--config",
        type=str,
        help="Configuration file path",
    )

    return parser.parse_args()


def process_defines(defines: List[str]) -> Dict[str, str]:
    """Process define arguments into dictionary.

    Args:
        defines: List of define strings in format "name=value"

    Returns:
        Dictionary mapping names to values
    """
    result = {}
    for define in defines:
        if "=" in define:
            name, value = define.split("=", 1)
            result[name] = value
        else:
            result[define] = "1"
    return result


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    args = parse_args()

    # Setup logging
    setup_logging(args.verbose, args.quiet, args.log)
    logger = logging.getLogger(__name__)

    try:
        # Load configuration if provided
        if args.config:
            load_config(args.config)
            # Override with command-line arguments
            # TODO: Use config values to override defaults

        # Process defines
        defines_dict = process_defines(args.defines)

        # Determine output format based on flatten_level
        flatten_level = args.flatten_level

        if flatten_level == "transistor":
            # Transistor-level requires flattened output with cell library
            flattened = True
            hierarchical = False if not args.both else True
        else:
            # Logic-level flattening
            hierarchical = (
                args.hierarchical or args.both or (not args.flattened and not args.both)
            )
            flattened = args.flattened or args.both

        # Determine output file (only used when single output format)
        output_file = args.output
        # Note: When --both is used, output_file should be None to avoid conflicts
        # Files will be named {top_module}.sp and {top_module}_flat.sp
        if args.both:
            # When --both is used, don't use output_file to avoid conflicts
            output_file = None
        elif not output_file and args.top:
            # Only set default output_file if not using --both
            output_file = f"{args.top}.sp"
        elif not output_file:
            # Try to infer from first Verilog file
            first_file = Path(args.verilog_files[0])
            output_file = f"{first_file.stem}.sp"

        # Create output directory
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Determine top module name (before synthesis)
            top_module = args.top
            if not top_module:
                # Try to infer from first file (basic heuristic)
                first_file = Path(args.verilog_files[0])
                top_module = first_file.stem
                logger.info(f"Inferred top module name: {top_module}")

            # Load cell library
            task1 = progress.add_task("Loading cell library...", total=None)
            cell_library = load_cell_library(
                args.cell_library,
                args.cell_metadata,
                args.tech,
            )
            progress.update(task1, completed=True)

            # Synthesize (Yosys parses and synthesizes)
            task2 = progress.add_task("Synthesizing design with Yosys...", total=None)
            netlist = synthesize(
                args.verilog_files,
                top_module,
                args.synthesis_script,
                args.optimize,
                str(output_dir),
                args.include_paths,
                defines_dict,
            )
            progress.update(task2, completed=True)

            # Parse Yosys JSON to get module information
            task3 = progress.add_task("Parsing netlist...", total=None)
            modules = parse_yosys_json(netlist.json_data)
            top_module_info = get_top_module(modules, netlist.top_module)
            # Use the actual top module name from netlist
            top_module = top_module_info.name.lstrip("\\")
            progress.update(task3, completed=True)

            # Generate SPICE
            task5 = progress.add_task("Generating SPICE netlist...", total=None)
            spice_netlist = generate_netlist(
                netlist,
                cell_library,
                top_module,
                args.verilog_files,
                embed_cells=flattened,
                flatten_level=flatten_level,
            )
            progress.update(task5, completed=True)

            # Load cell library content if flattened (needed for both logic and transistor levels)
            cell_library_content = None
            if flattened and cell_library.spice_file:
                task5b = progress.add_task("Loading cell library models...", total=None)
                cell_library_content = load_cell_library_content(
                    cell_library.spice_file
                )
                if not cell_library_content:
                    logger.error(
                        "Cell library content not loaded - cannot create flattened netlist"
                    )
                    raise RuntimeError(
                        f"Failed to load cell library content from: {cell_library.spice_file}"
                    )
                progress.update(task5b, completed=True)

            # Format output
            task6 = progress.add_task("Formatting output...", total=None)

            if hierarchical:
                hier_text = format_hierarchical(spice_netlist)
                # When both formats are generated, use distinct names to avoid conflicts
                if flattened and not output_file:
                    hier_file = output_dir / f"{top_module}.sp"
                else:
                    hier_file = output_dir / (output_file or f"{top_module}.sp")
                # Ensure parent directory exists
                hier_file.parent.mkdir(parents=True, exist_ok=True)
                hier_file.write_text(hier_text, encoding="utf-8")
                console.print(f"[green]Generated hierarchical netlist: {hier_file}")

            if flattened:
                flat_text = format_flattened(
                    spice_netlist,
                    cell_library_content=cell_library_content,
                    flatten_level=flatten_level,
                    cell_library=cell_library,
                )
                if flatten_level == "transistor":
                    flat_file = output_dir / (
                        output_file or f"{top_module}_transistor.sp"
                    )
                    console.print(
                        f"[green]Generated transistor-level netlist: {flat_file}"
                    )
                else:
                    flat_file = output_dir / (output_file or f"{top_module}_flat.sp")
                    console.print(
                        f"[green]Generated flattened netlist (logic-level): {flat_file}"
                    )
                # Ensure parent directory exists
                flat_file.parent.mkdir(parents=True, exist_ok=True)
                flat_file.write_text(flat_text, encoding="utf-8")

            progress.update(task6, completed=True)

            # Validate
            task7 = progress.add_task("Validating SPICE...", total=None)
            if hierarchical:
                validate_spice(hier_text)
            if flattened:
                validate_spice(flat_text)
            progress.update(task7, completed=True)

            # LVS Verification
            if args.verify or args.verify_flatten_levels or args.verify_reference:
                task8 = progress.add_task("Running LVS verification...", total=None)

                if not check_netgen():
                    console.print(
                        "[yellow]Warning: Netgen LVS tool not found - skipping LVS verification.\n"
                        "[yellow]  Note: The installed 'netgen' appears to be the mesh generator, not the LVS tool.\n"
                        "[yellow]  Install Netgen LVS (typically part of Magic VLSI): sudo apt-get install magic\n"
                        "[yellow]  Or use an alternative LVS tool like Calibre"
                    )
                    progress.update(task8, completed=True)
                else:
                    # Determine file paths (matching the actual file names used during generation)
                    # Hierarchical: when both are generated without output_file, uses {top_module}.sp
                    # Otherwise uses output_file or {top_module}.sp
                    if flattened and not output_file:
                        hier_file = output_dir / f"{top_module}.sp"
                    else:
                        hier_file = output_dir / (output_file or f"{top_module}.sp")
                    # Flattened: uses output_file if specified, otherwise {top_module}_flat.sp or {top_module}_transistor.sp
                    flat_file = output_dir / (output_file or f"{top_module}_flat.sp")
                    if flatten_level == "transistor":
                        flat_file = output_dir / (
                            output_file or f"{top_module}_transistor.sp"
                        )

                    # Priority 1: External reference comparison (if specified)
                    if args.verify_reference and flattened:
                        reference_file = Path(args.verify_reference)
                        if not reference_file.exists():
                            console.print(
                                f"[red]Error: Reference netlist not found: {reference_file}"
                            )
                            progress.update(task8, completed=True)
                        elif not flat_file.exists():
                            console.print(
                                f"[yellow]Warning: Flattened netlist not found: {flat_file}"
                            )
                            progress.update(task8, completed=True)
                        else:
                            report_file = (
                                output_dir / f"{top_module}_lvs_vs_reference.rpt"
                            )
                            lvs_result = verify_spice_vs_spice(
                                reference_file, flat_file, report_file=report_file
                            )
                            if lvs_result.matched:
                                console.print(
                                    f"[green]✓ LVS: Netlist matches reference: {reference_file.name}"
                                )
                            else:
                                console.print(
                                    f"[red]✗ LVS: Netlist does not match reference: {reference_file.name}"
                                )
                                if lvs_result.errors:
                                    for error in lvs_result.errors[
                                        :5
                                    ]:  # Show first 5 errors
                                        console.print(f"[red]  {error}")
                                if lvs_result.output:
                                    logger.debug(f"Netgen output:\n{lvs_result.output}")
                            console.print(f"[blue]LVS report saved to: {report_file}")
                            progress.update(task8, completed=True)

                    # Priority 2: Compare logic vs transistor levels (if requested and both exist)
                    elif args.verify_flatten_levels:
                        # Compare logic vs transistor levels
                        logic_file = output_dir / (
                            output_file or f"{top_module}_flat.sp"
                        )
                        transistor_file = output_dir / (
                            output_file or f"{top_module}_transistor.sp"
                        )

                        if logic_file.exists() and transistor_file.exists():
                            report_file = (
                                output_dir / f"{top_module}_lvs_flatten_levels.rpt"
                            )
                            matched, lvs_result = compare_flattening_levels(
                                logic_file, transistor_file, report_file=report_file
                            )
                            if matched:
                                console.print(
                                    "[green]✓ LVS: Logic-level and transistor-level netlists match!"
                                )
                            else:
                                console.print(
                                    "[red]✗ LVS: Logic-level and transistor-level netlists do not match"
                                )
                                if lvs_result.errors:
                                    for error in lvs_result.errors[
                                        :5
                                    ]:  # Show first 5 errors
                                        console.print(f"[red]  Error: {error}")
                            console.print(f"[blue]LVS report saved to: {report_file}")
                            if lvs_result.output:
                                logger.debug(f"Netgen output:\n{lvs_result.output}")
                            progress.update(task8, completed=True)
                        else:
                            console.print(
                                "[yellow]Warning: Both logic and transistor netlists required for comparison"
                            )
                            console.print(
                                f"[yellow]  Logic file exists: {logic_file.exists()} ({logic_file})"
                            )
                            console.print(
                                f"[yellow]  Transistor file exists: {transistor_file.exists()} ({transistor_file})"
                            )
                            console.print(
                                "[yellow]  Generate both with: --both --flatten-level transistor"
                            )
                            progress.update(task8, completed=True)

                    # Priority 3: Default verification - compare hierarchical vs flattened (if both exist)
                    elif args.verify:
                        # Check if both files actually exist (regardless of hierarchical/flattened flags)
                        # This handles cases where files were generated in previous runs
                        hier_exists = hier_file.exists()
                        flat_exists = flat_file.exists()

                        if hier_exists and flat_exists and hier_file != flat_file:
                            # Both files exist and are different - run verification
                            report_file = (
                                output_dir / f"{top_module}_lvs_hier_vs_flat.rpt"
                            )
                            logger.info(
                                "Running default verification: hierarchical vs flattened"
                            )
                            lvs_result = verify_spice_vs_spice(
                                hier_file, flat_file, report_file=report_file
                            )
                            if lvs_result.matched:
                                console.print(
                                    "[green]✓ LVS: Hierarchical and flattened netlists match!"
                                )
                            else:
                                console.print(
                                    "[red]✗ LVS: Hierarchical and flattened netlists do not match"
                                )
                                if lvs_result.errors:
                                    for error in lvs_result.errors[
                                        :5
                                    ]:  # Show first 5 errors
                                        console.print(f"[red]  {error}")
                                if lvs_result.output:
                                    logger.debug(f"Netgen output:\n{lvs_result.output}")
                            console.print(f"[blue]LVS report saved to: {report_file}")
                            progress.update(task8, completed=True)
                        else:
                            # Files don't exist or are the same - show helpful message
                            console.print(
                                "[yellow]Warning: Both hierarchical and flattened netlists required for default verification"
                            )
                            if not hierarchical:
                                console.print(
                                    "[yellow]  Generate hierarchical netlist with --hierarchical or --both"
                                )
                            if not flattened:
                                console.print(
                                    "[yellow]  Generate flattened netlist with --flattened or --both"
                                )
                            if not hier_exists:
                                console.print(
                                    f"[yellow]  Hierarchical file not found: {hier_file}"
                                )
                            if not flat_exists:
                                console.print(
                                    f"[yellow]  Flattened file not found: {flat_file}"
                                )
                            if hier_file == flat_file:
                                console.print(
                                    "[yellow]  Note: Both files point to the same location. Use --both to generate separate files."
                                )
                            console.print(
                                "[yellow]  Example: ./scripts/verilog2spice.sh --both --verify design.v"
                            )
                            progress.update(task8, completed=True)

        console.print("[green]✓ Conversion completed successfully!")
        return 0

    except KeyboardInterrupt:
        console.print("\n[yellow]Conversion interrupted by user")
        return 130
    except Exception as e:
        logger.exception("Conversion failed")
        console.print(f"[red]Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
