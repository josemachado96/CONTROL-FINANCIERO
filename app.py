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
# FUNCIONES DE ALMACENAMIENTO MULTI-PERFIL (GASTOS E INGRESOS)
# ---------------------------------------------------------
ARCH_PERFILES = "perfiles_config.json"

def cargar_perfiles():
    if os.path.exists(ARCH_PERFILES):
        with open(ARCH_PERFILES, "r", encoding="utf-8") as f:
            return json.load(f)
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
        with open(archivo, "r", encoding="utf-8") as f:
            datos = json.load(f)
            # Compatibilidad con archivos antiguos (que solo guardaban lista de gastos)
            if isinstance(datos, list):
                return {"gastos": datos, "ingresos": []}
            return datos
    return {"gastos": [], "ingresos": []}

def guardar_datos_perfil(nombre_perfil, datos_dict):
    archivo = obtener_nombre_archivo_perfil(nombre_perfil)
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(datos_dict, f, ensure_ascii=False, indent=4)

# ---------------------------------------------------------
# GESTIÓN DE SESIÓN Y PERFILES (BARRA LATERAL)
# ---------------------------------------------------------
st.sidebar.title("👤 Perfiles de Usuario")

perfiles = cargar_perfiles()
perfil_seleccionado = st.sidebar.selectbox("Selecciona tu Perfil:", perfiles)

# Crear nuevo perfil (límite 5)
with st.sidebar.expander("➕ Agregar Nuevo Perfil"):
    if len(perfiles) >= 5:
        st.warning("⚠️ Se ha alcanzado el límite máximo de 5 perfiles.")
    else:
        nuevo_nombre = st.text_input("Nombre y Apellido:")
        if st.button("Crear Perfil"):
            if nuevo_nombre.strip() != "":
                if nuevo_nombre.strip() in perfiles:
                    st.error("Este perfil ya existe.")
                else:
                    perfiles.append(nuevo_nombre.strip())
                    guardar_perfiles(perfiles)
                    st.success(f"Perfil '{nuevo_nombre.strip()}' creado con éxito.")
                    st.rerun()
            else:
                st.error("Ingresa un nombre válido.")

st.sidebar.markdown("---")

# Cargar los datos del perfil activo
if "perfil_actual" not in st.session_state or st.session_state.get("perfil_actual") != perfil_seleccionado:
    st.session_state["perfil_actual"] = perfil_seleccionado
    datos_cargados = cargar_datos_perfil(perfil_seleccionado)
    st.session_state["datos_gastos"] = datos_cargados.get("gastos", [])
    st.session_state["datos_ingresos"] = datos_cargados.get("ingresos", [])

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
# PESTAÑAS PRINCIPALES DE REGISTRO
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
                "Ciclo_Mes": mes_ciclo,
                "Año": anio_ciclo,
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
            guardar_datos_perfil(perfil_seleccionado, {
                "gastos": st.session_state["datos_gastos"],
                "ingresos": st.session_state["datos_ingresos"]
            })
            st.success(f"✅ ¡Gasto '{descripcion}' guardado con éxito!")
            st.rerun()

with tab_reg_ingreso:
    st.subheader("💵 Registrar Nuevo Ingreso / Fuente de Dinero")

    col_i1, col_i2, col_i3 = st.columns(3)

    with col_i1:
        fuente_ingreso = st.text_input("Origen / Fuente del Ingreso:", placeholder="Ej. Sueldo, Freelance, Venta de Garage, Bonos")
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
                "Ciclo_Mes": mes_ciclo,
                "Año": anio_ciclo,
                "Fuente": fuente_ingreso.strip(),
                "Monto": round(monto_ingreso, 2),
                "Fecha_Ingreso": fecha_ingreso.strftime("%Y-%m-%d"),
                "Fecha_Registro": datetime.now().strftime("%Y-%m-%d %H:%M")
            }

            st.session_state["datos_ingresos"].append(nuevo_ingreso)
            guardar_datos_perfil(perfil_seleccionado, {
                "gastos": st.session_state["datos_gastos"],
                "ingresos": st.session_state["datos_ingresos"]
            })
            st.success(f"✅ ¡Ingreso de **${monto_ingreso:,.2f}** desde '{fuente_ingreso}' guardado!")
            st.rerun()

