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



# Test 1: 
echo -e "${YELLOW}[TEST 1] LOCAL FLOW${NC}"
make variant1 VARIANT=v001 \
    RAW=data/01-raw/01_explore_raw_raw.csv \
    CLEANING_STRATEGY=basic \
    NAN_VALUES='[-999999]'
echo -e "${YELLOW}Executing notebook for v001${NC}"
make nb1-run VARIANT=v001
echo -e "${YELLOW}Executing script for v001${NC}"
make script1-run VARIANT=v001
echo -e "${YELLOW}Publishing variant v001${NC}"
make publish1 VARIANT=v001
echo -e "${GREEN}[✓] LOCAL FLOW PASSED${NC}"
echo ""

# Test 2: 
echo -e "${YELLOW}[TEST 2] LOCAL FLOW${NC}"
make variant2 VARIANT=v010 \
    PARENT=v001 \
    BANDS="40 60 80" \
    STRATEGY=transitions \
    NAN=keep
echo -e "${YELLOW}Executing notebook for v010${NC}"
make nb2-run VARIANT=v010
echo -e "${YELLOW}Executing script for v001${NC}"
make script2-run VARIANT=v010
echo -e "${YELLOW}Publishing variant v010${NC}"
make publish2 VARIANT=v010
echo -e "${GREEN}[✓] LOCAL FLOW PASSED${NC}"
echo ""

# Test 3: 
echo -e "${YELLOW}[TEST 3] LOCAL FLOW${NC}"
make variant3 VARIANT=v100 \
    PARENT=v010 \
    OW=600 \
    LT=100 \
    PW=100 \
    WS=synchro \
    NAN=discard
echo -e "${YELLOW}Executing notebook for v100${NC}"
make nb3-run VARIANT=v100
echo -e "${YELLOW}Executing script for v100${NC}"
make script3-run VARIANT=v100
echo -e "${YELLOW}Publishing variant v100${NC}"
make publish3 VARIANT=v100
echo -e "${GREEN}[✓] LOCAL FLOW PASSED${NC}"
echo ""

# Test 4: 
echo -e "${YELLOW}[TEST 4] LOCAL FLOW${NC}"
make variant4 VARIANT=v101 \
    PARENT=v100 \
    OBJECTIVE="{operator: OR, events: [Battery_Active_Power_0_40-to-80_100, Battery_Active_Power_40_60-to-80_100]}"     
echo -e "${YELLOW}Executing notebook for v101${NC}"
make nb4-run VARIANT=v101
echo -e "${YELLOW}Executing script for v101${NC}"
make script4-run VARIANT=v101
echo -e "${YELLOW}Publishing variant v101${NC}"
make publish4 VARIANT=v101  
echo -e "${GREEN}[✓] LOCAL FLOW PASSED${NC}"
echo ""

# Test 5: 
echo -e "${YELLOW}[TEST 5] LOCAL FLOW${NC}"
echo -e "${YELLOW}Creating variant v111 (local)${NC}"
make variant5 VARIANT=v111 PARENT=v101 \
    MODEL_FAMILY=dense_bow \
    IMBALANCE_STRATEGY=rare_events \
    IMBALANCE_MAX_MAJ=20000
echo -e "${YELLOW}Executing notebook for v111${NC}"
make nb5-run VARIANT=v111  
echo -e "${YELLOW}Executing script for v111${NC}"
make script5-run VARIANT=v111
echo -e "${YELLOW}Publishing variant v111${NC}"
make publish5 VARIANT=v111  
echo -e "${GREEN}[✓] LOCAL FLOW PASSED${NC}"
echo ""
