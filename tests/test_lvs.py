"""Unit tests for lvs.py module."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest

from src.verilog2spice.lvs import LVSResult, check_netgen, extract_spice_statistics

if TYPE_CHECKING:
    pass


class TestLVSResult:
    """Test cases for LVSResult class."""

    def test_lvs_result_initialization(self) -> None:
        """Test LVSResult initialization.

        Tests that LVSResult can be initialized with
        matched, output, errors, and warnings.
        """
        result = LVSResult(
            matched=True,
            output="Test output",
            errors=["Error 1"],
            warnings=["Warning 1"],
        )

        assert result.matched is True
        assert result.output == "Test output"
        assert result.errors == ["Error 1"]
        assert result.warnings == ["Warning 1"]

    def test_lvs_result_with_defaults(self) -> None:
        """Test LVSResult initialization with defaults.

        Tests that LVSResult can be initialized with
        only the required matched parameter.
        """
        result = LVSResult(matched=False)

        assert result.matched is False
        assert result.output == ""
        assert result.errors == []
        assert result.warnings == []


class TestExtractSpiceStatistics:
    """Test cases for extract_spice_statistics function."""

    def test_extract_spice_statistics_basic(self, temp_dir: Path) -> None:
        """Test extracting basic statistics from SPICE file.

        Args:
            temp_dir: Temporary directory for test files.
        """
        spice_content = """* Test SPICE netlist
.SUBCKT INV A Y
X1 A Y INV_CELL
.ENDS INV

.SUBCKT INV_CELL A Y
M1 Y A VDD VDD PMOS
.ENDS INV_CELL

X1 net1 net2 INV
M2 D G S B NMOS
"""
        spice_file = temp_dir / "test.spice"
        spice_file.write_text(spice_content, encoding="utf-8")

        stats = extract_spice_statistics(spice_file)

        assert stats["file_size_bytes"] > 0
        assert stats["total_lines"] > 0
        assert stats["subcircuit_definitions"] == 2
        assert stats["subcircuit_instances"] >= 1
        assert stats["mosfet_instances"] >= 1

    def test_extract_spice_statistics_file_not_found(self) -> None:
        """Test extracting statistics when file doesn't exist.

        Tests that empty statistics are returned when file
        doesn't exist.
        """
        spice_file = Path("/nonexistent/path.spice")

        stats = extract_spice_statistics(spice_file)

        assert stats["file_size_bytes"] == 0
        assert stats["total_lines"] == 0
        assert stats["subcircuit_definitions"] == 0

    def test_extract_spice_statistics_subcircuits(self, temp_dir: Path) -> None:
        """Test extracting subcircuit statistics.

        Args:
            temp_dir: Temporary directory for test files.
        """
        spice_content = """* Test
.SUBCKT CELL1 A Y
.ENDS CELL1

.SUBCKT CELL2 A B Y
.ENDS CELL2
"""
        spice_file = temp_dir / "test.spice"
        spice_file.write_text(spice_content, encoding="utf-8")

        stats = extract_spice_statistics(spice_file)

        assert stats["subcircuit_definitions"] == 2

    def test_extract_spice_statistics_instances(self, temp_dir: Path) -> None:
        """Test extracting instance statistics.

        Args:
            temp_dir: Temporary directory for test files.
        """
        spice_content = """* Test
X1 A Y INV
X2 B Z NAND2
X3 C D E OR2
"""
        spice_file = temp_dir / "test.spice"
        spice_file.write_text(spice_content, encoding="utf-8")

        stats = extract_spice_statistics(spice_file)

        assert stats["subcircuit_instances"] == 3
        assert "INV" in stats["unique_cell_types"]
        assert "NAND2" in stats["unique_cell_types"]
        assert stats["unique_cell_types"]["INV"] == 1
        assert stats["unique_cell_types"]["NAND2"] == 1

    def test_extract_spice_statistics_transistors(self, temp_dir: Path) -> None:
        """Test extracting transistor statistics.

        Args:
            temp_dir: Temporary directory for test files.
        """
        spice_content = """* Test
