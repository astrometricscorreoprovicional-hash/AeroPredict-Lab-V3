# export_logs_to_xlsx.py
from pathlib import Path
import argparse
import pandas as pd

def export_one_per_csv(log_dir: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    csvs = sorted(log_dir.glob("*.csv"))
    if not csvs:
        print(f"No hay CSVs en {log_dir}")
        return
    for csv in csvs:
        df = pd.read_csv(csv)
        out_path = out_dir / (csv.stem + ".xlsx")
        df.to_excel(out_path, index=False)
        print(f"OK -> {out_path}")

def export_all_in_one_file(log_dir: Path, out_file: Path):
    out_file.parent.mkdir(parents=True, exist_ok=True)
    csvs = sorted(log_dir.glob("*.csv"))
    if not csvs:
        print(f"No hay CSVs en {log_dir}")
        return
    with pd.ExcelWriter(out_file, engine="openpyxl") as xw:
        for csv in csvs:
            sheet = csv.stem[:31]  # límite de Excel
            pd.read_csv(csv).to_excel(xw, sheet_name=sheet, index=False)
    print(f"OK -> {out_file}")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Exporta logs CSV a Excel")
    p.add_argument("--log-dir", default="./logs", help="Carpeta con CSVs")
    p.add_argument("--out-dir", default="./exports", help="Salida para .xlsx (modo files)")
    p.add_argument("--out-file", default="./exports/logs.xlsx", help="Archivo único (modo sheets)")
    p.add_argument("--mode", choices=["files", "sheets"], default="files",
                   help="files=un .xlsx por CSV, sheets=todo en un .xlsx con varias hojas")
    args = p.parse_args()

    log_dir = Path(args.log_dir)
    if args.mode == "files":
        export_one_per_csv(log_dir, Path(args.out_dir))
    else:
        export_all_in_one_file(log_dir, Path(args.out_file))
