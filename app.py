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
# FUNCIONES DE AUTENTICACIÓN Y BASE DE DATOS LOCAL
# ---------------------------------------------------------
ARCH_USUARIOS = "usuarios_db.json"

def cargar_usuarios():
    if os.path.exists(ARCH_USUARIOS):
        try:
            with open(ARCH_USUARIOS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def guardar_usuarios(usuarios):
    with open(ARCH_USUARIOS, "w", encoding="utf-8") as f:
        json.dump(usuarios, f, ensure_ascii=False, indent=4)

def obtener_nombre_archivo_usuario(correo):
    correo_limpio = "".join(c for c in correo if c.isalnum() or c in ('@', '.', '_')).replace('@', '_at_').replace('.', '_')
    return f"datos_user_{correo_limpio}.json"

def cargar_datos_usuario(correo):
    archivo = obtener_nombre_archivo_usuario(correo)
    if os.path.exists(archivo):
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                datos = json.load(f)
                return {
                    "gastos": datos.get("gastos", []),
                    "ingresos": datos.get("ingresos", []),
                    "config_modulos": datos.get("config_modulos", [])
                }
        except Exception:
            pass
    return {"gastos": [], "ingresos": [], "config_modulos": []}

def guardar_datos_usuario(correo, gastos, ingresos, config_modulos):
    archivo = obtener_nombre_archivo_usuario(correo)
    datos_dict = {
        "gastos": gastos,
        "ingresos": ingresos,
        "config_modulos": config_modulos
    }
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(datos_dict, f, ensure_ascii=False, indent=4)

# ---------------------------------------------------------
# MANEJO DE ESTADO DE SESIÓN (LOGIN / REGISTRO)
# ---------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "usuario_actual" not in st.session_state:
    st.session_state["usuario_actual"] = None

# ---------------------------------------------------------
# PÁGINA 1: INICIO DE SESIÓN / REGISTRO DE USUARIO
# ---------------------------------------------------------
if not st.session_state["autenticado"]:
    st.title("🔐 Acceso al Sistema de Control Financiero")
    st.markdown("Bienvenido. Por favor inicia sesión o crea una cuenta para continuar.")

    tab_login, tab_registro = st.tabs(["🔑 Iniciar Sesión", "📝 Crear Cuenta"])

    usuarios = cargar_usuarios()

    with tab_login:
        st.subheader("Ingresa con tus credenciales")
        login_correo = st.text_input("Correo Electrónico:", key="login_email").lower().strip()
        login_pass = st.text_input("Contraseña:", type="password", key="login_pass")
        btn_login = st.button("Iniciar Sesión", type="primary")

        if btn_login:
            if login_correo in usuarios and usuarios[login_correo]["password"] == login_pass:
                st.session_state["autenticado"] = True
                st.session_state["usuario_actual"] = login_correo
                datos_u = cargar_datos_usuario(login_correo)
                st.session_state["datos_gastos"] = datos_u["gastos"]
                st.session_state["datos_ingresos"] = datos_u["ingresos"]
                st.session_state["config_modulos"] = datos_u["config_modulos"]
                st.success(f"¡Bienvenido de nuevo, {usuarios[login_correo]['nombre']}!")
                st.rerun()
            else:
                st.error("Correo o contraseña incorrectos.")

    with tab_registro:
        st.subheader("Regístrate como nuevo usuario")
        reg_nombre = st.text_input("Nombre y Apellido:", key="reg_nombre")
        reg_correo = st.text_input("Correo Electrónico:", key="reg_email").lower().strip()
        reg_pass = st.text_input("Contraseña:", type="password", key="reg_pass")
        reg_pass_conf = st.text_input("Confirmar Contraseña:", type="password", key="reg_pass_conf")
        btn_registro = st.button("Crear Cuenta")

        if btn_registro:
            if not reg_nombre.strip() or not reg_correo.strip() or not reg_pass:
                st.error("Por favor completa todos los campos.")
            elif reg_pass != reg_pass_conf:
                st.error("Las contraseñas no coinciden.")
            elif reg_correo in usuarios:
                st.error("Este correo electrónico ya está registrado.")
            else:
                usuarios[reg_correo] = {
                    "nombre": reg_nombre.strip(),
                    "password": reg_pass
                }
                guardar_usuarios(usuarios)
                # Iniciar sesión automáticamente
                st.session_state["autenticado"] = True
                st.session_state["usuario_actual"] = reg_correo
                st.session_state["datos_gastos"] = []
                st.session_state["datos_ingresos"] = []
                st.session_state["config_modulos"] = []
                st.success("¡Cuenta creada exitosamente!")
                st.rerun()

    st.stop() # Detiene la ejecución para no mostrar el panel si no ha iniciado sesión

# ---------------------------------------------------------
# PÁGINA 2: SELECCIÓN Y CONFIGURACIÓN DE MÓDULOS (CHECKBOXES)
# ---------------------------------------------------------
usuarios = cargar_usuarios()
nombre_usuario = usuarios.get(st.session_state["usuario_actual"], {}).get("nombre", "Usuario")

if not st.session_state.get("config_modulos"):
    st.balloons()
    st.title(f"👋 ¡Bienvenido a tu Sistema de Control Financiero, {nombre_usuario}!")
    st.markdown("### 🛠️ Personaliza tu Perfil")
    st.write("Selecciona los componentes y métodos de pago que utilizas frecuentemente para adaptar tu panel:")

    col_chk1, col_chk2 = st.columns(2)

    with col_chk1:
        mod_credito = st.checkbox("💳 Tarjetas de Crédito (Diners / Pacificard)", value=True)
        mod_debito = st.checkbox("🏦 Tarjetas de Débito / Cuentas Bancarias", value=True)
        mod_efectivo = st.checkbox("💵 Pagos en Efectivo", value=True)

    with col_chk2:
        mod_transf = st.checkbox("🔄 Transferencias Bancarias", value=True)
        mod_recurrentes = st.checkbox("📅 Pagos Recurrentes Fijos / Suscripciones", value=True)
        mod_ahorro = st.checkbox("💰 Sección de Ahorro e Inversión", value=True)

    btn_guardar_config = st.button("🚀 Configurar y Cargar Mi Perfil", type="primary")

    if btn_guardar_config:
        seleccionados = []
        if mod_credito: seleccionados.append("Tarjetas de Crédito")
        if mod_debito: seleccionados.append("Tarjetas de Débito")
        if mod_efectivo: seleccionados.append("Pagos en Efectivo")
        if mod_transf: seleccionados.append("Transferencias")
        if mod_recurrentes: seleccionados.append("Pagos Recurrentes")
        if mod_ahorro: seleccionados.append("Ahorro e Inversión")

        if not seleccionados:
            st.warning("Selecciona al menos una opción para continuar.")
        else:
            st.session_state["config_modulos"] = seleccionados
            guardar_datos_usuario(
                st.session_state["usuario_actual"],
                st.session_state["datos_gastos"],
                st.session_state["datos_ingresos"],
                st.session_state["config_modulos"]
            )
            st.success("¡Perfil cargado con éxito!")
            st.rerun()

    st.stop()

# ---------------------------------------------------------
# PÁGINA 3: PANEL PRINCIPAL FINANCIERO
# ---------------------------------------------------------
st.sidebar.title(f"👤 {nombre_usuario}")
st.sidebar.caption(f"📧 {st.session_state['usuario_actual']}")

if st.sidebar.button("⚙️ Reconfigurar Módulos"):
    st.session_state["config_modulos"] = []
    st.rerun()

if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state["autenticado"] = False
    st.session_state["usuario_actual"] = None
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("**Módulos Activos:**")
for mod in st.session_state["config_modulos"]:
    st.sidebar.write(f"✅ {mod}")

st.title(f"📊 Control Financiero Personal")

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
    st.subheader("📝 Registrar Nuevo Consumo")

    col_r1, col_r2, col_r3 = st.columns(3)

    # Filtrar medios de pago basados en la configuración seleccionada
    opciones_pago = []
    if "Tarjetas de Crédito" in st.session_state["config_modulos"]:
        opciones_pago.extend(["💳 Tarjeta Diners Club (Corte 19 al 18)", "💳 Tarjeta Pacificard (Corte 24 al 23)"])
    if "Tarjetas de Débito" in st.session_state["config_modulos"]:
        opciones_pago.append("🏦 Tarjeta de Débito")
    if "Pagos en Efectivo" in st.session_state["config_modulos"]:
        opciones_pago.append("💵 Efectivo")
    if "Transferencias" in st.session_state["config_modulos"]:
        opciones_pago.append("🔄 Transferencia Bancaria")
    if "Pagos Recurrentes" in st.session_state["config_modulos"]:
        opciones_pago.append("🔁 Pago Recurrente Fijo")

    if not opciones_pago:
        opciones_pago = ["💵 Efectivo / Otros"]

    with col_r1:
        descripcion = st.text_input("Establecimiento / Concepto:", placeholder="Ej. Supermaxi, Gimnasio")
        monto_base = st.number_input("Monto Base ($):", min_value=0.0, step=0.01)
        medio_pago = st.selectbox("Medio de Pago:", opciones_pago)

    with col_r2:
        es_contado = any(k in medio_pago for k in ["Efectivo", "Débito", "Transferencia"])
        es_recurrente = "Recurrente" in medio_pago

        if es_contado or es_recurrente:
            periodo_asignado = st.selectbox(
                "📌 Asignar Pago al Período:",
                ["Periodo 19 al 18 (Diners)", "Periodo 24 al 23 (Pacificard)"]
            )
        elif "Diners" in medio_pago:
            periodo_asignado = "Periodo 19 al 18 (Diners)"
        else:
            periodo_asignado = "Periodo 24 al 23 (Pacificard)"

        if es_contado:
            cuota_actual = 1
            cuota_total = 1
            st.info("ℹ️ Pago directo de contado.")
        else:
            c_c1, c_c2 = st.columns(2)
            with c_c1:
                cuota_total = st.number_input("Número Total Cuotas:", min_value=1, max_value=120, value=40 if es_recurrente else 1)
            with c_c2:
                cuota_actual = st.number_input("Cuota Actual:", min_value=1, max_value=120, value=1)

    with col_r3:
        incluye_iva = st.radio("Manejo de IVA:", ["Sin IVA / Exento", "Ya incluye IVA", "Sumar IVA (15%)"])
        if "Tarjetas de Crédito" in st.session_state["config_modulos"] and not es_contado:
            aplica_solca = st.checkbox("Aplica 0.5% SOLCA")
        else:
            aplica_solca = False

    btn_guardar_gasto = st.button("💾 Guardar Gasto", type="primary")

    if btn_guardar_gasto:
        if descripcion.strip() == "" or monto_base <= 0:
            st.error("Por favor ingresa un concepto válido y un monto mayor a 0.")
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
            monto_cuota_mensual = monto_final if (es_recurrente or es_contado) else (monto_final / cuota_total)

            nuevo_registro = {
                "id": int(datetime.now().timestamp() * 1000),
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
            guardar_datos_usuario(st.session_state["usuario_actual"], st.session_state["datos_gastos"], st.session_state["datos_ingresos"], st.session_state["config_modulos"])
            st.success(f"✅ ¡Gasto '{descripcion}' registrado!")
            st.rerun()

with tab_reg_ingreso:
    st.subheader("💵 Registrar Nuevo Ingreso")

    col_i1, col_i2, col_i3 = st.columns(3)

    with col_i1:
        fuente_ingreso = st.text_input("Fuente de Ingreso:", placeholder="Ej. Sueldo, Freelance")
    with col_i2:
        monto_ingreso = st.number_input("Monto ($):", min_value=0.0, step=10.0, key="monto_ingreso_val")
    with col_i3:
        fecha_ingreso = st.date_input("Fecha de Ingreso:", value=date.today())

    btn_guardar_ingreso = st.button("💾 Guardar Ingreso", type="primary", key="btn_ingreso")

    if btn_guardar_ingreso:
        if fuente_ingreso.strip() == "" or monto_ingreso <= 0:
            st.error("Ingresa una fuente válida y un monto mayor a $0.00")
        else:
            nuevo_ingreso = {
                "id": int(datetime.now().timestamp() * 1000),
                "Ciclo_Mes": str(mes_ciclo),
                "Año": str(anio_ciclo),
                "Fuente": fuente_ingreso.strip(),
                "Monto": round(monto_ingreso, 2),
                "Fecha_Ingreso": fecha_ingreso.strftime("%Y-%m-%d"),
                "Fecha_Registro": datetime.now().strftime("%Y-%m-%d %H:%M")
            }

            st.session_state["datos_ingresos"].append(nuevo_ingreso)
            guardar_datos_usuario(st.session_state["usuario_actual"], st.session_state["datos_gastos"], st.session_state["datos_ingresos"], st.session_state["config_modulos"])
            st.success(f"✅ ¡Ingreso de **${monto_ingreso:,.2f}** registrado!")
            st.rerun()

st.markdown("---")

# ---------------------------------------------------------
# RÉSUMEN Y BALANCE GENERAL
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
total_gastos_general = df_gastos["Monto_Cuota_Mensual"].sum() if not df_gastos.empty else 0.0
balance_neto = total_ingresos_mes - total_gastos_general

col_m1, col_m2, col_m3 = st.columns(3)
with col_m1:
    st.metric("💵 TOTAL INGRESOS", f"${total_ingresos_mes:,.2f}")
with col_m2:
    st.metric("💳 TOTAL GASTOS", f"${total_gastos_general:,.2f}")
with col_m3:
    st.metric("⚖️ BALANCE NETO", f"${balance_neto:,.2f}")

st.markdown("---")

# ---------------------------------------------------------
# TABLAS DE HISTORIAL
# ---------------------------------------------------------
cols_vis_gastos = ["Descripcion", "Medio_Pago", "Periodo_Asignado", "Cuota_Progreso", "Subtotal", "IVA_15", "SOLCA_05", "Monto_Cuota_Mensual"]

tab1, tab2, tab3 = st.tabs(["💵 Ingresos", "📋 Gastos Del Mes", "📚 Historial Global"])

with tab1:
    if not df_ingresos.empty:
        st.dataframe(df_ingresos[["Fuente", "Monto", "Fecha_Ingreso"]], use_container_width=True)
    else:
        st.info("Sin ingresos registrados en este ciclo.")

with tab2:
    if not df_gastos.empty:
        st.dataframe(df_gastos[cols_vis_gastos], use_container_width=True)
    else:
        st.info("Sin gastos registrados en este ciclo.")

with tab3:
    col_h1, col_h2 = st.columns(2)
    with col_h1:
        st.write("**Historial de Ingresos:**")
        if st.session_state["datos_ingresos"]:
            st.dataframe(pd.DataFrame(st.session_state["datos_ingresos"])[["Ciclo_Mes", "Año", "Fuente", "Monto"]], use_container_width=True)
    with col_h2:
        st.write("**Historial de Gastos:**")
        if st.session_state["datos_gastos"]:
            st.dataframe(pd.DataFrame(st.session_state["datos_gastos"])[["Ciclo_Mes", "Año", "Descripcion", "Monto_Cuota_Mensual"]], use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------
# EXPORTAR REPORTES (EXCEL Y PDF)
# ---------------------------------------------------------
st.subheader("📥 Exportar Reporte")
col_exp1, col_exp2 = st.columns(2)

with col_exp1:
    output_excel = io.BytesIO()
    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        df_resumen = pd.DataFrame([{"Usuario": nombre_usuario, "Ciclo": mes_ciclo, "Año": anio_ciclo, "Ingresos": total_ingresos_mes, "Gastos": total_gastos_general, "Balance": balance_neto}])
        df_resumen.to_excel(writer, sheet_name="Resumen", index=False)
        if not df_ingresos.empty:
            df_ingresos[["Fuente", "Monto", "Fecha_Ingreso"]].to_excel(writer, sheet_name="Ingresos", index=False)
        if not df_gastos.empty:
            df_gastos[cols_vis_gastos].to_excel(writer, sheet_name="Gastos", index=False)

    st.download_button(
        label="🟢 Descargar Reporte Excel (.xlsx)",
        data=output_excel.getvalue(),
        file_name=f"Reporte_{nombre_usuario}_{mes_ciclo.replace(' / ', '_')}_{anio_ciclo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

with col_exp2:
    buffer_pdf = io.BytesIO()
    p = canvas.Canvas(buffer_pdf, pagesize=letter)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, 750, f"Reporte Financiero — {nombre_usuario} ({mes_ciclo} {anio_ciclo})")
    p.line(50, 740, 550, 740)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, 715, f"Ingresos: ${total_ingresos_mes:,.2f} | Gastos: ${total_gastos_general:,.2f} | Balance: ${balance_neto:,.2f}")
    p.save()

    st.download_button(
        label="🔴 Descargar Reporte PDF (.pdf)",
        data=buffer_pdf.getvalue(),
        file_name=f"Reporte_{nombre_usuario}_{mes_ciclo.replace(' / ', '_')}_{anio_ciclo}.pdf",
        mime="application/pdf"
    )
