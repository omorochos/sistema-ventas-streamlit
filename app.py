import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sistema Proyecciones PRO", layout="wide")

# Conexión Segura
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Error de conexión: {e}")

# --- CARGA DE DATOS ---
@st.cache_data(ttl=60)
def obtener_productos():
    try:
        res = supabase.table("Productos").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except:
        return pd.DataFrame()

df_maestro = obtener_productos()

# --- FORMULARIO DE REGISTRO ---
@st.dialog("Registro de Proyección", width="large")
def formulario_nuevo():
    if "carrito" not in st.session_state: st.session_state.carrito = []
    
    if df_maestro.empty:
        st.error("No hay productos. Revisa las políticas RLS de la tabla 'Productos'.")
        return

    # Columnas según tu tabla 'Productos' (image_3aaefb.png)
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        mes = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
        cliente = st.selectbox("Cliente", sorted(df_maestro["cliente"].unique().tolist()))
    with col2:
        prods = df_maestro[df_maestro["cliente"] == cliente]
        prod_sel = st.selectbox("Producto", prods["producto"].tolist())
        cant = st.number_input("Cantidad", min_value=1, step=1)
    with col3:
        st.write("###")
        if st.button("➕ Añadir"):
            info = prods[prods["producto"] == prod_sel].iloc[0]
            st.session_state.carrito.append({
                "vendedor": st.session_state.usuario_logueado,
                "mes": mes,
                "cliente": cliente,
                "producto": prod_sel,
                "sector": info["sector"],
                "total_s": float(info["precio"] * cant),
                "total_kg": float(info["peso"] * cant)
            })

    if st.session_state.carrito:
        st.write("### Vista previa del registro")
        df_preview = pd.DataFrame(st.session_state.carrito)
        st.table(df_preview)
        
        if st.button("💾 GUARDAR EN NUBE"):
            try:
                # Quitamos cualquier ID manual para que Supabase use el Autoincrement (Is Identity)
                datos_finales = df_preview.to_dict(orient='records')
                for fila in datos_finales:
                    fila.pop('id', None) 
                
                res = supabase.table("ventas").insert(datos_finales).execute()
                if res.data:
                    st.success("¡Datos guardados exitosamente!")
                    st.session_state.carrito = []
                    st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

# --- LÓGICA DE ACCESO ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("Acceso Sistema")
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado, st.session_state.usuario_logueado = True, u
            st.rerun()
else:
    st.sidebar.title(f"Usuario: {st.session_state.usuario_logueado}")
    if st.sidebar.button("📄 Nuevo Registro"): formulario_nuevo()
    if st.sidebar.button("🚪 Salir"):
        st.session_state.autenticado = False
        st.rerun()

    # Tabla principal
    st.subheader("Mis Proyecciones Guardadas")
    res_v = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).execute()
    if res_v.data:
        st.dataframe(pd.DataFrame(res_v.data), use_container_width=True)
    else:
        st.info("Aún no tienes proyecciones en la nube.")