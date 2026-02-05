import streamlit as st
import pandas as pd
from supabase import create_client, Client
from io import BytesIO
from datetime import datetime

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

def generar_excel(df, nombre_archivo):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- DIALOG: EDICIÓN DE FILA ---
@st.dialog("Editar Registro")
def editar_registro(fila):
    st.write(f"Modificando ID: {fila['id']}")
    nuevo_mes = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(fila['mes']))
    nueva_cant = st.number_input("Nueva Cantidad (proporcional)", value=1.0, step=0.5)
    
    if st.button("Actualizar en Nube"):
        # Calculamos nuevos totales basados en la proporción de la cantidad
        update_data = {
            "mes": nuevo_mes,
            "total_s": float(fila['total_s'] * nueva_cant),
            "total_kg": float(fila['total_kg'] * nueva_cant)
        }
        supabase.table("ventas").update(update_data).eq("id", fila['id']).execute()
        st.success("¡Actualizado!")
        st.rerun()

# --- DIALOG: NUEVO REGISTRO ---
@st.dialog("Registro de Proyección", width="large")
def formulario_nuevo(df_m):
    if "carrito" not in st.session_state: st.session_state.carrito = []
    col1, col2 = st.columns(2)
    with col1:
        mes = st.selectbox("Mes de Proyección", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
        cliente = st.selectbox("Seleccione Cliente", sorted(df_m["cliente"].unique().tolist()))
    with col2:
        prods = df_m[df_m["cliente"] == cliente]
        prod_sel = st.selectbox("Producto", prods["producto"].tolist())
        cant = st.number_input("Cantidad", min_value=1, step=1)
    
    if st.button("➕ Añadir al Carrito"):
        info = prods[prods["producto"] == prod_sel].iloc[0]
        st.session_state.carrito.append({
            "vendedor": st.session_state.usuario_logueado, "mes": mes, "cliente": cliente,
            "producto": prod_sel, "sector": info["sector"],
            "total_s": float(info["precio"] * cant), "total_kg": float(info["peso"] * cant)
        })
    
    if st.session_state.carrito:
        df_c = pd.DataFrame(st.session_state.carrito)
        st.table(df_c)
        if st.button("💾 CONFIRMAR GUARDADO"):
            datos = df_c.to_dict(orient='records')
            for f in datos: f.pop('id', None)
            supabase.table("ventas").insert(datos).execute()
            st.session_state.carrito = []
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
    
    # --- BARRA LATERAL ---
    st.sidebar.title(f"Bienvenida, {st.session_state.usuario_logueado}")
    if st.sidebar.button("📄 Nuevo Registro"): formulario_nuevo(df_maestro)
    
    st.sidebar.divider()
    mes_actual = st.sidebar.selectbox("Mes de consulta", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    ver_consolidado = st.sidebar.toggle("Ver Consolidado (3 meses anteriores)")
    
    if st.sidebar.button("🚪 Salir"):
        st.session_state.autenticado = False
        st.rerun()

    # --- LÓGICA DE FILTRADO ---
    res_v = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).execute()
    df_ventas = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()

    if not df_ventas.empty:
        meses_lista = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        idx_mes = meses_lista.index(mes_actual)
        
        if ver_consolidado:
            # Filtramos los 3 meses anteriores + el actual
            meses_interes = meses_lista[max(0, idx_mes-3):idx_mes+1]
            df_mostrar = df_ventas[df_ventas["mes"].isin(meses_interes)]
            # Agrupamos para el consolidado
            df_mostrar = df_mostrar.groupby(["cliente", "producto", "sector"]).agg({"total_s": "sum", "total_kg": "sum"}).reset_index()
            st.subheader(f"📊 Consolidado: {', '.join(meses_interes)}")
        else:
            df_mostrar = df_ventas[df_ventas["mes"] == mes_actual]
            st.subheader(f"📅 Proyecciones de {mes_actual}")

        # Mostrar Tabla
        st.dataframe(df_mostrar, use_container_width=True)

        # Botones de Acción
        col_ex, col_ed = st.columns(2)
        with col_ex:
            excel_data = generar_excel(df_mostrar, "reporte.xlsx")
            st.download_button("📥 Descargar Excel", excel_data, f"Reporte_{mes_actual}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        with col_ed:
            if not ver_consolidado: # Solo se editan filas individuales, no consolidados
                sel_id = st.selectbox("Seleccione ID para editar", df_mostrar["id"].tolist())
                if st.button("✏️ Editar Fila Seleccionada"):
                    fila_editar = df_mostrar[df_mostrar["id"] == sel_id].iloc[0]
                    editar_registro(fila_editar)
    else:
        st.info("No hay datos para mostrar.")