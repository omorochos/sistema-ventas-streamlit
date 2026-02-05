import streamlit as st
import pandas as pd
from supabase import create_client, Client
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Proyecciones PRO", layout="wide")

# --- CONEXIÓN A SUPABASE ---
try:
    URL: str = st.secrets["SUPABASE_URL"]
    KEY: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL, KEY)
except Exception as e:
    st.error(f"Error en las credenciales de Secrets: {e}")

# --- CARGAR MEGA BASE DE PRODUCTOS ---
@st.cache_data(ttl=60)
def obtener_productos_maestros():
    try:
        res = supabase.table("Productos").select("*").execute()
        if not res.data:
            return pd.DataFrame()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"⚠️ Error de conexión con Supabase: {e}")
        return pd.DataFrame()

df_maestro = obtener_productos_maestros()

# --- FUNCIÓN EXCEL ---
def generar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Proyecciones')
    return output.getvalue()

# --- VENTANAS EMERGENTES (DIALOGS) ---
@st.dialog("Registro de Proyección", width="large")
def formulario_nuevo():
    if "carrito_proyeccion" not in st.session_state:
        st.session_state.carrito_proyeccion = []

    if df_maestro.empty:
        st.error("No se pudieron cargar productos. Revisa tu API Key y las políticas RLS en Supabase.")
        return

    # Detectamos nombres de columnas (Mayúsculas o minúsculas)
    c_cli = "cliente" if "cliente" in df_maestro.columns else "Cliente"
    c_pro = "producto" if "producto" in df_maestro.columns else "Producto"
    c_sec = "sector" if "sector" in df_maestro.columns else "Sector"
    c_pre = "precio" if "precio" in df_maestro.columns else "Precio"
    c_pes = "peso" if "peso" in df_maestro.columns else "Peso"

    with st.container(border=True):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
            lista_clientes = sorted(df_maestro[c_cli].unique().tolist())
            cliente_sel = st.selectbox("Cliente", lista_clientes)
        with col2:
            prods_filtro = df_maestro[df_maestro[c_cli] == cliente_sel]
            prod_sel = st.selectbox("Producto", prods_filtro[c_pro].tolist())
            cant_sel = st.number_input("Cantidad", min_value=1, step=1)
        with col3:
            st.write("###")
            if st.button("➕ Añadir"):
                info = prods_filtro[prods_filtro[c_pro] == prod_sel].iloc[0]
                st.session_state.carrito_proyeccion.append({
                    "vendedor": st.session_state.usuario_logueado, 
                    "mes": mes_sel, 
                    "cliente": cliente_sel,
                    "producto": prod_sel, 
                    "sector": info[c_sec],
                    "total_s": float(info[c_pre] * cant_sel),
                    "total_kg": float(info[c_pes] * cant_sel)
                })

    if st.session_state.carrito_proyeccion:
        st.write("### Vista previa del registro")
        st.table(pd.DataFrame(st.session_state.carrito_proyeccion))
        
        if st.button("💾 GUARDAR EN NUBE"):
            try:
                # Convertimos a lista de diccionarios
                datos_a_guardar = pd.DataFrame(st.session_state.carrito_proyeccion).to_dict(orient='records')
                
                # Eliminamos la columna 'id' si por error se coló en el carrito
                # Esto permite que Supabase use su propia secuencia autoincrementable
                for fila in datos_a_guardar:
                    fila.pop('id', None) 
                
                # Enviamos a la tabla 'ventas'
                resultado = supabase.table("ventas").insert(datos_a_guardar).execute()
                
                if resultado.data:
                    st.success("¡Proyección guardada con éxito en la nube!")
                    st.session_state.carrito_proyeccion = [] # Limpiamos el carrito local
                    st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

# --- LOGIN Y CUERPO PRINCIPAL ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado = True
            st.session_state.usuario_logueado = u
            st.rerun()
else:
    st.sidebar.title(f"Hola, {st.session_state.usuario_logueado}")
    if st.sidebar.button("📄 Nuevo Registro"): formulario_nuevo()
    if st.sidebar.button("🚪 Salir"):
        st.session_state.autenticado = False
        st.rerun()

    # Mostrar tabla de ventas actual
    st.subheader("Mis Proyecciones")
    try:
        res_v = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).execute()
        df_ventas = pd.DataFrame(res_v.data)
        if not df_ventas.empty:
            st.dataframe(df_ventas, use_container_width=True)
        else:
            st.info("No tienes registros guardados aún.")
    except:
        st.warning("No se pudieron cargar las ventas. Verifica la conexión.")