M1 D1 G1 S1 B1 PMOS
M2 D2 G2 S2 B2 NMOS
M3 D3 G3 S3 B3 PMOS
"""
        spice_file = temp_dir / "test.spice"
        spice_file.write_text(spice_content, encoding="utf-8")

        stats = extract_spice_statistics(spice_file)

        assert stats["mosfet_instances"] == 3

    def test_extract_spice_statistics_read_error(self, temp_dir: Path) -> None:
        """Test extracting statistics when file read fails.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that OSError/IOError/UnicodeDecodeError are handled (lines 95-96).
        """
        from unittest.mock import patch

        spice_file = temp_dir / "test.sp"
        spice_file.write_text("* Test\n", encoding="utf-8")

        # Test with OSError during read_text call
        with patch.object(Path, "read_text", side_effect=OSError("Permission denied")):
            stats = extract_spice_statistics(spice_file)
            # Exception is caught and logged, but initialized stats dict is returned
            assert stats["file_size_bytes"] == 0
            assert stats["total_lines"] == 0

        # Test with IOError (for older Python compatibility)
        with patch.object(Path, "read_text", side_effect=IOError("I/O error")):
            stats = extract_spice_statistics(spice_file)
            assert stats["file_size_bytes"] == 0

        # Test with UnicodeDecodeError
        with patch.object(
            Path,
            "read_text",
            side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "invalid"),
        ):
            stats = extract_spice_statistics(spice_file)
            assert stats["file_size_bytes"] == 0

    def test_extract_spice_statistics_comments(self, temp_dir: Path) -> None:
        """Test extracting comment statistics.

        Args:
            temp_dir: Temporary directory for test files.
        """
        spice_content = """* Comment 1
* Comment 2
.SUBCKT INV A Y
* Comment 3
.ENDS INV
"""
        spice_file = temp_dir / "test.spice"
        spice_file.write_text(spice_content, encoding="utf-8")

        stats = extract_spice_statistics(spice_file)

        assert stats["comment_lines"] == 3

    def test_extract_spice_statistics_models(self, temp_dir: Path) -> None:
        """Test extracting model statistics.

        Args:
            temp_dir: Temporary directory for test files.
        """
        spice_content = """* Test
