import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime, time as datetime_time
import plotly.express as px
from bson.objectid import ObjectId
from geopy.geocoders import ArcGIS
import time
import google.generativeai as genai

# Configuración de la página
st.set_page_config(page_title="Observatorio La Florida", layout="wide", page_icon="🛡️")

# --- 1. CONEXIÓN A LA BASE DE DATOS ---
@st.cache_resource
def iniciar_conexion():
    try:
        if "mongo" in st.secrets and "uri" in st.secrets["mongo"]:
            return MongoClient(st.secrets["mongo"]["uri"])
        else:
            st.error("❌ Error: No se encontraron los Secrets de Mongo.")
            return None
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None

client = iniciar_conexion()

# --- 2. MOTOR DE IA (GEMINI) ---
def consultar_gemini(pregunta, contexto_datos):
    try:
        if "ai" in st.secrets and "gemini_key" in st.secrets["ai"]:
            genai.configure(api_key=st.secrets["ai"]["gemini_key"])
            modelo_disponible = "gemini-1.5-flash" 
            try:
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        if 'flash' in m.name or 'pro' in m.name:
                            modelo_disponible = m.name
                            break
            except: pass
            
            model = genai.GenerativeModel(modelo_disponible)
            resumen = contexto_datos[['fecha_final', 'delito_final', 'modalidad_final', 'vehiculo_final', 'armamento_final', 'patente_final', 'detalles_final']].to_string()
            
            prompt = f"""
            Eres un analista de inteligencia delictual para el Observatorio de Seguridad de La Florida, Chile.
            REGISTROS: {resumen}
            PREGUNTA: {pregunta}
            Responde de forma profesional buscando patrones en vehículos, armas o MO.
            """
            respuesta = model.generate_content(prompt)
            return respuesta.text
        return "❌ Llave de IA no configurada."
    except Exception as e:
        return f"❌ Error IA: {e}"

# --- 3. MOTOR DE GEOLOCALIZACIÓN ---
@st.cache_data(show_spinner=False)
def obtener_coordenada_unica(d):
    try:
        time.sleep(0.5) 
        geolocator = ArcGIS(user_agent="observatorio_florida_app")
        loc = geolocator.geocode(f"{str(d)}, La Florida, Santiago, Chile", timeout=10)
        return (loc.latitude, loc.longitude) if loc else (None, None)
    except: return None, None

# --- 4. INTERFAZ PRINCIPAL ---
st.title("🛡️ Sistema Central - Observatorio de Seguridad")
st.markdown("---")

