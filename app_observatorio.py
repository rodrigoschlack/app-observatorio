import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
import plotly.express as px
from bson.objectid import ObjectId

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

tab1, tab2 = st.tabs(["📊 Analítica y Reportes", "📝 Área de Administración (Privado)"])

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

                def arreglar_fecha_absoluta(val):
                    if pd.isna(val): return pd.NaT
                    s = str(val).split(' ')[0].replace('/', '-')
                    try:
                        parts = s.split('-')
                        if len(parts) == 3:
                            p1, p2, p3 = int(parts[0]), int(parts[1]), int(parts[2])
                            if p1 > 2000:
                                return datetime(p1, p2, p3)
                            if p1 <= 12:
                                return datetime(p3, p1, p2)
                            else:
                                return datetime(p3, p2, p1)
                    except:
                        pass
                    return pd.to_datetime(val, errors='coerce')

                df['fecha_final'] = df['fecha_final'].apply(arreglar_fecha_absoluta)
                df = df.dropna(subset=['direccion_final', 'delito_final'], how='all')
                
                df['_id_str'] = df['_id'].astype(str)
                df = df.sort_values(by=['fecha_final', '_id_str'], ascending=[False, False])

                for col in ['img_final', 'vid_final']:
                    df[col] = df[col].apply(lambda x: "✅ Sí" if str(x).lower() in ['true', 'si', '1.0', '1'] else "❌ No")

                # --- NUEVO: BARRA LATERAL DE FILTROS ---
                with st.sidebar:
                    st.header("⚙️ Filtros Avanzados")
                    st.write("Filtra los datos para tus reportes:")
                    
                    # 1. Filtro de Búsqueda de Texto
                    busq = st.text_input("🔍 Buscar dirección o delito:", placeholder="Ej: RCV o Pudeto")
                    
                    # 2. Filtro de Fechas
                    st.markdown("---")
                    st.write("📅 **Rango de Fechas**")
                    min_date = df['fecha_final'].min().date()
                    max_date = df['fecha_final'].max().date()
                    
                    fecha_inicio = st.date_input("Desde:", min_date, min_value=min_date, max_value=max_date)
                    fecha_fin = st.date_input("Hasta:", max_date, min_value=min_date, max_value=max_date)

                # --- APLICAR LOS FILTROS AL DATAFRAME ---
                if busq:
                    mask_dir = df['direccion_final'].astype(str).str.contains(busq, case=False, na=False)
                    mask_del = df['delito_final'].astype(str).str.contains(busq, case=False, na=False)
                    df = df[mask_dir | mask_del]

                # Filtro de fechas (convertimos la columna a date para poder comparar)
                mask_fechas = (df['fecha_final'].dt.date >= fecha_inicio) & (df['fecha_final'].dt.date <= fecha_fin)
                df = df[mask_fechas]

                # Si después de filtrar aún hay datos, mostramos todo
                if not df.empty:
                    m1, m2 = st.columns(2)
                    m1.metric("Total de Casos en este periodo", len(df))
                    
                    st.subheader("Estadísticas del periodo seleccionado")
                    cnt = df['delito_final'].value_counts().reset_index()
                    cnt.columns = ['Delito', 'Cant']
                    fig = px.bar(cnt, x='Cant', y='Delito', orientation='h', text='Cant', color='Delito')
                    fig.update_layout(showlegend=False, height=300, margin=dict(l=0, r=10, t=10, b=10))
                    st.plotly_chart(fig, use_container_width=True)

                    st.subheader("Selección de Casos para Fiscalía")
                    st.write("📌 Marca la casilla 'Seleccionar' en los casos que necesites exportar.")
                    
                    df_v = df[['fecha_final', 'direccion_final', 'delito_final', 'img_final', 'vid_final', 'detalles_final']].copy()
                    
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
                    st.warning("No hay registros en el rango de fechas seleccionado.")

            else:
                st.info("Sin datos registrados.")
        except Exception as e:
            st.error(f"Error al procesar la tabla: {e}")