st.markdown("---")

# ---------------------------------------------------------
# DESGLOSE Y MÉTRICAS BALANCE GENERAL (INGRESOS VS GASTOS)
# ---------------------------------------------------------
st.subheader(f"📌 Resumen Financiero: {mes_ciclo} {anio_ciclo}")

# Filtro de Gastos
gastos_filtrados = [
    g for g in st.session_state["datos_gastos"]
    if g.get("Ciclo_Mes") == mes_ciclo and g.get("Año") == anio_ciclo
]
df_gastos = pd.DataFrame(gastos_filtrados)

# Filtro de Ingresos
ingresos_filtrados = [
    i for i in st.session_state["datos_ingresos"]
    if i.get("Ciclo_Mes") == mes_ciclo and i.get("Año") == anio_ciclo
]
df_ingresos = pd.DataFrame(ingresos_filtrados)

total_ingresos_mes = df_ingresos["Monto"].sum() if not df_ingresos.empty else 0.0

if not df_gastos.empty:
    cols_requeridas = {
        "Descripcion": "",
        "Medio_Pago": "",
        "Periodo_Asignado": "Periodo 19 al 18 (Diners)",
        "Subtotal": 0.0,
        "IVA_15": 0.0,
        "SOLCA_05": 0.0,
        "Cuota_Actual": 1,
        "Cuota_Total": 1,
        "Cuota_Progreso": "1/1",
        "Monto_Cuota_Mensual": 0.0
    }

    for col, default_val in cols_requeridas.items():
        if col not in df_gastos.columns:
            df_gastos[col] = default_val

    if "Cuota_Progreso" not in df_gastos.columns or df_gastos["Cuota_Progreso"].isnull().any():
        df_gastos["Cuota_Progreso"] = df_gastos.apply(
            lambda r: f"{int(r.get('Cuota_Actual', 1))}/{int(r.get('Cuota_Total', 1))}", axis=1
        )

    # Totales Periodo Diners
    df_p19_18 = df_gastos[df_gastos["Periodo_Asignado"] == "Periodo 19 al 18 (Diners)"]
    p19_diners = df_p19_18[df_p19_18["Medio_Pago"].str.contains("Diners", na=False)]["Monto_Cuota_Mensual"].sum() if not df_p19_18.empty else 0.0
    p19_efectivo = df_p19_18[~df_p19_18["Medio_Pago"].str.contains("Diners", na=False)]["Monto_Cuota_Mensual"].sum() if not df_p19_18.empty else 0.0
    total_p19_18 = p19_diners + p19_efectivo

    # Totales Periodo Pacificard
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
    color_delta = "off" if balance_neto == 0 else ("normal" if balance_neto > 0 else "inverse")
    st.metric("⚖️ BALANCE NETO", f"${balance_neto:,.2f}")

with col_m4:
    if total_ingresos_mes > 0:
        porcentaje_gasto = (total_gastos_general / total_ingresos_mes) * 100
        st.metric("📉 % Compromiso Ingresos", f"{porcentaje_gasto:.1f}%")
    else:
        st.metric("📉 % Compromiso Ingresos", "N/A")

st.markdown("---")

# Tablas de Visualización
cols_vis_gastos = ["Descripcion", "Medio_Pago", "Periodo_Asignado", "Cuota_Progreso", "Subtotal", "IVA_15", "SOLCA_05", "Monto_Cuota_Mensual"]

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💵 Ingresos del Mes",
    "📋 Consolidado Gastos", 
    "💳 Periodo 19 al 18 (Diners)", 
    "💳 Periodo 24 al 23 (Pacificard)",
    "🔄 Pagos Recurrentes / Efectivo"
])
