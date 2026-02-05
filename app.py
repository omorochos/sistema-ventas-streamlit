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

# --- DIALOG: EDICIÓN ---
@st.dialog("Editar Kg de Registros Seleccionados", width="large")
def editar_multiple(filas_seleccionadas):
    st.info("Modifica los Kg. Se actualizarán los Soles automáticamente.")
    cambios = []
    
    for i, fila in filas_seleccionadas.iterrows():
        id_real = int(float(fila['id']))
        with st.container(border=True):
            st.write(f"**ID:** {id_real} | **Cliente:** {fila['cliente']} | **Producto:** {fila['producto']}")
            n_kg = st.number_input(f"Nuevos Kg", value=float(fila['total_kg']), min_value=0.1, key=f"kg_{id_real}")
            
            # Recalcular soles proporcionalmente
            precio_u = float(fila['total_s']) / float(fila['total_kg']) if float(fila['total_kg']) > 0 else 0
            n_s = round(n_kg * precio_u, 2)
            
            cambios.append({"id": id_real, "total_kg": n_kg, "total_s": n_s})

    if st.button("💾 GUARDAR CAMBIOS EN LA NUBE", type="primary", use_container_width=True):
        exitos = 0
        with st.spinner("Actualizando..."):
            for c in cambios:
                try:
                    res = supabase.table("ventas").update({
                        "total_kg": c["total_kg"],
                        "total_s": c["total_s"]
                    }).eq("id", c["id"]).execute()
                    if res.data: exitos += 1
                except Exception as e:
                    st.error(f"Error en ID {c['id']}: {e}")
        
        if exitos > 0:
            st.success(f"✅ ¡Hecho! {exitos} registros actualizados.")
            time.sleep(1)
            st.rerun()
        else:
            st.error("No se actualizó nada. Revisa si activaste el permiso UPDATE en Supabase.")

# --- INTERFAZ ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False

if st.session_state.autenticado:
    st.sidebar.title(f"Usuario: {st.session_state.usuario_logueado}")
    mes_sel = st.sidebar.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    consolidado = st.sidebar.toggle("Ver últimos 3 meses")
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

    # Carga de datos
    try:
        query = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado)
        if consolidado:
            meses_f = obtener_meses_anteriores(mes_sel)
            res = query.in_("mes", meses_f).execute()
        else:
            res = query.eq("mes", mes_sel).execute()
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: df = pd.DataFrame()

    if not df.empty:
        df.insert(0, "Sel", False)
        editor = st.data_editor(df, hide_index=True, use_container_width=True,
                                column_config={"Sel": st.column_config.CheckboxColumn("✔"), "id": st.column_config.NumberColumn("ID", format="%d")},
                                disabled=[c for c in df.columns if c != "Sel"])

        c1, c2 = st.columns(2)
        with c1:
            st.download_button("📥 Descargar Excel", generar_excel(df.drop(columns=["Sel"])), f"Reporte_{mes_sel}.xlsx", use_container_width=True)
        with c2:
            sel = editor[editor["Sel"] == True]
            if not sel.empty:
                if st.button(f"✏️ Editar {len(sel)} filas", type="primary", use_container_width=True):
                    editar_multiple(sel)
    else:
        st.warning("No hay datos para este mes.")
else:
    # Login
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado, st.session_state.usuario_logueado = True, u
            st.rerun()