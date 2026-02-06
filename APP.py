
import os
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from datetime import timedelta 

TABLE_DIR = "tables_csv"

def read_table(name):
    path = f"{TABLE_DIR}/{name}.csv"
    return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()

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

    orders["order_id"] = pd.to_numeric(orders["order_id"], errors="coerce")
    orow = orders[orders["order_id"] == int(order_id)]
    branch_id = int(orow["branch_id"].iloc[0])

    items["order_id"] = pd.to_numeric(items["order_id"], errors="coerce")
    oitems = items[items["order_id"] == int(order_id)]
    if oitems.empty:
        return []

    # normalizar inventario
    inv["branch_id"] = pd.to_numeric(inv["branch_id"], errors="coerce").fillna(0).astype(int)
    inv["product_id"] = pd.to_numeric(inv["product_id"], errors="coerce").fillna(0).astype(int)
    inv["stock_on_hand"] = pd.to_numeric(inv["stock_on_hand"], errors="coerce").fillna(0).astype(int)
    inv["stock_min"] = pd.to_numeric(inv["stock_min"], errors="coerce").fillna(0).astype(int)
    inv["reorder_qty"] = pd.to_numeric(inv["reorder_qty"], errors="coerce").fillna(0).astype(int)

    alertas = []

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

        if stock < smin:
            alertas.append({
                "branch_id": branch_id,
                "product_id": pid,
                "stock_on_hand": stock,
                "stock_min": smin,
                "reorder_qty": rq
            })

    write_table("inventory", inv)
    return alertas



def scm_receive_po(po_id: int):
    po  = read_table("purchase_orders")
    poi = read_table("purchase_order_items")
    inv = read_table("inventory")

    # normalizar ids
    po["po_id"] = pd.to_numeric(po["po_id"], errors="coerce").fillna(0).astype(int)
    poi["po_id"] = pd.to_numeric(poi["po_id"], errors="coerce").fillna(0).astype(int)
    poi["product_id"] = pd.to_numeric(poi["product_id"], errors="coerce").fillna(0).astype(int)
    poi["qty_ordered"] = pd.to_numeric(poi["qty_ordered"], errors="coerce").fillna(0).astype(int)

    inv["branch_id"] = pd.to_numeric(inv["branch_id"], errors="coerce").fillna(0).astype(int)
    inv["product_id"] = pd.to_numeric(inv["product_id"], errors="coerce").fillna(0).astype(int)
    inv["stock_on_hand"] = pd.to_numeric(inv["stock_on_hand"], errors="coerce").fillna(0).astype(int)

    row_po = po[po["po_id"] == int(po_id)]
    if row_po.empty:
        return False, "PO no existe."

    status = str(row_po["status"].iloc[0])
    if status == "RECEIVED":
        return False, "PO ya fue recibida."

    branch_id = int(row_po["branch_id"].iloc[0])

    items = poi[poi["po_id"] == int(po_id)]
    if items.empty:
        return False, "PO no tiene items."

    # aplicar recepción: sumar stock
    for _, it in items.iterrows():
        pid = int(it["product_id"])
        qty = int(it["qty_ordered"])

        mask = (inv["branch_id"] == branch_id) & (inv["product_id"] == pid)
        if mask.any():
            inv.loc[mask, "stock_on_hand"] = inv.loc[mask, "stock_on_hand"] + qty
        else:
            # si no existe la fila, la creamos con mínimos por defecto
            inv = pd.concat([inv, pd.DataFrame([{
                "branch_id": branch_id,
                "product_id": pid,
                "stock_on_hand": qty,
                "stock_min": 10,
                "reorder_qty": 20,
            }])], ignore_index=True)

    # marcar PO como recibida
    po.loc[po["po_id"] == int(po_id), "status"] = "RECEIVED"
    po.loc[po["po_id"] == int(po_id), "received_ts"] = datetime.utcnow().isoformat()

    write_table("inventory", inv)
    write_table("purchase_orders", po)

    return True, "OK"

def scm_create_po_manual(branch_id: int, product_id: int, qty: int, expected_date: str):
    prod = read_table("products")

    prod["product_id"] = pd.to_numeric(prod["product_id"], errors="coerce").fillna(0).astype(int)
    prow = prod[prod["product_id"] == int(product_id)]
    if prow.empty:
        return False, "Producto no existe en products."

    prow = prow.iloc[0]
    supplier_id = int(prow["supplier_id"])
    unit_cost = float(prow["unit_cost"])

    now = datetime.utcnow().isoformat()
    po_id = next_id("purchase_orders", "po_id", 1)

    append_table("purchase_orders", pd.DataFrame([{
        "po_id": po_id,
        "po_ts": now,
        "supplier_id": supplier_id,
        "branch_id": int(branch_id),
        "status": "CREATED",
        "expected_date": expected_date
    }]))

    po_item_id = next_id("purchase_order_items", "po_item_id", 1)
    append_table("purchase_order_items", pd.DataFrame([{
        "po_item_id": po_item_id,
        "po_id": po_id,
        "product_id": int(product_id),
        "qty_ordered": int(qty),
        "unit_cost_est": unit_cost
    }]))

    return True, f"OC creada (po_id={po_id})"





