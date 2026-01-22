"""Technology mapping module for mapping gates to standard cells."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class CellLibrary:
    """Standard cell library representation.

    Attributes:
        technology: Technology name
        cells: Dictionary mapping cell names to cell information
        spice_file: Path to SPICE model file
    """

    def __init__(
        self,
        technology: str,
        cells: Dict[str, Dict[str, Any]],
        spice_file: Optional[str] = None,
    ) -> None:
        """Initialize CellLibrary.

        Args:
            technology: Technology name
            cells: Dictionary mapping cell names to cell information
            spice_file: Optional path to SPICE model file
        """
        self.technology = technology
        self.cells = cells
        self.spice_file = spice_file


class CellInstance:
    """Cell instance information.

    Attributes:
        cell_name: Name of the cell type
        instance_name: Name of this instance
        pins: Dictionary mapping pin names to net names
        parameters: Dictionary of cell parameters
    """

    def __init__(
        self,
        cell_name: str,
        instance_name: str,
        pins: Optional[Dict[str, str]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize CellInstance.

        Args:
            cell_name: Name of the cell type
            instance_name: Name of this instance
            pins: Dictionary mapping pin names to net names
            parameters: Dictionary of cell parameters
        """
        self.cell_name = cell_name
        self.instance_name = instance_name
        self.pins = pins or {}
        self.parameters = parameters or {}


# Yosys internal gate type to standard cell mapping
YOSYS_GATE_MAP: Dict[str, str] = {
    "$_AND_": "AND2",
    "$_NAND_": "NAND2",
    "$_OR_": "OR2",
    "$_NOR_": "NOR2",
    "$_XOR_": "XOR2",
    "$_XNOR_": "XNOR2",
    "$_NOT_": "INV",
    "$_BUF_": "BUF",
    "$_ANDNOT_": "AND2",  # Will need special handling
    "$_ORNOT_": "OR2",  # Will need special handling
    "$_MUX_": "MUX2",  # If available
    "$_DFF_": "DFF",
    "$_DFFE_": "DFF",
    "$_DFF_N_": "DFF",
    "$_DFF_P_": "DFF",
    "$_DFFE_N_": "DFF",
    "$_DFFE_P_": "DFF",
    "$_DFFSR_": "DFFR",
    "$_DFFSRE_": "DFFR",
}

# Generic gate to cell mapping (for non-Yosys gates)
DEFAULT_GATE_MAP: Dict[str, str] = {
    "NOT": "INV",
    "AND": "AND2",
    "NAND": "NAND2",
    "OR": "OR2",
    "NOR": "NOR2",
    "XOR": "XOR2",
    "XNOR": "XNOR2",
    "BUF": "BUF",
    "DFF": "DFF",
    "DFFR": "DFFR",
    "FA": "FA",
    "HA": "HA",
    "MUX2": "MUX2",
    "MUX4": "MUX4",
    "MUX8": "MUX8",
}


