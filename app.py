import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import os
import io
from datetime import datetime, date
from jinja2 import Template

# Importación de ReportLab para exportar a PDF
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

st.set_page_config(
    page_title="Control Financiero Personal — FinanzaPro",
    page_icon="💰",
    layout="wide"
)

# ---------------------------------------------------------
# FUNCIONES DE AUTENTICACIÓN Y BASE DE DATOS LOCAL (JSON)
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
    st.markdown("Bienvenido a **FinanzaPro**. Inicia sesión o crea una cuenta para continuar.")

    tab_login, tab_registro = st.tabs(["🔑 Iniciar Sesión", "📝 Crear Cuenta"])
    usuarios = cargar_usuarios()

    with tab_login:
        st.subheader("Ingresa con tus credenciales")
        with st.form("form_login", clear_on_submit=False):
            login_correo = st.text_input("Correo Electrónico:", key="login_email").lower().strip()
            login_pass = st.text_input("Contraseña:", type="password", key="login_pass")
            btn_login = st.form_submit_button("Iniciar Sesión", type="primary")

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
        with st.form("form_registro", clear_on_submit=False):
            reg_nombre = st.text_input("Nombre y Apellido:", key="reg_nombre")
            reg_correo = st.text_input("Correo Electrónico:", key="reg_email").lower().strip()
            reg_pass = st.text_input("Contraseña:", type="password", key="reg_pass")
            reg_pass_conf = st.text_input("Confirmar Contraseña:", type="password", key="reg_pass_conf")
            btn_registro = st.form_submit_button("Crear Cuenta", type="primary")

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
# PÁGINA 2: CONFIGURACIÓN INICIAL DE TARJETAS Y MÓDULOS
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
        st.subheader("💳 Registro de Tarjetas de Crédito (Fechas de Corte y Pago)")
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
                "dia_corte": int(t_corte),
                "dia_pago": int(t_pago)
            })

    btn_guardar_config = st.button("🚀 Guardar Perfil y Continuar", type="primary")

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
# PÁGINA 3: PANEL PRINCIPAL (FORMULARIO + PLANTILLA STITCH)
# ---------------------------------------------------------
st.sidebar.title(f"👤 {nombre_usuario}")
st.sidebar.caption(f"📧 {st.session_state['usuario_actual']}")

if st.sidebar.button("⚙️ Reconfigurar Perfil"):
    st.session_state["config_modulos"] = []
    st.rerun()

if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state["autenticado"] = False
    st.session_state["usuario_actual"] = None
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("📅 Período de Visualización")
mes_seleccionado = st.sidebar.selectbox("Seleccionar Mes:", range(1, 13), index=datetime.now().month - 1, format_func=lambda x: date(2000, x, 1).strftime('%B').capitalize())
anio_seleccionado = st.sidebar.number_input("Año:", min_value=2024, max_value=2040, value=datetime.now().year)

