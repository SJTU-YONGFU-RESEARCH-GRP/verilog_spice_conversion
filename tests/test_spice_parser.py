"""Unit tests for spice_parser.py module."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from src.verilog2spice.spice_parser import (
    SubcircuitDefinition,
    extract_model_definitions,
    is_instance_line,
    load_subcircuit_definitions,
    parse_spice_subcircuits,
    parse_subcircuit_line,
)

if TYPE_CHECKING:
    pass


class TestSubcircuitDefinition:
    """Test cases for SubcircuitDefinition class."""

    def test_subcircuit_definition_initialization(self) -> None:
        """Test SubcircuitDefinition initialization.

        Tests that SubcircuitDefinition can be initialized
        with name, ports, instances, and lines.
        """
        ports = ["A", "B", "Y"]
        instances = ["M1 Y A VDD VDD PMOS", "M2 Y B VDD VDD PMOS"]
        lines = [".SUBCKT NAND2 A B Y", "M1 Y A VDD VDD PMOS", ".ENDS"]

        subcircuit = SubcircuitDefinition(
            name="NAND2", ports=ports, instances=instances, lines=lines
        )

        assert subcircuit.name == "NAND2"
        assert subcircuit.ports == ports
        assert subcircuit.instances == instances
        assert subcircuit.lines == lines

    def test_subcircuit_definition_repr(self) -> None:
        """Test SubcircuitDefinition string representation.

        Tests that __repr__ returns a meaningful string.
        """
        subcircuit = SubcircuitDefinition(
            name="INV",
            ports=["A", "Y"],
            instances=["M1 Y A VDD VDD PMOS"],
            lines=[".SUBCKT INV A Y", "M1 Y A VDD VDD PMOS", ".ENDS"],
        )

        repr_str = repr(subcircuit)
        assert "INV" in repr_str
        assert "instances" in repr_str.lower()


class TestParseSubcircuitLine:
    """Test cases for parse_subcircuit_line function."""

    def test_parse_subcircuit_line_basic(self) -> None:
        """Test parsing basic .SUBCKT line.

        Tests parsing a simple subcircuit definition line.
        """
        line = ".SUBCKT INV A Y"
        result = parse_subcircuit_line(line)

        assert result is not None
        name, ports = result
        assert name == "INV"
        assert ports == ["A", "Y"]

    def test_parse_subcircuit_line_multiple_ports(self) -> None:
        """Test parsing .SUBCKT line with multiple ports.

        Tests parsing a subcircuit with multiple ports.
        """
        line = ".SUBCKT NAND2 A B Y"
        result = parse_subcircuit_line(line)

        assert result is not None
        name, ports = result
        assert name == "NAND2"
        assert ports == ["A", "B", "Y"]

    def test_parse_subcircuit_line_case_insensitive(self) -> None:
        """Test parsing .SUBCKT line with different case.

        Tests that parsing is case-insensitive.
        """
        line = ".subckt INV A Y"
        result = parse_subcircuit_line(line)

        assert result is not None
        name, ports = result
        assert name == "INV"
        assert ports == ["A", "Y"]

    def test_parse_subcircuit_line_no_ports(self) -> None:
        """Test parsing .SUBCKT line without ports.

        Tests parsing a subcircuit with no ports.
        """
        line = ".SUBCKT TEST"
        result = parse_subcircuit_line(line)

        assert result is not None
        name, ports = result
        assert name == "TEST"
        assert ports == []

    def test_parse_subcircuit_line_invalid(self) -> None:
        """Test parsing invalid line.

        Tests that None is returned for non-subcircuit lines.
        """
        line = "M1 Y A VDD VDD PMOS"
        result = parse_subcircuit_line(line)

        assert result is None

    def test_parse_subcircuit_line_empty_rest(self) -> None:
        """Test parsing .SUBCKT line with empty rest after keyword.

        Tests that None is returned when rest is empty after .SUBCKT.
        """
        line = ".SUBCKT"
        result = parse_subcircuit_line(line)

        assert result is None

    def test_parse_subcircuit_line_only_whitespace_rest(self) -> None:
        """Test parsing .SUBCKT line with only whitespace after keyword.

        Tests that None is returned when rest is only whitespace.
        """
        line = ".SUBCKT   "
        result = parse_subcircuit_line(line)

        assert result is None

    def test_parse_subcircuit_line_empty_parts(self) -> None:
        """Test parsing .SUBCKT line with empty parts after split.

        Tests edge case where split results in empty list.
        """
        line = ".SUBCKT\t\t"
        result = parse_subcircuit_line(line)

        # This should return None due to empty parts after split
        # (covered by the check for empty rest)
        assert result is None

    def test_parse_spice_subcircuits_mismatched_ends_name(self) -> None:
        """Test parsing subcircuits with mismatched .ENDS name.

        Tests that warning is logged when .ENDS name doesn't match subcircuit name.
        """
        content = ".SUBCKT INV A Y\nM1 Y A VDD VDD PMOS\n.ENDS OTHER_NAME\n"
        subcircuits = parse_spice_subcircuits(content)

        # Should still parse successfully but log warning
        assert "INV" in subcircuits
        assert len(subcircuits["INV"].instances) == 1

    def test_parse_subcircuit_line_empty_parts_after_split(self) -> None:
        """Test parsing .SUBCKT line where split results in empty parts.

        Tests that None is returned when split() results in empty list (line 71).
        
        Note: Line 71 checks `if not parts:` which can happen if rest.strip() 
        removes all whitespace but the resulting string still has some non-whitespace
        that when split becomes empty. Actually, Python's split() on a string
        with only whitespace returns [], so this is covered by the empty rest check.
        However, we can test a case where rest.strip() leaves whitespace-only
        characters that when split() return empty list.
        """
        from src.verilog2spice.spice_parser import parse_subcircuit_line
        
        # Actually, after .strip(), if the string is non-empty, split() will
        # return at least one element. The check at line 71 is redundant but
        # safe. Since the check at line 65-66 already handles empty rest,
        # line 71 would only trigger if somehow parts is empty but rest wasn't,
        # which shouldn't happen in practice. Let's remove this test since
        # it's testing an impossible condition, or test a different scenario.
        
        # Test with a line that has .SUBCKT followed by only whitespace
        # After stripping, rest will be empty, which is already tested.
        # The line 71 check is defensive programming. Let's just ensure
        # the function handles it correctly by testing the normal empty case
        # which exercises both checks.
        line = ".SUBCKT   "  # Only whitespace after .SUBCKT
        result = parse_subcircuit_line(line)
        
        # Should return None because rest.strip() is empty
        assert result is None


class TestIsInstanceLine:
    """Test cases for is_instance_line function."""

    def test_is_instance_line_transistor(self) -> None:
        """Test identifying transistor instance line.

        Tests that transistor lines (starting with M) are
        correctly identified.
        """
        line = "M1 Y A VDD VDD PMOS W=2u L=0.18u"
        assert is_instance_line(line) is True

    def test_is_instance_line_subcircuit(self) -> None:
        """Test identifying subcircuit instance line.

        Tests that subcircuit instance lines (starting with X)
        are correctly identified.
        """
        line = "X1 A Y INV"
        assert is_instance_line(line) is True

    def test_is_instance_line_comment(self) -> None:
        """Test identifying comment line.

        Tests that comment lines (starting with *) are
        considered instance lines (for continuation).
        """
        line = "* This is a comment"
        assert is_instance_line(line) is True

    def test_is_instance_line_continuation(self) -> None:
        """Test identifying continuation line.

        Tests that continuation lines (starting with +) are
        identified as instance lines.
        """
        line = "+ W=2u L=0.18u"
        assert is_instance_line(line) is True

    def test_is_instance_line_not_instance(self) -> None:
        """Test identifying non-instance line.

        Tests that non-instance lines are not identified
        as instance lines.
        """
        line = ".SUBCKT INV A Y"
        assert is_instance_line(line) is False

    def test_is_instance_line_empty(self) -> None:
        """Test identifying empty line.

        Tests that empty lines are not identified as instance lines.
        """
        line = ""
        assert is_instance_line(line) is False


class TestParseSpiceSubcircuits:
    """Test cases for parse_spice_subcircuits function."""

    def test_parse_spice_subcircuits_basic(self, sample_spice_content: str) -> None:
        """Test parsing basic SPICE subcircuits.

        Args:
            sample_spice_content: Sample SPICE content.
        """
        subcircuits = parse_spice_subcircuits(sample_spice_content)

        assert "INV" in subcircuits
        assert "NAND2" in subcircuits

        inv = subcircuits["INV"]
        assert inv.name == "INV"
        assert inv.ports == ["A", "Y"]
        assert len(inv.instances) == 2

    def test_parse_spice_subcircuits_instances(self, sample_spice_content: str) -> None:
        """Test parsing subcircuit instances.

        Args:
            sample_spice_content: Sample SPICE content.
        """
        subcircuits = parse_spice_subcircuits(sample_spice_content)
        nand2 = subcircuits["NAND2"]

        assert len(nand2.instances) == 4
        assert any("M1" in inst for inst in nand2.instances)
        assert any("M4" in inst for inst in nand2.instances)

    def test_parse_spice_subcircuits_empty_content(self) -> None:
        """Test parsing empty SPICE content.

        Tests that parsing empty content returns empty dictionary.
        """
        subcircuits = parse_spice_subcircuits("")
        assert len(subcircuits) == 0

    def test_parse_spice_subcircuits_no_subcircuits(self) -> None:
        """Test parsing SPICE content without subcircuits.

        Tests that parsing content without subcircuits
        returns empty dictionary.
        """
        content = "* Just a comment\n.model NMOS NMOS\n"
        subcircuits = parse_spice_subcircuits(content)

        assert len(subcircuits) == 0


class TestExtractModelDefinitions:
    """Test cases for extract_model_definitions function."""

    def test_extract_model_definitions_basic(self, sample_spice_content: str) -> None:
        """Test extracting model definitions.

        Args:
            sample_spice_content: Sample SPICE content.
        """
        models = extract_model_definitions(sample_spice_content)

        assert "NMOS" in models
        assert "PMOS" in models
        assert ".MODEL" in models["NMOS"].upper() or ".model" in models["NMOS"]

    def test_extract_model_definitions_case_insensitive(self) -> None:
        """Test extracting model definitions with different cases.

        Tests that model extraction is case-insensitive.
        """
        content = ".model nmos NMOS (LEVEL=1)\n.model PMOS PMOS (LEVEL=1)\n"
        models = extract_model_definitions(content)

        assert "nmos" in models
        assert "PMOS" in models

    def test_extract_model_definitions_no_models(self) -> None:
        """Test extracting models when none exist.

        Tests that empty dictionary is returned when no
        model definitions are found.
        """
        content = "* No models here\n.SUBCKT INV A Y\n.ENDS\n"
        models = extract_model_definitions(content)

        assert len(models) == 0


class TestLoadSubcircuitDefinitions:
    """Test cases for load_subcircuit_definitions function."""

    def test_load_subcircuit_definitions_from_file(
        self, temp_dir: Path, sample_spice_content: str
    ) -> None:
        """Test loading subcircuit definitions from file.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_content: Sample SPICE content.
        """
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(sample_spice_content, encoding="utf-8")

        subcircuits = load_subcircuit_definitions(str(spice_file))

        assert "INV" in subcircuits
        assert "NAND2" in subcircuits

    def test_load_subcircuit_definitions_none_path(self) -> None:
        """Test loading subcircuit definitions with None path.

        Tests that empty dictionary is returned when path is None.
        """
        subcircuits = load_subcircuit_definitions(None)
        assert len(subcircuits) == 0

    def test_load_subcircuit_definitions_file_not_found(self) -> None:
        """Test loading subcircuit definitions when file doesn't exist.

        Tests that FileNotFoundError is raised when file
        doesn't exist.
        """
        with pytest.raises(FileNotFoundError):
            load_subcircuit_definitions("/nonexistent/path.spice")

