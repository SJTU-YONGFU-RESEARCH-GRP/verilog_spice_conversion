"""SPICE netlist generator module."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .mapper import CellLibrary, map_gate_to_cell
from .synthesizer import Netlist

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SpiceNetlist:
    """SPICE netlist representation.
    
    Attributes:
        header: Header comments and directives
        subcircuits: Dictionary of subcircuit definitions
        instances: List of instance statements
        directives: List of SPICE directives
    """
    
    def __init__(
        self,
        header: Optional[List[str]] = None,
        subcircuits: Optional[Dict[str, str]] = None,
        instances: Optional[List[str]] = None,
        directives: Optional[List[str]] = None,
    ) -> None:
        """Initialize SpiceNetlist.
        
        Args:
            header: Header comments and directives
            subcircuits: Dictionary of subcircuit definitions
            instances: List of instance statements
            directives: List of SPICE directives
        """
        self.header = header or []
        self.subcircuits = subcircuits or {}
        self.instances = instances or []
        self.directives = directives or []


def build_signal_map(module_data: Dict[str, Any]) -> Dict[int, str]:
    """Build mapping from signal ID to net name from Yosys netnames.
    
    Args:
        module_data: Yosys module JSON data
        
    Returns:
        Dictionary mapping signal ID to net name
    """
    signal_map: Dict[int, str] = {}
    netnames = module_data.get("netnames", {})
    
    for net_name, net_info in netnames.items():
        bits = net_info.get("bits", [])
        # Clean net name (remove leading backslash if present)
        clean_name = net_name.lstrip("\\")
        
        for bit_id in bits:
            if isinstance(bit_id, int):
                # Use the net name for this signal
                # If multiple bits, append bit index
                if len(bits) > 1:
                    bit_idx = bits.index(bit_id)
                    signal_map[bit_id] = f"{clean_name}[{bit_idx}]"
                else:
                    signal_map[bit_id] = clean_name
    
    logger.debug(f"Built signal map with {len(signal_map)} entries")
    return signal_map


def generate_netlist(
    netlist: Netlist,
    cell_library: CellLibrary,
    top_module: str,
    source_files: Optional[List[str]] = None,
    embed_cells: bool = False,
) -> SpiceNetlist:
    """Generate SPICE netlist from Yosys gate-level netlist.
    
    Args:
        netlist: Gate-level netlist from Yosys
        cell_library: Cell library
        top_module: Top-level module name
        source_files: Optional list of source Verilog files
        embed_cells: If True, embed cell library models in output
        
    Returns:
        SpiceNetlist object
        
    Raises:
        ValueError: If no instances can be generated
    """
    logger.info(f"Generating SPICE netlist for top module: {top_module}")
    
    # Create header
    header = create_header(top_module, source_files, cell_library, embed_cells)
    
    # Generate subcircuits (for hierarchical mode)
    subcircuits: Dict[str, str] = {}
    
    # Generate instances from Yosys JSON
    instances: List[str] = []
    
    # Get the top module data from Yosys JSON
    modules = netlist.modules
    top_module_escaped = netlist.top_module or top_module
    
    if top_module_escaped not in modules:
        raise ValueError(
            f"Top module '{top_module_escaped}' not found in netlist. "
            f"Available modules: {list(modules.keys())}"
        )
    
    module_data = modules[top_module_escaped]
    instances = generate_module_instances(module_data, cell_library, top_module_escaped)
    
    if not instances:
        raise ValueError(
            f"No SPICE instances generated for module '{top_module_escaped}'. "
            f"Check that cell library contains mappings for Yosys gate types."
        )
    
    logger.info(f"Generated {len(instances)} SPICE instances")
    
    # Don't add power/ground by default - these are simulation directives
    # Users should add them manually if needed for simulation
    directives: List[str] = []
    
    return SpiceNetlist(
        header=header,
        subcircuits=subcircuits,
        instances=instances,
        directives=directives,
    )


def generate_module_instances(
    module_data: Dict[str, Any],
    cell_library: CellLibrary,
    module_name: str,
) -> List[str]:
    """Generate SPICE instances from Yosys module data.
    
    Args:
        module_data: Yosys module JSON data
        cell_library: Cell library
        module_name: Module name
        
    Returns:
        List of SPICE instance strings
    """
    instances: List[str] = []
    unmapped_gates: Dict[str, int] = {}  # Track unmapped gate types
    
    cells = module_data.get("cells", {})
    
    if not cells:
        logger.warning(f"Module '{module_name}' has no cells")
        return instances
    
    # Build signal ID to net name mapping
    signal_map = build_signal_map(module_data)
    
    logger.info(f"Processing {len(cells)} cells in module '{module_name}'")
    
    for cell_name, cell_info in cells.items():
        cell_type = cell_info.get("type", "")
        connections = cell_info.get("connections", {})
        
        if not cell_type:
            logger.warning(f"Cell '{cell_name}' has no type, skipping")
            continue
        
        # Map Yosys cell type to our cell library
        mapped_cell = map_gate_to_cell(cell_type, cell_library)
        if not mapped_cell:
            unmapped_gates[cell_type] = unmapped_gates.get(cell_type, 0) + 1
            continue
        
        # Get cell info from library
        if mapped_cell not in cell_library.cells:
            logger.error(
                f"Mapped cell '{mapped_cell}' for gate '{cell_type}' not in library. "
                f"Available cells: {list(cell_library.cells.keys())}"
            )
            unmapped_gates[cell_type] = unmapped_gates.get(cell_type, 0) + 1
            continue
        
        cell_lib_info = cell_library.cells[mapped_cell]
        pins = cell_lib_info.get("pins", [])
        spice_model = cell_lib_info.get("spice_model", mapped_cell)
        
        # Build pin connections in order
        pin_connections = []
        for pin in pins:
            # Yosys connections are lists of signal IDs
            signal_ids = connections.get(pin, [])
            if signal_ids:
                # Resolve signal ID to net name
                signal_id = signal_ids[0] if isinstance(signal_ids, list) else signal_ids
                if isinstance(signal_id, int) and signal_id in signal_map:
                    net_name = signal_map[signal_id]
                    pin_connections.append(net_name)
                elif isinstance(signal_id, int):
                    # Use signal ID as fallback if not in map
                    pin_connections.append(f"n{signal_id}")
                else:
                    pin_connections.append(str(signal_id))
            else:
                # Unconnected pin - use empty string or special marker
                pin_connections.append("NC")  # No Connection
        
        # Format: X<instance_name> <pin1> <pin2> ... <cell_model>
        instance_name = cell_name.lstrip("\\")
        # Clean instance name (remove special characters that might cause issues)
        instance_name = instance_name.replace("$", "_").replace("/", "_").replace(":", "_")
        instance_line = f"X{instance_name} {' '.join(pin_connections)} {spice_model}"
        instances.append(instance_line)
    
    # Log summary of unmapped gates
    if unmapped_gates:
        logger.error(
            f"Failed to map {sum(unmapped_gates.values())} cells: "
            f"{', '.join(f'{gt}({count})' for gt, count in unmapped_gates.items())}"
        )
    
    logger.debug(f"Generated {len(instances)} SPICE instances for module {module_name}")
    return instances


def create_header(
    top_module: str,
    source_files: Optional[List[str]],
    cell_library: CellLibrary,
    embed_cells: bool = False,
) -> List[str]:
    """Create SPICE netlist header.
    
    Args:
        top_module: Top-level module name
        source_files: Optional list of source files
        cell_library: Cell library
        embed_cells: If True, don't add .include (cells will be embedded)
        
    Returns:
        List of header lines
    """
    header = []
    header.append("* SPICE Netlist")
    header.append(f"* Generated from Verilog RTL using Yosys")
    if source_files:
        header.append(f"* Source files: {', '.join(source_files)}")
    header.append(f"* Top Module: {top_module}")
    header.append(f"* Technology: {cell_library.technology}")
    header.append(f"* Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    header.append("")
    
    # Add cell library include if available and not embedding
    if cell_library.spice_file and not embed_cells:
        header.append(f".include \"{cell_library.spice_file}\"")
        header.append("")
    elif embed_cells:
        header.append("* Cell library models embedded below (no .include needed)")
        header.append("")
    else:
        logger.warning("No SPICE model file specified in cell library")
    
    return header


def create_subcircuit(
    module_name: str,
    instances: List[str],
    cell_library: CellLibrary,
) -> str:
    """Create a SPICE subcircuit definition.
    
    Args:
        module_name: Module name
        instances: List of SPICE instance strings
        cell_library: Cell library
        
    Returns:
        SPICE subcircuit definition string
    """
    lines = []
    lines.append(f".SUBCKT {module_name}")
    
    # Add instance statements
    for inst in instances:
        lines.append(f"  {inst}")
    
    lines.append(".ENDS")
    lines.append("")
    
    return "\n".join(lines)


def add_power_ground() -> List[str]:
    """Add power and ground connections.
    
    Returns:
        List of SPICE directives for power/ground
    """
    directives = []
    directives.append("* Power and Ground")
    directives.append("VDD VDD 0 1.8")
    directives.append("VSS VSS 0 0")
    directives.append("")
    return directives


def add_simulation_directives(
    netlist: SpiceNetlist,
    analysis_type: str = "dc",
) -> SpiceNetlist:
    """Add simulation directives to netlist.
    
    Args:
        netlist: SPICE netlist
        analysis_type: Type of analysis (dc, tran, ac)
        
    Returns:
        Updated SPICE netlist
    """
    directives = netlist.directives.copy()
    
    if analysis_type == "dc":
        directives.append(".op")
    elif analysis_type == "tran":
        directives.append(".tran 1n 100n")
    elif analysis_type == "ac":
        directives.append(".ac dec 10 1 1G")
    
    directives.append(".end")
    
    netlist.directives = directives
    return netlist