# ====== TPS ======

def tps_create_order(customer_id, branch_id, payment_method):
    oid = next_id("orders", "order_id", 1)
    now = datetime.utcnow().isoformat()
    append_table("orders", pd.DataFrame([{
        "order_id": oid,
        "customer_id": int(customer_id),
        "branch_id": int(branch_id),
        "order_ts": now,
        "status": "OPEN",
        "payment_method": str(payment_method),
        "total_amount": 0.0,
        "is_synthetic": 0
    }]))
    return oid


def tps_checkout(order_id):
    orders = read_table("orders")
    orders["order_id"] = pd.to_numeric(orders["order_id"], errors="coerce")
    orders.loc[orders["order_id"] == int(order_id), "status"] = "PAID"
    write_table("orders", orders)

    erp_record_sale(order_id)

    # 👇 ahora SCM devuelve alertas (no crea compras)
    alertas = scm_apply_sale(order_id)
    return alertas



def tps_add_item(order_id, product_id, qty):
    # 1) saber sucursal del pedido
    orders = read_table("orders")
    orders["order_id"] = pd.to_numeric(orders["order_id"], errors="coerce")
    orow = orders[orders["order_id"] == int(order_id)]
    branch_id = int(orow["branch_id"].iloc[0])

    # 2) validar stock
    inv = read_table("inventory")
    inv["branch_id"] = pd.to_numeric(inv["branch_id"], errors="coerce").fillna(0).astype(int)
    inv["product_id"] = pd.to_numeric(inv["product_id"], errors="coerce").fillna(0).astype(int)
    inv["stock_on_hand"] = pd.to_numeric(inv["stock_on_hand"], errors="coerce").fillna(0).astype(int)

    mask = (inv["branch_id"] == branch_id) & (inv["product_id"] == int(product_id))
    if not mask.any():
        raise ValueError("No existe inventario para ese producto en esa sucursal.")

    stock = int(inv.loc[mask, "stock_on_hand"].iloc[0])
    if stock < int(qty):
        raise ValueError(f"No se pudo realizar la venta: stock insuficiente (quedan {stock}).")

    # 3) agregar item (si hay stock)
    prod = read_table("products")
    p = prod[prod["product_id"] == int(product_id)].iloc[0]
    price = float(p["sale_price"])
    lt = price * int(qty)

    item_id = next_id("order_items", "order_item_id", 1)
    append_table("order_items", pd.DataFrame([{
        "order_item_id": item_id, "order_id": int(order_id), "product_id": int(product_id),
        "quantity": int(qty), "unit_price": price, "line_total": lt
    }]))

    # 4) actualizar total del pedido
    items = read_table("order_items")
    total = items[items["order_id"] == int(order_id)]["line_total"].sum()
    orders.loc[orders["order_id"] == int(order_id), "total_amount"] = total
    write_table("orders", orders)


# ====== UI (AQUÍ VA PRIMERO EL TITLE + TABS) ======
st.title(" Verona Restaurant ")
tab_kpis, tab_rfm, tab_ops,tab_tps = st.tabs([" KPIs", " RFM", "ERP / SCM","TPS"])


customers = read_table("customers")
products  = read_table("products")
if "is_active" in products.columns:
    products["is_active"] = pd.to_numeric(products["is_active"], errors="coerce").fillna(1).astype(int)
    products = products[products["is_active"] == 1]


branches  = read_table("branches")

if customers.empty:
    st.error("No existe customers.csv. Corre primero: py -m src.run_demo")
    st.stop()



# ====== TAB KPIs

