import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime

# Configuración de la página (Ancho completo)
st.set_page_config(page_title="Observatorio de Seguridad", layout="wide", page_icon="🛡️")

# 1. Conexión a la base de datos (Usa los Secrets de Streamlit)
@st.cache_resource
def iniciar_conexion():
    try:
        uri = st.secrets["mongo"]["uri"]
        return MongoClient(uri)
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

client = iniciar_conexion()
db = client['observatorio_seguridad']
coleccion = db['registro_delitos']

# Título Principal
st.title("🛡️ Sistema Central - Observatorio de Seguridad")
st.markdown("---")

# Crear pestañas: Ingreso y Visualización
tab1, tab2 = st.tabs(["📝 Ingreso de Datos", "📊 Analítica y Reportes"])

# --- TAB 1: FORMULARIO DE INGRESO ---
with tab1:
    st.header("Registrar Nuevo Incidente")
    with st.form("formulario_registro", clear_on_submit=True):
        col_f, col_d = st.columns(2)
        with col_f:
            fecha = st.date_input("Fecha del Suceso", datetime.now())
        with col_d:
            direccion = st.text_input("Dirección / Ubicación", placeholder="Ej: Av. La Florida 1234")
            
        tipo_delito = st.selectbox("Tipo de Delito", ["Robo", "Hurto", "Vandalismo", "Asalto", "RLH", "Otro"])
        es_relevante = st.checkbox("¿Es un caso relevante para seguimiento?")
        detalles = st.text_area("Detalles o descripción del caso")
        
        boton_guardar = st.form_submit_button("Guardar en Base de Datos")
        
        if boton_guardar:
            nuevo_registro = {
                "fecha": datetime.combine(fecha, datetime.min.time()),
                "direccion": direccion,
                "tipo_delito": tipo_delito,
                "es_relevante": es_relevante,
                "detalles": detalles,
                "fecha_registro": datetime.now()
            }
            coleccion.insert_one(nuevo_registro)
            st.success(f"✅ Registro en '{direccion}' guardado correctamente en la nube.")

# --- TAB 2: PANEL DE ANÁ
