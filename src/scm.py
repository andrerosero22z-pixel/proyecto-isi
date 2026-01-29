from __future__ import annotations
from datetime import datetime, timedelta
import pandas as pd
from .storage import read_table, write_table, append_table, next_id

def apply_sale(order_id: int):
    orders = read_table("orders")
    items = read_table("order_items")
    inv = read_table("inventory")
    prod = read_table("products")
    supp = read_table("suppliers")

    orders["order_id"] = pd.to_numeric(orders["order_id"], errors="coerce")
    orow = orders[orders["order_id"] == int(order_id)]
    if orow.empty:
        raise ValueError("Order not found")
    branch_id = int(orow["branch_id"].iloc[0])

    items["order_id"] = pd.to_numeric(items["order_id"], errors="coerce")
    oitems = items[items["order_id"] == int(order_id)]
    if oitems.empty:
        return

    # normalizar tipos
    for c in ["branch_id","product_id","stock_on_hand","stock_min","reorder_qty"]:
        inv[c] = pd.to_numeric(inv[c], errors="coerce").fillna(0).astype(int)

    now = datetime.utcnow().isoformat()

    for _, it in oitems.iterrows():
        pid = int(it["product_id"]); qty = int(it["quantity"])
        mask = (inv["branch_id"] == branch_id) & (inv["product_id"] == pid)
        if not mask.any():
            continue

        inv.loc[mask, "stock_on_hand"] = inv.loc[mask, "stock_on_hand"] - qty

        mov_id = next_id("stock_movements","movement_id",start=1)
        append_table("stock_movements", pd.DataFrame([{
            "movement_id": mov_id,
            "movement_ts": now,
            "branch_id": branch_id,
            "product_id": pid,
            "qty_change": -qty,
            "reason": "SALE",
            "ref_order_id": int(order_id),
            "ref_po_id": float("nan")
        }]))

        soh = int(inv.loc[mask, "stock_on_hand"].iloc[0])
        smin = int(inv.loc[mask, "stock_min"].iloc[0])
        rq = int(inv.loc[mask, "reorder_qty"].iloc[0])

        if soh < smin:
            prow = prod[pd.to_numeric(prod["product_id"], errors="coerce") == pid].iloc[0]
            supplier_id = int(prow["supplier_id"])
            unit_cost = float(prow["unit_cost"])

            lead = int(supp[pd.to_numeric(supp["supplier_id"], errors="coerce") == supplier_id]["lead_time_days"].iloc[0])
            expected = (datetime.utcnow() + timedelta(days=lead)).date().isoformat()

            po_id = next_id("purchase_orders","po_id",start=1)
            append_table("purchase_orders", pd.DataFrame([{
                "po_id": po_id,
                "po_ts": now,
                "supplier_id": supplier_id,
                "branch_id": branch_id,
                "status": "CREATED",
                "expected_date": expected
            }]))

            po_item_id = next_id("purchase_order_items","po_item_id",start=1)
            append_table("purchase_order_items", pd.DataFrame([{
                "po_item_id": po_item_id,
                "po_id": po_id,
                "product_id": pid,
                "qty_ordered": rq,
                "unit_cost_est": unit_cost
            }]))

    write_table("inventory", inv)
