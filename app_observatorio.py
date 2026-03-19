import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
import plotly.express as px

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
            st.error("❌ Configuración faltante en Secrets.")
            return None
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None

client = iniciar_conexion()

# 2. Interfaz Principal
st.title("🛡️ Sistema Central - Observatorio de Seguridad")
st.markdown("---")

tab1, tab2 = st.tabs(["📝 Ingreso de Datos", "📊 Analítica y Reportes"])

# --- TAB 1: FORMULARIO DE INGRESO DINÁMICO ---
with tab1:
    st.header("Registrar Nuevo Incidente")
    
    if client:
        db = client['observatorio_seguridad']
        coleccion = db['registro_delitos']
        
        # OBTENER TIPOS DE DELITO EXISTENTES DE LA BASE DE DATOS
        # Esto busca todos los valores únicos que ya has ingresado
        delitos_existentes = sorted([str(d) for d in coleccion.distinct("tipo_delito") if d])
        
        # Si la base está vacía, ponemos unos por defecto
        if not delitos_existentes:
            delitos_existentes = ["RLH", "RCV", "RCI", "Delito sexual"]
            
        opciones_delito = delitos_existentes + ["Otro"]

        with st.form("formulario_registro", clear_on_submit=True):
            col_f, col_d = st.columns(2)
            with col_f:
                fecha_input = st.date_input("Fecha del Suceso", datetime.now())
            with col_d:
                direccion_input = st.text_input("Dirección / Ubicación", placeholder="Ej: Tegualda 305")
            
            # Selector dinámico
            tipo_sel = st.selectbox("Tipo de Delito (Existentes)", opciones_delito)
            
            # Si elige "Otro", habilitamos el espacio para escribir
            tipo_otro = st.text_input("Si eligió 'Otro', escriba el tipo aquí:", placeholder="Ej: Robo por sorpresa")
            
            col_c1, col_c2, col_c3 = st.columns(3)
            with col_c1: tiene_imagenes = st.checkbox("¿Imágenes?")
            with col_c2: tiene_videos = st.checkbox("¿Videos?")
            with col_c3: es_relevante = st.checkbox("¿Relevante?")
                
            detalles = st.text_area("Detalles del caso")
            btn = st.form_submit_button("Guardar Registro")
            
            if btn:
                # Determinar cuál nombre de delito usar
                tipo_final = tipo_otro if tipo_sel == "Otro" and tipo_otro else tipo_sel
                
                if tipo_sel == "Otro" and not tipo_otro:
                    st.error("⚠️ Por favor, escriba el nombre del nuevo tipo de delito.")
                else:
                    nuevo = {
                        "fecha": datetime.combine(fecha_input, datetime.min.time()),
                        "direccion": direccion_input,
                        "tipo_delito": tipo_final,
                        "tiene_imagenes": tiene_imagenes,
                        "tiene_videos": tiene_videos,
                        "es_relevante": es_relevante,
                        "detalles": detalles,
                        "fecha_registro": datetime.now()
                    }
                    coleccion.insert_one(nuevo)
                    st.success(f"✅ Registro '{tipo_final}' guardado. La lista se actualizará en el próximo ingreso.")
                    # Forzar recarga para que el nuevo delito aparezca en la lista
                    st.rerun()

# --- TAB 2: ANALÍTICA (GRÁFICO HORIZONTAL) ---
with tab2:
    st.header("Panel de Análisis de Datos")
    
    if client:
        try:
            db = client['observatorio_seguridad']
            coleccion = db['registro_delitos']
            datos = list(coleccion.find())
            
            if datos:
                df = pd.DataFrame(datos)
                
                # Unificación de columnas Excel + App
                mapeo = {'Fecha': 'fecha', 'Dirección': 'direccion', 'Tipo de delito': 'tipo_delito', 'Relevante': 'es_relevante'}
                for cv, cn in mapeo.items():
                    if cv in df.columns:
                        if cn not in df.columns: df[cn] = None
                        df[cn] = df[cn].fillna(df[cv])
                
                # Limpieza
                df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
                df = df.sort_values(by='fecha', ascending=False)
                
                # Buscador
                busqueda = st.text_input("🔍 Buscar dirección:", key="search_bar")
                if busqueda:
                    df = df[df['direccion'].astype(str).str.contains(busqueda, case=False, na=False)]

                # Métricas
                m1, m2, m3 = st.columns(3)
                m1.metric("Total", len(df))
                
                if 'es_relevante' in df.columns:
                    relev_bool = df['es_relevante'].astype(str).str.lower().isin(['true', 'si', '1'])
                    m2.metric("Casos Relevantes", int(relev_bool.sum()))
                
                m3.metric("Más Reciente", df['fecha'].dt.strftime('%d-%m-%Y').iloc[0] if not df.empty else "N/A")

                # GRÁFICO HORIZONTAL PROFESIONAL
                st.subheader("Resumen por Tipo de Delito")
                if 'tipo_delito' in df.columns:
                    conteo = df['tipo_delito'].value_counts().reset_index()
                    conteo.columns = ['Delito', 'Cantidad']
                    
                    fig = px.bar(conteo, x='Cantidad', y='Delito', orientation='h',
                                 text='Cantidad', color='Delito',
                                 color_discrete_sequence=px.colors.qualitative.Safe)
                    
                    fig.update_layout(showlegend=False, height=400, margin=dict(l=0, r=0, t=10, b=10),
                                      yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

                # Tabla
                st.subheader("Base de Datos")
                df_ver = df[['fecha', 'direccion', 'tipo_delito', 'es_relevante']].copy()
                df_ver['fecha'] = df_ver['fecha'].dt.strftime('%d-%m-%Y')
                st.dataframe(df_ver, use_container_width=True, hide_index=True)

            else:
                st.info("No hay datos todavía.")
        except Exception as e:
            st.error(f"Error: {e}")
