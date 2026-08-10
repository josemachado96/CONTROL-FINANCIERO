import streamlit as st
import pandas as pd
import json
import os
import io
from datetime import datetime, date

# Importación de ReportLab para exportar a PDF
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

st.set_page_config(
    page_title="Control Financiero Personal",
    page_icon="💰",
    layout="wide"
)

# ---------------------------------------------------------
# FUNCIONES DE ALMACENAMIENTO Y PERSISTENCIA
# ---------------------------------------------------------
ARCH_PERFILES = "perfiles_config.json"

def cargar_perfiles():
    if os.path.exists(ARCH_PERFILES):
        try:
            with open(ARCH_PERFILES, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return ["Usuario Principal"]

def guardar_perfiles(lista_perfiles):
    with open(ARCH_PERFILES, "w", encoding="utf-8") as f:
        json.dump(lista_perfiles, f, ensure_ascii=False, indent=4)

def obtener_nombre_archivo_perfil(nombre_perfil):
    nombre_limpio = "".join(c for c in nombre_perfil if c.isalnum() or c in (' ', '_')).rstrip()
    return f"datos_{nombre_limpio.replace(' ', '_')}.json"

def cargar_datos_perfil(nombre_perfil):
    archivo = obtener_nombre_archivo_perfil(nombre_perfil)
    if os.path.exists(archivo):
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                datos = json.load(f)
                if isinstance(datos, list):
                    return {"gastos": datos, "ingresos": []}
                if isinstance(datos, dict):
                    return {
                        "gastos": datos.get("gastos", []),
                        "ingresos": datos.get("ingresos", [])
                    }
        except Exception:
            pass
    return {"gastos": [], "ingresos": []}

def guardar_datos_perfil(nombre_perfil, gastos_lista, ingresos_lista):
    archivo = obtener_nombre_archivo_perfil(nombre_perfil)
    datos_dict = {
        "gastos": gastos_lista,
        "ingresos": ingresos_lista
    }
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(datos_dict, f, ensure_ascii=False, indent=4)

# ---------------------------------------------------------
# BARRA LATERAL: PERFILES Y RESPALDOS (BACKUP)
# ---------------------------------------------------------
st.sidebar.title("👤 Perfiles de Usuario")

perfiles = cargar_perfiles()
perfil_seleccionado = st.sidebar.selectbox("Selecciona tu Perfil:", perfiles)

# Crear nuevo perfil (límite 5)
with st.sidebar.expander("➕ Agregar Nuevo Perfil"):
    if len(perfiles) >= 5:
        st.warning("⚠️ Límite máximo de 5 perfiles.")
    else:
        nuevo_nombre = st.text_input("Nombre y Apellido:")
        if st.button("Crear Perfil"):
            if nuevo_nombre.strip() != "":
                if nuevo_nombre.strip() in perfiles:
                    st.error("Este perfil ya existe.")
                else:
                    perfiles.append(nuevo_nombre.strip())
                    guardar_perfiles(perfiles)
                    st.success(f"Perfil '{nuevo_nombre.strip()}' creado.")
                    st.rerun()
            else:
                st.error("Ingresa un nombre válido.")

st.sidebar.markdown("---")

# Cargar/Sincronizar datos del perfil activo
if "perfil_actual" not in st.session_state or st.session_state.get("perfil_actual") != perfil_seleccionado:
    st.session_state["perfil_actual"] = perfil_seleccionado
    datos_cargados = cargar_datos_perfil(perfil_seleccionado)
    st.session_state["datos_gastos"] = datos_cargados["gastos"]
    st.session_state["datos_ingresos"] = datos_cargados["ingresos"]

# Módulo de Copia de Seguridad en la Nube
st.sidebar.subheader("💾 Copia de Seguridad (Nube)")

# Exportar Respaldo
backup_data = {
    "perfiles": perfiles,
    "perfil_activo": perfil_seleccionado,
    "gastos": st.session_state["datos_gastos"],
    "ingresos": st.session_state["datos_ingresos"]
}
json_backup = json.dumps(backup_data, ensure_ascii=False, indent=4)

st.sidebar.download_button(
    label="📥 Descargar Respaldo Datos (.json)",
    data=json_backup,
    file_name=f"backup_finanzas_{perfil_seleccionado}.json",
    mime="application/json"
)

# Importar Respaldo
uploaded_file = st.sidebar.file_uploader("📤 Restaurar Respaldo", type=["json"])
if uploaded_file is not None:
    try:
        data_restaurada = json.load(uploaded_file)
        if "gastos" in data_restaurada and "ingresos" in data_restaurada:
            st.session_state["datos_gastos"] = data_restaurada["gastos"]
            st.session_state["datos_ingresos"] = data_restaurada["ingresos"]
            guardar_datos_perfil(perfil_seleccionado, st.session_state["datos_gastos"], st.session_state["datos_ingresos"])
            st.sidebar.success("¡Datos restaurados con éxito!")
            st.rerun()
    except Exception as e:
        st.sidebar.error("Archivo de respaldo no válido.")

st.title(f"📊 Control Financiero — Perfil: {perfil_seleccionado}")

# ---------------------------------------------------------
# FILTROS DE CICLO Y MES/AÑO
# ---------------------------------------------------------
col_f1, col_f2 = st.columns(2)
with col_f1:
    mes_ciclo = st.selectbox(
        "📅 Selección de Mes / Ciclo Doble:",
        ["Enero / Febrero", "Febrero / Marzo", "Marzo / Abril", "Abril / Mayo",
         "Mayo / Junio", "Junio / Julio", "Julio / Agosto", "Agosto / Septiembre",
         "Septiembre / Octubre", "Octubre / Noviembre", "Noviembre / Diciembre", "Diciembre / Enero"]
    )
with col_f2:
    anio_ciclo = st.selectbox("📆 Año:", [str(a) for a in range(2026, 2036)])

# ---------------------------------------------------------
# FORMULARIOS DE REGISTRO
# ---------------------------------------------------------
tab_reg_gasto, tab_reg_ingreso = st.tabs(["🛍️ Registrar Gasto / Consumo", "💵 Registrar Ingreso / Fuente"])

with tab_reg_gasto:
    st.subheader("📝 Registrar Nuevo Consumo o Pago Fijo")

    col_r1, col_r2, col_r3 = st.columns(3)

    with col_r1:
        descripcion = st.text_input("Establecimiento / Concepto:", placeholder="Ej. Supermaxi, Gimnasio, GánaVacaciones")
        monto_base = st.number_input("Monto / Valor Base ($):", min_value=0.0, step=0.01)
        
        medio_pago = st.selectbox(
            "Medio de Pago / Tipo de Consumo:",
            [
                "💳 Tarjeta Diners Club (Corte 19 al 18)",
                "💳 Tarjeta Pacificard (Corte 24 al 23)",
                "🔄 Pago Recurrente Mensual (Fijo / Cuotas Largas)",
                "💵 Efectivo / Transferencia"
            ]
        )

    with col_r2:
        es_efectivo = ("Efectivo" in medio_pago)
        es_recurrente = ("Recurrente" in medio_pago)

        if es_efectivo or es_recurrente:
            periodo_asignado = st.selectbox(
                "📌 Asignar Pago al Período:",
                ["Periodo 19 al 18 (Diners)", "Periodo 24 al 23 (Pacificard)"]
            )
        elif "Diners" in medio_pago:
            periodo_asignado = "Periodo 19 al 18 (Diners)"
        else:
            periodo_asignado = "Periodo 24 al 23 (Pacificard)"

        if es_efectivo:
            cuota_actual = 1
            cuota_total = 1
            st.info("ℹ️ Pago contado en efectivo.")
        else:
            c_c1, c_c2 = st.columns(2)
            with c_c1:
                cuota_total = st.number_input("Número Total de Cuotas:", min_value=1, max_value=120, value=40 if es_recurrente else 1)
            with c_c2:
                cuota_actual = st.number_input("Cuota Actual:", min_value=1, max_value=120, value=1)

    with col_r3:
        incluye_iva = st.radio("Manejo de IVA:", ["Sin IVA / Exento", "Ya incluye IVA", "Sumar IVA (15%)"])
        if not es_efectivo and not es_recurrente:
            aplica_solca = st.checkbox("Aplica 0.5% SOLCA (Diferidos crédito)")
        else:
            aplica_solca = False

    btn_guardar_gasto = st.button("💾 Guardar Gasto", type="primary")

    if btn_guardar_gasto:
        if descripcion.strip() == "" or monto_base <= 0:
            st.error("Por favor ingresa un concepto válido y un monto mayor a 0.")
        elif cuota_actual > cuota_total:
            st.error(f"La cuota actual ({cuota_actual}) no puede ser mayor que las cuotas totales ({cuota_total}).")
        else:
            if incluye_iva == "Sumar IVA (15%)":
                subtotal = monto_base
                iva = subtotal * 0.15
                monto_con_iva = subtotal + iva
            elif incluye_iva == "Ya incluye IVA":
                subtotal = monto_base / 1.15
                iva = monto_base - subtotal
                monto_con_iva = monto_base
            else:
                subtotal = monto_base
                iva = 0.0
                monto_con_iva = monto_base

            monto_solca = (subtotal * 0.005) if aplica_solca else 0.0
            monto_final = monto_con_iva + monto_solca
            monto_cuota_mensual = monto_final if (es_recurrente or es_efectivo) else (monto_final / cuota_total)

            nuevo_id = int(datetime.now().timestamp() * 1000)

            nuevo_registro = {
                "id": nuevo_id,
                "Perfil": perfil_seleccionado,
                "Ciclo_Mes": str(mes_ciclo),
                "Año": str(anio_ciclo),
                "Descripcion": descripcion.strip(),
                "Medio_Pago": medio_pago,
                "Periodo_Asignado": periodo_asignado,
                "Subtotal": round(subtotal, 2),
                "IVA_15": round(iva, 2),
                "SOLCA_05": round(monto_solca, 2),
                "Cuota_Actual": int(cuota_actual),
                "Cuota_Total": int(cuota_total),
                "Cuota_Progreso": f"{cuota_actual}/{cuota_total}",
                "Monto_Cuota_Mensual": round(monto_cuota_mensual, 2),
                "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
            }

            st.session_state["datos_gastos"].append(nuevo_registro)
            guardar_datos_perfil(perfil_seleccionado, st.session_state["datos_gastos"], st.session_state["datos_ingresos"])
            st.success(f"✅ ¡Gasto '{descripcion}' guardado para {mes_ciclo} {anio_ciclo}!")
            st.rerun()

with tab_reg_ingreso:
    st.subheader("💵 Registrar Nuevo Ingreso / Fuente de Dinero")

    col_i1, col_i2, col_i3 = st.columns(3)

    with col_i1:
        fuente_ingreso = st.text_input("Origen / Fuente del Ingreso:", placeholder="Ej. Sueldo, Freelance, Venta de Garage")
    with col_i2:
        monto_ingreso = st.number_input("Monto / Valor del Ingreso ($):", min_value=0.0, step=10.0, key="monto_ingreso_val")
    with col_i3:
        fecha_ingreso = st.date_input("Fecha de Ingreso:", value=date.today())

    btn_guardar_ingreso = st.button("💾 Guardar Ingreso", type="primary", key="btn_ingreso")

    if btn_guardar_ingreso:
        if fuente_ingreso.strip() == "" or monto_ingreso <= 0:
            st.error("Ingresa una fuente válida y un monto mayor a $0.00")
        else:
            nuevo_id_ing = int(datetime.now().timestamp() * 1000)
            nuevo_ingreso = {
                "id": nuevo_id_ing,
                "Perfil": perfil_seleccionado,
                "Ciclo_Mes": str(mes_ciclo),
                "Año": str(anio_ciclo),
                "Fuente": fuente_ingreso.strip(),
                "Monto": round(monto_ingreso, 2),
                "Fecha_Ingreso": fecha_ingreso.strftime("%Y-%m-%d"),
                "Fecha_Registro": datetime.now().strftime("%Y-%m-%d %H:%M")
            }

            st.session_state["datos_ingresos"].append(nuevo_ingreso)
            guardar_datos_perfil(perfil_seleccionado, st.session_state["datos_gastos"], st.session_state["datos_ingresos"])
            st.success(f"✅ ¡Ingreso de **${monto_ingreso:,.2f}** ('{fuente_ingreso}') guardado para {mes_ciclo} {anio_ciclo}!")
            st.rerun()

st.markdown("---")

# ---------------------------------------------------------
# FILTRADO Y MÉTRICAS
# ---------------------------------------------------------
st.subheader(f"📌 Resumen Financiero: {mes_ciclo} {anio_ciclo}")

gastos_filtrados = [
    g for g in st.session_state["datos_gastos"]
    if str(g.get("Ciclo_Mes")) == str(mes_ciclo) and str(g.get("Año")) == str(anio_ciclo)
]
df_gastos = pd.DataFrame(gastos_filtrados)

ingresos_filtrados = [
    i for i in st.session_state["datos_ingresos"]
    if str(i.get("Ciclo_Mes")) == str(mes_ciclo) and str(i.get("Año")) == str(anio_ciclo)
]
df_ingresos = pd.DataFrame(ingresos_filtrados)

total_ingresos_mes = df_ingresos["Monto"].sum() if not df_ingresos.empty else 0.0

if not df_gastos.empty:
    cols_requeridas = {
        "Descripcion": "", "Medio_Pago": "", "Periodo_Asignado": "Periodo 19 al 18 (Diners)",
        "Subtotal": 0.0, "IVA_15": 0.0, "SOLCA_05": 0.0,
        "Cuota_Actual": 1, "Cuota_Total": 1, "Cuota_Progreso": "1/1", "Monto_Cuota_Mensual": 0.0
    }
    for col, default_val in cols_requeridas.items():
        if col not in df_gastos.columns:
            df_gastos[col] = default_val

    df_p19_18 = df_gastos[df_gastos["Periodo_Asignado"] == "Periodo 19 al 18 (Diners)"]
    p19_diners = df_p19_18[df_p19_18["Medio_Pago"].str.contains("Diners", na=False)]["Monto_Cuota_Mensual"].sum() if not df_p19_18.empty else 0.0
    p19_efectivo = df_p19_18[~df_p19_18["Medio_Pago"].str.contains("Diners", na=False)]["Monto_Cuota_Mensual"].sum() if not df_p19_18.empty else 0.0
    total_p19_18 = p19_diners + p19_efectivo

    df_p24_23 = df_gastos[df_gastos["Periodo_Asignado"] == "Periodo 24 al 23 (Pacificard)"]
    p24_pacificard = df_p24_23[df_p24_23["Medio_Pago"].str.contains("Pacificard", na=False)]["Monto_Cuota_Mensual"].sum() if not df_p24_23.empty else 0.0
    p24_efectivo = df_p24_23[~df_p24_23["Medio_Pago"].str.contains("Pacificard", na=False)]["Monto_Cuota_Mensual"].sum() if not df_p24_23.empty else 0.0
    total_p24_23 = p24_pacificard + p24_efectivo

    total_gastos_general = total_p19_18 + total_p24_23
else:
    df_p19_18 = pd.DataFrame()
    df_p24_23 = pd.DataFrame()
    total_p19_18 = 0.0
    total_p24_23 = 0.0
    total_gastos_general = 0.0

balance_neto = total_ingresos_mes - total_gastos_general

# Métricas Principales
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
    st.metric("💵 TOTAL INGRESOS", f"${total_ingresos_mes:,.2f}")
with col_m2:
    st.metric("💳 TOTAL GASTOS", f"${total_gastos_general:,.2f}")
with col_m3:
    st.metric("⚖️ BALANCE NETO", f"${balance_neto:,.2f}")
with col_m4:
    if total_ingresos_mes > 0:
        porcentaje_gasto = (total_gastos_general / total_ingresos_mes) * 100
        st.metric("📉 % Compromiso Ingresos", f"{porcentaje_gasto:.1f}%")
    else:
        st.metric("📉 % Compromiso Ingresos", "N/A")

st.markdown("---")

# ---------------------------------------------------------
# TABLAS DE VISUALIZACIÓN E HISTORIAL
# ---------------------------------------------------------
cols_vis_gastos = ["Descripcion", "Medio_Pago", "Periodo_Asignado", "Cuota_Progreso", "Subtotal", "IVA_15", "SOLCA_05", "Monto_Cuota_Mensual"]

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "💵 Ingresos (Ciclo Actual)",
    "📋 Gastos (Ciclo Actual)", 
    "💳 Periodo 19 al 18 (Diners)", 
    "💳 Periodo 24 al 23 (Pacificard)",
    "🔄 Pagos Recurrentes / Efectivo",
    "📚 Todo el Historial (Global)"
])

