import streamlit as st
import pandas as pd
from supabase import create_client, Client
from io import BytesIO
import time

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sistema Proyecciones PRO", layout="wide")

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Error de conexión: {e}")

# --- UTILIDADES ---
def generar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

def obtener_meses_anteriores(mes_actual):
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    try:
        idx = meses.index(mes_actual)
        return meses[max(0, idx-3):idx+1]
    except: return [mes_actual]

# --- DIALOG: NUEVO REGISTRO ---
@st.dialog("Crear Nuevo Registro", width="medium")
def nuevo_registro():
    # Traemos productos de la tabla 'Productos' para el select
    res_p = supabase.table("Productos").select("cliente, producto, sector, precio_u").execute()
    df_p = pd.DataFrame(res_p.data)
    
    if not df_p.empty:
        cliente_sel = st.selectbox("Seleccione Cliente", df_p['cliente'].unique())
        prod_filtrados = df_p[df_p['cliente'] == cliente_sel]
        producto_sel = st.selectbox("Seleccione Producto", prod_filtrados['producto'].unique())
        
        # Obtener datos automáticos del producto
        detalle = prod_filtrados[prod_filtrados['producto'] == producto_sel].iloc[0]
        
        mes_reg = st.selectbox("Mes de la Proyección", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
        kg_reg = st.number_input("Cantidad de Kg", min_value=0.1, value=1.0)
        
        if st.button("🚀 GUARDAR NUEVO", type="primary", use_container_width=True):
            nuevo_dato = {
                "vendedor": st.session_state.usuario_logueado,
                "mes": mes_reg,
                "cliente": cliente_sel,
                "producto": producto_sel,
                "sector": detalle['sector'],
                "total_kg": kg_reg,
                "total_s": kg_reg * float(detalle['precio_u'])
            }
            try:
                supabase.table("ventas").insert(nuevo_dato).execute()
                st.success("¡Registro creado!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Error al insertar: {e}")
    else:
        st.error("No hay productos cargados en la tabla 'Productos'.")

# --- DIALOG: EDICIÓN ---
@st.dialog("Editar Registros Seleccionados", width="large")
def editar_multiple(filas_seleccionadas):
    st.info("Modifica los Kg. Los soles se recalcularán automáticamente.")
    cambios = []
    
    for i, fila in filas_seleccionadas.iterrows():
        id_real = int(float(fila['id']))
        with st.container(border=True):
            st.write(f"**ID:** {id_real} | **{fila['cliente']}**")
            n_kg = st.number_input(f"Kg para {fila['producto']}", value=float(fila['total_kg']), min_value=0.1, key=f"edit_{id_real}")
            
            # Cálculo de soles
            precio_u = float(fila['total_s']) / float(fila['total_kg']) if float(fila['total_kg']) > 0 else 0
            n_s = round(n_kg * precio_u, 2)
            
            cambios.append({"id": id_real, "total_kg": n_kg, "total_s": n_s})

    if st.button("💾 ACTUALIZAR EN NUBE", type="primary", use_container_width=True):
        exitos = 0
        for c in cambios:
            try:
                res = supabase.table("ventas").update({"total_kg": c["total_kg"], "total_s": c["total_s"]}).eq("id", c["id"]).execute()
                if res.data: exitos += 1
            except Exception as e: st.error(f"Error en ID {c['id']}: {e}")
        
        if exitos > 0:
            st.success(f"✅ {exitos} registros actualizados.")
            time.sleep(1)
            st.rerun()

# --- INTERFAZ ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False

if st.session_state.autenticado:
    # --- SIDEBAR COMPLETO ---
    st.sidebar.title(f"Bienvenida, {st.session_state.usuario_logueado}")
    
    if st.sidebar.button("➕ Nuevo Registro", type="primary", use_container_width=True):
        nuevo_registro()
    
    st.sidebar.divider()
    
    mes_sel = st.sidebar.selectbox("Mes de consulta", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    consolidado = st.sidebar.toggle("Ver Consolidado (3 meses)")
    
    if st.sidebar.button("🚪 Salir", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

    # --- CARGA Y TABLA ---
    try:
        query = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado)
        if consolidado:
            meses_f = obtener_meses_anteriores(mes_sel)
            res = query.in_("mes", meses_f).execute()
            st.subheader(f"📊 Consolidado de {', '.join(meses_f)}")
        else:
            res = query.eq("mes", mes_sel).execute()
            st.subheader(f"📅 Mis Proyecciones de {mes_sel}")
        
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: df = pd.DataFrame()

    if not df.empty:
        df.insert(0, "Selección", False)
        editor = st.data_editor(df, hide_index=True, use_container_width=True,
                                column_config={"Selección": st.column_config.CheckboxColumn("✔"), "id": st.column_config.NumberColumn("ID", format="%d")},
                                disabled=[c for c in df.columns if c != "Selección"])

        col1, col2 = st.columns(2)
        with col1:
            st.download_button("📥 Descargar Excel", generar_excel(df.drop(columns=["Selección"])), f"Reporte_{mes_sel}.xlsx", use_container_width=True)
        with col2:
            sel = editor[editor["Selección"] == True]
            if not sel.empty:
                if st.button(f"✏️ Editar {len(sel)} seleccionado(s)", type="primary", use_container_width=True):
                    editar_multiple(sel)
    else:
        st.warning(f"No hay datos para {mes_sel}.")

else:
    # --- LOGIN ---
    st.title("Acceso Sistema Ventas")
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar", use_container_width=True):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado, st.session_state.usuario_logueado = True, u
            st.rerun()