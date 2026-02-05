import streamlit as st
import pandas as pd
from datetime import datetime

# ====== paths ======
TABLE_DIR = "tables_csv"

def read_table(name):
    path = f"{TABLE_DIR}/{name}.csv"
    return pd.read_csv(path) if pd.io.common.file_exists(path) else pd.DataFrame()

def write_table(name, df):
    df.to_csv(f"{TABLE_DIR}/{name}.csv", index=False)

def append_table(name, df_new):
    df_old = read_table(name)
    if df_old.empty:
        write_table(name, df_new)
    else:
        write_table(name, pd.concat([df_old, df_new], ignore_index=True))

def next_id(name, id_col, start=1):
    df = read_table(name)
    if df.empty or id_col not in df.columns:
        return start
    mx = pd.to_numeric(df[id_col], errors="coerce").max()
    return start if pd.isna(mx) else int(mx) + 1


# ====== ERP ======
def erp_record_sale(order_id):
    orders = read_table("orders")
    items = read_table("order_items")
    prod  = read_table("products")

    orders["order_id"] = pd.to_numeric(orders["order_id"], errors="coerce")
    row = orders[orders["order_id"] == int(order_id)]
    total = float(row["total_amount"].iloc[0])

    now = datetime.utcnow().isoformat()
    entry_id = next_id("ledger_entries", "entry_id", 1)
    append_table("ledger_entries", pd.DataFrame([{
        "entry_id": entry_id, "entry_ts": now, "order_id": order_id,
        "entry_type": "REVENUE", "amount": total, "note": "Ingreso por venta"
    }]))

    # COGS estimado
    items["order_id"] = pd.to_numeric(items["order_id"], errors="coerce")
    oi = items[items["order_id"] == int(order_id)].merge(prod, on="product_id", how="left")
    oi["quantity"] = pd.to_numeric(oi["quantity"], errors="coerce").fillna(0)
    oi["unit_cost"] = pd.to_numeric(oi["unit_cost"], errors="coerce").fillna(0)
    cogs = float((oi["quantity"] * oi["unit_cost"]).sum())

    entry_id2 = next_id("ledger_entries", "entry_id", 1)
    append_table("ledger_entries", pd.DataFrame([{
        "entry_id": entry_id2, "entry_ts": now, "order_id": order_id,
        "entry_type": "COGS", "amount": cogs, "note": "Costo estimado"
    }]))

# ====== SCM ======
def scm_apply_sale(order_id):
    orders = read_table("orders")
    items  = read_table("order_items")
    inv    = read_table("inventory")
    prod   = read_table("products")
    supp   = read_table("suppliers")

    orders["order_id"] = pd.to_numeric(orders["order_id"], errors="coerce")
    orow = orders[orders["order_id"] == int(order_id)]
    branch_id = int(orow["branch_id"].iloc[0])

    items["order_id"] = pd.to_numeric(items["order_id"], errors="coerce")
    oitems = items[items["order_id"] == int(order_id)]
    if oitems.empty:
        return

    inv["branch_id"] = pd.to_numeric(inv["branch_id"], errors="coerce").fillna(0).astype(int)
    inv["product_id"] = pd.to_numeric(inv["product_id"], errors="coerce").fillna(0).astype(int)
    inv["stock_on_hand"] = pd.to_numeric(inv["stock_on_hand"], errors="coerce").fillna(0).astype(int)
    inv["stock_min"] = pd.to_numeric(inv["stock_min"], errors="coerce").fillna(0).astype(int)
    inv["reorder_qty"] = pd.to_numeric(inv["reorder_qty"], errors="coerce").fillna(0).astype(int)

    now = datetime.utcnow().isoformat()

    for _, it in oitems.iterrows():
        pid = int(it["product_id"])
        qty = int(it["quantity"])

        mask = (inv["branch_id"] == branch_id) & (inv["product_id"] == pid)
        if not mask.any():
            continue

        inv.loc[mask, "stock_on_hand"] -= qty

        stock = int(inv.loc[mask, "stock_on_hand"].iloc[0])
        smin  = int(inv.loc[mask, "stock_min"].iloc[0])
        rq    = int(inv.loc[mask, "reorder_qty"].iloc[0])

        # si bajo mínimo => orden de compra
        if stock < smin:
            prow = prod[prod["product_id"] == pid].iloc[0]
            supplier_id = int(prow["supplier_id"])
            unit_cost = float(prow["unit_cost"])

            lead = int(supp[supp["supplier_id"] == supplier_id]["lead_time_days"].iloc[0])
            expected = (datetime.utcnow().date()).isoformat()

            po_id = next_id("purchase_orders", "po_id", 1)
            append_table("purchase_orders", pd.DataFrame([{
                "po_id": po_id, "po_ts": now, "supplier_id": supplier_id,
                "branch_id": branch_id, "status": "CREATED", "expected_date": expected
            }]))

            poi_id = next_id("purchase_order_items", "po_item_id", 1)
            append_table("purchase_order_items", pd.DataFrame([{
                "po_item_id": poi_id, "po_id": po_id, "product_id": pid,
                "qty_ordered": rq, "unit_cost_est": unit_cost
            }]))

    write_table("inventory", inv)

