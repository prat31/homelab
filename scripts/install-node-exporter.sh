#!/bin/bash
# ===========================================
# Node Exporter Installation Script for macOS
# ===========================================
# This script installs node_exporter via Homebrew on macOS (ARM64)
# Homebrew handles code signing/notarization properly
# Run with: ./install-node-exporter.sh
# ===========================================

set -e

echo "=== Node Exporter Installation for macOS ==="

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "Error: Homebrew is not installed."
    echo "Install it from https://brew.sh"
    exit 1
fi

# Check if already installed
if brew list node_exporter &> /dev/null; then
    echo "Node exporter is already installed via Homebrew"
    echo "Current version: $(node_exporter --version 2>&1 | head -1)"

    # Check if service is running
    if brew services list | grep node_exporter | grep -q started; then
        echo "Service is already running"
    else
        echo "Starting service..."
        brew services start node_exporter
    fi
else
    echo "Installing node_exporter via Homebrew..."
    brew install node_exporter

    echo "Starting node_exporter service..."
    brew services start node_exporter
fi

# Wait a moment for service to start
sleep 2

# Verify installation
echo ""
echo "=== Verifying Installation ==="
if curl -s http://localhost:9100/metrics > /dev/null 2>&1; then
    echo "✓ Node exporter is running on http://localhost:9100"
else
    echo "✗ Node exporter is not responding. Check with: brew services list"
    exit 1
fi

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Useful commands:"
echo "  Check status:   brew services list | grep node_exporter"
echo "  View metrics:   curl -s http://localhost:9100/metrics | head"
echo "  Stop service:   brew services stop node_exporter"
echo "  Start service:  brew services start node_exporter"
echo "  Restart:        brew services restart node_exporter"