with tab1:
    st.markdown(f"#### Total de Ingresos en {mes_ciclo} {anio_ciclo}: **${total_ingresos_mes:,.2f}**")
    if not df_ingresos.empty:
        st.dataframe(df_ingresos[["Fuente", "Monto", "Fecha_Ingreso", "Fecha_Registro"]], use_container_width=True)
    else:
        st.info(f"No hay ingresos registrados en el ciclo {mes_ciclo} {anio_ciclo}.")

with tab2:
    if not df_gastos.empty:
        st.dataframe(df_gastos[cols_vis_gastos], use_container_width=True)
    else:
        st.info(f"No hay gastos registrados en el ciclo {mes_ciclo} {anio_ciclo}.")

with tab3:
    if not df_p19_18.empty:
        st.dataframe(df_p19_18[cols_vis_gastos], use_container_width=True)
    else:
        st.info("No hay transacciones asociadas al periodo 19 al 18 en este ciclo.")

with tab4:
    if not df_p24_23.empty:
        st.dataframe(df_p24_23[cols_vis_gastos], use_container_width=True)
    else:
        st.info("No hay transacciones asociadas al periodo 24 al 23 en este ciclo.")

with tab5:
    if not df_gastos.empty:
        df_rec = df_gastos[df_gastos["Medio_Pago"].str.contains("Recurrente|Efectivo", na=False)]
        if not df_rec.empty:
            st.dataframe(df_rec[cols_vis_gastos], use_container_width=True)
        else:
            st.info("No hay pagos recurrentes o efectivo registrados en este ciclo.")
    else:
        st.info("Sin registros de gastos en este ciclo.")

