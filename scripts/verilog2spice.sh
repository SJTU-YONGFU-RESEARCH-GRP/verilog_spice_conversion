#!/bin/bash

# Verilog to SPICE Conversion Script
# This script orchestrates the conversion of Verilog RTL to SPICE netlists
# Usage: ./verilog2spice.sh [OPTIONS] <verilog_file> [verilog_file ...]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default values
TOP_MODULE=""
OUTPUT_FILE=""
OUTPUT_DIR="${PROJECT_ROOT}/output"
INCLUDE_PATHS=()
DEFINES=()
SYNTHESIS_SCRIPT=""
CONSTRAINT_FILE=""
OPTIMIZE=true
CELL_LIBRARY=""
CELL_METADATA=""
TECH=""
FLATTENED=false
HIERARCHICAL=true
BOTH=false
FLATTEN_LEVEL="logic"
VERBOSE=false
QUIET=false
LOG_FILE=""
KEEP_TEMP=false
CONFIG_FILE=""
DRY_RUN=false
VERIFY=false
VERIFY_REFERENCE=""
VERIFY_FLATTEN_LEVELS=false

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    if [[ "$QUIET" == false ]]; then
        echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] ${message}${NC}"
    fi
}

# Function to print error
print_error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS] <verilog_file> [verilog_file ...]

Convert Verilog RTL designs to SPICE netlists.

Input Options:
  -t, --top <module>              Specify top-level module name
  -I, --include <path>            Add include/search path (can be repeated)
  -D, --define <name>=<value>     Define preprocessor macro (can be repeated)

Output Options:
  -o, --output <file>             Output SPICE netlist file (default: <top_module>.sp)
  -O, --output-dir <dir>         Output directory (default: ./output)
  --hierarchical, --hier         Generate hierarchical netlist (default)
  --flattened, --flat            Generate flattened netlist
  --both                         Generate both hierarchical and flattened netlists
  --flatten-level <level>        Flattening level for --flattened: 'logic' (gate-level, default) or 'transistor' (PMOS/NMOS level)

Synthesis Options:
  --synthesis-script <file>       Custom Yosys synthesis script
  --constraint <file>             Timing/area constraints file
  --optimize                      Enable optimization (default)
  --no-optimize                   Disable optimization

Technology Options:
  --cell-library <file>          Path to cell library SPICE file
  --cell-metadata <file>         Path to cell metadata JSON file
  --tech <name>                  Technology name (e.g., "tsmc65nm", "sky130")

Logging Options:
  -v, --verbose                  Verbose output
  -q, --quiet                    Quiet mode (errors only)
  --log <file>                   Log file path
  --keep-temp                    Keep temporary files

Verification Options:
  --verify                       Run LVS verification using Netgen
  --verify-reference <file>      Reference netlist file for verification (SPICE format)
  --verify-flatten-levels        Compare logic-level and transistor-level netlists

Other Options:
  --config <file>                Configuration file path
  --dry-run                      Show what would be done without executing
  -h, --help                     Show this help message
  --version                      Show version information

Examples:
  $0 adder.v
  $0 -t Adder -o adder.sp adder.v
  $0 --flattened design.v  # Logic-level flattened with embedded cell models
  $0 --flattened --flatten-level transistor design.v  # Transistor-level (PMOS/NMOS) flattening
  $0 --flattened --verify design.v  # Generate and verify netlist
  $0 --flattened --verify-reference reference.sp design.v  # Compare against reference
  $0 --both --flatten-level transistor --verify-flatten-levels design.v  # Compare logic vs transistor
  $0 -I ./libs -I ./rtl -t Top top.v module1.v module2.v
  $0 --both -o design design.v
  $0 -v --synthesis-script custom_synth.tcl design.v

EOF
}

# Function to check if Python is available
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed or not in PATH"
        exit 1
    fi

    local python_version
    python_version=$(python3 --version 2>&1 | awk '{print $2}')
    local major_version
    major_version=$(echo "$python_version" | cut -d. -f1)
    local minor_version
    minor_version=$(echo "$python_version" | cut -d. -f2)

    if [[ $major_version -lt 3 ]] || [[ $major_version -eq 3 && $minor_version -lt 10 ]]; then
        print_error "Python 3.10 or higher is required. Found: $python_version"
        exit 1
    fi
}

# Function to check if required tools are available
check_tools() {
    local missing_tools=()

    # Check for Yosys (optional but recommended)
    if ! command -v yosys &> /dev/null; then
        print_status $YELLOW "Warning: yosys not found. Synthesis may not work properly."
        print_status $YELLOW "Install with: apt-get install yosys (Linux) or brew install yosys (macOS)"
    fi

    # Check for Python packages (basic check - let Python handle import errors)
    # No specific package checks needed as Python will report import errors

    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        exit 1
    fi
}

