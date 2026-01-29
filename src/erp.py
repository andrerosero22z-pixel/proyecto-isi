from __future__ import annotations
from datetime import datetime
import pandas as pd
from .storage import read_table, append_table, next_id

def record_sale(order_id: int):
    orders = read_table("orders")
    items = read_table("order_items")
    prod = read_table("products")

    orders["order_id"] = pd.to_numeric(orders["order_id"], errors="coerce")
    row = orders[orders["order_id"] == int(order_id)]
    if row.empty:
        raise ValueError("Order not found")

    total = float(pd.to_numeric(row["total_amount"], errors="coerce").fillna(0.0).iloc[0])
    now = datetime.utcnow().isoformat()

    entry_id = next_id("ledger_entries","entry_id",start=1)
    append_table("ledger_entries", pd.DataFrame([{
        "entry_id": entry_id,
        "entry_ts": now,
        "order_id": int(order_id),
        "entry_type": "REVENUE",
        "amount": total,
        "note": "Ingreso por venta confirmada"
    }]))

    items["order_id"] = pd.to_numeric(items["order_id"], errors="coerce")
    oi = items[items["order_id"] == int(order_id)].merge(prod, on="product_id", how="left")

    if oi.empty:
        cogs = 0.0
    else:
        q = pd.to_numeric(oi["quantity"], errors="coerce").fillna(0).astype(int)
        uc = pd.to_numeric(oi["unit_cost"], errors="coerce").fillna(0.0)
        cogs = float((q * uc).sum())

    entry_id2 = next_id("ledger_entries","entry_id",start=1)
    append_table("ledger_entries", pd.DataFrame([{
        "entry_id": entry_id2,
        "entry_ts": now,
        "order_id": int(order_id),
        "entry_type": "COGS",
        "amount": cogs,
        "note": "Costo de venta estimado (unit_cost sintético)"
    }]))
