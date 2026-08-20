import streamlit as st
import pandas as pd
import json
import os
import io
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

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
                    "config_modulos": datos.get("config_modulos", []),
                    "tarjetas": datos.get("tarjetas", [])
                }
        except Exception:
            pass
    return {"gastos": [], "ingresos": [], "config_modulos": [], "tarjetas": []}

def guardar_datos_usuario(correo, gastos, ingresos, config_modulos, tarjetas):
    archivo = obtener_nombre_archivo_usuario(correo)
    datos_dict = {
        "gastos": gastos,
        "ingresos": ingresos,
        "config_modulos": config_modulos,
        "tarjetas": tarjetas
    }
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(datos_dict, f, ensure_ascii=False, indent=4)

# ---------------------------------------------------------
# MANEJO DE ESTADO DE SESIÓN
# ---------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "usuario_actual" not in st.session_state:
    st.session_state["usuario_actual"] = None

# ---------------------------------------------------------
# PÁGINA 1: INICIO DE SESIÓN / REGISTRO
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
                st.session_state["tarjetas"] = datos_u["tarjetas"]
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
                st.session_state["autenticado"] = True
                st.session_state["usuario_actual"] = reg_correo
                st.session_state["datos_gastos"] = []
                st.session_state["datos_ingresos"] = []
                st.session_state["config_modulos"] = []
                st.session_state["tarjetas"] = []
                st.success("¡Cuenta creada exitosamente!")
                st.rerun()

    st.stop()

# ---------------------------------------------------------
# PÁGINA 2: CONFIGURACIÓN DE TARJETAS Y MÓDULOS
# ---------------------------------------------------------
usuarios = cargar_usuarios()
nombre_usuario = usuarios.get(st.session_state["usuario_actual"], {}).get("nombre", "Usuario")

if not st.session_state.get("config_modulos"):
    st.balloons()
    st.title(f"👋 ¡Bienvenido, {nombre_usuario}!")
    st.markdown("### 🛠️ Personaliza tus Tarjetas y Métodos de Pago")

    col_chk1, col_chk2 = st.columns(2)
    with col_chk1:
        mod_credito = st.checkbox("💳 Tarjetas de Crédito", value=True)
        mod_debito = st.checkbox("🏦 Tarjetas de Débito / Cuentas Bancarias", value=True)
        mod_efectivo = st.checkbox("💵 Pagos en Efectivo", value=True)
    with col_chk2:
        mod_transf = st.checkbox("🔄 Transferencias Bancarias", value=True)
        mod_recurrentes = st.checkbox("📅 Pagos Recurrentes Fijos / Suscripciones", value=True)
        mod_ahorro = st.checkbox("💰 Sección de Ahorro e Inversión", value=True)

    tarjetas_config = []
    if mod_credito:
        st.markdown("---")
        st.subheader("💳 Registro de Tarjetas de Crédito (Cortes y Fechas)")
        num_tarjetas = st.number_input("¿Cuántas tarjetas de crédito posees?", min_value=1, max_value=10, value=2)
        
        for i in range(int(num_tarjetas)):
            st.markdown(f"**Tarjeta #{i+1}**")
            c_t1, c_t2, c_t3 = st.columns(3)
            with c_t1:
                t_nombre = st.text_input(f"Nombre / Banco:", value=f"Tarjeta {i+1}", key=f"t_name_{i}")
            with c_t2:
                t_corte = st.number_input(f"Día de Corte:", min_value=1, max_value=31, value=19, key=f"t_corte_{i}")
            with c_t3:
                t_pago = st.number_input(f"Día Límite de Pago:", min_value=1, max_value=31, value=10, key=f"t_pago_{i}")
            
            tarjetas_config.append({
                "nombre": t_nombre,
                "dia_corte": t_corte,
                "dia_pago": t_pago
            })

    btn_guardar_config = st.button("🚀 Configurar Perfil", type="primary")

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
            st.session_state["tarjetas"] = tarjetas_config
            guardar_datos_usuario(
                st.session_state["usuario_actual"],
                st.session_state["datos_gastos"],
                st.session_state["datos_ingresos"],
                st.session_state["config_modulos"],
                st.session_state["tarjetas"]
            )
            st.success("¡Perfil guardado con éxito!")
            st.rerun()

    st.stop()

# ---------------------------------------------------------
# PÁGINA 3: PANEL PRINCIPAL FINANCIERO
# ---------------------------------------------------------
st.sidebar.title(f"👤 {nombre_usuario}")
st.sidebar.caption(f"📧 {st.session_state['usuario_actual']}")

if st.sidebar.button("⚙️ Reconfigurar Módulos/Tarjetas"):
    st.session_state["config_modulos"] = []
    st.rerun()

if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state["autenticado"] = False
    st.session_state["usuario_actual"] = None
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("**Tarjetas Registradas:**")
for t in st.session_state.get("tarjetas", []):
    st.sidebar.write(f"💳 {t['nombre']} (Corte: {t['dia_corte']})")

st.title("📊 Control Financiero Personal")

# ---------------------------------------------------------
# FILTROS DE FECHA Y NAVEGACIÓN
# ---------------------------------------------------------
col_f1, col_f2 = st.columns(2)
with col_f1:
    mes_seleccionado = st.selectbox("📅 Seleccionar Mes:", range(1, 13), index=datetime.now().month - 1, format_func=lambda x: date(2000, x, 1).strftime('%B').capitalize())
with col_f2:
    anio_seleccionado = st.number_input("📆 Año:", min_value=2024, max_value=2040, value=datetime.now().year)

# ---------------------------------------------------------
# FORMULARIO DE REGISTRO
# ---------------------------------------------------------
tab_reg_gasto, tab_reg_ingreso = st.tabs(["🛍️ Registrar Consumo / Diferido", "💵 Registrar Ingreso"])

