"""SPICE netlist generator module."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .mapper import CellLibrary, map_gate_to_cell
from .spice_parser import SubcircuitDefinition, load_subcircuit_definitions
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
    flatten_level: str = "logic",
) -> SpiceNetlist:
    """Generate SPICE netlist from Yosys gate-level netlist.

    Args:
        netlist: Gate-level netlist from Yosys
        cell_library: Cell library
        top_module: Top-level module name
        source_files: Optional list of source Verilog files
        embed_cells: If True, embed cell library models in output
        flatten_level: Flattening level: "logic" (gates) or "transistor" (PMOS/NMOS)

    Returns:
        SpiceNetlist object

    Raises:
        ValueError: If no instances can be generated
    """
    logger.info(
        f"Generating SPICE netlist for top module: {top_module} (flatten_level={flatten_level})"
    )

    # Create header
    header = create_header(
        top_module, source_files, cell_library, embed_cells, flatten_level
    )

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
                signal_id = (
                    signal_ids[0] if isinstance(signal_ids, list) else signal_ids
                )
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
        instance_name = (
            instance_name.replace("$", "_").replace("/", "_").replace(":", "_")
        )
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
    flatten_level: str = "logic",
) -> List[str]:
    """Create SPICE netlist header.

    Args:
        top_module: Top-level module name
        source_files: Optional list of source files
        cell_library: Cell library
        embed_cells: If True, don't add .include (cells will be embedded)
        flatten_level: Flattening level ("logic" or "transistor")

    Returns:
        List of header lines
    """
    header = []
    header.append("* SPICE Netlist")
    header.append("* Generated from Verilog RTL using Yosys")
    if source_files:
        header.append(f"* Source files: {', '.join(source_files)}")
    header.append(f"* Top Module: {top_module}")
    header.append(f"* Technology: {cell_library.technology}")
    header.append(f"* Flatten Level: {flatten_level}")
    header.append(f"* Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    header.append("")

    # Add cell library include only if not embedding
    if embed_cells:
        header.append("* Cell library models embedded below (no .include needed)")
        header.append("")
    elif cell_library.spice_file:
        header.append(f'.include "{cell_library.spice_file}"')
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


def parse_instance_line(
    instance_line: str,
) -> Optional[Tuple[str, List[str], str, List[str]]]:
    """Parse a SPICE instance line.

    Args:
        instance_line: SPICE instance line (e.g., "Xinst A B Y INV" or "M1 D G S B PMOS W=2u")

    Returns:
        Tuple of (instance_name, net_connections, cell_type, params) or None if invalid
        params is empty list for subcircuits, contains parameters for transistors
    """
    instance_line = instance_line.strip()
    if not instance_line or instance_line.startswith("*"):
        return None

    parts = instance_line.split()
    if len(parts) < 2:
        return None

    instance_name = parts[0]
    if instance_name[0] not in ("X", "M", "x", "m"):
        return None

    # Find where parameters might start (for transistors)
    # For transistors: M<name> drain gate source bulk model [params...]
    # For subcircuits: X<name> pin1 pin2 ... subcircuit_name
    # We'll find the model/subcircuit name and separate params

    if instance_name[0].upper() == "M":
        # Transistor: M<name> drain gate source bulk model [params...]
        if len(parts) < 6:
            return None  # Need at least: M name drain gate source bulk model
        net_connections = parts[1:5]  # drain, gate, source, bulk
        cell_type = parts[5]
        params = parts[6:] if len(parts) > 6 else []
    else:
        # Subcircuit: X<name> pin1 pin2 ... subcircuit_name
        # Last part is the subcircuit name
        cell_type = parts[-1]
        # Everything in between is net connections
        net_connections = parts[1:-1]
        params = []

    return (instance_name, net_connections, cell_type, params)


def expand_instance_to_transistors(
    instance_line: str,
    subcircuit_defs: Dict[str, SubcircuitDefinition],
    net_name_counter: Dict[str, int],
    instance_prefix: str = "",
) -> List[str]:
    """Expand a subcircuit instance to transistor-level instances.

    Args:
        instance_line: SPICE instance line (e.g., "Xinst A B Y INV")
        subcircuit_defs: Dictionary of subcircuit definitions
        net_name_counter: Dictionary to track net name counters (for unique naming)
        instance_prefix: Prefix for instance names (for hierarchical expansion)

    Returns:
        List of transistor-level instance lines (M statements)
    """
    parsed = parse_instance_line(instance_line)
    if not parsed:
        return [instance_line]  # Return as-is if not parseable

    instance_name, port_connections, cell_type, params = parsed

    # If it's already a transistor (M statement), return as-is
    if instance_name[0].upper() == "M":
        return [instance_line]

    # Look up subcircuit definition
    if cell_type not in subcircuit_defs:
        logger.warning(
            f"Subcircuit '{cell_type}' not found in definitions, keeping as-is"
        )
        return [instance_line]

    subcircuit = subcircuit_defs[cell_type]

    # Map port connections: port name -> actual net
    port_map: Dict[str, str] = {}
    for i, port_name in enumerate(subcircuit.ports):
        if i < len(port_connections):
            port_map[port_name] = port_connections[i]
        else:
            logger.warning(f"Port {port_name} of {cell_type} not connected")
            port_map[port_name] = "NC"

    # Track internal nets: internal net name -> unique global net name
    internal_net_map: Dict[str, str] = {}

    def get_net_name(net: str) -> str:
        """Get the global net name for a net (port or internal)."""
        if net in port_map:
            # This is a port - use the port connection
            return port_map[net]
        elif net in ("VDD", "VSS", "0"):
            # Global nets - use as-is
            return net
        else:
            # Internal net - create unique name if not already mapped
            if net not in internal_net_map:
                # Use instance_prefix + instance_name + net as key for uniqueness
                counter_key = f"{instance_prefix}{instance_name}_{net}"
                counter = net_name_counter.get(counter_key, 0)
                unique_net = (
                    f"{instance_prefix}{instance_name}_{net}_{counter}"
                    if instance_prefix
                    else f"{instance_name}_{net}_{counter}"
                )
                internal_net_map[net] = unique_net
                net_name_counter[counter_key] = counter + 1
            return internal_net_map[net]

    # Expand all instances in the subcircuit
    expanded_instances: List[str] = []
    inst_counter = 0

    for inst_line in subcircuit.instances:
        inst_line_stripped = inst_line.strip()
        if not inst_line_stripped or inst_line_stripped.startswith("*"):
            continue

        inst_parsed = parse_instance_line(inst_line_stripped)
        if not inst_parsed:
            continue

        inst_name, inst_nets, inst_type, inst_params = inst_parsed

        # Map all nets
        mapped_nets = [get_net_name(net) for net in inst_nets]

        # Create new instance name
        new_inst_name = (
            f"{instance_prefix}{instance_name}_{inst_name}"
            if instance_prefix
            else f"{instance_name}_{inst_name}"
        )
        inst_counter += 1

        if inst_name[0].upper() == "M":
            # Transistor instance - combine nets, model, and params
            new_inst_line = f"{new_inst_name} {' '.join(mapped_nets)} {inst_type}"
            if inst_params:
                new_inst_line += " " + " ".join(inst_params)
            expanded_instances.append(new_inst_line)
        elif inst_name[0].upper() == "X":
            # Nested subcircuit - recursively expand
            nested_line = f"{new_inst_name} {' '.join(mapped_nets)} {inst_type}"
            nested_prefix = (
                f"{instance_prefix}{instance_name}_"
                if instance_prefix
                else f"{instance_name}_"
            )
            nested_expanded = expand_instance_to_transistors(
                nested_line, subcircuit_defs, net_name_counter, nested_prefix
            )
            expanded_instances.extend(nested_expanded)
        else:
            # Unknown instance type - keep as-is but with mapped nets
            new_inst_line = f"{new_inst_name} {' '.join(mapped_nets)} {inst_type}"
            if inst_params:
                new_inst_line += " " + " ".join(inst_params)
            expanded_instances.append(new_inst_line)

    return expanded_instances


def expand_to_transistor_level(
    instances: List[str],
    cell_library: CellLibrary,
) -> List[str]:
    """Expand all subcircuit instances to transistor level.

    Args:
        instances: List of SPICE instance lines
        cell_library: Cell library containing SPICE file path

    Returns:
        List of transistor-level instance lines

    Raises:
        FileNotFoundError: If cell library SPICE file not found
    """
    if not cell_library.spice_file:
        raise ValueError(
            "Cell library SPICE file required for transistor-level flattening"
        )

    # Load subcircuit definitions
    subcircuit_defs = load_subcircuit_definitions(cell_library.spice_file)
    if not subcircuit_defs:
        logger.warning(
            "No subcircuit definitions found, cannot expand to transistor level"
        )
        return instances

    logger.info(f"Expanding {len(instances)} instances to transistor level")

    expanded_instances: List[str] = []
    # Track net name counters to ensure unique names
    net_name_counter: Dict[str, int] = {}

    for inst_line in instances:
        expanded = expand_instance_to_transistors(
            inst_line, subcircuit_defs, net_name_counter
        )
        expanded_instances.extend(expanded)

    logger.info(f"Expanded to {len(expanded_instances)} transistor-level instances")
    return expanded_instances


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
