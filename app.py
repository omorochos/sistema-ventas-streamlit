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
    st.write("Modifica los kilogramos proyectados para cada ítem:")
    
    nuevos_datos = []
    
    for i, fila in filas_seleccionadas.iterrows():
        with st.container(border=True):
            st.write(f"**Cliente:** {fila['cliente']} | **Producto:** {fila['producto']}")
            # Solo permitimos editar los Kg
            n_kg = st.number_input(f"Kg Proyectados (ID: {fila['id']})", 
                                   value=float(fila['total_kg']), 
                                   key=f"kg_{fila['id']}")
            
            # Recalcular proporcionalmente el total_s si cambia el kg (opcional, basado en precio unitario previo)
            precio_unitario = fila['total_s'] / fila['total_kg'] if fila['total_kg'] > 0 else 0
            n_s = n_kg * precio_unitario
            
            nuevos_datos.append({
                "id": fila['id'],
                "total_kg": n_kg,
                "total_s": n_s
            })
    
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 GUARDAR TODOS LOS CAMBIOS", type="primary", use_container_width=True):
            for d in nuevos_datos:
                supabase.table("ventas").update({
                    "total_kg": d["total_kg"],
                    "total_s": d["total_s"]
                }).eq("id", d["id"]).execute()
            st.success("¡Registros actualizados!")
            st.rerun()
            
    with col2:
        if st.button("🗑️ ELIMINAR SELECCIONADOS", use_container_width=True):
            ids_a_borrar = filas_seleccionadas["id"].tolist()
            for id_b in ids_a_borrar:
                supabase.table("ventas").delete().eq("id", id_b).execute()
            st.warning("Registros eliminados")
            st.rerun()

# --- CUERPO PRINCIPAL ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False

if st.session_state.autenticado:
    # Sidebar
    st.sidebar.title(f"Hola, {st.session_state.usuario_logueado}")
    mes_consulta = st.sidebar.selectbox("Mes de consulta", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    ver_consolidado = st.sidebar.toggle("Ver Consolidado (3 meses anteriores)")

    # Carga de ventas
    res_v = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).execute()
    df_ventas = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()

    if not df_ventas.empty:
        if ver_consolidado:
            # Lógica de consolidado (se mantiene igual)
            meses_lista = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            idx = meses_lista.index(mes_consulta)
            meses_int = meses_lista[max(0, idx-3):idx+1]
            df_mostrar = df_ventas[df_ventas["mes"].isin(meses_int)]
            df_mostrar = df_mostrar.groupby(["cliente", "producto", "sector"]).agg({"total_s": "sum", "total_kg": "sum"}).reset_index()
            st.subheader(f"📊 Consolidado")
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
        else:
            df_mostrar = df_ventas[df_ventas["mes"] == mes_consulta]
            st.subheader(f"📅 Proyecciones de {mes_consulta}")
            
            # --- TABLA CON SELECCIÓN IZQUIERDA ---
            df_con_check = df_mostrar.copy()
            df_con_check.insert(0, "Sel", False)
            
            edited_df = st.data_editor(
                df_con_check,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Sel": st.column_config.CheckboxColumn("✔", default=False),
                    "id": None # Ocultamos el ID para que se vea más limpio
                },
                disabled=[col for col in df_con_check.columns if col != "Sel"]
            )

            col_ex, col_ed = st.columns([1, 1])
            with col_ex:
                st.download_button("📥 Descargar Excel", generar_excel(df_mostrar), f"Reporte_{mes_consulta}.xlsx")
            
            with col_ed:
                seleccionados = edited_df[edited_df["Sel"] == True]
                if not seleccionados.empty:
                    if st.button(f"✏️ Editar {len(seleccionados)} fila(s)", type="primary", use_container_width=True):
                        editar_multiple(seleccionados)
    else:
        st.info("No hay datos.")
else:
    # Pantalla de Login
    st.title("Acceso Sistema")
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado, st.session_state.usuario_logueado = True, u
            st.rerun()