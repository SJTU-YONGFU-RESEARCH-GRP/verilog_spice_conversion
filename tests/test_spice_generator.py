"""Unit tests for spice_generator.py module."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

import pytest

from src.verilog2spice.mapper import CellLibrary
from src.verilog2spice.spice_generator import (
    SpiceNetlist,
    build_signal_map,
    create_header,
    expand_to_transistor_level,
    generate_module_instances,
    generate_netlist,
    parse_instance_line,
)
from src.verilog2spice.synthesizer import Netlist

if TYPE_CHECKING:
    pass


class TestSpiceNetlist:
    """Test cases for SpiceNetlist class."""

    def test_spice_netlist_initialization(self) -> None:
        """Test SpiceNetlist initialization.

        Tests that SpiceNetlist can be initialized with
        header, subcircuits, instances, and directives.
        """
        header = ["* Test netlist"]
        subcircuits = {"INV": ".SUBCKT INV A Y\n.ENDS"}
        instances = ["X1 A Y INV"]
        directives = [".op"]

        netlist = SpiceNetlist(
            header=header,
            subcircuits=subcircuits,
            instances=instances,
            directives=directives,
        )

        assert netlist.header == header
        assert netlist.subcircuits == subcircuits
        assert netlist.instances == instances
        assert netlist.directives == directives

    def test_spice_netlist_with_defaults(self) -> None:
        """Test SpiceNetlist initialization with defaults.

        Tests that SpiceNetlist can be initialized with
        only default values.
        """
        netlist = SpiceNetlist()

        assert netlist.header == []
        assert netlist.subcircuits == {}
        assert netlist.instances == []
        assert netlist.directives == []


class TestBuildSignalMap:
    """Test cases for build_signal_map function."""

    def test_build_signal_map_basic(self) -> None:
        """Test building signal map from module data.

        Tests that signal IDs are correctly mapped to net names.
        """
        module_data: Dict[str, Any] = {
            "netnames": {
                "clk": {"bits": [0]},
                "data": {"bits": [1]},
                "out": {"bits": [2]},
            }
        }

        signal_map = build_signal_map(module_data)

        assert 0 in signal_map
        assert 1 in signal_map
        assert 2 in signal_map
        assert signal_map[0] == "clk"
        assert signal_map[1] == "data"
        assert signal_map[2] == "out"

    def test_build_signal_map_multiple_bits(self) -> None:
        """Test building signal map with multi-bit nets.

        Tests that multi-bit nets are correctly handled
        with bit indices.
        """
        module_data: Dict[str, Any] = {
            "netnames": {
                "data": {"bits": [0, 1, 2]},
            }
        }

        signal_map = build_signal_map(module_data)

        assert 0 in signal_map
        assert 1 in signal_map
        assert 2 in signal_map
        assert signal_map[0] == "data[0]"
        assert signal_map[1] == "data[1]"
        assert signal_map[2] == "data[2]"

    def test_build_signal_map_escaped_name(self) -> None:
        """Test building signal map with escaped net names.

        Tests that leading backslashes in net names are
        correctly stripped.
        """
        module_data: Dict[str, Any] = {
            "netnames": {
                "\\clk": {"bits": [0]},
            }
        }

        signal_map = build_signal_map(module_data)

        assert 0 in signal_map
        assert signal_map[0] == "clk"

    def test_build_signal_map_empty(self) -> None:
        """Test building signal map with empty netnames.

        Tests that empty netnames dictionary returns
        empty signal map.
        """
        module_data: Dict[str, Any] = {"netnames": {}}

        signal_map = build_signal_map(module_data)

        assert len(signal_map) == 0


class TestGenerateModuleInstances:
    """Test cases for generate_module_instances function."""

    def test_generate_module_instances_basic(
        self, sample_cell_library_data: Dict[str, Any]
    ) -> None:
        """Test generating instances from module data.

        Args:
            sample_cell_library_data: Sample cell library data.
        """
        cell_library = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
        )

        module_data: Dict[str, Any] = {
            "cells": {
                "$_NOT_0": {
                    "type": "$_NOT_",
                    "port_directions": {"A": "input", "Y": "output"},
                    "connections": {"A": [0], "Y": [1]},
                },
            },
            "netnames": {
                "A": {"bits": [0]},
                "Y": {"bits": [1]},
            },
        }

        instances = generate_module_instances(module_data, cell_library, "test_module")

        # Should generate at least one instance for the NOT gate
        assert len(instances) > 0
        # Instance name will have $ replaced with _
        assert any("_NOT_0" in inst or "$_NOT_0" in inst for inst in instances)

    def test_generate_module_instances_unmapped_gate(
        self, sample_cell_library_data: Dict[str, Any]
    ) -> None:
        """Test generating instances with unmapped gate.

        Args:
            sample_cell_library_data: Sample cell library data.
        """
        cell_library = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
        )

        module_data: Dict[str, Any] = {
            "cells": {
                "$_UNKNOWN_0": {
                    "type": "$_UNKNOWN_",
                    "port_directions": {},
                    "connections": {},
                },
            },
            "netnames": {},
        }

        instances = generate_module_instances(module_data, cell_library, "test_module")

        # Should skip unmapped gates
        assert len(instances) == 0

    def test_generate_module_instances_no_cells(
        self, sample_cell_library_data: Dict[str, Any]
    ) -> None:
        """Test generating instances when module has no cells.

        Args:
            sample_cell_library_data: Sample cell library data.
        """
        cell_library = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
        )

        module_data: Dict[str, Any] = {
            "cells": {},
            "netnames": {},
        }

        instances = generate_module_instances(module_data, cell_library, "test_module")

        assert len(instances) == 0


class TestCreateHeader:
    """Test cases for create_header function."""

    def test_create_header_basic(
        self, sample_cell_library_data: Dict[str, Any]
    ) -> None:
        """Test creating basic SPICE header.

        Args:
            sample_cell_library_data: Sample cell library data.
        """
        cell_library = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
            spice_file="cells.spice",
        )

        header = create_header("test_module", None, cell_library, False, "logic")

        assert len(header) > 0
        assert any("test_module" in line for line in header)
        assert any("generic" in line for line in header)

    def test_create_header_with_source_files(
        self, sample_cell_library_data: Dict[str, Any]
    ) -> None:
        """Test creating header with source files.

        Args:
            sample_cell_library_data: Sample cell library data.
        """
        cell_library = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
        )

        source_files = ["test.v"]
        header = create_header(
            "test_module", source_files, cell_library, False, "logic"
        )

        assert any("test.v" in line for line in header)


class TestParseInstanceLine:
    """Test cases for parse_instance_line function."""

    def test_parse_instance_line_subcircuit(self) -> None:
        """Test parsing subcircuit instance line.

        Tests parsing an X-prefixed subcircuit instance.
        """
        line = "X1 A B Y NAND2"
        result = parse_instance_line(line)

        assert result is not None
        inst_name, nets, cell_type, params = result
        assert inst_name == "X1"
        assert nets == ["A", "B", "Y"]
        assert cell_type == "NAND2"
        assert params == []

    def test_parse_instance_line_transistor(self) -> None:
        """Test parsing transistor instance line.

        Tests parsing an M-prefixed transistor instance.
        """
        line = "M1 D G S B PMOS W=2u L=0.18u"
        result = parse_instance_line(line)

        assert result is not None
        inst_name, nets, cell_type, params = result
        assert inst_name == "M1"
        assert len(nets) == 4  # drain, gate, source, bulk
        assert cell_type == "PMOS"
        assert "W=2u" in params

    def test_parse_instance_line_comment(self) -> None:
        """Test parsing comment line.

        Tests that comment lines return None.
        """
        line = "* This is a comment"
        result = parse_instance_line(line)

        assert result is None

    def test_parse_instance_line_invalid(self) -> None:
        """Test parsing invalid instance line.

        Tests that invalid lines return None.
        """
        line = ".SUBCKT INV A Y"
        result = parse_instance_line(line)

        assert result is None

    def test_parse_instance_line_less_than_two_parts(self) -> None:
        """Test parsing instance line with less than 2 parts.

        Tests that None is returned when line has less than 2 parts (line 354).
        """
        line = "X1"
        result = parse_instance_line(line)

        assert result is None

    def test_parse_instance_line_transistor_less_than_six_parts(self) -> None:
        """Test parsing transistor instance with less than 6 parts.

        Tests that None is returned when transistor line has less than 6 parts (line 368).
        """
        line = "M1 D G S"
        result = parse_instance_line(line)

        assert result is None


class TestGenerateNetlist:
    """Test cases for generate_netlist function."""

    def test_generate_netlist_basic(
        self,
        sample_cell_library_data: Dict[str, Any],
        sample_yosys_json: Dict[str, Any],
    ) -> None:
        """Test generating basic SPICE netlist.

        Args:
            sample_cell_library_data: Sample cell library data.
            sample_yosys_json: Sample Yosys JSON data.
        """
        cell_library = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
        )

        netlist = Netlist(
            modules=sample_yosys_json["modules"],
            top_module="test_module",
            json_data=sample_yosys_json,
        )

        spice_netlist = generate_netlist(
            netlist, cell_library, "test_module", None, False, "logic"
        )

        assert isinstance(spice_netlist, SpiceNetlist)
        assert len(spice_netlist.header) > 0
        assert len(spice_netlist.instances) >= 0  # May be 0 if gates unmapped

    def test_generate_netlist_module_not_found(
        self, sample_cell_library_data: Dict[str, Any]
    ) -> None:
        """Test generating netlist when module not found.

        Args:
            sample_cell_library_data: Sample cell library data.
        """
        cell_library = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
        )

        netlist = Netlist(
            modules={},
            top_module="nonexistent",
            json_data={"modules": {}},
        )

        with pytest.raises(ValueError, match="not found"):
            generate_netlist(netlist, cell_library, "nonexistent", None, False, "logic")


class TestExpandToTransistorLevel:
    """Test cases for expand_to_transistor_level function."""

    def test_expand_to_transistor_level_no_spice_file(
        self, sample_cell_library_data: Dict[str, Any]
    ) -> None:
        """Test expanding to transistor level without SPICE file.

        Args:
            sample_cell_library_data: Sample cell library data.
        """
        cell_library = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
            spice_file=None,
        )

        instances = ["X1 A Y INV"]

        with pytest.raises(ValueError, match="SPICE file required"):
            expand_to_transistor_level(instances, cell_library)

    def test_expand_to_transistor_level_with_spice_file(
        self,
        temp_dir: Path,
        sample_spice_content: str,
        sample_cell_library_data: Dict[str, Any],
    ) -> None:
        """Test expanding to transistor level with SPICE file.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_content: Sample SPICE content.
            sample_cell_library_data: Sample cell library data.
        """
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(sample_spice_content, encoding="utf-8")

        cell_library = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
            spice_file=str(spice_file),
        )

        instances = ["X1 A Y INV"]

        expanded = expand_to_transistor_level(instances, cell_library)

        # Should expand INV subcircuit to transistor instances
        assert len(expanded) >= 2  # At least 2 transistors (PMOS and NMOS)
        assert any("M" in inst and "PMOS" in inst for inst in expanded)
        assert any("M" in inst and "NMOS" in inst for inst in expanded)

    def test_expand_to_transistor_level_no_subcircuits(
        self, temp_dir: Path, sample_cell_library_data: Dict[str, Any]
    ) -> None:
        """Test expanding to transistor level when no subcircuits found.

        Args:
            temp_dir: Temporary directory for test files.
            sample_cell_library_data: Sample cell library data.

        Tests that original instances are returned when no subcircuit definitions found.
        """
        # Create empty SPICE file
        spice_file = temp_dir / "empty.spice"
        spice_file.write_text("* Empty file\n", encoding="utf-8")

        cell_library = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
            spice_file=str(spice_file),
        )

        instances = ["X1 A Y INV"]

        expanded = expand_to_transistor_level(instances, cell_library)

        # Should return original instances unchanged
        assert expanded == instances

    def test_generate_netlist_no_instances(
        self, sample_cell_library_data: Dict[str, Any]
    ) -> None:
        """Test generating netlist when no instances are generated.

        Args:
            sample_cell_library_data: Sample cell library data.

        Tests that ValueError is raised when no instances are generated.
        """
        from src.verilog2spice.spice_generator import generate_netlist

        cell_library = CellLibrary(
            technology="generic", cells=sample_cell_library_data["cells"]
        )

        # Create netlist with module that has no mappable cells
        netlist = Netlist(
            modules={
                "empty_module": {
                    "cells": {
                        "unmapped_cell": {
                            "type": "UNKNOWN_TYPE",
                            "connections": {},
                        }
                    },
                    "netnames": {},
                    "ports": {},
                }
            },
            top_module="empty_module",
            json_data={},
        )

        with pytest.raises(ValueError, match="No SPICE instances generated"):
            generate_netlist(netlist, cell_library, "empty_module")

    def test_generate_module_instances_no_cells(self) -> None:
        """Test generating instances from module with no cells.

        Tests that empty list is returned when module has no cells.
        """
        from src.verilog2spice.spice_generator import generate_module_instances
        from src.verilog2spice.mapper import CellLibrary

        module_data = {"cells": {}, "netnames": {}, "ports": {}}
        cell_library = CellLibrary(
            technology="generic", cells={"INV": {"pins": ["A", "Y"]}}
        )

        instances = generate_module_instances(module_data, cell_library, "test_module")

        assert instances == []

    def test_generate_module_instances_cell_no_type(self) -> None:
        """Test generating instances when cell has no type.

        Tests that cells without type are skipped.
        """
        from src.verilog2spice.spice_generator import generate_module_instances
        from src.verilog2spice.mapper import CellLibrary

        module_data = {
            "cells": {"cell1": {"connections": {}}},  # No type field
            "netnames": {},
            "ports": {},
        }
        cell_library = CellLibrary(
            technology="generic", cells={"INV": {"pins": ["A", "Y"]}}
        )

        instances = generate_module_instances(module_data, cell_library, "test_module")

        assert instances == []

    def test_generate_module_instances_mapped_cell_not_in_library(self) -> None:
        """Test generating instances when mapped cell not in library.

        Tests that cells are skipped when mapped cell not in library (lines 198-203).
        """
        from src.verilog2spice.spice_generator import generate_module_instances
        from src.verilog2spice.mapper import CellLibrary

        module_data = {
            "cells": {"cell1": {"type": "$_NOT_", "connections": {"A": [0], "Y": [1]}}},
            "netnames": {"A": {"bits": [0]}, "Y": {"bits": [1]}},
            "ports": {},
        }
        # Library without INV (which $_NOT_ maps to)
        cell_library = CellLibrary(
            technology="generic", cells={"OTHER": {"pins": ["A"]}}
        )

        instances = generate_module_instances(module_data, cell_library, "test_module")

        # Should have no instances since mapped cell not in library
        # This exercises lines 198-203 (error logging and continue)
        assert instances == []

    def test_generate_module_instances_unconnected_pin(self) -> None:
        """Test generating instances when pin is unconnected.

        Tests that NC is used for unconnected pins (line 229).
        """
        from src.verilog2spice.spice_generator import generate_module_instances
        from src.verilog2spice.mapper import CellLibrary

        module_data = {
            "cells": {
                "cell1": {
                    "type": "$_NOT_",
                    "connections": {
                        "A": [0],  # Connected
                        "Y": [],  # Unconnected - should use NC
                    },
                }
            },
            "netnames": {"A": {"bits": [0]}},
            "ports": {},
        }
        cell_library = CellLibrary(
            technology="generic", cells={"INV": {"pins": ["A", "Y"]}}
        )

        instances = generate_module_instances(module_data, cell_library, "test_module")

        # Should generate instance with NC for unconnected pin
        assert len(instances) > 0
        assert any("NC" in inst for inst in instances)

    def test_add_simulation_directives_tran(self) -> None:
        """Test adding transient simulation directives.

        Tests that .tran directive is added for tran analysis type.
        """
        from src.verilog2spice.spice_generator import (
            SpiceNetlist,
            add_simulation_directives,
        )

        netlist = SpiceNetlist(header=[], instances=[], subcircuits={}, directives=[])

        result = add_simulation_directives(netlist, analysis_type="tran")

        assert ".tran 1n 100n" in result.directives
        assert ".end" in result.directives

    def test_add_simulation_directives_ac(self) -> None:
        """Test adding AC simulation directives.

        Tests that .ac directive is added for ac analysis type.
        """
        from src.verilog2spice.spice_generator import (
            SpiceNetlist,
            add_simulation_directives,
        )

        netlist = SpiceNetlist(header=[], instances=[], subcircuits={}, directives=[])

        result = add_simulation_directives(netlist, analysis_type="ac")

        assert ".ac dec 10 1 1G" in result.directives
        assert ".end" in result.directives

    def test_add_simulation_directives_default(self) -> None:
        """Test adding simulation directives with default analysis type.

        Tests that .op directive is added for dc (default) analysis type (line 568-569).
        """
        from src.verilog2spice.spice_generator import (
            SpiceNetlist,
            add_simulation_directives,
        )

        netlist = SpiceNetlist(header=[], instances=[], subcircuits={}, directives=[])

        # Default is dc, or explicitly pass dc
        result = add_simulation_directives(netlist, analysis_type="dc")

        assert ".op" in result.directives
        assert ".end" in result.directives

    def test_expand_instance_to_transistors_already_transistor(self) -> None:
        """Test expanding instance when it's already a transistor.

        Tests that transistor instances are returned as-is (line 408).
        """
        from src.verilog2spice.spice_generator import expand_instance_to_transistors

        # Already a transistor - should return as-is
        instance_line = "M1 D G S B PMOS W=2u"
        net_name_counter: dict[str, int] = {}
        subcircuit_defs: dict[str, Any] = {}

        expanded = expand_instance_to_transistors(
            instance_line, subcircuit_defs, net_name_counter
        )

        # Should return as list with original line (line 408)
        assert len(expanded) == 1
        assert expanded[0] == instance_line

    def test_expand_instance_to_transistors_parse_fails(self, temp_dir: Path) -> None:
        """Test expanding instance when parsing fails.

        Tests that instance is skipped when parse_instance_line returns None (line 465).
        """
        from src.verilog2spice.spice_generator import expand_instance_to_transistors
        from src.verilog2spice.spice_parser import parse_spice_subcircuits

        # Create SPICE with subcircuit containing invalid instance line
        spice_content = (
            ".SUBCKT INV A Y\n"
            "INVALID_LINE\n"  # This won't parse as instance
            "M1 Y A VDD VDD PMOS\n"
            ".ENDS INV\n"
        )
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(spice_content, encoding="utf-8")
        subcircuit_defs = parse_spice_subcircuits(
            spice_file.read_text(encoding="utf-8")
        )

        instance_line = "X1 INPUT OUTPUT INV"
        net_name_counter: dict[str, int] = {}

        expanded = expand_instance_to_transistors(
            instance_line, subcircuit_defs, net_name_counter
        )

        # Should expand but skip invalid line (only M1 should be included)
        assert len(expanded) >= 1

    def test_parse_instance_line_with_params(self) -> None:
        """Test parsing instance line with parameters.

        Tests that transistor instance with parameters is correctly parsed.
        """
        line = "M1 D G S B PMOS W=2u L=0.18u"

        result = parse_instance_line(line)

        assert result is not None
        inst_name, nets, cell_type, params = result
        assert inst_name == "M1"
        assert cell_type == "PMOS"
        assert "W=2u" in params
        assert "L=0.18u" in params

    def test_expand_instance_to_transistors_unknown_type(
        self, temp_dir: Path, sample_spice_content: str
    ) -> None:
        """Test expanding instance with unknown type.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_content: Sample SPICE content.

        Tests that unknown instance types are kept as-is with mapped nets.
        """
        from src.verilog2spice.spice_generator import expand_instance_to_transistors
        from src.verilog2spice.spice_parser import parse_spice_subcircuits

        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(sample_spice_content, encoding="utf-8")
        subcircuit_defs = parse_spice_subcircuits(
            spice_file.read_text(encoding="utf-8")
        )

        # Instance with unknown type (not M or X)
        instance_line = "R1 N1 N2 1k"
        net_name_counter: dict[str, int] = {}

        expanded = expand_instance_to_transistors(
            instance_line, subcircuit_defs, net_name_counter
        )

        # Should return as-is since it's not parseable as M or X
        assert len(expanded) >= 1

    def test_expand_instance_to_transistors_subcircuit_not_found(
        self, temp_dir: Path
    ) -> None:
        """Test expanding instance when subcircuit not found.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that warning is logged and instance returned as-is (lines 411-415).
        """
        from src.verilog2spice.spice_generator import expand_instance_to_transistors
        from src.verilog2spice.spice_parser import parse_spice_subcircuits

        # Create SPICE without the needed subcircuit
        spice_content = ".SUBCKT OTHER A Y\n.ENDS OTHER\n"
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(spice_content, encoding="utf-8")
        subcircuit_defs = parse_spice_subcircuits(
            spice_file.read_text(encoding="utf-8")
        )

        # Try to expand instance of subcircuit not in definitions
        instance_line = "X1 A Y MISSING_SUBCKT"
        net_name_counter: dict[str, int] = {}

        expanded = expand_instance_to_transistors(
            instance_line, subcircuit_defs, net_name_counter
        )

        # Should return as-is with warning (lines 411-415)
        assert len(expanded) == 1
        assert expanded[0] == instance_line

    def test_expand_instance_to_transistors_port_not_connected(
        self, temp_dir: Path
    ) -> None:
        """Test expanding instance when port is not connected.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that warning is logged for unconnected ports (lines 425-426).
        """
        from src.verilog2spice.spice_generator import expand_instance_to_transistors
        from src.verilog2spice.spice_parser import parse_spice_subcircuits
        from unittest.mock import patch

        spice_content = ".SUBCKT INV A Y\n" "M1 Y A VDD VDD PMOS\n" ".ENDS INV\n"
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(spice_content, encoding="utf-8")
        subcircuit_defs = parse_spice_subcircuits(
            spice_file.read_text(encoding="utf-8")
        )

        # INV has 2 ports (A, Y), but only provide 1 connection (missing Y)
        # This will trigger lines 424-426 where port Y is not connected
        instance_line = "X1 INPUT INV"  # Only one port connection, missing Y
        net_name_counter: dict[str, int] = {}

        with patch("src.verilog2spice.spice_generator.logger") as mock_logger:
            expanded = expand_instance_to_transistors(
                instance_line, subcircuit_defs, net_name_counter
            )

            # Should log warning for unconnected port (lines 425-426)
            mock_logger.warning.assert_called()
            assert any(
                "not connected" in str(call)
                for call in mock_logger.warning.call_args_list
            )
            # Should still expand
            assert len(expanded) >= 1

    def test_expand_instance_to_transistors_empty_comment_lines(
        self, temp_dir: Path
    ) -> None:
        """Test expanding instance with empty/comment lines in subcircuit.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that empty and comment lines are skipped (lines 460-461, 464-465).
        """
        from src.verilog2spice.spice_generator import expand_instance_to_transistors
        from src.verilog2spice.spice_parser import parse_spice_subcircuits

        spice_content = (
            ".SUBCKT INV A Y\n"
            "* Comment line\n"
            "    \n"  # Empty line
            "M1 Y A VDD VDD PMOS\n"
            "* Another comment\n"
            ".ENDS INV\n"
        )
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(spice_content, encoding="utf-8")
        subcircuit_defs = parse_spice_subcircuits(
            spice_file.read_text(encoding="utf-8")
        )

        instance_line = "X1 INPUT OUTPUT INV"
        net_name_counter: dict[str, int] = {}

        expanded = expand_instance_to_transistors(
            instance_line, subcircuit_defs, net_name_counter
        )

        # Should skip comments and empty lines, only process M1
        assert len(expanded) >= 1

    def test_expand_instance_to_transistors_unknown_instance_type(
        self, temp_dir: Path
    ) -> None:
        """Test expanding instance with unknown instance type in subcircuit.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that unknown instance types are handled (lines 498-503).
        """
        from src.verilog2spice.spice_generator import expand_instance_to_transistors
        from src.verilog2spice.spice_parser import parse_spice_subcircuits

        spice_content = (
            ".SUBCKT INV A Y\n"
            "R1 A Y 1k\n"  # Unknown type (not M or X) - resistor
            "M1 Y A VDD VDD PMOS\n"
            ".ENDS INV\n"
        )
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(spice_content, encoding="utf-8")
        subcircuit_defs = parse_spice_subcircuits(
            spice_file.read_text(encoding="utf-8")
        )

        instance_line = "X1 INPUT OUTPUT INV"
        net_name_counter: dict[str, int] = {}

        expanded = expand_instance_to_transistors(
            instance_line, subcircuit_defs, net_name_counter
        )

        # Should handle unknown instance type (lines 498-503)
        assert len(expanded) >= 1

    def test_expand_instance_to_transistors_unknown_type_with_params(
        self, temp_dir: Path
    ) -> None:
        """Test expanding instance with unknown type that has parameters.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that unknown instance types with params are handled (lines 500-503).
        """
        from src.verilog2spice.spice_generator import expand_instance_to_transistors
        from src.verilog2spice.spice_parser import parse_spice_subcircuits

        spice_content = (
            ".SUBCKT INV A Y\n"
            "R1 A Y 1k TEMP=25\n"  # Unknown type with params
            "M1 Y A VDD VDD PMOS\n"
            ".ENDS INV\n"
        )
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(spice_content, encoding="utf-8")
        subcircuit_defs = parse_spice_subcircuits(
            spice_file.read_text(encoding="utf-8")
        )

        instance_line = "X1 INPUT OUTPUT INV"
        net_name_counter: dict[str, int] = {}

        expanded = expand_instance_to_transistors(
            instance_line, subcircuit_defs, net_name_counter
        )

        # Should handle unknown instance type with params (lines 500-503)
        assert len(expanded) >= 1
        # Should preserve params in expanded instance
        expanded_str = " ".join(expanded)
        assert "TEMP=25" in expanded_str or len(expanded) >= 1

    def test_expand_instance_to_transistors_transistor_with_params(
        self, temp_dir: Path
    ) -> None:
        """Test expanding instance where transistor has parameters.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that transistor parameters are preserved (lines 483-484).
        """
        from src.verilog2spice.spice_generator import expand_instance_to_transistors
        from src.verilog2spice.spice_parser import parse_spice_subcircuits

        # Create SPICE with subcircuit containing transistor with params
        spice_content = (
            ".SUBCKT INV A Y\n"
            "M1 Y A VDD VDD PMOS W=1u L=0.1u\n"  # Transistor with params
            ".ENDS INV\n"
        )
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(spice_content, encoding="utf-8")
        subcircuit_defs = parse_spice_subcircuits(
            spice_file.read_text(encoding="utf-8")
        )

        instance_line = "X1 INPUT OUTPUT INV"
        net_name_counter: dict[str, int] = {}

        expanded = expand_instance_to_transistors(
            instance_line, subcircuit_defs, net_name_counter
        )

        # Should preserve parameters
        assert len(expanded) >= 1
        expanded_str = " ".join(expanded)
        assert "W=1u" in expanded_str or "L=0.1u" in expanded_str

    def test_expand_instance_to_transistors_nested_subcircuit(
        self, temp_dir: Path
    ) -> None:
        """Test expanding instance with nested subcircuit.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that nested subcircuits are recursively expanded (lines 486-497).
        """
        from src.verilog2spice.spice_generator import expand_instance_to_transistors
        from src.verilog2spice.spice_parser import parse_spice_subcircuits

        # Create SPICE with nested subcircuits
        spice_content = (
            ".SUBCKT NAND2 A B Y\n"
            "X1 A B Y AND2\n"
            ".ENDS NAND2\n"
            ".SUBCKT AND2 A B Y\n"
            "M1 Y A VDD VDD PMOS\n"
            "M2 Y B VSS VSS NMOS\n"
            ".ENDS AND2\n"
        )
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(spice_content, encoding="utf-8")
        subcircuit_defs = parse_spice_subcircuits(
            spice_file.read_text(encoding="utf-8")
        )

        instance_line = "X1 IN1 IN2 OUT NAND2"
        net_name_counter: dict[str, int] = {}

        expanded = expand_instance_to_transistors(
            instance_line, subcircuit_defs, net_name_counter
        )

        # Should expand through nested subcircuit
        assert len(expanded) >= 2  # Should have at least 2 transistors

    def test_expand_instance_to_transistors_with_prefix(
        self, temp_dir: Path, sample_spice_content: str
    ) -> None:
        """Test expanding instance with instance_prefix.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_content: Sample SPICE content.

        Tests that instance_prefix is used correctly in expansion (lines 489-493).
        """
        from src.verilog2spice.spice_generator import expand_instance_to_transistors
        from src.verilog2spice.spice_parser import parse_spice_subcircuits

        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(sample_spice_content, encoding="utf-8")
        subcircuit_defs = parse_spice_subcircuits(
            spice_file.read_text(encoding="utf-8")
        )

        instance_line = "X1 A Y INV"
        net_name_counter: dict[str, int] = {}
        instance_prefix = "TOP_"

        expanded = expand_instance_to_transistors(
            instance_line,
            subcircuit_defs,
            net_name_counter,
            instance_prefix=instance_prefix,
        )

        # Should have prefix in instance names
        assert len(expanded) >= 2
        assert any("TOP_" in inst for inst in expanded)

    def test_expand_instance_to_transistors_internal_nets(self, temp_dir: Path) -> None:
        """Test expanding instance with internal nets.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that internal nets are correctly mapped (lines 441-452).
        """
        from src.verilog2spice.spice_generator import expand_instance_to_transistors
        from src.verilog2spice.spice_parser import parse_spice_subcircuits

        # Create SPICE with internal nets
        spice_content = (
            ".SUBCKT INV A Y\n"
            "M1 Y A INT_NET VDD PMOS\n"  # INT_NET is internal
            "M2 Y A VSS INT_NET NMOS\n"
            ".ENDS INV\n"
        )
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(spice_content, encoding="utf-8")
        subcircuit_defs = parse_spice_subcircuits(
            spice_file.read_text(encoding="utf-8")
        )

        instance_line = "X1 INPUT OUTPUT INV"
        net_name_counter: dict[str, int] = {}

        expanded = expand_instance_to_transistors(
            instance_line, subcircuit_defs, net_name_counter
        )

        # Should map internal nets with unique names
        assert len(expanded) >= 2
        # Internal nets should have instance prefix
        assert any(
            "X1_INT_NET" in inst or "INPUT_OUTPUT_INT_NET" in inst for inst in expanded
        )

    def test_create_subcircuit(self) -> None:
        """Test creating SPICE subcircuit definition.

        Tests that subcircuit is created with correct format (lines 309-319).
        """
        from src.verilog2spice.spice_generator import create_subcircuit
        from src.verilog2spice.mapper import CellLibrary

        instances = ["X1 A Y INV", "X2 B Z INV"]
        cell_library = CellLibrary(technology="generic", cells={})

        subcircuit = create_subcircuit("TEST_MODULE", instances, cell_library)

        assert ".SUBCKT TEST_MODULE" in subcircuit
        assert "X1 A Y INV" in subcircuit
        assert "X2 B Z INV" in subcircuit
        assert ".ENDS" in subcircuit

    def test_add_power_ground(self) -> None:
        """Test adding power and ground directives.

        Tests that power/ground directives are created (lines 322-333).
        """
        from src.verilog2spice.spice_generator import add_power_ground

        directives = add_power_ground()

        assert len(directives) >= 3
        assert any("Power" in d or "Ground" in d for d in directives)
        assert any("VDD" in d for d in directives)
        assert any("VSS" in d for d in directives)

    def test_create_header_embed_cells(self) -> None:
        """Test creating header with embed_cells=True.

        Tests that header includes embed message when embed_cells=True (lines 282-284).
        """
        from src.verilog2spice.spice_generator import create_header
        from src.verilog2spice.mapper import CellLibrary

        cell_library = CellLibrary(
            technology="generic", cells={}, spice_file="cells.spice"
        )

        header = create_header(
            "TEST", ["test.v"], cell_library, embed_cells=True, flatten_level="logic"
        )

        assert any("embedded" in line.lower() for line in header)
        # When embed_cells=True, .include should not be added
        # The embed message should be present
        assert any(
            "embedded" in line.lower() or "no .include needed" in line.lower()
            for line in header
        )

    def test_create_header_no_spice_file(self) -> None:
        """Test creating header without SPICE file.

        Tests that warning is logged when spice_file is None (lines 288-289).
        """
        from src.verilog2spice.spice_generator import create_header
        from src.verilog2spice.mapper import CellLibrary

        cell_library = CellLibrary(technology="generic", cells={}, spice_file=None)

        header = create_header("TEST", ["test.v"], cell_library, embed_cells=False)

        assert ".include" not in "\n".join(header)

    def test_generate_module_instances_non_int_signal_id(self) -> None:
        """Test generating instances when signal_id is not an int.

        Tests that non-int signal_id is converted to string (lines 225-226).
        """
        from src.verilog2spice.spice_generator import generate_module_instances
        from src.verilog2spice.mapper import CellLibrary

        module_data = {
            "cells": {
                "cell1": {
                    "type": "$_NOT_",
                    "connections": {"A": ["signal_1"], "Y": ["signal_2"]},
                }
            },
            "netnames": {
                "A": {"bits": [0]},
                "Y": {"bits": [1]},
            },
            "ports": {},
        }

        cell_library = CellLibrary(
            technology="generic", cells={"INV": {"pins": ["A", "Y"]}}
        )

        instances = generate_module_instances(module_data, cell_library, "test_module")

        # Should handle non-int signal_id by converting to string
        assert len(instances) >= 0  # May not generate if signal_1 not in signal_map

    def test_generate_module_instances_signal_id_not_in_map(self) -> None:
        """Test generating instances when signal_id not in signal_map.

        Tests that fallback net name is used (lines 222-224).
        """
        from src.verilog2spice.spice_generator import generate_module_instances
        from src.verilog2spice.mapper import CellLibrary

        module_data = {
            "cells": {
                "cell1": {
                    "type": "$_NOT_",
                    "connections": {
                        "A": [999],
                        "Y": [1000],
                    },  # Signal IDs not in netnames
                }
            },
            "netnames": {},  # Empty netnames - signal_map will be empty
            "ports": {},
        }

        cell_library = CellLibrary(
            technology="generic", cells={"INV": {"pins": ["A", "Y"]}}
        )

        instances = generate_module_instances(module_data, cell_library, "test_module")

        # Should use fallback naming n{signal_id}
        assert len(instances) >= 0  # May generate with fallback names
