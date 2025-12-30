"""SPICE subcircuit parser for extracting transistor-level definitions."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SubcircuitDefinition:
    """SPICE subcircuit definition.

    Attributes:
        name: Subcircuit name
        ports: List of port names in order
        instances: List of instance statements (transistors or subcircuit calls)
        lines: Raw lines of the subcircuit definition
    """

    def __init__(
        self,
        name: str,
        ports: List[str],
        instances: List[str],
        lines: List[str],
    ) -> None:
        """Initialize SubcircuitDefinition.

        Args:
            name: Subcircuit name
            ports: List of port names
            instances: List of instance statements
            lines: Raw lines of the subcircuit
        """
        self.name = name
        self.ports = ports
        self.instances = instances
        self.lines = lines

    def __repr__(self) -> str:
        """String representation."""
        return f"SubcircuitDefinition(name={self.name}, ports={self.ports}, instances={len(self.instances)})"


def parse_subcircuit_line(line: str) -> Optional[Tuple[str, List[str]]]:
    """Parse a .SUBCKT line to extract name and ports.

    Args:
        line: SPICE .SUBCKT line

    Returns:
        Tuple of (name, ports) or None if not a valid .SUBCKT line
    """
    line = line.strip()
    if not line.upper().startswith(".SUBCKT"):
        return None

    # Remove .SUBCKT keyword
    rest = line[7:].strip()
    if not rest:
        return None

    # Split by whitespace
    parts = rest.split()
    if not parts:
        return None

    name = parts[0]
    ports = parts[1:] if len(parts) > 1 else []

    return (name, ports)


def is_instance_line(line: str) -> bool:
    """Check if a line is a SPICE instance statement.

    Args:
        line: Line to check

    Returns:
        True if the line is an instance statement (transistor or subcircuit call)
    """
    line = line.strip()
    if not line:
        return False

    # Instance lines start with M (transistor) or X (subcircuit call)
    # They can also have a + continuation marker
    first_char = line[0].upper()
    return first_char in ("M", "X") or line.startswith("+") or line.startswith("*")


def parse_spice_subcircuits(spice_content: str) -> Dict[str, SubcircuitDefinition]:
    """Parse SPICE content to extract all subcircuit definitions.

    Args:
        spice_content: SPICE file content as string

    Returns:
        Dictionary mapping subcircuit names to SubcircuitDefinition objects
    """
    subcircuits: Dict[str, SubcircuitDefinition] = {}
    lines = spice_content.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for .SUBCKT
        subcircuit_info = parse_subcircuit_line(line)
        if subcircuit_info:
            name, ports = subcircuit_info

            # Collect subcircuit body until .ENDS
            subcircuit_lines = [line]
            instance_lines: List[str] = []
            i += 1

            while i < len(lines):
                current_line = lines[i]
                subcircuit_lines.append(current_line)

                # Check for .ENDS
                if current_line.strip().upper().startswith(".ENDS"):
                    # Check if .ENDS has a name (should match subcircuit name)
                    ends_rest = current_line[5:].strip()
                    if ends_rest and ends_rest != name:
                        logger.warning(
                            f"Subcircuit {name} ends with different name: {ends_rest}"
                        )
                    break

                # Check for instance statements
                if is_instance_line(current_line):
                    instance_lines.append(current_line.strip())

                i += 1

            # Create subcircuit definition
            subcircuits[name] = SubcircuitDefinition(
                name=name,
                ports=ports,
                instances=instance_lines,
                lines=subcircuit_lines,
            )

            logger.debug(
                f"Parsed subcircuit: {name} with {len(instance_lines)} instances"
            )

        i += 1

    logger.info(f"Parsed {len(subcircuits)} subcircuits from SPICE content")
    return subcircuits


def extract_model_definitions(spice_content: str) -> Dict[str, str]:
    """Extract MOSFET model definitions from SPICE content.

    Args:
        spice_content: SPICE file content

    Returns:
        Dictionary mapping model names (NMOS, PMOS) to their .model line
    """
    models: Dict[str, str] = {}
    lines = spice_content.split("\n")

    for line in lines:
        line_stripped = line.strip()
        if line_stripped.upper().startswith(".MODEL"):
            # Parse model line: .MODEL name type (params...)
            match = re.match(r"\.model\s+(\w+)\s+(\w+)", line_stripped, re.IGNORECASE)
            if match:
                model_name = match.group(1)
                model_type = match.group(2)
                models[model_name] = line_stripped
                logger.debug(f"Found model: {model_name} ({model_type})")

    return models


def load_subcircuit_definitions(
    spice_file: Optional[str],
) -> Dict[str, SubcircuitDefinition]:
    """Load subcircuit definitions from SPICE file.

    Args:
        spice_file: Path to SPICE file

    Returns:
        Dictionary mapping subcircuit names to definitions

    Raises:
        FileNotFoundError: If file not found
    """
    if not spice_file:
        return {}

    from pathlib import Path

    spice_path = Path(spice_file)
    if not spice_path.exists():
        raise FileNotFoundError(f"SPICE file not found: {spice_file}")

    content = spice_path.read_text(encoding="utf-8")
    return parse_spice_subcircuits(content)
