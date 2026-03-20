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

# Pestañas
tab1, tab2 = st.tabs(["📊 Analítica y Reportes", "📝 Ingreso de Datos (Solo Admin)"])

# --- TAB 1: ANALÍTICA Y GENERADOR DE TXT ---
with tab1:
    st.header("Panel de Análisis de Datos")
    if client:
        try:
            db = client['observatorio_seguridad']
            coleccion = db['registro_delitos']
            datos = list(coleccion.find())
            
            if datos:
                df = pd.DataFrame(datos)
                
                # Fusión de columnas
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

                # Limpieza
                df['fecha_final'] = pd.to_datetime(df['fecha_final'], dayfirst=True, errors='coerce')
                df = df.dropna(subset=['direccion_final', 'delito_final'], how='all')
                df = df.sort_values(by='fecha_final', ascending=False)

                for col in ['img_final', 'vid_final']:
                    df[col] = df[col].apply(lambda x: "✅ Sí" if str(x).lower() in ['true', 'si', '1.0', '1'] else "❌ No")

                # Buscador
                busq = st.text_input("🔍 Buscar dirección o delito:", key="search_v5")
                if busq:
                    mask_dir = df['direccion_final'].astype(str).str.contains(busq, case=False, na=False)
                    mask_del = df['delito_final'].astype(str).str.contains(busq, case=False, na=False)
                    df = df[mask_dir | mask_del]

                # Gráfico
                st.subheader("Estadísticas")
                cnt = df['delito_final'].value_counts().reset_index()
                cnt.columns = ['Delito', 'Cant']
                fig = px.bar(cnt, x='Cant', y='Delito', orientation='h', text='Cant', color='Delito')
                fig.update_layout(showlegend=False, height=350, margin=dict(l=0, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)

                # --- TABLA INTERACTIVA PARA SELECCIONAR CASOS ---
                st.subheader("Selección de Casos para Fiscalía")
                st.write("📌 Marca la casilla 'Seleccionar' en los casos que necesites exportar al reporte.")
                
                df_v = df[['fecha_final', 'direccion_final', 'delito_final', 'img_final', 'vid_final', 'detalles_final']].copy()
                df_v.columns = ['Fecha', 'Dirección', 'Tipo de Delito', '¿Imágenes?', '¿Videos?', 'Detalles']
                df_v['Fecha'] = df_v['Fecha'].dt.strftime('%d de %B del %Y').str.replace('March', 'Marzo').str.replace('February', 'Febrero').str.replace('January', 'Enero') # Formateo chileno básico
                df_v['Detalles'] = df_v['Detalles'].fillna("-")
                
                # Agregamos la columna de checkbox al principio
                df_v.insert(0, "Seleccionar", False)

                # Usamos data_editor para que puedas marcar las casillas
                edited_df = st.data_editor(
                    df_v,
                    hide_index=True,
                    column_config={"Seleccionar": st.column_config.CheckboxColumn("Seleccionar", required=True)},
                    disabled=df_v.columns.drop("Seleccionar"), # Bloquea las otras columnas para que no edites los datos por error
                    use_container_width=True
                )

                # Filtramos solo los que marcaste
                seleccionados = edited_df[edited_df["Seleccionar"] == True]

                # --- GENERADOR DEL BLOC DE NOTAS (TXT) ---
                if not seleccionados.empty:
                    st.success(f"Has seleccionado {len(seleccionados)} caso(s) para el reporte.")
                    
                    # Construir el texto con el formato exacto que pediste
                    texto_reporte = "Estimadas/os,\n\nJunto con saludar y esperando se encuentren bien, adjunto información de hechos de relevancia.\n\n"
                    
                    contador = 1
                    for index, row in seleccionados.iterrows():
                        texto_reporte += f"{contador}- {row['Dirección']}, La Florida.\n"
                        texto_reporte += f"Fecha: {row['Fecha']}.\n"
                        texto_reporte += f"Hora: [EDITAR HORA] (como referencia)\n"
                        texto_reporte += f"Delito: {row['Tipo de Delito']}.\n"
                        
                        # Lógica automática para las observaciones
                        if row['¿Imágenes?'] == "❌ No" and row['¿Videos?'] == "❌ No":
                            obs = "En el lugar no fue posible realizar el levantamiento de material audiovisual."
                        else:
                            obs = "Se logró levantamiento de material audiovisual en el lugar."
                            
                        # Sumar los detalles si existen
                        if row['Detalles'] != "-":
                            obs += f" {row['Detalles']}"
                            
                        texto_reporte += f"Observaciones: {obs}\n\n"
                        contador += 1
                        
                    texto_reporte += "Isabel Romero\nRodrigo Schlack\nDepartamento de televigilancia y comunicación radial."

                    # Botón de descarga
                    st.download_button(
                        label="📄 Descargar Reporte (TXT)",
                        data=texto_reporte,
                        file_name=f"Reporte_Fiscalia_{datetime.now().strftime('%d%m%Y')}.txt",
                        mime="text/plain"
                    )

            else:
                st.info("Sin datos registrados.")
        except Exception as e:
            st.error(f"Error al procesar la tabla: {e}")

# --- TAB 2: INGRESO (PROTEGIDO) ---
with tab2:
    st.header("Registrar Nuevo Incidente")
    
    clave_ingresada = st.text_input("🔑 Ingrese la clave de administrador:", type="password")
    
    clave_secreta = "Florida2026" 
    if "admin" in st.secrets and "clave" in st.secrets["admin"]:
        clave_secreta = st.secrets["admin"]["clave"]
        
    if clave_ingresada == clave_secreta:
        st.success("✅ Acceso concedido.")
        if client:
            db = client['observatorio_seguridad']
            coleccion = db['registro_delitos']
            
            opciones = ["RLH", "RCI", "RCV", "RP", "Otros"]

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
    elif clave_ingresada != "":
        st.error("❌ Clave incorrecta. Solo el personal autorizado puede ingresar datos.")
