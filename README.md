# Verilog to SPICE Conversion Tool

## Overview

This tool converts Verilog RTL designs to SPICE netlists, supporting both hierarchical and flattened output formats.

## Installation

### Prerequisites

1. **Python 3.10+** (required)
2. **Yosys** (optional but recommended for synthesis)
   - Linux: `sudo apt-get install yosys`
   - macOS: `brew install yosys`
   - Windows: Use WSL or install via MSYS2/MinGW

### Python Dependencies

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
# Convert a Verilog file to SPICE
./scripts/verilog2spice.sh examples/configurable_brent_kung_adder.v

# Specify top module and output file
./scripts/verilog2spice.sh -t configurable_brent_kung_adder -o adder.sp examples/configurable_brent_kung_adder.v
```

### Advanced Usage

```bash
# Generate flattened netlist
./scripts/verilog2spice.sh --flattened examples/configurable_brent_kung_adder.v

# Generate both hierarchical and flattened
./scripts/verilog2spice.sh --both -o design examples/configurable_brent_kung_adder.v

# Use custom cell library
./scripts/verilog2spice.sh --cell-library custom_cells.spice --cell-metadata cells.json examples/configurable_brent_kung_adder.v

# Multiple files with includes
./scripts/verilog2spice.sh -I ./libs -I ./rtl -t Top top.v module1.v module2.v

# Verbose output
./scripts/verilog2spice.sh -v examples/configurable_brent_kung_adder.v
```

### Command-Line Options

#### Input Options
- `-t, --top <module>`: Specify top-level module name
- `-I, --include <path>`: Add include/search path (can be repeated)
- `-D, --define <name>=<value>`: Define preprocessor macro (can be repeated)

#### Output Options
- `-o, --output <file>`: Output SPICE netlist file (default: <top_module>.sp)
- `-O, --output-dir <dir>`: Output directory (default: ./output)
- `--hierarchical, --hier`: Generate hierarchical netlist (default)
- `--flattened, --flat`: Generate flattened netlist
- `--both`: Generate both hierarchical and flattened netlists

#### Synthesis Options
- `--synthesis-script <file>`: Custom Yosys synthesis script
- `--constraint <file>`: Timing/area constraints file
- `--optimize`: Enable optimization (default)
- `--no-optimize`: Disable optimization

#### Technology Options
- `--cell-library <file>`: Path to cell library SPICE file
- `--cell-metadata <file>`: Path to cell metadata JSON file
- `--tech <name>`: Technology name (e.g., "tsmc65nm", "sky130")

#### Logging Options
- `-v, --verbose`: Verbose output
- `-q, --quiet`: Quiet mode (errors only)
- `--log <file>`: Log file path
- `--keep-temp`: Keep temporary files

#### Other Options
- `--config <file>`: Configuration file path
- `--dry-run`: Show what would be done without executing
- `-h, --help`: Show help message
- `--version`: Show version information

## Project Structure

```
verilog_spice_conversion/
├── scripts/
│   ├── verilog2spice.sh          # Main shell script
│   └── PLAN.md                    # Implementation plan
├── src/
│   └── verilog2spice/
│       ├── __init__.py
│       ├── parser.py              # Verilog parsing
│       ├── synthesizer.py         # Synthesis logic
│       ├── mapper.py              # Technology mapping
│       ├── spice_generator.py     # SPICE netlist generation
│       ├── formatter.py           # Hierarchical/flattened formatting
│       └── cli.py                 # Command-line interface
├── config/
│   ├── default_synthesis.tcl      # Default Yosys synthesis script
│   └── cell_libraries/            # Standard cell libraries
│       ├── cells.spice            # SPICE models
│       └── cells.json             # Cell metadata
├── examples/                      # Example Verilog files
└── output/                        # Generated netlists
```

## Examples

The `examples/` directory contains sample Verilog files for testing:

- `configurable_brent_kung_adder.v`
- `configurable_carry_lookahead_adder.v`
- `configurable_carry_select_adder.v`
- `configurable_carry_skip_adder.v`
- `configurable_conditional_sum_adder.v`
- `configurable_kogge_stone_adder.v`

### Example: Convert Brent-Kung Adder

```bash
./scripts/verilog2spice.sh \
    -t configurable_brent_kung_adder \
    -o brent_kung_adder.sp \
    examples/configurable_brent_kung_adder.v
```

## Cell Library Format

### JSON Metadata Format

The cell library metadata (`cells.json`) defines cell information:

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

### SPICE Model Format

Cell SPICE models are defined in `.spice` files:

```spice
.SUBCKT INV A Y
* Transistor-level model
M1 Y A VDD VDD PMOS W=1u L=0.18u
M2 Y A VSS VSS NMOS W=0.5u L=0.18u
.ENDS INV
```

## Output Format

### Hierarchical Netlist

```spice
* SPICE Netlist
* Generated from Verilog RTL
* Top Module: Adder
* Date: 2024-01-01

.include "cells.spice"

.SUBCKT Adder A[3:0] B[3:0] Sum[3:0] Cout
  X1 A[0] B[0] Sum[0] Cout_int1 FullAdder
  ...
.ENDS Adder

.SUBCKT FullAdder A B Cin Sum Cout
  X1 A B S1 NAND2
  ...
.ENDS FullAdder
```

### Flattened Netlist

```spice
* SPICE Netlist
* Generated from Verilog RTL
* Top Module: Adder
* Date: 2024-01-01

.include "cells.spice"

* All instances at top level
X1 A[0] B[0] Sum[0] Cout_int1 NAND2
X2 A[1] B[1] Sum[1] Cout_int2 NAND2
...
```

## Troubleshooting

### Yosys Not Found

If Yosys is not installed, the tool will use a simplified synthesis path. Install Yosys for better results:

```bash
# Linux
sudo apt-get install yosys

# macOS
brew install yosys
```

### Python Import Errors

Ensure you're running from the project root and dependencies are installed:

```bash
pip install -r requirements.txt
```

### Module Not Found

If the top module cannot be found, explicitly specify it:

```bash
./scripts/verilog2spice.sh -t ModuleName design.v
```

## Limitations

- Current implementation provides a foundation for Verilog to SPICE conversion
- Full synthesis requires Yosys or similar tool
- Cell library models are placeholders - replace with actual SPICE models
- Complex hierarchical designs may need additional processing

## Future Enhancements

- Support for SystemVerilog
- Integration with commercial EDA tools
- Automatic cell library generation
- SPICE validation using ngspice
- Performance analysis and optimization

## License

See LICENSE file for details.