# ====== TPS ======
def tps_create_order(customer_id, branch_id, payment_method):
    oid = next_id("orders", "order_id", 1)
    now = datetime.utcnow().isoformat()
    append_table("orders", pd.DataFrame([{
        "order_id": oid, "customer_id": customer_id, "branch_id": branch_id,
        "order_ts": now, "status": "OPEN", "payment_method": payment_method,
        "total_amount": 0.0, "is_synthetic": 0
    }]))
    return oid

def tps_add_item(order_id, product_id, qty):
    prod = read_table("products")
    p = prod[prod["product_id"] == product_id].iloc[0]
    price = float(p["sale_price"])
    lt = price * qty

    item_id = next_id("order_items", "order_item_id", 1)
    append_table("order_items", pd.DataFrame([{
        "order_item_id": item_id, "order_id": order_id, "product_id": product_id,
        "quantity": qty, "unit_price": price, "line_total": lt
    }]))

    orders = read_table("orders")
    items = read_table("order_items")
    total = items[items["order_id"] == order_id]["line_total"].sum()
    orders.loc[orders["order_id"] == order_id, "total_amount"] = total
    write_table("orders", orders)

def tps_checkout(order_id):
    orders = read_table("orders")
    orders.loc[orders["order_id"] == order_id, "status"] = "PAID"
    write_table("orders", orders)

    # integración automática
    erp_record_sale(order_id)
    scm_apply_sale(order_id)


# ====== UI ======
st.title("🧾 TPS Restaurante (Demo)")

customers = read_table("customers")
products  = read_table("products")
branches  = read_table("branches")

st.subheader("👤 Crear nuevo cliente")

new_name = st.text_input("Nombre del nuevo cliente (ej: Juan Perez)")
if st.button("➕ Guardar cliente"):
    new_name = new_name.strip()
    if len(new_name) < 3:
        st.warning("Escribe un nombre válido (mínimo 3 caracteres).")
    else:
        customers = read_table("customers")  # refresca
        if (customers["customer_name"].astype(str).str.lower() == new_name.lower()).any():
            st.warning("Ese cliente ya existe.")
        else:
            new_id = next_id("customers", "customer_id", 1)
            append_table("customers", pd.DataFrame([{
                "customer_id": new_id,
                "customer_name": new_name,
                "created_at": datetime.utcnow().isoformat()
            }]))
            st.success(f"✅ Cliente creado con ID {new_id}.")
            st.rerun()








if customers.empty:
    st.error("No existe customers.csv. Corre primero: py -m src.run_demo")
    st.stop()

cust_opt = {f'{r.customer_id} - {r.customer_name}': int(r.customer_id) for _, r in customers.iterrows()}
prod_opt = {f'{r.product_id} - {r.food_item} ({r.category}) ${r.sale_price}': int(r.product_id) for _, r in products.iterrows()}
branch_opt = {f'{r.branch_id} - {r.branch_name}': int(r.branch_id) for _, r in branches.iterrows()}

if "order_id" not in st.session_state:
    st.session_state.order_id = None

col1, col2, col3 = st.columns(3)
with col1:
    cust_key = st.selectbox("Cliente", list(cust_opt.keys()))
with col2:
    br_key = st.selectbox("Sucursal", list(branch_opt.keys()))
with col3:
    pay = st.selectbox("Pago", ["Cash","Card","Transfer"])

if st.button("➕ Nuevo pedido"):
    st.session_state.order_id = tps_create_order(cust_opt[cust_key], branch_opt[br_key], pay)
    st.success(f"Pedido creado: #{st.session_state.order_id}")

st.subheader("🛒 Carrito")
if st.session_state.order_id is None:
    st.info("Crea un pedido para empezar.")
else:
    pkey = st.selectbox("Producto", list(prod_opt.keys()))
    qty = st.number_input("Cantidad", min_value=1, max_value=20, value=1)

    if st.button("Agregar item"):
        tps_add_item(st.session_state.order_id, prod_opt[pkey], int(qty))
        st.success("Item agregado.")

    items = read_table("order_items")
    prod = read_table("products")
    cart = items[items["order_id"] == st.session_state.order_id].merge(
        prod[["product_id","food_item","category"]], on="product_id", how="left"
    )
    st.dataframe(cart[["food_item","category","quantity","unit_price","line_total"]])

    if st.button("💳 Checkout (pagar)"):
        tps_checkout(st.session_state.order_id)
        st.success("✅ Checkout completado. Se actualizó ERP y SCM automáticamente.")

st.subheader("📌 Evidencia de integración")
st.write("ERP (últimos 10 asientos):")
st.dataframe(read_table("ledger_entries").tail(10))

st.write("SCM (últimas 10 órdenes de compra):")
st.dataframe(read_table("purchase_orders").tail(10))

st.write("Inventario (top 10 menor stock):")

inv = read_table("inventory")
prod = read_table("products")

inv["stock_on_hand"] = pd.to_numeric(inv["stock_on_hand"], errors="coerce").fillna(0)

# ✅ Traer nombre del producto y categoría
inv_view = inv.merge(
    prod[["product_id", "food_item", "category", "sale_price"]],
    on="product_id",
    how="left"
)

inv_view = inv_view.sort_values("stock_on_hand").head(10)

# Orden bonito de columnas
inv_view = inv_view[[
    "branch_id", "product_id", "food_item", "category",
    "stock_on_hand", "stock_min", "reorder_qty", "sale_price"
]]

st.dataframe(inv_view)


