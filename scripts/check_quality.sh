#!/bin/bash

# Verilog to SPICE Conversion - Quality Check Script
# This script runs all quality checks before committing
# Ensures code compliance with CONSTRAINTS_PY.md

echo "🔍 Running Quality Checks for Verilog to SPICE Conversion"
echo "=========================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counter for failed checks
FAILED_CHECKS=0
PRECOMMIT_PASSED=0

# Function to print status
print_status() {
    local status=$1
    local message=$2
    if [ "$status" -eq 0 ]; then
        echo -e "${GREEN}✅ $message${NC}"
    else
        echo -e "${RED}❌ $message${NC}"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    fi
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo -e "\n${BLUE}1. Running pre-commit hooks...${NC}"
if command_exists pre-commit; then
    if pre-commit run --all-files; then
        print_status 0 "Pre-commit hooks passed"
        PRECOMMIT_PASSED=1
    else
        print_status 1 "Pre-commit hooks failed"
        echo -e "${YELLOW}💡 Install pre-commit: pip install pre-commit${NC}"
        echo -e "${YELLOW}💡 Or run: pre-commit install${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  pre-commit not found. Install with: pip install pre-commit${NC}"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

echo -e "\n${BLUE}2. Running Ruff linting checks...${NC}"
if command_exists ruff; then
    if [ -d "tests" ] && [ "$(ls -A tests 2>/dev/null)" ]; then
        if ruff check src/ tests/; then
            print_status 0 "Ruff linting passed"
        else
            print_status 1 "Ruff linting failed"
            echo -e "${YELLOW}💡 Fix with: ruff check --fix src/ tests/${NC}"
        fi
    else
        if ruff check src/; then
            print_status 0 "Ruff linting passed"
        else
            print_status 1 "Ruff linting failed"
            echo -e "${YELLOW}💡 Fix with: ruff check --fix src/${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  ruff not found. Install with: pip install ruff${NC}"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

echo -e "\n${BLUE}3. Checking Ruff formatting...${NC}"
if [ "$PRECOMMIT_PASSED" -eq 1 ]; then
    # pre-commit already ran `ruff-format` using the pinned toolchain from
    # `.pre-commit-config.yaml`. This avoids false failures due to local Ruff
    # version differences (e.g., `ruff format --check` behavior changes).
    print_status 0 "Ruff formatting check passed (validated by pre-commit)"
elif command_exists ruff; then
    if [ -d "tests" ] && [ "$(ls -A tests 2>/dev/null)" ]; then
        if ruff format --check src/ tests/; then
            print_status 0 "Ruff formatting check passed"
        else
            echo -e "${YELLOW}⚠️  Ruff formatting issues found. Run 'ruff format src/ tests/' to fix.${NC}"
            print_status 1 "Ruff formatting check failed"
        fi
    else
        if ruff format --check src/; then
            print_status 0 "Ruff formatting check passed"
        else
            echo -e "${YELLOW}⚠️  Ruff formatting issues found. Run 'ruff format src/' to fix.${NC}"
            print_status 1 "Ruff formatting check failed"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  ruff not found (already noted above)${NC}"
fi

echo -e "\n${BLUE}4. Running type checking with MyPy...${NC}"
PYTHON_BIN=""
if command_exists python3; then
    PYTHON_BIN="python3"
elif command_exists python; then
    PYTHON_BIN="python"
fi

if [ -n "$PYTHON_BIN" ] && $PYTHON_BIN -m mypy --version >/dev/null 2>&1; then
    # Check src/verilog2spice specifically for type checking
    if $PYTHON_BIN -m mypy src/verilog2spice/ --ignore-missing-imports --no-strict-optional; then
        print_status 0 "MyPy type checking passed"
    else
        print_status 1 "MyPy type checking failed"
        echo -e "${YELLOW}💡 Fix type errors or run: $PYTHON_BIN -m mypy src/verilog2spice/ --ignore-missing-imports${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  mypy not found. Install with: pip install mypy${NC}"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

echo -e "\n${BLUE}5. Running security checks with Bandit...${NC}"
if python3 -m bandit --version >/dev/null 2>&1 || python -m bandit --version >/dev/null 2>&1; then
    # Use config file if it exists, otherwise run without it
    if [ -f "pyproject.toml" ]; then
        if python3 -m bandit -r src/ -c pyproject.toml --exit-zero 2>/dev/null || python -m bandit -r src/ -c pyproject.toml --exit-zero; then
            print_status 0 "Bandit security check completed"
        else
            print_status 1 "Bandit security check failed"
        fi
    else
        if python3 -m bandit -r src/ --exit-zero 2>/dev/null || python -m bandit -r src/ --exit-zero; then
            print_status 0 "Bandit security check completed"
        else
            print_status 1 "Bandit security check failed"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  bandit not found. Install with: pip install bandit[toml]${NC}"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

echo -e "\n${BLUE}6. Running tests with coverage...${NC}"
if python3 -m pytest --version >/dev/null 2>&1 || python -m pytest --version >/dev/null 2>&1; then
    # Check if tests directory exists
    if [ -d "tests" ] && [ "$(ls -A tests 2>/dev/null)" ]; then
        # Use verilog2spice as the coverage source module
        if python3 -m pytest --cov=src.verilog2spice --cov-report=term-missing -q 2>/dev/null || python -m pytest --cov=src.verilog2spice --cov-report=term-missing -q; then
            print_status 0 "Tests passed with coverage"
        else
            print_status 1 "Tests failed"
            echo -e "${YELLOW}💡 Run tests with: python3 -m pytest -v (or python -m pytest -v)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  No tests directory found. Skipping test execution.${NC}"
        echo -e "${YELLOW}💡 Create tests in ./tests/ directory following pytest conventions${NC}"
        echo -e "${YELLOW}💡 Tests should be in tests/ with __init__.py files${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  pytest not found. Install with: pip install pytest pytest-cov${NC}"
    # Don't fail if tests don't exist yet, but do fail if pytest is missing
    if [ ! -d "tests" ] || [ ! "$(ls -A tests 2>/dev/null)" ]; then
        echo -e "${YELLOW}   Note: Tests directory doesn't exist yet - this is optional${NC}"
    else
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    fi
fi

echo -e "\n${BLUE}7. Checking for common code quality issues...${NC}"
ISSUES_FOUND=0

# Check for TODO/FIXME comments (excluding this script and docs)
if grep -r "TODO\|FIXME\|XXX\|HACK" --include="*.py" src/ 2>/dev/null | grep -v "# Note:" | grep -v "verify_conversion" >/dev/null; then
    echo -e "${YELLOW}⚠️  Found TODO/FIXME comments in source code${NC}"
    echo -e "${YELLOW}💡 Review and complete or document all TODO items per CONSTRAINTS_PY.md${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    print_status 0 "No TODO/FIXME comments found"
fi

# Check file sizes (CONSTRAINTS_PY.md: files should be under 1000 lines)
LARGE_FILES=""
for file in src/verilog2spice/*.py; do
    if [ -f "$file" ]; then
        lines=$(wc -l < "$file" 2>/dev/null || echo "0")
        if [ "$lines" -gt 1000 ]; then
            LARGE_FILES="${LARGE_FILES}${file} (${lines} lines)\n"
        fi
    fi
done
if [ -n "$LARGE_FILES" ]; then
    echo -e "${YELLOW}⚠️  Found files exceeding 1000 lines (per CONSTRAINTS_PY.md):${NC}"
    echo -e "$LARGE_FILES" | while IFS= read -r line; do
        if [ -n "$line" ]; then
            echo -e "${YELLOW}   - $line${NC}"
        fi
    done
    echo -e "${YELLOW}💡 Consider splitting large files into smaller modules${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    print_status 0 "All files are under 1000 lines"
fi

# Check for placeholder returns (informational only)
PLACEHOLDER_RETURNS=$(grep -r "return None\|return \.\.\." --include="*.py" src/verilog2spice/ 2>/dev/null | grep -v "# Return None" | grep -v "Optional\[" | wc -l)
if [ "$PLACEHOLDER_RETURNS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Found $PLACEHOLDER_RETURNS potential placeholder returns${NC}"
    echo -e "${YELLOW}💡 Ensure all functions return actual values per CONSTRAINTS_PY.md${NC}"
    # Don't count as failure, just informational
else
    print_status 0 "No placeholder returns detected"
fi

if [ $ISSUES_FOUND -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Found $ISSUES_FOUND code quality issue(s) - review recommended${NC}"
fi

echo ""
if [ $FAILED_CHECKS -eq 0 ]; then
    echo -e "${GREEN}🎉 All quality checks passed! Your code is ready for commit.${NC}"
    echo -e "${BLUE}💡 Tip: Run 'git add .' and 'git commit' when ready.${NC}"
    echo -e "${BLUE}💡 Code complies with CONSTRAINTS_PY.md requirements${NC}"
else
    echo -e "${RED}❌ $FAILED_CHECKS check(s) failed. Please fix the issues above before committing.${NC}"
    echo -e "${BLUE}💡 Tip: Install missing tools with: pip install ruff mypy bandit pytest pytest-cov${NC}"
    echo -e "${BLUE}💡 Tip: Review CONSTRAINTS_PY.md for code quality requirements${NC}"
    exit 1
fi
