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

# --- FUNCIONES DE APOYO ---
def generar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Proyecciones')
    return output.getvalue()

def obtener_meses_anteriores(mes_actual):
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    try:
        idx = meses.index(mes_actual)
        return meses[max(0, idx-3):idx+1]
    except:
        return [mes_actual]

# --- DIALOGO DE EDICIÓN ---
@st.dialog("Editar Kg de Registros Seleccionados", width="large")
def editar_multiple(filas_seleccionadas):
    st.info("Modifica los kilogramos. El sistema recalculará los soles automáticamente.")
    
    cambios_preparados = []
    
    for i, fila in filas_seleccionadas.iterrows():
        # CORRECCIÓN CLAVE: Forzamos el ID a ser un entero puro de Python
        id_real = int(float(fila['id']))
        
        with st.container(border=True):
            st.markdown(f"**Cliente:** {fila['cliente']} | **Producto:** {fila['producto']}")
            
            n_kg = st.number_input(
                f"Nuevos Kg (ID {id_real})", 
                value=float(fila['total_kg']), 
                min_value=0.1,
                key=f"input_kg_{id_real}"
            )
            
            # Recalcular soles (total_s) manteniendo el precio unitario
            precio_unit = float(fila['total_s']) / float(fila['total_kg']) if float(fila['total_kg']) > 0 else 0
            n_s = n_kg * precio_unit
            
            cambios_preparados.append({
                "id": id_real,
                "total_kg": float(n_kg),
                "total_s": float(n_s)
            })
    
    st.divider()
    
    if st.button("💾 GUARDAR TODOS LOS CAMBIOS", type="primary", use_container_width=True):
        exitos = 0
        with st.spinner("Actualizando en la nube..."):
            for cambio in cambios_preparados:
                try:
                    # Usamos .match para asegurar coincidencia exacta de ID
                    res = supabase.table("ventas").update({
                        "total_kg": cambio["total_kg"],
                        "total_s": cambio["total_s"]
                    }).match({"id": cambio["id"]}).execute()
                    
                    if res.data:
                        exitos += 1
                except Exception as e:
                    st.error(f"Error en ID {cambio['id']}: {e}")
        
        if exitos > 0:
            st.success(f"✅ Se actualizaron {exitos} registros.")
            time.sleep(1)
            st.rerun()

# --- INTERFAZ PRINCIPAL ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False

if st.session_state.autenticado:
    # Sidebar con todas tus opciones originales
    st.sidebar.title(f"Usuario: {st.session_state.usuario_logueado}")
    mes_consulta = st.sidebar.selectbox("Mes de consulta", 
        ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    
    ver_consolidado = st.sidebar.toggle("Ver Consolidado (3 meses anteriores)")
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

    # Carga de datos
    try:
        if ver_consolidado:
            meses_filtro = obtener_meses_anteriores(mes_consulta)
            res = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).in_("mes", meses_filtro).execute()
            titulo_tabla = f"📊 Consolidado: {', '.join(meses_filtro)}"
        else:
            res = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).eq("mes", mes_consulta).execute()
            titulo_tabla = f"📅 Proyecciones de {mes_consulta}"
            
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Error al cargar: {e}")
        df = pd.DataFrame()

    if not df.empty:
        st.subheader(titulo_tabla)
        
        # Preparamos el editor con columna de selección
        df_edit = df.copy()
        df_edit.insert(0, "Seleccionar", False)
        
        editor_principal = st.data_editor(
            df_edit,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Seleccionar": st.column_config.CheckboxColumn("✔", default=False),
                "id": st.column_config.NumberColumn("ID", format="%d"),
                "vendedor": None # Ocultamos vendedor para ahorrar espacio
            },
            disabled=[c for c in df_edit.columns if c != "Seleccionar"]
        )

        # Botones de Acción (Excel y Edición)
        col_excel, col_edit = st.columns(2)
        
        with col_excel:
            nombre_archivo = f"Consolidado_{mes_consulta}.xlsx" if ver_consolidado else f"Reporte_{mes_consulta}.xlsx"
            st.download_button(
                label="📥 Descargar Excel",
                data=generar_excel(df),
                file_name=nombre_archivo,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
        with col_edit:
            seleccionados = editor_principal[editor_principal["Seleccionar"] == True]
            if not seleccionados.empty:
                if st.button(f"✏️ Editar {len(seleccionados)} seleccionado(s)", type="primary", use_container_width=True):
                    editar_multiple(seleccionados)
    else:
        st.warning(f"No hay datos para mostrar en {mes_consulta}.")

else:
    # Login
    st.title("Acceso Sistema de Ventas")
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar", use_container_width=True):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado, st.session_state.usuario_logueado = True, u
            st.rerun()