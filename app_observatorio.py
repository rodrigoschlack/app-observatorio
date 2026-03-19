import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Observatorio de Seguridad", layout="wide")

# 1. Conexión a la base de datos (Usando Secrets de Streamlit)
@st.cache_resource
def iniciar_conexion():
    try:
        # Busca la URI en los Secrets que configuramos en Streamlit
        uri = st.secrets["mongo"]["uri"]
        return MongoClient(uri)
    except Exception as e:
        st.error(f"Error de configuración: {e}")
        return None

client = iniciar_conexion()
db = client['observatorio_seguridad']
coleccion = db['registro_delitos']

# Interfaz de Streamlit
st.title("🛡️ Sistema Central - Observatorio de Seguridad")

# Crear pestañas
tab1, tab2 = st.tabs(["📝 Ingreso de Datos", "📊 Analítica y Reportes"])

with tab1:
    st.header("Registrar Nuevo Incidente")
    with st.form("formulario_registro"):
        fecha = st.date_input("Fecha del Suceso", datetime.now())
        direccion = st.text_input("Dirección / Ubicación")
        tipo_delito = st.selectbox("Tipo de Delito", 
                                  ["Robo", "Hurto", "Vandalismo", "Asalto", "Otro"])
        es_relevante = st.checkbox("¿Es un caso relevante?")
        detalles = st.text_area("Detalles adicionales")
        
        boton_guardar = st.form_submit_button("Guardar Registro")
        
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
            st.success("✅ Registro guardado exitosamente en la nube.")

with tab2:
    st.header("Panel de Visualización")
    
    # Cargar datos desde MongoDB
    datos = list(coleccion.find())
    
    if datos:
        df = pd.DataFrame(datos)
        
        # --- PROCESO DE UNIFICACIÓN DE COLUMNAS (EXCEL + NUEVOS) ---
        # Si existen columnas del Excel (Mayúsculas), las movemos a las nuevas (minúsculas)
        mapeo = {
            'Fecha': 'fecha',
            'Dirección': 'direccion',
            'Tipo de delito': 'tipo_delito',
            'Relevante': 'es_relevante'
        }
        
        for col_vieja, col_nueva in mapeo.items():
            if col_vieja in df.columns:
                if col_nueva not in df.columns:
                    df[col_nueva] = None
                # Rellenamos los vacíos de la columna nueva con los datos de la vieja
                df[col_nueva] = df[col_nueva].fillna(df[col_vieja])
        
        # Ajuste especial para la columna de Relevancia (Si/No a Verdadero/Falso)
        if 'Relevante' in df.columns:
            mask = df['Relevante'].isin(['Si', 'SI', 'si'])
            df.loc[mask, 'es_relevante'] = True
            df.loc[~mask & df['Relevante'].notna(), 'es_relevante'] = False

        # Eliminar el ID de MongoDB para la vista de usuario y columnas viejas
        columnas_finales = ['fecha', 'direccion', 'tipo_delito', 'es_relevante', 'detalles']
        df_display = df[[c for c in columnas_finales if c in df.columns]].copy()
        
        # Métricas
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Casos", len(df))
        
        relevantes = df['es_relevante'].sum() if 'es_relevante' in df.columns else 0
        col2.metric("Casos Relevantes", int(relevantes))
        col3.metric("Última Actualización", datetime.now().strftime("%H:%M"))

        # Gráfico simple
        st.subheader("Distribución por Tipo de Delito")
        if 'tipo_delito' in df.columns:
            st.bar_chart(df['tipo_delito'].value_counts())

        # Tabla de datos limpia
        st.subheader("Listado de Registros")
        st.dataframe(df_display, use_container_width=True)
    else:
        st.info("Aún no hay datos registrados en la base de datos de la nube.")
