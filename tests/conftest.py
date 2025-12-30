"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Generator

import pytest

if TYPE_CHECKING:
    pass


@pytest.fixture
def sample_cell_library_data() -> Dict[str, Any]:
    """Provide sample cell library data for testing.

    Returns:
        Dictionary containing sample cell library configuration.
    """
    return {
        "technology": "generic",
        "spice_file": "cells.spice",
        "cells": {
            "INV": {
                "spice_model": "INV",
                "pins": ["A", "Y"],
                "parameters": ["W", "L"],
                "description": "Inverter",
            },
            "NAND2": {
                "spice_model": "NAND2",
                "pins": ["A", "B", "Y"],
                "parameters": ["W", "L"],
                "description": "2-input NAND gate",
            },
            "AND2": {
                "spice_model": "AND2",
                "pins": ["A", "B", "Y"],
                "parameters": ["W", "L"],
                "description": "2-input AND gate",
            },
        },
    }


@pytest.fixture
def sample_yosys_json() -> Dict[str, Any]:
    """Provide sample Yosys JSON output for testing.

    Returns:
        Dictionary containing sample Yosys JSON structure.
    """
    return {
        "modules": {
            "test_module": {
                "ports": {
                    "clk": {"direction": "input", "bits": [0]},
                    "rst": {"direction": "input", "bits": [1]},
                    "data": {"direction": "input", "bits": [2]},
                    "out": {"direction": "output", "bits": [3]},
                },
                "cells": {
                    "$_NOT_0": {
                        "type": "$_NOT_",
                        "port_directions": {"A": "input", "Y": "output"},
                        "connections": {"A": [2], "Y": [3]},
                    },
                    "$_AND_0": {
                        "type": "$_AND_",
                        "port_directions": {"A": "input", "B": "input", "Y": "output"},
                        "connections": {"A": [4], "B": [5], "Y": [6]},
                    },
                },
                "netnames": {
                    "clk": {"bits": [0]},
                    "rst": {"bits": [1]},
                    "data": {"bits": [2]},
                    "out": {"bits": [3]},
                },
            }
        }
    }


@pytest.fixture
def sample_spice_content() -> str:
    """Provide sample SPICE subcircuit content for testing.

    Returns:
        String containing sample SPICE subcircuit definitions.
    """
    return """* Sample SPICE subcircuit
.SUBCKT INV A Y
M1 Y A VDD VDD PMOS W=2u L=0.18u
M2 Y A VSS VSS NMOS W=1u L=0.18u
.ENDS INV

.SUBCKT NAND2 A B Y
M1 Y A VDD VDD PMOS W=2u L=0.18u
M2 Y B VDD VDD PMOS W=2u L=0.18u
M3 Y A net1 VSS NMOS W=1u L=0.18u
M4 net1 B VSS VSS NMOS W=1u L=0.18u
.ENDS NAND2

.model NMOS NMOS (LEVEL=1 VTO=0.7)
.model PMOS PMOS (LEVEL=1 VTO=-0.7)
"""


@pytest.fixture
def temp_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide a temporary directory for test files.

    Args:
        tmp_path: Pytest temporary path fixture.

    Yields:
        Path to temporary directory.
    """
    yield tmp_path


@pytest.fixture
def sample_cell_library_json_file(
    temp_dir: Path, sample_cell_library_data: Dict[str, Any]
) -> Generator[Path, None, None]:
    """Create a temporary cell library JSON file for testing.

    Args:
        temp_dir: Temporary directory path.
        sample_cell_library_data: Sample cell library data.

    Yields:
        Path to temporary JSON file.
    """
    import json

    json_file = temp_dir / "cells.json"
    json_file.write_text(json.dumps(sample_cell_library_data, indent=2), encoding="utf-8")
    yield json_file


@pytest.fixture
def sample_spice_file(temp_dir: Path, sample_spice_content: str) -> Generator[Path, None, None]:
    """Create a temporary SPICE file for testing.

    Args:
        temp_dir: Temporary directory path.
        sample_spice_content: Sample SPICE content.

    Yields:
        Path to temporary SPICE file.
    """
    spice_file = temp_dir / "cells.spice"
    spice_file.write_text(sample_spice_content, encoding="utf-8")
    yield spice_file

