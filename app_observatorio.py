import streamlit as st
import pandas as pd
from pymongo import MongoClient

# Configuración de la página para que use toda la pantalla
st.set_page_config(page_title="App Observatorio", page_icon="🚓", layout="wide")

# 1. Conexión a la base de datos
@st.cache_resource
def iniciar_conexion():
    # Usamos la clave guardada en los "Secrets" de Streamlit
    uri = st.secrets["mongo"]["uri"]
    return MongoClient(uri)

cliente = iniciar_conexion()
db = cliente['observatorio_seguridad']
coleccion = db['registro_delitos']

st.title("🚓 Sistema Central - Observatorio de Seguridad")

# 2. CREAMOS LAS PESTAÑAS (TABS)
tab_ingreso, tab_analitica = st.tabs(["📝 Ingreso de Datos", "📊 Analítica y Reportes"])

# ==========================================
# PESTAÑA 1: INGRESO DE DATOS (Lo que ya tenías)
# ==========================================
with tab_ingreso:
    st.write("Completa el formulario para ingresar un nuevo registro a la base de datos.")
    
    with st.form("formulario_ingreso", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            fecha_input = st.date_input("Fecha del Delito")
            direccion_input = st.text_input("Dirección (Ej. Alameda Oriente 9585)")
            tipo_delito = st.selectbox("Tipo de Delito", ["RLH", "RCV", "RCI", "RLHF", "Otro"])
            
        with col2:
            st.write("Evidencia y Relevancia")
            tiene_imagenes = st.checkbox("¿Se recopilaron Imágenes?")
            tiene_videos = st.checkbox("¿Se recopilaron Videos?")
            es_relevante = st.checkbox("¿Es un caso Relevante para seguimiento?")
            
        submit_button = st.form_submit_button("Guardar Registro")
        
        if submit_button:
            if direccion_input == "":
                st.warning("⚠️ Por favor, ingresa una dirección válida.")
            else:
                nuevo_documento = {
                    "fecha": fecha_input.strftime("%d/%m/%Y"), 
                    "direccion": direccion_input,
                    "tipo_delito": tipo_delito,
                    "evidencia": {
                        "tiene_imagenes": tiene_imagenes,
                        "tiene_videos": tiene_videos
                    },
                    "es_relevante": es_relevante
                }
                coleccion.insert_one(nuevo_documento)
                st.success(f"✅ Registro en {direccion_input} guardado correctamente.")

# ==========================================
# PESTAÑA 2: ANALÍTICA DELICTUAL (¡Lo Nuevo!)
# ==========================================
with tab_analitica:
    st.header("Panel de Análisis de Datos")
    
    # Extraemos todos los datos de MongoDB y los convertimos en un formato analítico
    datos_crudos = list(coleccion.find())
    
    if len(datos_crudos) > 0:
        # Convertimos la lista de diccionarios en un DataFrame de Pandas
        df = pd.DataFrame(datos_crudos)
        # 1. Traer los datos de MongoDB
datos = list(coleccion.find())
df = pd.DataFrame(datos)

# 2. UNIFICAR COLUMNAS (Añade estas líneas)
if not df.empty:
    # Fusionamos 'Fecha' con 'fecha', 'Dirección' con 'direccion', etc.
    if 'Fecha' in df.columns:
        df['fecha'] = df['fecha'].fillna(df['Fecha'])
    if 'Dirección' in df.columns:
        df['direccion'] = df['direccion'].fillna(df['Dirección'])
    if 'Tipo de delito' in df.columns:
        df['tipo_delito'] = df['tipo_delito'].fillna(df['Tipo de delito'])
    if 'Relevante' in df.columns:
        # Convertimos "Si" a True para que los gráficos lo entiendan
        df['es_relevante'] = df['es_relevante'].fillna(df['Relevante'].map({'Si': True, 'No': False}))

    # Limpiamos las columnas viejas que ya no necesitamos
    columnas_a_borrar = ['Fecha', 'Dirección', 'Tipo de delito', 'Relevante', 'Imágenes', 'Videos']
    df = df.drop(columns=[col for col in columnas_a_borrar if col in df.columns])


        # 1. TARJETAS DE RESUMEN (Métricas rápidas)
        st.subheader("Métricas Generales")
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total de Registros", len(df))
        col_m2.metric("Casos Relevantes", len(df[df['es_relevante'] == True]))
        # Contamos cuántos delitos diferentes hay en el registro
        col_m3.metric("Tipos de Delitos Distintos", df['tipo_delito'].nunique())
        
        st.divider() # Línea separadora
        
        # 2. GRÁFICOS ANALÍTICOS
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.write("**Frecuencia por Tipo de Delito**")
            # Agrupamos por delito y contamos cuántos hay de cada uno
            conteo_delitos = df['tipo_delito'].value_counts()
            # Streamlit hace el gráfico de barras automáticamente
            st.bar_chart(conteo_delitos)
            
        with col_g2:
            st.write("**Direcciones con más reiteraciones (Top 5)**")
            # Buscamos direcciones repetidas (posibles blancos recurrentes)
            top_direcciones = df['direccion'].value_counts().head(5)
            st.bar_chart(top_direcciones, color="#ff4b4b")
            
        # 3. TABLA DE DATOS FILTRABLE
        st.subheader("Base de Datos Completa")
        # Mostramos una tabla interactiva, ocultando el ID técnico de MongoDB
        st.dataframe(df.drop(columns=['_id', 'evidencia']), use_container_width=True)
        
    else:
        st.info("No hay datos suficientes para mostrar analítica. Ingresa algunos registros primero.")
