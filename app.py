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

# --- DIALOG: EDICIÓN DE FILA ---
@st.dialog("Editar Registro")
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
        if st.button("🗑️ Eliminar Fila"):
            supabase.table("ventas").delete().eq("id", fila['id']).execute()
            st.warning("Registro eliminado")
            st.rerun()

# --- DIALOG: NUEVO REGISTRO ---
@st.dialog("Registro de Proyección", width="large")
def formulario_nuevo(df_m):
    if "carrito" not in st.session_state: st.session_state.carrito = []
    c1, c2 = st.columns(2)
    with c1:
        mes = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
        cliente = st.selectbox("Cliente", sorted(df_m["cliente"].unique().tolist()))
    with c2:
        prods = df_m[df_m["cliente"] == cliente]
        prod_sel = st.selectbox("Producto", prods["producto"].tolist())
        cant = st.number_input("Cantidad", min_value=1, step=1)
    
    if st.button("➕ Añadir"):
        info = prods[prods["producto"] == prod_sel].iloc[0]
        st.session_state.carrito.append({
            "vendedor": st.session_state.usuario_logueado, "mes": mes, "cliente": cliente,
            "producto": prod_sel, "sector": info["sector"],
            "total_s": float(info["precio"] * cant), "total_kg": float(info["peso"] * cant)
        })
    
    if st.session_state.carrito:
        st.table(pd.DataFrame(st.session_state.carrito))
        if st.button("💾 Enviar a la Nube"):
            datos = pd.DataFrame(st.session_state.carrito).to_dict(orient='records')
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
    
    # Sidebar
    st.sidebar.title(f"Hola, {st.session_state.usuario_logueado}")
    if st.sidebar.button("📄 Nuevo Registro"): formulario_nuevo(df_maestro)
    
    st.sidebar.divider()
    mes_consulta = st.sidebar.selectbox("Mes de consulta", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    ver_consolidado = st.sidebar.toggle("Ver Consolidado (3 meses anteriores)")

    # Carga de ventas desde Supabase
    res_v = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).execute()
    df_ventas = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()

    if not df_ventas.empty:
        meses_lista = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        idx = meses_lista.index(mes_consulta)
        
        if ver_consolidado:
            meses_interes = meses_lista[max(0, idx-3):idx+1]
            df_mostrar = df_ventas[df_ventas["mes"].isin(meses_interes)]
            df_mostrar = df_mostrar.groupby(["cliente", "producto", "sector"]).agg({"total_s": "sum", "total_kg": "sum"}).reset_index()
            st.subheader(f"📊 Consolidado: {', '.join(meses_interes)}")
        else:
            df_mostrar = df_ventas[df_ventas["mes"] == mes_consulta]
            st.subheader(f"📅 Proyecciones de {mes_consulta}")

        # --- SELECCIÓN DE FILA (LOS CIRCULITOS) ---
        if not df_mostrar.empty:
            # Creamos una columna de selección amigable
            opciones = df_mostrar.apply(lambda x: f"ID {x.get('id', 'S/N')} | {x['cliente']} - {x['producto']}", axis=1).tolist()
            
            col_tabla, col_accion = st.columns([3, 1])
            
            with col_tabla:
                st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
            
            with col_accion:
                st.write("### Acciones")
                excel_bin = generar_excel(df_mostrar)
                st.download_button("📥 Descargar Excel", excel_bin, f"Reporte_{mes_consulta}.xlsx", use_container_width=True)
                
                if not ver_consolidado:
                    fila_sel_text = st.radio("Seleccione una fila para editar:", opciones)
                    if st.button("✏️ Editar Seleccionado", use_container_width=True):
                        # Extraemos el ID del texto seleccionado
                        id_sel = int(fila_sel_text.split(" | ")[0].replace("ID ", ""))
                        fila_data = df_mostrar[df_mostrar["id"] == id_sel].iloc[0]
                        editar_registro(fila_data)
        else:
            st.info(f"No hay datos para {mes_consulta}")
    else:
        st.info("No hay registros en la base de datos.")