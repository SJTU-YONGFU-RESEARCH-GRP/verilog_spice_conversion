"""Unit tests for formatter.py module."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from src.verilog2spice.formatter import (
    add_comments,
    flatten_hierarchy,
    format_flattened,
    format_hierarchical,
    load_cell_library_content,
    validate_spice,
)
from src.verilog2spice.spice_generator import SpiceNetlist

if TYPE_CHECKING:
    pass


class TestLoadCellLibraryContent:
    """Test cases for load_cell_library_content function."""

    def test_load_cell_library_content_success(
        self, temp_dir: Path, sample_spice_content: str
    ) -> None:
        """Test loading cell library content from file.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_content: Sample SPICE content.
        """
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(sample_spice_content, encoding="utf-8")

        content = load_cell_library_content(str(spice_file))

        assert content is not None
        assert "INV" in content
        assert ".SUBCKT" in content

    def test_load_cell_library_content_none_path(self) -> None:
        """Test loading cell library content with None path.

        Tests that None is returned when path is None.
        """
        content = load_cell_library_content(None)

        assert content is None

    def test_load_cell_library_content_not_found(self) -> None:
        """Test loading cell library content when file doesn't exist.

        Tests that None is returned when file doesn't exist.
        """
        content = load_cell_library_content("/nonexistent/path.spice")

        assert content is None

    def test_load_cell_library_content_read_error(
        self, temp_dir: Path
    ) -> None:
        """Test loading cell library content when read fails.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that None is returned when file read fails (OSError/IOError).
        """
        from unittest.mock import patch

        spice_file = temp_dir / "cells.spice"
        spice_file.write_text("test", encoding="utf-8")

        # Mock read_text to raise OSError
        with patch.object(Path, "read_text", side_effect=OSError("Permission denied")):
            content = load_cell_library_content(str(spice_file))

        assert content is None


class TestFormatHierarchical:
    """Test cases for format_hierarchical function."""

    def test_format_hierarchical_basic(self) -> None:
        """Test formatting basic hierarchical netlist.

        Tests that hierarchical netlist is correctly formatted.
        """
        netlist = SpiceNetlist(
            header=["* Test netlist"],
            subcircuits={"INV": ".SUBCKT INV A Y\nM1 Y A VDD VDD PMOS\n.ENDS INV"},
            instances=["X1 A Y INV"],
            directives=[".op"],
        )

        formatted = format_hierarchical(netlist)

        assert "* Test netlist" in formatted
        assert ".SUBCKT INV" in formatted
        assert "X1 A Y INV" in formatted

    def test_format_hierarchical_top_level(self) -> None:
        """Test formatting hierarchical netlist with top level.

        Tests that top-level instances are correctly included.
        """
        netlist = SpiceNetlist(
            header=["* Test"],
            instances=["X1 A Y INV", "X2 B Z INV"],
            subcircuits={},
            directives=[],
        )

        formatted = format_hierarchical(netlist)

        assert "X1 A Y INV" in formatted
        assert "X2 B Z INV" in formatted
        assert ".SUBCKT TOP" in formatted
        assert ".ENDS TOP" in formatted

    def test_format_hierarchical_no_instances(self) -> None:
        """Test formatting hierarchical netlist without instances.

        Tests that netlist without instances is still formatted.
        """
        netlist = SpiceNetlist(
            header=["* Test"],
            instances=[],
            subcircuits={"INV": ".SUBCKT INV A Y\n.ENDS INV"},
            directives=[],
        )

        formatted = format_hierarchical(netlist)

        assert "* Test" in formatted
        assert ".SUBCKT INV" in formatted


class TestFormatFlattened:
    """Test cases for format_flattened function."""

    def test_format_flattened_logic_level(self) -> None:
        """Test formatting flattened netlist at logic level.

        Tests that logic-level flattened netlist is correctly formatted.
        """
        netlist = SpiceNetlist(
            header=["* Test netlist"],
            instances=["X1 A Y INV"],
            subcircuits={},
            directives=[],
        )

        cell_library_content = ".SUBCKT INV A Y\n.ENDS INV"

        formatted = format_flattened(
            netlist,
            cell_library_content=cell_library_content,
            flatten_level="logic",
        )

        assert "* Test netlist" in formatted
        assert "X1 A Y INV" in formatted
        assert "Embedded Cell Library Models" in formatted

    def test_format_flattened_transistor_level_no_cell_library(self) -> None:
        """Test formatting flattened netlist at transistor level without cell library.

        Tests that ValueError is raised when cell library is missing.
        """
        netlist = SpiceNetlist(
            header=["* Test netlist"],
            instances=["X1 A Y INV"],
            subcircuits={},
            directives=[],
        )

        with pytest.raises(ValueError, match="Cell library required"):
            format_flattened(
                netlist,
                cell_library_content=".SUBCKT INV A Y\n.ENDS INV",
                flatten_level="transistor",
                cell_library=None,
            )

    def test_format_flattened_no_cell_library_content(self) -> None:
        """Test formatting flattened netlist without cell library content.

        Tests that flattened netlist can be formatted without
        cell library content (for logic level).
        """
        netlist = SpiceNetlist(
            header=["* Test"],
            instances=["X1 A Y INV"],
            subcircuits={},
            directives=[],
        )

        formatted = format_flattened(
            netlist,
            cell_library_content=None,
            flatten_level="logic",
        )

        assert "* Test" in formatted
        assert "X1 A Y INV" in formatted

    def test_format_flattened_transistor_level_with_models(
        self, temp_dir: Path, sample_cell_library_json_file: Path
    ) -> None:
        """Test formatting flattened netlist at transistor level with model extraction.

        Args:
            temp_dir: Temporary directory for test files.
            sample_cell_library_json_file: Sample cell library JSON file fixture.

        Tests that transistor-level flattening extracts and includes MOSFET models.
        """
        from src.verilog2spice.mapper import CellLibrary

        # Create a SPICE file with models
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(
            ".MODEL NMOS NMOS (VTO=0.5 KP=200e-6)\n"
            ".MODEL PMOS PMOS (VTO=-0.5 KP=100e-6)\n"
            ".SUBCKT INV A Y\n"
            "M1 Y A VSS VSS NMOS\n"
            "M2 Y A VDD VDD PMOS\n"
            ".ENDS INV\n",
            encoding="utf-8",
        )

        # Load cell library
        with open(sample_cell_library_json_file, "r", encoding="utf-8") as f:
            import json

            data = json.load(f)
        cell_library = CellLibrary(
            technology=data.get("technology", "generic"),
            cells=data.get("cells", {}),
            spice_file=str(spice_file),
        )

        netlist = SpiceNetlist(
            header=["* Test netlist"],
            instances=["X1 A Y INV"],
            subcircuits={},
            directives=[],
        )

        cell_library_content = spice_file.read_text(encoding="utf-8")

        formatted = format_flattened(
            netlist,
            cell_library_content=cell_library_content,
            flatten_level="transistor",
            cell_library=cell_library,
        )

        assert "* Test netlist" in formatted
        assert "MOSFET Model Definitions" in formatted
        assert ".MODEL NMOS" in formatted
        assert ".MODEL PMOS" in formatted
        assert "Transistor-Level Circuit Instances" in formatted

    def test_format_flattened_transistor_level_expansion_error(
        self, temp_dir: Path, sample_cell_library_json_file: Path
    ) -> None:
        """Test formatting flattened netlist when transistor expansion fails.

        Args:
            temp_dir: Temporary directory for test files.
            sample_cell_library_json_file: Sample cell library JSON file fixture.

        Tests that ValueError/KeyError/FileNotFoundError during expansion are re-raised.
        """
        from src.verilog2spice.mapper import CellLibrary
        from unittest.mock import patch

        # Create a SPICE file
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(".SUBCKT INV A Y\n.ENDS INV\n", encoding="utf-8")

        with open(sample_cell_library_json_file, "r", encoding="utf-8") as f:
            import json

            data = json.load(f)
        cell_library = CellLibrary(
            technology=data.get("technology", "generic"),
            cells=data.get("cells", {}),
            spice_file=str(spice_file),
        )

        netlist = SpiceNetlist(
            header=["* Test"],
            instances=["X1 A Y INV"],
            subcircuits={},
            directives=[],
        )

        # Mock expand_to_transistor_level to raise an error
        with patch("src.verilog2spice.formatter.expand_to_transistor_level", side_effect=ValueError("Expansion failed")):
            with pytest.raises(ValueError, match="Expansion failed"):
                format_flattened(
                    netlist,
                    cell_library_content=None,
                    flatten_level="transistor",
                    cell_library=cell_library,
                )

    def test_format_flattened_with_directives(self) -> None:
        """Test formatting flattened netlist with directives.

        Tests that directives are included in formatted output.
        """
        netlist = SpiceNetlist(
            header=["* Test"],
            instances=["X1 A Y INV"],
            subcircuits={},
            directives=[".op", ".dc VDD 0 1.8 0.1"],
        )

        formatted = format_flattened(netlist, flatten_level="logic")

        assert ".op" in formatted
        assert ".dc VDD 0 1.8 0.1" in formatted

    def test_format_flattened_transistor_header(
        self, temp_dir: Path, sample_cell_library_json_file: Path
    ) -> None:
        """Test formatting flattened netlist with transistor-level header.

        Args:
            temp_dir: Temporary directory for test files.
            sample_cell_library_json_file: Sample cell library JSON file fixture.

        Tests that transistor-level header text is used.
        """
        from src.verilog2spice.mapper import CellLibrary

        # Create a SPICE file
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(".SUBCKT INV A Y\nM1 Y A VSS VSS NMOS\n.ENDS INV\n", encoding="utf-8")

        with open(sample_cell_library_json_file, "r", encoding="utf-8") as f:
            import json

            data = json.load(f)
        cell_library = CellLibrary(
            technology=data.get("technology", "generic"),
            cells=data.get("cells", {}),
            spice_file=str(spice_file),
        )

        netlist = SpiceNetlist(
            header=["* Test"],
            instances=["X1 A Y INV"],
            subcircuits={},
            directives=[],
        )

        formatted = format_flattened(
            netlist, flatten_level="transistor", cell_library=cell_library
        )

        # Should have transistor-level header
        assert "Transistor-Level Circuit Instances" in formatted


class TestFlattenHierarchy:
    """Test cases for flatten_hierarchy function."""

    def test_flatten_hierarchy_basic(self) -> None:
        """Test flattening basic hierarchical netlist.

        Tests that hierarchical netlist is correctly flattened.
        """
        netlist = SpiceNetlist(
            header=["* Test"],
            instances=["X1 A Y INV"],
            subcircuits={"INV": ".SUBCKT INV A Y\n.ENDS INV"},
            directives=[],
        )

        flattened = flatten_hierarchy(netlist)

        assert isinstance(flattened, SpiceNetlist)
        # Note: Current implementation just returns the netlist as-is
        assert flattened.header == netlist.header


class TestAddComments:
    """Test cases for add_comments function."""

    def test_add_comments_basic(self) -> None:
        """Test adding comments to netlist.

        Tests that metadata comments are correctly added.
        """
        netlist_text = ".SUBCKT INV A Y\n.ENDS INV"
        metadata = {"author": "test", "date": "2024-01-01"}

        result = add_comments(netlist_text, metadata)

        assert "* Metadata:" in result
        assert "author: test" in result
        assert "date: 2024-01-01" in result
        assert ".SUBCKT INV A Y" in result

    def test_add_comments_empty_metadata(self) -> None:
        """Test adding comments with empty metadata.

        Tests that empty metadata still adds metadata header.
        """
        netlist_text = ".SUBCKT INV A Y\n.ENDS INV"
        metadata = {}

        result = add_comments(netlist_text, metadata)

        assert "* Metadata:" in result
        assert ".SUBCKT INV A Y" in result


class TestValidateSpice:
    """Test cases for validate_spice function."""

    def test_validate_spice_valid_with_subcircuit(self) -> None:
        """Test validating valid SPICE with subcircuit.

        Tests that valid SPICE netlist with subcircuit passes validation.
        """
        spice_text = ".SUBCKT INV A Y\nM1 Y A VDD VDD PMOS\n.ENDS INV"

        result = validate_spice(spice_text)

        assert result is True

    def test_validate_spice_valid_with_instance(self) -> None:
        """Test validating valid SPICE with instance.

        Tests that valid SPICE netlist with instance passes validation.
        """
        spice_text = "X1 A Y INV"

        result = validate_spice(spice_text)

        assert result is True

    def test_validate_spice_valid_with_transistor(self) -> None:
        """Test validating valid SPICE with transistor.

        Tests that valid SPICE netlist with transistor passes validation.
        """
        spice_text = "M1 D G S B PMOS W=2u L=0.18u"

        result = validate_spice(spice_text)

        assert result is True

    def test_validate_spice_empty(self) -> None:
        """Test validating empty SPICE netlist.

        Tests that empty netlist fails validation.
        """
        spice_text = ""

        result = validate_spice(spice_text)

        assert result is False

    def test_validate_spice_only_comments(self) -> None:
        """Test validating SPICE with only comments.

        Tests that netlist with only comments fails validation.
        """
        spice_text = "* Just comments\n* No actual netlist content"

        result = validate_spice(spice_text)

        assert result is False

    def test_validate_spice_whitespace_only(self) -> None:
        """Test validating SPICE with only whitespace.

        Tests that netlist with only whitespace fails validation.
        """
        spice_text = "   \n\n   "

        result = validate_spice(spice_text)

        assert result is False

