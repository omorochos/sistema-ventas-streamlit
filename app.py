import streamlit as st
import pandas as pd
from supabase import create_client, Client
from io import BytesIO
import time

# --- 1. CONFIGURACIÓN Y CONEXIÓN ---
st.set_page_config(page_title="Sistema Proyecciones PRO", layout="wide")

try:
    # Asegúrate de que estos nombres coincidan con tus Secrets en Streamlit Cloud
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Error de conexión con la base de datos: {e}")

# --- 2. FUNCIONES DE APOYO ---
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
        # Retorna el rango de los últimos 3 meses incluyendo el actual
        return meses[max(0, idx-3):idx+1]
    except:
        return [mes_actual]

# --- 3. DIALOG: NUEVO REGISTRO (MULTI-PRODUCTO) ---
@st.dialog("Crear Nuevos Registros", width="large")
def nuevo_registro():
    if "lista_temporal" not in st.session_state:
        st.session_state.lista_temporal = []

    try:
        # Carga de productos desde Supabase
        res_p = supabase.table("Productos").select("cliente, producto, sector, precio").execute()
        df_p = pd.DataFrame(res_p.data)

        if df_p.empty:
            st.warning("No hay productos disponibles en la tabla 'Productos'.")
            return

        # Interfaz de selección
        col1, col2 = st.columns(2)
        with col1:
            cliente_sel = st.selectbox("Seleccione Cliente", df_p['cliente'].unique())
        with col2:
            prod_filtrados = df_p[df_p['cliente'] == cliente_sel]
            producto_sel = st.selectbox("Seleccione Producto", prod_filtrados['producto'].unique())
        
        col3, col4 = st.columns(2)
        with col3:
            mes_reg = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
        with col4:
            kg_reg = st.number_input("Cantidad Kg", min_value=0.1, value=1.0, step=0.1)

        # Botón para añadir a la cola local
        if st.button("➕ Añadir a la lista", use_container_width=True):
            detalle = prod_filtrados[prod_filtrados['producto'] == producto_sel].iloc[0]
            nuevo_item = {
                "vendedor": st.session_state.usuario_logueado,
                "mes": mes_reg,
                "cliente": cliente_sel,
                "producto": producto_sel,
                "sector": detalle['sector'],
                "total_kg": kg_reg,
                "total_s": round(kg_reg * float(detalle['precio']), 2)
            }
            st.session_state.lista_temporal.append(nuevo_item)
            st.toast(f"Añadido: {producto_sel}")

        # Mostrar lista previa antes de guardar
        if st.session_state.lista_temporal:
            st.divider()
            st.subheader("📋 Ítems por guardar")
            df_temp = pd.DataFrame(st.session_state.lista_temporal)
            st.dataframe(df_temp[['cliente', 'producto', 'mes', 'total_kg', 'total_s']], use_container_width=True, hide_index=True)

            c_1, c_2 = st.columns(2)
            with c_1:
                if st.button("🗑️ Limpiar Lista", use_container_width=True):
                    st.session_state.lista_temporal = []
                    st.rerun()
            with c_2:
                if st.button("🚀 GUARDAR TODO EN NUBE", type="primary", use_container_width=True):
                    supabase.table("ventas").insert(st.session_state.lista_temporal).execute()
                    st.success(f"¡{len(st.session_state.lista_temporal)} registros guardados!")
                    st.session_state.lista_temporal = []
                    time.sleep(1.5)
                    st.rerun()

    except Exception as e:
        st.error(f"Error en el formulario: {e}")

# --- 4. DIALOG: EDICIÓN ---
@st.dialog("Editar Kg de Registros Seleccionados", width="large")
def editar_multiple(filas_seleccionadas):
    st.info("Solo se permite la edición de Kilogramos. El sistema recalcula los Soles.")
    cambios = []
    
    for i, fila in filas_seleccionadas.iterrows():
        # Forzamos ID a entero para evitar errores de coincidencia
        id_real = int(float(fila['id']))
        with st.container(border=True):
            st.write(f"**ID:** {id_real} | **Cliente:** {fila['cliente']} | **Producto:** {fila['producto']}")
            n_kg = st.number_input(f"Nuevos Kg", value=float(fila['total_kg']), min_value=0.1, key=f"ed_{id_real}")
            
            # Recalcular soles manteniendo el precio unitario original
            precio_u = float(fila['total_s']) / float(fila['total_kg']) if float(fila['total_kg']) > 0 else 0
            n_s = round(n_kg * precio_u, 2)
            
            cambios.append({"id": id_real, "total_kg": n_kg, "total_s": n_s})

    if st.button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True):
        exitos = 0
        with st.spinner("Actualizando..."):
            for c in cambios:
                try:
                    # Uso de .eq() con ID limpio
                    res = supabase.table("ventas").update({"total_kg": c["total_kg"], "total_s": c["total_s"]}).eq("id", c["id"]).execute()
                    if res.data: exitos += 1
                except Exception as e:
                    st.error(f"Error en ID {c['id']}: {e}")
        
        if exitos > 0:
            st.success(f"✅ Se actualizaron {exitos} registros.")
            time.sleep(1)
            st.rerun()

# --- 5. INTERFAZ PRINCIPAL ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False

if st.session_state.autenticado:
    # Sidebar
    st.sidebar.title(f"Usuario: {st.session_state.usuario_logueado}")
    
    if st.sidebar.button("➕ Nuevo Registro", type="primary", use_container_width=True):
        nuevo_registro()
    
    st.sidebar.divider()
    mes_sel = st.sidebar.selectbox("Mes de consulta", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    consolidado = st.sidebar.toggle("Ver Consolidado (3 meses anteriores)")
    
    if st.sidebar.button("Cerrar Sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

    # Carga de datos
    try:
        query = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado)
        if consolidado:
            meses_f = obtener_meses_anteriores(mes_sel)
            res = query.in_("mes", meses_f).execute()
            titulo = f"📊 Consolidado: {', '.join(meses_f)}"
        else:
            res = query.eq("mes", mes_sel).execute()
            titulo = f"📅 Proyecciones de {mes_sel}"
        
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except:
        df = pd.DataFrame()

    if not df.empty:
        st.subheader(titulo)
        df.insert(0, "Sel", False)
        
        editor = st.data_editor(
            df, 
            hide_index=True, 
            use_container_width=True,
            column_config={
                "Sel": st.column_config.CheckboxColumn("✔"),
                "id": st.column_config.NumberColumn("ID", format="%d")
            },
            disabled=[c for c in df.columns if c != "Sel"]
        )

        col_ex, col_ed = st.columns(2)
        with col_ex:
            st.download_button("📥 Descargar Excel", generar_excel(df.drop(columns=["Sel"])), f"Reporte_{mes_sel}.xlsx", use_container_width=True)
        with col_ed:
            seleccion = editor[editor["Sel"] == True]
            if not seleccion.empty:
                if st.button(f"✏️ Editar {len(seleccion)} filas", type="primary", use_container_width=True):
                    editar_multiple(seleccion)
    else:
        st.info(f"No hay registros para mostrar en {mes_sel}.")

else:
    # Login
    st.title("Acceso Sistema Ventas")
    col_l, col_r = st.columns([1, 2])
    with col_l:
        u = st.text_input("Usuario")
        p = st.text_input("Password", type="password")
        if st.button("Entrar", use_container_width=True):
            if u == "MARIA_AVILA" and p == "maria2026":
                st.session_state.autenticado, st.session_state.usuario_logueado = True, u
                st.rerun()
            else:
                st.error("Credenciales incorrectas")