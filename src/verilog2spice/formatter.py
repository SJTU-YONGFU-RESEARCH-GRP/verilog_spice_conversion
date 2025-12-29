"""SPICE netlist formatter module for hierarchical and flattened output."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from .spice_generator import SpiceNetlist

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def load_cell_library_content(spice_file: Optional[str]) -> Optional[str]:
    """Load cell library SPICE file content.
    
    Args:
        spice_file: Path to SPICE cell library file
        
    Returns:
        Cell library content as string, or None if file not found
    """
    if not spice_file:
        return None
    
    spice_path = Path(spice_file)
    if not spice_path.exists():
        logger.warning(f"SPICE cell library file not found: {spice_file}")
        return None
    
    try:
        content = spice_path.read_text(encoding="utf-8")
        logger.info(f"Loaded cell library content from: {spice_file} ({len(content)} bytes)")
        return content
    except Exception as e:
        logger.error(f"Failed to read cell library file '{spice_file}': {e}")
        return None


def format_hierarchical(netlist: SpiceNetlist) -> str:
    """Format SPICE netlist as hierarchical.
    
    Args:
        netlist: SPICE netlist object
        
    Returns:
        Formatted hierarchical SPICE netlist string
    """
    logger.info("Formatting hierarchical SPICE netlist")
    
    lines: List[str] = []
    
    # Add header
    lines.extend(netlist.header)
    lines.append("")
    
    # Add top-level subcircuit
    if netlist.instances:
        lines.append("* Top Level Module")
        lines.append(".SUBCKT TOP")
        for inst in netlist.instances:
            lines.append(f"  {inst}")
        lines.append(".ENDS TOP")
        lines.append("")
    
    # Add subcircuits
    for subcircuit_name, subcircuit_def in netlist.subcircuits.items():
        lines.append(f"* Subcircuit: {subcircuit_name}")
        lines.append(subcircuit_def)
    
    # Add directives (if any - power/ground sources are not added by default)
    if netlist.directives:
        lines.extend(netlist.directives)
    
    return "\n".join(lines)


def format_flattened(
    netlist: SpiceNetlist,
    embed_cells: bool = False,
    cell_library_content: Optional[str] = None,
) -> str:
    """Format SPICE netlist as flattened.
    
    Args:
        netlist: SPICE netlist object
        embed_cells: If True, embed cell library models in output
        cell_library_content: Optional cell library SPICE content to embed
        
    Returns:
        Formatted flattened SPICE netlist string
    """
    logger.info("Formatting flattened SPICE netlist")
    
    lines: List[str] = []
    
    # Add header
    lines.extend(netlist.header)
    
    # Embed cell library if requested
    if embed_cells and cell_library_content:
        lines.append("")
        lines.append("* ============================================================================")
        lines.append("* Embedded Cell Library Models")
        lines.append("* ============================================================================")
        lines.append("")
        lines.append(cell_library_content)
        lines.append("")
        lines.append("* ============================================================================")
        lines.append("* Circuit Instances")
        lines.append("* ============================================================================")
        lines.append("")
    else:
        lines.append("* Flattened Netlist - All instances at top level")
        lines.append("")
    
    # Flatten hierarchy
    flattened_netlist = flatten_hierarchy(netlist)
    
    # Add all instances at top level
    if flattened_netlist.instances:
        for inst in flattened_netlist.instances:
            lines.append(inst)
        lines.append("")
    
    # Add directives (if any - power/ground sources are not added by default)
    if flattened_netlist.directives:
        lines.extend(flattened_netlist.directives)
    
    return "\n".join(lines)


def flatten_hierarchy(netlist: SpiceNetlist) -> SpiceNetlist:
    """Flatten hierarchical netlist structure.
    
    Args:
        netlist: Hierarchical SPICE netlist
        
    Returns:
        Flattened SPICE netlist
        
    Note:
        This is a simplified implementation. A full version would
        recursively expand subcircuits and rename instances.
    """
    logger.debug("Flattening netlist hierarchy")
    
    # For now, just return the netlist as-is
    # In a full implementation, we would:
    # 1. Extract all instances from subcircuits
    # 2. Rename instances with hierarchical paths (e.g., top.sub1.gate1)
    # 3. Resolve port connections
    # 4. Remove subcircuit definitions
    
    return netlist


def add_comments(netlist_text: str, metadata: Dict[str, str]) -> str:
    """Add metadata comments to netlist.
    
    Args:
        netlist_text: SPICE netlist text
        metadata: Dictionary of metadata to add as comments
        
    Returns:
        Netlist text with added comments
    """
    lines = netlist_text.split("\n")
    
    # Add metadata at the beginning
    comment_lines = ["* Metadata:"]
    for key, value in metadata.items():
        comment_lines.append(f"*   {key}: {value}")
    comment_lines.append("")
    
    return "\n".join(comment_lines + lines)


def validate_spice(netlist_text: str) -> bool:
    """Validate SPICE netlist syntax.
    
    Args:
        netlist_text: SPICE netlist text
        
    Returns:
        True if valid, False otherwise
        
    Note:
        This is a basic validation. A full implementation would
        use a SPICE parser or simulator for validation.
    """
    logger.debug("Validating SPICE syntax")
    
    # Basic checks
    if not netlist_text.strip():
        logger.warning("Empty netlist")
        return False
    
    # Check for basic SPICE statements
    lines = netlist_text.split("\n")
    has_subcircuit = False
    has_instance = False
    
    for line in lines:
        line_upper = line.strip().upper()
        if line_upper.startswith(".SUBCKT"):
            has_subcircuit = True
        if line_upper.startswith("X") or line_upper.startswith("M"):
            has_instance = True
    
    # Basic validation passed
    if has_subcircuit or has_instance:
        logger.debug("SPICE syntax validation passed")
        return True
    
    logger.warning("SPICE netlist appears to be empty or invalid")
    return False
