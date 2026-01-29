from __future__ import annotations
import numpy as np
import pandas as pd
from .storage import write_table

def generate_master_data(df_raw: pd.DataFrame, seed: int = 42):
    rng = np.random.default_rng(seed)

    branches = pd.DataFrame([
        {"branch_id": 1, "branch_name": "Sucursal Centro", "city": "Quito"},
        {"branch_id": 2, "branch_name": "Sucursal Norte",  "city": "Quito"},
        {"branch_id": 3, "branch_name": "Sucursal Valle",  "city": "Cumbayá"},
    ])

    categories = sorted(df_raw["category"].dropna().unique().tolist())
    suppliers = pd.DataFrame([
        {
            "supplier_id": i,
            "supplier_name": f"Proveedor {cat}",
            "lead_time_days": int(rng.integers(1, 5)),
            "contact_email": f"compras_{str(cat).lower()}@proveedor.ec"
        }
        for i, cat in enumerate(categories, start=1)
    ])

    prod_keys = df_raw[["food_item", "category", "price"]].drop_duplicates().copy()
    prod_keys = prod_keys.sort_values(["category", "food_item"]).reset_index(drop=True)
    prod_keys["product_id"] = np.arange(1001, 1001 + len(prod_keys))

    margins = rng.uniform(0.35, 0.60, size=len(prod_keys))
    prod_keys["unit_cost"] = (prod_keys["price"] * (1 - margins)).round(2)

    cat_to_supplier = {cat: int(suppliers.loc[suppliers["supplier_name"] == f"Proveedor {cat}", "supplier_id"].iloc[0])
                       for cat in categories}
    prod_keys["supplier_id"] = prod_keys["category"].map(cat_to_supplier)

    products = prod_keys.rename(columns={"price": "sale_price"})[
        ["product_id", "food_item", "category", "sale_price", "unit_cost", "supplier_id"]
    ]

    demand = df_raw.groupby(["food_item", "category"])["quantity"].sum().reset_index()
    demand = demand.merge(products, on=["food_item", "category"], how="left")

    qmin, qmax = demand["quantity"].min(), demand["quantity"].max()
    inv_rows = []
    for _, r in demand.iterrows():
        base = 20 + int(80 * ((r["quantity"] - qmin) / (qmax - qmin + 1e-9)))
        stock_min = int(max(10, base * 0.25))
        reorder_qty = int(max(20, base * 0.60))
        for b in branches["branch_id"]:
            factor = float(rng.uniform(0.8, 1.2))
            inv_rows.append({
                "branch_id": int(b),
                "product_id": int(r["product_id"]),
                "stock_on_hand": int(base * factor),
                "stock_min": stock_min,
                "reorder_qty": reorder_qty,
            })
    inventory = pd.DataFrame(inv_rows)

    return branches, suppliers, products, inventory

def seed_and_save(df_raw: pd.DataFrame, seed: int = 42):
    branches, suppliers, products, inventory = generate_master_data(df_raw, seed=seed)
    write_table("branches", branches)
    write_table("suppliers", suppliers)
    write_table("products", products)
    write_table("inventory", inventory)
