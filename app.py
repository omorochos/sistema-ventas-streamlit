import streamlit as st
import pandas as pd
from supabase import create_client, Client
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Proyecciones PRO", layout="wide")

# --- CONEXIÓN A SUPABASE ---
URL: str = st.secrets["SUPABASE_URL"]
KEY: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

# --- CARGAR MEGA BASE DE PRODUCTOS (DINÁMICA) ---
@st.cache_data(ttl=600)  # Se actualiza cada 10 minutos
def obtener_productos_maestros():
    try:
        # Traemos la lista de productos de la tabla 'Productos'
        res = supabase.table("Productos").select("*").execute()
        df = pd.DataFrame(res.data)
        return df
    except Exception as e:
        st.error(f"Error al cargar base de productos: {e}")
        return pd.DataFrame()

# Cargamos la base una sola vez al inicio
df_maestro = obtener_productos_maestros()

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
    
    # 1. Verificamos si df_maestro tiene datos
    if df_maestro.empty:
        st.warning("⚠️ No se encontraron productos en la base de datos. Verifica la tabla 'Productos' en Supabase.")
        return

    # 2. Detectamos automáticamente cómo se llaman las columnas (Mayúsculas/Minúsculas)
    col_cliente = "cliente" if "cliente" in df_maestro.columns else "Cliente"
    col_prod = "producto" if "producto" in df_maestro.columns else "Producto"
    col_sec = "sector" if "sector" in df_maestro.columns else "Sector"
    col_pre = "precio" if "precio" in df_maestro.columns else "Precio"
    col_pes = "peso" if "peso" in df_maestro.columns else "Peso"

    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
            lista_clientes = sorted(df_maestro[col_cliente].unique().tolist())
            cliente_sel = st.selectbox("Cliente", lista_clientes)

        with c2:
            # FILTRADO DINÁMICO
            productos_filtrados = df_maestro[df_maestro[col_cliente] == cliente_sel]
            prod_sel = st.selectbox("Producto", productos_filtrados[col_prod].tolist())
            cant_sel = st.number_input("Cantidad", min_value=1, step=1)

        with c3:
            st.write("###")
            if st.button("➕ Añadir"):
                info = productos_filtrados[productos_filtrados[col_prod] == prod_sel].iloc[0]
                
                st.session_state.carrito_proyeccion.append({
                    "vendedor": vendedor_actual, 
                    "mes": mes_sel, 
                    "cliente": cliente_sel,
                    "producto": prod_sel, 
                    "sector": info[col_sec],
                    "total_s": float(info[col_pre] * cant_sel),
                    "total_kg": float(info[col_pes] * cant_sel)
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
        # Buscamos precio/peso en la maestra para recalcular
        col_prod = "producto" if "producto" in df_maestro.columns else "Producto"
        col_pre = "precio" if "precio" in df_maestro.columns else "Precio"
        col_pes = "peso" if "peso" in df_maestro.columns else "Peso"
        
        info = df_maestro[df_maestro[col_prod] == fila['producto']].iloc[0]
        
        supabase.table("ventas").update({
            "total_s": float(info[col_pre] * nueva_cant),
            "total_kg": float(info[col_pes] * nueva_cant)
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
    # --- FILTROS LADO IZQUIERDO ---
    st.sidebar.header("Configuración")
    mes_consulta = st.sidebar.selectbox("Mes:", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    ver_consolidado = st.sidebar.toggle("Ver Consolidado (3 meses anteriores)")

    # --- OBTENCIÓN DE DATOS (TABLA VENTAS) ---
    try:
        res = supabase.table("ventas").select("*").execute()
        df_raw = pd.DataFrame(res.data)
        
        if not df_raw.empty:
            df = df_raw[df_raw['vendedor'] == st.session_state.usuario_logueado]
            
            if ver_consolidado:
                meses_orden = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                idx = meses_orden.index(mes_consulta)
                meses_interes = meses_orden[max(0, idx-3):idx+1]
                df = df[df['mes'].isin(meses_interes)]
                df = df.groupby(["cliente", "producto"]).agg({"total_s": "sum", "total_kg": "sum"}).reset_index()
            else:
                df = df[df['mes'] == mes_consulta]

            df = df.rename(columns={"total_s": "Monto Soles", "total_kg": "Kg Proyectados"})
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