with tab_kpis:
    st.subheader("📊 KPIs de Demanda, Menú y Pagos")

    orders = read_table("orders")
    items  = read_table("order_items")
    prod   = read_table("products")

    if orders.empty:
        st.warning("No hay órdenes. Crea una venta en TPS primero.")
        st.stop()

    # --- preparar datos ---
    orders["order_ts"] = pd.to_datetime(orders["order_ts"], errors="coerce")
    orders["total_amount"] = pd.to_numeric(orders["total_amount"], errors="coerce").fillna(0)
    orders["status"] = orders["status"].astype(str)

    paid = orders[orders["status"] == "PAID"].copy()
    if paid.empty:
        st.warning("No hay órdenes pagadas todavía. Haz Checkout en TPS.")
        st.stop()

    paid["order_hour"] = paid["order_ts"].dt.hour
    paid["order_date"] = paid["order_ts"].dt.date.astype(str)

    # --- tarjetas (indicadores rápidos) ---
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Órdenes pagadas", int(paid["order_id"].nunique()))
    col2.metric("Ventas totales", f"${paid['total_amount'].sum():,.2f}")
    col3.metric("Ticket promedio", f"${paid['total_amount'].mean():,.2f}")
    col4.metric("Clientes únicos", int(paid["customer_id"].nunique()))
    col5.metric("Sucursales activas", int(paid["branch_id"].nunique()))

    st.divider()
    # ================== KPIs (CREAR FIGURAS, NO MOSTRAR AÚN) ==================

    # --- KPI 1: pedidos por hora ---
    h = paid.groupby("order_hour")["order_id"].nunique().reindex(range(24), fill_value=0)
    fig1, ax1 = plt.subplots(figsize=(4.5, 3.2))
    ax1.bar(h.index, h.values)
    ax1.set_xticks(range(0, 24, 2))
    ax1.set_xlabel("Hora")
    ax1.set_ylabel("# Pedidos")
    ax1.set_title("Pedidos por hora")

    # --- KPI 2: ingresos por hora ---
    hr = paid.groupby("order_hour")["total_amount"].sum().reindex(range(24), fill_value=0)
    fig2, ax2 = plt.subplots(figsize=(4.5, 3.2))
    ax2.plot(hr.index, hr.values, marker="o")
    ax2.set_xticks(range(0, 24, 2))
    ax2.set_xlabel("Hora")
    ax2.set_ylabel("$ Ingresos")
    ax2.set_title("Ingresos por hora")

    # --- KPI 3 y 4: top productos ---
    items["line_total"] = pd.to_numeric(items["line_total"], errors="coerce").fillna(0)
    items["quantity"]   = pd.to_numeric(items["quantity"], errors="coerce").fillna(0)

    mix = items.merge(prod[["product_id","food_item","category"]], on="product_id", how="left")

    top_qty = mix.groupby("food_item")["quantity"].sum().sort_values(ascending=False).head(10)
    fig3, ax3 = plt.subplots(figsize=(4.5, 3.2))
    ax3.barh(top_qty.index[::-1], top_qty.values[::-1])
    ax3.set_xlabel("Cantidad")
    ax3.set_title("Top 10 por cantidad")

    top_rev = mix.groupby("food_item")["line_total"].sum().sort_values(ascending=False).head(10)
    fig4, ax4 = plt.subplots(figsize=(4.5, 3.2))
    ax4.barh(top_rev.index[::-1], top_rev.values[::-1])
    ax4.set_xlabel("Ingresos ($)")
    ax4.set_title("Top 10 por ingresos")

    # --- KPI 5: por categoría ---
    cat_rev = mix.groupby("category")["line_total"].sum().sort_values(ascending=False)
    fig5, ax5 = plt.subplots(figsize=(4.5, 3.2))
    ax5.bar(cat_rev.index, cat_rev.values)
    ax5.tick_params(axis="x", rotation=30)
    ax5.set_ylabel("Ingresos ($)")
    ax5.set_title("Ingresos por categoría")

    # --- KPI 6: método de pago ---
    if "payment_method" not in paid.columns:
        paid["payment_method"] = "Desconocido"
    paid["payment_method"] = paid["payment_method"].fillna("Desconocido").astype(str)

    pm = paid["payment_method"].value_counts()
    fig6, ax6 = plt.subplots(figsize=(4.5, 3.2))
    ax6.bar(pm.index, pm.values)
    ax6.tick_params(axis="x", rotation=20)
    ax6.set_ylabel("# Órdenes")
    ax6.set_title("Órdenes por método de pago")

    # ================== DASHBOARD 3x2 (MOSTRAR AQUÍ) ==================
    st.subheader(" Dashboard de KPIs")

    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        st.caption("Pedidos por hora")
        st.pyplot(fig1, use_container_width=True)
    with r1c2:
        st.caption("Ingresos por hora")
        st.pyplot(fig2, use_container_width=True)
    with r1c3:
        st.caption("Método de pago")
        st.pyplot(fig6, use_container_width=True)

    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1:
        st.caption("Top productos (cantidad)")
        st.pyplot(fig3, use_container_width=True)
    with r2c2:
        st.caption("Top productos (ingresos)")
        st.pyplot(fig4, use_container_width=True)
    with r2c3:
        st.caption("Ingresos por categoría")
        st.pyplot(fig5, use_container_width=True)

    # (opcional) liberar memoria matplotlib
    plt.close(fig1); plt.close(fig2); plt.close(fig3)
    plt.close(fig4); plt.close(fig5); plt.close(fig6)