# --- TAB 2: INGRESO Y EDICIÓN (PROTEGIDO) ---
with tab2:
    st.header("Área de Administración")
    
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

            with admin_tab2:
                st.write("Selecciona un registro reciente para modificarlo o eliminarlo de la base de datos.")
                ultimos = list(coleccion.find().sort("_id", -1).limit(100))
                
                if ultimos:
                    opciones_dict = {}
                    for r in ultimos:
                        f_str = "Fecha desc."
                        if "fecha" in r and isinstance(r["fecha"], datetime):
                            f_str = r["fecha"].strftime('%d-%m-%Y')
                        elif "Fecha" in r:
                            f_str = str(r["Fecha"]).split(" ")[0]
                            
                        d_str = r.get("direccion", r.get("Dirección", "Sin Dirección"))
                        t_str = r.get("tipo_delito", r.get("Tipo de delito", "Delito desc."))
                        
                        label = f"{f_str} | {d_str} | {t_str}"
                        opciones_dict[label] = r
                        
                    seleccion = st.selectbox("🔍 Buscar registro a editar:", ["Seleccione..."] + list(opciones_dict.keys()))
                    
                    if seleccion != "Seleccione...":
                        doc = opciones_dict[seleccion]
                        st.markdown("---")
                        
                        fecha_pre = doc.get("fecha", datetime.now())
                        if not isinstance(fecha_pre, datetime): fecha_pre = datetime.now()
                        dir_pre = doc.get("direccion", doc.get("Dirección", ""))
                        del_pre = doc.get("tipo_delito", doc.get("Tipo de delito", "RLH"))
                        img_pre = bool(doc.get("tiene_imagenes", doc.get("Imágenes", False)))
                        vid_pre = bool(doc.get("tiene_videos", doc.get("Videos", False)))
                        rel_pre = bool(doc.get("es_relevante", doc.get("Relevante", False)))
                        det_pre = doc.get("detalles", doc.get("Detalles", ""))
                        if pd.isna(det_pre): det_pre = ""
                        
                        e_fecha = st.date_input("Corregir Fecha", fecha_pre)
                        e_dir = st.text_input("Corregir Dirección", dir_pre)
                        
                        ops_edit = opciones.copy()
                        if del_pre not in ops_edit and del_pre != "Otros":
                            ops_edit.insert(0, del_pre)
                        e_del = st.selectbox("Corregir Delito", ops_edit, index=ops_edit.index(del_pre) if del_pre in ops_edit else 0)
                        
                        c1, c2, c3 = st.columns(3)
                        with c1: e_img = st.checkbox("¿Imágenes?", value=img_pre, key="e_img")
                        with c2: e_vid = st.checkbox("¿Videos?", value=vid_pre, key="e_vid")
                        with c3: e_rel = st.checkbox("¿Relevante?", value=rel_pre, key="e_rel")
                            
                        e_det = st.text_area("Corregir Detalles", value=str(det_pre))
                        
                        st.warning("⚠️ Los cambios serán permanentes.")
                        
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button("💾 Actualizar Registro", use_container_width=True):
                                coleccion.update_one(
                                    {"_id": doc["_id"]},
                                    {"$set": {
                                        "fecha": datetime.combine(e_fecha, datetime.min.time()),
                                        "direccion": e_dir,
                                        "tipo_delito": e_del,
                                        "tiene_imagenes": e_img,
                                        "tiene_videos": e_vid,
                                        "es_relevante": e_rel,
                                        "detalles": e_det
                                    }}
                                )
                                st.success("✅ Registro actualizado. Recargando...")
                                st.rerun()
                                
                        with col_btn2:
                            seguro = st.checkbox("Confirmar eliminación")
                            if st.button("🗑️ Eliminar Definitivamente", type="primary", use_container_width=True):
                                if seguro:
                                    coleccion.delete_one({"_id": doc["_id"]})
                                    st.error("🚨 Registro eliminado. Recargando...")
                                    st.rerun()
                                else:
                                    st.warning("Debes marcar la casilla de confirmación para borrar.")
                else:
                    st.info("No hay registros disponibles para editar.")

    elif clave_ingresada != "":
        st.error("❌ Clave incorrecta. Solo el personal autorizado puede ingresar datos.")
