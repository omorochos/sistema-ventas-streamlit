import streamlit as st
import pandas as pd
from supabase import create_client, Client
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Proyecciones PRO", layout="wide")

# --- CONEXIÓN A SUPABASE ---
# Verifica que en Streamlit Cloud no existan errores de formato en los Secrets
URL: str = st.secrets["SUPABASE_URL"]
KEY: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

# --- DATOS MAESTROS ---
DATA_MAESTRA = {
    "DELOSI S.A": ["KIT FOOD 6", "NEOCLOR DX PLUS"],
    "CINEPLANET": ["LIMPIADOR MULTIUSOS", "DESINFECTANTE"],
    "SAGA FALABELLA": ["PRODUCTO A", "PRODUCTO B"]
}

INFO_PRODUCTOS = {
    "KIT FOOD 6": {"sector": "Alimentos y Bebidas", "precio": 15.5, "peso": 1.2},
    "NEOCLOR DX PLUS": {"sector": "Alimentos y Bebidas", "precio": 145.0, "peso": 23.404},
    "LIMPIADOR MULTIUSOS": {"sector": "Limpieza", "precio": 10.0, "peso": 5.0},
    "DESINFECTANTE": {"sector": "Limpieza", "precio": 12.0, "peso": 1.0},
    "PRODUCTO A": {"sector": "Retail", "precio": 20.0, "peso": 0.5},
    "PRODUCTO B": {"Retail": "Retail", "precio": 25.0, "peso": 1.0}
}

# --- FUNCIÓN EXCEL ---
def generar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Proyecciones')
    return output.getvalue()

# --- VENTANAS EMERGENTES (DIALOGS) ---
@st.dialog("Registro de Proyección", width="large")
def formulario_nuevo():
    if "carrito_proyeccion" not in st.session_state:
        st.session_state.carrito_proyeccion = []

    vendedor_actual = st.session_state.usuario_logueado
    
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
            cliente_sel = st.selectbox("Cliente", list(DATA_MAESTRA.keys()))
        with c2:
            prod_sel = st.selectbox("Producto", DATA_MAESTRA[cliente_sel])
            cant_sel = st.number_input("Cantidad", min_value=1, step=1)
        with c3:
            st.write("###")
            if st.button("➕ Añadir"):
                info = INFO_PRODUCTOS[prod_sel]
                st.session_state.carrito_proyeccion.append({
                    "vendedor": vendedor_actual, 
                    "mes": mes_sel, 
                    "cliente": cliente_sel,
                    "producto": prod_sel, 
                    "sector": info["sector"],
                    "total_s": float(info["precio"] * cant_sel),
                    "total_kg": float(info["peso"] * cant_sel)
                })

    if st.session_state.carrito_proyeccion:
        st.dataframe(pd.DataFrame(st.session_state.carrito_proyeccion), use_container_width=True, hide_index=True)
        if st.button("💾 GUARDAR TODO EN SUPABASE"):
            supabase.table("ventas").insert(st.session_state.carrito_proyeccion).execute()
            st.session_state.carrito_proyeccion = []
            st.success("¡Datos guardados!")
            st.rerun()

@st.dialog("Actualizar Registro", width="large")
def formulario_actualizar(fila):
    nueva_cant = st.number_input("Nueva cantidad:", min_value=1, step=1)
    if st.button("Confirmar"):
        info = INFO_PRODUCTOS[fila['producto']]
        supabase.table("ventas").update({
            "total_s": float(info["precio"] * nueva_cant),
            "total_kg": float(info["peso"] * nueva_cant)
        }).eq("cliente", fila['cliente']).eq("producto", fila['producto']).execute()
        st.rerun()

# --- LÓGICA DE ACCESO ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("Acceso al Sistema")
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado = True
            st.session_state.usuario_logueado = u
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
else:
    # --- FILTROS ---
    st.sidebar.header("Configuración")
    mes_consulta = st.sidebar.selectbox("Mes:", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    ver_consolidado = st.sidebar.toggle("Ver Consolidado (3 meses anteriores)")

    # --- OBTENCIÓN DE DATOS ---
    try:
        # Consulta base simplificada para evitar errores de sintaxis
        query = supabase.table("ventas").select("*")
        
        # Ejecutamos la consulta y luego filtramos con Pandas para mayor seguridad
        res = query.execute()
        df_raw = pd.DataFrame(res.data)
        
        if not df_raw.empty:
            # Filtramos por vendedor y mes usando Pandas
            df = df_raw[df_raw['vendedor'] == st.session_state.usuario_logueado]
            
            if ver_consolidado:
                meses_orden = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                idx = meses_orden.index(mes_consulta)
                meses_interes = meses_orden[max(0, idx-3):idx+1]
                df = df[df['mes'].isin(meses_interes)]
                df = df.groupby(["cliente", "producto"]).agg({"total_s": "sum", "total_kg": "sum"}).reset_index()
            else:
                df = df[df['mes'] == mes_consulta]

            # Renombrar para vista
            df = df.rename(columns={"total_s": "Monto Soles", "total_kg": "Kg Proyectados"})
            # Asegurar que existan todas las columnas para la tabla
            for col in ["Ventas kg", "Total", "Etapa de Venta"]:
                if col not in df.columns: df[col] = ""
            df["Etapa de Venta"] = "Propuesta Económica"
            df = df[["cliente", "producto", "Monto Soles", "Kg Proyectados", "Ventas kg", "Total", "Etapa de Venta"]]
        else:
            df = pd.DataFrame(columns=["cliente", "producto", "Monto Soles", "Kg Proyectados", "Ventas kg", "Total", "Etapa de Venta"])

    except Exception as e:
        st.error(f"Error de conexión: {e}")
        df = pd.DataFrame(columns=["cliente", "producto", "Monto Soles", "Kg Proyectados", "Ventas kg", "Total", "Etapa de Venta"])

    # --- INTERFAZ PRINCIPAL ---
    c_btns = st.columns([1, 1.2, 1.5, 1, 4])
    with c_btns[0]:
        if st.button("📄 Nuevo"): formulario_nuevo()
    with c_btns[1]:
        if st.button("🔄 Actualizar"):
            if "seleccion" in st.session_state and not st.session_state.seleccion.empty:
                formulario_actualizar(st.session_state.seleccion.iloc[0])
            else: st.warning("Selecciona una fila")
    with c_btns[2]:
        st.download_button("📊 Excel", data=generar_excel(df), file_name=f"{mes_consulta}.xlsx")
    with c_btns[3]:
        if st.button("🚪 Salir"):
            st.session_state.autenticado = False
            st.rerun()

    st.divider()
    st.write(f"### Detalle - {mes_consulta}")
    
    event = st.dataframe(df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")

    if len(event.selection.rows) > 0:
        st.session_state.seleccion = df.iloc[event.selection.rows]
    else:
        st.session_state.seleccion = pd.DataFrame()
    
    t1, t2 = st.columns(2)
    t1.metric("Total Soles", f"S/ {df['Monto Soles'].sum() if not df.empty else 0:,.2f}")
    t2.metric("Total Kg", f"{df['Kg Proyectados'].sum() if not df.empty else 0:,.2f}")