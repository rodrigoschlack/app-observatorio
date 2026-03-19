import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
import plotly.express as px

# Configuración de la página para que se vea bien en celulares
st.set_page_config(page_title="Observatorio La Florida", layout="wide", page_icon="🛡️")

# 1. Conexión a MongoDB Atlas
@st.cache_resource
def iniciar_conexion():
    try:
        if "mongo" in st.secrets and "uri" in st.secrets["mongo"]:
            uri = st.secrets["mongo"]["uri"]
            return MongoClient(uri)
        else:
            st.error("❌ Error: No se encontraron las credenciales en Streamlit Secrets.")
            return None
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None

client = iniciar_conexion()

# 2. Título e Interfaz
st.title("🛡️ Sistema Central - Observatorio de Seguridad")
st.markdown("---")

tab1, tab2 = st.tabs(["📝 Ingreso de Datos", "📊 Analítica y Reportes"])

# --- TAB 1: FORMULARIO DE INGRESO ---
with tab1:
    st.header("Registrar Nuevo Incidente")
    
    if client:
        db = client['observatorio_seguridad']
        coleccion = db['registro_delitos']
        
        # OBTENER TODOS LOS TIPOS DE DELITOS EXISTENTES (De Compass y App)
        with st.spinner("Sincronizando tipos de delitos..."):
            # Buscamos en todas las columnas posibles (mayúsculas y minúsculas)
            docs = list(coleccion.find({}, {"tipo_delito": 1, "Tipo de delito": 1, "_id": 0}))
            delitos_en_db = set()
            for d in docs:
                for val in d.values():
                    if val and isinstance(val, str): delitos_en_db.add(val.strip())
            
            # Opciones base que siempre deben estar
            opciones_base = {"RLH", "RCI", "RCV", "Delito sexual"}
            lista_final = sorted(list(opciones_base.union(delitos_en_db)))
            opciones_con_otro = lista_final + ["Otro"]

        with st.form("formulario_registro", clear_on_submit=True):
            col_f, col_d = st.columns(2)
            with col_f:
                fecha_input = st.date_input("Fecha del Suceso", datetime.now())
            with col_d:
                direccion_input = st.text_input("Dirección / Ubicación", placeholder="Ej: Vicuña Mackenna 1234")
            
            tipo_sel = st.selectbox("Tipo de Delito", opciones_con_otro)
            tipo_otro = st.text_input("Si eligió 'Otro', escríbalo aquí:")
            
            col_c1, col_c2, col_c3 = st.columns(3)
            with col_c1: tiene_imagenes = st.checkbox("¿Imágenes?")
            with col_c2: tiene_videos = st.checkbox("¿Videos?")
            with col_c3: es_relevante = st.checkbox("¿Caso Relevante?")
                
            detalles = st.text_area("Detalles adicionales")
            btn = st.form_submit_button("Guardar Registro")
            
            if btn:
                tipo_final = tipo_otro.strip() if tipo_sel == "Otro" and tipo_otro else tipo_sel
                if not direccion_input:
                    st.warning("⚠️ La dirección es obligatoria.")
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
                    st.success(f"✅ Registro '{tipo_final}' guardado exitosamente.")
                    st.rerun()

# --- TAB 2: ANALÍTICA (ORDEN CRONOLÓGICO Y BUSCADOR) ---
with tab2:
    st.header("Panel de Análisis de Datos")
    
    if client:
        try:
            db = client['observatorio_seguridad']
            coleccion = db['registro_delitos']
            datos = list(coleccion.find())
            
            if datos:
                df = pd.DataFrame(datos)
                
                # --- LIMPIEZA DE FECHAS Y COLUMNAS ---
                # Unificamos 'Fecha' con 'fecha'
                if 'Fecha' in df.columns:
                    df['fecha'] = df['fecha'].fillna(df['Fecha'])
                
                # Convertir a fecha real y ordenar (2026 ARRIBA)
                df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
                df = df.sort_values(by='fecha', ascending=False)
                
                # Unificar Direcciones y Tipos
                for cv, cn in {'Tipo de delito': 'tipo_delito', 'Dirección': 'direccion'}.items():
                    if cv in df.columns:
                        if cn not in df.columns: df[cn] = df[cv]
                        else: df[cn] = df[cn].fillna(df[cv])

                # BUSCADOR
                busqueda = st.text_input("🔍 Buscar por dirección:", placeholder="Ej: Tegualda...")
                if busqueda:
                    df = df[df['direccion'].astype(str).str.contains(busqueda, case=False, na=False)]

                # MÉTRICAS
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Registros", len(df))
                m2.metric("Casos Relevantes", int(df['es_relevante'].sum()) if 'es_relevante' in df.columns else 0)
                m3.metric("Último Ingreso", df['fecha'].dt.strftime('%d-%m-%Y').iloc[0] if not df.empty else "--")

                # GRÁFICO HORIZONTAL (Perfecto para iPhone)
                st.subheader("Distribución por Delito")
                if 'tipo_delito' in df.columns:
                    conteo = df['tipo_delito'].value_counts().reset_index()
                    conteo.columns = ['Delito', 'Cant']
                    fig = px.bar(conteo, x='Cant', y='Delito', orientation='h', text='Cant', 
                                 color='Delito', color_discrete_sequence=px.colors.qualitative.Safe)
                    fig.update_layout(showlegend=False, height=400, margin=dict(l=0, r=10, t=10, b=10),
                                      yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

                # TABLA FINAL
                st.subheader("Listado de Registros (Nuevos primero)")
                df_ver = df[['fecha', 'direccion', 'tipo_delito']].copy()
                df_ver['fecha'] = df_ver['fecha'].dt.strftime('%d-%m-%Y')
                st.dataframe(df_ver, use_container_width=True, hide_index=True)

            else:
                st.info("No hay datos en la nube.")
        except Exception as e:
            st.error(f"Error en analítica: {e}")
