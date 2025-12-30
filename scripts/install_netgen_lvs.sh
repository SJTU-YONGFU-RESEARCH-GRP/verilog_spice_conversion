#!/bin/bash
# Script to install Netgen LVS tool for SPICE netlist comparison
# Netgen LVS is typically part of Magic VLSI layout editor

# Don't exit on error - we want to continue checking
set +e

echo "=========================================="
echo "Netgen LVS Installation Guide"
echo "=========================================="
echo ""
echo "Netgen LVS is required for LVS verification of SPICE netlists."
echo "It is typically distributed as part of Magic VLSI."
echo ""
echo "Option 1: Install netgen-lvs package (Recommended)"
echo "----------------------------------------------------------"
echo "sudo apt-get update"
echo "sudo apt-get install netgen-lvs"
echo ""
echo "Note: This is a separate package from 'netgen' (mesh generator)"
echo "      and from 'magic' (VLSI editor)."
echo ""
echo "After installation, verify with:"
echo "  netgen-lvs -help"
echo "  or"
echo "  which netgen-lvs"
echo ""
echo "Option 1b: Install Magic (may include netgen-lvs)"
echo "----------------------------------------------------------"
echo "sudo apt-get update"
echo "sudo apt-get install magic"
echo ""
echo "Note: Some Magic packages include netgen-lvs, but the Debian/Ubuntu"
echo "      package may not include it as a separate executable."
echo ""
echo "Option 2: Build Magic/Netgen from source"
echo "----------------------------------------------------------"
echo "This requires building Magic VLSI, which includes Netgen LVS."
echo "See: https://github.com/RTimothyEdwards/magic"
echo ""
echo "Dependencies needed:"
echo "  sudo apt-get install build-essential tcl-dev tk-dev \\"
echo "    libcairo2-dev libx11-dev libx11-6 libxrender1 \\"
echo "    libxrender-dev libxmu6 libxmu-dev libxt6 libxt-dev \\"
echo "    libxft2 libxft-dev libxi6 libxi-dev freeglut3 \\"
echo "    freeglut3-dev libglu1-mesa libglu1-mesa-dev"
echo ""
echo "Then clone and build Magic:"
echo "  git clone https://github.com/RTimothyEdwards/magic.git"
echo "  cd magic"
echo "  ./configure"
echo "  make"
echo "  sudo make install"
echo ""
echo "Option 3: Use alternative LVS tools"
echo "----------------------------------------------------------"
echo "If Netgen LVS is not available, consider:"
echo "  - Calibre (commercial, requires license)"
echo "  - Electric VLSI (includes LVS)"
echo "  - Custom SPICE comparison scripts"
echo ""
echo "=========================================="
echo "Checking current Netgen installation..."
echo "=========================================="

# Check what netgen is currently installed
if command -v netgen &> /dev/null; then
    echo "Found 'netgen' command"
    netgen -batch -version 2>&1 | head -5
    echo ""
    
    # Check if it's the mesh generator
    VERSION_OUTPUT=$(netgen -batch -version 2>&1 | head -20)
    if echo "$VERSION_OUTPUT" | grep -qi "vienna\|mesh"; then
        echo "⚠️  WARNING: This is Netgen mesh generator, not Netgen LVS tool!"
        echo "   Netgen mesh generator cannot perform LVS comparisons."
        echo "   You need Netgen LVS (part of Magic VLSI)."
    fi
else
    echo "No 'netgen' command found"
fi

# Check for netgen-lvs in various locations
NETGEN_LVS_FOUND=0
NETGEN_LVS_PATH=""

# Check in PATH first
if command -v netgen-lvs &> /dev/null; then
    NETGEN_LVS_FOUND=1
    NETGEN_LVS_PATH=$(command -v netgen-lvs)
    echo "✓ Found 'netgen-lvs' command in PATH: $NETGEN_LVS_PATH"
