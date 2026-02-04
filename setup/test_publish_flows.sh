#!/bin/bash
set -e

echo "=========================================="
echo "MLOps4OFP — Test Publish Flows (Local + Remote)"
echo "=========================================="
echo ""

# Color helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# ==========================================
# Test 1: LOCAL FLOW
# ==========================================
echo -e "${YELLOW}[TEST 1] LOCAL FLOW${NC}"
echo "---"
echo "Setup: clean-setup → setup(local.yaml) → check-setup"
echo "Variant: create v001 → publish v001"
echo ""

make clean-setup
make setup SETUP_CFG=setup/local.yaml
make check-setup

echo -e "${YELLOW}Creating variant v001 (local)${NC}"
make variant1 VARIANT=v001 RAW=data/01-raw/01_explore_raw_raw.csv

echo -e "${YELLOW}Executing notebook for v001${NC}"
make nb1-run VARIANT=v001

echo -e "${YELLOW}Executing script for v001${NC}"
make script1-run VARIANT=v001

echo -e "${YELLOW}Publishing variant v001${NC}"
make publish1 VARIANT=v001

echo -e "${GREEN}[✓] LOCAL FLOW PASSED${NC}"
echo ""

# ==========================================
# Test 2: REMOTE FLOW
# ==========================================
echo -e "${YELLOW}[TEST 2] REMOTE FLOW${NC}"
echo "---"
echo "Setup: clean-setup → setup(remote.yaml) → check-setup"
echo "Variant: create v002 → publish v002"
echo ""

make clean-setup
make setup SETUP_CFG=setup/remote.yaml
make check-setup

echo -e "${YELLOW}Creating variant v002 (remote)${NC}"
make variant1 VARIANT=v002 RAW=data/01-raw/01_explore_raw_raw.csv

echo -e "${YELLOW}Executing notebook for v002${NC}"
make nb1-run VARIANT=v002

echo -e "${YELLOW}Executing script for v002${NC}"
make script1-run VARIANT=v002

echo -e "${YELLOW}Publishing variant v002${NC}"
make publish1 VARIANT=v002

echo -e "${GREEN}[✓] REMOTE FLOW PASSED${NC}"
echo ""

# ==========================================
# Summary
# ==========================================
echo "=========================================="
echo -e "${GREEN}[✓] ALL TESTS PASSED${NC}"
echo "=========================================="
echo ""
echo "Results:"
echo "  • Local flow: v001 published to .dvc_storage (local)"
echo "  • Remote flow: v002 published to publish remote + gdrive"
echo ""
