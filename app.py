import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema de Proyecciones v2", layout="wide")

# --- FUNCIONES DE BASE DE DATOS ---
def conectar_db():
    return sqlite3.connect('proyecciones.db')

def crear_tabla():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendedor TEXT,
            mes TEXT,
            cliente TEXT,
            producto TEXT,
            sector TEXT,
            total_s REAL,
            total_kg REAL
        )
    ''')
    conn.commit()
    conn.close()

crear_tabla()

# --- DATOS MAESTROS ---
DATA_MAESTRA = {
    "DELOSI S.A": ["KIT FOOD 6", "NEOCLOR DX PLUS"],
    "CINEPLANET": ["LIMPIADOR MULTIUSOS", "DESINFECTANTE"],
    "SAGA FALABELLA": ["PRODUCTO A", "PRODUCTO B"]
}

INFO_PRODUCTOS = {
    "KIT FOOD 6": {"sector": "Alimentos y Bebidas", "precio": 15.5, "peso": 1.2},
    "NEOCLOR DX PLUS": {"sector": "Alimentos y Bebidas", "precio": 145.0, "peso": 23.404},
    "LIMPIADOR MULTIUSOS": {"sector": "Limpieza", "precio": 10.0, "peso": 5.0},
    "DESINFECTANTE": {"sector": "Limpieza", "precio": 12.0, "peso": 1.0},
    "PRODUCTO A": {"sector": "Retail", "precio": 20.0, "peso": 0.5},
    "PRODUCTO B": {"sector": "Retail", "precio": 25.0, "peso": 1.0}
}

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

    vendedor = st.session_state.usuario_logueado
    
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            mes = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
            cliente = st.selectbox("Cliente", list(DATA_MAESTRA.keys()))
        with c2:
            producto = st.selectbox("Producto", DATA_MAESTRA[cliente])
            cantidad = st.number_input("Cantidad", min_value=1, step=1)
        with c3:
            st.write("###")
            if st.button("➕ Añadir"):
                info = INFO_PRODUCTOS[producto]
                item = {
                    "vendedor": vendedor,
                    "mes": mes,
                    "cliente": cliente,
                    "producto": producto,
                    "sector": info["sector"],
                    "Monto Soles": info["precio"] * cantidad,
                    "Kg": info["peso"] * cantidad
                }
                st.session_state.carrito_proyeccion.append(item)

    if st.session_state.carrito_proyeccion:
        st.write("### 📝 Lista por Guardar")
        df_temp = pd.DataFrame(st.session_state.carrito_proyeccion)
        st.dataframe(df_temp[["mes", "cliente", "producto", "Monto Soles", "Kg"]], use_container_width=True, hide_index=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Borrar Lista"):
                st.session_state.carrito_proyeccion = []
                st.rerun()
        with col2:
            if st.button("💾 GUARDAR TODO EN BASE DE DATOS"):
                conn = conectar_db()
                cursor = conn.cursor()
                for i in st.session_state.carrito_proyeccion:
                    cursor.execute('''
                        INSERT INTO ventas (vendedor, mes, cliente, producto, sector, total_s, total_kg)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (i["vendedor"], i["mes"], i["cliente"], i["producto"], i["sector"], i["Monto Soles"], i["Kg"]))
                conn.commit()
                conn.close()
                st.session_state.carrito_proyeccion = []
                st.success("¡Todo se guardó correctamente!")
                st.rerun()
    else:
        st.info("La lista está vacía. Agrega productos arriba.")

