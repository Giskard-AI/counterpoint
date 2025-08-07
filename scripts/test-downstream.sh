#!/bin/bash

# Test downstream packages against local counterpoint changes
# This script helps validate that counterpoint changes don't break downstream dependencies

set -e

cleanup() {
    if [ ! -d "$DOWNSTREAM_DIR" ]; then return; fi
    log_info "Cleaning up..."
    for pkg_dir in "$DOWNSTREAM_DIR"/*; do
        if [ -d "$pkg_dir" ] && [ -f "$pkg_dir/pyproject.toml.backup" ]; then
            log_info "Restoring pyproject.toml for $(basename "$pkg_dir")"
            mv "$pkg_dir/pyproject.toml.backup" "$pkg_dir/pyproject.toml"
        fi
    done
}
trap cleanup EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOWNSTREAM_DIR="$PROJECT_ROOT/.downstream"

# Downstream packages to test
PACKAGES=("lidar")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -p, --package PACKAGE   Test specific package (default: all packages)"
    echo "  -c, --clean            Clean downstream directories before testing"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Available packages: ${PACKAGES[*]}"
}

# Parse command line arguments
CLEAN=false
SELECTED_PACKAGES=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--package)
            SELECTED_PACKAGES+=("$2")
            shift 2
            ;;
        -c|--clean)
            CLEAN=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Use all packages if none specified
if [ ${#SELECTED_PACKAGES[@]} -eq 0 ]; then
    SELECTED_PACKAGES=("${PACKAGES[@]}")
fi

# Validate selected packages
for pkg in "${SELECTED_PACKAGES[@]}"; do
    if [[ ! " ${PACKAGES[*]} " =~ " ${pkg} " ]]; then
        log_error "Unknown package: $pkg"
        log_info "Available packages: ${PACKAGES[*]}"
        exit 1
    fi
done

log_info "Starting downstream testing for packages: ${SELECTED_PACKAGES[*]}"

# Clean if requested
if [ "$CLEAN" = true ]; then
    log_info "Cleaning downstream directories..."
    rm -rf "$DOWNSTREAM_DIR"
    rm -rf "$PROJECT_ROOT/dist"
fi

# Create downstream directory
mkdir -p "$DOWNSTREAM_DIR"

# Build counterpoint wheel
log_info "Building counterpoint wheel..."
cd "$PROJECT_ROOT"
if ! uv build; then
    log_error "Failed to build counterpoint wheel"
    exit 1
fi

WHEEL_PATH=$(ls "$PROJECT_ROOT/dist"/*.whl | head -1)
if [ -z "$WHEEL_PATH" ]; then
    log_error "No wheel file found in dist/"
    exit 1
fi

log_success "Built wheel: $(basename "$WHEEL_PATH")"

# Test each package
failed_packages=()
successful_packages=()

for package in "${SELECTED_PACKAGES[@]}"; do
    log_info "Testing package: $package"
    
    package_dir="$DOWNSTREAM_DIR/$package"
    
    # Clone or update repository
    if [ ! -d "$package_dir" ]; then
        log_info "Cloning $package repository..."
        cd "$DOWNSTREAM_DIR"
        if ! git clone "https://github.com/Giskard-AI/$package.git"; then
            log_error "Failed to clone $package repository"
            failed_packages+=("$package")
            continue
        fi
    else
        log_info "Updating $package repository..."
        cd "$package_dir"
        if ! git pull; then
            log_warning "Failed to update $package repository, continuing with existing version..."
        fi
    fi
    
    cd "$package_dir"
    
    # Copy wheel and update dependencies
    log_info "Setting up $package with local counterpoint..."
    WHEEL_NAME=$(basename "$WHEEL_PATH")
    cp "$WHEEL_PATH" "./$WHEEL_NAME"
    
    # Backup original pyproject.toml
    if [ -f pyproject.toml ]; then
        cp pyproject.toml pyproject.toml.backup
        
        # Update counterpoint dependency to use local wheel
        if grep -q "counterpoint" pyproject.toml; then
            # Handle both dependency formats:
            # 1. Simple dependency in array: "counterpoint"
            # 2. Source specification: counterpoint = { git = "..." }
            
            # Ensure [tool.uv.sources] exists, creating it if necessary.
            if ! grep -q "\[tool\.uv\.sources\]" pyproject.toml; then
                echo "" >> pyproject.toml
                echo "[tool.uv.sources]" >> pyproject.toml
            fi

            # Remove any existing counterpoint source definition from the section to avoid duplicates.
            sed -i.bak '/\[tool\.uv\.sources\]/,/^\[/ { /\s*counterpoint\s*=/d; }' pyproject.toml

            # Add the new counterpoint source pointing to the local wheel.
            awk -v whl="$WHEEL_NAME" '/\[tool\.uv\.sources\]/{print;print "counterpoint = { path = \"./" whl "\" }";next}1' pyproject.toml > pyproject.toml.tmp && mv pyproject.toml.tmp pyproject.toml

            rm -f pyproject.toml.bak
            log_success "Updated counterpoint source to use local wheel"
        else
            log_warning "counterpoint not found in dependencies - this might not be a counterpoint consumer"
        fi
    else
        log_warning "No pyproject.toml found in $package"
        failed_packages+=("$package")
        continue
    fi
    
    # Install dependencies
    log_info "Installing dependencies for $package..."
    if ! uv sync --all-extras; then
        log_error "Failed to sync dependencies for $package"
        failed_packages+=("$package")
        continue
    fi
  
    # Run tests
    log_info "Running tests for $package..."
    
    # Try different test approaches
    test_passed=false
    
    # Method 1: Use Makefile if available
    if [ -f Makefile ] && grep -q "^test:" Makefile; then
        log_info "Using 'make test' command..."
        if make test; then
            test_passed=true
        fi
    fi
    
    # Method 2: Direct pytest if Makefile didn't work
    if [ "$test_passed" = false ]; then
        log_info "Using direct pytest command..."
        if uv run pytest tests/ --maxfail=10 -v; then
            test_passed=true
        fi
    fi
    
    # Restore original pyproject.toml
    if [ -f pyproject.toml.backup ]; then
        mv pyproject.toml.backup pyproject.toml
    fi
    
    # Clean up wheel
    rm -f "$WHEEL_NAME"
    
    if [ "$test_passed" = true ]; then
        log_success "Tests passed for $package"
        successful_packages+=("$package")
    else
        log_error "Tests failed for $package"
        failed_packages+=("$package")
    fi
    
    echo ""
done

# Summary
log_info "=== Downstream Testing Summary ==="

if [ ${#successful_packages[@]} -gt 0 ]; then
    log_success "Successful packages (${#successful_packages[@]}): ${successful_packages[*]}"
fi

if [ ${#failed_packages[@]} -gt 0 ]; then
    log_error "Failed packages (${#failed_packages[@]}): ${failed_packages[*]}"
    echo ""
    log_error "Some downstream tests failed. Please review the output above."
    exit 1
else
    log_success "All downstream tests passed! 🎉"
fi
