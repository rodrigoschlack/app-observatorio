import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
import plotly.express as px
from bson.objectid import ObjectId
from geopy.geocoders import Nominatim
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

# --- 2. MOTOR DE GEOLOCALIZACIÓN INTELIGENTE (1 a 1) ---
@st.cache_data(show_spinner=False)
def obtener_coordenada_unica(d):
    try:
        time.sleep(1.5) # Freno de seguridad para no saturar al satélite
        geolocator = Nominatim(user_agent="observatorio_florida_app")
        dir_limpia = str(d).replace("&", "y")
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
        
        # Fusión de columnas antiguas y nuevas
        mapeos = {
            'fecha_final': ['fecha', 'Fecha'],
            'direccion_final': ['direccion', 'Dirección', 'Ubicación'],
            'delito_final': ['tipo_delito', 'Tipo de delito', 'Delito'],
            'img_final': ['tiene_imagenes', 'Imágenes', 'Imagenes'],
            'vid_final': ['tiene_videos', 'Videos', 'Video'],
            'detalles_final': ['detalles', 'Detalles']
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

        for col in ['img_final', 'vid_final']:
            df[col] = df[col].apply(lambda x: "✅ Sí" if str(x).lower() in ['true', 'si', '1.0', '1'] else "❌ No")

        # --- BARRA LATERAL (FILTROS) ---
        with st.sidebar:
            st.header("⚙️ Filtros del Sistema")
            st.write("Estos filtros controlan la Tabla y el Mapa.")
            
            busq = st.text_input("🔍 Buscar dirección o delito:", placeholder="Ej: RCV o Pudeto")
            st.markdown("---")
            st.write("📅 **Rango de Fechas**")
            min_date = df['fecha_final'].min().date()
            max_date = df['fecha_final'].max().date()
            
            fecha_inicio = st.date_input("Desde:", min_date, min_value=min_date, max_value=max_date)
            fecha_fin = st.date_input("Hasta:", max_date, min_value=min_date, max_value=max_date)

        # Aplicamos los filtros
        if busq:
            mask_dir = df['direccion_final'].astype(str).str.contains(busq, case=False, na=False)
            mask_del = df['delito_final'].astype(str).str.contains(busq, case=False, na=False)
            df = df[mask_dir | mask_del]

        mask_fechas = (df['fecha_final'].dt.date >= fecha_inicio) & (df['fecha_final'].dt.date <= fecha_fin)
        df = df[mask_fechas]

        # --- LAS 3 PESTAÑAS PRINCIPALES ---
        tab1, tab2, tab3 = st.tabs(["📊 Analítica y Reportes", "🗺️ Mapa de Delitos", "📝 Área de Administración"])

        # PESTAÑA 1: TABLA Y TXT
        with tab1:
            if not df.empty:
                st.subheader("Estadísticas del periodo seleccionado")
                cnt = df['delito_final'].value_counts().reset_index()
                cnt.columns = ['Delito', 'Cant']
                fig = px.bar(cnt, x='Cant', y='Delito', orientation='h', text='Cant', color='Delito')
                fig.update_layout(showlegend=False, height=300, margin=dict(l=0, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("Selección de Casos para Fiscalía")
                df_v = df[['fecha_final', 'direccion_final', 'delito_final', 'img_final', 'vid_final', 'detalles_final']].copy()
                df_v['fecha_final'] = df_v['fecha_final'].dt.strftime('%d-%m-%Y')
                df_v['detalles_final'] = df_v['detalles_final'].fillna("-")
                df_v.columns = ['Fecha', 'Dirección', 'Tipo de Delito', '¿Imágenes?', '¿Videos?', 'Detalles']
                df_v.insert(0, "Seleccionar", False)

                edited_df = st.data_editor(
                    df_v, hide_index=True,
                    column_config={"Seleccionar": st.column_config.CheckboxColumn("Seleccionar", required=True)},
                    disabled=['Fecha', 'Dirección', 'Tipo de Delito', '¿Imágenes?', '¿Videos?', 'Detalles'], 
                    use_container_width=True
                )

                seleccionados = edited_df[edited_df["Seleccionar"] == True]
                if not seleccionados.empty:
                    texto_reporte = "Estimadas/os,\n\nJunto con saludar y esperando se encuentren bien, adjunto información de hechos de relevancia.\n\n"
                    meses_es = {"01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril", "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto", "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"}
                    
                    contador = 1
                    for index, row in seleccionados.iterrows():
                        texto_reporte += f"{contador}- {row['Dirección']}, La Florida.\n"
                        partes_fecha = str(row['Fecha']).split('-')
                        if len(partes_fecha) == 3:
                            fecha_formateada = f"{partes_fecha[0]} de {meses_es.get(partes_fecha[1], partes_fecha[1])} del {partes_fecha[2]}"
                        else: fecha_formateada = row['Fecha']

                        texto_reporte += f"Fecha: {fecha_formateada}.\n"
                        texto_reporte += f"Hora: [EDITAR HORA] (como referencia)\n"
                        texto_reporte += f"Delito: {row['Tipo de Delito']}.\n"
                        obs = "En el lugar no fue posible realizar el levantamiento de material audiovisual." if row['¿Imágenes?'] == "❌ No" and row['¿Videos?'] == "❌ No" else "Se logró levantamiento de material audiovisual en el lugar."
                        if row['Detalles'] != "-": obs += f" {row['Detalles']}"
                        texto_reporte += f"Observaciones: {obs}\n\n"
                        contador += 1
                        
                    texto_reporte += "Isabel Romero\nRodrigo Schlack\nDepartamento de televigilancia y comunicación radial."
                    st.download_button("📄 Descargar Reporte (TXT)", data=texto_reporte, file_name=f"Reporte_Fiscalia_{datetime.now().strftime('%d%m%Y')}.txt", mime="text/plain")
            else:
                st.warning("No hay registros en el rango de fechas seleccionado.")

        # PESTAÑA 2: EL MAPA CON BARRA DE PROGRESO
        with tab2:
            st.header("📍 Mapa de Puntos Calientes")
            if not df.empty:
                st.write("Presiona el botón para escanear las direcciones. Solo tomará tiempo la primera vez.")
                
                if st.button("🗺️ Cargar Mapa", type="primary"):
                    direcciones_unicas = df['direccion_final'].unique()
                    total_dirs = len(direcciones_unicas)
                    
                    st.info(f"Iniciando escaneo de {total_dirs} direcciones...")
                    barra = st.progress(0)
                    texto_progreso = st.empty()
                    
                    dic_coords = {}
                    for i, d in enumerate(direcciones_unicas):
                        texto_progreso.text(f"Buscando por satélite ({i+1}/{total_dirs}): {d}")
                        lat, lon = obtener_coordenada_unica(d)
                        dic_coords[d] = (lat, lon)
                        barra.progress((i + 1) / total_dirs)
                    
                    texto_progreso.empty()
                    barra.empty()
                    
                    df['lat'] = df['direccion_final'].map(lambda x: dic_coords.get(x, (None, None))[0])
                    df['lon'] = df['direccion_final'].map(lambda x: dic_coords.get(x, (None, None))[1])
                    
                    df_mapa = df.dropna(subset=['lat', 'lon'])
                    
                    if not df_mapa.empty:
                        fig_mapa = px.scatter_mapbox(
                            df_mapa, 
                            lat="lat", 
                            lon="lon", 
                            color="delito_final", 
                            hover_name="direccion_final", 
                            zoom=12, 
                            height=600
                        )
                        fig_mapa.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
                        st.plotly_chart(fig_mapa, use_container_width=True)
                        
                        encontrados = len(df_mapa)
                        if encontrados < len(df):
                            mensaje_alerta = f"⚠️ Se ubicaron {encontrados} de {len(df)} registros. Algunas direcciones pueden ser muy ambiguas."
                            st.warning(mensaje_alerta)
                        else:
                            st.success("✅ ¡Todas las direcciones fueron ubicadas con éxito en La Florida!")
                    else:
                        st.error("❌ No se encontraron coordenadas exactas para ninguna de las direcciones.")
            else:
                st.warning("No hay datos para mostrar en el mapa.")

        # PESTAÑA 3: ADMINISTRACIÓN
        with tab3:
            st.header("Área de Administración")
            clave_ingresada = st.text_input("🔑 Ingrese la clave de administrador:", type="password")
            
            clave_secreta = "Florida2026" 
            if "admin" in st.secrets and "clave" in st.secrets["admin"]:
                clave_secreta = st.secrets["admin"]["clave"]
                
            if clave_ingresada == clave_secreta:
                st.success("✅ Acceso concedido.")
                opciones = ["RLH", "RCI", "RCV", "RP", "Otros"]

                admin_tab1, admin_tab2 = st.tabs(["➕ Ingresar Nuevo", "✏️ Editar o Borrar Registro"])

                with admin_tab1:
                    with st.form("formulario_registro", clear_on_submit=True):
                        col1, col2 = st.columns(2)
                        with col1: fecha_in = st.date_input("Fecha del Suceso", datetime.now())
                        with col2: dir_in = st.text_input("Dirección / Ubicación")
                        
                        t_sel = st.selectbox("Tipo de Delito", opciones)
                        t_otro = st.text_input("Si eligió 'Otros', escriba el tipo de procedimiento aquí:")
                        
                        c1, c2, c3 = st.columns(3)
                        with c1: tiene_img = st.checkbox("¿Imágenes?")
                        with c2: tiene_vid = st.checkbox("¿Videos?")
                        with c3: es_rel = st.checkbox("¿Relevante?")
                            
                        det = st.text_area("Detalles")
                        if st.form_submit_button("Guardar Registro"):
                            t_fin = t_otro.strip() if t_sel == "Otros" and t_otro else t_sel
                            coleccion.insert_one({
                                "fecha": datetime.combine(fecha_in, datetime.min.time()),
                                "direccion": dir_in,
                                "tipo_delito": t_fin,
                                "tiene_imagenes": tiene_img,
                                "tiene_videos": tiene_vid,
                                "es_relevante": es_rel,
                                "detalles": det,
                                "fecha_registro": datetime.now()
                            })
                            st.success("✅ Guardado correctamente")
                            st.rerun()