elif [ -f "/usr/local/bin/netgen-lvs" ]; then
    NETGEN_LVS_FOUND=1
    NETGEN_LVS_PATH="/usr/local/bin/netgen-lvs"
    echo "✓ Found 'netgen-lvs' at: $NETGEN_LVS_PATH"
elif [ -f "/usr/bin/netgen-lvs" ]; then
    NETGEN_LVS_FOUND=1
    NETGEN_LVS_PATH="/usr/bin/netgen-lvs"
    echo "✓ Found 'netgen-lvs' at: $NETGEN_LVS_PATH"
fi

# Check Magic installation directory
if command -v magic &> /dev/null; then
    MAGIC_PATH=$(command -v magic)
    MAGIC_DIR=$(dirname "$MAGIC_PATH")
    MAGIC_BIN_DIR="$MAGIC_DIR"
    
    # Check common Magic installation locations
    for DIR in "$MAGIC_DIR" "/usr/local/lib/magic/tcl" "/usr/local/bin" "/usr/bin"; do
        if [ -f "$DIR/netgen-lvs" ] && [ $NETGEN_LVS_FOUND -eq 0 ]; then
            NETGEN_LVS_FOUND=1
            NETGEN_LVS_PATH="$DIR/netgen-lvs"
            echo "✓ Found 'netgen-lvs' at: $NETGEN_LVS_PATH"
        fi
    done
    
    # Also check if Magic includes netgen as a script
    if [ -f "$MAGIC_DIR/netgen" ] && [ $NETGEN_LVS_FOUND -eq 0 ]; then
        # Check if this netgen is the LVS version
        NETGEN_CHECK=$(head -1 "$MAGIC_DIR/netgen" 2>/dev/null || echo "")
        if echo "$NETGEN_CHECK" | grep -qi "magic\|lvs"; then
            NETGEN_LVS_FOUND=1
            NETGEN_LVS_PATH="$MAGIC_DIR/netgen"
            echo "✓ Found Netgen LVS script at: $NETGEN_LVS_PATH"
        fi
    fi
fi

if [ $NETGEN_LVS_FOUND -eq 1 ]; then
    echo ""
    echo "Testing Netgen LVS..."
    "$NETGEN_LVS_PATH" -help 2>&1 | head -10 || echo "  (Command executed, output may vary)"
else
    echo "✗ 'netgen-lvs' command not found"
    echo "  This is the tool needed for LVS verification."
    echo ""
    echo "Note: Magic is installed, but netgen-lvs may:"
    echo "  - Be in a non-standard location"
    echo "  - Need to be invoked through Magic's interface"
    echo "  - Not be included in this Magic build"
    echo ""
    echo "You can try:"
    echo "  find /usr/local -name '*netgen*' 2>/dev/null"
    echo "  find /usr -name '*netgen*' 2>/dev/null"
fi

echo ""
echo "=========================================="
echo "Searching for Netgen in Magic installation..."
echo "=========================================="

# Search for netgen files in common locations
echo "Searching for netgen files..."
find /usr/local -name "*netgen*" 2>/dev/null | head -10
find /usr -name "*netgen*" 2>/dev/null | head -10

echo ""
echo "=========================================="
echo "Note about Magic and Netgen LVS:"
echo "=========================================="
echo "In some Magic installations, Netgen LVS is:"
echo "  1. Integrated into Magic (not a separate executable)"
echo "  2. Accessible through Magic's TCL interface"
echo "  3. Located in Magic's library directory"
echo ""
echo "The Debian/Ubuntu Magic package (8.3.105) may not include"
echo "a standalone 'netgen-lvs' executable. You may need to:"
echo "  - Build Magic from source to get netgen-lvs"
echo "  - Use Magic's built-in LVS functionality"
echo "  - Install a different Magic package that includes netgen-lvs"
echo ""
echo "To use Magic's LVS (if available through Magic):"
echo "  magic -dnull -noconsole -rcfile /dev/null <<EOF"
echo "  lvs file1.sp file2.sp"
echo "  exit"
echo "EOF"
echo ""

