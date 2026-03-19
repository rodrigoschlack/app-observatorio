import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
import plotly.express as px

# Configuración de la página
st.set_page_config(page_title="Observatorio La Florida", layout="wide", page_icon="🛡️")

# 1. Conexión a MongoDB Atlas
@st.cache_resource
def iniciar_conexion():
    try:
        if "mongo" in st.secrets and "uri" in st.secrets["mongo"]:
            uri = st.secrets["mongo"]["uri"]
            return MongoClient(uri)
        else:
            st.error("❌ Error: No se encontraron los Secrets.")
            return None
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None

client = iniciar_conexion()

# 2. Interfaz
st.title("🛡️ Sistema Central - Observatorio de Seguridad")
st.markdown("---")

tab1, tab2 = st.tabs(["📝 Ingreso de Datos", "📊 Analítica y Reportes"])

# --- TAB 1: INGRESO ---
with tab1:
    st.header("Registrar Nuevo Incidente")
    if client:
        db = client['observatorio_seguridad']
        coleccion = db['registro_delitos']
        
        # Sincronizar lista de delitos (buscando en todas las variantes de columnas)
        docs = list(coleccion.find({}, {"tipo_delito": 1, "Tipo de delito": 1, "Delito": 1, "_id": 0}))
        delitos_db = set()
        for d in docs:
            for val in d.values():
                if val and isinstance(val, str) and len(val) < 40: 
                    delitos_db.add(val.strip())
        
        opciones = sorted(list({"RLH", "RCI", "RCV", "Delito sexual"}.union(delitos_db))) + ["Otro"]

        with st.form("formulario_registro", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1: fecha_in = st.date_input("Fecha del Suceso", datetime.now())
            with col2: dir_in = st.text_input("Dirección / Ubicación")
            
            t_sel = st.selectbox("Tipo de Delito", opciones)
            t_otro = st.text_input("Si eligió 'Otro', escriba aquí:")
            
            c1, c2, c3 = st.columns(3)
            with c1: img = st.checkbox("¿Imágenes?")
            with c2: vid = st.checkbox("¿Videos?")
            with c3: rel = st.checkbox("¿Relevante?")
                
            det = st.text_area("Detalles")
            if st.form_submit_button("Guardar Registro"):
                t_fin = t_otro.strip() if t_sel == "Otro" and t_otro else t_sel
                coleccion.insert_one({
                    "fecha": datetime.combine(fecha_in, datetime.min.time()),
                    "direccion": dir_in,
                    "tipo_delito": t_fin,
                    "tiene_imagenes": img,
                    "tiene_videos": vid,
                    "es_relevante": rel,
                    "detalles": det,
                    "fecha_registro": datetime.now()
                })
                st.success("✅ Guardado")
                st.rerun()

# --- TAB 2: ANALÍTICA (FUSIÓN TOTAL DE COLUMNAS) ---
with tab2:
    st.header("Panel de Análisis de Datos")
    if client:
        try:
            db = client['observatorio_seguridad']
            coleccion = db['registro_delitos']
            datos = list(coleccion.find())
            
            if datos:
                df = pd.DataFrame(datos)
                
                # --- PASO CRUCIAL: FUSIÓN DE COLUMNAS (Mapeo de Compass/Excel a App) ---
                # Definimos qué columnas significan lo mismo
                mapa_fechas = ['fecha', 'Fecha']
                mapa_direcciones = ['direccion', 'Dirección', 'Ubicación']
                mapa_delitos = ['tipo_delito', 'Tipo de delito', 'Delito']

                # Creamos las columnas definitivas si no existen
                for col in ['fecha_final', 'direccion_final', 'delito_final']:
                    df[col] = None

                # Llenamos las definitivas recorriendo las opciones posibles
                for f in mapa_fechas:
                    if f in df.columns: df['fecha_final'] = df['fecha_final'].fillna(df[f])
                
                for d in mapa_direcciones:
                    if d in df.columns: df['direccion_final'] = df['direccion_final'].fillna(df[d])
                
                for t in mapa_delitos:
                    if t in df.columns: df['delito_final'] = df['delito_final'].fillna(df[t])

                # --- LIMPIEZA Y ORDEN ---
                # Forzamos conversión de fecha (día primero)
                df['fecha_final'] = pd.to_datetime(df['fecha_final'], dayfirst=True, errors='coerce')
                
                # Eliminamos las filas que realmente no tienen nada (basura real)
                df = df.dropna(subset=['direccion_final', 'delito_final'], how='all')
                
                # Ordenar: 2026 arriba
                df = df.sort_values(by='fecha_final', ascending=False)

                # Buscador
                busq = st.text_input("🔍 Buscar dirección:", key="search_final")
                if busq:
                    df = df[df['direccion_final'].astype(str).str.contains(busq, case=False, na=False)]

                # Métricas
                m1, m2 = st.columns(2)
                m1.metric("Total Registros", len(df))
                if not df.empty:
                    m2.metric("Último Reporte", df['fecha_final'].iloc[0].strftime('%d-%m-%Y'))

                # Gráfico
                st.subheader("Estadísticas por Delito")
                cnt = df['delito_final'].value_counts().reset_index()
                cnt.columns = ['Delito', 'Cant']
                fig = px.bar(cnt, x='Cant', y='Delito', orientation='h', text='Cant', color='Delito')
                fig.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig, use_container_width=True)

                # TABLA FINAL (SIN NONES)
                st.subheader("Base de Datos Unificada")
                df_v = df[['fecha_final', 'direccion_final', 'delito_final']].copy()
                df_v.columns = ['Fecha', 'Dirección', 'Tipo de Delito'] # Renombramos para la vista
                df_v['Fecha'] = df_v['Fecha'].dt.strftime('%d-%m-%Y')
                
                st.dataframe(df_v, use_container_width=True, hide_index=True)
            else:
                st.info("Sin datos.")
        except Exception as e:
            st.error(f"Error en el procesamiento: {e}")
