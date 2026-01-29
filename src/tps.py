from __future__ import annotations
from datetime import datetime
import pandas as pd
from .storage import read_table, write_table, append_table, ensure_table, next_id
from . import erp, scm

def init_tables():
    ensure_table("customers", ["customer_id","customer_name","created_at"])
    ensure_table("orders", ["order_id","customer_id","branch_id","order_ts","status","payment_method","total_amount","is_synthetic"])
    ensure_table("order_items", ["order_item_id","order_id","product_id","quantity","unit_price","line_total"])
    ensure_table("ledger_entries", ["entry_id","entry_ts","order_id","entry_type","amount","note"])
    ensure_table("stock_movements", ["movement_id","movement_ts","branch_id","product_id","qty_change","reason","ref_order_id","ref_po_id"])
    ensure_table("purchase_orders", ["po_id","po_ts","supplier_id","branch_id","status","expected_date"])
    ensure_table("purchase_order_items", ["po_item_id","po_id","product_id","qty_ordered","unit_cost_est"])

def ensure_customer(customer_name: str) -> int:
    customers = read_table("customers")
    if not customers.empty:
        row = customers[customers["customer_name"] == customer_name]
        if not row.empty:
            return int(row["customer_id"].iloc[0])
    cid = next_id("customers","customer_id",start=1)
    append_table("customers", pd.DataFrame([{
        "customer_id": cid,
        "customer_name": customer_name,
        "created_at": datetime.utcnow().isoformat()
    }]))
    return cid

def import_real_transactions(df_raw: pd.DataFrame):
    products = read_table("products")
    orders = read_table("orders")

    if not orders.empty and "is_synthetic" in orders.columns:
        if (pd.to_numeric(orders["is_synthetic"], errors="coerce").fillna(0).astype(int) == 0).any():
            return 0

    order_id_start = next_id("orders", "order_id", start=1)
    oi_id_start = next_id("order_items", "order_item_id", start=1)

    new_orders, new_items = [], []
    branches_pool = [1,2,3]

    for i, row in df_raw.reset_index(drop=True).iterrows():
        cname = str(row.get("customer_name","")).strip() or "Cliente_Anon"
        cid = ensure_customer(cname)

        oid = order_id_start + i
        p = products[(products["food_item"] == row["food_item"]) & (products["category"] == row["category"])]
        if p.empty:
            continue
        pid = int(p["product_id"].iloc[0])

        ts = pd.to_datetime(row.get("order_ts"), errors="coerce")
        ts_iso = ts.isoformat() if pd.notna(ts) else datetime.utcnow().isoformat()

        branch_id = branches_pool[i % len(branches_pool)]
        payment = str(row.get("payment_method","Cash"))
        qty = int(row.get("quantity",1))
        unit_price = float(row.get("price",0.0))
        line_total = float(row.get("line_total", unit_price*qty))

        new_orders.append({
            "order_id": oid,
            "customer_id": cid,
            "branch_id": branch_id,
            "order_ts": ts_iso,
            "status": "PAID",
            "payment_method": payment,
            "total_amount": line_total,
            "is_synthetic": 0
        })
        new_items.append({
            "order_item_id": oi_id_start + i,
            "order_id": oid,
            "product_id": pid,
            "quantity": qty,
            "unit_price": unit_price,
            "line_total": line_total
        })

    append_table("orders", pd.DataFrame(new_orders))
    append_table("order_items", pd.DataFrame(new_items))
    return len(new_orders)

def create_order(customer_name: str, branch_id: int, payment_method: str, order_ts: str | None = None) -> int:
    cid = ensure_customer(customer_name.strip() or "Cliente_Anon")
    oid = next_id("orders","order_id",start=1)
    ts = order_ts or datetime.utcnow().isoformat()
    append_table("orders", pd.DataFrame([{
        "order_id": oid,
        "customer_id": cid,
        "branch_id": int(branch_id),
        "order_ts": ts,
        "status": "OPEN",
        "payment_method": payment_method,
        "total_amount": 0.0,
        "is_synthetic": 0
    }]))
    return oid

def add_item(order_id: int, product_id: int, quantity: int):
    prod = read_table("products")
    p = prod[pd.to_numeric(prod["product_id"], errors="coerce") == int(product_id)]
    if p.empty:
        raise ValueError("Product not found")
    unit_price = float(p["sale_price"].iloc[0])
    line_total = unit_price * int(quantity)

    item_id = next_id("order_items","order_item_id",start=1)
    append_table("order_items", pd.DataFrame([{
        "order_item_id": item_id,
        "order_id": int(order_id),
        "product_id": int(product_id),
        "quantity": int(quantity),
        "unit_price": unit_price,
        "line_total": float(line_total)
    }]))

    orders = read_table("orders")
    items = read_table("order_items")
    items["order_id"] = pd.to_numeric(items["order_id"], errors="coerce")
    total = float(items[items["order_id"] == int(order_id)]["line_total"].sum())
    orders["order_id"] = pd.to_numeric(orders["order_id"], errors="coerce")
    orders.loc[orders["order_id"] == int(order_id), "total_amount"] = total
    write_table("orders", orders)

def checkout(order_id: int) -> dict:
    orders = read_table("orders")
    orders["order_id"] = pd.to_numeric(orders["order_id"], errors="coerce")
    mask = orders["order_id"] == int(order_id)
    if not mask.any():
        raise ValueError("Order not found")

    orders.loc[mask, "status"] = "PAID"
    write_table("orders", orders)

    # ✅ Integración automática TPS -> ERP + SCM
    erp.record_sale(int(order_id))
    scm.apply_sale(int(order_id))

    out = read_table("orders")
    out["order_id"] = pd.to_numeric(out["order_id"], errors="coerce")
    return out[out["order_id"] == int(order_id)].iloc[0].to_dict()
