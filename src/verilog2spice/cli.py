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

from .formatter import format_flattened, format_hierarchical, load_cell_library_content, validate_spice
from .mapper import load_cell_library
from .parser import get_top_module, parse_yosys_json
from .spice_generator import generate_netlist, add_simulation_directives
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
    
    handlers: List[logging.Handler] = [RichHandler(console=console, rich_tracebacks=True)]
    
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
        "--fully-flattened",
        "--fully-flat",
        action="store_true",
        dest="fully_flattened",
        help="Generate fully flattened netlist with embedded cell library models",
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
        config = {}
        if args.config:
            config = load_config(args.config)
            # Override with command-line arguments
        
        # Process defines
        defines_dict = process_defines(args.defines)
        
        # Determine output format
        fully_flattened = args.fully_flattened
        hierarchical = args.hierarchical or (not args.flattened and not args.both and not fully_flattened)
        flattened = args.flattened or args.both or fully_flattened
        
        # Determine output file
        output_file = args.output
        if not output_file and args.top:
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
                embed_cells=fully_flattened,
            )
            progress.update(task5, completed=True)
            
            # Load cell library content if fully flattened
            cell_library_content = None
            if fully_flattened and cell_library.spice_file:
                task5b = progress.add_task("Loading cell library models...", total=None)
                cell_library_content = load_cell_library_content(cell_library.spice_file)
                if not cell_library_content:
                    logger.error("Cell library content not loaded - cannot create fully flattened netlist")
                    raise RuntimeError(f"Failed to load cell library content from: {cell_library.spice_file}")
                progress.update(task5b, completed=True)
            
            # Format output
            task6 = progress.add_task("Formatting output...", total=None)
            
            if hierarchical:
                hier_text = format_hierarchical(spice_netlist)
                hier_file = output_dir / (output_file or f"{top_module}_hier.sp")
                hier_file.write_text(hier_text, encoding="utf-8")
                console.print(f"[green]Generated hierarchical netlist: {hier_file}")
            
            if flattened:
                flat_text = format_flattened(
                    spice_netlist,
                    embed_cells=fully_flattened,
                    cell_library_content=cell_library_content,
                )
                if fully_flattened:
                    flat_file = output_dir / (output_file or f"{top_module}_fully_flat.sp")
                    console.print(f"[green]Generated fully flattened netlist (with embedded cells): {flat_file}")
                else:
                    flat_file = output_dir / (output_file or f"{top_module}_flat.sp")
                    console.print(f"[green]Generated flattened netlist: {flat_file}")
                flat_file.write_text(flat_text, encoding="utf-8")
            
            progress.update(task6, completed=True)
            
            # Validate
            task7 = progress.add_task("Validating SPICE...", total=None)
            if hierarchical:
                validate_spice(hier_text)
            if flattened:
                validate_spice(flat_text)
            progress.update(task7, completed=True)
        
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