with tab6:
    st.markdown("### 📜 Registros Históricos Acumulados")
    col_h1, col_h2 = st.columns(2)
    with col_h1:
        st.markdown("**Todos los Ingresos:**")
        if st.session_state["datos_ingresos"]:
            df_ing_global = pd.DataFrame(st.session_state["datos_ingresos"])
            st.dataframe(df_ing_global[["Ciclo_Mes", "Año", "Fuente", "Monto", "Fecha_Ingreso"]], use_container_width=True)
        else:
            st.write("No hay ingresos en el historial.")

    with col_h2:
        st.markdown("**Todos los Gastos:**")
        if st.session_state["datos_gastos"]:
            df_gast_global = pd.DataFrame(st.session_state["datos_gastos"])
            st.dataframe(df_gast_global[["Ciclo_Mes", "Año", "Descripcion", "Medio_Pago", "Monto_Cuota_Mensual"]], use_container_width=True)
        else:
            st.write("No hay gastos en el historial.")

st.markdown("---")

# ---------------------------------------------------------
# MÓDULO PARA EDITAR O ELIMINAR REGISTROS
# ---------------------------------------------------------
st.subheader(f"⚙️ Modificar o Eliminar Registros — {perfil_seleccionado}")

ver_todos = st.checkbox("🌐 Ver todos los meses del historial (desmarcado solo muestra el ciclo actual)")

