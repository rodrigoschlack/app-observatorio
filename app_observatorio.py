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

# --- TAB 1: FORMULARIO DE INGRESO INTELIGENTE ---
with tab1:
    st.header("Registrar Nuevo Incidente")
    
    if client:
        db = client['observatorio_seguridad']
        coleccion = db['registro_delitos']
        
        # --- LÓGICA PARA EXTRAER TODOS LOS DELITOS DE COMPASS/ATLAS ---
        with st.spinner("Actualizando lista de delitos..."):
            # Obtenemos todos los registros para mapear columnas viejas y nuevas
            todos_los_docs = list(coleccion.find({}, {"tipo_delito": 1, "Tipo de delito": 1, "Delito": 1, "_id": 0}))
            
            # Extraemos valores de cualquier columna que pueda contener el nombre del delito
            delitos_encontrados = set()
            for doc in todos_los_docs:
                for val in doc.values():
                    if val and isinstance(val, str):
                        delitos_encontrados.add(val.strip())
            
            # Opciones que siempre queremos tener por si acaso
            opciones_base = {"RLH", "RCI", "RCV", "Delito sexual"}
            
            # Combinamos todo, eliminamos vacíos y ordenamos
            lista_final = sorted(list(opciones_base.union(delitos_encontrados)))
            opciones_con_otro = lista_final + ["Otro"]

        with st.form("formulario_registro", clear_on_submit=True):
            col_f, col_d = st.columns(2)
            with col_f:
                fecha_input = st.date_input("Fecha del Suceso", datetime.now())
            with col_d:
                direccion_input = st.text_input("Dirección / Ubicación", placeholder="Ej: Av. La Florida")
            
            # Selector que ahora incluye TODO lo que hay en tu Atlas/Compass
            tipo_sel = st.selectbox("Seleccione Tipo de Delito", opciones_con_otro)
            
            # Espacio para nuevos delitos
            tipo_otro = st.text_input("Si no aparece en la lista, escríbalo aquí:", placeholder="Ej: Robo con Intimidación")
            
            col_c1, col_c2, col_c3 = st.columns(3)
            with col_c1: tiene_imagenes = st.checkbox("¿Imágenes?")
            with col_c2: tiene_videos = st.checkbox("¿Videos?")
            with col_c3: es_relevante = st.checkbox("¿Relevante?")
                
            detalles = st.text_area("Detalles del caso")
            btn = st.form_submit_button("Guardar Registro")
            
            if btn:
                tipo_final = tipo_otro.strip() if tipo_sel == "Otro" and tipo_otro else tipo_sel
                
                if not direccion_input:
                    st.warning("⚠️ La dirección es obligatoria.")
                elif tipo_sel == "Otro" and not tipo_otro:
                    st.warning("⚠️ Escriba el nombre del nuevo delito.")
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
                    st.success(f"✅ Guardado: {tipo_final}")
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
                
                # Unificamos columnas para que la analítica no falle con datos viejos
                for col_vieja, col_nueva in {'Tipo de delito': 'tipo_delito', 'Dirección': 'direccion', 'Fecha': 'fecha'}.items():
                    if col_vieja in df.columns:
                        df['tipo_delito'] = df['tipo_delito'].fillna(df[col_vieja]) if 'tipo_delito' in df.columns else df[col_vieja]
                        df['direccion'] = df['direccion'].fillna(df[col_vieja]) if 'direccion' in df.columns else df[col_vieja]

                df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
                df = df.sort_values(by='fecha', ascending=False)
                
                # Buscador
                busqueda = st.text_input("🔍 Filtrar por dirección:", key="filtro_busqueda")
                if busqueda:
                    df = df[df['direccion'].astype(str).str.contains(busqueda, case=False, na=False)]

                # Métricas
                m1, m2, m3 = st.columns(3)
                m1.metric("Total", len(df))
                
                # Gráfico Horizontal Plotly (Mejorado para 60+ registros)
                st.subheader("Distribución por Delito")
                if 'tipo_delito' in df.columns:
                    conteo = df['tipo_delito'].value_counts().reset_index()
                    conteo.columns = ['Delito', 'Cant']
                    
                    fig = px.bar(conteo, x='Cant', y='Delito', orientation='h',
                                 text='Cant', color='Delito',
                                 color_discrete_sequence=px.colors.qualitative.Prism)
                    
                    fig.update_layout(showlegend=False, height=450, margin=dict(l=0, r=10, t=10, b=10),
                                      yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

                # Tabla
                st.subheader("Registros Recientes")
                df_ver = df[['fecha', 'direccion', 'tipo_delito']].copy()
                df_ver['fecha'] = df_ver['fecha'].dt.strftime('%d-%m-%Y')
                st.dataframe(df_ver, use_container_width=True, hide_index=True)

            else:
                st.info("Sin datos.")
        except Exception as e:
            st.error(f"Error: {e}")
