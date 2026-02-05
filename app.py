import streamlit as st
import pandas as pd
from supabase import create_client, Client
from io import BytesIO
import time

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
    st.info("Modifica los Kg. Los cambios se enviarán uno por uno a la base de datos.")
    
    cambios_a_realizar = []
    
    for i, fila in filas_seleccionadas.iterrows():
        with st.container(border=True):
            st.markdown(f"**ID:** {fila['id']} | **Cliente:** {fila['cliente']} | **Producto:** {fila['producto']}")
            
            # Input de KG
            n_kg = st.number_input(
                f"Nuevos Kg", 
                value=float(fila['total_kg']), 
                min_value=0.0,
                key=f"input_edit_{fila['id']}"
            )
            
            # Recalcular soles basado en el precio unitario original
            # total_s / total_kg = precio por kg
            precio_unitario = float(fila['total_s']) / float(fila['total_kg']) if float(fila['total_kg']) > 0 else 0
            n_s = n_kg * precio_unitario
            
            cambios_a_realizar.append({
                "id": int(fila['id']),
                "total_kg": float(n_kg),
                "total_s": float(n_s)
            })
    
    st.divider()
    
    if st.button("💾 CONFIRMAR Y GUARDAR EN NUBE", type="primary", use_container_width=True):
        exitos = 0
        errores = 0
        
        with st.spinner("Conectando con Supabase..."):
            for cambio in cambios_a_realizar:
                try:
                    # EJECUCIÓN DIRECTA
                    resultado = supabase.table("ventas").update({
                        "total_kg": cambio["total_kg"],
                        "total_s": cambio["total_s"]
                    }).eq("id", cambio["id"]).execute()
                    
                    # Verificamos si realmente se editó algo
                    if len(resultado.data) > 0:
                        exitos += 1
                    else:
                        st.error(f"No se encontró el registro ID {cambio['id']} para actualizar.")
                except Exception as e:
                    st.error(f"Error en ID {cambio['id']}: {str(e)}")
                    errores += 1
        
        if exitos > 0:
            st.success(f"✅ Se actualizaron {exitos} registros correctamente.")
            time.sleep(1) # Pausa pequeña para que veas el mensaje
            st.cache_data.clear() # Limpia cualquier dato viejo
            st.rerun()

# --- CUERPO PRINCIPAL ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False

if st.session_state.autenticado:
    st.sidebar.title(f"Usuario: {st.session_state.usuario_logueado}")
    mes_consulta = st.sidebar.selectbox("Mes de consulta", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    
    # BOTÓN DE SALIR (Opcional pero útil)
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

    # CARGA DE DATOS SIN CACHÉ (PARA VER CAMBIOS REALES)
    res_v = supabase.table("ventas").select("*").eq("vendedor", st.session_state.usuario_logueado).execute()
    df_ventas = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()

    if not df_ventas.empty:
        df_mostrar = df_ventas[df_ventas["mes"] == mes_consulta].copy()
        
        st.subheader(f"📅 Proyecciones de {mes_consulta}")
        
        if not df_mostrar.empty:
            # PREPARAR TABLA PARA SELECCIÓN
            df_mostrar.insert(0, "Sel", False)
            
            # EDITOR DE DATOS
            edited_df = st.data_editor(
                df_mostrar,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Sel": st.column_config.CheckboxColumn("✔", default=False),
                    "id": st.column_config.NumberColumn("ID", disabled=True),
                    "vendedor": None # Ocultar para ganar espacio
                },
                disabled=[c for c in df_mostrar.columns if c != "Sel"]
            )

            # ACCIONES
            col_izq, col_der = st.columns(2)
            with col_izq:
                st.download_button("📥 Excel", generar_excel(df_mostrar.drop(columns=["Sel"])), f"Data_{mes_consulta}.xlsx")
            
            with col_der:
                seleccionados = edited_df[edited_df["Sel"] == True]
                if not seleccionados.empty:
                    if st.button(f"✏️ Editar {len(seleccionados)} filas seleccionadas", type="primary", use_container_width=True):
                        editar_multiple(seleccionados)
        else:
            st.warning(f"No hay datos registrados para {mes_consulta}.")
    else:
        st.info("No hay registros en la base de datos.")

else:
    st.title("Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Password", type="password")
    if st.button("Entrar"):
        if u == "MARIA_AVILA" and p == "maria2026":
            st.session_state.autenticado, st.session_state.usuario_logueado = True, u
            st.rerun()