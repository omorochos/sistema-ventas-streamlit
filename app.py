import streamlit as st
import pandas as pd
from supabase import create_client, Client
from io import BytesIO

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sistema Proyecciones PRO", layout="wide")

# Conexión Segura
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
    st.info("Modifica los Kilogramos. El Cliente y Producto no son editables.")
    
    cambios_a_realizar = []
    
    # Mostrar cada fila seleccionada para editar
    for i, fila in filas_seleccionadas.iterrows():
        with st.container(border=True):
            st.markdown(f"**Cliente:** {fila['cliente']} | **Producto:** {fila['producto']}")
            
            # Input de KG
            n_kg = st.number_input(
                f"Kg Proyectados (ID: {fila['id']})", 
                value=float(fila['total_kg']), 
                min_value=0.0,
                key=f"input_edit_{fila['id']}"
            )
            
            # Recalcular soles (total_s) manteniendo el precio unitario
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
            with st.spinner("Guardando en Supabase..."):
                try:
                    for cambio in cambios_a_realizar:
                        # Ejecutamos la actualización fila por fila
                        supabase.table("ventas").update({
                            "total_kg": cambio["total_kg"],
                            "total_s": cambio["total_s"]
                        }).eq("id", cambio["id"]).execute()
                    
                    st.success("¡Guardado correctamente!")
                    # USAR st.rerun() SOLITO PARA REFRESCAR TODO
                    st.rerun() 
                except Exception as err:
                    st.error(f"Error al guardar: {err}")
            
    with col2:
        if st.button("🗑️ ELIMINAR SELECCIONADOS", use_container_width=True):
            with st.spinner("Eliminando..."):
                try:
                    ids = filas_seleccionadas["id"].tolist()
                    for id_b in ids:
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
    ver_consolidado = st.sidebar.toggle("Ver Consolidado")

    # CARGA DE DATOS (Sin caché para ver los cambios al instante)
    res_v = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).execute()
    df_ventas = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()

    if not df_ventas.empty:
        if ver_consolidado:
            # Lógica de consolidado...
            st.subheader("📊 Consolidado")
            st.dataframe(df_ventas, use_container_width=True, hide_index=True)
        else:
            df_mostrar = df_ventas[df_ventas["mes"] == mes_consulta]
            st.subheader(f"📅 Proyecciones de {mes_consulta}")
            
            if not df_mostrar.empty:
                # TABLA CON CHECKS AL COSTADO
                df_con_check = df_mostrar.copy()
                df_con_check.insert(0, "Sel", False)
                
                # Usamos st.data_editor para capturar la selección
                edited_df = st.data_editor(
                    df_con_check,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Sel": st.column_config.CheckboxColumn("✔", default=False),
                        "id": st.column_config.TextColumn("ID", width="small")
                    },
                    disabled=[col for col in df_con_check.columns if col != "Sel"]
                )

                # Botones de Acción
                c1, c2 = st.columns([1, 1])
                with c1:
                    st.download_button("📥 Excel", generar_excel(df_mostrar), f"Proyeccion_{mes_consulta}.xlsx")
                with c2:
                    seleccionados = edited_df[edited_df["Sel"] == True]
                    if not seleccionados.empty:
                        if st.button(f"✏️ Editar {len(seleccionados)} seleccionado(s)", type="primary", use_container_width=True):
                            editar_multiple(seleccionados)
            else:
                st.warning(f"No hay datos para {mes_consulta}")
    else:
        st.info("Aún no tienes proyecciones registradas.")

else:
    # Login
    st.title("Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado, st.session_state.usuario_logueado = True, u
            st.rerun()