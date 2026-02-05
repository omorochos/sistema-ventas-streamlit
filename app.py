import streamlit as st
import pandas as pd
from supabase import create_client, Client
from io import BytesIO

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sistema Proyecciones PRO", layout="wide")

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Error de conexión: {e}")

# --- UTILIDADES ---
@st.cache_data(ttl=60)
def obtener_productos():
    res = supabase.table("Productos").select("*").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def generar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- DIALOG: EDICIÓN DE FILA ---
@st.dialog("Editar Registro")
def editar_registro(fila):
    st.subheader(f"Editando Producto: {fila['producto']}")
    nuevo_mes = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], 
                             index=["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(fila['mes']))
    
    # Supongamos que quieres editar la cantidad base (estimada por el total actual)
    nueva_cant = st.number_input("Multiplicador de Cantidad (ej: 2 para duplicar)", value=1.0, step=0.1)
    
    if st.button("💾 Actualizar Cambios"):
        update_data = {
            "mes": nuevo_mes,
            "total_s": float(fila['total_s'] * nueva_cant),
            "total_kg": float(fila['total_kg'] * nueva_cant)
        }
        supabase.table("ventas").update(update_data).eq("id", fila['id']).execute()
        st.success("¡Registro actualizado!")
        st.rerun()

# --- CUERPO PRINCIPAL ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado, st.session_state.usuario_logueado = True, u
            st.rerun()
else:
    df_maestro = obtener_productos()
    
    # Sidebar
    st.sidebar.title(f"Hola, {st.session_state.usuario_logueado}")
    mes_actual = st.sidebar.selectbox("Mes de consulta", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    ver_consolidado = st.sidebar.toggle("Ver Consolidado (3 meses anteriores)")
    
    # Carga de ventas
    res_v = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).execute()
    df_ventas = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()

    if not df_ventas.empty:
        # Lógica de Consolidado
        meses_lista = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        if ver_consolidado:
            idx = meses_lista.index(mes_actual)
            meses_interes = meses_lista[max(0, idx-3):idx+1]
            df_mostrar = df_ventas[df_ventas["mes"].isin(meses_interes)]
            df_mostrar = df_mostrar.groupby(["cliente", "producto", "sector"]).agg({"total_s": "sum", "total_kg": "sum"}).reset_index()
            st.subheader(f"📊 Consolidado de {mes_actual} (y 3 meses previos)")
        else:
            df_mostrar = df_ventas[df_ventas["mes"] == mes_actual]
            st.subheader(f"📅 Proyecciones de {mes_actual}")

        # --- TABLA CON SELECCIÓN (EL "CIRCULITO") ---
        # "selection_mode='single'" activa el radio button al costado
        evento_seleccion = st.dataframe(
            df_mostrar, 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun",
            selection_mode="single" 
        )

        # --- BOTONES DINÁMICOS ---
        col1, col2 = st.columns([1, 4])
        
        with col1:
            # Botón de Excel (siempre visible)
            excel_bin = generar_excel(df_mostrar)
            st.download_button("📥 Descargar Excel", excel_bin, f"Reporte_{mes_actual}.xlsx")

        with col2:
            # El botón de editar SOLO aparece si hay una fila seleccionada
            if not ver_consolidado and len(evento_seleccion.selection.rows) > 0:
                indice_fila = evento_seleccion.selection.rows[0]
                fila_seleccionada = df_mostrar.iloc[indice_fila]
                if st.button(f"✏️ Editar: {fila_seleccionada['producto']}"):
                    editar_registro(fila_seleccionada)
    else:
        st.info("No hay datos guardados para este vendedor.")