col_mod_g, col_mod_i = st.columns(2)

with col_mod_g:
    st.markdown("#### 🛍️ Editar / Borrar Gastos")
    gastos_editables = list(enumerate(st.session_state["datos_gastos"])) if ver_todos else [
        (idx, r) for idx, r in enumerate(st.session_state["datos_gastos"])
        if str(r.get("Ciclo_Mes")) == str(mes_ciclo) and str(r.get("Año")) == str(anio_ciclo)
    ]

    if gastos_editables:
        opciones_gasto = {
            f"[{r.get('Ciclo_Mes')} {r.get('Año')}] {r.get('Descripcion')} | ${float(r.get('Monto_Cuota_Mensual', 0)):.2f}": idx
            for idx, r in gastos_editables
        }
        sel_gasto = st.selectbox("Selecciona gasto:", list(opciones_gasto.keys()), key="sb_edit_gasto")
        idx_gasto_real = opciones_gasto[sel_gasto]
        item_g = st.session_state["datos_gastos"][idx_gasto_real]

        with st.expander("✏️ Opciones de Modificación"):
            edit_desc = st.text_input("Concepto / Local", value=item_g.get("Descripcion", ""), key="e_desc")
            edit_monto = st.number_input("Monto Mensual ($)", min_value=0.01, value=float(item_g.get("Monto_Cuota_Mensual", 0.01)), step=0.5, key="e_monto")
            
            c_g1, c_g2 = st.columns(2)
            with c_g1:
                if st.button("💾 Guardar Cambios Gasto", key="btn_g_edit"):
                    st.session_state["datos_gastos"][idx_gasto_real]["Descripcion"] = edit_desc
                    st.session_state["datos_gastos"][idx_gasto_real]["Monto_Cuota_Mensual"] = round(edit_monto, 2)
                    guardar_datos_perfil(perfil_seleccionado, st.session_state["datos_gastos"], st.session_state["datos_ingresos"])
                    st.success("Gasto actualizado exitosamente.")
                    st.rerun()
            with c_g2:
                if st.button("❌ Eliminar Gasto", type="primary", key="btn_g_del"):
                    st.session_state["datos_gastos"].pop(idx_gasto_real)
                    guardar_datos_perfil(perfil_seleccionado, st.session_state["datos_gastos"], st.session_state["datos_ingresos"])
                    st.success("Gasto eliminado exitosamente.")
                    st.rerun()
    else:
        st.info("No hay gastos disponibles para editar en la selección actual.")

