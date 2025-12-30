# Verilog to SPICE Conversion Tool

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](https://github.com/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-blue.svg)](https://github.com/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](https://github.com/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion/actions)
[![Coverage](https://img.shields.io/badge/coverage-76%25-yellow.svg)](https://github.com/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion)
[![Code Style](https://img.shields.io/badge/code%20style-Ruff-black.svg)](https://github.com/astral-sh/ruff)
[![Type Checking](https://img.shields.io/badge/type%20checking-mypy-blue.svg)](https://github.com/python/mypy)
[![Security](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Code Quality](https://img.shields.io/badge/code%20quality-A%2B-brightgreen.svg)](https://github.com/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion)
[![Maintained](https://img.shields.io/badge/maintained-yes-green.svg)](https://github.com/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion)
[![Issues](https://img.shields.io/github/issues/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion.svg)](https://github.com/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion/issues)
[![Pull Requests](https://img.shields.io/github/issues-pr/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion.svg)](https://github.com/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion/pulls)
[![Contributors](https://img.shields.io/github/contributors/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion.svg)](https://github.com/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion/graphs/contributors)
[![Stars](https://img.shields.io/github/stars/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion.svg?style=social)](https://github.com/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion/stargazers)

A comprehensive tool for converting Verilog RTL designs to SPICE netlists, supporting hierarchical and flattened representations at both logic and transistor levels.

## Features

- 🔄 **Dual Output Formats**: Generate hierarchical or flattened SPICE netlists (or both)
- ⚡ **Multi-Level Flattening**: Support for logic-level (gate-level) and transistor-level (PMOS/NMOS) flattening
- 🔧 **Yosys Integration**: Automatic synthesis using Yosys for gate-level netlist generation
- 📚 **Cell Library Support**: Flexible cell library system with metadata support
- ✅ **LVS Verification**: Built-in Layout vs. Schematic (LVS) verification using Netgen
- 🎯 **Technology Support**: Configurable technology libraries (e.g., TSMC 65nm, Sky130)
- 📝 **Rich Output**: Colorized console output with progress indicators
- 🔍 **Comprehensive Logging**: Verbose logging and error reporting

## Requirements

### System Requirements

- **Python**: 3.10 or higher
- **Yosys**: For Verilog synthesis (recommended)
  - Ubuntu/Debian: `sudo apt-get install yosys`
  - macOS: `brew install yosys`
  - Windows: Use WSL or install via MSYS2/MinGW
- **Netgen LVS**: For LVS verification (optional)
  - See [INSTALL_NETGEN_LVS.md](docs/INSTALL_NETGEN_LVS.md) for installation instructions

### Python Dependencies

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Key dependencies:
- `rich` - Enhanced terminal output
- `pyyaml` - Configuration file support
- `numpy`, `matplotlib`, `seaborn` - Data visualization (optional)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/verilog_spice_conversion.git
cd verilog_spice_conversion
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Install Yosys (if not already installed):
```bash
# Ubuntu/Debian
sudo apt-get install yosys

# macOS
brew install yosys
```

4. (Optional) Install Netgen LVS for verification:
```bash
./scripts/install_netgen_lvs.sh
```

## Quick Start

### Basic Usage

Convert a Verilog file to SPICE:

```bash
./scripts/verilog2spice.sh adder.v
```

### Specify Top Module

```bash
./scripts/verilog2spice.sh -t Adder -o adder.sp adder.v
```

### Generate Flattened Netlist

```bash
# Logic-level flattened (gate-level with embedded cell models)
./scripts/verilog2spice.sh --flattened design.v

# Transistor-level flattened (PMOS/NMOS level)
./scripts/verilog2spice.sh --flattened --flatten-level transistor design.v
```

### Generate Both Formats

```bash
./scripts/verilog2spice.sh --both design.v
```

### With Verification

```bash
# Generate and verify netlist
./scripts/verilog2spice.sh --flattened --verify design.v

# Compare against reference netlist
./scripts/verilog2spice.sh --flattened --verify-reference reference.sp design.v

# Compare logic vs transistor levels
./scripts/verilog2spice.sh --both --flatten-level transistor --verify-flatten-levels design.v
```

## Usage

### Command-Line Interface

The main entry point is the `verilog2spice.sh` script:

```bash
./scripts/verilog2spice.sh [OPTIONS] <verilog_file> [verilog_file ...]
```

### Input Options

| Option | Description |
|--------|-------------|
| `-t, --top <module>` | Specify top-level module name |
| `-I, --include <path>` | Add include/search path (can be repeated) |
| `-D, --define <name>=<value>` | Define preprocessor macro (can be repeated) |

### Output Options

| Option | Description |
|--------|-------------|
| `-o, --output <file>` | Output SPICE netlist file (default: `<top_module>.sp`) |
| `-O, --output-dir <dir>` | Output directory (default: `./output`) |
| `--hierarchical, --hier` | Generate hierarchical netlist (default) |
| `--flattened, --flat` | Generate flattened netlist |
| `--both` | Generate both hierarchical and flattened netlists |
| `--flatten-level <level>` | Flattening level: `logic` (gate-level, default) or `transistor` (PMOS/NMOS level) |

### Synthesis Options

| Option | Description |
|--------|-------------|
| `--synthesis-script <file>` | Custom Yosys synthesis script |
| `--constraint <file>` | Timing/area constraints file |
| `--optimize` | Enable optimization (default) |
| `--no-optimize` | Disable optimization |

### Technology Options

| Option | Description |
|--------|-------------|
| `--cell-library <file>` | Path to cell library SPICE file |
| `--cell-metadata <file>` | Path to cell metadata JSON file |
| `--tech <name>` | Technology name (e.g., "tsmc65nm", "sky130") |

### Verification Options

| Option | Description |
|--------|-------------|
| `--verify` | Run LVS verification using Netgen |
| `--verify-reference <file>` | Reference netlist file for verification (SPICE format) |
| `--verify-flatten-levels` | Compare logic-level and transistor-level netlists |

### Logging Options

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Verbose output |
| `-q, --quiet` | Quiet mode (errors only) |
| `--log <file>` | Log file path |
| `--keep-temp` | Keep temporary files |

### Other Options

| Option | Description |
|--------|-------------|
| `--config <file>` | Configuration file path |
| `--dry-run` | Show what would be done without executing |
| `-h, --help` | Show help message |
| `--version` | Show version information |

## Examples

### Example 1: Simple Conversion

```bash
./scripts/verilog2spice.sh examples/configurable_brent_kung_adder.v
```

This generates a hierarchical SPICE netlist in `output/configurable_brent_kung_adder.sp`.

### Example 2: Flattened Logic-Level Netlist

```bash
./scripts/verilog2spice.sh --flattened examples/configurable_brent_kung_adder.v
```

Generates a flattened gate-level netlist with embedded cell models.

### Example 3: Transistor-Level Flattening

```bash
./scripts/verilog2spice.sh --flattened --flatten-level transistor \
    --cell-library config/cell_libraries/cells.spice \
    --cell-metadata config/cell_libraries/cells.json \
    examples/configurable_brent_kung_adder.v
```

Generates a fully flattened transistor-level netlist (PMOS/NMOS).

### Example 4: Both Formats with Verification

```bash
./scripts/verilog2spice.sh --both --verify examples/configurable_brent_kung_adder.v
```

Generates both hierarchical and flattened netlists and verifies they match.

### Example 5: Multiple Files with Include Paths

```bash
./scripts/verilog2spice.sh \
    -I ./libs \
    -I ./rtl \
    -t Top \
    top.v module1.v module2.v
```

### Example 6: Custom Synthesis Script

```bash
./scripts/verilog2spice.sh \
    -v \
    --synthesis-script config/default_synthesis.tcl \
    design.v
```

## Project Structure

```
verilog_spice_conversion/
├── config/                 # Configuration files
│   ├── cell_libraries/    # Cell library definitions
│   └── default_synthesis.tcl
├── docs/                  # Documentation
│   └── INSTALL_NETGEN_LVS.md
├── examples/              # Example Verilog designs
├── output/               # Generated SPICE netlists
├── scripts/              # Utility scripts
│   └── verilog2spice.sh  # Main conversion script
├── src/                  # Source code
│   └── verilog2spice/    # Python package
│       ├── cli.py        # Command-line interface
│       ├── synthesizer.py # Yosys integration
│       ├── parser.py     # Netlist parsing
│       ├── mapper.py     # Cell library mapping
│       ├── spice_generator.py # SPICE generation
│       ├── formatter.py  # SPICE formatting
│       └── lvs.py        # LVS verification
├── requirements.txt      # Python dependencies
└── LICENSE               # License file
```

## Cell Library Configuration

Cell libraries are defined using JSON metadata files and SPICE model files. See `config/cell_libraries/cells.json` for an example.

### Cell Metadata Format

```json
{
  "technology": "generic",
  "spice_file": "cells.spice",
  "cells": {
    "INV": {
      "spice_model": "INV",
      "pins": ["A", "Y"],
      "parameters": ["W", "L"],
      "description": "Inverter"
    }
  }
}
```

## LVS Verification

The tool supports Layout vs. Schematic (LVS) verification using Netgen:

1. **Hierarchical vs. Flattened**: Compare hierarchical and flattened netlists
2. **Logic vs. Transistor**: Compare logic-level and transistor-level flattened netlists
3. **Reference Comparison**: Compare against an external reference netlist

Example:
```bash
./scripts/verilog2spice.sh --both --verify design.v
```

LVS reports are saved in the output directory with `.rpt` extension.

## Python API

You can also use the tool programmatically:

```python
from src.verilog2spice.cli import main
import sys

# Equivalent to: ./scripts/verilog2spice.sh design.v
sys.argv = ['verilog2spice', 'design.v', '--flattened']
main()
```

Or use individual modules:

```python
from src.verilog2spice.synthesizer import synthesize
from src.verilog2spice.spice_generator import generate_netlist

# Synthesize and generate netlist
netlist = synthesize(['design.v'], 'Top', ...)
spice = generate_netlist(netlist, cell_library, ...)
```

## Troubleshooting

### Yosys Not Found

If you see a warning about Yosys not being found:
```bash
# Ubuntu/Debian
sudo apt-get install yosys

# macOS
brew install yosys
```

### Netgen LVS Not Found

If LVS verification fails, install Netgen LVS:
```bash
./scripts/install_netgen_lvs.sh
```

See [INSTALL_NETGEN_LVS.md](docs/INSTALL_NETGEN_LVS.md) for detailed instructions.

### Python Version Issues

Ensure Python 3.10+ is installed:
```bash
python3 --version  # Should show 3.10 or higher
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the Creative Commons Attribution 4.0 International License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Yosys](https://github.com/YosysHQ/yosys) - Verilog synthesis framework
- [Netgen](http://opencircuitdesign.com/netgen/) - LVS verification tool
- [Rich](https://github.com/Textualize/rich) - Beautiful terminal output

## Citation

If you use this tool in your research, please cite:

```bibtex
@software{verilog2spice2024,
  title = {Verilog to SPICE Conversion Tool},
  author = {Your Name},
  year = {2024},
  url = {https://github.com/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion},
  version = {1.0.0}
}
```

## Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**Made with ❤️ for the VLSI design community**
