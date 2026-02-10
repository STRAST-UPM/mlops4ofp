#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Compara nb3-run vs script3-run en Fase 03 para una o varias variantes.
Genera copias de los parquet, los convierte a CSV con progreso y hace diff.
"""

import argparse
import subprocess
from pathlib import Path

import pyarrow.parquet as pq
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def stringify_list(col: pd.Series) -> pd.Series:
    return col.apply(lambda x: "" if x is None else ",".join(map(str, x)))


def parquet_to_csv(parquet_path: Path, csv_path: Path, label: str, batch_size: int) -> None:
    pf = pq.ParquetFile(parquet_path)
    total_rows = pf.metadata.num_rows if pf.metadata else None
    if csv_path.exists():
        csv_path.unlink()

    written = 0
    batch_idx = 0
    header = True

    print(f"[{label}] start: {parquet_path} -> {csv_path}")
    for batch in pf.iter_batches(batch_size=batch_size):
        df = batch.to_pandas()
        df["OW_events"] = stringify_list(df["OW_events"])
        df["PW_events"] = stringify_list(df["PW_events"])
        df.to_csv(csv_path, mode="a", index=False, header=header)
        header = False
        written += len(df)
        batch_idx += 1
        if batch_idx % 10 == 0 or (total_rows and written == total_rows):
            if total_rows:
                print(f"[{label}] batches: {batch_idx} | rows: {written}/{total_rows}")
            else:
                print(f"[{label}] batches: {batch_idx} | rows: {written}")

    print(f"[{label}] done: rows={written}")


def compare_variant(variant: str, batch_size: int, diff_lines: int) -> None:
    print(f"\n=== VARIANT {variant} ===")

    run(["make", "nb3-run", f"VARIANT={variant}"])

    base = ROOT / "executions" / "03_preparewindowsds" / variant
    nb_parquet = base / "03_preparewindowsds_dataset.parquet"
    nb_copy = base / "03_preparewindowsds_dataset_nb.parquet"
    nb_copy.write_bytes(nb_parquet.read_bytes())

    run(["make", "script3-run", f"VARIANT={variant}"])

    sc_parquet = base / "03_preparewindowsds_dataset.parquet"
    sc_copy = base / "03_preparewindowsds_dataset_script.parquet"
    sc_copy.write_bytes(sc_parquet.read_bytes())

    nb_csv = base / "03_preparewindowsds_dataset_nb.csv"
    sc_csv = base / "03_preparewindowsds_dataset_script.csv"

    parquet_to_csv(nb_copy, nb_csv, f"{variant} NB", batch_size=batch_size)
    parquet_to_csv(sc_copy, sc_csv, f"{variant} SCRIPT", batch_size=batch_size)

    diff_cmd = ["diff", "-u", str(nb_csv), str(sc_csv)]
    diff = subprocess.run(diff_cmd, cwd=ROOT, capture_output=True, text=True)
    diff_out = diff.stdout.splitlines()[:diff_lines]
    print("--- diff (head) ---")
    if diff_out:
        print("\n".join(diff_out))
    else:
        print("(no differences)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", nargs="+", required=True)
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument("--diff-lines", type=int, default=200)
    args = parser.parse_args()

    for variant in args.variants:
        compare_variant(variant, args.batch_size, args.diff_lines)


if __name__ == "__main__":
    main()