with tab_rfm:
    st.subheader(" Segmentación RFM ")

    orders = read_table("orders")
    customers = read_table("customers")

    if orders.empty:
        st.warning("No hay órdenes todavía. Crea ventas en TPS primero.")
        st.stop()
    
    st.markdown("### 📌 Leyenda: Scores RFM y Segmentos")

    with st.expander("Ver cómo se calcula el score (R, F, M) y qué significa cada segmento"):
        st.markdown("""
    **RFM = (R, F, M)** con puntajes típicos de **1 a 5**:

    - **R (Recency)**: qué tan reciente compró  
    - **5 = muy reciente**, **1 = hace mucho**
    - **F (Frequency)**: cuántas compras hizo  
    - **5 = muchas compras**, **1 = pocas**
    - **M (Monetary)**: cuánto dinero gastó  
    - **5 = gastó mucho**, **1 = gastó poco**
    """)

        seg = pd.DataFrame([
            {"Segmento": "Campeones", "Regla (ejemplo)": "R≥4 y F≥4 y M≥4", "Interpretación": "Clientes top: recientes, frecuentes y alto gasto."},
            {"Segmento": "Leales", "Regla (ejemplo)": "F≥4 y R≥3", "Interpretación": "Compran seguido; buena relación."},
            {"Segmento": "Nuevos", "Regla (ejemplo)": "R=5 y F≤2", "Interpretación": "Compraron hace poco; aún no son recurrentes."},
            {"Segmento": "En riesgo", "Regla (ejemplo)": "R≤2 y F≥3", "Interpretación": "Antes compraban, ahora se están yendo."},
            {"Segmento": "Dormidos", "Regla (ejemplo)": "R=1 y F≤2", "Interpretación": "Hace mucho no compran y no eran frecuentes."},
            {"Segmento": "Alto gasto", "Regla (ejemplo)": "M=5 (y F no necesariamente alto)", "Interpretación": "Gastan mucho, aunque quizá no compren tan seguido."},
            {"Segmento": "Sin clasificar (Otros)", "Regla (ejemplo)": "No cae en reglas", "Interpretación": "No cumple criterios específicos definidos arriba."},
        ])

        st.dataframe(seg, use_container_width=True)

    st.caption("Nota: Si ves muchos 'Otros', significa que tus reglas no cubren todos los casos. Puedes renombrar 'Otros' a 'Sin clasificar' o añadir más segmentos.")

    
    
    
    
    
    
    # Solo ventas pagadas
    orders["order_ts"] = pd.to_datetime(orders.get("order_ts"), errors="coerce")
    orders["total_amount"] = pd.to_numeric(orders.get("total_amount"), errors="coerce").fillna(0)
    orders["customer_id"] = pd.to_numeric(orders.get("customer_id"), errors="coerce").fillna(0).astype(int)
    orders["order_id"] = pd.to_numeric(orders.get("order_id"), errors="coerce").fillna(0).astype(int)
    orders["status"] = orders.get("status").astype(str)

    paid = orders[(orders["status"] == "PAID") & orders["order_ts"].notna()].copy()
    if paid.empty:
        st.warning("Aún no hay órdenes pagadas. Haz Checkout en TPS.")
        st.stop()

    # Fecha de referencia (snapshot) -> para recency
    snapshot = paid["order_ts"].max() + pd.Timedelta(days=1)

    rfm = (
        paid.groupby("customer_id")
        .agg(
            recency_days=("order_ts", lambda x: int((snapshot - x.max()).days)),
            frequency=("order_id", "nunique"),
            monetary=("total_amount", "sum"),
        )
        .reset_index()
    )

    # Join con nombres de clientes (si existe)
    if not customers.empty and "customer_id" in customers.columns:
        customers["customer_id"] = pd.to_numeric(customers["customer_id"], errors="coerce").fillna(0).astype(int)
        if "customer_name" in customers.columns:
            rfm = rfm.merge(customers[["customer_id", "customer_name"]], on="customer_id", how="left")
        else:
            rfm["customer_name"] = None
    else:
        rfm["customer_name"] = None

    # --- Scoring robusto (qcut a veces falla con pocos datos) ---
    def qscore(series: pd.Series, bins: int = 5, reverse: bool = False) -> pd.Series:
        s = pd.to_numeric(series, errors="coerce").fillna(0)
        # rank para evitar empates exactos en qcut
        r = s.rank(method="first")

        b = min(bins, int(r.nunique())) if int(r.nunique()) > 0 else 1
        if b == 1:
            score = pd.Series([1] * len(r), index=r.index)
        else:
            try:
                score = pd.qcut(r, q=b, labels=list(range(1, b + 1)))
                score = score.astype(int)
            except Exception:
                # fallback simple si qcut se pone pesado
                score = pd.Series(pd.cut(r, bins=b, labels=list(range(1, b + 1)), include_lowest=True)).astype(int)

        if reverse:
            score = (b + 1) - score  # recency: menor recency => mejor score
        return score

    r_bins = 5
    f_bins = 5
    m_bins = 5

    rfm["R"] = qscore(rfm["recency_days"], bins=r_bins, reverse=True)
    rfm["F"] = qscore(rfm["frequency"], bins=f_bins, reverse=False)
    rfm["M"] = qscore(rfm["monetary"], bins=m_bins, reverse=False)

    rfm["RFM"] = rfm["R"].astype(str) + rfm["F"].astype(str) + rfm["M"].astype(str)
    rfm["rfm_score_total"] = rfm["R"] + rfm["F"] + rfm["M"]

    # Segmentos simples (claros para el profe)
    def segment(row):
        R, F, M = int(row["R"]), int(row["F"]), int(row["M"])
        if R >= 4 and F >= 4 and M >= 4:
            return "Campeones"
        if R >= 4 and F >= 3:
            return "Leales"
        if R >= 4 and F <= 2:
            return "Nuevos"
        if R <= 2 and F >= 3:
            return "En riesgo"
        if R <= 2 and F <= 2:
            return "Dormidos"
        if M >= 4 and R >= 3:
            return "Alto gasto"
        return "Otros"

    rfm["segmento"] = rfm.apply(segment, axis=1)

    # Orden bonito
    cols = ["customer_id", "customer_name", "recency_days", "frequency", "monetary", "segmento", "R", "F", "M", "RFM", "rfm_score_total"]
    rfm = rfm[cols].sort_values(["segmento", "rfm_score_total"], ascending=[True, False]).reset_index(drop=True)

    # Guardar CSV en tables_csv
    write_table("rfm_customers", rfm)

    # ====== UI ======
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Clientes (RFM)", int(rfm["customer_id"].nunique()))
    c2.metric("Ventas pagadas", int(paid["order_id"].nunique()))
    c3.metric("Ingreso total", f"${paid['total_amount'].sum():,.2f}")
    c4.metric("Ticket promedio", f"${paid['total_amount'].mean():,.2f}")

    st.write("### 📋 Tabla RFM (se guarda en tables_csv/rfm_customers.csv)")
    st.dataframe(rfm, use_container_width=True)

    st.download_button(
        "⬇️ Descargar RFM CSV",
        data=rfm.to_csv(index=False).encode("utf-8"),
        file_name="rfm_customers.csv",
        mime="text/csv",
    )

    st.divider()

    # ====== Gráficas (DASHBOARD en 3 columnas) ======
    st.write("###  Dashboard RFM")

    colA, colB, colC = st.columns(3)

    # 1) Clientes por segmento
    with colA:
        st.caption("Clientes por segmento")
        seg_counts = rfm["segmento"].value_counts()
        fig1, ax1 = plt.subplots()
        ax1.bar(seg_counts.index, seg_counts.values)
        ax1.set_ylabel("# Clientes")
        ax1.tick_params(axis="x", rotation=30)
        ax1.set_title("Segmentos")
        st.pyplot(fig1, use_container_width=True)
        plt.close(fig1)

    # 2) Histograma de Recency
    with colB:
        st.caption("Recency (días desde última compra)")
        fig2, ax2 = plt.subplots()
        ax2.hist(rfm["recency_days"], bins=10)
        ax2.set_xlabel("Días")
        ax2.set_ylabel("# Clientes")
        ax2.set_title("Recency")
        st.pyplot(fig2, use_container_width=True)
        plt.close(fig2)

    # 3) Scatter Frequency vs Monetary
    with colC:
        st.caption("Frequency vs Monetary")
        fig3, ax3 = plt.subplots()
        ax3.scatter(rfm["frequency"], rfm["monetary"])
        ax3.set_xlabel("Frequency (# órdenes)")
        ax3.set_ylabel("Monetary ($)")
        ax3.set_title("F vs M")
        st.pyplot(fig3, use_container_width=True)
        plt.close(fig3)





    st.divider()
    st.write("###  Top 10 clientes por Monetary")
    top10 = rfm.sort_values("monetary", ascending=False).head(10)
    st.dataframe(top10[["customer_id", "customer_name", "recency_days", "frequency", "monetary", "segmento"]], use_container_width=True)












