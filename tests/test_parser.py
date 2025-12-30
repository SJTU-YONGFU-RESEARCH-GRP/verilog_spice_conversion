"""Unit tests for parser.py module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.verilog2spice.parser import ModuleInfo, get_top_module, parse_yosys_json

if TYPE_CHECKING:
    pass


class TestModuleInfo:
    """Test cases for ModuleInfo class."""

    def test_module_info_initialization(self) -> None:
        """Test ModuleInfo initialization with all parameters.

        Tests that ModuleInfo can be initialized with name,
        ports, parameters, cells, and nets.
        """
        ports = {"clk": {"direction": "input", "bits": [0]}}
        parameters = {"WIDTH": 8}
        cells = [{"name": "cell1", "type": "INV"}]
        nets = {"net1": {"bits": [1]}}

        module = ModuleInfo(
            name="test_module",
            ports=ports,
            parameters=parameters,
            cells=cells,
            nets=nets,
        )

        assert module.name == "test_module"
        assert module.ports == ports
        assert module.parameters == parameters
        assert module.cells == cells
        assert module.nets == nets

    def test_module_info_with_defaults(self) -> None:
        """Test ModuleInfo initialization with default parameters.

        Tests that ModuleInfo can be initialized with only
        the required name parameter.
        """
        module = ModuleInfo(name="test_module")

        assert module.name == "test_module"
        assert module.ports == {}
        assert module.parameters == {}
        assert module.cells == []
        assert module.nets == {}


class TestParseYosysJson:
    """Test cases for parse_yosys_json function."""

    def test_parse_yosys_json_basic(self, sample_yosys_json: dict) -> None:
        """Test parsing basic Yosys JSON structure.

        Args:
            sample_yosys_json: Sample Yosys JSON data.
        """
        modules = parse_yosys_json(sample_yosys_json)

        assert "test_module" in modules
        module = modules["test_module"]

        assert module.name == "test_module"
        assert "clk" in module.ports
        assert len(module.cells) == 2

    def test_parse_yosys_json_ports(self, sample_yosys_json: dict) -> None:
        """Test parsing ports from Yosys JSON.

        Args:
            sample_yosys_json: Sample Yosys JSON data.
        """
        modules = parse_yosys_json(sample_yosys_json)
        module = modules["test_module"]

        assert module.ports["clk"]["direction"] == "input"
        assert module.ports["clk"]["bits"] == [0]
        assert module.ports["out"]["direction"] == "output"

    def test_parse_yosys_json_cells(self, sample_yosys_json: dict) -> None:
        """Test parsing cells from Yosys JSON.

        Args:
            sample_yosys_json: Sample Yosys JSON data.
        """
        modules = parse_yosys_json(sample_yosys_json)
        module = modules["test_module"]

        assert len(module.cells) == 2
        cell_types = [cell["type"] for cell in module.cells]
        assert "$_NOT_" in cell_types
        assert "$_AND_" in cell_types

    def test_parse_yosys_json_nets(self, sample_yosys_json: dict) -> None:
        """Test parsing nets from Yosys JSON.

        Args:
            sample_yosys_json: Sample Yosys JSON data.
        """
        modules = parse_yosys_json(sample_yosys_json)
        module = modules["test_module"]

        assert "clk" in module.nets
        assert "data" in module.nets
        assert module.nets["clk"]["bits"] == [0]

    def test_parse_yosys_json_with_parameters(self) -> None:
        """Test parsing Yosys JSON with parameter attributes.

        Tests that parameters with _param suffix are parsed (lines 104-106).
        """
        json_data = {
            "modules": {
                "test_module": {
                    "attributes": {
                        "\\WIDTH_param": 8,
                        "\\ENABLE_param": 1,
                        "\\OTHER_attr": "not_a_param",  # Should be ignored
                    },
                    "ports": {},
                    "cells": {},
                    "netnames": {},
                }
            }
        }

        modules = parse_yosys_json(json_data)
        module = modules["test_module"]

        assert "WIDTH" in module.parameters
        assert module.parameters["WIDTH"] == 8
        assert "ENABLE" in module.parameters
        assert module.parameters["ENABLE"] == 1
        assert "OTHER_attr" not in module.parameters

    def test_parse_yosys_json_empty_modules(self) -> None:
        """Test parsing empty modules dictionary.

        Tests that parsing empty modules returns empty dictionary.
        """
        json_data = {"modules": {}}
        modules = parse_yosys_json(json_data)

        assert len(modules) == 0

    def test_parse_yosys_json_multiple_modules(self) -> None:
        """Test parsing multiple modules from Yosys JSON.

        Tests that parsing can handle multiple modules in the JSON.
        """
        json_data = {
            "modules": {
                "module1": {
                    "ports": {},
                    "cells": {},
                    "netnames": {},
                },
                "module2": {
                    "ports": {},
                    "cells": {},
                    "netnames": {},
                },
            }
        }

        modules = parse_yosys_json(json_data)

        assert len(modules) == 2
        assert "module1" in modules
        assert "module2" in modules


class TestGetTopModule:
    """Test cases for get_top_module function."""

    def test_get_top_module_exact_match(self, sample_yosys_json: dict) -> None:
        """Test getting top module with exact name match.

        Args:
            sample_yosys_json: Sample Yosys JSON data.
        """
        modules = parse_yosys_json(sample_yosys_json)
        top_module = get_top_module(modules, "test_module")

        assert top_module.name == "test_module"

    def test_get_top_module_single_module(self) -> None:
        """Test getting top module when only one module exists.

        Tests that when only one module is present, it is
        automatically selected as the top module.
        """
        json_data = {
            "modules": {
                "single_module": {
                    "ports": {},
                    "cells": {},
                    "netnames": {},
                }
            }
        }
        modules = parse_yosys_json(json_data)
        top_module = get_top_module(modules)

        assert top_module.name == "single_module"

    def test_get_top_module_escaped_name(self) -> None:
        """Test getting top module with escaped backslash.

        Tests that module names with escaped backslashes
        are handled correctly.
        """
        json_data = {
            "modules": {
                "\\test_module": {
                    "ports": {},
                    "cells": {},
                    "netnames": {},
                }
            }
        }
        modules = parse_yosys_json(json_data)
        top_module = get_top_module(modules, "test_module")

        assert top_module.name == "\\test_module"

    def test_get_top_module_strip_backslash(self) -> None:
        """Test getting top module with backslash stripping.

        Tests that lstrip logic works correctly (lines 151-152).
        """
        from unittest.mock import patch

        json_data = {
            "modules": {
                "\\test_module": {
                    "ports": {},
                    "cells": {},
                    "netnames": {},
                },
                "other_module": {
                    "ports": {},
                    "cells": {},
                    "netnames": {},
                },
            }
        }
        modules = parse_yosys_json(json_data)

        # Test with logging to verify lines 151-152 are executed
        with patch("src.verilog2spice.parser.logger") as mock_logger:
            top_module = get_top_module(modules, "test_module")

            # Should match via lstrip logic (lines 150-152)
            assert top_module.name == "\\test_module"
            # This should execute the logger.info at line 151
            mock_logger.info.assert_called_once()
            assert "test_module" in mock_logger.info.call_args[0][0]

    def test_get_top_module_not_found(self, sample_yosys_json: dict) -> None:
        """Test getting top module when name doesn't exist.

        Args:
            sample_yosys_json: Sample Yosys JSON data.
        """
        modules = parse_yosys_json(sample_yosys_json)

        with pytest.raises(ValueError, match="not found"):
            get_top_module(modules, "nonexistent_module")

    def test_get_top_module_auto_detect(self) -> None:
        """Test auto-detecting top module.

        Tests that the top module is auto-detected when
        not explicitly specified.
        """
        json_data = {
            "modules": {
                "parent_module": {
                    "ports": {},
                    "cells": {
                        "child_inst": {
                            "type": "child_module",
                            "port_directions": {},
                            "connections": {},
                        }
                    },
                    "netnames": {},
                },
                "child_module": {
                    "ports": {},
                    "cells": {},
                    "netnames": {},
                },
            }
        }
        modules = parse_yosys_json(json_data)
        top_module = get_top_module(modules)

        # Should detect parent_module as top (not used as cell type)
        assert top_module.name == "parent_module"

    def test_get_top_module_fallback_to_first(self) -> None:
        """Test fallback to first module when auto-detection fails.

        Tests that first module is used with warning when no clear top (lines 191-196).
        """
        json_data = {
            "modules": {
                "module1": {
                    "ports": {},
                    "cells": {
                        "inst1": {
                            "type": "module2",  # module1 uses module2
                            "port_directions": {},
                            "connections": {},
                        }
                    },
                    "netnames": {},
                },
                "module2": {
                    "ports": {},
                    "cells": {
                        "inst2": {
                            "type": "module1",  # module2 uses module1 (circular)
                            "port_directions": {},
                            "connections": {},
                        }
                    },
                    "netnames": {},
                },
            }
        }
        modules = parse_yosys_json(json_data)
        top_module = get_top_module(modules)

        # Should fallback to first module with warning
        assert top_module.name == "module1"

    def test_get_top_module_empty_modules(self) -> None:
        """Test getting top module when no modules exist.

        Tests that ValueError is raised when trying to get
        top module from empty modules dictionary.
        """
        modules = {}

        with pytest.raises(ValueError, match="No modules found"):
            get_top_module(modules)
