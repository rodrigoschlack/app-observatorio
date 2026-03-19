import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
import plotly.express as px  # Librería para gráficos profesionales

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

# --- TAB 1: FORMULARIO DE INGRESO ---
with tab1:
    st.header("Registrar Nuevo Incidente")
    with st.form("formulario_registro", clear_on_submit=True):
        col_f, col_d = st.columns(2)
        with col_f:
            fecha_input = st.date_input("Fecha del Suceso", datetime.now())
        with col_d:
            direccion_input = st.text_input("Dirección / Ubicación", placeholder="Ej: Tegualda 305")
            
        tipo_delito = st.selectbox("Tipo de Delito", ["RLH", "Robo", "Hurto", "Vandalismo", "Asalto", "Otro"])
        
        # Casillas de verificación solicitadas
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1: tiene_imagenes = st.checkbox("¿Se recopilaron Imágenes?")
        with col_c2: tiene_videos = st.checkbox("¿Se recopilaron Videos?")
        with col_c3: es_relevante = st.checkbox("¿Es un caso relevante?")
            
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
                st.success(f"✅ Registro guardado correctamente.")
            else:
                st.error("No hay conexión con la base de datos.")

# --- TAB 2: ANALÍTICA Y REPORTES (MEJORADA PARA MÓVIL) ---
with tab2:
    st.header("Panel de Análisis de Datos")
    
    if client:
        try:
            db = client['observatorio_seguridad']
            coleccion = db['registro_delitos']
            datos = list(coleccion.find())
            
            if datos:
                df = pd.DataFrame(datos)
                
                # Unificación de columnas Excel + Formulario
                mapeo = {
                    'Fecha': 'fecha', 'Dirección': 'direccion', 
                    'Tipo de delito': 'tipo_delito', 'Relevante': 'es_relevante',
                    'Imágenes': 'tiene_imagenes', 'Videos': 'tiene_videos'
                }
                for cv, cn in mapeo.items():
                    if cv in df.columns:
                        if cn not in df.columns: df[cn] = None
                        df[cn] = df[cn].fillna(df[cv])
                
                # Limpieza de valores Sí/No a Booleanos
                for c in ['es_relevante', 'tiene_imagenes', 'tiene_videos']:
                    if c in df.columns:
                        df[c] = df[c].astype(str).str.lower().isin(['true', 'si', '1', 'yes'])

                # Orden cronológico (2026 arriba)
                df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
                df = df.sort_values(by='fecha', ascending=False)
                
                # Buscador de Direcciones
                busqueda = st.text_input("🔍 Buscar dirección:", placeholder="Ej: Tegualda...")
                if busqueda:
                    df = df[df['direccion'].astype(str).str.contains(busqueda, case=False, na=False)]

                # Métricas Rápidas
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Registros", len(df))
                m2.metric("Casos Relevantes", int(df['es_relevante'].sum()))
                m3.metric("Con Imágenes", int(df['tiene_imagenes'].sum()))

                # --- GRÁFICO HORIZONTAL PARA MÓVIL ---
                st.subheader("Resumen por Tipo de Delito")
                if 'tipo_delito' in df.columns:
                    # Contamos los datos
                    conteo = df['tipo_delito'].value_counts().reset_index()
                    conteo.columns = ['Delito', 'Cantidad']
                    
                    # Creamos el gráfico horizontal con Plotly
                    fig = px.bar(conteo, 
                                 x='Cantidad', 
                                 y='Delito', 
                                 orientation='h',
                                 text='Cantidad', # Muestra el número exacto al lado
                                 color='Delito',
                                 color_discrete_sequence=px.colors.qualitative.Safe)
                    
                    # Ajustes de diseño para que no se mueva en el celular
                    fig.update_layout(
                        showlegend=False, 
                        height=400, 
                        margin=dict(l=0, r=0, t=10, b=10),
                        yaxis={'categoryorder':'total ascending'} # El más frecuente arriba
                    )
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

                # Tabla de Datos
                st.subheader("Base de Datos Completa")
                df_ver = df[['fecha', 'direccion', 'tipo_delito', 'es_relevante']].copy()
                df_ver['fecha'] = df_ver['fecha'].dt.strftime('%d-%m-%Y')
                
                # Iconos para que se entienda mejor en pantalla chica
                for c in ['es_relevante']:
                    df_ver[c] = df_ver[c].map({True: '✅ Si', False: '❌ No'})
                
                st.dataframe(df_ver, use_container_width=True, hide_index=True)

            else:
                st.info("Aún no hay datos para mostrar.")
        except Exception as e:
            st.error(f"Error al procesar analítica: {e}")