# ====== TAB OPS ======
with tab_ops:
    st.subheader("⚙️ Evidencia (ERP / SCM)")

    ledger = read_table("ledger_entries")
    po     = read_table("purchase_orders")
    inv    = read_table("inventory")
    prod   = read_table("products")
    br     = read_table("branches")

    c1, c2, c3 = st.columns(3)
    c1.metric("Asientos ERP", 0 if ledger.empty else len(ledger))
    c2.metric("Órdenes de compra", 0 if po.empty else po["po_id"].nunique())
    if not inv.empty:
        inv["stock_on_hand"] = pd.to_numeric(inv["stock_on_hand"], errors="coerce").fillna(0)
        c3.metric("Items con stock < mínimo", int((inv["stock_on_hand"] < inv["stock_min"]).sum()))
    else:
        c3.metric("Items con stock < mínimo", 0)

    st.write("### ERP: últimos asientos")
    st.dataframe(ledger.tail(10))

    st.write("### SCM: últimas órdenes de compra")
    st.dataframe(po.tail(10))
    
    st.write("### 📥 Recibir Orden de Compra (cargar stock al inventario)")

    po = read_table("purchase_orders")
    poi = read_table("purchase_order_items")

    if po.empty:
        st.info("No hay órdenes de compra todavía.")
    else:
        po["po_id"] = pd.to_numeric(po["po_id"], errors="coerce").fillna(0).astype(int)
        po["status"] = po["status"].astype(str)

        pendientes = po[po["status"] != "RECEIVED"].copy()

        if pendientes.empty:
            st.success("✅ No hay OCs pendientes. Todo recibido.")
        else:
            # selector bonito
            pendientes["label"] = pendientes.apply(
                lambda r: f'PO #{int(r["po_id"])} | Sucursal={int(r["branch_id"])} | Proveedor={int(r["supplier_id"])} | Entrega={r.get("expected_date","")} | Estado={r["status"]}',
                axis=1
            )

            sel = st.selectbox("Selecciona una OC pendiente", pendientes["label"].tolist())
            po_id = int(pendientes[pendientes["label"] == sel]["po_id"].iloc[0])

            # preview items de la OC
            poi["po_id"] = pd.to_numeric(poi["po_id"], errors="coerce").fillna(0).astype(int)
            items_po = poi[poi["po_id"] == po_id].copy()

            if not items_po.empty:
                prod = read_table("products")
                prod["product_id"] = pd.to_numeric(prod["product_id"], errors="coerce").fillna(0).astype(int)
                items_po["product_id"] = pd.to_numeric(items_po["product_id"], errors="coerce").fillna(0).astype(int)

                items_po = items_po.merge(prod[["product_id","food_item","category"]], on="product_id", how="left")
                st.dataframe(items_po[["product_id","food_item","category","qty_ordered","unit_cost_est"]])

            if st.button("✅ Marcar como RECIBIDA y cargar inventario"):
                ok, msg = scm_receive_po(po_id)
                if ok:
                    st.success("📦 Mercancía recibida. Inventario actualizado.")
                    st.rerun()
                else:
                    st.warning(msg)

    
    

    st.write("### SCM: inventario ")
    if not inv.empty:
        inv_view = inv.merge(prod[["product_id","food_item","category","sale_price"]], on="product_id", how="left")
        if not br.empty:
            inv_view = inv_view.merge(br[["branch_id","branch_name"]], on="branch_id", how="left")
        inv_view = inv_view.sort_values("stock_on_hand").head(10)

        cols = ["branch_id"]
        if "branch_name" in inv_view.columns: cols = ["branch_name"]
        cols += ["product_id","food_item","category","stock_on_hand","stock_min","reorder_qty","sale_price"]

        st.dataframe(inv_view[cols])
        st.write("###  Ajustar inventario (manual)")

    with st.expander("Abrir editor de inventario"):
        # opciones
        branch_opt = {f'{r.branch_id} - {r.branch_name}': int(r.branch_id) for _, r in br.iterrows()}
        prod_opt2  = {f'{r.product_id} - {r.food_item} ({r.category})': int(r.product_id) for _, r in prod.iterrows()}

        bkey = st.selectbox("Sucursal (inventario)", list(branch_opt.keys()))
        pkey = st.selectbox("Producto (inventario)", list(prod_opt2.keys()))

        branch_id = branch_opt[bkey]
        product_id = prod_opt2[pkey]

        # buscar fila actual
        mask = (inv["branch_id"] == branch_id) & (inv["product_id"] == product_id)
        if mask.any():
            current = inv.loc[mask].iloc[0]
            cur_stock_raw = int(current["stock_on_hand"])
            cur_min_raw   = int(current["stock_min"])
            cur_rq_raw    = int(current["reorder_qty"])

            # ✅ evitar que el number_input explote
            cur_stock = max(0, cur_stock_raw)
            cur_min   = max(0, cur_min_raw)
            cur_rq    = max(0, cur_rq_raw)

            if cur_stock_raw < 0:
                st.warning(f"⚠️ Inventario estaba en negativo ({cur_stock_raw}). Se mostrará como 0 para editar.")
        else:
            cur_stock, cur_min, cur_rq = 50, 10, 20


        new_stock = st.number_input("Stock actual", min_value=0, max_value=100000, value=cur_stock)
        new_min   = st.number_input("Stock mínimo", min_value=0, max_value=100000, value=cur_min)
        new_rq    = st.number_input("Reorder qty", min_value=0, max_value=100000, value=cur_rq)

        if st.button("💾 Guardar ajuste de inventario"):
            if mask.any():
                inv.loc[mask, "stock_on_hand"] = int(new_stock)
                inv.loc[mask, "stock_min"] = int(new_min)
                inv.loc[mask, "reorder_qty"] = int(new_rq)
            else:
                inv = pd.concat([inv, pd.DataFrame([{
                    "branch_id": int(branch_id),
                    "product_id": int(product_id),
                    "stock_on_hand": int(new_stock),
                    "stock_min": int(new_min),
                    "reorder_qty": int(new_rq),
                }])], ignore_index=True)

            write_table("inventory", inv)
            st.success("✅ Inventario actualizado.")
            st.rerun()
            
    st.subheader("🧾 Reabastecimiento manual (SCM)")

    inv = read_table("inventory")
    prod = read_table("products")
    br   = read_table("branches")

    if not inv.empty:
        inv["stock_on_hand"] = pd.to_numeric(inv["stock_on_hand"], errors="coerce").fillna(0).astype(int)
        inv["stock_min"] = pd.to_numeric(inv["stock_min"], errors="coerce").fillna(0).astype(int)

        crit = inv[inv["stock_on_hand"] < inv["stock_min"]].copy()

        if not crit.empty:
            crit_view = crit.merge(prod[["product_id","food_item","category","supplier_id"]], on="product_id", how="left")
            crit_view = crit_view.merge(br[["branch_id","branch_name"]], on="branch_id", how="left")
            st.warning(f"⚠️ Hay {len(crit_view)} item(s) bajo mínimo.")
            st.dataframe(crit_view[["branch_name","product_id","food_item","category","stock_on_hand","stock_min","reorder_qty"]])
        else:
            st.success("✅ No hay items bajo mínimo.")

        with st.expander("➕ Crear Orden de Compra (manual)"):
            # opciones solo desde críticos (si hay)
            base_df = crit if not crit.empty else inv

            # nombres bonitos
            inv_opt = base_df.merge(prod[["product_id","food_item","category"]], on="product_id", how="left") \
                            .merge(br[["branch_id","branch_name"]], on="branch_id", how="left")

            inv_opt["label"] = inv_opt.apply(
                lambda r: f'{r["branch_name"]} | {int(r["product_id"])} - {r["food_item"]} ({r["category"]}) | stock={int(r["stock_on_hand"])} min={int(r["stock_min"])}',
                axis=1
            )
            choice = st.selectbox("Elegir producto bajo mínimo", inv_opt["label"].tolist())
            row = inv_opt[inv_opt["label"] == choice].iloc[0]

            branch_id = int(row["branch_id"])
            product_id = int(row["product_id"])
            sug_qty = int(row.get("reorder_qty", 20))

            qty = st.number_input("Cantidad a pedir", min_value=1, max_value=100000, value=max(1, sug_qty))
            entrega = st.date_input("Fecha de entrega (expected_date)")

            if st.button(" Crear OC"):
                ok, msg = scm_create_po_manual(branch_id, product_id, int(qty), entrega.isoformat())
                if ok:
                    st.success("✅ " + msg)
                    st.rerun()
                else:
                    st.error("❌ " + msg)
    else:
        st.info("No hay inventario todavía.")
        
    st.subheader("🧩 Catálogo de productos (alta / baja)")

    products = read_table("products")
    suppliers = read_table("suppliers")
    branches = read_table("branches")
    inv = read_table("inventory")

    # Asegurar columna is_active
    if not products.empty and "is_active" not in products.columns:
        products["is_active"] = 1
        write_table("products", products)

    # Normalizar por si acaso
    if not products.empty:
        products["product_id"] = pd.to_numeric(products["product_id"], errors="coerce").fillna(0).astype(int)
        if "is_active" in products.columns:
            products["is_active"] = pd.to_numeric(products["is_active"], errors="coerce").fillna(1).astype(int)

    # ====== ALTA PRODUCTO ======
    with st.expander("➕ Añadir producto"):
        with st.form("form_add_product", clear_on_submit=True):
            food_item = st.text_input("Nombre del producto (food_item)", placeholder="Ej: Pizza Margarita")
            # Puedes usar categorías existentes o escribir nueva
            cats = []
            if not products.empty and "category" in products.columns:
                cats = sorted(products["category"].dropna().astype(str).unique().tolist())
            category = st.selectbox("Categoría", cats + ["(Nueva...)"]) if cats else st.selectbox("Categoría", ["(Nueva...)"])
            if category == "(Nueva...)":
                category = st.text_input("Nueva categoría", placeholder="Ej: Main")

            sale_price = st.number_input("Precio de venta (sale_price)", min_value=0.0, value=10.0, step=0.5)
            unit_cost  = st.number_input("Costo unitario (unit_cost)", min_value=0.0, value=6.0, step=0.5)

            # Proveedor
            supplier_id = None
            if suppliers.empty:
                st.info("No hay suppliers.csv (proveedores). Puedes agregarlo luego o dejar supplier_id=1.")
                supplier_id = st.number_input("supplier_id", min_value=1, value=1, step=1)
            else:
                suppliers["supplier_id"] = pd.to_numeric(suppliers["supplier_id"], errors="coerce").fillna(0).astype(int)
                sup_opt = {f'{r.supplier_id} - {r.supplier_name}': int(r.supplier_id) for _, r in suppliers.iterrows()}
                sup_key = st.selectbox("Proveedor", list(sup_opt.keys()))
                supplier_id = sup_opt[sup_key]

            # Inventario inicial (aplicado a TODAS las sucursales)
            init_stock = st.number_input("Stock inicial (todas las sucursales)", min_value=0, value=0, step=1)
            stock_min  = st.number_input("Stock mínimo (todas las sucursales)", min_value=0, value=10, step=1)
            reorder_q  = st.number_input("Reorder qty sugerido", min_value=0, value=20, step=1)

            submit = st.form_submit_button("✅ Crear producto")

        if submit:
            food_item = (food_item or "").strip()
            category  = (category or "").strip()

            if len(food_item) < 2 or len(category) < 2:
                st.error("Nombre y categoría deben tener al menos 2 caracteres.")
            else:
                # evitar duplicados por nombre+categoría (opcional)
                if not products.empty:
                    dup = products[
                        (products["food_item"].astype(str).str.lower() == food_item.lower()) &
                        (products["category"].astype(str).str.lower() == category.lower()) &
                        (products.get("is_active", 1).fillna(1).astype(int) == 1)
                    ]
                    if not dup.empty:
                        st.error("Ese producto ya existe (mismo nombre y categoría).")
                    else:
                        new_id = next_id("products", "product_id", 1001)

                        new_row = pd.DataFrame([{
                            "product_id": int(new_id),
                            "food_item": food_item,
                            "category": category,
                            "sale_price": float(sale_price),
                            "unit_cost": float(unit_cost),
                            "supplier_id": int(supplier_id),
                            "is_active": 1
                        }])

                        append_table("products", new_row)

                        # crear inventario para cada sucursal si no existe
                        inv = read_table("inventory")
                        if inv.empty:
                            inv = pd.DataFrame(columns=["branch_id","product_id","stock_on_hand","stock_min","reorder_qty"])

                        inv["branch_id"] = pd.to_numeric(inv["branch_id"], errors="coerce").fillna(0).astype(int)
                        inv["product_id"] = pd.to_numeric(inv["product_id"], errors="coerce").fillna(0).astype(int)

                        if not branches.empty:
                            branches["branch_id"] = pd.to_numeric(branches["branch_id"], errors="coerce").fillna(0).astype(int)
                            new_inv_rows = []
                            for b in branches["branch_id"].tolist():
                                mask = (inv["branch_id"] == int(b)) & (inv["product_id"] == int(new_id))
                                if not mask.any():
                                    new_inv_rows.append({
                                        "branch_id": int(b),
                                        "product_id": int(new_id),
                                        "stock_on_hand": int(init_stock),
                                        "stock_min": int(stock_min),
                                        "reorder_qty": int(reorder_q),
                                    })
                            if new_inv_rows:
                                inv = pd.concat([inv, pd.DataFrame(new_inv_rows)], ignore_index=True)
                                write_table("inventory", inv)

                        st.success(f"✅ Producto creado con ID {new_id}.")
                        st.rerun()

    # ====== BAJA (DESACTIVAR) PRODUCTO ======
    with st.expander("🛑 Desactivar producto "):
        products = read_table("products")
        if products.empty:
            st.info("No hay productos todavía.")
        else:
            if "is_active" not in products.columns:
                products["is_active"] = 1
                write_table("products", products)

            products["product_id"] = pd.to_numeric(products["product_id"], errors="coerce").fillna(0).astype(int)
            products["is_active"] = pd.to_numeric(products["is_active"], errors="coerce").fillna(1).astype(int)

            active = products[products["is_active"] == 1].copy()
            if active.empty:
                st.info("No hay productos activos para desactivar.")
            else:
                active["label"] = active.apply(lambda r: f'{int(r["product_id"])} - {r["food_item"]} ({r["category"]})', axis=1)
                pick = st.selectbox("Producto activo", active["label"].tolist())
                pid = int(active[active["label"] == pick]["product_id"].iloc[0])

                if st.button("🚫 Desactivar"):
                    products.loc[products["product_id"] == pid, "is_active"] = 0
                    write_table("products", products)
                    st.success("✅ Producto desactivado. Ya no aparecerá en el TPS.")
                    st.rerun()
                    
    with st.expander("✅ Reactivar producto"):
        products = read_table("products")
        if products.empty:
            st.info("No hay productos.")
        else:
            if "is_active" not in products.columns:
                products["is_active"] = 1
                write_table("products", products)

            products["product_id"] = pd.to_numeric(products["product_id"], errors="coerce").fillna(0).astype(int)
            products["is_active"] = pd.to_numeric(products["is_active"], errors="coerce").fillna(1).astype(int)

            inactive = products[products["is_active"] == 0].copy()
            if inactive.empty:
                st.info("No hay productos desactivados.")
            else:
                inactive["label"] = inactive.apply(
                    lambda r: f'{int(r["product_id"])} - {r["food_item"]} ({r["category"]})',
                    axis=1
                )
                pick = st.selectbox("Producto desactivado", inactive["label"].tolist())
                pid = int(inactive[inactive["label"] == pick]["product_id"].iloc[0])

                if st.button("♻️ Reactivar"):
                    products.loc[products["product_id"] == pid, "is_active"] = 1
                    write_table("products", products)
                    st.success("✅ Producto reactivado. Ya aparece en el TPS.")
                    st.rerun()


