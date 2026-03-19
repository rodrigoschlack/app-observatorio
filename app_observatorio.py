import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Observatorio de Seguridad", layout="wide", page_icon="🛡️")

# 1. Conexión segura a MongoDB
@st.cache_resource
def iniciar_conexion():
    try:
        if "mongo" in st.secrets and "uri" in st.secrets["mongo"]:
            uri = st.secrets["mongo"]["uri"]
            return MongoClient(uri)
        else:
            st.error("❌ No se encontró la clave 'uri' en los Secrets de Streamlit.")
            return None
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None

client = iniciar_conexion()

# 2. Interfaz Principal
st.title("🛡️ Sistema Central - Observatorio de Seguridad")
st.markdown("---")

tab1, tab2 = st.tabs(["📝 Ingreso de Datos", "📊 Analítica y Reportes"])

# --- TAB 1: INGRESO ---
with tab1:
    st.header("Registrar Nuevo Incidente")
    with st.form("formulario_registro", clear_on_submit=True):
        col_f, col_d = st.columns(2)
        with col_f:
            fecha_input = st.date_input("Fecha del Suceso", datetime.now())
        with col_d:
            direccion_input = st.text_input("Dirección / Ubicación", placeholder="Ej: Av. La Florida 1234")
            
        tipo_delito = st.selectbox("Tipo de Delito", ["Robo", "Hurto", "Vandalismo", "Asalto", "RLH", "Otro"])
        es_relevante = st.checkbox("¿Es un caso relevante?")
        detalles = st.text_area("Detalles del caso")
        
        btn = st.form_submit_button("Guardar Registro")
        
        if btn:
            if client:
                db = client['observatorio_seguridad']
                coleccion = db['registro_delitos']
                nuevo = {
                    "fecha": datetime.combine(fecha_input, datetime.min.time()),
                    "direccion": direccion_input,
                    "tipo_delito": tipo_delito,
                    "es_relevante": es_relevante,
                    "detalles": detalles,
                    "fecha_registro": datetime.now()
                }
                coleccion.insert_one(nuevo)
                st.success(f"✅ Guardado: {direccion_input}")
            else:
                st.error("No hay conexión con la base de datos.")

# --- TAB 2: ANALÍTICA (EL QUE ESTABA EN BLANCO) ---
with tab2:
    st.header("Panel de Análisis de Datos")
    
    if client:
        try:
            db = client['observatorio_seguridad']
            coleccion = db['registro_delitos']
            datos = list(coleccion.find())
            
            if datos:
                df = pd.DataFrame(datos)
                
                # --- UNIFICACIÓN DE COLUMNAS ---
                mapeo = {'Fecha': 'fecha', 'Dirección': 'direccion', 'Tipo de delito': 'tipo_delito', 'Relevante': 'es_relevante'}
                for col_vieja, col_nueva in mapeo.items():
                    if col_vieja in df.columns:
                        if col_nueva not in df.columns: df[col_nueva] = None
                        df[col_nueva] = df[col_nueva].fillna(df[col_vieja])
                
                # --- LIMPIEZA Y ORDEN (2026 ARRIBA) ---
                df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
                df = df.sort_values(by='fecha', ascending=False)
                
                # Asegurar que 'direccion' sea texto para el buscador
                df['direccion'] = df['direccion'].fillna("Sin Dirección").astype(str)

                # --- BUSCADOR ---
                st.subheader("🔍 Buscador de Direcciones")
                busqueda = st.text_input("Filtrar por calle:", placeholder="Ej: Vicuña Mackenna...")
                if busqueda:
                    df = df[df['direccion'].str.contains(busqueda, case=False)]

                # --- MÉTRICAS ---
                m1, m2, m3 = st.columns(3)
                m1.metric("Total de Registros", len(df))
                
                # Cálculo seguro de relevantes
                if 'es_relevante' in df.columns:
                    # Convierte valores como "Si" o True a booleanos reales
                    relev_bool = df['es_relevante'].astype(str).str.lower().isin(['true', 'si', '1'])
                    m2.metric("Casos Relevantes", int(relev_bool.sum()))
                else:
                    m2.metric("Casos Relevantes", 0)
                
                m3.metric("Última Fecha", df['fecha'].dt.strftime('%d-%m-%Y').iloc[0] if not df.empty else "N/A")

                # --- TABLA ---
                st.subheader("Base de Datos (Más recientes primero)")
                cols_ok = ['fecha', 'direccion', 'tipo_delito', 'es_relevante']
                # Solo mostrar columnas que existan para evitar errores
                df_ver = df[[c for c in cols_ok if c in df.columns]].copy()
                df_ver['fecha'] = df_ver['fecha'].dt.strftime('%d-%m-%Y')
                
                st.dataframe(df_ver, use_container_width=True, hide_index=True)
                
                # --- GRÁFICO ---
                if 'tipo_delito' in df.columns:
                    st.subheader("Delitos por Tipo")
                    st.bar_chart(df['tipo_delito'].value_counts())
            else:
                st.info("Aún no hay datos en MongoDB Atlas. Ingresa uno en la otra pestaña.")
                
        except Exception as e:
            st.error(f"Ocurrió un error al cargar los datos: {e}")
    else:
        st.error("No se pudo establecer la conexión con MongoDB.")
