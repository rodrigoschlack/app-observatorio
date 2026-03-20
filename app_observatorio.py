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

                # --- FUNCIÓN "MÁGICA" PARA ARREGLAR EL ERROR DE EXCEL ---
                def arreglar_fechas_locas(f):
                    if pd.isna(f): return pd.NaT
                    if isinstance(f, datetime): return f
                    
                    try:
                        s = str(f).split(' ')[0].replace('/', '-')
                        partes = s.split('-')
                        
                        if len(partes) == 3:
                            p1, p2, p3 = int(partes[0]), int(partes[1]), int(partes[2])
                            
                            # Si el formato viene bien de la App (YYYY-MM-DD)
                            if p1 > 2000:
                                return datetime(p1, p2, p3)
                            
                            # REGLAS ESTRICTAS PARA TUS DATOS DE EXCEL:
                            if p2 == 2: 
                                # Si el mes está al medio y es 2 -> FEBRERO (DD-MM-YYYY)
                                return datetime(p3, 2, p1)
                            elif p1 == 1: 
                                # Si el primer número es 1 -> ENERO (MM-DD-YYYY)
                                return datetime(p3, 1, p2)
                            else: 
                                # Para todo lo demás, forzamos formato CHILENO (DD-MM-YYYY)
                                if p2 <= 12:
                                    return datetime(p3, p2, p1)
                                else:
                                    return datetime(p3, p1, p2)
                    except:
                        pass
                    return pd.to_datetime(f, errors='coerce')

                # Aplicamos la magia y ordenamos
                df['fecha_final'] = df['fecha_final'].apply(arreglar_fechas_locas)
                df = df.dropna(subset=['direccion_final', 'delito_final'], how='all')
                
                # ORDEN CRONOLÓGICO: Más reciente (Febrero) arriba, más antiguo (Enero) abajo
                df = df.sort_values(by='fecha_final', ascending=False)

                for col in ['img_final', 'vid_final']:
                    df[col] = df[col].apply(lambda x: "✅ Sí" if str(x).lower() in ['true', 'si', '1.0', '1'] else "❌ No")

                busq = st.text_input("🔍 Buscar dirección o delito:", key="search_v5")
                if busq:
                    mask_dir = df['direccion_final'].astype(str).str.contains(busq, case=False, na=False)
                    mask_del = df['delito_final'].astype(str).str.contains(busq, case=False, na=False)
                    df = df[mask_dir | mask_del]

                st.subheader("Estadísticas")
                cnt = df['delito_final'].value_counts().reset_index()
                cnt.columns = ['Delito', 'Cant']
                fig = px.bar(cnt, x='Cant', y='Delito', orientation='h', text='Cant', color='Delito')
                fig.update_layout(showlegend=False, height=350, margin=dict(l=0, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("Selección de Casos para Fiscalía")
                st.write("📌 Marca la casilla 'Seleccionar' en los casos que necesites exportar.")
                
                df_v = df[['fecha_final', 'direccion_final', 'delito_final', 'img_final', 'vid_final', 'detalles_final']].copy()
                
                # FORMATEAMOS VISUALMENTE PARA QUE SIEMPRE VEAS DIA-MES-AÑO
                df_v['fecha_final'] = df_v['fecha_final'].dt.strftime('%d-%m-%Y')
                df_v['detalles_final'] = df_v['detalles_final'].fillna("-")
                
                df_v.columns = ['Fecha', 'Dirección', 'Tipo de Delito', '¿Imágenes?', '¿Videos?', 'Detalles']
                
                df_v.insert(0, "Seleccionar", False)

                edited_df = st.data_editor(
                    df_v,
                    hide_index=True,
                    column_config={"Seleccionar": st.column_config.CheckboxColumn("Seleccionar", required=True)},
                    disabled=['Fecha', 'Dirección', 'Tipo de Delito', '¿Imágenes?', '¿Videos?', 'Detalles'], 
                    use_container_width=True
                )

                seleccionados = edited_df[edited_df["Seleccionar"] == True]

                if not seleccionados.empty:
                    st.success(f"Has seleccionado {len(seleccionados)} caso(s) para el reporte.")
                    
                    texto_reporte = "Estimadas/os,\n\nJunto con saludar y esperando se encuentren bien, adjunto información de hechos de relevancia.\n\n"
                    
                    meses_es = {"01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril", "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto", "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"}
                    
                    contador = 1
                    for index, row in seleccionados.iterrows():
                        texto_reporte += f"{contador}- {row['Dirección']}, La Florida.\n"
                        
                        partes_fecha = str(row['Fecha']).split('-')
                        if len(partes_fecha) == 3:
                            fecha_formateada = f"{partes_fecha[0]} de {meses_es.get(partes_fecha[1], partes_fecha[1])} del {partes_fecha[2]}"
                        else:
                            fecha_formateada = row['Fecha']

                        texto_reporte += f"Fecha: {fecha_formateada}.\n"
                        texto_reporte += f"Hora: [EDITAR HORA] (como referencia)\n"
                        texto_reporte += f"Delito: {row['Tipo de Delito']}.\n"
                        
                        if row['¿Imágenes?'] == "❌ No" and row['¿Videos?'] == "❌ No":
                            obs = "En el lugar no fue posible realizar el levantamiento de material audiovisual."
                        else:
                            obs = "Se logró levantamiento de material audiovisual en el lugar."
                            
                        if row['Detalles'] != "-":
                            obs += f" {row['Detalles']}"
                            
                        texto_reporte += f"Observaciones: {obs}\n\n"
                        contador += 1
                        
                    texto_reporte += "Isabel Romero\nRodrigo Schlack\nDepartamento de televigilancia y comunicación radial."

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