with col_mod_i:
    st.markdown("#### 💵 Editar / Borrar Ingresos")
    ingresos_editables = list(enumerate(st.session_state["datos_ingresos"])) if ver_todos else [
        (idx, r) for idx, r in enumerate(st.session_state["datos_ingresos"])
        if str(r.get("Ciclo_Mes")) == str(mes_ciclo) and str(r.get("Año")) == str(anio_ciclo)
    ]

    if ingresos_editables:
        opciones_ingreso = {
            f"[{r.get('Ciclo_Mes')} {r.get('Año')}] {r.get('Fuente')} | ${float(r.get('Monto', 0)):.2f}": idx
            for idx, r in ingresos_editables
        }
        sel_ingreso = st.selectbox("Selecciona ingreso:", list(opciones_ingreso.keys()), key="sb_edit_ingreso")
        idx_ing_real = opciones_ingreso[sel_ingreso]
        item_i = st.session_state["datos_ingresos"][idx_ing_real]

        with st.expander("✏️ Opciones de Modificación"):
            edit_fuente = st.text_input("Fuente / Origen", value=item_i.get("Fuente", ""), key="e_fuente")
            edit_monto_i = st.number_input("Monto ($)", min_value=0.01, value=float(item_i.get("Monto", 0.01)), step=1.0, key="e_monto_i")
            
            c_i1, c_i2 = st.columns(2)
            with c_i1:
                if st.button("💾 Guardar Cambios Ingreso", key="btn_i_edit"):
                    st.session_state["datos_ingresos"][idx_ing_real]["Fuente"] = edit_fuente
                    st.session_state["datos_ingresos"][idx_ing_real]["Monto"] = round(edit_monto_i, 2)
                    guardar_datos_perfil(perfil_seleccionado, st.session_state["datos_gastos"], st.session_state["datos_ingresos"])
                    st.success("Ingreso actualizado exitosamente.")
                    st.rerun()
            with c_i2:
                if st.button("❌ Eliminar Ingreso", type="primary", key="btn_i_del"):
                    st.session_state["datos_ingresos"].pop(idx_ing_real)
                    guardar_datos_perfil(perfil_seleccionado, st.session_state["datos_gastos"], st.session_state["datos_ingresos"])
                    st.success("Ingreso eliminado exitosamente.")
                    st.rerun()
    else:
        st.info("No hay ingresos disponibles para editar en la selección actual.")

