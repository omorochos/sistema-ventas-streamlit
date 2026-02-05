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

# --- DIALOG: EDICIÓN MÚLTIPLE ---
@st.dialog("Editar Kg de Registros Seleccionados", width="large")
def editar_multiple(filas_seleccionadas):
    st.warning("⚠️ Asegúrate de que los IDs coincidan con la tabla 'ventas' en Supabase.")
    
    cambios_a_realizar = []
    
    for i, fila in filas_seleccionadas.iterrows():
        # LIMPIEZA DE ID: Aseguramos que sea un entero
        id_real = int(fila['id'])
        
        with st.container(border=True):
            st.markdown(f"**Registro ID:** `{id_real}` | **Cliente:** {fila['cliente']}")
            st.markdown(f"**Producto:** {fila['producto']}")
            
            n_kg = st.number_input(
                f"Nuevos Kg para el ID {id_real}", 
                value=float(fila['total_kg']), 
                min_value=0.1, # Evitamos 0 para no romper el cálculo de soles
                key=f"edit_input_{id_real}"
            )
            
            # Cálculo de soles (total_s)
            # Intentamos obtener el precio unitario original
            old_kg = float(fila['total_kg'])
            old_s = float(fila['total_s'])
            precio_unitario = old_s / old_kg if old_kg > 0 else 0
            n_s = n_kg * precio_unitario
            
            cambios_a_realizar.append({
                "id": id_real,
                "total_kg": float(n_kg),
                "total_s": float(n_s)
            })
    
    st.divider()
    
    if st.button("💾 CONFIRMAR Y GUARDAR EN NUBE", type="primary", use_container_width=True):
        exitos = 0
        
        with st.spinner("Actualizando base de datos..."):
            for cambio in cambios_a_realizar:
                try:
                    # USAMOS .match({'id': cambio['id']}) que es más estricto
                    res = supabase.table("ventas").update({
                        "total_kg": cambio["total_kg"],
                        "total_s": cambio["total_s"]
                    }).match({'id': cambio['id']}).execute()
                    
                    if res.data:
                        exitos += 1
                except Exception as e:
                    st.error(f"Error en ID {cambio['id']}: {str(e)}")
        
        if exitos > 0:
            st.success(f"✅ ¡Éxito! Se actualizaron {exitos} registros.")
            time.sleep(1.5)
            # Limpiamos caché de Streamlit y reiniciamos
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("No se pudo actualizar ningún registro. Verifica que el ID exista en la tabla 'ventas'.")

# --- CUERPO PRINCIPAL ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False

if st.session_state.autenticado:
    st.sidebar.title(f"Usuario: {st.session_state.usuario_logueado}")
    mes_consulta = st.sidebar.selectbox("Mes de consulta", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

    # CARGA FRESCA DE DATOS
    try:
        res_v = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).execute()
        df_ventas = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        df_ventas = pd.DataFrame()

    if not df_ventas.empty:
        df_mostrar = df_ventas[df_ventas["mes"] == mes_consulta].copy()
        
        st.subheader(f"📅 Proyecciones de {mes_consulta}")
        
        if not df_mostrar.empty:
            # Check de selección
            df_mostrar.insert(0, "Sel", False)
            
            # Editor de tabla
            edited_df = st.data_editor(
                df_mostrar,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Sel": st.column_config.CheckboxColumn("✔", default=False),
                    "id": st.column_config.NumberColumn("ID", help="ID único de la venta", format="%d"),
                    "vendedor": None
                },
                disabled=[c for c in df_mostrar.columns if c != "Sel"]
            )

            col1, col2 = st.columns(2)
            with col1:
                st.download_button("📥 Excel", generar_excel(df_mostrar.drop(columns=["Sel"])), f"Reporte_{mes_consulta}.xlsx")
            with col2:
                seleccionados = edited_df[edited_df["Sel"] == True]
                if not seleccionados.empty:
                    if st.button(f"✏️ Editar {len(seleccionados)} filas", type="primary", use_container_width=True):
                        editar_multiple(seleccionados)
        else:
            st.warning(f"No hay registros para {mes_consulta}.")
    else:
        st.info("La tabla 'ventas' está vacía.")
else:
    # Login
    st.title("Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado, st.session_state.usuario_logueado = True, u
            st.rerun()