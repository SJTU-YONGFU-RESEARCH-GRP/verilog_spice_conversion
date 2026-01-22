"""SPICE netlist generator module."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from .mapper import CellLibrary, map_gate_to_cell
from .spice_parser import SubcircuitDefinition, load_subcircuit_definitions
from .synthesizer import Netlist

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_ASSOCIATIVE_2INPUT_TYPES: Dict[str, str] = {
    # Yosys internal names -> base cell name
    "$_AND_": "AND",
    "$_OR_": "OR",
    "$_NAND_": "NAND",
    "$_NOR_": "NOR",
    "$_XOR_": "XOR",
    "$_XNOR_": "XNOR",
}


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

    # Pattern matching: detect FA/HA from gate-level logic
    cells = _detect_adder_patterns(module_data, cells, cell_library)
    
    # Debug: Count FA/HA cells after pattern detection
    fa_ha_count = sum(1 for c in cells.values() if c.get("type") in ("FA", "HA"))
    if fa_ha_count > 0:
        logger.info(f"Found {fa_ha_count} FA/HA cells after pattern detection")
        # Log first few HA/FA cell names for debugging
        fa_ha_cells = [name for name, c in cells.items() if c.get("type") in ("FA", "HA")]
        logger.debug(f"FA/HA cell names (first 5): {fa_ha_cells[:5]}")
    
    # Gate collapsing: collapse associative gate chains (AND/OR/NAND/NOR)
    cells = _collapse_associative_gate_chains(module_data, cells, cell_library)
    
    # Debug: Count FA/HA cells after gate collapsing
    fa_ha_count_after = sum(1 for c in cells.values() if c.get("type") in ("FA", "HA"))
    if fa_ha_count != fa_ha_count_after:
        logger.warning(
            f"FA/HA cell count changed after gate collapsing: {fa_ha_count} -> {fa_ha_count_after}"
        )

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
            # Log FA/HA cells specifically for debugging
            if cell_type in ("FA", "HA"):
                logger.error(
                    f"Failed to map {cell_type} cell '{cell_name}'. "
                    f"Available cells: {list(cell_library.cells.keys())}"
                )
            unmapped_gates[cell_type] = unmapped_gates.get(cell_type, 0) + 1
            continue

        # Get cell info from library
        if mapped_cell not in cell_library.cells:
            # Log FA/HA cells specifically for debugging
            if cell_type in ("FA", "HA"):
                logger.error(
                    f"Mapped cell '{mapped_cell}' for {cell_type} cell '{cell_name}' not in library. "
                    f"Available cells: {list(cell_library.cells.keys())}"
                )
            logger.error(
                f"Mapped cell '{mapped_cell}' for gate '{cell_type}' not in library. "
                f"Available cells: {list(cell_library.cells.keys())}"
            )
            unmapped_gates[cell_type] = unmapped_gates.get(cell_type, 0) + 1
            continue

        # Debug log for FA/HA cells
        if cell_type in ("FA", "HA"):
            logger.debug(
                f"Processing {cell_type} cell '{cell_name}' -> mapped to '{mapped_cell}'"
            )

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


def _detect_adder_patterns(
    module_data: Dict[str, Any],
    cells: Dict[str, Any],
    cell_library: CellLibrary,
) -> Dict[str, Any]:
    """Detect and replace gate-level FA/HA patterns with FA/HA cells.

    This pattern matching helps identify full/half adders from gate-level implementations,
    reducing cell count and improving module identification.

    Half Adder pattern:
    - XOR(A, B) -> SUM
    - AND(A, B) -> CARRY
    - Both gates share the same A and B inputs

    Full Adder pattern:
    - XOR(A, B) -> temp1
    - XOR(temp1, CI) -> SUM
    - AND(A, B) -> temp2
    - AND(CI, temp1) -> temp3
    - OR(temp2, temp3) -> CARRY

    Args:
        module_data: Yosys module JSON data.
        cells: Cells dict from Yosys module.
        cell_library: Cell library (must contain FA/HA cells).

    Returns:
        Potentially rewritten `cells` dict with FA/HA cells replacing gate patterns.
    """
    # Quick exit if library doesn't have FA/HA
    has_ha = "HA" in cell_library.cells
    has_fa = "FA" in cell_library.cells
    if not has_ha and not has_fa:
        return cells

    def _first_int(sig_list: Any) -> Optional[int]:
        """Extract first integer from signal list."""
        if isinstance(sig_list, list) and sig_list and isinstance(sig_list[0], int):
            return sig_list[0]
        if isinstance(sig_list, int):
            return sig_list
        return None

    # Build maps: output net -> cell, and cell -> (A, B, Y) connections
    out_net_to_cell: Dict[int, str] = {}
    cell_connections: Dict[str, Tuple[Optional[int], Optional[int], Optional[int]]] = {}
    cell_types: Dict[str, str] = {}

    for cell_name, cell_info in cells.items():
        ctype = cell_info.get("type", "")
        conns = cell_info.get("connections", {})
        a = _first_int(conns.get("A", []))
        b = _first_int(conns.get("B", []))
        y = _first_int(conns.get("Y", []))
        cell_connections[cell_name] = (a, b, y)
        cell_types[cell_name] = ctype
        if y is not None:
            out_net_to_cell[y] = cell_name

    removed: Set[str] = set()
    rewritten_cells: Dict[str, Any] = dict(cells)

    # Detect Half Adder pattern: XOR(A, B) -> SUM, AND(A, B) -> CARRY
    if has_ha:
        for xor_cell, xor_info in list(cells.items()):
            if xor_cell in removed or xor_info.get("type") != "$_XOR_":
                continue

            xor_a, xor_b, xor_y = cell_connections.get(xor_cell, (None, None, None))
            if xor_a is None or xor_b is None or xor_y is None:
                continue

            # Look for AND gate with same A, B inputs
            for and_cell, and_info in cells.items():
                if and_cell in removed or and_cell == xor_cell:
                    continue
                if and_info.get("type") != "$_AND_":
                    continue

                and_a, and_b, and_y = cell_connections.get(and_cell, (None, None, None))
                if and_a is None or and_b is None or and_y is None:
                    continue

                # Check if XOR and AND share the same A, B inputs (order-independent)
                if (xor_a, xor_b) == (and_a, and_b) or (xor_a, xor_b) == (and_b, and_a):
                    # Found HA pattern! Replace with HA cell
                    ha_cell_name = f"HA_{xor_cell}"
                    rewritten_cells[ha_cell_name] = {
                        "type": "HA",
                        "connections": {
                            "A": [xor_a],
                            "B": [xor_b],
                            "SUM": [xor_y],
                            "CARRY": [and_y],
                        },
                        "port_directions": {
                            "A": "input",
                            "B": "input",
                            "SUM": "output",
                            "CARRY": "output",
                        },
                    }
                    removed.add(xor_cell)
                    removed.add(and_cell)
                    logger.debug(
                        f"Detected HA pattern: {xor_cell} (XOR) + {and_cell} (AND) -> {ha_cell_name}"
                    )
                    break

    # Detect Full Adder pattern
    if has_fa:
        for xor1_cell, xor1_info in list(cells.items()):
            if xor1_cell in removed or xor1_info.get("type") != "$_XOR_":
                continue

            xor1_a, xor1_b, xor1_y = cell_connections.get(xor1_cell, (None, None, None))
            if xor1_a is None or xor1_b is None or xor1_y is None:
                continue

            # Look for second XOR that takes xor1_y as one input (SUM path)
            for xor2_cell, xor2_info in cells.items():
                if xor2_cell in removed or xor2_cell == xor1_cell:
                    continue
                if xor2_info.get("type") != "$_XOR_":
                    continue

                xor2_a, xor2_b, xor2_y = cell_connections.get(xor2_cell, (None, None, None))
                if xor2_a is None or xor2_b is None or xor2_y is None:
                    continue

                # Check if second XOR uses first XOR's output
                ci = None
                if xor2_a == xor1_y:
                    ci = xor2_b
                elif xor2_b == xor1_y:
                    ci = xor2_a
                else:
                    continue

                # ------------------------------------------------------------------
                # Variant 1 (textbook form):
                #   CARRY = (A & B) | (CI & (A ^ B))
                # ------------------------------------------------------------------
                and1_cell: Optional[str] = None
                and1_y: Optional[int] = None
                and2_cell: Optional[str] = None
                and2_y: Optional[int] = None

                for and_cell, and_info in cells.items():
                    if and_cell in removed or and_cell in (xor1_cell, xor2_cell):
                        continue
                    if and_info.get("type") != "$_AND_":
                        continue

                    and_a, and_b, and_y = cell_connections.get(and_cell, (None, None, None))
                    if and_a is None or and_b is None or and_y is None:
                        continue

                    # AND(A, B)
                    if and1_cell is None and (
                        (and_a, and_b) == (xor1_a, xor1_b)
                        or (and_a, and_b) == (xor1_b, xor1_a)
                    ):
                        and1_cell = and_cell
                        and1_y = and_y
                        continue

                    # AND(CI, xor1_y)
                    if and2_cell is None and (
                        (and_a, and_b) == (ci, xor1_y)
                        or (and_a, and_b) == (xor1_y, ci)
                    ):
                        and2_cell = and_cell
                        and2_y = and_y

                fa_built = False

                if and1_cell is not None and and2_cell is not None:
                    # Look for OR(temp2, temp3) -> CARRY
                    or_cell: Optional[str] = None
                    or_y: Optional[int] = None
                    for or_cell_name, or_info in cells.items():
                        if or_cell_name in removed or or_cell_name in (
                            xor1_cell,
                            xor2_cell,
                            and1_cell,
                            and2_cell,
                        ):
                            continue
                        if or_info.get("type") != "$_OR_":
                            continue

                        or_a, or_b, or_y_val = cell_connections.get(
                            or_cell_name, (None, None, None)
                        )
                        if or_a is None or or_b is None or or_y_val is None:
                            continue

                        if (or_a, or_b) == (and1_y, and2_y) or (
                            or_a,
                            or_b,
                        ) == (and2_y, and1_y):
                            or_cell = or_cell_name
                            or_y = or_y_val
                            break

                    if or_cell is not None:
                        fa_cell_name = f"FA_{xor1_cell}"
                        rewritten_cells[fa_cell_name] = {
                            "type": "FA",
                            "connections": {
                                "A": [xor1_a],
                                "B": [xor1_b],
                                "CI": [ci],
                                "SUM": [xor2_y],
                                "CARRY": [or_y],
                            },
                            "port_directions": {
                                "A": "input",
                                "B": "input",
                                "CI": "input",
                                "SUM": "output",
                                "CARRY": "output",
                            },
                        }
                        removed.update(
                            {xor1_cell, xor2_cell, and1_cell, and2_cell, or_cell}
                        )
                        logger.debug(
                            "Detected FA pattern (2-AND/1-OR form): "
                            f"{xor1_cell}, {xor2_cell}, {and1_cell}, "
                            f"{and2_cell}, {or_cell} -> {fa_cell_name}"
                        )
                        fa_built = True

                # ------------------------------------------------------------------
                # Variant 2 (CSA-style form used in configurable_carry_select_adder):
                #   CARRY = (A & B) | (A & CI) | (B & CI)
                #   Implemented as three AND2 and two OR2 forming an OR3 tree.
                # ------------------------------------------------------------------
                if not fa_built:
                    # Find three AND gates: (A&B), (A&CI), (B&CI)
                    and_ab_cell: Optional[str] = None
                    and_ab_y: Optional[int] = None
                    and_aci_cell: Optional[str] = None
                    and_aci_y: Optional[int] = None
                    and_bci_cell: Optional[str] = None
                    and_bci_y: Optional[int] = None

                    for and_cell, and_info in cells.items():
                        if and_cell in removed or and_cell in (xor1_cell, xor2_cell):
                            continue
                        if and_info.get("type") != "$_AND_":
                            continue

                        and_a, and_b, and_y = cell_connections.get(
                            and_cell, (None, None, None)
                        )
                        if and_a is None or and_b is None or and_y is None:
                            continue

                        pair = {and_a, and_b}
                        if pair == {xor1_a, xor1_b} and and_ab_cell is None:
                            and_ab_cell = and_cell
                            and_ab_y = and_y
                        elif pair == {xor1_a, ci} and and_aci_cell is None:
                            and_aci_cell = and_cell
                            and_aci_y = and_y
                        elif pair == {xor1_b, ci} and and_bci_cell is None:
                            and_bci_cell = and_cell
                            and_bci_y = and_y

                    if (
                        and_ab_cell is None
                        or and_aci_cell is None
                        or and_bci_cell is None
                    ):
                        continue

                    and_outputs = {
                        and_ab_y,
                        and_aci_y,
                        and_bci_y,
                    }

                    # Find two OR2 gates that form an OR3 tree whose leaves are
                    # exactly the three AND outputs above.
                    or_candidates = [
                        name
                        for name, info in cells.items()
                        if info.get("type") == "$_OR_" and name not in removed
                    ]

                    fa_or_root: Optional[str] = None
                    fa_or_inner: Optional[str] = None
                    carry_net: Optional[int] = None

                    for or1 in or_candidates:
                        if or1 in removed:
                            continue
                        or1_a, or1_b, or1_y = cell_connections.get(
                            or1, (None, None, None)
                        )
                        if or1_a is None or or1_b is None or or1_y is None:
                            continue

                        for or2 in or_candidates:
                            if or2 == or1 or or2 in removed:
                                continue
                            or2_a, or2_b, or2_y = cell_connections.get(
                                or2, (None, None, None)
                            )
                            if or2_a is None or or2_b is None or or2_y is None:
                                continue

                            # Require that one OR's output feeds the other.
                            if or1_y == or2_a:
                                inner_y = or1_y
                                leaf_nets = {or1_a, or1_b, or2_b}
                                root_cell = or2
                                inner_cell = or1
                                root_y = or2_y
                            elif or1_y == or2_b:
                                inner_y = or1_y
                                leaf_nets = {or1_a, or1_b, or2_a}
                                root_cell = or2
                                inner_cell = or1
                                root_y = or2_y
                            elif or2_y == or1_a:
                                inner_y = or2_y
                                leaf_nets = {or2_a, or2_b, or1_b}
                                root_cell = or1
                                inner_cell = or2
                                root_y = or1_y
                            elif or2_y == or1_b:
                                inner_y = or2_y
                                leaf_nets = {or2_a, or2_b, or1_a}
                                root_cell = or1
                                inner_cell = or2
                                root_y = or1_y
                            else:
                                continue

                            # Leaf nets must be exactly the three AND outputs.
                            if leaf_nets != and_outputs:
                                continue

                            fa_or_root = root_cell
                            fa_or_inner = inner_cell
                            carry_net = root_y
                            break

                        if fa_or_root is not None:
                            break

                    if fa_or_root is None or fa_or_inner is None or carry_net is None:
                        continue

                    fa_cell_name = f"FA_{xor1_cell}"
                    rewritten_cells[fa_cell_name] = {
                        "type": "FA",
                        "connections": {
                            "A": [xor1_a],
                            "B": [xor1_b],
                            "CI": [ci],
                            "SUM": [xor2_y],
                            "CARRY": [carry_net],
                        },
                        "port_directions": {
                            "A": "input",
                            "B": "input",
                            "CI": "input",
                            "SUM": "output",
                            "CARRY": "output",
                        },
                    }

                    removed.update(
                        {
                            xor1_cell,
                            xor2_cell,
                            and_ab_cell,
                            and_aci_cell,
                            and_bci_cell,
                            fa_or_root,
                            fa_or_inner,
                        }
                    )
                    logger.debug(
                        "Detected FA pattern (3-AND/2-OR CSA form): "
                        f"{xor1_cell}, {xor2_cell}, {and_ab_cell}, "
                        f"{and_aci_cell}, {and_bci_cell}, "
                        f"{fa_or_root}, {fa_or_inner} -> {fa_cell_name}"
                    )

                # Whether we matched variant 1 or 2, once we have built an FA
                # for this xor1/xor2 pair we should not reuse these gates again.
                if fa_built or fa_or_root is not None:
                    break

    # Remove detected cells from the rewritten dict
    for cell_name in removed:
        rewritten_cells.pop(cell_name, None)

    if removed:
        logger.info(f"Detected {len(removed)} gate(s) forming FA/HA patterns, replaced with {len(removed) // 2 if has_ha else len(removed) // 5} adder cell(s)")

    return rewritten_cells


def _collapse_associative_gate_chains(
    module_data: Dict[str, Any],
    cells: Dict[str, Any],
    cell_library: CellLibrary,
    *,
    max_arity: int = 4,
) -> Dict[str, Any]:
    """Collapse safe cascades of 2-input associative gates into N-input gates.

    This is a *generic* peephole optimization intended to reduce gate count and
    produce more human-meaningful cells (e.g., AND3/AND4), which can improve
    downstream module identification.

    Safety rules (conservative):
    - Only collapses Yosys internal 2-input associative gates: $_AND_, $_OR_, $_NAND_, $_NOR_
    - Only collapses when intermediate nets are single-fanout (used as an input exactly once)
    - Never collapses through module output ports (to avoid surprising boundary changes)
    - Only collapses up to `max_arity` inputs
    - Only collapses if the target N-input cell exists in `cell_library`

    Args:
        module_data: Yosys module JSON data.
        cells: Cells dict from Yosys module.
        cell_library: Cell library (used to check N-input cell availability).
        max_arity: Maximum N-input gate size to create (default: 4).

    Returns:
        Potentially rewritten `cells` dict with some cells removed/replaced.
    """
    if max_arity < 3:
        return cells

    # Quick exit if library doesn't support any N-input gates.
    has_any_multi = any(
        f"{base}{n}" in cell_library.cells
        for base in ("AND", "OR", "NAND", "NOR", "XOR", "XNOR")
        for n in range(3, max_arity + 1)
    )
    if not has_any_multi:
        return cells

    # Collect module output bits so we don't collapse through boundary nets.
    output_port_bits: Set[int] = set()
    ports = module_data.get("ports", {})
    for port_info in ports.values():
        if port_info.get("direction") == "output":
            for bit in port_info.get("bits", []):
                if isinstance(bit, int):
                    output_port_bits.add(bit)

    # Count fanout of each signal ID by scanning *inputs* of all cells.
    # Also record each cell's scalar A/B/Y connections (if present).
    fanout: Dict[int, int] = {}
    cell_ab_y: Dict[str, Tuple[Optional[int], Optional[int], Optional[int]]] = {}
    out_net_to_cell: Dict[int, str] = {}

    def _first_int(sig_list: Any) -> Optional[int]:
        if isinstance(sig_list, list) and sig_list and isinstance(sig_list[0], int):
            return sig_list[0]
        if isinstance(sig_list, int):
            return sig_list
        return None

    for cell_name, cell_info in cells.items():
        ctype = cell_info.get("type", "")
        conns = cell_info.get("connections", {})

        a = _first_int(conns.get("A", []))
        b = _first_int(conns.get("B", []))
        y = _first_int(conns.get("Y", []))
        cell_ab_y[cell_name] = (a, b, y)
        if y is not None:
            out_net_to_cell[y] = cell_name

        # Fanout counts: count uses of A/B as inputs.
        # This is intentionally conservative and ignores other ports.
        for net in (a, b):
            if net is None:
                continue
            fanout[net] = fanout.get(net, 0) + 1

    # If there are no candidate gate types, exit.
    if not any(c.get("type") in _ASSOCIATIVE_2INPUT_TYPES for c in cells.values()):
        return cells

    removed: Set[str] = set()
    rewritten_cells: Dict[str, Any] = dict(cells)

    def _collect_leaf_inputs(
        cell_name: str,
        gate_type: str,
        net: int,
        visited_cells: Set[str],
        leaf_inputs: List[int],
    ) -> None:
        """Collect leaf input nets for `net`, expanding same-type producers when safe."""
        if len(leaf_inputs) >= max_arity:
            leaf_inputs.append(net)
            return

        producer = out_net_to_cell.get(net)
        if not producer:
            leaf_inputs.append(net)
            return

        if producer == cell_name:
            leaf_inputs.append(net)
            return

        if producer in visited_cells or producer in removed:
            leaf_inputs.append(net)
            return

        p_info = rewritten_cells.get(producer)
        if not p_info or p_info.get("type") != gate_type:
            leaf_inputs.append(net)
            return

        # Only collapse through internal, single-fanout nets.
        if net in output_port_bits:
            leaf_inputs.append(net)
            return

        if fanout.get(net, 0) != 1:
            leaf_inputs.append(net)
            return

        pa, pb, py = cell_ab_y.get(producer, (None, None, None))
        if py is None or py != net or pa is None or pb is None:
            leaf_inputs.append(net)
            return

        visited_cells.add(producer)
        _collect_leaf_inputs(cell_name, gate_type, pa, visited_cells, leaf_inputs)
        _collect_leaf_inputs(cell_name, gate_type, pb, visited_cells, leaf_inputs)

    # Main rewrite pass: for each candidate cell, attempt to expand its A/B into leaf inputs.
    for cell_name, cell_info in list(rewritten_cells.items()):
        if cell_name in removed:
            continue

        gate_type = cell_info.get("type", "")
        base = _ASSOCIATIVE_2INPUT_TYPES.get(gate_type)
        if not base:
            continue

        a, b, y = cell_ab_y.get(cell_name, (None, None, None))
        if a is None or b is None or y is None:
            continue

        # Expand leaf inputs.
        visited: Set[str] = set()
        leaf_inputs: List[int] = []
        _collect_leaf_inputs(cell_name, gate_type, a, visited, leaf_inputs)
        _collect_leaf_inputs(cell_name, gate_type, b, visited, leaf_inputs)

        # Remove duplicates while preserving order (can happen in weird degenerate nets).
        deduped: List[int] = []
        seen_nets: Set[int] = set()
        for n in leaf_inputs:
            if n in seen_nets:
                continue
            seen_nets.add(n)
            deduped.append(n)

        if len(deduped) <= 2:
            continue

        if len(deduped) > max_arity:
            continue

        target_cell = f"{base}{len(deduped)}"
        if target_cell not in cell_library.cells:
            continue

        # Rewrite this cell to the N-input gate, and mark producers for removal.
        # Preserve instance name (cell_name) and output Y net.
        new_conns: Dict[str, List[int]] = {}
        for idx, net_id in enumerate(deduped):
            pin = chr(ord("A") + idx)  # A, B, C, D...
            new_conns[pin] = [net_id]
        new_conns["Y"] = [y]

        rewritten_cells[cell_name] = {
            **cell_info,
            "type": target_cell,
            "connections": new_conns,
        }

        for producer in visited:
            removed.add(producer)

    if removed:
        for r in removed:
            rewritten_cells.pop(r, None)
        logger.info(
            f"Collapsed associative gate chains: removed {len(removed)} intermediate cells"
        )

    return rewritten_cells


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
        # For Yosys-generated flattened netlists, keep X_ prefix for MOSFETs
        # to match the format that Yosys produces (X_ prefixes for all flattened instances)
        base_instance_name = instance_name
        inst_name_to_use = inst_name
        
        # If expanding X_ subcircuit to M transistor, use X_ prefix to match Yosys format
        if inst_name[0].upper() == "M" and instance_name[0].upper() == "X":
            # Replace M prefix with X prefix in the transistor instance name
            inst_name_to_use = "X" + inst_name[1:] if len(inst_name) > 1 else inst_name
        
        new_inst_name = (
            f"{instance_prefix}{base_instance_name}_{inst_name_to_use}"
            if instance_prefix
            else f"{base_instance_name}_{inst_name_to_use}"
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
            # Convert X_ prefix to clean prefix for nested expansion
            clean_instance_name = base_instance_name if instance_name[0].upper() == "X" else instance_name
            nested_prefix = (
                f"{instance_prefix}{clean_instance_name}_"
                if instance_prefix
                else f"{clean_instance_name}_"
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
