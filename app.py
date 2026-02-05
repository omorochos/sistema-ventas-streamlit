import streamlit as st
import pandas as pd
from supabase import create_client, Client
from io import BytesIO
import time

# --- 1. CONEXIÓN ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Error crítico de conexión: {e}")

# --- 2. FUNCIONES DE EXCEL Y MESES ---
def generar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Proyecciones')
    return output.getvalue()

def obtener_rango_meses(mes_actual):
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    idx = meses.index(mes_actual)
    return meses[max(0, idx-3):idx+1]

# --- 3. DIÁLOGO DE EDICIÓN (REFORZADO) ---
@st.dialog("Editar Kg de Registros", width="large")
def editar_multiple(filas_seleccionadas):
    st.warning("Se actualizarán los Kg y los Soles proporcionalmente.")
    
    cambios_finales = []
    for _, fila in filas_seleccionadas.iterrows():
        id_fijo = int(fila['id']) # Forzamos entero puro
        with st.container(border=True):
            st.write(f"**{fila['cliente']}** - {fila['producto']}")
            n_kg = st.number_input(f"Kg (ID {id_fijo})", value=float(fila['total_kg']), min_value=0.1, key=f"k_{id_fijo}")
            
            # Cálculo de soles
            precio_u = float(fila['total_s']) / float(fila['total_kg']) if float(fila['total_kg']) > 0 else 0
            n_s = round(n_kg * precio_u, 2)
            
            cambios_finales.append({"p_id": id_fijo, "p_kg": n_kg, "p_s": n_s})

    if st.button("💾 CONFIRMAR GUARDADO FINAL", type="primary", use_container_width=True):
        exitos = 0
        with st.spinner("Escribiendo en la base de datos..."):
            for c in cambios_finales:
                # Intentamos la actualización con un formato más simple y directo
                try:
                    res = supabase.table("ventas").update({
                        "total_kg": c["p_kg"],
                        "total_s": c["p_s"]
                    }).eq("id", c["p_id"]).execute()
                    
                    if res.data:
                        exitos += 1
                except Exception as e:
                    st.error(f"Error en ID {c['p_id']}: {e}")
        
        if exitos > 0:
            st.success(f"✅ ¡Hecho! {exitos} filas actualizadas.")
            time.sleep(1)
            st.rerun()

# --- 4. INTERFAZ PRINCIPAL ---
st.set_page_config(page_title="Sistema Proyecciones", layout="wide")

if "autenticado" not in st.session_state: st.session_state.autenticado = False

if st.session_state.autenticado:
    # SIDEBAR
    st.sidebar.title(f"Usuario: {st.session_state.usuario_logueado}")
    mes_sel = st.sidebar.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    consolidado = st.sidebar.toggle("Ver últimos 3 meses")
    
    if st.sidebar.button("Salir"):
        st.session_state.autenticado = False
        st.rerun()

    # CARGA DE DATOS
    try:
        if consolidado:
            meses_filtro = obtener_rango_meses(mes_sel)
            res = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).in_("mes", meses_filtro).execute()
        else:
            res = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).eq("mes", mes_sel).execute()
        
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except:
        df = pd.DataFrame()

    # VISUALIZACIÓN
    if not df.empty:
        st.subheader(f"Data de {mes_sel} (Consolidado: {'Si' if consolidado else 'No'})")
        
        # Tabla con selección
        df_view = df.copy()
        df_view.insert(0, "Seleccionar", False)
        
        editor = st.data_editor(
            df_view,
            hide_index=True,
            use_container_width=True,
            column_config={"Seleccionar": st.column_config.CheckboxColumn("✔")},
            disabled=[c for c in df_view.columns if c != "Seleccionar"]
        )

        # BOTONES
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("📥 Descargar Excel", generar_excel(df), f"Reporte_{mes_sel}.xlsx", use_container_width=True)
        with c2:
            seleccionados = editor[editor["Seleccionar"] == True]
            if not seleccionados.empty:
                if st.button(f"✏️ Editar {len(seleccionados)} filas", type="primary", use_container_width=True):
                    editar_multiple(seleccionados)
    else:
        st.info(f"No hay datos para {mes_sel}.")

else:
    # LOGIN
    st.title("Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado, st.session_state.usuario_logueado = True, u
            st.rerun()