def load_cell_library(
    library_path: Optional[str] = None,
    metadata_path: Optional[str] = None,
    tech: Optional[str] = None,
) -> CellLibrary:
    """Load cell library from file.

    Args:
        library_path: Path to SPICE cell library file
        metadata_path: Path to cell metadata JSON file
        tech: Technology name (for default library selection)

    Returns:
        CellLibrary object

    Raises:
        FileNotFoundError: If library file is not found
        ValueError: If library format is invalid
    """
    # Try to load from metadata file
    if metadata_path and Path(metadata_path).exists():
        logger.info(f"Loading cell library from metadata file: {metadata_path}")
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        technology = data.get("technology", tech or "generic")
        cells = data.get("cells", {})
        spice_file_name = data.get("spice_file", library_path)

        # Resolve SPICE file path relative to metadata file location
        if spice_file_name and not Path(spice_file_name).is_absolute():
            metadata_dir = Path(metadata_path).parent
            spice_file = metadata_dir / spice_file_name
        else:
            spice_file = Path(spice_file_name) if spice_file_name else None

        if not cells:
            raise ValueError(f"Cell library file '{metadata_path}' contains no cells")

        if spice_file and not spice_file.exists():
            logger.warning(f"SPICE model file not found: {spice_file}")
            spice_file = None

        logger.info(f"Loaded {len(cells)} cells from library: {metadata_path}")
        if spice_file:
            logger.info(f"SPICE model file: {spice_file}")

        return CellLibrary(
            technology=technology,
            cells=cells,
            spice_file=str(spice_file) if spice_file else None,
        )

    # Try to load default library
    # Path calculation: mapper.py -> verilog2spice -> src -> project_root
    project_root = Path(__file__).parent.parent.parent
    default_lib_path = project_root / "config" / "cell_libraries" / "cells.json"

    if default_lib_path.exists():
        logger.info(f"Loading default cell library from: {default_lib_path}")
        with open(default_lib_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        technology = data.get("technology", tech or "generic")
        cells = data.get("cells", {})

        # Resolve SPICE file path relative to config directory
        spice_file_name = data.get("spice_file", "cells.spice")
        spice_file = project_root / "config" / "cell_libraries" / spice_file_name

        if not cells:
            raise ValueError(
                f"Cell library file '{default_lib_path}' contains no cells"
            )

        if not spice_file.exists():
            logger.warning(f"SPICE model file not found: {spice_file}")
            spice_file = None

        logger.info(f"Loaded {len(cells)} cells from default library")
        logger.info(f"SPICE model file: {spice_file}")
        return CellLibrary(
            technology=technology,
            cells=cells,
            spice_file=str(spice_file) if spice_file else None,
        )

    # No fallback - fail if library not found
    raise FileNotFoundError(
        f"Cell library not found. Please specify --cell-metadata or ensure "
        f"default library exists at: {default_lib_path}"
    )


def map_gate_to_cell(
    gate_type: str,
    cell_library: CellLibrary,
    params: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Map a gate type to a cell name in the library.

    Args:
        gate_type: Gate type name (e.g., "$_AND_", "AND2")
        cell_library: Cell library to search
        params: Optional gate parameters

    Returns:
        Cell name if found, None otherwise
    """
    # Try Yosys gate mapping first (most common case)
    if gate_type in YOSYS_GATE_MAP:
        mapped_name = YOSYS_GATE_MAP[gate_type]
        if mapped_name in cell_library.cells:
            logger.debug(f"Mapped Yosys gate '{gate_type}' to '{mapped_name}'")
            return mapped_name
        else:
            logger.error(
                f"Yosys gate '{gate_type}' maps to '{mapped_name}' but this cell "
                f"is not in the library. Available cells: {list(cell_library.cells.keys())}"
            )
            return None

    # Try direct match
    if gate_type in cell_library.cells:
        return gate_type

    # Try default mapping
    mapped_name = DEFAULT_GATE_MAP.get(gate_type)
    if mapped_name and mapped_name in cell_library.cells:
        return mapped_name

    # Try case-insensitive match
    gate_upper = gate_type.upper()
    for cell_name in cell_library.cells:
        if cell_name.upper() == gate_upper:
            return cell_name

    logger.error(
        f"Gate type '{gate_type}' cannot be mapped to any cell in library. "
        f"Available cells: {list(cell_library.cells.keys())}. "
        f"Yosys gates should be mapped via YOSYS_GATE_MAP."
    )
    return None


def resolve_cell_parameters(
    cell: CellInstance,
    gate_params: Dict[str, Any],
    cell_library: CellLibrary,
) -> Dict[str, Any]:
    """Resolve cell parameters from gate parameters.

    Args:
        cell: Cell instance
        gate_params: Gate-level parameters
        cell_library: Cell library

    Returns:
        Dictionary of resolved cell parameters
    """
    if cell.cell_name not in cell_library.cells:
        return {}

    cell_info = cell_library.cells[cell.cell_name]
    cell_params = cell_info.get("parameters", [])

    resolved = {}
    for param in cell_params:
        # Try to get from gate params, or use default
        if param in gate_params:
            resolved[param] = gate_params[param]
        else:
            # Use default values (would be in cell library in full implementation)
            resolved[param] = "1.0"  # Default

    return resolved


def get_spice_model(cell_name: str, cell_library: CellLibrary) -> Optional[str]:
    """Get SPICE model name for a cell.

    Args:
        cell_name: Cell name
        cell_library: Cell library

    Returns:
        SPICE model name if found, None otherwise
    """
    if cell_name in cell_library.cells:
        return cell_library.cells[cell_name].get("spice_model", cell_name)

    return None
