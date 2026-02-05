import streamlit as st
import pandas as pd
from supabase import create_client, Client
import time

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sistema Proyecciones", layout="wide")

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Error de conexión: {e}")

# --- DIALOG: EDICIÓN MÚLTIPLE ---
@st.dialog("Editar Kg de Registros Seleccionados", width="large")
def editar_multiple(filas_seleccionadas):
    st.info("Solo se permite editar los Kg. El sistema actualizará los Soles automáticamente.")
    
    cambios_a_enviar = []
    
    for i, fila in filas_seleccionadas.iterrows():
        # --- SOLUCIÓN AL ERROR DE ID ---
        # Forzamos que el ID sea un entero de Python (int) 
        # Esto elimina el ".0" que a veces agrega Streamlit/Pandas
        id_limpio = int(float(fila['id'])) 
        
        with st.container(border=True):
            st.markdown(f"**ID:** `{id_limpio}` | **Cliente:** {fila['cliente']} | **Producto:** {fila['producto']}")
            
            n_kg = st.number_input(
                f"Nuevos Kg (ID {id_limpio})", 
                value=float(fila['total_kg']), 
                min_value=0.1,
                key=f"edit_kg_{id_limpio}"
            )
            
            # Cálculo de soles proporcional
            old_kg = float(fila['total_kg'])
            old_s = float(fila['total_s'])
            precio = old_s / old_kg if old_kg > 0 else 0
            n_s = n_kg * precio
            
            cambios_a_enviar.append({
                "id": id_limpio,
                "total_kg": float(n_kg),
                "total_s": float(n_s)
            })
    
    st.divider()
    
    if st.button("💾 CONFIRMAR Y GUARDAR EN NUBE", type="primary", use_container_width=True):
        exitos = 0
        with st.spinner("Actualizando en Supabase..."):
            for cambio in cambios_a_enviar:
                try:
                    # Usamos .eq('id', ...) asegurando que el ID es un INT
                    resultado = supabase.table("ventas").update({
                        "total_kg": cambio["total_kg"],
                        "total_s": cambio["total_s"]
                    }).eq("id", cambio["id"]).execute()
                    
                    if len(resultado.data) > 0:
                        exitos += 1
                except Exception as e:
                    st.error(f"Error en ID {cambio['id']}: {e}")
        
        if exitos > 0:
            st.success(f"✅ Se actualizaron {exitos} registros con éxito.")
            time.sleep(1)
            st.cache_data.clear() # Forzamos limpieza de memoria
            st.rerun()

# --- CUERPO PRINCIPAL ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False

if st.session_state.autenticado:
    st.sidebar.title(f"Usuario: {st.session_state.usuario_logueado}")
    mes_consulta = st.sidebar.selectbox("Mes de consulta", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    
    # CARGA DIRECTA DE SUPABASE
    res = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).eq("mes", mes_consulta).execute()
    df = pd.DataFrame(res.data) if res.data else pd.DataFrame()

    if not df.empty:
        st.subheader(f"📅 Proyecciones: {mes_consulta}")
        
        # Agregamos columna de selección al inicio
        df.insert(0, "Sel", False)
        
        # Configuramos la tabla para que el ID se vea como número entero
        editor = st.data_editor(
            df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Sel": st.column_config.CheckboxColumn("✔", default=False),
                "id": st.column_config.NumberColumn("ID", format="%d"), # %d quita los decimales
            },
            disabled=[c for c in df.columns if c != "Sel"]
        )

        seleccionados = editor[editor["Sel"] == True]
        if not seleccionados.empty:
            if st.button(f"✏️ Editar {len(seleccionados)} seleccionado(s)", type="primary"):
                editar_multiple(seleccionados)
    else:
        st.warning(f"No hay datos en 'ventas' para {mes_consulta}.")
else:
    # Pantalla de Login (mantenla como la tenías)
    st.title("Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado, st.session_state.usuario_logueado = True, u
            st.rerun()