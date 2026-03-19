import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Observatorio de Seguridad", layout="wide", page_icon="🛡️")

# 1. Conexión a MongoDB Atlas
@st.cache_resource
def iniciar_conexion():
    try:
        if "mongo" in st.secrets and "uri" in st.secrets["mongo"]:
            uri = st.secrets["mongo"]["uri"]
            return MongoClient(uri)
        else:
            st.error("❌ Configuración faltante: Verifica los Secrets en Streamlit.")
            return None
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None

client = iniciar_conexion()

# 2. Interfaz Principal
st.title("🛡️ Sistema Central - Observatorio de Seguridad")
st.markdown("---")

tab1, tab2 = st.tabs(["📝 Ingreso de Datos", "📊 Analítica y Reportes"])

# --- TAB 1: FORMULARIO DE INGRESO (CON TODAS LAS CASILLAS) ---
with tab1:
    st.header("Registrar Nuevo Incidente")
    with st.form("formulario_registro", clear_on_submit=True):
        col_f, col_d = st.columns(2)
        with col_f:
            fecha_input = st.date_input("Fecha del Suceso", datetime.now())
        with col_d:
            direccion_input = st.text_input("Dirección / Ubicación", placeholder="Ej: Tegualda 305")
            
        tipo_delito = st.selectbox("Tipo de Delito", ["RLH", "Robo", "Hurto", "Vandalismo", "Asalto", "Otro"])
        
        # Nuevas casillas solicitadas
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            tiene_imagenes = st.checkbox("¿Se recopilaron Imágenes?")
        with col_c2:
            tiene_videos = st.checkbox("¿Se recopilaron Videos?")
        with col_c3:
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
                    "tiene_imagenes": tiene_imagenes,
                    "tiene_videos": tiene_videos,
                    "es_relevante": es_relevante,
                    "detalles": detalles,
                    "fecha_registro": datetime.now()
                }
                coleccion.insert_one(nuevo)
                st.success(f"✅ Registro en {direccion_input} guardado correctamente.")
            else:
                st.error("No hay conexión con la base de datos.")

# --- TAB 2: ANALÍTICA Y REPORTES ---
with tab2:
    st.header("Panel de Análisis de Datos")
    
    if client:
        try:
            db = client['observatorio_seguridad']
            coleccion = db['registro_delitos']
            datos = list(coleccion.find())
            
            if datos:
                df = pd.DataFrame(datos)
                
                # --- UNIFICACIÓN DE COLUMNAS (Mapeo de Excel a Formulario) ---
                mapeo = {
                    'Fecha': 'fecha', 
                    'Dirección': 'direccion', 
                    'Tipo de delito': 'tipo_delito', 
                    'Relevante': 'es_relevante',
                    'Imágenes': 'tiene_imagenes',
                    'Videos': 'tiene_videos'
                }
                
                for col_vieja, col_nueva in mapeo.items():
                    if col_vieja in df.columns:
                        if col_nueva not in df.columns: df[col_nueva] = None
                        df[col_nueva] = df[col_nueva].fillna(df[col_vieja])
                
                # --- LIMPIEZA DE DATOS ---
                # Convertir "Si"/"No" del Excel a Verdadero/Falso para que la tabla sea uniforme
                cols_bool = ['es_relevante', 'tiene_imagenes', 'tiene_videos']
                for col in cols_bool:
                    if col in df.columns:
                        df[col] = df[col].astype(str).str.lower().isin(['true', 'si', '1', 'yes'])

                # Ordenar por fecha (2026 primero)
                df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
                df = df.sort_values(by='fecha', ascending=False)
                
                # Buscador
                st.subheader("🔍 Buscador de Direcciones")
                busqueda = st.text_input("Filtrar por calle:", placeholder="Ej: Tegualda...")
                if busqueda:
                    df = df[df['direccion'].astype(str).str.contains(busqueda, case=False, na=False)]

                # Métricas
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Registros", len(df))
                m2.metric("Casos Relevantes", int(df['es_relevante'].sum()))
                m3.metric("Con Imágenes", int(df['tiene_imagenes'].sum()))

                # Tabla Final
                st.subheader("Base de Datos Completa")
                # Seleccionar y renombrar columnas para que se vean bien
                cols_mostrar = {
                    'fecha': 'Fecha',
                    'direccion': 'Dirección',
                    'tipo_delito': 'Delito',
                    'tiene_imagenes': 'Imágenes',
                    'tiene_videos': 'Videos',
                    'es_relevante': 'Relevante'
                }
                
                df_ver = df[[c for c in cols_mostrar.keys() if c in df.columns]].copy()
                df_ver['fecha'] = df_ver['fecha'].dt.strftime('%d-%m-%Y')
                
                # Convertir True/False a Si/No solo para la vista visual
                for c in ['tiene_imagenes', 'tiene_videos', 'es_relevante']:
                    if c in df_ver.columns:
                        df_ver[c] = df_ver[c].map({True: '✅ Si', False: '❌ No'})

                st.dataframe(df_ver, use_container_width=True, hide_index=True)
                
                # Gráfico
                st.subheader("Resumen por Tipo de Delito")
                st.bar_chart(df['tipo_delito'].value_counts())

            else:
                st.info("No hay datos para mostrar.")
        except Exception as e:
            st.error(f"Error al cargar analítica: {e}")