if client:
    db = client['observatorio_seguridad']
    coleccion = db['registro_delitos']
    datos = list(coleccion.find())
    
    if datos:
        df = pd.DataFrame(datos)
        
        # Mapeo de columnas con prioridad
        for final, originales in {
            'fecha_final': ['fecha', 'Fecha'],
            'direccion_final': ['direccion', 'Dirección'],
            'delito_final': ['tipo_delito', 'Tipo de delito'],
            'img_final': ['tiene_imagenes', 'Imágenes'],
            'vid_final': ['tiene_videos', 'Videos'],
            'relevante_final': ['es_relevante', 'Relevante'], 
            'detalles_final': ['detalles', 'Detalles'],
            'modalidad_final': ['modalidad', 'Modalidad'],
            'vehiculo_final': ['vehiculo', 'Vehículo'],
            'armamento_final': ['armamento', 'Armamento'],
            'patente_final': ['patente', 'Patente'],
            'caracteristicas_final': ['caracteristicas', 'Características']
        }.items():
            df[final] = None
            for orig in originales:
                if orig in df.columns:
                    df[final] = df[final].fillna(df[orig])

        # NUEVA REGLA DE FECHA: NO MÁS RECORTE DE HORAS
        def limpiar_fecha_completa(val):
            if pd.isna(val) or val is None: return pd.NaT
            if isinstance(val, datetime): return val # Si ya es datetime, NO TOCAR
            return pd.to_datetime(val, errors='coerce')

        df['fecha_final'] = df['fecha_final'].apply(limpiar_fecha_completa)
        df = df.dropna(subset=['direccion_final', 'delito_final'], how='all')
        df = df.sort_values(by=['fecha_final'], ascending=False)

        for col in ['img_final', 'vid_final', 'relevante_final']:
            df[col] = df[col].apply(lambda x: "✅ Sí" if str(x).lower() in ['true', 'si', '1.0', '1'] else "❌ No")

        # --- BARRA LATERAL ---
        with st.sidebar:
            st.header("⚙️ Filtros")
            busq = st.text_input("🔍 Buscar:")
            min_date = df['fecha_final'].min().date()
            max_date = df['fecha_final'].max().date()
            fecha_inicio = st.date_input("Desde:", min_date)
            fecha_fin = st.date_input("Hasta:", max_date)

        if busq:
            df = df[df.apply(lambda row: busq.lower() in row.astype(str).str.lower().values, axis=1)]

        mask_fechas = (df['fecha_final'].dt.date >= fecha_inicio) & (df['fecha_final'].dt.date <= fecha_fin)
        df = df[mask_fechas]

        tab_ia, tab1, tab2, tab3 = st.tabs(["🤖 Analista IA", "📊 Analítica y Reportes", "🗺️ Mapa", "📝 Administración"])

        with tab_ia:
            st.header("🤖 Asistente de Inteligencia")
            pregunta = st.text_input("Pregunta sobre patrones:")
            if st.button("Consultar", type="primary"):
                with st.spinner("Analizando..."):
                    st.info(consultar_gemini(pregunta, df.head(100)))

        with tab1:
            if not df.empty:
                st.subheader("Estadísticas y Reportes")
                df_v = df[['fecha_final', 'direccion_final', 'delito_final', 'modalidad_final', 'vehiculo_final', 'armamento_final', 'patente_final', 'caracteristicas_final', 'img_final', 'vid_final', 'relevante_final']].copy()
                df_v['fecha_final'] = df_v['fecha_final'].dt.strftime('%d-%m-%Y %H:%M')
                df_v.columns = ['Fecha y Hora', 'Dirección', 'Delito', 'Modalidad', 'Vehículo', 'Armamento', 'Patente', 'Sujetos', '¿Imgs?', '¿Vids?', '¿Rel?']
                df_v.insert(0, "Seleccionar", False)

                edited_df = st.data_editor(df_v, hide_index=True, use_container_width=True)

                seleccionados = edited_df[edited_df["Seleccionar"] == True]
                if not seleccionados.empty:
                    texto = "Reporte de Seguridad Ciudadana\n\n"
                    for _, row in seleccionados.iterrows():
                        texto += f"- {row['Dirección']} | {row['Fecha y Hora']} hrs.\n  Delito: {row['Delito']}\n  Modalidad: {row['Modalidad']} | Armas: {row['Armamento']}\n  Patente: {row['Patente']}\n\n"
                    st.download_button("📄 Bajar TXT para Fiscalía", data=texto, file_name="reporte.txt")

        with tab2:
            if st.button("🗺️ Generar Mapa"):
                df_map = df.dropna(subset=['direccion_final']).copy()
                df_map['coords'] = df_map['direccion_final'].apply(obtener_coordenada_unica)
                df_map['lat'] = df_map['coords'].apply(lambda x: x[0])
                df_map['lon'] = df_map['coords'].apply(lambda x: x[1])
                st.plotly_chart(px.density_mapbox(df_map.dropna(subset=['lat']), lat="lat", lon="lon", radius=20, zoom=12, mapbox_style="open-street-map"))

        with tab3:
            admin_clave = st.text_input("Clave Admin", type="password")
            if admin_clave == st.secrets.get("admin", {}).get("clave", "Florida2026"):
                t1, t2 = st.tabs(["Ingresar", "Editar"])
                with t1:
                    with st.form("nuevo"):
                        c1, c2, c3 = st.columns([1,1,2])
                        f_in = c1.date_input("Fecha", datetime.now())
                        h_in = c2.time_input("Hora", datetime.now().time())
                        d_in = c3.text_input("Dirección")
                        del_in = st.selectbox("Delito", ["RLH", "RCI", "RCV", "RP", "Otros"])
                        mod_in = st.text_input("Modalidad")
                        veh_in = st.text_input("Vehículo")
                        arm_in = st.text_input("Armamento")
                        pat_in = st.text_input("Patente")
                        car_in = st.text_input("Características Sujetos")
                        det_in = st.text_area("Detalles")
                        if st.form_submit_button("Guardar"):
                            coleccion.insert_one({"fecha": datetime.combine(f_in, h_in), "direccion": d_in, "tipo_delito": del_in, "modalidad": mod_in, "vehiculo": veh_in, "armamento": arm_in, "patente": pat_in, "caracteristicas": car_in, "detalles": det_in})
                            st.success("Guardado"); st.rerun()
                with t2:
                    ultimos = list(coleccion.find().sort("fecha", -1).limit(50))
                    sel_edit = st.selectbox("Editar:", [f"{r.get('fecha')} | {r.get('direccion')}" for r in ultimos])
                    # Lógica de edición simplificada para asegurar persistencia