@st.dialog("Actualizar Registro", width="large")
def formulario_actualizar(fila_seleccionada):
    st.write(f"### Editando: {fila_seleccionada['cliente']}")
    st.write(f"Producto: {fila_seleccionada['producto']}")
    nueva_cantidad = st.number_input("Actualizar cantidad de unidades:", min_value=1, step=1)
    
    if st.button("Confirmar Actualización"):
        info = INFO_PRODUCTOS[fila_seleccionada['producto']]
        nuevo_total_s = info["precio"] * nueva_cantidad
        nuevo_total_kg = info["peso"] * nueva_cantidad
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE ventas SET total_s = ?, total_kg = ?
            WHERE cliente = ? AND producto = ? AND vendedor = ?
        ''', (nuevo_total_s, nuevo_total_kg, fila_seleccionada['cliente'], fila_seleccionada['producto'], st.session_state.usuario_logueado))
        conn.commit()
        conn.close()
        st.success("Actualizado con éxito")
        st.rerun()

# --- LÓGICA DE ACCESO ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("Acceso al Sistema")
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado = True
            st.session_state.usuario_logueado = u
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
else:
    # --- 1. PRIMERO DEFINIMOS LOS FILTROS PARA PODER CONSULTAR LA DATA ---
    st.sidebar.header("Filtros de Vista")
    mes_consulta = st.sidebar.selectbox("Mes a consultar:", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    ver_consolidado = st.sidebar.toggle("Ver Consolidado (3 meses anteriores)")

    # --- 2. OBTENCIÓN DE DATOS DINÁMICOS ---
    conn = conectar_db()
    meses_orden = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    if ver_consolidado:
        idx = meses_orden.index(mes_consulta)
        meses_a_buscar = [meses_orden[i] for i in range(max(0, idx-3), idx)]
        if not meses_a_buscar: meses_a_buscar = [mes_consulta]
        
        query = f"""
            SELECT cliente, producto, SUM(total_s) as 'Monto Soles', SUM(total_kg) as 'Kg Proyectados'
            FROM ventas 
            WHERE vendedor='{st.session_state.usuario_logueado}' 
            AND mes IN ({str(meses_a_buscar)[1:-1]})
            GROUP BY cliente, producto
        """
        nombre_archivo = f"Consolidado_{mes_consulta}.xlsx"
    else:
        query = f"""
            SELECT cliente, producto, total_s as 'Monto Soles', total_kg as 'Kg Proyectados'
            FROM ventas 
            WHERE vendedor='{st.session_state.usuario_logueado}' AND mes='{mes_consulta}'
        """
        nombre_archivo = f"Proyeccion_{mes_consulta}.xlsx"

    df = pd.read_sql_query(query, conn)
    conn.close()

    # Columnas requeridas
    df["Ventas kg"] = "" 
    df["Total"] = ""     
    df["Etapa de Venta"] = "Propuesta Económica"
    columnas_finales = ["cliente", "producto", "Monto Soles", "Kg Proyectados", "Ventas kg", "Total", "Etapa de Venta"]
    df = df[columnas_finales]
    st.session_state.df_actual = df 

    # --- 3. BARRA SUPERIOR DE BOTONES (AHORA YA SABE QUÉ DESCARGAR) ---
    col_btns = st.columns([1, 1.2, 1.5, 1, 4])
    
    with col_btns[0]:
        if st.button("📄 Nuevo"): formulario_nuevo()
    
    with col_btns[1]:
        if st.button("🔄 Actualizar"):
            if "seleccion" in st.session_state and not st.session_state.seleccion.empty:
                formulario_actualizar(st.session_state.seleccion.iloc[0])
            else: st.warning("Selecciona una fila")

    with col_btns[2]:
        excel_bin = generar_excel(st.session_state.df_actual)
        st.download_button(
            label="📊 Transformar Excel",
            data=excel_bin,
            file_name=nombre_archivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    with col_btns[3]:
        if st.button("🚪 Salir"):
            st.session_state.autenticado = False
            st.rerun()

    st.divider()

    # --- 4. TABLA INTERACTIVA ---
    st.write(f"### Vista: {'Consolidado' if ver_consolidado else 'Mes Individual'}")
    
    event = st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    if len(event.selection.rows) > 0:
        st.session_state.seleccion = df.iloc[event.selection.rows]
    else:
        st.session_state.seleccion = pd.DataFrame()

    # --- TOTALES ---
    st.divider()
    t1, t2 = st.columns(2)
    with t1: st.metric("Total Soles", f"S/ {df['Monto Soles'].sum():,.2f}")
    with t2: st.metric("Total Kg Proyectados", f"{df['Kg Proyectados'].sum():,.2f}")