# ====== TAB TPS ======
with tab_tps:
    st.subheader("👤 Crear nuevo cliente")

    new_name = st.text_input("Nombre del nuevo cliente (ej: Juan Perez)")
    if st.button("➕ Guardar cliente"):
        new_name = new_name.strip()
        if len(new_name) < 3:
            st.warning("Escribe un nombre válido (mínimo 3 caracteres).")
        else:
            customers2 = read_table("customers")
            if (customers2["customer_name"].astype(str).str.lower() == new_name.lower()).any():
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

    # TPS UI
    
    customers = read_table("customers")
    products  = read_table("products")
    if "is_active" in products.columns:
        products["is_active"] = pd.to_numeric(products["is_active"], errors="coerce").fillna(1).astype(int)
        products = products[products["is_active"] == 1]
    branches  = read_table("branches")

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
        qty = st.number_input("Cantidad", min_value=1, max_value=50, value=1)

        if st.button("Agregar item"):
            try:
                tps_add_item(st.session_state.order_id, prod_opt[pkey], int(qty))
                st.success("✅ Item agregado.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))



        items = read_table("order_items")
        prod = read_table("products")
        cart = items[items["order_id"] == st.session_state.order_id].merge(
            prod[["product_id","food_item","category"]], on="product_id", how="left"
        )
        st.dataframe(cart[["food_item","category","quantity","unit_price","line_total"]])

        if st.button("💳 Checkout (pagar)"):
            alertas = tps_checkout(st.session_state.order_id)
            st.success("✅ Checkout completado. ERP actualizado y stock descontado.")

            if alertas:
                st.session_state["alertas_reabastecer"] = alertas
                st.warning("⚠️ Stock bajo mínimo. Debes abastecerte (crear Orden de Compra).")
            else:
                st.session_state["alertas_reabastecer"] = []

            
    
            



