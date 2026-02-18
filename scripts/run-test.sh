#!/bin/bash
set -e

# Color helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Test 7: 
echo -e "${YELLOW}[TEST 7]${NC}"
make variant7 VARIANT=v701 PARENT=v601 BATCH_SIZE=512
echo -e "${YELLOW}Executing notebook for v701${NC}"
make nb7-run VARIANT=v701  
echo -e "${YELLOW}Executing script for v701${NC}"
make script7-run VARIANT=v701
echo -e "${YELLOW}Publishing variant v701${NC}"
#make publish7 VARIANT=v701  
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""


exit



# Test 1: 
echo -e "${YELLOW}[TEST 1]${NC}"
make variant1 VARIANT=v101 \
    RAW=data/01-raw/01_explore_raw_raw.csv \
    CLEANING_STRATEGY=basic \
    NAN_VALUES='[-999999]'
echo -e "${YELLOW}Executing notebook for v101${NC}"
make nb1-run VARIANT=v101
echo -e "${YELLOW}Executing script for v101${NC}"
make script1-run VARIANT=v101
echo -e "${YELLOW}Publishing variant v101${NC}"
#make publish1 VARIANT=v101
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""


# Test 1.1: 
echo -e "${YELLOW}[TEST 1.1]${NC}"
make variant1 VARIANT=v100 \
    RAW=data/01-raw/01_explore_raw_raw.csv \
    CLEANING_STRATEGY=basic \
    NAN_VALUES='[-999999]' \
    FIRST_LINE=1 MAX_LINES=50000
echo -e "${YELLOW}Executing notebook for v100${NC}"
make nb1-run VARIANT=v100
echo -e "${YELLOW}Executing script for v100${NC}"
make script1-run VARIANT=v100
echo -e "${YELLOW}Publishing variant v100${NC}"
#make publish1 VARIANT=v100
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""

# Test 2: 
echo -e "${YELLOW}[TEST 2]${NC}"
make variant2 VARIANT=v201 \
    PARENT=v101 \
    BANDS="40 60 80" \
    STRATEGY=transitions \
    NAN=keep
echo -e "${YELLOW}Executing notebook for v201${NC}"
make nb2-run VARIANT=v201
echo -e "${YELLOW}Executing script for v201${NC}"
make script2-run VARIANT=v201
echo -e "${YELLOW}Publishing variant v201${NC}"
#make publish2 VARIANT=v201
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""

# Test 2.1: 
echo -e "${YELLOW}[TEST 2]${NC}"
make variant2 VARIANT=v200 \
    PARENT=v101 \
    BANDS="40 60 80" \
    STRATEGY=levels \
    NAN=discard
echo -e "${YELLOW}Executing notebook for v200${NC}"
make nb2-run VARIANT=v200
echo -e "${YELLOW}Executing script for v200${NC}"
make script2-run VARIANT=v200
echo -e "${YELLOW}Publishing variant v200${NC}"
#make publish2 VARIANT=v200
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""



# Test 3: 
echo -e "${YELLOW}[TEST 3]${NC}"
make variant3 VARIANT=v301 \
    PARENT=v201 \
    OW=600 \
    LT=100 \
    PW=100 \
    WS=synchro \
    NAN=discard
echo -e "${YELLOW}Executing notebook for v301${NC}"
make nb3-run VARIANT=v301
echo -e "${YELLOW}Executing script for v301${NC}"
make script3-run VARIANT=v301
echo -e "${YELLOW}Publishing variant v301${NC}"
#make publish3 VARIANT=v301
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""

# Test 3.1: 
echo -e "${YELLOW}[TEST 3.1]${NC}"
make variant3 VARIANT=v300 \
    PARENT=v201 \
    OW=600 \
    LT=100 \
    PW=100 \
    WS=asynOW \
    NAN=discard
echo -e "${YELLOW}Executing notebook for v300${NC}"
make nb3-run VARIANT=v300
echo -e "${YELLOW}Executing script for v300${NC}"
make script3-run VARIANT=v300
echo -e "${YELLOW}Publishing variant v300${NC}"
#make publish3 VARIANT=v300
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""

# Test 3.2: 
echo -e "${YELLOW}[TEST 3.2]${NC}"
make variant3 VARIANT=v302 \
    PARENT=v201 \
    OW=600 \
    LT=100 \
    PW=100 \
    WS=asynPW \
    NAN=discard
echo -e "${YELLOW}Executing notebook for v302${NC}"
make nb3-run VARIANT=v302
echo -e "${YELLOW}Executing script for v302${NC}"
make script3-run VARIANT=v302
echo -e "${YELLOW}Publishing variant v302${NC}"
#make publish3 VARIANT=v302
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""


# Test 4: 
echo -e "${YELLOW}[TEST 4]${NC}"
make variant4 VARIANT=v401 \
    PREDICTION_NAME=Battery_Active_Power_any-to-80_100 \
    PARENT=v301 \
    OBJECTIVE="{operator: OR, events: [Battery_Active_Power_0_40-to-80_100, Battery_Active_Power_40_60-to-80_100, Battery_Active_Power_60_80-to-80_100]}"     
echo -e "${YELLOW}Executing notebook for v401${NC}"
make nb4-run VARIANT=v401
echo -e "${YELLOW}Executing script for v401${NC}"
make script4-run VARIANT=v401
echo -e "${YELLOW}Publishing variant v401${NC}"
#make publish4 VARIANT=v401  
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""

