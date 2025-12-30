#!/bin/bash
# Script to uninstall Netgen mesh generator and install Netgen LVS instead

echo "=========================================="
echo "Uninstalling Netgen Mesh Generator"
echo "=========================================="
echo ""
echo "This will remove the Netgen mesh generator (wrong tool)"
echo "so you can install Netgen LVS (correct tool for SPICE LVS)."
echo ""
read -p "Continue? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

echo ""
echo "Uninstalling netgen package..."
sudo apt-get remove --purge netgen

echo ""
echo "Removing any remaining configuration files..."
sudo apt-get autoremove
sudo apt-get autoclean

echo ""
echo "=========================================="
echo "Next steps:"
echo "=========================================="
echo "1. Install Netgen LVS:"
echo "   sudo apt-get update"
echo "   sudo apt-get install netgen-lvs"
echo ""
echo "2. Verify installation:"
echo "   netgen-lvs -help"
echo ""
echo "3. Test with your conversion tool:"
echo "   ./scripts/verilog2spice.sh --both --verify examples/your_file.v"
echo ""

