import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO # Necesario para manejar el archivo en memoria

# 1. CONFIGURACIÓN E INTERFAZ
st.set_page_config(page_title="Sistema de Proyecciones", layout="wide")

# --- CONEXIÓN A BASE DE DATOS ---
def conectar_db():
    conn = sqlite3.connect('proyecciones.db')
    return conn

# --- FUNCIÓN PARA GENERAR EL EXCEL ---
def generar_excel(df):
    output = BytesIO()
    # Usamos XlsxWriter como motor para crear el archivo
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Proyecciones')
    return output.getvalue()

# Crear tabla si no existe
conn = conectar_db()
conn.execute('''CREATE TABLE IF NOT EXISTS ventas 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              vendedor TEXT, cliente TEXT, sector TEXT, 
              producto TEXT, cantidad REAL, precio_u REAL, 
              total_s REAL, total_kg REAL, mes TEXT)''')
conn.close()

# --- DATOS MAESTROS ---
DATA_MAESTRA = {
    "MARIA_AVILA": {
        "DELOSI S.A": {"sector": "Alimentos y Bebidas", "productos": ["KIT FOOD 6", "NEOCLOR DX PLUS"]},
        "ADMINISTRADORA CENTRAL": {"sector": "Industrial", "productos": ["NEOCLOR DX", "ANTIBAC LAC"]}
    }
}

INFO_PRODUCTOS = {
    "KIT FOOD 6": {"peso": 1.2, "precio": 15.50},
    "NEOCLOR DX PLUS": {"peso": 23.404, "precio": 145.00},
    "NEOCLOR DX": {"peso": 0.08, "precio": 12.00},
    "ANTIBAC LAC": {"peso": 0.05, "precio": 8.50}
}

if "items_temporales" not in st.session_state:
    st.session_state.items_temporales = []

# --- VENTANA FLOTANTE (NUEVO) ---
@st.dialog("Registro de Proyección de Ventas", width="large")
def formulario_nuevo():
    vendedor = st.session_state.usuario_logueado
    clientes = list(DATA_MAESTRA.get(vendedor, {}).keys())
    
    col1, col2 = st.columns(2)
    with col1:
        cliente_sel = st.selectbox("Cliente:", clientes)
        sector = DATA_MAESTRA[vendedor][cliente_sel]["sector"]
        st.text_input("Sector:", value=sector, disabled=True)
    with col2:
        oportunidad = st.text_input("Oportunidad:")
        mes_cierre = st.selectbox("Mes de Cierre:", ["Enero", "Febrero", "Marzo", "Abril"])

    st.divider()
    prods = DATA_MAESTRA[vendedor][cliente_sel]["productos"]
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1: prod_f = st.selectbox("Producto:", prods)
    with c2: cant_f = st.number_input("Cantidad:", min_value=1.0, step=1.0)
    
    info = INFO_PRODUCTOS[prod_f]
    t_kg = cant_f * info["peso"]
    t_s = cant_f * info["precio"]
    
    with c3: st.metric("Kilos", f"{t_kg:.2f}")
    with c4: st.metric("Soles", f"S/ {t_s:.2f}")

    if st.button("➕ Agregar a la lista"):
        st.session_state.items_temporales.append({
            "vendedor": vendedor, "cliente": cliente_sel, "sector": sector,
            "producto": prod_f, "cantidad": cant_f, "precio_u": info["precio"],
            "total_s": t_s, "total_kg": t_kg, "mes": mes_cierre
        })

    if st.session_state.items_temporales:
        df_temp = pd.DataFrame(st.session_state.items_temporales)
        st.table(df_temp[["producto", "cantidad", "total_s", "total_kg"]])
        
        if st.button("💾 GUARDAR TODO EN SISTEMA"):
            conn = conectar_db()
            for item in st.session_state.items_temporales:
                conn.execute('''INSERT INTO ventas (vendedor, cliente, sector, producto, cantidad, precio_u, total_s, total_kg, mes) 
                             VALUES (?,?,?,?,?,?,?,?,?)''', 
                             (item['vendedor'], item['cliente'], item['sector'], item['producto'], 
                              item['cantidad'], item['precio_u'], item['total_s'], item['total_kg'], item['mes']))
            conn.commit()
            conn.close()
            st.session_state.items_temporales = []
            st.success("✅ Registro Guardado Exitosamente")
            st.rerun()

# --- PANTALLA PRINCIPAL ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado = True
            st.session_state.usuario_logueado = u
            st.rerun()
else:
    col_btns = st.columns([1, 1, 8])
    with col_btns[0]:
        if st.button("📄 Nuevo"): formulario_nuevo()
    with col_btns[1]:
        if st.button("🚪 Salir"): 
            st.session_state.autenticado = False
            st.rerun()

    st.divider()
    mes_consulta = st.selectbox("Mes a consultar:", ["-- Seleccione --", "Enero", "Febrero", "Marzo"])

    if mes_consulta != "-- Seleccione --":
        # LEER DE LA BASE DE DATOS REAL
        conn = conectar_db()
        query = f"SELECT cliente, producto, sector, cantidad, total_s as 'Monto Soles', total_kg as 'Kg' FROM ventas WHERE mes='{mes_consulta}' AND vendedor='{st.session_state.usuario_logueado}'"
        df_fondo = pd.read_sql_query(query, conn)
        conn.close()

        if not df_fondo.empty:
            st.write(f"### Detalle de Proyección - {mes_consulta}")
            st.dataframe(df_fondo, use_container_width=True)
            
            c1, c2, c3 = st.columns([1, 1, 1])
            c1.metric("Total Soles", f"S/ {df_fondo['Monto Soles'].sum():,.2f}")
            c2.metric("Total Kg", f"{df_fondo['Kg'].sum():,.2f}")
            
            # --- BOTÓN DE EXCEL AQUÍ ---
            with c3:
                st.write("") # Espaciado
                data_excel = generar_excel(df_fondo)
                st.download_button(
                    label="📊 Descargar Excel",
                    data=data_excel,
                    file_name=f"Proyección_{mes_consulta}_{st.session_state.usuario_logueado}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.warning(f"No hay datos reales guardados para {mes_consulta}.")