# Test 4.1: 
echo -e "${YELLOW}[TEST 4.1]${NC}"
make variant4 VARIANT=v400 \
    PREDICTION_NAME=Battery_Active_Power_Set_Response_any-to-80_100 \
    PARENT=v301 \
    OBJECTIVE="{operator: OR, \
    events: [Battery_Active_Power_Set_Response_0_40-to-80_100, \
    Battery_Active_Power_Set_Response_40_60-to-80_100, \
    Battery_Active_Power_Set_Response_60_80-to-80_100]}"     
echo -e "${YELLOW}Executing notebook for v400${NC}"
make nb4-run VARIANT=v400  
echo -e "${YELLOW}Executing script for v400${NC}"
make script4-run VARIANT=v400
echo -e "${YELLOW}Publishing variant v400${NC}"
#make publish4 VARIANT=v400  
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""

# Test 4.2: 
echo -e "${YELLOW}[TEST 4.2]${NC}"
make variant4 VARIANT=v402 \
    PREDICTION_NAME=PVPCS_Active_Power_any-to-80_100 \
    PARENT=v301 \
    OBJECTIVE="{operator: OR, \
    events: [PVPCS_Active_Power_0_40-to-80_100, \
    PVPCS_Active_Power_40_60-to-80_100, \
    PVPCS_Active_Power_60_80-to-80_100]}"     
echo -e "${YELLOW}Executing notebook for v402${NC}"
make nb4-run VARIANT=v402  
echo -e "${YELLOW}Executing script for v402${NC}"
make script4-run VARIANT=v402
echo -e "${YELLOW}Publishing variant v402${NC}"
#make publish4 VARIANT=v402  
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""

# Test 4.3: 
echo -e "${YELLOW}[TEST 4.3]${NC}"
make variant4 VARIANT=v403 \
    PREDICTION_NAME=GE_Active_Power_any-to-80_100 \
    PARENT=v301 \
    OBJECTIVE="{operator: OR, \
    events: [GE_Active_Power_0_40-to-80_100, \
    GE_Active_Power_40_60-to-80_100, \
    GE_Active_Power_60_80-to-80_100]}"     
echo -e "${YELLOW}Executing notebook for v403${NC}"
make nb4-run VARIANT=v403  
echo -e "${YELLOW}Executing script for v403${NC}"
make script4-run VARIANT=v403
echo -e "${YELLOW}Publishing variant v403${NC}"
#make publish4 VARIANT=v403  
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""

# Test 5: 
echo -e "${YELLOW}[TEST 5]${NC}"
make variant5 VARIANT=v501 PARENT=v401 \
    MODEL_FAMILY=dense_bow \
    IMBALANCE_STRATEGY=rare_events \
    IMBALANCE_MAX_MAJ=20000
echo -e "${YELLOW}Executing notebook for v501${NC}"
make nb5-run VARIANT=v501  
echo -e "${YELLOW}Executing script for v501${NC}"
make script5-run VARIANT=v501
echo -e "${YELLOW}Publishing variant v501${NC}"
#make publish5 VARIANT=v501  
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""


# Test 5.2: 
echo -e "${YELLOW}[TEST 5.2]${NC}"
make variant5 VARIANT=v502 PARENT=v400 \
    MODEL_FAMILY=dense_bow \
    IMBALANCE_STRATEGY=rare_events \
    IMBALANCE_MAX_MAJ=20000
echo -e "${YELLOW}Executing notebook for v502${NC}"
make nb5-run VARIANT=v502  
echo -e "${YELLOW}Executing script for v502${NC}"
make script5-run VARIANT=v502
echo -e "${YELLOW}Publishing variant v502${NC}"
#make publish5 VARIANT=v502  
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""

# Test 5.3: 
echo -e "${YELLOW}[TEST 5.3]${NC}"
make variant5 VARIANT=v503 PARENT=v402 \
    MODEL_FAMILY=sequence_embedding \
    IMBALANCE_STRATEGY=rare_events \
    IMBALANCE_MAX_MAJ=20000
echo -e "${YELLOW}Executing notebook for v503${NC}"
make nb5-run VARIANT=v503  
echo -e "${YELLOW}Executing script for v503${NC}"
make script5-run VARIANT=v503
echo -e "${YELLOW}Publishing variant v503${NC}"
#make publish5 VARIANT=v503  
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""

# Test 5.4: 
echo -e "${YELLOW}[TEST 5.4]${NC}"
make variant5 VARIANT=v504 PARENT=v403 \
    MODEL_FAMILY=cnn1d \
    IMBALANCE_STRATEGY=rare_events \
    IMBALANCE_MAX_MAJ=20000
echo -e "${YELLOW}Executing notebook for v504${NC}"
make nb5-run VARIANT=v504  
echo -e "${YELLOW}Executing script for v504${NC}"
make script5-run VARIANT=v504
echo -e "${YELLOW}Publishing variant v504${NC}"
#make publish5 VARIANT=v504  
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""





# Test 6: 
echo -e "${YELLOW}[TEST 6]${NC}"
make variant6 VARIANT=v601 \
    PARENTS_F05="v501 v502 v503 v504" 
echo -e "${YELLOW}Executing notebook for v601${NC}"
make nb6-run VARIANT=v601  
echo -e "${YELLOW}Executing script for v601${NC}"
make script6-run VARIANT=v601
echo -e "${YELLOW}Publishing variant v601${NC}"
#make publish6 VARIANT=v601  
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""


# Test 7: 
echo -e "${YELLOW}[TEST 7]${NC}"
make variant7 VARIANT=v701 PARENT=v601
echo -e "${YELLOW}Executing notebook for v701${NC}"
make nb7-run VARIANT=v701  
echo -e "${YELLOW}Executing script for v701${NC}"
make script7-run VARIANT=v701
echo -e "${YELLOW}Publishing variant v701${NC}"
#make publish7 VARIANT=v701  
echo -e "${GREEN}[✓] PASSED${NC}"
echo ""