with tab_reg_gasto:
    st.subheader("📝 Registrar Consumo o Diferido")
    col_r1, col_r2, col_r3 = st.columns(3)

    opciones_pago = []
    if "Tarjetas de Crédito" in st.session_state["config_modulos"]:
        for t in st.session_state.get("tarjetas", []):
            opciones_pago.append(f"💳 Crédito: {t['nombre']}")
    if "Tarjetas de Débito" in st.session_state["config_modulos"]:
        opciones_pago.append("🏦 Tarjeta de Débito")
    if "Pagos en Efectivo" in st.session_state["config_modulos"]:
        opciones_pago.append("💵 Efectivo")
    if "Transferencias" in st.session_state["config_modulos"]:
        opciones_pago.append("🔄 Transferencia Bancaria")

    with col_r1:
        descripcion = st.text_input("Establecimiento / Concepto:", placeholder="Ej. Casa, Vacaciones, Supermercado")
        monto_base = st.number_input("Monto Base Total ($):", min_value=0.0, step=100.0)
        medio_pago = st.selectbox("Medio de Pago:", opciones_pago if opciones_pago else ["Efectivo"])

    with col_r2:
        es_credito = "💳 Crédito:" in medio_pago
        es_recurrente = st.checkbox("🔄 ¿Es un Pago Recurrente Fijo? (Mes a Mes)")
        
        if es_credito and not es_recurrente:
            cuota_total = st.number_input("Número Total de Cuotas:", min_value=1, max_value=120, value=12)
            cuota_inicial = st.number_input("Cuota Actual al Registrar:", min_value=1, max_value=cuota_total, value=1)
        else:
            cuota_total = 1
            cuota_inicial = 1

    with col_r3:
        fecha_inicio_gasto = st.date_input("Fecha de Primera Cuota / Consumo:", value=date.today())
        incluye_iva = st.radio("Manejo de IVA:", ["Sin IVA", "Ya incluye IVA", "+15% IVA"])

    btn_guardar_gasto = st.button("💾 Guardar Consumo", type="primary")

    if btn_guardar_gasto:
        if not descripcion.strip() or monto_base <= 0:
            st.error("Ingresa un concepto y monto válidos.")
        else:
            if incluye_iva == "+15% IVA":
                monto_final = monto_base * 1.15
            else:
                monto_final = monto_base

            monto_cuota_calculado = monto_final if es_recurrente else (monto_final / cuota_total)

            nuevo_gasto = {
                "id": int(datetime.now().timestamp() * 1000),
                "descripcion": descripcion.strip(),
                "monto_total_base": monto_final,
                "monto_cuota": round(monto_cuota_calculado, 2),
                "medio_pago": medio_pago,
                "es_recurrente": es_recurrente,
                "cuota_inicial": cuota_inicial,
                "cuota_total": cuota_total,
                "fecha_inicio": fecha_inicio_gasto.strftime("%Y-%m-%d")
            }

            st.session_state["datos_gastos"].append(nuevo_gasto)
            guardar_datos_usuario(
                st.session_state["usuario_actual"],
                st.session_state["datos_gastos"],
                st.session_state["datos_ingresos"],
                st.session_state["config_modulos"],
                st.session_state["tarjetas"]
            )
            st.success("✅ ¡Consumo guardado exitosamente!")
            st.rerun()

# ---------------------------------------------------------
# LÓGICA DE PROYECCIÓN DE GASTOS PARA EL MES SELECCIONADO
# ---------------------------------------------------------
gastos_proyectados = []

for g in st.session_state["datos_gastos"]:
    f_inicio = datetime.strptime(g["fecha_inicio"], "%Y-%m-%d").date()
    
    # 1. Manejo de Pagos Recurrentes Fijos
    if g["es_recurrente"]:
        if date(anio_seleccionado, mes_seleccionado, 1) >= date(f_inicio.year, f_inicio.month, 1):
            gastos_proyectados.append({
                "Concepto": g["descripcion"],
                "Medio de Pago": g["medio_pago"],
                "Cuota Progreso": "Recurrente",
                "Monto a Pagar": g["monto_cuota"],
                "Monto Total Base": g["monto_total_base"]
            })
    # 2. Manejo de Diferidos por Cuotas
    else:
        # Calcular meses transcurridos desde la fecha de inicio
        meses_diferencia = (anio_seleccionado - f_inicio.year) * 12 + (mes_seleccionado - f_inicio.month)
        cuota_actual_calculada = g["cuota_inicial"] + meses_diferencia

        # Verificar si la cuota cae dentro del rango válido (entre 1 y cuota_total)
        if 1 <= cuota_actual_calculada <= g["cuota_total"]:
            gastos_proyectados.append({
                "Concepto": g["descripcion"],
                "Medio de Pago": g["medio_pago"],
                "Cuota Progreso": f"Cuota {cuota_actual_calculada} de {g['cuota_total']}",
                "Monto a Pagar": g["monto_cuota"],
                "Monto Total Base": g["monto_total_base"]
            })

df_gastos_mes = pd.DataFrame(gastos_proyectados)

# ---------------------------------------------------------
# MOSTRAR RESULTADOS
# ---------------------------------------------------------
st.markdown("---")
st.subheader(f"📋 Resumen de Obligaciones: {date(2000, mes_seleccionado, 1).strftime('%B')} {anio_seleccionado}")

if not df_gastos_mes.empty:
    st.dataframe(df_gastos_mes, use_container_width=True)
    total_mes = df_gastos_mes["Monto a Pagar"].sum()
    st.metric("💳 Total a Pagar en este Mes:", f"${total_mes:,.2f}")
else:
    st.info("No hay obligaciones ni cuotas pendientes para este mes.")
