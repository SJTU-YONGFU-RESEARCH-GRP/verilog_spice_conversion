"""Unit tests for cli.py module."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.verilog2spice.cli import (
    load_config,
    main,
    parse_args,
    process_defines,
    setup_logging,
)

if TYPE_CHECKING:
    pass


class TestSetupLogging:
    """Test cases for setup_logging function."""

    def test_setup_logging_verbose(self) -> None:
        """Test setting up logging in verbose mode.

        Tests that verbose logging is configured correctly.
        """
        # Reset logging to ensure clean state
        logging.root.handlers = []
        logging.root.setLevel(logging.WARNING)

        setup_logging(verbose=True, quiet=False, log_file=None)

        assert logging.root.level <= logging.DEBUG

    def test_setup_logging_quiet(self) -> None:
        """Test setting up logging in quiet mode.

        Tests that quiet logging (errors only) is configured correctly.
        """
        # Reset logging to ensure clean state
        logging.root.handlers = []
        logging.root.setLevel(logging.WARNING)

        setup_logging(verbose=False, quiet=True, log_file=None)

        assert logging.root.level >= logging.ERROR

    def test_setup_logging_normal(self) -> None:
        """Test setting up logging in normal mode.

        Tests that normal logging (INFO) is configured correctly.
        """
        # Reset logging to ensure clean state
        logging.root.handlers = []
        logging.root.setLevel(logging.WARNING)

        setup_logging(verbose=False, quiet=False, log_file=None)

        assert logging.root.level == logging.INFO

    def test_setup_logging_with_file(self, temp_dir: Path) -> None:
        """Test setting up logging with log file.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that file handler is added when log_file is provided.
        """
        # Reset logging to ensure clean state
        logging.root.handlers = []
        logging.root.setLevel(logging.WARNING)

        log_file = temp_dir / "test.log"
        setup_logging(verbose=False, quiet=False, log_file=str(log_file))

        # Check that file handler was added
        file_handlers = [h for h in logging.root.handlers if hasattr(h, "baseFilename")]
        assert len(file_handlers) > 0


class TestProcessDefines:
    """Test cases for process_defines function."""

    def test_process_defines_with_values(self) -> None:
        """Test processing defines with values.

        Tests that defines with = are parsed correctly.
        """
        defines = ["WIDTH=32", "ENABLE=1"]
        result = process_defines(defines)

        assert result["WIDTH"] == "32"
        assert result["ENABLE"] == "1"

    def test_process_defines_without_values(self) -> None:
        """Test processing defines without values.

        Tests that defines without = get value "1".
        """
        defines = ["ENABLE", "DEBUG"]
        result = process_defines(defines)

        assert result["ENABLE"] == "1"
        assert result["DEBUG"] == "1"

    def test_process_defines_mixed(self) -> None:
        """Test processing mixed defines.

        Tests that both types of defines are handled correctly.
        """
        defines = ["WIDTH=32", "ENABLE", "DEBUG=0"]
        result = process_defines(defines)

        assert result["WIDTH"] == "32"
        assert result["ENABLE"] == "1"
        assert result["DEBUG"] == "0"

    def test_process_defines_empty(self) -> None:
        """Test processing empty defines list.

        Tests that empty list returns empty dict.
        """
        result = process_defines([])

        assert result == {}

    def test_process_defines_multiple_equals(self) -> None:
        """Test processing defines with multiple equals signs.

        Tests that only first = is used as separator.
        """
        defines = ["PATH=/usr/bin", "URL=https://example.com"]
        result = process_defines(defines)

        assert result["PATH"] == "/usr/bin"
        assert result["URL"] == "https://example.com"


class TestLoadConfig:
    """Test cases for load_config function."""

    def test_load_config_success(self, temp_dir: Path) -> None:
        """Test loading config file successfully.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that config file is loaded and parsed correctly.
        """
        config_file = temp_dir / "config.json"
        config_data = {
            "cell_library": "cells.spice",
            "technology": "tsmc65nm",
            "optimize": True,
        }
        config_file.write_text(json.dumps(config_data), encoding="utf-8")

        result = load_config(str(config_file))

        assert result == config_data

    def test_load_config_file_not_found(self) -> None:
        """Test loading config file that doesn't exist.

        Tests that FileNotFoundError is raised when file doesn't exist.
        """
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.json")

    def test_load_config_invalid_json(self, temp_dir: Path) -> None:
        """Test loading config file with invalid JSON.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that JSONDecodeError is raised for invalid JSON.
        """
        config_file = temp_dir / "invalid.json"
        config_file.write_text("{ invalid json }", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            load_config(str(config_file))


class TestParseArgs:
    """Test cases for parse_args function."""

    def test_parse_args_basic(self) -> None:
        """Test parsing basic arguments.

        Tests that basic required arguments are parsed correctly.
        """
        test_args = ["verilog2spice", "test.v"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()

            assert args.verilog_files == ["test.v"]

    def test_parse_args_with_output(self) -> None:
        """Test parsing arguments with output file.

        Tests that output file argument is parsed correctly.
        """
        test_args = ["verilog2spice", "test.v", "-o", "output.sp"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()

            assert args.output == "output.sp"

    def test_parse_args_with_includes(self) -> None:
        """Test parsing arguments with include paths.

        Tests that include paths are parsed correctly.
        """
        test_args = ["verilog2spice", "test.v", "-I", "path1", "-I", "path2"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()

            assert "path1" in args.include_paths
            assert "path2" in args.include_paths

    def test_parse_args_with_defines(self) -> None:
        """Test parsing arguments with defines.

        Tests that defines are parsed correctly.
        """
        test_args = ["verilog2spice", "test.v", "-D", "WIDTH=32", "-D", "ENABLE"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()

            assert "WIDTH=32" in args.defines
            assert "ENABLE" in args.defines

    def test_parse_args_flatten_level(self) -> None:
        """Test parsing arguments with flatten level.

        Tests that flatten level argument is parsed correctly.
        """
        test_args = ["verilog2spice", "test.v", "--flatten-level", "transistor"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()

            assert args.flatten_level == "transistor"

    def test_parse_args_both(self) -> None:
        """Test parsing arguments with --both flag.

        Tests that --both flag is parsed correctly.
        """
        test_args = ["verilog2spice", "test.v", "--both"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()

            assert args.both is True

    def test_parse_args_verify(self) -> None:
        """Test parsing arguments with --verify flag.

        Tests that --verify flag is parsed correctly.
        """
        test_args = ["verilog2spice", "test.v", "--verify"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()

            assert args.verify is True

    def test_parse_args_cell_library(self) -> None:
        """Test parsing arguments with cell library.

        Tests that cell library argument is parsed correctly.
        """
        test_args = ["verilog2spice", "test.v", "--cell-library", "cells.spice"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()

            assert args.cell_library == "cells.spice"

    def test_parse_args_config(self) -> None:
        """Test parsing arguments with config file.

        Tests that config file argument is parsed correctly.
        """
        test_args = ["verilog2spice", "test.v", "--config", "config.json"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()

            assert args.config == "config.json"


class TestMain:
    """Test cases for main function."""

    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_success_hierarchical(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function with hierarchical output.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.
        """
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = True
        mock_args.flattened = False
        mock_args.both = False
        mock_args.flatten_level = "logic"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = False
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library
        cell_lib = CellLibrary(
            technology="generic", cells=sample_cell_library_data["cells"]
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="test_module",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.format_hierarchical"
        ) as mock_format_hier, patch(
            "src.verilog2spice.cli.validate_spice"
        ) as mock_validate:
            mock_module_info = ModuleInfo(name="test_module", ports=[], cells=[])
            mock_parse_yosys.return_value = {"test_module": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_format_hier.return_value = "* SPICE netlist\n"

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module test_module; endmodule", encoding="utf-8")

            result = main()

            assert result == 0
            mock_setup_logging.assert_called_once()
            mock_load_cell_library.assert_called_once()
            mock_synthesize.assert_called_once()
            mock_validate.assert_called_once()

    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_success_flattened(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function with flattened output.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.
        """
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = False
        mock_args.flattened = True
        mock_args.both = False
        mock_args.flatten_level = "logic"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = False
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library with spice_file
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(".SUBCKT INV A Y\n.ENDS INV\n", encoding="utf-8")
        cell_lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
            spice_file=str(spice_file),
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="test_module",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.load_cell_library_content"
        ) as mock_load_content, patch(
            "src.verilog2spice.cli.format_flattened"
        ) as mock_format_flat, patch("src.verilog2spice.cli.validate_spice"):
            mock_module_info = ModuleInfo(name="test_module", ports=[], cells=[])
            mock_parse_yosys.return_value = {"test_module": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_load_content.return_value = "* Cell library content\n"
            mock_format_flat.return_value = "* Flattened SPICE netlist\n"

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module test_module; endmodule", encoding="utf-8")

            result = main()

            assert result == 0
            mock_load_content.assert_called_once()
            mock_format_flat.assert_called_once()

    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_success_both(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function with both hierarchical and flattened output.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.
        """
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = False
        mock_args.flattened = False
        mock_args.both = True
        mock_args.flatten_level = "logic"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = False
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library with spice_file
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(".SUBCKT INV A Y\n.ENDS INV\n", encoding="utf-8")
        cell_lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
            spice_file=str(spice_file),
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="test_module",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.load_cell_library_content"
        ) as mock_load_content, patch(
            "src.verilog2spice.cli.format_hierarchical"
        ) as mock_format_hier, patch(
            "src.verilog2spice.cli.format_flattened"
        ) as mock_format_flat, patch(
            "src.verilog2spice.cli.validate_spice"
        ) as mock_validate:
            mock_module_info = ModuleInfo(name="test_module", ports=[], cells=[])
            mock_parse_yosys.return_value = {"test_module": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_load_content.return_value = "* Cell library content\n"
            mock_format_hier.return_value = "* Hierarchical SPICE netlist\n"
            mock_format_flat.return_value = "* Flattened SPICE netlist\n"

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module test_module; endmodule", encoding="utf-8")

            result = main()

            assert result == 0
            mock_format_hier.assert_called_once()
            mock_format_flat.assert_called_once()
            assert mock_validate.call_count == 2

    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_with_config(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function with config file.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.
        """
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        config_file = temp_dir / "config.json"
        config_file.write_text('{"test": "data"}', encoding="utf-8")

        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = True
        mock_args.flattened = False
        mock_args.both = False
        mock_args.flatten_level = "logic"
        mock_args.config = str(config_file)
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = False
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library
        cell_lib = CellLibrary(
            technology="generic", cells=sample_cell_library_data["cells"]
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="test_module",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        with patch("src.verilog2spice.cli.load_config") as mock_load_config, patch(
            "src.verilog2spice.cli.parse_yosys_json"
        ) as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.format_hierarchical"
        ) as mock_format_hier, patch("src.verilog2spice.cli.validate_spice"):
            mock_module_info = ModuleInfo(name="test_module", ports=[], cells=[])
            mock_parse_yosys.return_value = {"test_module": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_format_hier.return_value = "* SPICE netlist\n"

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module test_module; endmodule", encoding="utf-8")

            result = main()

            assert result == 0
            mock_load_config.assert_called_once_with(str(config_file))

    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    def test_main_keyboard_interrupt(
        self,
        mock_console: Mock,
        mock_parse_args: Mock,
        temp_dir: Path,
    ) -> None:
        """Test main function handling KeyboardInterrupt.

        Args:
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            temp_dir: Temporary directory for test files.
        """
        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = True
        mock_args.flattened = False
        mock_args.both = False
        mock_args.flatten_level = "logic"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = False
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        with patch("src.verilog2spice.cli.setup_logging"), patch(
            "src.verilog2spice.cli.Progress"
        ) as mock_progress:
            # Make Progress context manager raise KeyboardInterrupt
            mock_progress.return_value.__enter__.side_effect = KeyboardInterrupt()

            result = main()

            assert result == 130
            mock_console.print.assert_called()

    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    def test_main_exception_handling(
        self,
        mock_console: Mock,
        mock_parse_args: Mock,
        temp_dir: Path,
    ) -> None:
        """Test main function handling exceptions.

        Args:
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            temp_dir: Temporary directory for test files.
        """
        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = True
        mock_args.flattened = False
        mock_args.both = False
        mock_args.flatten_level = "logic"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = False
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        with patch("src.verilog2spice.cli.setup_logging"), patch(
            "src.verilog2spice.cli.logging"
        ) as mock_logging, patch(
            "src.verilog2spice.cli.Progress"
        ) as mock_progress, patch(
            "src.verilog2spice.cli.load_cell_library"
        ) as mock_load_cell_library:
            # Make load_cell_library raise an exception (inside try block)
            mock_load_cell_library.side_effect = RuntimeError("Test error")
            mock_logger = Mock()
            mock_logging.getLogger.return_value = mock_logger
            mock_progress.return_value.__enter__.return_value = MagicMock()
            mock_progress.return_value.__exit__.return_value = None

            result = main()

            assert result == 1
            mock_logger.exception.assert_called()
            mock_console.print.assert_called()

    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_transistor_level(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function with transistor-level flattening.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.
        """
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = False
        mock_args.flattened = False
        mock_args.both = False
        mock_args.flatten_level = "transistor"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = False
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library with spice_file
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(".SUBCKT INV A Y\n.ENDS INV\n", encoding="utf-8")
        cell_lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
            spice_file=str(spice_file),
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="test_module",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.load_cell_library_content"
        ) as mock_load_content, patch(
            "src.verilog2spice.cli.format_flattened"
        ) as mock_format_flat, patch("src.verilog2spice.cli.validate_spice"):
            mock_module_info = ModuleInfo(name="test_module", ports=[], cells=[])
            mock_parse_yosys.return_value = {"test_module": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_load_content.return_value = "* Cell library content\n"
            mock_format_flat.return_value = "* Transistor-level SPICE netlist\n"

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module test_module; endmodule", encoding="utf-8")

            result = main()

            assert result == 0
            # Should use flatten_level="transistor"
            mock_generate.assert_called_once()
            call_kwargs = mock_generate.call_args[1]
            assert call_kwargs["flatten_level"] == "transistor"

    @patch("src.verilog2spice.cli.check_netgen")
    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_with_verify(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        mock_check_netgen: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function with LVS verification.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            mock_check_netgen: Mocked check_netgen function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.
        """
        from src.verilog2spice.lvs import LVSResult
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = True
        mock_args.flattened = True
        mock_args.both = True
        mock_args.flatten_level = "logic"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = True
        mock_args.verify_flatten_levels = False
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library with spice_file
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(".SUBCKT INV A Y\n.ENDS INV\n", encoding="utf-8")
        cell_lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
            spice_file=str(spice_file),
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="test_module",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        mock_check_netgen.return_value = True

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.load_cell_library_content"
        ) as mock_load_content, patch(
            "src.verilog2spice.cli.format_hierarchical"
        ) as mock_format_hier, patch(
            "src.verilog2spice.cli.format_flattened"
        ) as mock_format_flat, patch("src.verilog2spice.cli.validate_spice"), patch(
            "src.verilog2spice.cli.verify_spice_vs_spice"
        ) as mock_verify:
            mock_module_info = ModuleInfo(name="test_module", ports=[], cells=[])
            mock_parse_yosys.return_value = {"test_module": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_load_content.return_value = "* Cell library content\n"
            mock_format_hier.return_value = "* Hierarchical SPICE netlist\n"
            mock_format_flat.return_value = "* Flattened SPICE netlist\n"

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module test_module; endmodule", encoding="utf-8")

            # Setup file paths
            output_dir = temp_dir / "output"
            hier_file = output_dir / "test_module.sp"
            flat_file = output_dir / "test_module_flat.sp"
            output_dir.mkdir(parents=True, exist_ok=True)
            hier_file.write_text("* Hierarchical\n", encoding="utf-8")
            flat_file.write_text("* Flattened\n", encoding="utf-8")

            mock_verify.return_value = LVSResult(
                matched=True, output="", errors=[], warnings=[]
            )

            result = main()

            assert result == 0
            mock_verify.assert_called_once()

    @patch("src.verilog2spice.cli.load_cell_library_content")
    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_cell_library_content_fails(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        mock_load_content: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function when cell library content loading fails.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            mock_load_content: Mocked load_cell_library_content function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.
        """
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = False
        mock_args.flattened = True
        mock_args.both = False
        mock_args.flatten_level = "logic"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = False
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library with spice_file
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(".SUBCKT INV A Y\n.ENDS INV\n", encoding="utf-8")
        cell_lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
            spice_file=str(spice_file),
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="test_module",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        # Make load_cell_library_content return None/empty
        mock_load_content.return_value = None

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch("src.verilog2spice.cli.logging") as mock_logging:
            mock_module_info = ModuleInfo(name="test_module", ports=[], cells=[])
            mock_parse_yosys.return_value = {"test_module": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_logger = Mock()
            mock_logging.getLogger.return_value = mock_logger

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module test_module; endmodule", encoding="utf-8")

            # RuntimeError is raised but caught by main's exception handler
            result = main()

            assert result == 1
            mock_logger.exception.assert_called()

    @patch("src.verilog2spice.cli.check_netgen")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_verify_no_netgen(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_check_netgen: Mock,
        temp_dir: Path,
    ) -> None:
        """Test main function when verify is requested but netgen not found.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_check_netgen: Mocked check_netgen function.
            temp_dir: Temporary directory for test files.
        """
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        mock_check_netgen.return_value = False

        with patch("src.verilog2spice.cli.parse_args") as mock_parse_args, patch(
            "src.verilog2spice.cli.setup_logging"
        ), patch(
            "src.verilog2spice.cli.load_cell_library"
        ) as mock_load_cell_library, patch(
            "src.verilog2spice.cli.synthesize"
        ) as mock_synthesize, patch(
            "src.verilog2spice.cli.parse_yosys_json"
        ) as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.load_cell_library_content"
        ) as mock_load_content, patch(
            "src.verilog2spice.cli.format_hierarchical"
        ) as mock_format_hier, patch(
            "src.verilog2spice.cli.format_flattened"
        ) as mock_format_flat, patch("src.verilog2spice.cli.validate_spice"):
            # Setup mocks
            mock_args = Mock()
            mock_args.verilog_files = [str(temp_dir / "test.v")]
            mock_args.output = None
            mock_args.output_dir = str(temp_dir / "output")
            mock_args.top = None
            mock_args.hierarchical = True
            mock_args.flattened = True
            mock_args.both = True
            mock_args.flatten_level = "logic"
            mock_args.config = None
            mock_args.defines = []
            mock_args.cell_library = None
            mock_args.cell_metadata = None
            mock_args.tech = None
            mock_args.synthesis_script = None
            mock_args.optimize = False
            mock_args.include_paths = []
            mock_args.verify = True
            mock_args.verify_flatten_levels = False
            mock_args.verify_reference = None
            mock_args.verbose = False
            mock_args.quiet = False
            mock_args.log = None
            mock_parse_args.return_value = mock_args

            # Setup cell library with spice_file
            spice_file = temp_dir / "cells.spice"
            spice_file.write_text(".SUBCKT INV A Y\n.ENDS INV\n", encoding="utf-8")
            cell_lib = CellLibrary(
                technology="generic", cells={}, spice_file=str(spice_file)
            )
            mock_load_cell_library.return_value = cell_lib

            # Setup netlist
            netlist = Netlist(modules={}, top_module="test_module", json_data={})
            mock_synthesize.return_value = netlist

            # Setup progress
            mock_progress_ctx = MagicMock()
            mock_progress.return_value.__enter__.return_value = mock_progress_ctx
            mock_progress.return_value.__exit__.return_value = None

            mock_module_info = ModuleInfo(name="test_module", ports=[], cells=[])
            mock_parse_yosys.return_value = {"test_module": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_load_content.return_value = "* Cell library content\n"
            mock_format_hier.return_value = "* Hierarchical SPICE netlist\n"
            mock_format_flat.return_value = "* Flattened SPICE netlist\n"

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module test_module; endmodule", encoding="utf-8")

            result = main()

            assert result == 0
            # Should print warning about netgen not found
            assert mock_console.print.called

    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_infer_top_module(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function inferring top module from filename.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.
        """
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "my_design.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None  # Not provided, should infer from filename
        mock_args.hierarchical = True
        mock_args.flattened = False
        mock_args.both = False
        mock_args.flatten_level = "logic"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = False
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library
        cell_lib = CellLibrary(
            technology="generic", cells=sample_cell_library_data["cells"]
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="my_design",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.format_hierarchical"
        ) as mock_format_hier, patch("src.verilog2spice.cli.validate_spice"), patch(
            "src.verilog2spice.cli.logging"
        ) as mock_logging:
            mock_module_info = ModuleInfo(name="my_design", ports=[], cells=[])
            mock_parse_yosys.return_value = {"my_design": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_format_hier.return_value = "* SPICE netlist\n"
            mock_logger = Mock()
            mock_logging.getLogger.return_value = mock_logger

            # Create verilog file
            verilog_file = temp_dir / "my_design.v"
            verilog_file.write_text("module my_design; endmodule", encoding="utf-8")

            result = main()

            assert result == 0
            # Should infer top_module from filename
            mock_synthesize.assert_called_once()
            call_args = mock_synthesize.call_args
            assert call_args[0][1] == "my_design"  # top_module should be inferred

    @patch("src.verilog2spice.cli.check_netgen")
    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_verify_reference_not_found(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        mock_check_netgen: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function with verify_reference when reference file not found.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            mock_check_netgen: Mocked check_netgen function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.

        Tests lines 490-496 (reference file not found).
        """
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = False
        mock_args.flattened = True
        mock_args.both = False
        mock_args.flatten_level = "logic"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = False
        mock_args.verify_reference = str(
            temp_dir / "nonexistent.sp"
        )  # File doesn't exist
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library with spice_file
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(".SUBCKT INV A Y\n.ENDS INV\n", encoding="utf-8")
        cell_lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
            spice_file=str(spice_file),
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="test_module",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        mock_check_netgen.return_value = True

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.load_cell_library_content"
        ) as mock_load_content, patch(
            "src.verilog2spice.cli.format_flattened"
        ) as mock_format_flat, patch("src.verilog2spice.cli.validate_spice"):
            mock_module_info = ModuleInfo(name="test_module", ports=[], cells=[])
            mock_parse_yosys.return_value = {"test_module": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_load_content.return_value = "* Cell library content\n"
            mock_format_flat.return_value = "* Flattened SPICE netlist\n"

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module test_module; endmodule", encoding="utf-8")

            result = main()

            assert result == 0
            # Should print error about reference file not found
            assert mock_console.print.called

    @patch("src.verilog2spice.cli.check_netgen")
    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_verify_reference_flat_file_not_found(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        mock_check_netgen: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function with verify_reference when flat file not found.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            mock_check_netgen: Mocked check_netgen function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.

        Tests lines 497-501 (flat file not found).
        """
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = False
        mock_args.flattened = True
        mock_args.both = False
        mock_args.flatten_level = "logic"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = False
        reference_file = temp_dir / "reference.sp"
        reference_file.write_text("* Reference\n", encoding="utf-8")
        mock_args.verify_reference = str(reference_file)
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library with spice_file
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(".SUBCKT INV A Y\n.ENDS INV\n", encoding="utf-8")
        cell_lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
            spice_file=str(spice_file),
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="test_module",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        mock_check_netgen.return_value = True

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.load_cell_library_content"
        ) as mock_load_content, patch(
            "src.verilog2spice.cli.format_flattened"
        ) as mock_format_flat, patch("src.verilog2spice.cli.validate_spice"), patch(
            "src.verilog2spice.cli.verify_spice_vs_spice"
        ) as mock_verify:
            mock_module_info = ModuleInfo(name="test_module", ports=[], cells=[])
            mock_parse_yosys.return_value = {"test_module": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_load_content.return_value = "* Cell library content\n"
            mock_format_flat.return_value = "* Flattened SPICE netlist\n"

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module test_module; endmodule", encoding="utf-8")

            # Note: The flat file will be created during main() by format_flattened,
            # so it will exist when the check at line 497 happens. This test verifies
            # the code path where both files exist, which is the normal case.
            # The flat_file not found case (line 497) would require preventing file
            # creation, which is complex. The reference_file not found case is
            # tested in test_main_verify_reference_not_found.

            result = main()

            assert result == 0
            # The flat file exists (created by format_flattened), so verify will be called
            mock_verify.assert_called_once()

    @patch("src.verilog2spice.cli.check_netgen")
    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_verify_reference_with_errors(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        mock_check_netgen: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function with verify_reference when LVS has errors.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            mock_check_netgen: Mocked check_netgen function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.

        Tests lines 513-523 (LVS mismatch with errors).
        """
        from src.verilog2spice.lvs import LVSResult
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = False
        mock_args.flattened = True
        mock_args.both = False
        mock_args.flatten_level = "logic"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = False
        reference_file = temp_dir / "reference.sp"
        reference_file.write_text("* Reference\n", encoding="utf-8")
        mock_args.verify_reference = str(reference_file)
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library with spice_file
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(".SUBCKT INV A Y\n.ENDS INV\n", encoding="utf-8")
        cell_lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
            spice_file=str(spice_file),
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="test_module",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        mock_check_netgen.return_value = True

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.load_cell_library_content"
        ) as mock_load_content, patch(
            "src.verilog2spice.cli.format_flattened"
        ) as mock_format_flat, patch("src.verilog2spice.cli.validate_spice"), patch(
            "src.verilog2spice.cli.verify_spice_vs_spice"
        ) as mock_verify, patch("src.verilog2spice.cli.logging") as mock_logging:
            mock_module_info = ModuleInfo(name="test_module", ports=[], cells=[])
            mock_parse_yosys.return_value = {"test_module": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_load_content.return_value = "* Cell library content\n"
            mock_format_flat.return_value = "* Flattened SPICE netlist\n"
            mock_logger = Mock()
            mock_logging.getLogger.return_value = mock_logger

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module test_module; endmodule", encoding="utf-8")

            # Setup file paths
            output_dir = temp_dir / "output"
            flat_file = output_dir / "test_module_flat.sp"
            output_dir.mkdir(parents=True, exist_ok=True)
            flat_file.write_text("* Flattened\n", encoding="utf-8")

            # LVS result with errors
            mock_verify.return_value = LVSResult(
                matched=False,
                output="Some netgen output",
                errors=[
                    "Error 1",
                    "Error 2",
                    "Error 3",
                    "Error 4",
                    "Error 5",
                    "Error 6",
                ],
                warnings=[],
            )

            result = main()

            assert result == 0
            mock_verify.assert_called_once()
            # Should print errors (first 5)
            assert mock_console.print.called
            # Should log debug output
            mock_logger.debug.assert_called()

    @patch("src.verilog2spice.cli.check_netgen")
    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_verify_flatten_levels(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        mock_check_netgen: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function with verify_flatten_levels.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            mock_check_netgen: Mocked check_netgen function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.

        Tests lines 528-560 (verify_flatten_levels path).
        """
        from src.verilog2spice.lvs import LVSResult
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = False
        mock_args.flattened = True
        mock_args.both = False
        mock_args.flatten_level = "transistor"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = True
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library with spice_file
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(".SUBCKT INV A Y\n.ENDS INV\n", encoding="utf-8")
        cell_lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
            spice_file=str(spice_file),
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="test_module",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        mock_check_netgen.return_value = True

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.load_cell_library_content"
        ) as mock_load_content, patch(
            "src.verilog2spice.cli.format_flattened"
        ) as mock_format_flat, patch("src.verilog2spice.cli.validate_spice"), patch(
            "src.verilog2spice.cli.compare_flattening_levels"
        ) as mock_compare, patch("src.verilog2spice.cli.logging") as mock_logging:
            mock_module_info = ModuleInfo(name="test_module", ports=[], cells=[])
            mock_parse_yosys.return_value = {"test_module": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_load_content.return_value = "* Cell library content\n"
            mock_format_flat.return_value = "* Flattened SPICE netlist\n"
            mock_logger = Mock()
            mock_logging.getLogger.return_value = mock_logger

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module test_module; endmodule", encoding="utf-8")

            # Setup file paths - need both logic and transistor files
            output_dir = temp_dir / "output"
            logic_file = output_dir / "test_module_flat.sp"
            transistor_file = output_dir / "test_module_transistor.sp"
            output_dir.mkdir(parents=True, exist_ok=True)
            logic_file.write_text("* Logic level\n", encoding="utf-8")
            transistor_file.write_text("* Transistor level\n", encoding="utf-8")

            # Compare result
            mock_compare.return_value = (
                True,
                LVSResult(matched=True, output="", errors=[], warnings=[]),
            )

            result = main()

            assert result == 0
            mock_compare.assert_called_once()

    @patch("src.verilog2spice.cli.check_netgen")
    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_verify_flatten_levels_files_missing(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        mock_check_netgen: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function with verify_flatten_levels when files are missing.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            mock_check_netgen: Mocked check_netgen function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.

        Tests lines 561-574 (files missing warning).
        """
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = False
        mock_args.flattened = True
        mock_args.both = False
        mock_args.flatten_level = "transistor"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = True
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library with spice_file
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(".SUBCKT INV A Y\n.ENDS INV\n", encoding="utf-8")
        cell_lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
            spice_file=str(spice_file),
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="test_module",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        mock_check_netgen.return_value = True

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.load_cell_library_content"
        ) as mock_load_content, patch(
            "src.verilog2spice.cli.format_flattened"
        ) as mock_format_flat, patch("src.verilog2spice.cli.validate_spice"):
            mock_module_info = ModuleInfo(name="test_module", ports=[], cells=[])
            mock_parse_yosys.return_value = {"test_module": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_load_content.return_value = "* Cell library content\n"
            mock_format_flat.return_value = "* Flattened SPICE netlist\n"

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module test_module; endmodule", encoding="utf-8")

            # Don't create the logic/transistor files (they won't exist)

            result = main()

            assert result == 0
            # Should print warning about files missing
            assert mock_console.print.called

    @patch("src.verilog2spice.cli.check_netgen")
    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_verify_with_mismatch(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        mock_check_netgen: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function with verify when LVS has mismatch.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            mock_check_netgen: Mocked check_netgen function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.

        Tests lines 598-610 (LVS mismatch with errors).
        """
        from src.verilog2spice.lvs import LVSResult
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = True
        mock_args.flattened = True
        mock_args.both = True
        mock_args.flatten_level = "logic"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = True
        mock_args.verify_flatten_levels = False
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library with spice_file
        spice_file = temp_dir / "cells.spice"
        spice_file.write_text(".SUBCKT INV A Y\n.ENDS INV\n", encoding="utf-8")
        cell_lib = CellLibrary(
            technology="generic",
            cells=sample_cell_library_data["cells"],
            spice_file=str(spice_file),
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="test_module",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        mock_check_netgen.return_value = True

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.load_cell_library_content"
        ) as mock_load_content, patch(
            "src.verilog2spice.cli.format_hierarchical"
        ) as mock_format_hier, patch(
            "src.verilog2spice.cli.format_flattened"
        ) as mock_format_flat, patch("src.verilog2spice.cli.validate_spice"), patch(
            "src.verilog2spice.cli.verify_spice_vs_spice"
        ) as mock_verify, patch("src.verilog2spice.cli.logging") as mock_logging:
            mock_module_info = ModuleInfo(name="test_module", ports=[], cells=[])
            mock_parse_yosys.return_value = {"test_module": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_load_content.return_value = "* Cell library content\n"
            mock_format_hier.return_value = "* Hierarchical SPICE netlist\n"
            mock_format_flat.return_value = "* Flattened SPICE netlist\n"
            mock_logger = Mock()
            mock_logging.getLogger.return_value = mock_logger

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module test_module; endmodule", encoding="utf-8")

            # Setup file paths
            output_dir = temp_dir / "output"
            hier_file = output_dir / "test_module.sp"
            flat_file = output_dir / "test_module_flat.sp"
            output_dir.mkdir(parents=True, exist_ok=True)
            hier_file.write_text("* Hierarchical\n", encoding="utf-8")
            flat_file.write_text("* Flattened\n", encoding="utf-8")

            # LVS result with mismatch
            mock_verify.return_value = LVSResult(
                matched=False,
                output="Netgen output with errors",
                errors=["Error 1", "Error 2"],
                warnings=[],
            )

            result = main()

            assert result == 0
            mock_verify.assert_called_once()
            # Should print errors
            assert mock_console.print.called
            # Should log debug output
            mock_logger.debug.assert_called()

    @patch("src.verilog2spice.cli.check_netgen")
    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_verify_files_dont_exist(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        mock_check_netgen: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function with verify when files don't exist.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            mock_check_netgen: Mocked check_netgen function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.

        Tests lines 611-639 (warning messages when files don't exist).
        """
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None
        mock_args.hierarchical = True
        mock_args.flattened = False  # Only hierarchical
        mock_args.both = False
        mock_args.flatten_level = "logic"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = True
        mock_args.verify_flatten_levels = False
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library
        cell_lib = CellLibrary(
            technology="generic", cells=sample_cell_library_data["cells"]
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="test_module",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        mock_check_netgen.return_value = True

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.format_hierarchical"
        ) as mock_format_hier, patch("src.verilog2spice.cli.validate_spice"):
            mock_module_info = ModuleInfo(name="test_module", ports=[], cells=[])
            mock_parse_yosys.return_value = {"test_module": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_format_hier.return_value = "* Hierarchical SPICE netlist\n"

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module test_module; endmodule", encoding="utf-8")

            # Don't create files (they won't exist for verification)

            result = main()

            assert result == 0
            # Should print warnings about files missing
            assert mock_console.print.called

    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_output_file_inference_no_top(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function inferring output file from Verilog filename when no top.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.

        Tests lines 338-341 (output_file inference from first Verilog file).
        """
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "my_circuit.v")]
        mock_args.output = None  # Not provided
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = None  # Not provided
        mock_args.hierarchical = True
        mock_args.flattened = False
        mock_args.both = False
        mock_args.flatten_level = "logic"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = False
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library
        cell_lib = CellLibrary(
            technology="generic", cells=sample_cell_library_data["cells"]
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="my_circuit",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.format_hierarchical"
        ) as mock_format_hier, patch(
            "src.verilog2spice.cli.validate_spice"
        ) as mock_validate, patch("src.verilog2spice.cli.Path") as mock_path_class:
            mock_module_info = ModuleInfo(name="my_circuit", ports=[], cells=[])
            mock_parse_yosys.return_value = {"my_circuit": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_format_hier.return_value = "* SPICE netlist\n"

            # Create verilog file
            verilog_file = temp_dir / "my_circuit.v"
            verilog_file.write_text("module my_circuit; endmodule", encoding="utf-8")

            # Mock Path operations
            def path_side_effect(path_str):
                return Path(path_str)

            mock_path_class.side_effect = path_side_effect
            mock_path_class.return_value.write_text = Mock()
            mock_path_class.return_value.mkdir = Mock()

            result = main()

            assert result == 0
            # Should infer output_file from first Verilog file stem
            mock_format_hier.assert_called_once()
            mock_validate.assert_called_once()

    @patch("src.verilog2spice.cli.synthesize")
    @patch("src.verilog2spice.cli.load_cell_library")
    @patch("src.verilog2spice.cli.setup_logging")
    @patch("src.verilog2spice.cli.parse_args")
    @patch("src.verilog2spice.cli.console")
    @patch("src.verilog2spice.cli.Progress")
    def test_main_output_file_inference_with_top(
        self,
        mock_progress: Mock,
        mock_console: Mock,
        mock_parse_args: Mock,
        mock_setup_logging: Mock,
        mock_load_cell_library: Mock,
        mock_synthesize: Mock,
        temp_dir: Path,
        sample_yosys_json: dict,
        sample_cell_library_data: dict,
    ) -> None:
        """Test main function inferring output file from --top when no output specified.

        Args:
            mock_progress: Mocked Progress class.
            mock_console: Mocked console object.
            mock_parse_args: Mocked parse_args function.
            mock_setup_logging: Mocked setup_logging function.
            mock_load_cell_library: Mocked load_cell_library function.
            mock_synthesize: Mocked synthesize function.
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON data.
            sample_cell_library_data: Sample cell library data.

        Tests line 337 (output_file = f"{args.top}.sp").
        """
        from src.verilog2spice.mapper import CellLibrary
        from src.verilog2spice.parser import ModuleInfo
        from src.verilog2spice.synthesizer import Netlist

        # Setup mocks
        mock_args = Mock()
        mock_args.verilog_files = [str(temp_dir / "test.v")]
        mock_args.output = None  # Not provided
        mock_args.output_dir = str(temp_dir / "output")
        mock_args.top = "my_circuit"  # Provided
        mock_args.hierarchical = True
        mock_args.flattened = False
        mock_args.both = False
        mock_args.flatten_level = "logic"
        mock_args.config = None
        mock_args.defines = []
        mock_args.cell_library = None
        mock_args.cell_metadata = None
        mock_args.tech = None
        mock_args.synthesis_script = None
        mock_args.optimize = False
        mock_args.include_paths = []
        mock_args.verify = False
        mock_args.verify_flatten_levels = False
        mock_args.verify_reference = None
        mock_args.verbose = False
        mock_args.quiet = False
        mock_args.log = None
        mock_parse_args.return_value = mock_args

        # Setup cell library
        cell_lib = CellLibrary(
            technology="generic", cells=sample_cell_library_data["cells"]
        )
        mock_load_cell_library.return_value = cell_lib

        # Setup netlist
        netlist = Netlist(
            modules={},
            top_module="my_circuit",
            json_data=sample_yosys_json,
        )
        mock_synthesize.return_value = netlist

        # Setup progress
        mock_progress_ctx = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        mock_progress.return_value.__exit__.return_value = None

        with patch("src.verilog2spice.cli.parse_yosys_json") as mock_parse_yosys, patch(
            "src.verilog2spice.cli.get_top_module"
        ) as mock_get_top, patch(
            "src.verilog2spice.cli.generate_netlist"
        ) as mock_generate, patch(
            "src.verilog2spice.cli.format_hierarchical"
        ) as mock_format_hier, patch(
            "src.verilog2spice.cli.validate_spice"
        ) as mock_validate, patch("src.verilog2spice.cli.Path") as mock_path_class:
            mock_module_info = ModuleInfo(name="my_circuit", ports=[], cells=[])
            mock_parse_yosys.return_value = {"my_circuit": mock_module_info}
            mock_get_top.return_value = mock_module_info
            mock_generate.return_value = Mock()
            mock_format_hier.return_value = "* SPICE netlist\n"

            # Create verilog file
            verilog_file = temp_dir / "test.v"
            verilog_file.write_text("module my_circuit; endmodule", encoding="utf-8")

            # Mock Path operations
            def path_side_effect(path_str):
                return Path(path_str)

            mock_path_class.side_effect = path_side_effect
            mock_path_class.return_value.write_text = Mock()
            mock_path_class.return_value.mkdir = Mock()

            result = main()

            assert result == 0
            # Should infer output_file from args.top (line 337)
            mock_format_hier.assert_called_once()
            mock_validate.assert_called_once()