st.markdown("---")

# ---------------------------------------------------------
# EXPORTACIÓN A EXCEL (CORREGIDO SIN ERRORES DE HOJAS VACÍAS) Y PDF
# ---------------------------------------------------------
st.subheader("📥 Exportar Reporte del Perfil")

col_exp1, col_exp2 = st.columns(2)

with col_exp1:
    output_excel = io.BytesIO()
    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        # Pestaña fija que garantiza que la hoja NUNCA esté vacía
        df_resumen = pd.DataFrame([{
            "Perfil": perfil_seleccionado,
            "Ciclo": mes_ciclo,
            "Año": anio_ciclo,
            "Total Ingresos": total_ingresos_mes,
            "Total Gastos": total_gastos_general,
            "Balance Neto": balance_neto
        }])
        df_resumen.to_excel(writer, sheet_name="Resumen", index=False)

        if not df_ingresos.empty:
            df_ingresos[["Fuente", "Monto", "Fecha_Ingreso"]].to_excel(writer, sheet_name="Ingresos", index=False)
        if not df_gastos.empty:
            df_gastos[cols_vis_gastos].to_excel(writer, sheet_name="Consolidado_Gastos", index=False)
        if not df_p19_18.empty:
            df_p19_18[cols_vis_gastos].to_excel(writer, sheet_name="Periodo_19_18", index=False)
        if not df_p24_23.empty:
            df_p24_23[cols_vis_gastos].to_excel(writer, sheet_name="Periodo_24_23", index=False)

    st.download_button(
        label="🟢 Descargar Reporte Excel (.xlsx)",
        data=output_excel.getvalue(),
        file_name=f"Reporte_{perfil_seleccionado}_{mes_ciclo.replace(' / ', '_')}_{anio_ciclo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

with col_exp2:
    buffer_pdf = io.BytesIO()
    p = canvas.Canvas(buffer_pdf, pagesize=letter)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, 750, f"Reporte Financiero — {perfil_seleccionado} ({mes_ciclo} {anio_ciclo})")
    p.line(50, 740, 550, 740)

    y = 715
    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, y, f"Total Ingresos: ${total_ingresos_mes:,.2f} | Total Gastos: ${total_gastos_general:,.2f} | Balance: ${balance_neto:,.2f}")
    y -= 25

    if not df_ingresos.empty:
        p.setFont("Helvetica-Bold", 9)
        p.drawString(50, y, "--- INGRESOS ---")
        y -= 15
        p.setFont("Helvetica-Bold", 8)
        p.drawString(50, y, "Fuente")
        p.drawString(250, y, "Fecha")
        p.drawString(450, y, "Monto")
        y -= 12

        p.setFont("Helvetica", 8)
        for _, row_i in df_ingresos.iterrows():
            p.drawString(50, y, str(row_i['Fuente'])[:30])
            p.drawString(250, y, str(row_i['Fecha_Ingreso']))
            p.drawString(450, y, f"${row_i['Monto']:.2f}")
            y -= 14

    y -= 15
    if not df_gastos.empty:
        p.setFont("Helvetica-Bold", 9)
        p.drawString(50, y, "--- GASTOS ---")
        y -= 15
        p.setFont("Helvetica-Bold", 8)
        p.drawString(50, y, "Concepto")
        p.drawString(200, y, "Medio Pago")
        p.drawString(350, y, "Cuota")
        p.drawString(450, y, "Monto Mensual")
        y -= 12

        p.setFont("Helvetica", 8)
        for _, row in df_gastos.iterrows():
            p.drawString(50, y, str(row['Descripcion'])[:24])
            p.drawString(200, y, str(row['Medio_Pago'])[:22])
            p.drawString(350, y, str(row['Cuota_Progreso']))
            p.drawString(450, y, f"${row['Monto_Cuota_Mensual']:.2f}")
            y -= 14

            if y < 60:
                p.showPage()
                y = 750

    p.save()

    st.download_button(
        label="🔴 Descargar Reporte PDF (.pdf)",
        data=buffer_pdf.getvalue(),
        file_name=f"Reporte_{perfil_seleccionado}_{mes_ciclo.replace(' / ', '_')}_{anio_ciclo}.pdf",
        mime="application/pdf"
    )