# Function to validate input files
validate_input_files() {
    local files=("$@")

    if [[ ${#files[@]} -eq 0 ]]; then
        print_error "No Verilog files specified"
        show_usage
        exit 1
    fi

    for file in "${files[@]}"; do
        if [[ ! -f "$file" ]]; then
            print_error "File not found: $file"
            exit 1
        fi

        if [[ ! -r "$file" ]]; then
            print_error "File is not readable: $file"
            exit 1
        fi
    done
}

# Function to setup output directory
setup_output_dir() {
    if [[ ! -d "$OUTPUT_DIR" ]]; then
        mkdir -p "$OUTPUT_DIR"
        print_status $BLUE "Created output directory: $OUTPUT_DIR"
    fi
}

# Function to build Python command
build_python_cmd() {
    local cmd="python3 -m src.verilog2spice.cli"

    # Add input files
    for file in "$@"; do
        cmd="$cmd \"$file\""
    done

    # Add options
    if [[ -n "$TOP_MODULE" ]]; then
        cmd="$cmd --top \"$TOP_MODULE\""
    fi

    if [[ -n "$OUTPUT_FILE" ]]; then
        cmd="$cmd --output \"$OUTPUT_FILE\""
    fi

    if [[ -n "$OUTPUT_DIR" ]]; then
        cmd="$cmd --output-dir \"$OUTPUT_DIR\""
    fi

    for include_path in "${INCLUDE_PATHS[@]}"; do
        cmd="$cmd --include \"$include_path\""
    done

    for define in "${DEFINES[@]}"; do
        cmd="$cmd --define \"$define\""
    done

    if [[ -n "$SYNTHESIS_SCRIPT" ]]; then
        cmd="$cmd --synthesis-script \"$SYNTHESIS_SCRIPT\""
    fi

    if [[ -n "$CONSTRAINT_FILE" ]]; then
        cmd="$cmd --constraint \"$CONSTRAINT_FILE\""
    fi

    if [[ "$OPTIMIZE" == false ]]; then
        cmd="$cmd --no-optimize"
    fi

    if [[ -n "$CELL_LIBRARY" ]]; then
        cmd="$cmd --cell-library \"$CELL_LIBRARY\""
    fi

    if [[ -n "$CELL_METADATA" ]]; then
        cmd="$cmd --cell-metadata \"$CELL_METADATA\""
    fi

    if [[ -n "$TECH" ]]; then
        cmd="$cmd --tech \"$TECH\""
    fi

    if [[ "$FLATTENED" == true ]]; then
        cmd="$cmd --flattened"
    fi

    if [[ "$HIERARCHICAL" == true && "$BOTH" == false ]]; then
        cmd="$cmd --hierarchical"
    fi

    if [[ "$BOTH" == true ]]; then
        cmd="$cmd --both"
    fi

    if [[ -n "$FLATTEN_LEVEL" ]]; then
        cmd="$cmd --flatten-level \"$FLATTEN_LEVEL\""
    fi

    if [[ "$VERBOSE" == true ]]; then
        cmd="$cmd --verbose"
    fi

    if [[ "$QUIET" == true ]]; then
        cmd="$cmd --quiet"
    fi

    if [[ -n "$LOG_FILE" ]]; then
        cmd="$cmd --log \"$LOG_FILE\""
    fi

    if [[ "$KEEP_TEMP" == true ]]; then
        cmd="$cmd --keep-temp"
    fi

    if [[ -n "$CONFIG_FILE" ]]; then
        cmd="$cmd --config \"$CONFIG_FILE\""
    fi

    if [[ "$VERIFY" == true ]]; then
        cmd="$cmd --verify"
    fi

    if [[ -n "$VERIFY_REFERENCE" ]]; then
        cmd="$cmd --verify-reference \"$VERIFY_REFERENCE\""
    fi

    if [[ "$VERIFY_FLATTEN_LEVELS" == true ]]; then
        cmd="$cmd --verify-flatten-levels"
    fi

    echo "$cmd"
}

# Function to parse command line arguments
parse_args() {
    local verilog_files=()

    while [[ $# -gt 0 ]]; do
        case $1 in
            -t|--top)
                if [[ -z "${2:-}" ]] || [[ "${2:-}" =~ ^- ]]; then
                    print_error "--top requires a module name"
                    show_usage
                    exit 1
                fi
                TOP_MODULE=$2
                shift 2
                ;;
            -o|--output)
                if [[ -z "${2:-}" ]] || [[ "${2:-}" =~ ^- ]]; then
                    print_error "--output requires a file path"
                    show_usage
                    exit 1
                fi
                OUTPUT_FILE=$2
                shift 2
                ;;
            -O|--output-dir)
                if [[ -z "${2:-}" ]] || [[ "${2:-}" =~ ^- ]]; then
                    print_error "--output-dir requires a directory path"
                    show_usage
                    exit 1
                fi
                OUTPUT_DIR=$2
                shift 2
                ;;
            -I|--include)
                if [[ -z "${2:-}" ]] || [[ "${2:-}" =~ ^- ]]; then
                    print_error "--include requires a path"
                    show_usage
                    exit 1
                fi
                INCLUDE_PATHS+=("$2")
                shift 2
                ;;
            -D|--define)
                if [[ -z "${2:-}" ]] || [[ "${2:-}" =~ ^- ]]; then
                    print_error "--define requires name=value"
                    show_usage
                    exit 1
                fi
                DEFINES+=("$2")
                shift 2
                ;;
            --synthesis-script)
                if [[ -z "${2:-}" ]] || [[ "${2:-}" =~ ^- ]]; then
                    print_error "--synthesis-script requires a file path"
                    show_usage
                    exit 1
                fi
                SYNTHESIS_SCRIPT=$2
                shift 2
                ;;
            --constraint)
                if [[ -z "${2:-}" ]] || [[ "${2:-}" =~ ^- ]]; then
                    print_error "--constraint requires a file path"
                    show_usage
                    exit 1
                fi
                CONSTRAINT_FILE=$2
                shift 2
                ;;
            --optimize)
                OPTIMIZE=true
                shift
                ;;
            --no-optimize)
                OPTIMIZE=false
                shift
                ;;
            --cell-library)
                if [[ -z "${2:-}" ]] || [[ "${2:-}" =~ ^- ]]; then
                    print_error "--cell-library requires a file path"
                    show_usage
                    exit 1
                fi
                CELL_LIBRARY=$2
                shift 2
                ;;
            --cell-metadata)
                if [[ -z "${2:-}" ]] || [[ "${2:-}" =~ ^- ]]; then
                    print_error "--cell-metadata requires a file path"
                    show_usage
                    exit 1
                fi
                CELL_METADATA=$2
                shift 2
                ;;
            --tech)
                if [[ -z "${2:-}" ]] || [[ "${2:-}" =~ ^- ]]; then
                    print_error "--tech requires a technology name"
                    show_usage
                    exit 1
                fi
                TECH=$2
                shift 2
                ;;
            --hierarchical|--hier)
                HIERARCHICAL=true
                FLATTENED=false
                BOTH=false
                shift
                ;;
            --flattened|--flat)
                FLATTENED=true
                HIERARCHICAL=false
                BOTH=false
                shift
                ;;
            --both)
                BOTH=true
                HIERARCHICAL=false
                FLATTENED=false
                shift
                ;;
            --flatten-level)
                if [[ -z "${2:-}" ]] || [[ "${2:-}" =~ ^- ]]; then
                    print_error "--flatten-level requires a level (logic or transistor)"
                    show_usage
                    exit 1
                fi
                if [[ "$2" != "logic" && "$2" != "transistor" ]]; then
                    print_error "--flatten-level must be 'logic' or 'transistor'"
                    show_usage
                    exit 1
                fi
                FLATTEN_LEVEL=$2
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                QUIET=false
                shift
                ;;
            -q|--quiet)
                QUIET=true
                VERBOSE=false
                shift
                ;;
            --log)
                if [[ -z "${2:-}" ]] || [[ "${2:-}" =~ ^- ]]; then
                    print_error "--log requires a file path"
                    show_usage
                    exit 1
                fi
                LOG_FILE=$2
                shift 2
                ;;
            --keep-temp)
                KEEP_TEMP=true
                shift
                ;;
            --config)
                if [[ -z "${2:-}" ]] || [[ "${2:-}" =~ ^- ]]; then
                    print_error "--config requires a file path"
                    show_usage
                    exit 1
                fi
                CONFIG_FILE=$2
                shift 2
                ;;
            --verify)
                VERIFY=true
                shift
                ;;
            --verify-reference)
                if [[ -z "${2:-}" ]] || [[ "${2:-}" =~ ^- ]]; then
                    print_error "--verify-reference requires a file path"
                    show_usage
                    exit 1
                fi
                VERIFY_REFERENCE=$2
                VERIFY=true
                shift 2
                ;;
            --verify-flatten-levels)
                VERIFY_FLATTEN_LEVELS=true
                VERIFY=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            --version)
                echo "verilog2spice.sh version 1.0.0"
                exit 0
                ;;
            -*)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
            *)
                verilog_files+=("$1")
                shift
                ;;
        esac
    done

    # Return verilog files as array (using global variable)
    VERILOG_FILES=("${verilog_files[@]}")
}

# Main function
main() {
    print_status $BLUE "Starting Verilog to SPICE conversion..."

    # Parse arguments
    parse_args "$@"

    # Validate environment
    check_python
    check_tools

    # Validate input files
    if [[ ${#VERILOG_FILES[@]} -eq 0 ]]; then
        print_error "No Verilog files specified"
        show_usage
        exit 1
    fi

    validate_input_files "${VERILOG_FILES[@]}"

    # Setup output directory
    setup_output_dir

    # Change to project root for Python imports
    cd "$PROJECT_ROOT"

    # Build Python command
    local python_cmd
    python_cmd=$(build_python_cmd "${VERILOG_FILES[@]}")

    if [[ "$DRY_RUN" == true ]]; then
        print_status $YELLOW "Dry run mode - would execute:"
        echo "$python_cmd"
        exit 0
    fi

    # Execute Python tool
    print_status $BLUE "Executing Python conversion tool..."
    if eval "$python_cmd"; then
        print_status $GREEN "Verilog to SPICE conversion completed successfully!"
    else
        print_error "Conversion failed"
        exit 1
    fi
}

# Run main function with all arguments
main "$@"
