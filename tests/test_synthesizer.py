"""Unit tests for synthesizer.py module."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest

from src.verilog2spice.synthesizer import (
    Netlist,
    check_yosys,
    create_default_synthesis_script,
)

if TYPE_CHECKING:
    pass


class TestNetlist:
    """Test cases for Netlist class."""

    def test_netlist_initialization(self) -> None:
        """Test Netlist initialization.

        Tests that Netlist can be initialized with
        modules, top_module, and json_data.
        """
        modules = {"module1": {}}
        json_data = {"modules": modules}

        netlist = Netlist(modules=modules, top_module="module1", json_data=json_data)

        assert netlist.modules == modules
        assert netlist.top_module == "module1"
        assert netlist.json_data == json_data

    def test_netlist_with_defaults(self) -> None:
        """Test Netlist initialization with defaults.

        Tests that Netlist can be initialized with
        only default values.
        """
        netlist = Netlist()

        assert netlist.modules == {}
        assert netlist.top_module is None
        assert netlist.json_data == {}


class TestCheckYosys:
    """Test cases for check_yosys function."""

    def test_check_yosys_not_available(self) -> None:
        """Test checking Yosys when not available.

        Tests that False is returned when Yosys is not found.
        """
        # Mock subprocess.run to simulate Yosys not found
        with patch("src.verilog2spice.synthesizer.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = check_yosys()

            assert result is False

    def test_check_yosys_timeout(self) -> None:
        """Test checking Yosys with timeout.

        Tests that False is returned when Yosys check times out.
        """
        import subprocess

        # Mock subprocess.run to simulate timeout
        with patch("src.verilog2spice.synthesizer.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("yosys", timeout=5)

            result = check_yosys()

            assert result is False

    def test_check_yosys_available(self) -> None:
        """Test checking Yosys when available.

        Tests that True is returned when Yosys is available.
        """
        # Mock subprocess.run to simulate Yosys available
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("src.verilog2spice.synthesizer.subprocess.run") as mock_run:
            mock_run.return_value = mock_result

            result = check_yosys()

            assert result is True


class TestCreateDefaultSynthesisScript:
    """Test cases for create_default_synthesis_script function."""

    def test_create_default_synthesis_script_basic(self, temp_dir: Path) -> None:
        """Test creating basic synthesis script.

        Args:
            temp_dir: Temporary directory for test files.
        """
        verilog_files = ["test1.v", "test2.v"]
        top_module = "test_top"
        optimize = True

        script_path, netlist_path = create_default_synthesis_script(
            verilog_files, top_module, optimize, str(temp_dir), None, None
        )

        assert Path(script_path).exists()
        # netlist_path is just a Path object - it will be created when Yosys runs
        # So we just check it's a Path object pointing to the right location
        assert isinstance(netlist_path, Path)
        assert str(netlist_path).endswith("netlist.json")

        script_content = Path(script_path).read_text(encoding="utf-8")

        assert "read_verilog" in script_content
        assert "test1.v" in script_content
        assert "test2.v" in script_content
        assert f"hierarchy -check -top {top_module}" in script_content
        assert "proc" in script_content
        assert "opt" in script_content

    def test_create_default_synthesis_script_no_optimize(self, temp_dir: Path) -> None:
        """Test creating synthesis script without optimization.

        Args:
            temp_dir: Temporary directory for test files.
        """
        verilog_files = ["test.v"]
        top_module = "test_top"
        optimize = False

        script_path, netlist_path = create_default_synthesis_script(
            verilog_files, top_module, optimize, str(temp_dir), None, None
        )

        script_content = Path(script_path).read_text(encoding="utf-8")

        # Should not contain optimization commands
        assert "proc" not in script_content.lower()
        assert "opt" not in script_content.lower()

    def test_create_default_synthesis_script_with_includes(
        self, temp_dir: Path
    ) -> None:
        """Test creating synthesis script with include paths.

        Args:
            temp_dir: Temporary directory for test files.
        """
        verilog_files = ["test.v"]
        top_module = "test_top"
        include_paths = ["/path/to/inc1", "/path/to/inc2"]

        script_path, netlist_path = create_default_synthesis_script(
            verilog_files, top_module, True, str(temp_dir), include_paths, None
        )

        script_content = Path(script_path).read_text(encoding="utf-8")

        assert "-I/path/to/inc1" in script_content
        assert "-I/path/to/inc2" in script_content

    def test_create_default_synthesis_script_with_defines(self, temp_dir: Path) -> None:
        """Test creating synthesis script with defines.

        Args:
            temp_dir: Temporary directory for test files.
        """
        verilog_files = ["test.v"]
        top_module = "test_top"
        defines = {"WIDTH": "8", "ENABLE": "1"}

        script_path, netlist_path = create_default_synthesis_script(
            verilog_files, top_module, True, str(temp_dir), None, defines
        )

        script_content = Path(script_path).read_text(encoding="utf-8")

        assert "-DWIDTH=8" in script_content
        assert "-DENABLE=1" in script_content

    def test_create_default_synthesis_script_no_output_dir(self) -> None:
        """Test creating synthesis script without output directory.

        Tests that script is created in temp directory when
        output_dir is None.
        """
        import tempfile

        verilog_files = ["test.v"]
        top_module = "test_top"

        script_path, netlist_path = create_default_synthesis_script(
            verilog_files, top_module, True, None, None, None
        )

        # Should be in temp directory
        assert Path(script_path).exists()
        assert tempfile.gettempdir() in str(script_path)


class TestRunYosys:
    """Test cases for run_yosys function."""

    def test_run_yosys_success(self, temp_dir: Path) -> None:
        """Test running Yosys successfully.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that Yosys runs successfully with a script.
        """
        from src.verilog2spice.synthesizer import run_yosys

        script_file = temp_dir / "test.ys"
        script_file.write_text("read_verilog test.v\n", encoding="utf-8")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Yosys output"
        mock_result.stderr = ""

        with patch("src.verilog2spice.synthesizer.subprocess.run") as mock_run:
            mock_run.return_value = mock_result

            # Should not raise an exception
            run_yosys(str(script_file))

            mock_run.assert_called_once()

    def test_run_yosys_timeout(self, temp_dir: Path) -> None:
        """Test running Yosys with timeout.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that RuntimeError is raised on timeout.
        """
        from src.verilog2spice.synthesizer import run_yosys

        import subprocess

        script_file = temp_dir / "test.ys"
        script_file.write_text("read_verilog test.v\n", encoding="utf-8")

        with patch("src.verilog2spice.synthesizer.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("yosys", timeout=300)

            with pytest.raises(RuntimeError, match="timed out"):
                run_yosys(str(script_file))

    def test_run_yosys_not_found(self, temp_dir: Path) -> None:
        """Test running Yosys when not found.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that RuntimeError is raised when Yosys is not found.
        """
        from src.verilog2spice.synthesizer import run_yosys

        script_file = temp_dir / "test.ys"
        script_file.write_text("read_verilog test.v\n", encoding="utf-8")

        with patch("src.verilog2spice.synthesizer.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with pytest.raises(RuntimeError, match="not found"):
                run_yosys(str(script_file))

    def test_run_yosys_process_error(self, temp_dir: Path) -> None:
        """Test running Yosys with process error.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that RuntimeError is raised on process error.
        """
        from src.verilog2spice.synthesizer import run_yosys

        import subprocess

        script_file = temp_dir / "test.ys"
        script_file.write_text("read_verilog test.v\n", encoding="utf-8")

        mock_error = subprocess.CalledProcessError(1, "yosys", stderr="Error output")

        with patch("src.verilog2spice.synthesizer.subprocess.run") as mock_run:
            mock_run.side_effect = mock_error

            with pytest.raises(RuntimeError, match="failed"):
                run_yosys(str(script_file))

    def test_run_yosys_nonzero_returncode(self, temp_dir: Path) -> None:
        """Test running Yosys with nonzero return code.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that RuntimeError is raised when returncode is nonzero.
        """
        from src.verilog2spice.synthesizer import run_yosys

        script_file = temp_dir / "test.ys"
        script_file.write_text("read_verilog test.v\n", encoding="utf-8")

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Yosys error"

        with patch("src.verilog2spice.synthesizer.subprocess.run") as mock_run:
            mock_run.return_value = mock_result

            with pytest.raises(RuntimeError, match="failed"):
                run_yosys(str(script_file))


class TestParseYosysJson:
    """Test cases for parse_yosys_json function."""

    def test_parse_yosys_json_success(self, sample_yosys_json: dict) -> None:
        """Test parsing Yosys JSON successfully.

        Args:
            sample_yosys_json: Sample Yosys JSON fixture.

        Tests that Netlist is created from Yosys JSON.
        """
        from src.verilog2spice.synthesizer import parse_yosys_json

        netlist = parse_yosys_json(sample_yosys_json, "test_module")

        assert netlist.top_module == "test_module"
        assert "test_module" in netlist.modules

    def test_parse_yosys_json_top_not_found(self, sample_yosys_json: dict) -> None:
        """Test parsing Yosys JSON when top module not found.

        Args:
            sample_yosys_json: Sample Yosys JSON fixture.

        Tests that first module is used when top module not found.
        """
        from src.verilog2spice.synthesizer import parse_yosys_json

        netlist = parse_yosys_json(sample_yosys_json, "nonexistent_module")

        # Should use first module as fallback
        assert netlist.top_module == "test_module"

    def test_parse_yosys_json_escaped_backslash(self) -> None:
        """Test parsing Yosys JSON with escaped backslash in module name.

        Tests that escaped backslash is handled correctly.
        """
        from src.verilog2spice.synthesizer import parse_yosys_json

        json_data = {
            "modules": {
                "\\test_module": {
                    "ports": {},
                    "cells": {},
                    "netnames": {},
                }
            }
        }

        netlist = parse_yosys_json(json_data, "test_module")

        assert netlist.top_module == "\\test_module"

    def test_parse_yosys_json_empty_modules(self) -> None:
        """Test parsing Yosys JSON with empty modules.

        Tests that empty modules dict is handled correctly.
        """
        from src.verilog2spice.synthesizer import parse_yosys_json

        json_data = {"modules": {}}

        netlist = parse_yosys_json(json_data, "test_module")

        assert netlist.top_module == "test_module"  # Uses provided name as fallback
        assert netlist.modules == {}


class TestSynthesize:
    """Test cases for synthesize function."""

    def test_synthesize_yosys_not_found(self, temp_dir: Path) -> None:
        """Test synthesize when Yosys is not found.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that RuntimeError is raised when Yosys is not available.
        """
        from src.verilog2spice.synthesizer import synthesize

        with patch("src.verilog2spice.synthesizer.check_yosys", return_value=False):
            with pytest.raises(RuntimeError, match="Yosys is required"):
                synthesize(verilog_files=["test.v"], top_module="test")

    def test_synthesize_custom_script_exists(
        self, temp_dir: Path, sample_yosys_json: dict
    ) -> None:
        """Test synthesize with custom script that exists.

        Args:
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON fixture.

        Tests that custom script is used when provided and exists.
        """
        from src.verilog2spice.synthesizer import synthesize

        script_file = temp_dir / "custom.ys"
        script_file.write_text(
            "read_verilog test.v\nwrite_json netlist.json\n", encoding="utf-8"
        )
        netlist_file = temp_dir / "netlist.json"

        import json

        netlist_file.write_text(json.dumps(sample_yosys_json), encoding="utf-8")

        with patch("src.verilog2spice.synthesizer.check_yosys", return_value=True):
            with patch("src.verilog2spice.synthesizer.run_yosys") as mock_run:
                mock_run.return_value = None

                netlist = synthesize(
                    verilog_files=["test.v"],
                    top_module="test_module",
                    script=str(script_file),
                    output_dir=str(temp_dir),
                )

                assert netlist is not None
                assert netlist.top_module == "test_module"

    def test_synthesize_custom_script_no_output_dir(
        self, temp_dir: Path, sample_yosys_json: dict
    ) -> None:
        """Test synthesize with custom script and no output_dir.

        Args:
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON fixture.

        Tests that netlist path uses tempdir when output_dir is None (line 106).
        """
        import tempfile
        import json
        from src.verilog2spice.synthesizer import synthesize

        script_file = temp_dir / "custom.ys"
        script_file.write_text(
            "read_verilog test.v\nwrite_json netlist.json\n", encoding="utf-8"
        )
        netlist_file = Path(tempfile.gettempdir()) / "netlist.json"

        netlist_file.write_text(json.dumps(sample_yosys_json), encoding="utf-8")

        try:
            with patch("src.verilog2spice.synthesizer.check_yosys", return_value=True):
                with patch("src.verilog2spice.synthesizer.run_yosys"):
                    netlist = synthesize(
                        verilog_files=["test.v"],
                        top_module="test_module",
                        script=str(script_file),
                        output_dir=None,
                    )

                    assert netlist is not None
                    assert netlist.top_module == "test_module"
        finally:
            # Cleanup
            if netlist_file.exists():
                netlist_file.unlink()

    def test_run_yosys_with_warnings(self, temp_dir: Path) -> None:
        """Test running Yosys with warnings in stderr.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that warnings in stderr are logged (line 236).
        """
        from src.verilog2spice.synthesizer import run_yosys

        script_file = temp_dir / "test.ys"
        script_file.write_text("read_verilog test.v\n", encoding="utf-8")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Yosys output"
        mock_result.stderr = "Warning: Some warning message"

        with patch("src.verilog2spice.synthesizer.subprocess.run") as mock_run:
            mock_run.return_value = mock_result

            # Should not raise an exception
            run_yosys(str(script_file))

            mock_run.assert_called_once()

    def test_synthesize_default_script(
        self, temp_dir: Path, sample_yosys_json: dict
    ) -> None:
        """Test synthesize with default script creation.

        Args:
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON fixture.

        Tests that default script is created when custom script not provided.
        """
        from src.verilog2spice.synthesizer import synthesize

        verilog_file = temp_dir / "test.v"
        verilog_file.write_text("module test_module(); endmodule\n", encoding="utf-8")
        netlist_file = temp_dir / "netlist.json"

        import json

        netlist_file.write_text(json.dumps(sample_yosys_json), encoding="utf-8")

        with patch("src.verilog2spice.synthesizer.check_yosys", return_value=True):
            with patch("src.verilog2spice.synthesizer.run_yosys") as mock_run:
                mock_run.return_value = None

                netlist = synthesize(
                    verilog_files=[str(verilog_file)],
                    top_module="test_module",
                    output_dir=str(temp_dir),
                )

                assert netlist is not None
                mock_run.assert_called_once()

    def test_synthesize_json_file_not_found(self, temp_dir: Path) -> None:
        """Test synthesize when JSON output file is not found.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that RuntimeError is raised when netlist JSON file doesn't exist.
        """
        from src.verilog2spice.synthesizer import synthesize

        with patch("src.verilog2spice.synthesizer.check_yosys", return_value=True):
            with patch("src.verilog2spice.synthesizer.run_yosys"):
                with patch(
                    "src.verilog2spice.synthesizer.create_default_synthesis_script"
                ) as mock_create:
                    mock_create.return_value = (
                        "script.ys",
                        temp_dir / "nonexistent.json",
                    )

                    with pytest.raises(
                        RuntimeError, match="JSON output file not found"
                    ):
                        synthesize(
                            verilog_files=["test.v"],
                            top_module="test",
                            output_dir=str(temp_dir),
                        )

    def test_synthesize_json_decode_error(self, temp_dir: Path) -> None:
        """Test synthesize when JSON decode fails.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that RuntimeError is raised on JSON decode error.
        """
        from src.verilog2spice.synthesizer import synthesize

        netlist_file = temp_dir / "netlist.json"
        netlist_file.write_text("invalid json", encoding="utf-8")

        with patch("src.verilog2spice.synthesizer.check_yosys", return_value=True):
            with patch("src.verilog2spice.synthesizer.run_yosys"):
                with patch(
                    "src.verilog2spice.synthesizer.create_default_synthesis_script"
                ) as mock_create:
                    mock_create.return_value = ("script.ys", netlist_file)

                    with pytest.raises(RuntimeError, match="Synthesis failed"):
                        synthesize(
                            verilog_files=["test.v"],
                            top_module="test",
                            output_dir=str(temp_dir),
                        )

    def test_synthesize_with_include_paths_and_defines(
        self, temp_dir: Path, sample_yosys_json: dict
    ) -> None:
        """Test synthesize with include paths and defines.

        Args:
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON fixture.

        Tests that include paths and defines are passed to script creation.
        """
        from src.verilog2spice.synthesizer import synthesize

        verilog_file = temp_dir / "test.v"
        verilog_file.write_text("module test(); endmodule\n", encoding="utf-8")
        netlist_file = temp_dir / "netlist.json"

        import json

        netlist_file.write_text(json.dumps(sample_yosys_json), encoding="utf-8")

        with patch("src.verilog2spice.synthesizer.check_yosys", return_value=True):
            with patch("src.verilog2spice.synthesizer.run_yosys"):
                netlist = synthesize(
                    verilog_files=[str(verilog_file)],
                    top_module="test_module",
                    output_dir=str(temp_dir),
                    include_paths=["/include/path"],
                    defines={"DEFINE1": "value1", "DEFINE2": "value2"},
                )

                assert netlist is not None

    def test_synthesize_with_optimize(
        self, temp_dir: Path, sample_yosys_json: dict
    ) -> None:
        """Test synthesize with optimization enabled.

        Args:
            temp_dir: Temporary directory for test files.
            sample_yosys_json: Sample Yosys JSON fixture.

        Tests that optimization flag is passed to script creation.
        """
        from src.verilog2spice.synthesizer import synthesize

        verilog_file = temp_dir / "test.v"
        verilog_file.write_text("module test(); endmodule\n", encoding="utf-8")
        netlist_file = temp_dir / "netlist.json"

        import json

        netlist_file.write_text(json.dumps(sample_yosys_json), encoding="utf-8")

        with patch("src.verilog2spice.synthesizer.check_yosys", return_value=True):
            with patch("src.verilog2spice.synthesizer.run_yosys"):
                netlist = synthesize(
                    verilog_files=[str(verilog_file)],
                    top_module="test_module",
                    output_dir=str(temp_dir),
                    optimize=True,
                )

                assert netlist is not None

    def test_synthesize_timeout_error(self, temp_dir: Path) -> None:
        """Test synthesize when timeout occurs.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that RuntimeError is raised on timeout.
        """
        from src.verilog2spice.synthesizer import synthesize
        import subprocess

        with patch("src.verilog2spice.synthesizer.check_yosys", return_value=True):
            with patch("src.verilog2spice.synthesizer.run_yosys") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("yosys", timeout=300)

                with pytest.raises(RuntimeError, match="Synthesis failed"):
                    synthesize(
                        verilog_files=["test.v"],
                        top_module="test",
                        output_dir=str(temp_dir),
                    )

    def test_synthesize_os_error(self, temp_dir: Path) -> None:
        """Test synthesize when OSError occurs.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that RuntimeError is raised on OSError.
        """
        from src.verilog2spice.synthesizer import synthesize

        with patch("src.verilog2spice.synthesizer.check_yosys", return_value=True):
            with patch("src.verilog2spice.synthesizer.run_yosys") as mock_run:
                mock_run.side_effect = OSError("Permission denied")

                with pytest.raises(RuntimeError, match="Synthesis failed"):
                    synthesize(
                        verilog_files=["test.v"],
                        top_module="test",
                        output_dir=str(temp_dir),
                    )
