#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mlops4ofp.tools import params_manager

PROJECT_ROOT = Path(__file__).resolve().parents[1]
params_manager.PROJECT_ROOT = PROJECT_ROOT

PM1 = params_manager.ParamsManager("01_explore", PROJECT_ROOT)
PM2 = params_manager.ParamsManager("02_prepareeventsds", PROJECT_ROOT)
PM3 = params_manager.ParamsManager("03_preparewindowsds", PROJECT_ROOT)

# Phase 1
clean_opts = ["basic", "full"]
nan_opts = [[-999999], [-1, -999999]]
err_opts = [ {}, {"col1": [1, 2]} ]

j = 1
print("[SCRIPT] Creating Phase 01 variants v001..v008 (skip existing)")
for c in clean_opts:
    for n in nan_opts:
        for e in err_opts:
            variant = f"v{j:03d}"
            vdir = PROJECT_ROOT / "executions" / "01_explore" / variant
            if vdir.exists():
                print(f"skip {variant} (exists)")
            else:
                print(f"create {variant}: cleaning={c} nan={n} err={e}")
                PM1.create_named_variant(variant, raw_path_from_make=str(PROJECT_ROOT / "data" / "raw.csv"), extra_params=[f"cleaning_strategy={c}", f"nan_values={n}", f"error_values_by_column={e}"])
            j += 1

# Phase 2
bands_list = [[40, 60, 90], [30, 60, 90]]
strategies = ["levels", "transitions", "both"]
nans = ["keep", "discard"]
tu_opts = [None, 10]

j = 1
print("[SCRIPT] Creating Phase 02 variants v011..v034 (skip existing)")
for bands in bands_list:
    for strat in strategies:
        for nan in nans:
            for tu in tu_opts:
                variant = f"v{10 + j:03d}"
                pidx = (j - 1) % 8 + 1
                parent = f"v{pidx:03d}"
                vdir = PROJECT_ROOT / "executions" / "02_prepareeventsds" / variant
                if vdir.exists():
                    print(f"skip {variant} (exists)")
                else:
                    extra = [f"band_thresholds_pct={bands}", f"event_strategy={strat}", f"nan_handling={nan}", f"parent_variant={parent}"]
                    if tu is not None:
                        extra.append(f"Tu={tu}")
                    print(f"create {variant}: parent={parent} bands={bands} strat={strat} nan={nan} Tu={tu}")
                    PM2.create_named_variant(variant, extra_params=extra)
                j += 1

# Phase 3
ws_opts = [30, 60]
ow_opts = [0.25, 0.5]
nans = ["preserve", "discard"]
lts = [1, 2]  # placeholder numeric values for LT (schema expects number)
pws = [5, 10] # placeholder numeric values for PW

# Note: mapping from earlier shorthand to schema-compliant values:
# - window_strategy in schema expects strings like 'synchro', but original workflow used numbers.
#   We will map 30->'synchro', 60->'withinPW' as a reasonable mapping.
ws_map = {30: 'synchro', 60: 'withinPW'}

j = 1
print("[SCRIPT] Creating Phase 03 variants v111..v142 (skip existing)")
for ws in ws_opts:
    for ow in ow_opts:
        for nan in ['preserve', 'discard']:
            for lt in [1, 2]:
                for pw in [5, 10]:
                    variant = f"v{111 + j - 1:03d}"
                    pidx = (j - 1) % 24 + 11
                    parent = f"v{pidx:03d}"
                    vdir = PROJECT_ROOT / "executions" / "03_preparewindowsds" / variant
                    if vdir.exists():
                        print(f"skip {variant} (exists)")
                    else:
                        extra = [f"variant_id={variant}", f"parent_variant={parent}", f"OW={ow}", f"LT={lt}", f"PW={pw}", f"window_strategy={ws_map.get(ws, ws)}", f"nan_strategy={nan}"]
                        print(f"create {variant}: parent={parent} ws={ws} ow={ow} lt={lt} pw={pw} nan={nan}")
                        PM3.create_named_variant(variant, extra_params=extra)
                    j += 1

print('[SCRIPT] Done')
