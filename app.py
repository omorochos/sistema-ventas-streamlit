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

# --- DIALOG: EDICIÓN ---
@st.dialog("Editar Registro Seleccionado")
def editar_registro(fila):
    st.write(f"### Editando: {fila['producto']}")
    nuevo_mes = st.selectbox("Cambiar Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], 
                             index=["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(fila['mes']))
    
    nueva_cant = st.number_input("Multiplicador de cantidad (actual: 1.0)", value=1.0, step=0.1)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Guardar Cambios"):
            update_data = {
                "mes": nuevo_mes,
                "total_s": float(fila['total_s'] * nueva_cant),
                "total_kg": float(fila['total_kg'] * nueva_cant)
            }
            supabase.table("ventas").update(update_data).eq("id", fila['id']).execute()
            st.success("¡Actualizado!")
            st.rerun()
    with col2:
        if st.button("🗑️ Eliminar"):
            supabase.table("ventas").delete().eq("id", fila['id']).execute()
            st.rerun()

# --- CUERPO PRINCIPAL ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False

if st.session_state.autenticado:
    df_maestro = obtener_productos()
    
    # Sidebar
    st.sidebar.title(f"Hola, {st.session_state.usuario_logueado}")
    mes_consulta = st.sidebar.selectbox("Mes de consulta", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    ver_consolidado = st.sidebar.toggle("Ver Consolidado (3 meses anteriores)")

    # Carga de ventas
    res_v = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).execute()
    df_ventas = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()

    if not df_ventas.empty:
        meses_lista = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        idx = meses_lista.index(mes_consulta)
        
        if ver_consolidado:
            meses_interes = meses_lista[max(0, idx-3):idx+1]
            df_mostrar = df_ventas[df_ventas["mes"].isin(meses_interes)]
            df_mostrar = df_mostrar.groupby(["cliente", "producto", "sector"]).agg({"total_s": "sum", "total_kg": "sum"}).reset_index()
            st.subheader(f"📊 Consolidado")
        else:
            df_mostrar = df_ventas[df_ventas["mes"] == mes_consulta]
            st.subheader(f"📅 Proyecciones de {mes_consulta}")

        # --- AQUÍ ESTÁ EL CAMBIO CLAVE ---
        # Añadimos una columna temporal de "Seleccionar"
        if not df_mostrar.empty and not ver_consolidado:
            df_con_check = df_mostrar.copy()
            df_con_check.insert(0, "Seleccionar", False) # Ponemos el check al inicio (costado izquierdo)
            
            # Usamos data_editor para mostrar los cuadritos/círculos de selección
            edited_df = st.data_editor(
                df_con_check,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Seleccionar": st.column_config.CheckboxColumn(
                        "✔",
                        help="Selecciona la fila para editar",
                        default=False,
                    )
                },
                disabled=[col for col in df_con_check.columns if col != "Seleccionar"]
            )

            # Lógica de los botones
            col_ex, col_ed = st.columns([1, 1])
            with col_ex:
                excel_bin = generar_excel(df_mostrar)
                st.download_button("📥 Descargar Excel", excel_bin, f"Reporte_{mes_consulta}.xlsx")
            
            with col_ed:
                # Verificamos qué fila fue marcada en el check
                filas_seleccionadas = edited_df[edited_df["Seleccionar"] == True]
                if not filas_seleccionadas.empty:
                    if st.button(f"✏️ Editar Fila Seleccionada", type="primary"):
                        editar_registro(filas_seleccionadas.iloc[0])
        else:
            # Si es consolidado, mostramos tabla normal sin checks
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
            excel_bin = generar_excel(df_mostrar)
            st.download_button("📥 Descargar Excel", excel_bin, f"Consolidado_{mes_consulta}.xlsx")

    else:
        st.info("No hay datos.")
else:
    # Lógica de Login (la misma que ya tienes)
    st.title("Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado, st.session_state.usuario_logueado = True, u
            st.rerun()