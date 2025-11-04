
# backend/export_router.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pathlib import Path
from io import BytesIO
from datetime import datetime
import os
import pandas as pd

router = APIRouter()

# Config: carpeta de logs con CSV
LOG_DIR = Path(os.getenv("LOG_DIR", "./logs"))

@router.get("/export/xlsx")
def export_logs_as_xlsx():
    """
    Lee todos los CSV de LOG_DIR y devuelve un .xlsx con una hoja por archivo.
    - Nombre de hoja: stem del CSV (máx 31 chars).
    - Si un CSV falla, se agrega una hoja *_ERR con el error, sin abortar.
    """
    if not LOG_DIR.exists():
        raise HTTPException(status_code=404, detail=f"No existe {LOG_DIR}")

    csvs = sorted(LOG_DIR.glob("*.csv"))
    if not csvs:
        raise HTTPException(status_code=404, detail=f"No hay CSVs en {LOG_DIR}")

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as xw:
        for csv_path in csvs:
            try:
                sheet = csv_path.stem[:31] or "data"
                df = pd.read_csv(csv_path)
                df.to_excel(xw, sheet_name=sheet, index=False)
            except Exception as e:
                err_sheet = (csv_path.stem[:25] + "_ERR")[:31]
                pd.DataFrame({ "error": [str(e)], "file": [csv_path.name] }).to_excel(
                    xw, sheet_name=err_sheet, index=False
                )

    buffer.seek(0)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"logs_{ts}.xlsx"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
