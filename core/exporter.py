# core/exporter.py
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
from io import BytesIO
from apify import Actor


async def export_table(rows, csv_path, xlsx_path):
    if not rows:
        Actor.log.warning("No rows to export")
        return

    df = pd.DataFrame(rows)

    # ----------------------------
    # 1) LOCAL FILES (for dev)
    # ----------------------------
    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False)

    Actor.log.info(
        f"[EXPORT] rows={len(rows)}  csv={csv_path}  xlsx={xlsx_path}"
    )

    # ----------------------------
    # 2) APIFY DATASET (CRITICAL)
    # ----------------------------
    for row in rows:
        await Actor.push_data(row)

    Actor.log.info("[EXPORT] Dataset updated")

    # ----------------------------
    # 3) APIFY KEY-VALUE STORE FILES
    # ----------------------------
    csv_text = df.to_csv(index=False)
    await Actor.set_value(
        "SHOPIFY_CATALOG.csv",
        csv_text,
        content_type="text/csv",
    )

    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="catalog")

    await Actor.set_value(
        "SHOPIFY_CATALOG.xlsx",
        bio.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    Actor.log.info("[EXPORT] Files saved to Key-Value Store")
