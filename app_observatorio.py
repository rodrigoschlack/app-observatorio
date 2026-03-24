import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
import plotly.express as px
from bson.objectid import ObjectId
from geopy.geocoders import ArcGIS
import time

# Configuración de la página
st.set_page_config(page_title="Observatorio La Florida", layout="wide", page_icon="🛡️")

# --- 1. CONEXIÓN A LA BASE DE DATOS ---
@st.cache_resource
def iniciar_conexion():
    try:
        if "mongo" in st.secrets and "uri" in st.secrets["mongo"]:
            return MongoClient(st.secrets["mongo"]["uri"])
        else:
            st.error("❌ Error: No se encontraron los Secrets.")
            return None
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None

client = iniciar_conexion()

# --- 2. MOTOR DE GEOLOCALIZACIÓN INTELIGENTE (ArcGIS) ---
@st.cache_data(show_spinner=False)
def obtener_coordenada_unica(d):
    try:
        time.sleep(0.5) 
        geolocator = ArcGIS(user_agent="observatorio_florida_app")
        dir_limpia = str(d).replace("&", "y").replace("N°", "").replace("Nro.", "")
        loc = geolocator.geocode(f"{dir_limpia}, La Florida, Santiago, Chile", timeout=10)
        if loc:
            return loc.latitude, loc.longitude
        return None, None
    except:
        return None, None

# --- 3. INTERFAZ PRINCIPAL ---
st.title("🛡️ Sistema Central - Observatorio de Seguridad")
st.markdown("---")

if client:
    db = client['observatorio_seguridad']
    coleccion = db['registro_delitos']
    datos = list(coleccion.find())
    
    if datos:
        df = pd.DataFrame(datos)
        
        # Fusión de columnas antiguas y todas las NUEVAS DE INTELIGENCIA
        mapeos = {
            'fecha_final': ['fecha', 'Fecha'],
            'direccion_final': ['direccion', 'Dirección', 'Ubicación'],
            'delito_final': ['tipo_delito', 'Tipo de delito', 'Delito'],
            'img_final': ['tiene_imagenes', 'Imágenes', 'Imagenes'],
            'vid_final': ['tiene_videos', 'Videos', 'Video'],
            'detalles_final': ['detalles', 'Detalles'],
            'modalidad_final': ['modalidad', 'Modalidad'],
            'vehiculo_final': ['vehiculo', 'Vehículo'],
            'patente_final': ['patente', 'Patente'],
            'caracteristicas_final': ['caracteristicas', 'Características']
        }
        for final, originales in mapeos.items():
            df[final] = None
            for orig in originales:
                if orig in df.columns:
                    df[final] = df[final].fillna(df[orig])

        # Regla de Oro para las fechas
        def arreglar_fecha_absoluta(val):
            if pd.isna(val): return pd.NaT
            s = str(val).split(' ')[0].replace('/', '-')
            try:
                parts = s.split('-')
                if len(parts) == 3:
                    p1, p2, p3 = int(parts[0]), int(parts[1]), int(parts[2])
                    if p1 > 2000: return datetime(p1, p2, p3)
                    if p1 <= 12: return datetime(p3, p1, p2)
                    else: return datetime(p3, p2, p1)
            except: pass
            return pd.to_datetime(val, errors='coerce')

        df['fecha_final'] = df['fecha_final'].apply(arreglar_fecha_absoluta)
        df = df.dropna(subset=['direccion_final', 'delito_final'], how='all')
        df['_id_str'] = df['_id'].astype(str)
        df = df.sort_values(by=['fecha_final', '_id_str'], ascending=[False, False])

        for col in ['img_final',
