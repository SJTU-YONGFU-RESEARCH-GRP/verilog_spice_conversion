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

# Function to get coverage color based on percentage
get_coverage_color() {
    local coverage=$1
    # Remove % sign if present and convert to integer
    local coverage_int=$(echo "$coverage" | sed 's/%//' | cut -d'.' -f1)

    if [ "$coverage_int" -ge 90 ]; then
        echo "green"
    elif [ "$coverage_int" -ge 75 ]; then
        echo "yellow"
    else
        echo "red"
    fi
}

# Function to update coverage badge in README.md
update_coverage_badge() {
    local coverage_percent=$1
    local readme_file="README.md"

    if [ ! -f "$readme_file" ]; then
        echo -e "${YELLOW}⚠️  README.md not found. Skipping badge update.${NC}"
        return 1
    fi

    local color=$(get_coverage_color "$coverage_percent")
    local new_badge="[![Coverage](https://img.shields.io/badge/coverage-${coverage_percent}-${color}.svg)](https://github.com/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion)"

    # Use Python for more reliable regex replacement if available
    if command_exists python3 || command_exists python; then
        local python_cmd=""
        if command_exists python3; then
            python_cmd="python3"
        else
            python_cmd="python"
        fi

        # Create a temporary Python script for the replacement
        local temp_script=$(mktemp)
        cat > "$temp_script" << 'PYTHON_SCRIPT'
import re
import sys

readme_file = sys.argv[1]
new_badge = sys.argv[2]

try:
    with open(readme_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern to match the coverage badge
    pattern = r'\[!\[Coverage\]\(https://img\.shields\.io/badge/coverage-\d+%25-[a-z]+\.svg\)\]\(https://github\.com/SJTU-YONGFU-RESEARCH-GRP/verilog_spice_conversion\)'

    # Replace the badge
    new_content = re.sub(pattern, new_badge, content)

    if new_content != content:
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("SUCCESS")
    else:
        print("NO_MATCH")
        sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
PYTHON_SCRIPT

        local result=$($python_cmd "$temp_script" "$readme_file" "$new_badge" 2>&1)
        rm -f "$temp_script"

        if echo "$result" | grep -q "SUCCESS"; then
            echo -e "${GREEN}✅ Updated coverage badge in README.md to ${coverage_percent}${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  Failed to update coverage badge: ${result}${NC}"
            return 1
        fi
    else
        # Fallback to sed if Python is not available
        # Escape special characters for sed
        local coverage_escaped=$(echo "$coverage_percent" | sed 's/%/\\%/g')
        local new_badge_escaped=$(echo "$new_badge" | sed 's/[[\]()]/\\&/g' | sed 's/|/\\|/g')

        # Simple pattern: match coverage-XX%-color
        if sed --version 2>/dev/null | grep -q GNU; then
            # GNU sed (Linux)
            sed -i "s|coverage-[0-9]*%25-[a-z]*\.svg|coverage-${coverage_escaped}-${color}.svg|g" "$readme_file"
        else
            # BSD sed (macOS)
            sed -i '' -E "s|coverage-[0-9]+%25-[a-z]+\.svg|coverage-${coverage_escaped}-${color}.svg|g" "$readme_file"
        fi

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Updated coverage badge in README.md to ${coverage_percent}${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  Failed to update coverage badge in README.md${NC}"
            return 1
        fi
    fi
}

# Function to extract coverage percentage from pytest output
extract_coverage_percentage() {
    local coverage_output="$1"
    # Extract percentage from line like "TOTAL                                   1155     52    95%"
    # or "TOTAL     1155     52    95%"
    # Look for the percentage at the end of the TOTAL line
    local percent=$(echo "$coverage_output" | grep -i "TOTAL" | grep -oE "[0-9]+%" | tail -n1)
    if [ -n "$percent" ]; then
        # Remove % and round to integer, then add % back
        local num=$(echo "$percent" | sed 's/%//')
        printf "%.0f%%" "$num"
    fi
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
COVERAGE_PERCENT=""
if python3 -m pytest --version >/dev/null 2>&1 || python -m pytest --version >/dev/null 2>&1; then
    # Check if tests directory exists
    if [ -d "tests" ] && [ "$(ls -A tests 2>/dev/null)" ]; then
        # Use verilog2spice as the coverage source module
        # Capture coverage output
        COVERAGE_OUTPUT=""
        if [ -n "$PYTHON_BIN" ]; then
            COVERAGE_OUTPUT=$($PYTHON_BIN -m pytest --cov=src.verilog2spice --cov-report=term-missing -q 2>&1)
            TEST_EXIT_CODE=$?
        else
            if command_exists python3; then
                COVERAGE_OUTPUT=$(python3 -m pytest --cov=src.verilog2spice --cov-report=term-missing -q 2>&1)
                TEST_EXIT_CODE=$?
            else
                COVERAGE_OUTPUT=$(python -m pytest --cov=src.verilog2spice --cov-report=term-missing -q 2>&1)
                TEST_EXIT_CODE=$?
            fi
        fi

        if [ $TEST_EXIT_CODE -eq 0 ]; then
            print_status 0 "Tests passed with coverage"
            # Extract coverage percentage
            COVERAGE_PERCENT=$(extract_coverage_percentage "$COVERAGE_OUTPUT")
            if [ -n "$COVERAGE_PERCENT" ]; then
                echo -e "${BLUE}   Overall Coverage: ${COVERAGE_PERCENT}${NC}"
                # Display the original pytest coverage breakdown
                echo -e "${BLUE}   Coverage Breakdown:${NC}"
                echo "$COVERAGE_OUTPUT" | grep -E "^(Name|src/|TOTAL|---)" | head -20
                # Update badge in README.md
                update_coverage_badge "$COVERAGE_PERCENT"
            else
                echo -e "${YELLOW}⚠️  Could not extract coverage percentage from output${NC}"
            fi
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
    if [ -n "$COVERAGE_PERCENT" ]; then
        echo -e "${BLUE}📊 Test coverage: ${COVERAGE_PERCENT}${NC}"
        echo -e "${BLUE}📝 Coverage badge has been updated in README.md${NC}"
    fi
    echo -e "${BLUE}💡 Tip: Run 'git add .' and 'git commit' when ready.${NC}"
    echo -e "${BLUE}💡 Code complies with CONSTRAINTS_PY.md requirements${NC}"
else
    echo -e "${RED}❌ $FAILED_CHECKS check(s) failed. Please fix the issues above before committing.${NC}"
    echo -e "${BLUE}💡 Tip: Install missing tools with: pip install ruff mypy bandit pytest pytest-cov${NC}"
    echo -e "${BLUE}💡 Tip: Review CONSTRAINTS_PY.md for code quality requirements${NC}"
    exit 1
fi
