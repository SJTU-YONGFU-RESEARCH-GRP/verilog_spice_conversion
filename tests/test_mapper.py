"""Unit tests for mapper.py module."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from src.verilog2spice.mapper import (
    CellInstance,
    CellLibrary,
    DEFAULT_GATE_MAP,
    YOSYS_GATE_MAP,
    load_cell_library,
    map_gate_to_cell,
    resolve_cell_parameters,
)

if TYPE_CHECKING:
    pass


class TestCellLibrary:
    """Test cases for CellLibrary class."""

    def test_cell_library_initialization(self) -> None:
        """Test CellLibrary initialization with valid parameters.

        Tests that CellLibrary can be initialized with technology,
        cells dictionary, and optional spice_file.
        """
        cells = {"INV": {"pins": ["A", "Y"]}}
        lib = CellLibrary(technology="generic", cells=cells, spice_file="cells.spice")

        assert lib.technology == "generic"
        assert lib.cells == cells
        assert lib.spice_file == "cells.spice"

    def test_cell_library_without_spice_file(self) -> None:
        """Test CellLibrary initialization without spice_file.

        Tests that CellLibrary can be initialized with None for spice_file.
        """
        cells = {"INV": {"pins": ["A", "Y"]}}
        lib = CellLibrary(technology="generic", cells=cells)

        assert lib.technology == "generic"
        assert lib.cells == cells
        assert lib.spice_file is None


class TestCellInstance:
    """Test cases for CellInstance class."""

    def test_cell_instance_initialization(self) -> None:
        """Test CellInstance initialization with all parameters.

        Tests that CellInstance can be initialized with cell_name,
        instance_name, pins, and parameters.
        """
        pins = {"A": "net1", "Y": "net2"}
        params = {"W": "2u", "L": "0.18u"}
        inst = CellInstance(
            cell_name="INV", instance_name="inst1", pins=pins, parameters=params
        )

        assert inst.cell_name == "INV"
        assert inst.instance_name == "inst1"
        assert inst.pins == pins
        assert inst.parameters == params

    def test_cell_instance_with_defaults(self) -> None:
        """Test CellInstance initialization with default parameters.

        Tests that CellInstance can be initialized with only
        required parameters (cell_name and instance_name).
        """
        inst = CellInstance(cell_name="INV", instance_name="inst1")

        assert inst.cell_name == "INV"
        assert inst.instance_name == "inst1"
        assert inst.pins == {}
        assert inst.parameters == {}


class TestLoadCellLibrary:
    """Test cases for load_cell_library function."""

    def test_load_cell_library_from_metadata(
        self, temp_dir: Path, sample_cell_library_data: dict
    ) -> None:
        """Test loading cell library from metadata file.

        Args:
            temp_dir: Temporary directory for test files.
            sample_cell_library_data: Sample cell library data.
        """
        import json

        metadata_file = temp_dir / "metadata.json"
        metadata_file.write_text(json.dumps(sample_cell_library_data), encoding="utf-8")

        lib = load_cell_library(metadata_path=str(metadata_file))

        assert lib.technology == "generic"
        assert "INV" in lib.cells
        assert "NAND2" in lib.cells

    def test_load_cell_library_with_spice_file(
        self, temp_dir: Path, sample_cell_library_data: dict, sample_spice_content: str
    ) -> None:
        """Test loading cell library with SPICE file.

        Args:
            temp_dir: Temporary directory for test files.
            sample_cell_library_data: Sample cell library data.
            sample_spice_content: Sample SPICE content.
        """
        import json

        # Update spice_file to be relative to metadata
        sample_cell_library_data["spice_file"] = "cells.spice"

        metadata_file = temp_dir / "metadata.json"
        spice_file = temp_dir / "cells.spice"

        metadata_file.write_text(json.dumps(sample_cell_library_data), encoding="utf-8")
        spice_file.write_text(sample_spice_content, encoding="utf-8")

        lib = load_cell_library(metadata_path=str(metadata_file))

        assert lib.spice_file is not None
        assert Path(lib.spice_file).exists()

    def test_load_cell_library_not_found(self) -> None:
        """Test loading cell library when file doesn't exist.

        Tests that FileNotFoundError is raised when metadata
        file doesn't exist and default library is also not found.
        """
        from unittest.mock import patch
        import os

        # Mock Path.exists to return False for both metadata and default library paths
        def mock_exists(self):
            path_str = str(self)
            # Return False for the metadata path
            if path_str == "/nonexistent/path.json" or path_str.endswith(
                "nonexistent/path.json"
            ):
                return False
            # Return False for default library path
            if "cell_libraries" in path_str and "cells.json" in path_str:
                return False
            # For other paths, use actual os.path.exists
            return os.path.exists(path_str)

        # Patch Path.exists for the mapper module
        with patch.object(Path, "exists", mock_exists):
            with pytest.raises(FileNotFoundError):
                load_cell_library(metadata_path="/nonexistent/path.json")

    def test_load_cell_library_empty_cells(self, temp_dir: Path) -> None:
        """Test loading cell library with empty cells.

        Args:
            temp_dir: Temporary directory for test files.
        """
        import json

        metadata_file = temp_dir / "metadata.json"
        metadata_data = {"technology": "generic", "cells": {}}
        metadata_file.write_text(json.dumps(metadata_data), encoding="utf-8")

        with pytest.raises(ValueError, match="contains no cells"):
            load_cell_library(metadata_path=str(metadata_file))

    def test_load_cell_library_spice_file_not_found(self, temp_dir: Path) -> None:
        """Test loading cell library when SPICE file is not found.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that warning is logged when SPICE file doesn't exist.
        """
        import json

        metadata_data = {
            "technology": "generic",
            "cells": {"INV": {"pins": ["A", "Y"]}},
            "spice_file": "nonexistent.spice",
        }
        metadata_file = temp_dir / "metadata.json"
        metadata_file.write_text(json.dumps(metadata_data), encoding="utf-8")

        lib = load_cell_library(metadata_path=str(metadata_file))

        assert lib.spice_file is None  # Should be None when file not found

    def test_load_cell_library_default_library_not_found(self) -> None:
        """Test loading default library when not found.

        Tests that FileNotFoundError is raised when default library doesn't exist.
        """
        from unittest.mock import patch
        import os

        def mock_exists(self):
            path_str = str(self)
            if "cell_libraries" in path_str and "cells.json" in path_str:
                return False
            return os.path.exists(path_str)

        with patch.object(Path, "exists", mock_exists):
            with pytest.raises(FileNotFoundError, match="Cell library not found"):
                load_cell_library()

    def test_load_cell_library_default_with_tech(self, temp_dir: Path) -> None:
        """Test loading default library with tech parameter.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that tech parameter is used as fallback (line 175).
        """
        import json

        # Create a mock default library structure
        lib_data = {
            "technology": "custom_tech",
            "cells": {
                "INV": {"pins": ["A", "Y"]},
                "NAND2": {"pins": ["A", "B", "Y"]},
            },
            "spice_file": "cells.spice",
        }

        # Calculate the default library path (same as in mapper.py)
        # mapper.py -> verilog2spice -> src -> project_root
        mapper_file = (
            Path(__file__).parent.parent / "src" / "verilog2spice" / "mapper.py"
        )
        project_root = mapper_file.parent.parent.parent
        default_lib_path = project_root / "config" / "cell_libraries" / "cells.json"

        # Create the directory structure if needed
        default_lib_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the default library file
        default_lib_path.write_text(json.dumps(lib_data), encoding="utf-8")

        # Create the SPICE file too
        spice_file = project_root / "config" / "cell_libraries" / "cells.spice"
        spice_file.write_text("* SPICE models\n", encoding="utf-8")

        try:
            # Test loading default library
            lib = load_cell_library(tech="generic")

            assert lib.technology == "custom_tech"  # From file, not tech parameter
            assert "INV" in lib.cells
            assert "NAND2" in lib.cells
            assert lib.spice_file is not None

            # Test with tech parameter when file doesn't specify technology
            lib_data_no_tech = {"cells": {"INV": {"pins": ["A", "Y"]}}}
            default_lib_path.write_text(json.dumps(lib_data_no_tech), encoding="utf-8")

            lib2 = load_cell_library(tech="test_tech")
            # Should use tech parameter as fallback (line 175)
            assert lib2.technology == "test_tech"
        finally:
            # Cleanup
            if default_lib_path.exists():
                default_lib_path.unlink()
            if spice_file.exists():
                spice_file.unlink()
            # Remove empty directories if they exist
            try:
                if default_lib_path.parent.exists():
                    default_lib_path.parent.rmdir()
                if default_lib_path.parent.parent.exists():
                    default_lib_path.parent.parent.rmdir()
            except OSError:
                pass  # Directory not empty or doesn't exist

    def test_load_cell_library_default_empty_cells(self, temp_dir: Path) -> None:
        """Test loading default library with empty cells.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that ValueError is raised when cells are empty (lines 182-185).
        """
        import json

        # Calculate the default library path
        mapper_file = (
            Path(__file__).parent.parent / "src" / "verilog2spice" / "mapper.py"
        )
        project_root = mapper_file.parent.parent.parent
        default_lib_path = project_root / "config" / "cell_libraries" / "cells.json"

        # Create the directory structure if needed
        default_lib_path.parent.mkdir(parents=True, exist_ok=True)

        # Write empty cells library
        lib_data = {"technology": "generic", "cells": {}}
        default_lib_path.write_text(json.dumps(lib_data), encoding="utf-8")

        try:
            # Test that ValueError is raised for empty cells (lines 182-185)
            with pytest.raises(ValueError, match="contains no cells"):
                load_cell_library()
        finally:
            # Cleanup
            if default_lib_path.exists():
                default_lib_path.unlink()
            try:
                if default_lib_path.parent.exists():
                    default_lib_path.parent.rmdir()
                if default_lib_path.parent.parent.exists():
                    default_lib_path.parent.parent.rmdir()
            except OSError:
                pass

    def test_load_cell_library_default_spice_not_found(self, temp_dir: Path) -> None:
        """Test loading default library when SPICE file not found.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that warning is logged when SPICE file doesn't exist (lines 187-189).
        """
        import json
        from unittest.mock import patch

        # Calculate the default library path
        mapper_file = (
            Path(__file__).parent.parent / "src" / "verilog2spice" / "mapper.py"
        )
        project_root = mapper_file.parent.parent.parent
        default_lib_path = project_root / "config" / "cell_libraries" / "cells.json"

        # Create the directory structure if needed
        default_lib_path.parent.mkdir(parents=True, exist_ok=True)

        # Write library data with nonexistent SPICE file
        lib_data = {
            "technology": "generic",
            "cells": {"INV": {"pins": ["A", "Y"]}},
            "spice_file": "nonexistent.spice",  # This file won't exist
        }
        default_lib_path.write_text(json.dumps(lib_data), encoding="utf-8")

        try:
            # Test that warning is logged and spice_file is None (lines 187-189)
            with patch("src.verilog2spice.mapper.logger") as mock_logger:
                lib = load_cell_library()

                # Should log warning about missing SPICE file (line 188)
                mock_logger.warning.assert_called()
                assert any(
                    "SPICE model file not found" in str(call)
                    for call in mock_logger.warning.call_args_list
                )

                # SPICE file should be None when not found (line 189)
                assert lib.spice_file is None
                assert lib.technology == "generic"
                assert "INV" in lib.cells
        finally:
            # Cleanup
            if default_lib_path.exists():
                default_lib_path.unlink()
            try:
                if default_lib_path.parent.exists():
                    default_lib_path.parent.rmdir()
                if default_lib_path.parent.parent.exists():
                    default_lib_path.parent.parent.rmdir()
            except OSError:
                pass

    def test_load_cell_library_default_full_path(self, temp_dir: Path) -> None:
        """Test loading default library with full path (lines 171-193).

        Args:
            temp_dir: Temporary directory for test files.

        Tests the complete default library loading path including all logging.
        """
        import json
        from unittest.mock import patch

        # Calculate the default library path (same as in mapper.py)
        mapper_file = (
            Path(__file__).parent.parent / "src" / "verilog2spice" / "mapper.py"
        )
        project_root = mapper_file.parent.parent.parent
        default_lib_path = project_root / "config" / "cell_libraries" / "cells.json"
        spice_file = project_root / "config" / "cell_libraries" / "cells.spice"

        # Create the directory structure
        default_lib_path.parent.mkdir(parents=True, exist_ok=True)

        # Write library data with SPICE file
        lib_data = {
            "technology": "test_tech",
            "cells": {
                "INV": {"pins": ["A", "Y"]},
                "NAND2": {"pins": ["A", "B", "Y"]},
            },
            "spice_file": "cells.spice",
        }
        default_lib_path.write_text(json.dumps(lib_data), encoding="utf-8")
        spice_file.write_text("* SPICE models\n", encoding="utf-8")

        try:
            # Test loading default library with logging (lines 171-193)
            with patch("src.verilog2spice.mapper.logger") as mock_logger:
                lib = load_cell_library()

                # Should log loading message (line 171)
                mock_logger.info.assert_any_call(
                    f"Loading default cell library from: {default_lib_path}"
                )

                # Should log loaded cells count (line 191)
                assert any(
                    "Loaded" in str(call) and "cells" in str(call)
                    for call in mock_logger.info.call_args_list
                )

                # Should log SPICE file path (line 192)
                assert any(
                    "SPICE model file" in str(call)
                    for call in mock_logger.info.call_args_list
                )

                # Verify library content
                assert lib.technology == "test_tech"
                assert len(lib.cells) == 2
                assert "INV" in lib.cells
                assert "NAND2" in lib.cells
                assert lib.spice_file is not None
                assert Path(lib.spice_file).exists()
        finally:
            # Cleanup
            if default_lib_path.exists():
                default_lib_path.unlink()
            if spice_file.exists():
                spice_file.unlink()
            try:
                if default_lib_path.parent.exists():
                    default_lib_path.parent.rmdir()
                if default_lib_path.parent.parent.exists():
                    default_lib_path.parent.parent.rmdir()
            except OSError:
                pass


class TestMapGateToCell:
    """Test cases for map_gate_to_cell function."""

    def test_map_yosys_gate(self, sample_cell_library_data: dict) -> None:
        """Test mapping Yosys gate types to cells.

        Args:
            sample_cell_library_data: Sample cell library data.
        """
        from src.verilog2spice.mapper import CellLibrary

        lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
        )

        # Test Yosys gate mapping
        mapped = map_gate_to_cell("$_NOT_", lib)
        assert mapped == "INV"

    def test_map_direct_match(self, sample_cell_library_data: dict) -> None:
        """Test direct gate to cell mapping.

        Args:
            sample_cell_library_data: Sample cell library data.
        """
        from src.verilog2spice.mapper import CellLibrary

        lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
        )

        mapped = map_gate_to_cell("INV", lib)
        assert mapped == "INV"

    def test_map_default_gate(self, sample_cell_library_data: dict) -> None:
        """Test default gate mapping.

        Args:
            sample_cell_library_data: Sample cell library data.
        """
        from src.verilog2spice.mapper import CellLibrary

        lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
        )

        mapped = map_gate_to_cell("NOT", lib)
        assert mapped == "INV"

    def test_map_case_insensitive(self, sample_cell_library_data: dict) -> None:
        """Test case-insensitive gate mapping.

        Args:
            sample_cell_library_data: Sample cell library data.
        """
        from src.verilog2spice.mapper import CellLibrary

        lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
        )

        mapped = map_gate_to_cell("inv", lib)
        assert mapped == "INV"

    def test_map_unmapped_gate(self, sample_cell_library_data: dict) -> None:
        """Test mapping unmapped gate type.

        Args:
            sample_cell_library_data: Sample cell library data.
        """
        from src.verilog2spice.mapper import CellLibrary

        lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
        )

        mapped = map_gate_to_cell("UNKNOWN_GATE", lib)
        assert mapped is None

    def test_map_yosys_gate_not_in_library(
        self, sample_cell_library_data: dict
    ) -> None:
        """Test mapping Yosys gate when mapped cell is not in library.

        Args:
            sample_cell_library_data: Sample cell library data.

        Tests that None is returned when Yosys gate maps to cell not in library.
        """
        from src.verilog2spice.mapper import CellLibrary

        # Create library without the mapped cell
        lib = CellLibrary(technology="generic", cells={"OTHER_CELL": {"pins": ["A"]}})

        # Use a Yosys gate that maps to a cell not in this library
        mapped = map_gate_to_cell("$_NOT_", lib)
        assert mapped is None


class TestResolveCellParameters:
    """Test cases for resolve_cell_parameters function."""

    def test_resolve_cell_parameters_with_gate_params(
        self, sample_cell_library_data: dict
    ) -> None:
        """Test resolving cell parameters from gate parameters.

        Args:
            sample_cell_library_data: Sample cell library data.
        """
        from src.verilog2spice.mapper import CellLibrary, CellInstance

        lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
        )

        cell = CellInstance(cell_name="INV", instance_name="inst1")
        gate_params = {"W": "2u", "L": "0.18u"}

        resolved = resolve_cell_parameters(cell, gate_params, lib)

        assert "W" in resolved
        assert "L" in resolved
        assert resolved["W"] == "2u"
        assert resolved["L"] == "0.18u"

    def test_resolve_cell_parameters_with_defaults(
        self, sample_cell_library_data: dict
    ) -> None:
        """Test resolving cell parameters with default values.

        Args:
            sample_cell_library_data: Sample cell library data.
        """
        from src.verilog2spice.mapper import CellLibrary, CellInstance

        lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
        )

        cell = CellInstance(cell_name="INV", instance_name="inst1")
        gate_params = {}

        resolved = resolve_cell_parameters(cell, gate_params, lib)

        # Should have default values for W and L
        assert "W" in resolved or "L" in resolved

    def test_resolve_cell_parameters_cell_not_in_library(
        self, sample_cell_library_data: dict
    ) -> None:
        """Test resolving parameters when cell is not in library.

        Args:
            sample_cell_library_data: Sample cell library data.

        Tests that empty dict is returned when cell not in library.
        """
        from src.verilog2spice.mapper import CellLibrary, CellInstance

        lib = CellLibrary(technology="generic", cells=sample_cell_library_data["cells"])
        cell = CellInstance(cell_name="UNKNOWN_CELL", instance_name="inst1")
        gate_params = {"W": "2u"}

        resolved = resolve_cell_parameters(cell, gate_params, lib)

        assert resolved == {}


class TestGateMaps:
    """Test cases for gate mapping dictionaries."""

    def test_yosys_gate_map_not_empty(self) -> None:
        """Test that YOSYS_GATE_MAP is not empty.

        Verifies that the YOSYS_GATE_MAP dictionary contains
        expected gate type mappings.
        """
        assert len(YOSYS_GATE_MAP) > 0
        assert "$_NOT_" in YOSYS_GATE_MAP
        assert "$_AND_" in YOSYS_GATE_MAP
        assert "$_NAND_" in YOSYS_GATE_MAP

    def test_default_gate_map_not_empty(self) -> None:
        """Test that DEFAULT_GATE_MAP is not empty.

        Verifies that the DEFAULT_GATE_MAP dictionary contains
        expected gate type mappings.
        """
        assert len(DEFAULT_GATE_MAP) > 0
        assert "NOT" in DEFAULT_GATE_MAP
        assert "AND" in DEFAULT_GATE_MAP
        assert "NAND" in DEFAULT_GATE_MAP


class TestGetSpiceModel:
    """Test cases for get_spice_model function."""

    def test_get_spice_model_found(self, sample_cell_library_data: dict) -> None:
        """Test getting SPICE model when cell is found.

        Args:
            sample_cell_library_data: Sample cell library data.

        Tests that spice_model is returned from cell library.
        """
        from src.verilog2spice.mapper import CellLibrary, get_spice_model

        # Add spice_model to cell data
        cells_with_model = sample_cell_library_data["cells"].copy()
        cells_with_model["INV"]["spice_model"] = "INV_MODEL"

        lib = CellLibrary(technology="generic", cells=cells_with_model)

        model = get_spice_model("INV", lib)
        assert model == "INV_MODEL"

    def test_get_spice_model_uses_cell_name(
        self, sample_cell_library_data: dict
    ) -> None:
        """Test getting SPICE model when spice_model not in cell data.

        Args:
            sample_cell_library_data: Sample cell library data.

        Tests that cell_name is returned when spice_model not specified.
        """
        from src.verilog2spice.mapper import CellLibrary, get_spice_model

        lib = CellLibrary(technology="generic", cells=sample_cell_library_data["cells"])

        model = get_spice_model("INV", lib)
        assert model == "INV"  # Should use cell_name as fallback

    def test_get_spice_model_not_found(self, sample_cell_library_data: dict) -> None:
        """Test getting SPICE model when cell is not found.

        Args:
            sample_cell_library_data: Sample cell library data.

        Tests that None is returned when cell not in library.
        """
        from src.verilog2spice.mapper import CellLibrary, get_spice_model

        lib = CellLibrary(technology="generic", cells=sample_cell_library_data["cells"])

        model = get_spice_model("UNKNOWN_CELL", lib)
        assert model is None
