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
def generar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- DIALOG: EDICIÓN MÚLTIPLE ---
@st.dialog("Editar Kg de Registros Seleccionados", width="large")
def editar_multiple(filas_seleccionadas):
    st.info("Solo se permite la edición de Kilogramos. El Cliente y Producto son informativos.")
    
    # Lista para almacenar los nuevos valores de cada fila
    cambios_a_realizar = []
    
    for i, fila in filas_seleccionadas.iterrows():
        with st.container(border=True):
            st.markdown(f"**Cliente:** {fila['cliente']} | **Producto:** {fila['producto']}")
            
            # Input de KG (Solo editable)
            n_kg = st.number_input(
                f"Kg Proyectados para ID: {fila['id']}", 
                value=float(fila['total_kg']), 
                min_value=0.0,
                key=f"kg_input_{fila['id']}"
            )
            
            # Calculamos proporcionalmente el dinero (total_s) basado en el precio anterior
            precio_unitario = fila['total_s'] / fila['total_kg'] if fila['total_kg'] > 0 else 0
            n_s = n_kg * precio_unitario
            
            cambios_a_realizar.append({
                "id": fila['id'],
                "total_kg": n_kg,
                "total_s": n_s
            })
    
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 GUARDAR TODOS LOS CAMBIOS", type="primary", use_container_width=True):
            with st.spinner("Actualizando registros en la nube..."):
                try:
                    for cambio in cambios_a_realizar:
                        supabase.table("ventas").update({
                            "total_kg": cambio["total_kg"],
                            "total_s": cambio["total_s"]
                        }).eq("id", cambio["id"]).execute()
                    
                    st.success("¡Datos actualizados con éxito!")
                    st.session_state.clear # Limpiamos caché para forzar recarga
                    st.rerun() # Refrescamos la página
                except Exception as err:
                    st.error(f"Error técnico al guardar: {err}")
            
    with col2:
        if st.button("🗑️ ELIMINAR SELECCIONADOS", use_container_width=True):
            with st.spinner("Eliminando registros..."):
                try:
                    ids_a_borrar = filas_seleccionadas["id"].tolist()
                    for id_b in ids_a_borrar:
                        supabase.table("ventas").delete().eq("id", id_b).execute()
                    st.rerun()
                except Exception as err:
                    st.error(f"Error al eliminar: {err}")

# --- CUERPO PRINCIPAL ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False

if st.session_state.autenticado:
    # Sidebar
    st.sidebar.title(f"Usuario: {st.session_state.usuario_logueado}")
    mes_consulta = st.sidebar.selectbox("Mes de consulta", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    ver_consolidado = st.sidebar.toggle("Ver Consolidado (3 meses anteriores)")

    # Carga de ventas desde Supabase
    try:
        res_v = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).execute()
        df_ventas = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()
    except:
        df_ventas = pd.DataFrame()

    if not df_ventas.empty:
        if ver_consolidado:
            # Lógica de consolidado (Sin selección para evitar errores)
            meses_lista = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            idx = meses_lista.index(mes_consulta)
            meses_int = meses_lista[max(0, idx-3):idx+1]
            df_mostrar = df_ventas[df_ventas["mes"].isin(meses_int)]
            df_mostrar = df_mostrar.groupby(["cliente", "producto", "sector"]).agg({"total_s": "sum", "total_kg": "sum"}).reset_index()
            st.subheader(f"📊 Consolidado")
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
            st.download_button("📥 Descargar Excel", generar_excel(df_mostrar), f"Consolidado_{mes_consulta}.xlsx")
        else:
            df_mostrar = df_ventas[df_ventas["mes"] == mes_consulta]
            st.subheader(f"📅 Proyecciones de {mes_consulta}")
            
            # --- TABLA CON SELECCIÓN AL COSTADO ---
            df_con_check = df_mostrar.copy()
            df_con_check.insert(0, "Sel", False) # Columna de check al inicio
            
            edited_df = st.data_editor(
                df_con_check,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Sel": st.column_config.CheckboxColumn("✔", default=False),
                    "id": None # Ocultamos el ID para estética
                },
                disabled=[col for col in df_con_check.columns if col != "Sel"]
            )

            col_ex, col_ed = st.columns([1, 1])
            with col_ex:
                st.download_button("📥 Descargar Excel", generar_excel(df_mostrar), f"Reporte_{mes_consulta}.xlsx")
            
            with col_ed:
                seleccionados = edited_df[edited_df["Sel"] == True]
                if not seleccionados.empty:
                    if st.button(f"✏️ Editar {len(seleccionados)} registros", type="primary", use_container_width=True):
                        editar_multiple(seleccionados)
    else:
        st.info("No se encontraron registros para este mes.")
else:
    # Login
    st.title("Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado, st.session_state.usuario_logueado = True, u
            st.rerun()