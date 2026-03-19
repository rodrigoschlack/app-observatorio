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
            st.error("❌ Error en Secrets.")
            return None
    except Exception as e:
        st.error(f"❌ Error: {e}")
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
        
        # Sincronizar lista de delitos
        docs = list(coleccion.find({}, {"tipo_delito": 1, "Tipo de delito": 1, "_id": 0}))
        delitos_db = set()
        for d in docs:
            for val in d.values():
                if val and isinstance(val, str): delitos_db.add(val.strip())
        
        opciones = sorted(list({"RLH", "RCI", "RCV", "Delito sexual"}.union(delitos_db))) + ["Otro"]

        with st.form("formulario_registro", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1: fecha_in = st.date_input("Fecha del Suceso", datetime.now())
            with col2: dir_in = st.text_input("Dirección / Ubicación")
            
            t_sel = st.selectbox("Tipo de Delito", opciones)
            t_otro = st.text_input("Si eligió 'Otro':")
            
            c1, c2, c3 = st.columns(3)
            with c1: img = st.checkbox("¿Imágenes?")
            with c2: vid = st.checkbox("¿Videos?")
            with c3: rel = st.checkbox("¿Relevante?")
                
            det = st.text_area("Detalles")
            if st.form_submit_button("Guardar"):
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

# --- TAB 2: ANALÍTICA (CORRECCIÓN DEFINITIVA DE FECHAS) ---
with tab2:
    st.header("Panel de Análisis de Datos")
    if client:
        try:
            db = client['observatorio_seguridad']
            coleccion = db['registro_delitos']
            datos = list(coleccion.find())
            
            if datos:
                df = pd.DataFrame(datos)
                
                # UNIFICACIÓN DE FECHAS
                if 'Fecha' in df.columns:
                    df['fecha'] = df['fecha'].fillna(df['Fecha'])
                
                # --- AQUÍ ESTÁ EL TRUCO: dayfirst=True ---
                # Esto obliga a Pandas a entender que el primer número es el DÍA
                df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
                
                # Ordenar (2026 arriba)
                df = df.sort_values(by='fecha', ascending=False)
                
                # Unificar columnas
                for cv, cn in {'Tipo de delito': 'tipo_delito', 'Dirección': 'direccion'}.items():
                    if cv in df.columns:
                        df[cn] = df[cn].fillna(df[cv]) if cn in df.columns else df[cv]

                # Buscador y Métricas
                busq = st.text_input("🔍 Buscar dirección:")
                if busq:
                    df = df[df['direccion'].astype(str).str.contains(busq, case=False, na=False)]

                m1, m2 = st.columns(2)
                m1.metric("Total Registros", len(df))
                # Mostrar la fecha del primer registro (el más nuevo)
                if not df.empty:
                    m2.metric("Último Registro", df['fecha'].iloc[0].strftime('%d-%m-%Y'))

                # Gráfico
                if 'tipo_delito' in df.columns:
                    cnt = df['tipo_delito'].value_counts().reset_index()
                    cnt.columns = ['Delito', 'Cant']
                    fig = px.bar(cnt, x='Cant', y='Delito', orientation='h', text='Cant', color='Delito')
                    st.plotly_chart(fig, use_container_width=True)

                # Tabla
                st.subheader("Registros Ordenados")
                df_v = df[['fecha', 'direccion', 'tipo_delito']].copy()
                df_v['fecha'] = df_v['fecha'].dt.strftime('%d-%m-%Y')
                st.dataframe(df_v, use_container_width=True, hide_index=True)
            else:
                st.info("Sin datos.")
        except Exception as e:
            st.error(f"Error: {e}")