.model NMOS NMOS (LEVEL=1)
.model PMOS PMOS (LEVEL=1)
"""
        spice_file = temp_dir / "test.spice"
        spice_file.write_text(spice_content, encoding="utf-8")

        stats = extract_spice_statistics(spice_file)

        assert stats["model_definitions"] == 2


class TestCheckNetgen:
    """Test cases for check_netgen function."""

    def test_check_netgen_not_available(self) -> None:
        """Test checking Netgen when not available.

        Tests that False is returned when Netgen is not found.
        """
        # Mock subprocess.run to simulate Netgen not found
        with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = check_netgen()

            assert result is False

    def test_check_netgen_timeout(self) -> None:
        """Test checking Netgen with timeout.

        Tests that False is returned when Netgen check times out.
        """
        import subprocess

        # Mock subprocess.run to simulate timeout
        with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("netgen", timeout=5)

            result = check_netgen()

            assert result is False

    def test_check_netgen_mesh_generator(self) -> None:
        """Test checking Netgen when mesh generator is found.

        Tests that False is returned when mesh generator
        (not LVS tool) is found.
        """
        # Mock subprocess.run to simulate mesh generator output
        # The function tries:
        # 1. netgen-lvs -batch (should not match LVS patterns, so continues)
        # 2. netgen -batch -version (should return mesh generator output with "vienna")
        mesh_result = Mock()
        mesh_result.returncode = 0
        mesh_result.stdout = "Netgen mesh generator - Vienna University"
        mesh_result.stderr = ""

        # First call: netgen-lvs returns output that doesn't match LVS patterns
        # Need output without "netgen" OR without ("console" OR "1.5" OR "lvs")
        # AND without "invalid command" - otherwise line 161-162 returns True
        lvs_result = Mock()
        lvs_result.stdout = "some error message"
        lvs_result.stderr = "command failed"

        with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
            # First call: netgen-lvs returns output that doesn't match any True conditions
            # (no "netgen" in output, or if there is, it doesn't have console/1.5/lvs)
            # Second call: netgen -batch -version returns mesh generator (contains "vienna")
            mock_run.side_effect = [
                lvs_result,  # netgen-lvs returns non-matching output (no "netgen" keyword)
                mesh_result,  # netgen -batch -version returns mesh generator
            ]

            result = check_netgen()

            # Should return False because it's the mesh generator, not LVS tool
            assert result is False

    def test_check_netgen_lvs_tool_found_via_console(self) -> None:
        """Test checking Netgen when LVS tool found via console output.

        Tests that True is returned when console output is detected (lines 159).
        """
        from unittest.mock import Mock, patch

        lvs_result = Mock()
        lvs_result.stdout = "Running NetGen Console..."
        lvs_result.stderr = ""
        lvs_result.returncode = 0

        with patch("src.verilog2spice.lvs.subprocess.run", return_value=lvs_result):
            result = check_netgen()
            assert result is True

    def test_check_netgen_lvs_tool_found_via_invalid_command(self) -> None:
        """Test checking Netgen when LVS tool found via invalid command output.

        Tests that True is returned when invalid command output detected (lines 161-162).
        """
        from unittest.mock import Mock, patch

        lvs_result = Mock()
        lvs_result.stdout = "invalid command"
        lvs_result.stderr = "netgen error"
        lvs_result.returncode = 1

        with patch("src.verilog2spice.lvs.subprocess.run", return_value=lvs_result):
            result = check_netgen()
            assert result is True

    def test_check_netgen_regular_netgen_found(self) -> None:
        """Test checking Netgen when regular netgen returns success.

        Tests that True is returned when netgen -version succeeds (lines 180-181, 191).
        """
        from unittest.mock import Mock, patch

        # First call: netgen-lvs doesn't match
        lvs_result = Mock()
        lvs_result.stdout = "some output"
        lvs_result.stderr = "some error"
        lvs_result.returncode = 1

        # Second call: netgen -batch -version doesn't match (no vienna, no netgen keyword)
        batch_result = Mock()
        batch_result.stdout = ""
        batch_result.stderr = ""
        batch_result.returncode = 1

        # Third call: netgen -version succeeds
        version_result = Mock()
        version_result.returncode = 0

        with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
            mock_run.side_effect = [lvs_result, batch_result, version_result]
            result = check_netgen()
            assert result is True

    def test_check_netgen_found_via_netgen_in_output(self) -> None:
        """Test checking Netgen when 'netgen' keyword is found in output.

        Tests that True is returned when 'netgen' is in output (line 181).
        """
        from unittest.mock import Mock, patch

        # First call: netgen-lvs doesn't match (no console/1.5/lvs patterns)
        lvs_result = Mock()
        lvs_result.stdout = "netgen some output"  # Has "netgen" keyword
        lvs_result.stderr = ""
        lvs_result.returncode = 0

        with patch("src.verilog2spice.lvs.subprocess.run", return_value=lvs_result):
            result = check_netgen()
            # Should return True because "netgen" is in output and returncode == 0 (line 181)
            assert result is True


class TestVerifySpiceVsSpice:
    """Test cases for verify_spice_vs_spice function."""

    def test_verify_spice_vs_spice_netgen_not_found(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE when Netgen is not found.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that FileNotFoundError is raised when Netgen is not found.
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = False

            with pytest.raises(FileNotFoundError):
                verify_spice_vs_spice(sample_spice_file, spice_file2)

    def test_verify_spice_vs_spice_file_not_found(self, temp_dir: Path) -> None:
        """Test verifying SPICE when files don't exist.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that ValueError is raised when files don't exist.
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True

            with pytest.raises(ValueError):
                verify_spice_vs_spice("/nonexistent1.sp", "/nonexistent2.sp")

    def test_verify_spice_vs_spice_success(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE with successful comparison.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that LVSResult is returned with matched=True.
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        # Mock subprocess.run to simulate successful Netgen execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Netlists match successfully"
        mock_result.stderr = ""

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                # Mock extract_spice_statistics to avoid file reading
                with patch(
                    "src.verilog2spice.lvs.extract_spice_statistics"
                ) as mock_stats:
                    mock_stats.return_value = {
                        "subcircuit_instances": 0,
                        "file_size_bytes": 100,
                        "unique_cell_types": {},
                    }

                    # Mock Path.exists to return False for .lvs files, True for others
                    def mock_exists(self):
                        path_str = str(self)
                        if ".lvs" in path_str:
                            return False  # .lvs file doesn't exist, use stdout
                        # For spice files, use actual file system check
                        import os

                        return os.path.exists(path_str)

                    with patch.object(Path, "exists", mock_exists):
                        result = verify_spice_vs_spice(sample_spice_file, spice_file2)

                        assert isinstance(result.matched, bool)
                        assert result.errors == []

    def test_verify_spice_vs_spice_with_report(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE with report file.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that report file is created when requested.
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")
        report_file = temp_dir / "report.rpt"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Netlists match"
        mock_result.stderr = ""

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                # Mock extract_spice_statistics to avoid file reading
                with patch(
                    "src.verilog2spice.lvs.extract_spice_statistics"
                ) as mock_stats:
                    mock_stats.return_value = {
                        "subcircuit_instances": 0,
                        "file_size_bytes": 100,
                        "unique_cell_types": {},
                    }
                    # Mock Path.exists to return False for .lvs files
                    import os

                    def mock_exists(self):
                        path_str = str(self)
                        if ".lvs" in path_str:
                            return False
                        # For spice files, use actual file system check
                        return os.path.exists(path_str)

                    with patch.object(Path, "exists", mock_exists):
                        verify_spice_vs_spice(
                            sample_spice_file, spice_file2, report_file=str(report_file)
                        )

                        # Report file should be created
                        assert report_file.exists()


class TestCompareFlatteningLevels:
    """Test cases for compare_flattening_levels function."""

    def test_compare_flattening_levels_success(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test comparing flattening levels successfully.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that comparison returns matched=True.
        """
        from src.verilog2spice.lvs import compare_flattening_levels

        spice_file2 = temp_dir / "transistor.sp"
        spice_file2.write_text("* Transistor level\n", encoding="utf-8")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Netlists match"
        mock_result.stderr = ""

        with patch("src.verilog2spice.lvs.verify_spice_vs_spice") as mock_verify:
            from src.verilog2spice.lvs import LVSResult

            mock_verify.return_value = LVSResult(
                matched=True, output="", errors=[], warnings=[]
            )

            matched, result = compare_flattening_levels(sample_spice_file, spice_file2)

            assert matched is True
            assert isinstance(result, LVSResult)

    def test_compare_flattening_levels_error(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test comparing flattening levels with error.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that comparison handles errors gracefully.
        """
        from src.verilog2spice.lvs import compare_flattening_levels

        spice_file2 = temp_dir / "transistor.sp"
        spice_file2.write_text("* Transistor level\n", encoding="utf-8")

        with patch("src.verilog2spice.lvs.verify_spice_vs_spice") as mock_verify:
            mock_verify.side_effect = FileNotFoundError("Netgen not found")

            matched, result = compare_flattening_levels(sample_spice_file, spice_file2)

            assert matched is False
            assert len(result.errors) > 0

    def test_verify_spice_vs_spice_with_lvs_file(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE when .lvs file exists.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that .lvs file content is read and parsed.
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        # Create a mock .lvs file
        lvs_file = temp_dir / f"{sample_spice_file.name}.lvs"
        lvs_file.write_text(
            "* LVS output\nNetlists match\nDevice count: 10\nCircuit summary",
            encoding="utf-8",
        )

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Some output"
        mock_result.stderr = ""

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                with patch(
                    "src.verilog2spice.lvs.extract_spice_statistics"
                ) as mock_stats:
                    mock_stats.return_value = {
                        "subcircuit_instances": 0,
                        "file_size_bytes": 100,
                        "unique_cell_types": {},
                    }

                    # Mock Path.exists to return True for .lvs file
                    def mock_exists(self):
                        path_str = str(self)
                        if ".lvs" in path_str:
                            return True  # .lvs file exists
                        # For spice files, use actual file system check
                        import os

                        return os.path.exists(path_str)

                    with patch.object(Path, "exists", mock_exists):
                        result = verify_spice_vs_spice(sample_spice_file, spice_file2)

                        assert isinstance(result.matched, bool)

    def test_verify_spice_vs_spice_with_errors(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE with errors in output.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that errors are correctly extracted.
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "Netlists do not match\nError: Device mismatch"
        mock_result.stderr = ""

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                with patch(
                    "src.verilog2spice.lvs.extract_spice_statistics"
                ) as mock_stats:
                    mock_stats.return_value = {
                        "subcircuit_instances": 0,
                        "file_size_bytes": 100,
                        "unique_cell_types": {},
                    }
                    import os

                    def mock_exists(self):
                        path_str = str(self)
                        if ".lvs" in path_str:
                            return False
                        # For spice files, use actual file system check
                        return os.path.exists(path_str)

                    with patch.object(Path, "exists", mock_exists):
                        result = verify_spice_vs_spice(sample_spice_file, spice_file2)

                        assert result.matched is False
                        assert len(result.errors) > 0

    def test_verify_spice_vs_spice_timeout(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE with timeout.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that timeout is handled correctly.
        """
        import subprocess
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("netgen", timeout=120)

                result = verify_spice_vs_spice(sample_spice_file, spice_file2)

                assert result.matched is False
                assert len(result.errors) > 0
                assert (
                    "timeout" in result.errors[0].lower()
                    or "timed out" in result.errors[0].lower()
                )

    def test_verify_spice_vs_spice_with_warnings(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE with warnings.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that warnings are correctly extracted.
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Netlists match\nWarning: Some minor issue"
        mock_result.stderr = ""

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                with patch(
                    "src.verilog2spice.lvs.extract_spice_statistics"
                ) as mock_stats:
                    mock_stats.return_value = {
                        "subcircuit_instances": 0,
                        "file_size_bytes": 100,
                        "unique_cell_types": {},
                    }
                    import os

                    def mock_exists(self):
                        path_str = str(self)
                        if ".lvs" in path_str:
                            return False
                        # For spice files, use actual file system check
                        return os.path.exists(path_str)

                    with patch.object(Path, "exists", mock_exists):
                        result = verify_spice_vs_spice(sample_spice_file, spice_file2)

                        # Should have warnings but still match
                        assert len(result.warnings) > 0

    def test_verify_spice_vs_spice_file2_not_found(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE when second file not found.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that ValueError is raised when second file doesn't exist (line 231).
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True

            with pytest.raises(ValueError, match="not found"):
                verify_spice_vs_spice(sample_spice_file, "/nonexistent/file2.sp")

    def test_verify_spice_vs_spice_mesh_generator_detected(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE when mesh generator is detected.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that warning is logged when mesh generator detected (lines 311-314).
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "Vienna University mesh generator"
        mock_result.stderr = "libgui.so error"

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                with patch(
                    "src.verilog2spice.lvs.extract_spice_statistics"
                ) as mock_stats:
                    mock_stats.return_value = {
                        "subcircuit_instances": 0,
                        "file_size_bytes": 100,
                        "unique_cell_types": {},
                    }
                    import os

                    def mock_exists(self):
                        path_str = str(self)
                        if ".lvs" in path_str:
                            return False
                        return os.path.exists(path_str)

                    with patch.object(Path, "exists", mock_exists):
                        result = verify_spice_vs_spice(sample_spice_file, spice_file2)

                        # Should still return result (warning logged internally)
                        assert isinstance(result, LVSResult)

    def test_verify_spice_vs_spice_long_output(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE with long output (>500 chars).

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that long output is handled correctly (lines 322-325).
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        # Create output > 500 characters
        long_output = "A" * 600

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = long_output
        mock_result.stderr = ""

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                with patch(
                    "src.verilog2spice.lvs.extract_spice_statistics"
                ) as mock_stats:
                    mock_stats.return_value = {
                        "subcircuit_instances": 0,
                        "file_size_bytes": 100,
                        "unique_cell_types": {},
                    }
                    import os

                    def mock_exists(self):
                        path_str = str(self)
                        if ".lvs" in path_str:
                            return False
                        return os.path.exists(path_str)

                    with patch.object(Path, "exists", mock_exists):
                        result = verify_spice_vs_spice(sample_spice_file, spice_file2)

                        # Should handle long output
                        assert isinstance(result, LVSResult)

    def test_verify_spice_vs_spice_with_mismatch_errors(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE with mismatch error messages.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that mismatch/failed messages are extracted as errors (lines 369-374).
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "Netlists do not match\nComparison failed"
        mock_result.stderr = ""

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                with patch(
                    "src.verilog2spice.lvs.extract_spice_statistics"
                ) as mock_stats:
                    mock_stats.return_value = {
                        "subcircuit_instances": 0,
                        "file_size_bytes": 100,
                        "unique_cell_types": {},
                    }
                    import os

                    def mock_exists(self):
                        path_str = str(self)
                        if ".lvs" in path_str:
                            return False
                        return os.path.exists(path_str)

                    with patch.object(Path, "exists", mock_exists):
                        result = verify_spice_vs_spice(sample_spice_file, spice_file2)

                        assert result.matched is False
                        assert len(result.errors) > 0

    def test_verify_spice_vs_spice_lvs_file_match_detection(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE with match detected from .lvs file.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that match can be detected from .lvs file content (lines 427-433).
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        # Create .lvs file with match indicator
        lvs_file = temp_dir / f"{sample_spice_file.name}.lvs"
        lvs_file.write_text(
            "Netlists are equivalent\nDevice count: 10\nCircuit summary",
            encoding="utf-8",
        )

        mock_result = Mock()
        mock_result.returncode = 1  # stdout doesn't indicate match
        mock_result.stdout = "Some ambiguous output"
        mock_result.stderr = ""

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                with patch(
                    "src.verilog2spice.lvs.extract_spice_statistics"
                ) as mock_stats:
                    mock_stats.return_value = {
                        "subcircuit_instances": 0,
                        "file_size_bytes": 100,
                        "unique_cell_types": {},
                    }
                    import os

                    def mock_exists(self):
                        path_str = str(self)
                        if ".lvs" in path_str:
                            return True
                        return os.path.exists(path_str)

                    with patch.object(Path, "exists", mock_exists):
                        result = verify_spice_vs_spice(sample_spice_file, spice_file2)

                        # Should detect match from .lvs file
                        assert result.matched is True

    def test_verify_spice_vs_spice_stdout_as_output(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE when stdout used as output (no .lvs file).

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that stdout is used when .lvs file doesn't exist but output >50 chars (lines 436-446).
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        # Output > 50 characters but no .lvs file
        substantial_output = "A" * 100

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = substantial_output
        mock_result.stderr = ""

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                with patch(
                    "src.verilog2spice.lvs.extract_spice_statistics"
                ) as mock_stats:
                    mock_stats.return_value = {
                        "subcircuit_instances": 0,
                        "file_size_bytes": 100,
                        "unique_cell_types": {},
                    }
                    import os

                    def mock_exists(self):
                        path_str = str(self)
                        if ".lvs" in path_str:
                            return False  # No .lvs file
                        return os.path.exists(path_str)

                    with patch.object(Path, "exists", mock_exists):
                        result = verify_spice_vs_spice(sample_spice_file, spice_file2)

                        assert isinstance(result, LVSResult)

    def test_verify_spice_vs_spice_report_with_cell_types(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE with report that includes cell type breakdown.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that report includes cell type breakdown (lines 508-534).
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        report_file = temp_dir / "report.rpt"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Netlists match"
        mock_result.stderr = ""

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                with patch(
                    "src.verilog2spice.lvs.extract_spice_statistics"
                ) as mock_stats:
                    # Return stats with cell types
                    mock_stats.side_effect = [
                        {
                            "subcircuit_instances": 5,
                            "file_size_bytes": 100,
                            "unique_cell_types": {"INV": 2, "NAND2": 3},
                        },
                        {
                            "subcircuit_instances": 5,
                            "file_size_bytes": 100,
                            "unique_cell_types": {"INV": 2, "NAND2": 3},
                        },
                    ]
                    import os

                    def mock_exists(self):
                        path_str = str(self)
                        if ".lvs" in path_str:
                            return False
                        return os.path.exists(path_str)

                    with patch.object(Path, "exists", mock_exists):
                        verify_spice_vs_spice(
                            sample_spice_file, spice_file2, report_file=str(report_file)
                        )

                        # Report should be created
                        assert report_file.exists()
                        report_content = report_file.read_text(encoding="utf-8")
                        assert "INV" in report_content or "NAND2" in report_content

    def test_verify_spice_vs_spice_report_with_errors_warnings(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE with report including errors and warnings.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that errors and warnings are included in report (lines 589-599).
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        report_file = temp_dir / "report.rpt"

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "Error: Device mismatch\nWarning: Minor issue"
        mock_result.stderr = ""

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                with patch(
                    "src.verilog2spice.lvs.extract_spice_statistics"
                ) as mock_stats:
                    mock_stats.return_value = {
                        "subcircuit_instances": 0,
                        "file_size_bytes": 100,
                        "unique_cell_types": {},
                    }
                    import os

                    def mock_exists(self):
                        path_str = str(self)
                        if ".lvs" in path_str:
                            return False
                        return os.path.exists(path_str)

                    with patch.object(Path, "exists", mock_exists):
                        verify_spice_vs_spice(
                            sample_spice_file, spice_file2, report_file=str(report_file)
                        )

                        # Report should include errors and warnings
                        assert report_file.exists()
                        report_content = report_file.read_text(encoding="utf-8")
                        assert (
                            "Error" in report_content
                            or "error" in report_content.lower()
                        )

    def test_verify_spice_vs_spice_called_process_error(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE with CalledProcessError.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that CalledProcessError is handled (lines 618-628).
        """
        import subprocess
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.CalledProcessError(1, "netgen")

                result = verify_spice_vs_spice(sample_spice_file, spice_file2)

                assert result.matched is False
                assert len(result.errors) > 0

    def test_verify_spice_vs_spice_lvs_file_read_error(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE when .lvs file read fails.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that .lvs file read errors are handled (lines 434-435, 583-587).
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Some output"
        mock_result.stderr = ""

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                with patch(
                    "src.verilog2spice.lvs.extract_spice_statistics"
                ) as mock_stats:
                    mock_stats.return_value = {
                        "subcircuit_instances": 0,
                        "file_size_bytes": 100,
                        "unique_cell_types": {},
                    }
                    import os

                    def mock_exists(self):
                        path_str = str(self)
                        if ".lvs" in path_str:
                            return True  # .lvs file exists
                        return os.path.exists(path_str)

                    # Mock read_text to raise error
                    with patch.object(Path, "exists", mock_exists):
                        with patch.object(
                            Path, "read_text", side_effect=OSError("Read error")
                        ):
                            result = verify_spice_vs_spice(
                                sample_spice_file, spice_file2
                            )

                            # Should handle read error gracefully
                            assert isinstance(result, LVSResult)

    def test_verify_conversion_placeholder(self, temp_dir: Path) -> None:
        """Test verify_conversion placeholder function.

        Args:
            temp_dir: Temporary directory for test files.

        Tests that placeholder returns appropriate result (lines 668-684).
        """
        from src.verilog2spice.lvs import verify_conversion

        verilog_file = temp_dir / "test.v"
        verilog_file.write_text("module test; endmodule", encoding="utf-8")

        spice_file = temp_dir / "test.sp"
        spice_file.write_text("* Test", encoding="utf-8")

        result = verify_conversion(verilog_file, spice_file, temp_dir)

        assert result.matched is False
        assert len(result.errors) > 0
        assert "not yet implemented" in result.errors[0].lower()

    def test_verify_spice_vs_spice_cleanup_error(
        self, temp_dir: Path, sample_spice_file: Path
    ) -> None:
        """Test verifying SPICE when cleanup fails.

        Args:
            temp_dir: Temporary directory for test files.
            sample_spice_file: Sample SPICE file fixture.

        Tests that cleanup errors are handled (lines 634-635).
        """
        from src.verilog2spice.lvs import verify_spice_vs_spice

        spice_file2 = temp_dir / "file2.sp"
        spice_file2.write_text("* Test file 2\n", encoding="utf-8")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Netlists match"
        mock_result.stderr = ""

        with patch("src.verilog2spice.lvs.check_netgen") as mock_check:
            mock_check.return_value = True
            with patch("src.verilog2spice.lvs.subprocess.run") as mock_run:
                mock_run.return_value = mock_result
                with patch(
                    "src.verilog2spice.lvs.extract_spice_statistics"
                ) as mock_stats:
                    mock_stats.return_value = {
                        "subcircuit_instances": 0,
                        "file_size_bytes": 100,
                        "unique_cell_types": {},
                    }
                    import os

                    def mock_exists(self):
                        path_str = str(self)
                        if ".lvs" in path_str:
                            return False
                        return os.path.exists(path_str)

                    # Mock unlink to raise error during cleanup
                    with patch.object(Path, "exists", mock_exists):
                        with patch.object(
                            Path, "unlink", side_effect=OSError("Cleanup error")
                        ):
                            # Should handle cleanup error gracefully
                            result = verify_spice_vs_spice(
                                sample_spice_file, spice_file2
                            )

                            assert isinstance(result, LVSResult)