# ---------------------------------------------------------
# FORMULARIOS PARA REGISTRAR GASTOS / INGRESOS
# ---------------------------------------------------------
with st.sidebar.expander("➕ Registrar Consumo / Ingreso", expanded=False):
    tab_gasto, tab_ingreso = st.tabs(["🛍️ Gasto", "💵 Ingreso"])

    with tab_gasto:
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

        desc_gasto = st.text_input("Concepto / Local:", placeholder="Ej. Casa, Vacaciones")
        monto_gasto = st.number_input("Monto Total ($):", min_value=0.0, step=10.0)
        medio_gasto = st.selectbox("Medio de Pago:", opciones_pago if opciones_pago else ["Efectivo"])
        
        es_credito = "💳 Crédito:" in medio_gasto
        es_recurrente = st.checkbox("🔄 Pago Recurrente Fijo")

        if es_credito and not es_recurrente:
            cuotas_totales = st.number_input("Número Total de Cuotas:", min_value=1, max_value=120, value=12)
            cuota_inicial = st.number_input("Cuota Actual al Registrar:", min_value=1, max_value=cuotas_totales, value=1)
        else:
            cuotas_totales = 1
            cuota_inicial = 1

        fecha_inicio_gasto = st.date_input("Fecha Inicio:", value=date.today())
        
        if st.button("💾 Guardar Consumo", type="primary"):
            if not desc_gasto.strip() or monto_gasto <= 0:
                st.error("Campos inválidos.")
            else:
                monto_cuota_calc = monto_gasto if es_recurrente else (monto_gasto / cuotas_totales)
                nuevo_gasto = {
                    "id": int(datetime.now().timestamp() * 1000),
                    "descripcion": desc_gasto.strip(),
                    "monto_total_base": monto_gasto,
                    "monto_cuota": round(monto_cuota_calc, 2),
                    "medio_pago": medio_gasto,
                    "es_recurrente": es_recurrente,
                    "cuota_inicial": cuota_inicial,
                    "cuota_total": cuotas_totales,
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
                st.success("¡Gasto registrado!")
                st.rerun()

    with tab_ingreso:
        fuente_ingreso = st.text_input("Fuente:", placeholder="Ej. Sueldo, Freelance")
        monto_ingreso = st.number_input("Monto ($):", min_value=0.0, step=100.0)
        
        if st.button("💾 Guardar Ingreso"):
            if not fuente_ingreso.strip() or monto_ingreso <= 0:
                st.error("Campos inválidos.")
            else:
                nuevo_ingreso = {
                    "id": int(datetime.now().timestamp() * 1000),
                    "Ciclo_Mes": str(mes_seleccionado),
                    "Año": str(anio_seleccionado),
                    "Fuente": fuente_ingreso.strip(),
                    "Monto": round(monto_ingreso, 2)
                }
                st.session_state["datos_ingresos"].append(nuevo_ingreso)
                guardar_datos_usuario(
                    st.session_state["usuario_actual"],
                    st.session_state["datos_gastos"],
                    st.session_state["datos_ingresos"],
                    st.session_state["config_modulos"],
                    st.session_state["tarjetas"]
                )
                st.success("¡Ingreso registrado!")
                st.rerun()

# ---------------------------------------------------------
# PROCESAMIENTO Y RENDERIZADO DE LA PLANTILLA STITCH (INDEX.HTML)
# ---------------------------------------------------------
def RENDERIZAR_FINANZA_PRO():
    # 1. Calcular Ingresos del Mes Seleccionado
    total_ingresos = sum(
        i["Monto"] for i in st.session_state["datos_ingresos"]
        if str(i.get("Ciclo_Mes")) == str(mes_seleccionado) and str(i.get("Año")) == str(anio_seleccionado)
    )

    # 2. Proyección de Cuotas Diferidas y Recurrentes
    gastos_proyectados = []
    total_gastos = 0.0

    for g in st.session_state["datos_gastos"]:
        f_inicio = datetime.strptime(g["fecha_inicio"], "%Y-%m-%d").date()
        
        if g.get("es_recurrente", False):
            if date(anio_seleccionado, mes_seleccionado, 1) >= date(f_inicio.year, f_inicio.month, 1):
                gastos_proyectados.append({
                    "Concepto": g["descripcion"],
                    "Medio de Pago": g["medio_pago"],
                    "Cuota Progreso": "Recurrente",
                    "Monto a Pagar": g["monto_cuota"]
                })
                total_gastos += g["monto_cuota"]
        else:
            meses_diff = (anio_seleccionado - f_inicio.year) * 12 + (mes_seleccionado - f_inicio.month)
            cuota_actual = g.get("cuota_inicial", 1) + meses_diff

            if 1 <= cuota_actual <= g.get("cuota_total", 1):
                gastos_proyectados.append({
                    "Concepto": g["descripcion"],
                    "Medio de Pago": g["medio_pago"],
                    "Cuota Progreso": f"Cuota {cuota_actual} de {g['cuota_total']}",
                    "Monto a Pagar": g["monto_cuota"]
                })
                total_gastos += g["monto_cuota"]

    balance_neto = total_ingresos - total_gastos
    nombre_mes = date(2000, mes_seleccionado, 1).strftime('%B').capitalize()

    # 3. Cargar y Renderizar Plantilla HTML de Stitch
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            plantilla = Template(f.read())
        
        html_final = plantilla.render(
            usuario=nombre_usuario,
            mes_nombre=nombre_mes,
            anio=anio_seleccionado,
            total_ingresos=total_ingresos,
            total_gastos=total_gastos,
            balance_neto=balance_neto,
            num_tarjetas=len(st.session_state.get("tarjetas", [])),
            gastos=gastos_proyectados,
            tarjetas=st.session_state.get("tarjetas", [])
        )

        components.html(html_final, height=880, scrolling=True)
    else:
        st.error("El archivo 'index.html' no se encuentra en el repositorio.")

# Ejecutar el renderizado de la interfaz principal
RENDERIZAR_FINANZA_PRO()
