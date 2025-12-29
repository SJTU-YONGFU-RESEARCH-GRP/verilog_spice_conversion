# Verilog to SPICE Conversion Tool

## Overview

This tool converts Verilog RTL designs to SPICE netlists using Yosys for synthesis. It supports hierarchical, flattened, and fully-flattened (with embedded cell models) output formats.

## Installation

### Prerequisites

1. **Python 3.10+** (required)
2. **Yosys** (required for synthesis)
   - Linux: `sudo apt-get install yosys`
   - macOS: `brew install yosys`
   - Windows: Use WSL or install via MSYS2/MinGW
   - **Note**: Yosys is required - the tool will fail if Yosys is not found

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

# Generate fully flattened netlist with embedded cell models (standalone file)
./scripts/verilog2spice.sh --fully-flattened examples/configurable_brent_kung_adder.v

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
- `--fully-flattened, --fully-flat`: Generate fully flattened netlist with embedded cell library models (standalone file, no .include needed)
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
│   └── verilog2spice.sh          # Main shell script
├── src/
│   └── verilog2spice/
│       ├── __init__.py
│       ├── parser.py              # Yosys JSON parsing
│       ├── synthesizer.py         # Yosys synthesis integration
│       ├── mapper.py              # Technology mapping (Yosys gates to cells)
│       ├── spice_generator.py     # SPICE netlist generation
│       ├── formatter.py           # Hierarchical/flattened formatting
│       └── cli.py                 # Command-line interface
├── config/
│   ├── default_synthesis.tcl      # Default Yosys synthesis script template
│   └── cell_libraries/            # Standard cell libraries
│       ├── cells.spice            # SPICE models (ngspice compatible)
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
# Basic conversion (hierarchical)
./scripts/verilog2spice.sh \
    -t configurable_brent_kung_adder \
    -o brent_kung_adder.sp \
    examples/configurable_brent_kung_adder.v

# Fully flattened with embedded cell models (standalone file)
./scripts/verilog2spice.sh \
    --fully-flattened \
    -t configurable_brent_kung_adder \
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
* Generated from Verilog RTL using Yosys
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
* Generated from Verilog RTL using Yosys
* Top Module: Adder
* Date: 2024-01-01

.include "cells.spice"

* Flattened Netlist - All instances at top level
X1 A[0] B[0] Sum[0] Cout_int1 NAND2
X2 A[1] B[1] Sum[1] Cout_int2 NAND2
...
```

### Fully Flattened Netlist (with Embedded Cell Models)

```spice
* SPICE Netlist
* Generated from Verilog RTL using Yosys
* Top Module: Adder
* Date: 2024-01-01

* Cell library models embedded below (no .include needed)

* ============================================================================
* Embedded Cell Library Models
* ============================================================================

* Standard Cell Library SPICE Models
* Generic technology library for ngspice
...

.SUBCKT INV A Y
M1 Y A VDD VDD PMOS W=2u L=0.18u
M2 Y A VSS VSS NMOS W=1u L=0.18u
.ENDS INV

.SUBCKT NAND2 A B Y
...
.ENDS NAND2

* ============================================================================
* Circuit Instances
* ============================================================================

X1 A[0] B[0] Sum[0] Cout_int1 NAND2
X2 A[1] B[1] Sum[1] Cout_int2 NAND2
...
```

**Note**: The fully flattened format is a standalone file that includes all cell library models directly, making it self-contained for simulation.

## How It Works

The tool uses the following workflow:

1. **Yosys Synthesis**: Yosys parses the Verilog RTL and synthesizes it to a gate-level netlist
2. **JSON Parsing**: The Yosys JSON output is parsed to extract module information, cells, and connections
3. **Technology Mapping**: Yosys internal gate types (e.g., `$_AND_`, `$_XOR_`) are mapped to standard cells
4. **SPICE Generation**: Gate-level netlist is converted to SPICE format with proper signal name resolution
5. **Formatting**: Output is formatted as hierarchical, flattened, or fully-flattened (with embedded models)

## Troubleshooting

### Yosys Not Found

**Yosys is required** - the tool will fail if Yosys is not installed. Install Yosys:

```bash
# Linux
sudo apt-get install yosys

# macOS
brew install yosys

# Verify installation
yosys -V
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

- **Yosys Required**: The tool requires Yosys to be installed and available in PATH
- **Gate Mapping**: Yosys internal gate types are mapped to standard cells - ensure your cell library supports all required gates
- **Signal Resolution**: Signal names are resolved from Yosys netnames - complex designs may have auto-generated signal names
- **Cell Library**: Default cell library uses generic 0.18μm CMOS models - replace with technology-specific models for production use
- **Hierarchical Flattening**: Full hierarchical flattening (expanding subcircuits) is not yet implemented - flattened mode shows top-level instances only

## Yosys Gate Type Mapping

The tool automatically maps Yosys internal gate types to standard cells:

| Yosys Gate | Standard Cell |
|------------|---------------|
| `$_AND_`   | `AND2`        |
| `$_OR_`    | `OR2`         |
| `$_XOR_`   | `XOR2`        |
| `$_NAND_`  | `NAND2`       |
| `$_NOR_`   | `NOR2`        |
| `$_NOT_`   | `INV`         |
| `$_BUF_`   | `BUF`         |
| `$_DFF_`   | `DFF`         |

Ensure your cell library (`cells.json`) contains these standard cells.

## Technical Details

### Yosys Integration

The tool uses Yosys for both parsing and synthesis:
- Verilog files are read by Yosys (no separate parser needed)
- Yosys synthesizes RTL to gate-level netlist
- Output is in JSON format containing complete design information
- All module hierarchy, ports, cells, and connections are extracted from Yosys JSON

### Cell Library

The default cell library (`config/cell_libraries/`) includes:
- **cells.json**: Metadata defining cell pins, parameters, and SPICE model names
- **cells.spice**: ngspice-compatible SPICE models with generic 0.18μm CMOS technology

For production use, replace these with your foundry's technology-specific models.

### Signal Name Resolution

Yosys uses signal IDs (integers) internally. The tool resolves these to net names by:
1. Extracting netnames from Yosys JSON
2. Building a mapping from signal ID to net name
3. Using this mapping when generating SPICE instances

## Future Enhancements

- Support for SystemVerilog
- Full hierarchical flattening (expanding subcircuits recursively)
- Integration with commercial EDA tools (Synopsys DC, Cadence Genus)
- Automatic cell library generation from foundry PDKs
- SPICE validation using ngspice
- Performance analysis and optimization
- Support for analog/mixed-signal designs

## License

See LICENSE file for details.

