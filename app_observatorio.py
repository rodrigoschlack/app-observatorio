import streamlit as st
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
import plotly.express as px
from bson.objectid import ObjectId
from geopy.geocoders import ArcGIS
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

# --- 2. MOTOR DE GEOLOCALIZACIÓN INTELIGENTE (ArcGIS) ---
@st.cache_data(show_spinner=False)
def obtener_coordenada_unica(d):
    try:
        time.sleep(0.5) 
        geolocator = ArcGIS(user_agent="observatorio_florida_app")
        dir_limpia = str(d).replace("&", "y").replace("N°", "").replace("Nro.", "")
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
        
        # Fusión de columnas antiguas y NUEVO CAMPO ARMAMENTO
        mapeos = {
            'fecha_final': ['fecha', 'Fecha'],
            'direccion_final': ['direccion', 'Dirección', 'Ubicación'],
            'delito_final': ['tipo_delito', 'Tipo de delito', 'Delito'],
            'img_final': ['tiene_imagenes', 'Imágenes', 'Imagenes'],
            'vid_final': ['tiene_videos', 'Videos', 'Video'],
            'detalles_final': ['detalles', 'Detalles'],
            'modalidad_final': ['modalidad', 'Modalidad'],
            'vehiculo_final': ['vehiculo', 'Vehículo'],
            'armamento_final': ['armamento', 'Armamento'], # <-- NUEVO
            'patente_final': ['patente', 'Patente'],
            'caracteristicas_final': ['caracteristicas', 'Características']
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

        # --- BARRA LATERAL (FILTROS MAESTROS) ---
        with st.sidebar:
            st.header("⚙️ Filtros del Sistema")
            busq = st.text_input("🔍 Buscar dirección, delito, patente, MO o arma:", placeholder="Ej: RCV, Pudeto o Arma de fuego")
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
            mask_mod = df['modalidad_final'].astype(str).str.contains(busq, case=False, na=False)
            mask_veh = df['vehiculo_final'].astype(str).str.contains(busq, case=False, na=False)
            mask_arm = df['armamento_final'].astype(str).str.contains(busq, case=False, na=False)
            mask_pat = df['patente_final'].astype(str).str.contains(busq, case=False, na=False)
            mask_car = df['caracteristicas_final'].astype(str).str.contains(busq, case=False, na=False)
            df = df[mask_dir | mask_del | mask_mod | mask_veh | mask_arm | mask_pat | mask_car]

        mask_fechas = (df['fecha_final'].dt.date >= fecha_inicio) & (df['fecha_final'].dt.date <= fecha_fin)
        df = df[mask_fechas]

        # --- LAS 3 PESTAÑAS PRINCIPALES ---
        tab1, tab2, tab3 = st.tabs(["📊 Analítica y Reportes", "🗺️ Mapa de Delitos", "📝 Área de Administración"])

        # PESTAÑA 1: TABLA Y TXT
        with tab1:
            if not df.empty:
                col_graf, col_intel = st.columns([1, 1.5])
                
                with col_graf:
                    st.subheader("Estadísticas del periodo")
                    cnt = df['delito_final'].value_counts().reset_index()
                    cnt.columns = ['Delito', 'Cant']
                    fig = px.bar(cnt, x='Cant', y='Delito', orientation='h', text='Cant', color='Delito')
                    fig.update_layout(showlegend=False, height=280, margin=dict(l=0, r=10, t=10, b=10))
                    st.plotly_chart(fig, use_container_width=True)

                # --- PANEL DE INTELIGENCIA CRIMINAL ---
                with col_intel:
                    st.subheader("🕵️‍♂️ Panel de Inteligencia Criminal")
                    
                    df_pat = df[(df['patente_final'].notna()) & (df['patente_final'] != "") & (df['patente_final'] != "-")]
                    if not df_pat.empty:
                        conteo_pat = df_pat['patente_final'].value_counts()
                        repetidas = conteo_pat[conteo_pat > 1]
                        if not repetidas.empty:
                            st.error("🚨 **¡ALERTA DE PATRÓN! Patentes reincidentes detectadas:**")
                            st.dataframe(repetidas.reset_index().rename(columns={'patente_final': 'Placa Patente', 'count': 'Cant. de Delitos'}), hide_index=True, use_container_width=True)
                    
                    df_mod = df[(df['modalidad_final'].notna()) & (df['modalidad_final'] != "") & (df['modalidad_final'] != "-")]
                    df_veh = df[(df['vehiculo_final'].notna()) & (df['vehiculo_final'] != "") & (df['vehiculo_final'] != "-")]
                    df_arm = df[(df['armamento_final'].notna()) & (df['armamento_final'] != "") & (df['armamento_final'] != "-")]
                    
                    c_m, c_v, c_a = st.columns(3)
                    with c_m:
                        if not df_mod.empty:
                            st.write("🔥 **Top Modalidad**")
                            st.dataframe(df_mod['modalidad_final'].value_counts().reset_index().rename(columns={'modalidad_final': 'Modalidad', 'count': 'Casos'}), hide_index=True)
                    with c_v:
                        if not df_veh.empty:
                            st.write("🚗 **Top Vehículos**")
                            st.dataframe(df_veh['vehiculo_final'].value_counts().reset_index().rename(columns={'vehiculo_final': 'Vehículo', 'count': 'Casos'}), hide_index=True)
                    with c_a:
                        if not df_arm.empty:
                            st.write("🔫 **Top Armamento**")
                            st.dataframe(df_arm['armamento_final'].value_counts().reset_index().rename(columns={'armamento_final': 'Armamento', 'count': 'Casos'}), hide_index=True)

                st.markdown("---")
                st.subheader("Selección de Casos para Fiscalía")
                
                df_v = df[['fecha_final', 'direccion_final', 'delito_final', 'modalidad_final', 'vehiculo_final', 'armamento_final', 'patente_final', 'caracteristicas_final', 'img_final', 'vid_final', 'detalles_final']].copy()
                df_v['fecha_final'] = df_v['fecha_final'].dt.strftime('%d-%m-%Y')
                
                for col in ['modalidad_final', 'vehiculo_final', 'armamento_final', 'patente_final', 'caracteristicas_final', 'detalles_final']:
                    df_v[col] = df_v[col].fillna("-")
                    
                df_v.columns = ['Fecha', 'Dirección', 'Tipo de Delito', 'Modalidad', 'Vehículo', 'Armamento', 'Patente', 'Características Sujetos', '¿Imágenes?', '¿Videos?', 'Detalles Generales']
                df_v.insert(0, "Seleccionar", False)

                edited_df = st.data_editor(
                    df_v, hide_index=True,
                    column_config={"Seleccionar": st.column_config.CheckboxColumn("Seleccionar", required=True)},
                    disabled=['Fecha', 'Dirección', 'Tipo de Delito', 'Modalidad', 'Vehículo', 'Armamento', 'Patente', 'Características Sujetos', '¿Imágenes?', '¿Videos?', 'Detalles Generales'], 
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
                        
                        mod = row.get('Modalidad', "-")
                        if mod != "-": texto_reporte += f"Modalidad: {mod}\n"
                            
                        veh = row.get('Vehículo', "-")
                        if veh != "-": texto_reporte += f"Vehículo Involucrado: {veh}\n"
                            
                        arm = row.get('Armamento', "-")
                        if arm != "-": texto_reporte += f"Armamento Utilizado: {arm}\n"
                            
                        pat = row.get('Patente', "-")
                        if pat != "-": texto_reporte += f"Placa Patente: {pat}\n"
                            
                        car = row.get('Características Sujetos', "-")
                        if car != "-": texto_reporte += f"Características de Sujetos: {car}\n"

                        obs = "En el lugar no fue posible realizar el levantamiento de material audiovisual." if row['¿Imágenes?'] == "❌ No" and row['¿Videos?'] == "❌ No" else "Se logró levantamiento de material audiovisual en el lugar."
                        det_gen = row.get('Detalles Generales', "-")
                        if det_gen != "-": obs += f" {det_gen}"
                        texto_reporte += f"Observaciones: {obs}\n\n"
                        contador += 1
                        
                    texto_reporte += "Isabel Romero\nRodrigo Schlack\nDepartamento de televigilancia y comunicación radial."
                    st.download_button("📄 Descargar Reporte (TXT)", data=texto_reporte, file_name=f"Reporte_Fiscalia_{datetime.now().strftime('%d%m%Y')}.txt", mime="text/plain")
            else:
                st.warning("No hay registros en el rango de fechas seleccionado.")

        # PESTAÑA 2: EL MAPA DE CALOR
        with tab2:
            st.header("🔥 Zona de Calor de Delitos")
            if not df.empty:
                st.write("Presiona el botón para escanear las direcciones y generar la zona de calor.")
                if st.button("🗺️ Generar Mapa de Calor", type="primary"):
                    direcciones_unicas = df['direccion_final'].unique()
                    total_dirs = len(direcciones_unicas)
                    
                    st.info(f"Geolocalizando {total_dirs} direcciones con satélite ArcGIS...")
                    barra = st.progress(0)
                    texto_progreso = st.empty()
                    
                    dic_coords = {}
                    for i, d in enumerate(direcciones_unicas):
                        texto_progreso.text(f"Ubicando ({i+1}/{total_dirs}): {d}")
                        lat, lon = obtener_coordenada_unica(d)
                        dic_coords[d] = (lat, lon)
                        barra.progress((i + 1) / total_dirs)
                    
                    texto_progreso.empty()
                    barra.empty()
                    
                    df['lat'] = df['direccion_final'].map(lambda x: dic_coords.get(x, (None, None))[0])
                    df['lon'] = df['direccion_final'].map(lambda x: dic_coords.get(x, (None, None))[1])
                    df_mapa = df.dropna(subset=['lat', 'lon']).copy()
                    
                    if not df_mapa.empty:
                        df_mapa['intensidad'] = 1 
                        fig_mapa = px.density_mapbox(
                            df_mapa, lat="lat", lon="lon", z="intensidad", radius=25,
                            hover_name="direccion_final", hover_data={"intensidad": False, "delito_final": True},
                            zoom=12, height=600
                        )
                        fig_mapa.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False)
                        st.plotly_chart(fig_mapa, use_container_width=True)
                        
                        encontrados = len(df_mapa)
                        if encontrados < len(df): st.warning(f"⚠️ Se ubicaron {encontrados} de {len(df)} registros exitosamente con ArcGIS.")
                        else: st.success("✅ ¡Ubicación perfecta! 100% de los datos mapeados.")
            else: st.warning("No hay datos para mostrar en el mapa.")

        # PESTAÑA 3: ADMINISTRACIÓN
        with tab3:
            st.header("Área de Administración")
            clave_ingresada = st.text_input("🔑 Ingrese la clave de administrador:", type="password")
            clave_secreta = "Florida2026" 
            if "admin" in st.secrets and "clave" in st.secrets["admin"]: clave_secreta = st.secrets["admin"]["clave"]
                
            if clave_ingresada == clave_secreta:
                st.success("✅ Acceso concedido.")
                opciones = ["RLH", "RCI", "RCV", "RP", "Otros"]

                admin_tab1, admin_tab2 = st.tabs(["➕ Ingresar Nuevo", "✏️ Editar o Borrar Registro"])

                with admin_tab1:
                    with st.form("formulario_registro", clear_on_submit=True):
                        st.write("📍 **Datos Principales del Suceso**")
                        col1, col2 = st.columns(2)
                        with col1: fecha_in = st.date_input("Fecha del Suceso", datetime.now())
                        with col2: dir_in = st.text_input("Dirección / Ubicación")
                        
                        t_sel = st.selectbox("Tipo de Delito", opciones)
                        t_otro = st.text_input("Si eligió 'Otros', escriba el tipo de procedimiento aquí:")
                        
                        st.markdown("---")
                        st.write("👤 **Datos de Sujetos / Modus Operandi (Opcional)**")
                        col_mod, col_veh = st.columns(2)
                        with col_mod: t_mod = st.text_input("Modalidad (Ej: Encerrona, Alunizaje, etc.)")
                        with col_veh: t_veh = st.text_input("Vehículo Involucrado (Ej: Moto roja, Sedán gris)")
                        
                        col_arm, col_pat = st.columns(2)
                        with col_arm: t_arm = st.text_input("Armamento (Ej: Arma de fuego, Arma blanca)")
                        with col_pat: t_pat = st.text_input("Placa Patente (Si se mantiene)")
                        
                        t_car = st.text_input("Características / Vestimenta de Sujetos")
                        
                        st.markdown("---")
                        c1, c2, c3 = st.columns(3)
                        with c1: tiene_img = st.checkbox("¿Imágenes?")
                        with c2: tiene_vid = st.checkbox("¿Videos?")
                        with c3: es_rel = st.checkbox("¿Relevante?")
                            
                        det = st.text_area("Detalles Generales del Procedimiento")
                        
                        if st.form_submit_button("Guardar Registro"):
                            t_fin = t_otro.strip() if t_sel == "Otros" and t_otro else t_sel
                            coleccion.insert_one({
                                "fecha": datetime.combine(fecha_in, datetime.min.time()), "direccion": dir_in, "tipo_delito": t_fin,
                                "modalidad": t_mod.strip(), "vehiculo": t_veh.strip(), "armamento": t_arm.strip(), "patente": t_pat.strip(), "caracteristicas": t_car.strip(),
                                "tiene_imagenes": tiene_img, "tiene_videos": tiene_vid, "es_relevante": es_rel, "detalles": det, "fecha_registro": datetime.now()
                            })
                            st.success("✅ Guardado correctamente")
                            st.rerun()

                with admin_tab2:
                    st.write("Selecciona un registro reciente para modificarlo o eliminarlo de la base de datos.")
                    ultimos = list(coleccion.find().sort("_id", -1).limit(100))
                    
                    if ultimos:
                        opciones_dict = {}
                        for r in ultimos:
                            f_str = r["fecha"].strftime('%d-%m-%Y') if "fecha" in r and isinstance(r["fecha"], datetime) else str(r.get("Fecha", "Fecha desc.")).split(" ")[0]
                            label = f"{f_str} | {r.get('direccion', 'Sin Dir.')} | {r.get('tipo_delito', 'S/D')}"
                            opciones_dict[label] = r
                            
                        seleccion = st.selectbox("🔍 Buscar registro a editar:", ["Seleccione..."] + list(opciones_dict.keys()))
                        
                        if seleccion != "Seleccione...":
                            doc = opciones_dict[seleccion]
                            st.markdown("---")
                            
                            st.write("📍 **Corregir Datos Principales**")
                            e_fecha = st.date_input("Corregir Fecha", doc.get("fecha", datetime.now()) if isinstance(doc.get("fecha"), datetime) else datetime.now())
                            e_dir = st.text_input("Corregir Dirección", doc.get("direccion", doc.get("Dirección", "")))
                            
                            ops_edit = opciones.copy()
                            del_pre = doc.get("tipo_delito", "RLH")
                            if del_pre not in ops_edit and del_pre != "Otros": ops_edit.insert(0, del_pre)
                            e_del = st.selectbox("Corregir Delito", ops_edit, index=ops_edit.index(del_pre) if del_pre in ops_edit else 0)
                            
                            st.markdown("---")
                            st.write("👤 **Corregir Datos de Sujetos / Modus Operandi**")
                            col_emod, col_eveh = st.columns(2)
                            with col_emod: e_mod = st.text_input("Corregir Modalidad", doc.get("modalidad", ""))
                            with col_eveh: e_veh = st.text_input("Corregir Vehículo", doc.get("vehiculo", ""))
                            
                            col_earm, col_epat = st.columns(2)
                            with col_earm: e_arm = st.text_input("Corregir Armamento", doc.get("armamento", ""))
                            with col_epat: e_pat = st.text_input("Corregir Patente", doc.get("patente", ""))
                            
                            e_car = st.text_input("Corregir Características", doc.get("caracteristicas", ""))
                            
                            st.markdown("---")
                            c1, c2, c3 = st.columns(3)
                            with c1: e_img = st.checkbox("¿Imágenes?", value=bool(doc.get("tiene_imagenes", False)), key="e_img")
                            with c2: e_vid = st.checkbox("¿Videos?", value=bool(doc.get("tiene_videos", False)), key="e_vid")
                            with c3: e_rel = st.checkbox("¿Relevante?", value=bool(doc.get("es_relevante", False)), key="e_rel")
                                
                            e_det = st.text_area("Corregir Detalles Generales", value=str(doc.get("detalles", doc.get("Detalles", ""))))
                            
                            st.warning("⚠️ Los cambios serán permanentes.")
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                if st.button("💾 Actualizar Registro", use_container_width=True):
                                    coleccion.update_one({"_id": doc["_id"]}, {"$set": {
                                        "fecha": datetime.combine(e_fecha, datetime.min.time()), "direccion": e_dir, "tipo_delito": e_del, 
                                        "modalidad": e_mod.strip(), "vehiculo": e_veh.strip(), "armamento": e_arm.strip(), "patente": e_pat.strip(), "caracteristicas": e_car.strip(),
                                        "tiene_imagenes": e_img, "tiene_videos": e_vid, "es_relevante": e_rel, "detalles": e_det
                                    }})
                                    st.success("✅ Registro actualizado.")
                                    st.rerun()
                            with col_btn2:
                                if st.button("🗑️ Eliminar Definitivamente", type="primary", use_container_width=True):
                                    if st.checkbox("Confirmar eliminación", key="confirm_del"):
                                        coleccion.delete_one({"_id": doc["_id"]}); st.error("🚨 Registro eliminado."); st.rerun()
                                    else: st.warning("Debes marcar la casilla para borrar.")
                    else: st.info("No hay registros disponibles.")
            elif clave_ingresada != "": st.error("❌ Clave incorrecta.")
    else: st.info("Sin datos registrados o error de base de datos.")
