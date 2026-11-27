import base64
import io
import json
import os
import re
import unicodedata
from datetime import date, datetime

from jinja2 import Template
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import streamlit as st
import streamlit.components.v1 as components

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None

st.set_page_config(
    page_title="FinanzaPro — Control Financiero con Capu 🐱",
    page_icon="🐱",
    layout="wide",
)

ARCHIVO_DATOS = "finanzas_datos.json"
MODELO_GEMINI = "gemini-2.5-flash-lite"


def normalizar_texto(texto: str) -> str:
    if not texto:
        return ""
    limpio = unicodedata.normalize("NFD", str(texto).lower().strip())
    limpio = "".join(c for c in limpio if unicodedata.category(c) != "Mn")
    return " ".join(limpio.split())


def nombre_hoja_excel(nombre: str, usados: set) -> str:
    limpio = re.sub(r'[\\/*?:\[\]]', "", str(nombre)).strip() or "Hoja"
    limpio = limpio.replace(" ", "_")[:28]
    candidato = limpio
    contador = 2
    while candidato.lower() in usados:
        sufijo = f"_{contador}"
        candidato = f"{limpio[:31 - len(sufijo)]}{sufijo}"
        contador += 1
    usados.add(candidato.lower())
    return candidato


def tarjetas_por_defecto():
    return [
        {
            "nombre": "Diners Club",
            "dia_corte": 19,
            "dia_pago": 10,
            "maximo_pagar": 500.0,
        },
        {
            "nombre": "Pacificard",
            "dia_corte": 24,
            "dia_pago": 15,
            "maximo_pagar": 400.0,
        },
    ]


def cargar_datos():
    base = {
        "usuario": "Jose Machado",
        "ingreso_base": 300.0,
        "porcentaje_gasto": 80.0,
        "extras_al_ahorro": True,
        "tarjetas": tarjetas_por_defecto(),
        "gastos": [],
        "ingresos": [],
    }
    if os.path.exists(ARCHIVO_DATOS):
        try:
            with open(ARCHIVO_DATOS, "r", encoding="utf-8") as f:
                data = json.load(f)
                base["usuario"] = str(data.get("usuario", "Jose Machado"))
                base["ingreso_base"] = float(data.get("ingreso_base", 300.0))
                base["porcentaje_gasto"] = float(data.get("porcentaje_gasto", 80.0))
                base["extras_al_ahorro"] = bool(data.get("extras_al_ahorro", True))
                tarjetas_guardadas = data.get("tarjetas")
                if isinstance(tarjetas_guardadas, list) and len(tarjetas_guardadas) > 0:
                    base["tarjetas"] = tarjetas_guardadas
                base["gastos"] = data.get("gastos", [])
                base["ingresos"] = data.get("ingresos", [])
        except Exception:
            pass
    return base


def guardar_datos():
    payload = {
        "usuario": st.session_state["usuario"],
        "ingreso_base": st.session_state["ingreso_base"],
        "porcentaje_gasto": st.session_state["porcentaje_gasto"],
        "extras_al_ahorro": st.session_state["extras_al_ahorro"],
        "tarjetas": st.session_state["tarjetas"],
        "gastos": st.session_state["gastos"],
        "ingresos": st.session_state["ingresos"],
    }
    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)


# ---------------------------------------------------------
# GESTOS, IMÁGENES/GIFS Y BURBUJA DE CAPU
# ---------------------------------------------------------
RUTAS_GESTOS_CAPU = {
    "caminando": [
        "capu_caminando.gif", "assets/capu_caminando.gif",
        "capu_caminando.png", "capu_normal.jpeg", "assets/capu_normal.jpeg",
    ],
    "hablando": [
        "capu_hablando.gif", "assets/capu_hablando.gif",
        "capu_hablando.png", "capu_hablando.jpeg", "assets/capu_hablando.jpeg",
    ],
    "curioso": [
        "capu_curioso.gif", "assets/capu_curioso.gif",
        "capu_curioso.png", "capu_normal.jpeg", "assets/capu_normal.jpeg",
    ],
    "molesto": [
        "capu_molesto.gif", "assets/capu_molesto.gif",
        "capu_molesto.png", "capu_alerta.jpeg", "assets/capu_alerta.jpeg",
    ],
}


def buscar_medio_capu(gesto: str):
    candidatos = RUTAS_GESTOS_CAPU.get(gesto, []) + RUTAS_GESTOS_CAPU["caminando"]
    for ruta in candidatos:
        if os.path.exists(ruta):
            ext = os.path.splitext(ruta)[1].lower()
            es_gif = ext == ".gif"
            mime = (
                "image/gif"
                if es_gif
                else ("image/png" if ext == ".png" else "image/jpeg")
            )
            with open(ruta, "rb") as f:
                uri = f"data:{mime};base64," + base64.b64encode(f.read()).decode("utf-8")
            return uri, es_gif
    return "", False


def resolver_gesto_capu(
    pregunta: str,
    disponible_mes: float,
    total_gastos_mes: float,
    ingresos_mes_val: float,
    alerta_tarjeta: bool = False,
    gesto_gemini: str = "",
) -> str:
    if disponible_mes < 0 or alerta_tarjeta:
        return "molesto"

    g_gem = normalizar_texto(gesto_gemini)
    if g_gem in ("caminando", "hablando", "curioso", "molesto"):
        return g_gem

    p = normalizar_texto(pregunta)
    if p:
        palabras_molesto = ["pasado", "excedi", "deuda", "error", "mal", "caro", "problema", "alerta"]
        palabras_curioso = ["cuanto", "como", "que pasa", "iva", "solca", "cuota", "ahorrar", "alcanza", "puedo", "tarjeta"]
        if any(w in p for w in palabras_molesto):
            return "molesto"
        if any(w in p for w in palabras_curioso):
            return "curioso"
        return "hablando"

    if total_gastos_mes > 0 or ingresos_mes_val > 0:
        return "hablando"
    return "caminando"


def _respuesta_local_respaldo(pregunta: str, contexto: dict) -> str:
    p = normalizar_texto(pregunta)
    mes = contexto["mes_nombre"]
    gastos = contexto["total_gastos_mes"]
    limite = contexto["limite_gasto_mensual"]
    disp = contexto["disponible_mes"]
    quincena = contexto["limite_gasto_quincenal"]
    ahorro = contexto["ahorro_proyectado_mes"]
    iva = contexto["total_iva_mes"]
    solca = contexto["total_solca_mes"]

    if "tarjeta" in p or "corte" in p or "maximo" in p:
        resumen_t = ", ".join(
            f"{t['nombre']} (usado ${t['consumo_actual']:,.2f} / máx ${t['maximo_pagar']:,.2f}, corte día {t['dia_corte']})"
            for t in contexto["tarjetas_detalle"]
        )
        return f"¡Miau! Estado de tus tarjetas en {mes}: {resumen_t or 'sin tarjetas configuradas'}."
    if "quincena" in p or "quincenal" in p:
        return (
            f"¡Miau! En {mes} tu tope quincenal de gasto es ${quincena:,.2f} "
            f"(sobre un límite mensual de ${limite:,.2f}). Te quedan ${disp:,.2f} disponibles en el mes."
        )
    if "iva" in p or "solca" in p:
        return (
            f"¡Miau! En {mes} llevas ${iva:,.2f} acumulados en IVA (15%) y "
            f"${solca:,.2f} en SOLCA (0.5%) dentro de tus ${gastos:,.2f} de gastos."
        )
    if "ahorr" in p or "extra" in p:
        return (
            f"¡Miau! Tu meta de ahorro proyectada para {mes} es ${ahorro:,.2f}, "
            f"incluyendo tus trabajos extras (${contexto['extras_mes']:,.2f})."
        )
    if disp < 0:
        return (
            f"¡Miau! Ojo en {mes}: llevas ${gastos:,.2f} en gastos y superaste tu cupo "
            f"de ${limite:,.2f} por ${abs(disp):,.2f}. Toca frenar compras no urgentes."
        )
    return (
        f"¡Miau! En {mes} llevas ${gastos:,.2f} de gastos, te quedan ${disp:,.2f} "
        f"disponibles de tu cupo (${limite:,.2f}) y vas con ${ahorro:,.2f} de ahorro proyectado."
    )


def responder_consulta_capu(pregunta: str, contexto: dict):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        try:
            if "GEMINI_API_KEY" in st.secrets:
                api_key = str(st.secrets["GEMINI_API_KEY"]).strip()
        except Exception:
            pass

    if not genai or not types or not api_key:
        texto_fb = _respuesta_local_respaldo(pregunta, contexto)
        gesto_fb = resolver_gesto_capu(
            pregunta,
            contexto["disponible_mes"],
            contexto["total_gastos_mes"],
            contexto["total_ingresos_mes"],
            contexto["alerta_tarjeta"],
        )
        return texto_fb, gesto_fb

    detalle_tarjetas_txt = "\n".join(
        f"  * {t['nombre']}: usado ${t['consumo_actual']:,.2f} de máximo ${t['maximo_pagar']:,.2f} "
        f"(corte día {t['dia_corte']}, pago día {t['dia_pago']})"
        for t in contexto["tarjetas_detalle"]
    ) or "  * Ninguna configurada"

    prompt_usuario = (
        f"Datos financieros de {contexto['usuario']} en {contexto['mes_nombre']} {contexto['anio_sel']}:\n"
        f"- Ingreso base mensual: ${contexto['ingreso_base']:,.2f}\n"
        f"- Total ingresos del mes (base + registrados): ${contexto['total_ingresos_mes']:,.2f}\n"
        f"- Trabajos extras del mes: ${contexto['extras_mes']:,.2f}\n"
        f"- Límite de gasto mensual: ${contexto['limite_gasto_mensual']:,.2f}\n"
        f"- Límite de gasto quincenal: ${contexto['limite_gasto_quincenal']:,.2f}\n"
        f"- Gastos proyectados del mes: ${contexto['total_gastos_mes']:,.2f}\n"
        f"- Disponible del cupo mensual: ${contexto['disponible_mes']:,.2f}\n"
        f"- Balance neto (Ingresos - Gastos): ${contexto['balance_neto']:,.2f}\n"
        f"- Meta de ahorro proyectada: ${contexto['ahorro_proyectado_mes']:,.2f}\n"
        f"- IVA (15%) acumulado: ${contexto['total_iva_mes']:,.2f}\n"
        f"- SOLCA (0.5%) acumulado: ${contexto['total_solca_mes']:,.2f}\n"
        f"- Tarjetas de crédito:\n{detalle_tarjetas_txt}\n\n"
        f"Pregunta del usuario: {pregunta}"
    )

    instruccion_sistema = (
        "Eres Capu, un gato siamés asistente de control financiero personal en FinanzaPro. "
        "Responde en español, de forma clara, cercana y práctica, basándote en los números y tarjetas entregados. "
        "No des asesoría financiera profesional certificada ni prometas rendimientos. "
        "Devuelve ÚNICAMENTE un JSON válido con dos claves: "
        '{"gesto": "hablando|curioso|molesto", "respuesta": "texto breve para la burbuja empezando con ¡Miau!"}'
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODELO_GEMINI,
            contents=prompt_usuario,
            config=types.GenerateContentConfig(
                system_instruction=instruccion_sistema,
                temperature=0.4,
                response_mime_type="application/json",
            ),
        )
        raw_text = (response.text or "").strip()
        data = json.loads(raw_text)
        respuesta_txt = str(data.get("respuesta", "")).strip() or raw_text
        gesto_txt = normalizar_texto(data.get("gesto", "hablando"))
        if gesto_txt not in ("caminando", "hablando", "curioso", "molesto"):
            gesto_txt = resolver_gesto_capu(
                pregunta,
                contexto["disponible_mes"],
                contexto["total_gastos_mes"],
                contexto["total_ingresos_mes"],
                contexto["alerta_tarjeta"],
            )
        return respuesta_txt, gesto_txt
    except Exception:
        texto_fb = _respuesta_local_respaldo(pregunta, contexto)
        gesto_fb = resolver_gesto_capu(
            pregunta,
            contexto["disponible_mes"],
            contexto["total_gastos_mes"],
            contexto["total_ingresos_mes"],
            contexto["alerta_tarjeta"],
        )
        return texto_fb, gesto_fb


def mostrar_capu_burbuja(mensaje: str, gesto: str = "caminando"):
    img_uri, es_gif = buscar_medio_capu(gesto)

    if es_gif:
        anim_css = "none"
    else:
        anim_css = {
            "caminando": "caminarPaso 2.8s ease-in-out infinite alternate",
            "hablando": "hablarSalto 0.85s ease-in-out infinite",
            "curioso": "curiosoInclinar 1.6s ease-in-out infinite",
            "molesto": "molestoSacudida 0.45s ease-in-out infinite",
        }.get(gesto, "caminarPaso 2.8s ease-in-out infinite alternate")

    color_gesto = {
        "caminando": "#d97706",
        "hablando": "#059669",
        "curioso": "#2563eb",
        "molesto": "#dc2626",
    }.get(gesto, "#d97706")

    html_capu = f"""
    <style>
      .capu-escenario {{
        display: flex;
        align-items: center;
        gap: 18px;
        padding: 16px 20px;
        background: linear-gradient(135deg, #fffbeb 0%, #f8fafc 100%);
        border: 1.5px solid #cbd5e1;
        border-radius: 16px;
        overflow: hidden;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }}
      .capu-carril {{
        width: 145px;
        flex-shrink: 0;
        display: flex;
        align-items: center;
      }}
      .capu-movil {{
        animation: {anim_css};
      }}
      .capu-foto {{
        width: 86px;
        height: 86px;
        border-radius: 50%;
        object-fit: cover;
        border: 3px solid {color_gesto};
        background: #fef3c7;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 44px;
        box-shadow: 0 6px 14px rgba(15, 23, 42, 0.12);
      }}
      .capu-burbuja {{
        position: relative;
        flex: 1;
        background: #ffffff;
        border: 2px solid #0f172a;
        border-radius: 16px;
        padding: 13px 18px;
        color: #0f172a;
        font-size: 15px;
        line-height: 1.45;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
      }}
      .capu-burbuja::before {{
        content: "";
        position: absolute;
        left: -12px;
        top: 22px;
        border-width: 8px 12px 8px 0;
        border-style: solid;
        border-color: transparent #0f172a transparent transparent;
      }}
      .capu-badge {{
        display: inline-block;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: {color_gesto};
        margin-bottom: 4px;
      }}
      @keyframes caminarPaso {{
        0%   {{ transform: translateX(0px) translateY(0px); }}
        25%  {{ transform: translateX(14px) translateY(-5px); }}
        50%  {{ transform: translateX(28px) translateY(0px); }}
        75%  {{ transform: translateX(42px) translateY(-5px); }}
        100% {{ transform: translateX(52px) translateY(0px); }}
      }}
      @keyframes hablarSalto {{
        0%, 100% {{ transform: translateY(0px) scale(1); }}
        50%      {{ transform: translateY(-7px) scale(1.04); }}
      }}
      @keyframes curiosoInclinar {{
        0%, 100% {{ transform: rotate(0deg) scale(1); }}
        50%      {{ transform: rotate(9deg) scale(1.03); }}
      }}
      @keyframes molestoSacudida {{
        0%, 100% {{ transform: translateX(0px) rotate(0deg); }}
        25%      {{ transform: translateX(-5px) rotate(-3deg); }}
        75%      {{ transform: translateX(5px) rotate(3deg); }}
      }}
    </style>

    <div class="capu-escenario">
      <div class="capu-carril">
        <div class="capu-movil">
          {f'<img class="capu-foto" src="{img_uri}" alt="Capu {gesto}"/>' if img_uri else '<div class="capu-foto">🐱</div>'}
        </div>
      </div>
      <div class="capu-burbuja">
        <div class="capu-badge">Capu • {gesto}</div>
        <div id="capu-texto-animado"></div>
      </div>
    </div>

    <script>
      const texto = {json.dumps(mensaje)};
      const destino = document.getElementById("capu-texto-animado");
      let idx = 0;
      function tipear() {{
        if (idx <= texto.length) {{
          destino.textContent = texto.slice(0, idx);
          idx++;
          setTimeout(tipear, 18);
        }}
      }}
      tipear();
    </script>
    """
    components.html(html_capu, height=148)


# ---------------------------------------------------------
# INICIALIZACIÓN DE ESTADO DE SESIÓN
# ---------------------------------------------------------
if "datos_cargados" not in st.session_state:
    datos_ini = cargar_datos()
    st.session_state["usuario"] = datos_ini["usuario"]
    st.session_state["ingreso_base"] = datos_ini["ingreso_base"]
    st.session_state["porcentaje_gasto"] = datos_ini["porcentaje_gasto"]
    st.session_state["extras_al_ahorro"] = datos_ini["extras_al_ahorro"]
    st.session_state["tarjetas"] = datos_ini["tarjetas"]
    st.session_state["gastos"] = datos_ini["gastos"]
    st.session_state["ingresos"] = datos_ini["ingresos"]
    st.session_state["datos_cargados"] = True

if "consulta_capu" not in st.session_state:
    st.session_state["consulta_capu"] = ""
if "respuesta_capu" not in st.session_state:
    st.session_state["respuesta_capu"] = ""
if "gesto_gemini" not in st.session_state:
    st.session_state["gesto_gemini"] = ""


# ---------------------------------------------------------
# BARRA LATERAL: PERÍODO, REGLAS Y RESPALDO JSON
# ---------------------------------------------------------
st.sidebar.title("⚙️ FinanzaPro — Control")

meses = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
mes_idx = st.sidebar.selectbox(
    "Mes del ciclo:",
    list(range(12)),
    index=datetime.now().month - 1,
    format_func=lambda i: meses[i],
)
mes_numero = mes_idx + 1
mes_nombre = meses[mes_idx]
anio_sel = st.sidebar.selectbox("Año:", list(range(2026, 2036)), index=0)

st.sidebar.markdown("---")
usuario_in = st.sidebar.text_input("Usuario:", value=st.session_state["usuario"])
ingreso_base = st.sidebar.number_input(
    "Ingreso mensual base ($):",
    min_value=0.0,
    value=float(st.session_state["ingreso_base"]),
    step=10.0,
)
porcentaje_gasto = st.sidebar.slider(
    "% Límite de gasto del ingreso base:",
    min_value=10,
    max_value=100,
    value=int(st.session_state["porcentaje_gasto"]),
    step=5,
)
extras_al_ahorro = st.sidebar.checkbox(
    "Enviar 100% de ingresos extras al ahorro",
    value=bool(st.session_state["extras_al_ahorro"]),
)

if (
    usuario_in != st.session_state["usuario"]
    or ingreso_base != st.session_state["ingreso_base"]
    or porcentaje_gasto != st.session_state["porcentaje_gasto"]
    or extras_al_ahorro != st.session_state["extras_al_ahorro"]
):
    st.session_state["usuario"] = usuario_in.strip() or "Usuario"
    st.session_state["ingreso_base"] = ingreso_base
    st.session_state["porcentaje_gasto"] = porcentaje_gasto
    st.session_state["extras_al_ahorro"] = extras_al_ahorro
    guardar_datos()

limite_gasto_mensual = ingreso_base * (porcentaje_gasto / 100.0)
limite_gasto_quincenal = limite_gasto_mensual / 2.0
ahorro_base_mensual = ingreso_base - limite_gasto_mensual

st.sidebar.markdown("---")
st.sidebar.caption(f"Tope gasto mensual: **${limite_gasto_mensual:,.2f}**")
st.sidebar.caption(f"Tope gasto quincenal: **${limite_gasto_quincenal:,.2f}**")
st.sidebar.caption(f"Ahorro base mensual: **${ahorro_base_mensual:,.2f}**")

# Respaldo / Restauración JSON
st.sidebar.markdown("---")
st.sidebar.subheader("💾 Respaldo de Datos")
json_backup = json.dumps(
    {
        "usuario": st.session_state["usuario"],
        "ingreso_base": st.session_state["ingreso_base"],
        "porcentaje_gasto": st.session_state["porcentaje_gasto"],
        "extras_al_ahorro": st.session_state["extras_al_ahorro"],
        "tarjetas": st.session_state["tarjetas"],
        "gastos": st.session_state["gastos"],
        "ingresos": st.session_state["ingresos"],
    },
    ensure_ascii=False,
    indent=4,
)
st.sidebar.download_button(
    "📥 Descargar Respaldo (.json)",
    data=json_backup,
    file_name=f"respaldo_finanzas_{mes_nombre.lower()}_{anio_sel}.json",
    mime="application/json",
    use_container_width=True,
)
archivo_subido = st.sidebar.file_uploader("📤 Restaurar desde .json", type=["json"])
if archivo_subido is not None:
    try:
        datos_rest = json.load(archivo_subido)
        st.session_state["usuario"] = datos_rest.get("usuario", st.session_state["usuario"])
        st.session_state["ingreso_base"] = float(datos_rest.get("ingreso_base", 300.0))
        st.session_state["porcentaje_gasto"] = float(datos_rest.get("porcentaje_gasto", 80.0))
        st.session_state["extras_al_ahorro"] = bool(datos_rest.get("extras_al_ahorro", True))
        if isinstance(datos_rest.get("tarjetas"), list):
            st.session_state["tarjetas"] = datos_rest["tarjetas"]
        st.session_state["gastos"] = datos_rest.get("gastos", [])
        st.session_state["ingresos"] = datos_rest.get("ingresos", [])
        guardar_datos()
        st.sidebar.success("¡Datos restaurados!")
        st.rerun()
    except Exception:
        st.sidebar.error("Archivo JSON inválido.")


# ---------------------------------------------------------
# CÁLCULOS Y PROYECCIÓN DE CUOTAS DEL PERÍODO SELECCIONADO
# ---------------------------------------------------------
gastos_proyectados = []
total_gastos_mes = 0.0
total_iva_mes = 0.0
total_solca_mes = 0.0

for g in st.session_state["gastos"]:
    fecha_ini_str = g.get("fecha_inicio")
    if fecha_ini_str:
        try:
            f_ini = datetime.strptime(fecha_ini_str, "%Y-%m-%d").date()
        except Exception:
            f_ini = date(int(g.get("Año", anio_sel)), mes_numero, 1)

        meses_diff = (int(anio_sel) - f_ini.year) * 12 + (mes_numero - f_ini.month)
        cuota_ini = int(g.get("Cuota Actual", 1))
        cuota_tot = int(g.get("Cuotas Totales", 1))
        es_rec = bool(g.get("Recurrente", False))

        if es_rec:
            aplica = date(int(anio_sel), mes_numero, 1) >= date(f_ini.year, f_ini.month, 1) and (
                cuota_ini + meses_diff <= cuota_tot
            )
            cuota_vis = min(cuota_ini + max(0, meses_diff), cuota_tot)
            etiqueta_cuota = f"Recurrente ({cuota_vis}/{cuota_tot})"
        else:
            cuota_vis = cuota_ini + meses_diff
            aplica = 1 <= cuota_vis <= cuota_tot
            etiqueta_cuota = f"Cuota {cuota_vis} de {cuota_tot}"
    else:
        aplica = g.get("Mes") == mes_nombre and int(g.get("Año", anio_sel)) == int(anio_sel)
        cuota_vis = int(g.get("Cuota Actual", 1))
        cuota_tot = int(g.get("Cuotas Totales", 1))
        etiqueta_cuota = (
            f"Recurrente ({cuota_vis}/{cuota_tot})"
            if g.get("Recurrente")
            else f"Cuota {cuota_vis} de {cuota_tot}"
        )

    if aplica:
        cuota_pagar = float(g.get("Cuota a Pagar", 0.0))
        iva_item = float(g.get("IVA (15%)", 0.0))
        solca_item = float(g.get("SOLCA (0.5%)", 0.0))

        if not g.get("Recurrente") and int(g.get("Cuotas Totales", 1)) > 1:
            iva_mes_item = round(iva_item / int(g.get("Cuotas Totales", 1)), 2)
            solca_mes_item = round(solca_item / int(g.get("Cuotas Totales", 1)), 2)
        else:
            iva_mes_item = iva_item
            solca_mes_item = solca_item

        gastos_proyectados.append(
            {
                "id": g.get("id"),
                "Concepto": g.get("Concepto", ""),
                "Medio de Pago": g.get("Medio de Pago", ""),
                "Cuota Progreso": etiqueta_cuota,
                "Cuota Actual": cuota_vis,
                "Cuotas Totales": int(g.get("Cuotas Totales", 1)),
                "Subtotal": float(g.get("Subtotal", 0.0)),
                "IVA (15%)": iva_mes_item,
                "SOLCA (0.5%)": solca_mes_item,
                "Monto a Pagar": round(cuota_pagar, 2),
                "Cuota a Pagar": round(cuota_pagar, 2),
            }
        )
        total_gastos_mes += cuota_pagar
        total_iva_mes += iva_mes_item
        total_solca_mes += solca_mes_item

# Ordenar cuotas de mayor a menor plazo (ej. 12 cuotas -> 6 cuotas -> 3 cuotas -> 1 cuota)
gastos_proyectados.sort(
    key=lambda item: (item["Cuotas Totales"], item["Monto a Pagar"]),
    reverse=True,
)

ingresos_mes = [
    i for i in st.session_state["ingresos"]
    if i.get("Mes") == mes_nombre and int(i.get("Año", anio_sel)) == int(anio_sel)
]
df_ingresos = pd.DataFrame(ingresos_mes)

ingresos_sueldo_reg = (
    float(df_ingresos[df_ingresos["Tipo"] == "Ingreso Base / Sueldo"]["Monto"].sum())
    if not df_ingresos.empty
    else 0.0
)
extras_mes = (
    float(df_ingresos[df_ingresos["Tipo"] == "Trabajo Extra / Freelance"]["Monto"].sum())
    if not df_ingresos.empty
    else 0.0
)
ingresos_registrados_mes = float(df_ingresos["Monto"].sum()) if not df_ingresos.empty else 0.0

total_ingresos_mes = (
    ingresos_registrados_mes
    if ingresos_sueldo_reg > 0
    else (ingreso_base + extras_mes)
)

disponible_mes = limite_gasto_mensual - total_gastos_mes
ahorro_proyectado_mes = ahorro_base_mensual + (extras_mes if extras_al_ahorro else 0.0)
balance_neto = total_ingresos_mes - total_gastos_mes

# Calcular consumo actual por cada tarjeta configurada
tarjetas_detalle = []
alerta_tarjeta = False
tarjetas_excedidas = []
for t in st.session_state["tarjetas"]:
    nombre_t = str(t.get("nombre", "")).strip()
    norm_t = normalizar_texto(nombre_t)
    consumo_t = sum(
        gp["Monto a Pagar"]
        for gp in gastos_proyectados
        if norm_t and norm_t in normalizar_texto(gp["Medio de Pago"])
    )
    max_pagar = float(t.get("maximo_pagar", 0.0))
    if max_pagar > 0 and consumo_t > max_pagar:
        alerta_tarjeta = True
        tarjetas_excedidas.append(f"{nombre_t} (${consumo_t:,.2f} / máx ${max_pagar:,.2f})")
    tarjetas_detalle.append(
        {
            "nombre": nombre_t,
            "dia_corte": int(t.get("dia_corte", 19)),
            "dia_pago": int(t.get("dia_pago", 10)),
            "maximo_pagar": round(max_pagar, 2),
            "consumo_actual": round(consumo_t, 2),
        }
    )

contexto_mes = {
    "usuario": st.session_state["usuario"],
    "mes_nombre": mes_nombre,
    "anio_sel": anio_sel,
    "ingreso_base": ingreso_base,
    "total_ingresos_mes": total_ingresos_mes,
    "total_gastos_mes": total_gastos_mes,
    "limite_gasto_mensual": limite_gasto_mensual,
    "limite_gasto_quincenal": limite_gasto_quincenal,
    "disponible_mes": disponible_mes,
    "balance_neto": balance_neto,
    "ahorro_proyectado_mes": ahorro_proyectado_mes,
    "extras_mes": extras_mes,
    "total_iva_mes": total_iva_mes,
    "total_solca_mes": total_solca_mes,
    "tarjetas_detalle": tarjetas_detalle,
    "alerta_tarjeta": alerta_tarjeta,
}


# ---------------------------------------------------------
# 1. ASISTENTE CAPU ANIMADO + CONSULTA CON GEMINI
# ---------------------------------------------------------
if st.session_state["respuesta_capu"]:
    mensaje_burbuja = st.session_state["respuesta_capu"]
elif alerta_tarjeta:
    mensaje_burbuja = (
        f"¡Miau, {st.session_state['usuario']}! Alerta en {mes_nombre}: superaste el máximo a pagar en "
        f"{', '.join(tarjetas_excedidas)}."
    )
elif disponible_mes < 0:
    mensaje_burbuja = (
        f"¡Miau, {st.session_state['usuario']}! Ojo en {mes_nombre}: llevas ${total_gastos_mes:,.2f} "
        f"en gastos y superaste tu cupo mensual de ${limite_gasto_mensual:,.2f}."
    )
elif total_gastos_mes > 0 or extras_mes > 0:
    mensaje_burbuja = (
        f"¡Miau, {st.session_state['usuario']}! En {mes_nombre} llevas ${total_gastos_mes:,.2f} gastados, "
        f"te quedan ${disponible_mes:,.2f} del cupo y tu ahorro proyectado es ${ahorro_proyectado_mes:,.2f}."
    )
else:
    mensaje_burbuja = (
        f"¡Miau, {st.session_state['usuario']}! Aquí Capu vigilando {mes_nombre} {anio_sel}. "
        f"Tu cupo mensual es ${limite_gasto_mensual:,.2f} (${limite_gasto_quincenal:,.2f} por quincena)."
    )

gesto_activo = resolver_gesto_capu(
    st.session_state["consulta_capu"],
    disponible_mes,
    total_gastos_mes,
    total_ingresos_mes,
    alerta_tarjeta,
    st.session_state["gesto_gemini"],
)
mostrar_capu_burbuja(mensaje_burbuja, gesto_activo)

with st.form("form_pregunta_capu", clear_on_submit=False):
    col_p1, col_p2, col_p3 = st.columns([4, 1, 1])
    with col_p1:
        pregunta_in = st.text_input(
            "Pregúntale a Capu:",
            value=st.session_state["consulta_capu"],
            placeholder="Ej. ¿Cómo van mis tarjetas frente a su máximo a pagar? ¿Cuánto ahorro este mes?",
            label_visibility="collapsed",
        )
    with col_p2:
        btn_preguntar = st.form_submit_button("💬 Preguntar", type="primary", use_container_width=True)
    with col_p3:
        btn_limpiar_q = st.form_submit_button("🔄 Limpiar", use_container_width=True)

if btn_preguntar:
    st.session_state["consulta_capu"] = pregunta_in.strip()
    if st.session_state["consulta_capu"]:
        resp_txt, gesto_gem = responder_consulta_capu(
            st.session_state["consulta_capu"], contexto_mes
        )
        st.session_state["respuesta_capu"] = resp_txt
        st.session_state["gesto_gemini"] = gesto_gem
    else:
        st.session_state["respuesta_capu"] = ""
        st.session_state["gesto_gemini"] = ""
    st.rerun()

if btn_limpiar_q:
    st.session_state["consulta_capu"] = ""
    st.session_state["respuesta_capu"] = ""
    st.session_state["gesto_gemini"] = ""
    st.rerun()


# ---------------------------------------------------------
# 2. DASHBOARD PROFESIONAL (INDEX.HTML CON TARJETAS Y KPIs)
# ---------------------------------------------------------
if os.path.exists("index.html"):
    with open("index.html", "r", encoding="utf-8") as f:
        plantilla = Template(f.read())

    html_dashboard = plantilla.render(
        usuario=st.session_state["usuario"],
        mes_nombre=mes_nombre,
        anio=anio_sel,
        total_ingresos=total_ingresos_mes,
        total_gastos=total_gastos_mes,
        balance_neto=balance_neto,
        num_tarjetas=len(tarjetas_detalle),
        gastos=gastos_proyectados,
        tarjetas=tarjetas_detalle,
    )
    alto_dinamico = max(720, 560 + max(len(gastos_proyectados), len(tarjetas_detalle) * 2) * 52)
    components.html(html_dashboard, height=alto_dinamico, scrolling=True)
else:
    st.error("No se encontró `index.html` en la raíz del proyecto.")

# Barra rápida de metas adicionales (Cupo quincenal, Ahorro, IVA y SOLCA)
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric("Disponible Cupo Gasto", f"${disponible_mes:,.2f}", f"Quincenal: ${limite_gasto_quincenal:,.2f}")
with k2:
    st.metric("Meta de Ahorro", f"${ahorro_proyectado_mes:,.2f}", f"Extras: ${extras_mes:,.2f}")
with k3:
    st.metric("IVA (15%) del Mes", f"${total_iva_mes:,.2f}")
with k4:
    st.metric("SOLCA (0.5%) del Mes", f"${total_solca_mes:,.2f}")

st.markdown("---")


# ---------------------------------------------------------
# 3. GESTIÓN DE TARJETAS, GASTOS E INGRESOS
# ---------------------------------------------------------
tab_gasto, tab_ingreso, tab_tarjetas = st.tabs(
    ["🛍️ Registrar Gasto", "💵 Registrar Ingreso / Extra", "💳 Configurar Tarjetas (Corte y Máx. a Pagar)"]
)

with tab_gasto:
    concepto = st.text_input(
        "Concepto / Establecimiento:",
        placeholder="Ej. GanaVacaciones, Supermaxi, Gasolina, Netflix",
        key="g_concepto",
    )

    sug_cuota_tot = 1
    sug_cuota_act = 1
    sug_monto = 0.0
    sug_medio = None
    encontrado = False
    norm_c = normalizar_texto(concepto)

    if norm_c and st.session_state["gastos"]:
        for prev in reversed(st.session_state["gastos"]):
            if normalizar_texto(prev.get("Concepto", "")) == norm_c:
                encontrado = True
                sug_cuota_tot = int(prev.get("Cuotas Totales", 1))
                prev_act = int(prev.get("Cuota Actual", 1))
                sug_cuota_act = min(prev_act + 1, sug_cuota_tot) if prev.get("Recurrente") else prev_act
                sug_monto = float(prev.get("Monto Base", 0.0))
                sug_medio = prev.get("Medio de Pago")
                break

    if encontrado:
        st.info(f"Registro previo de **{concepto}** detectado: cuota sugerida **{sug_cuota_act}/{sug_cuota_tot}**.")

    medios_opciones = [
        f"💳 {t['nombre']} (Corte día {t['dia_corte']})"
        for t in st.session_state["tarjetas"]
    ] + [
        "🔄 Pago Recurrente Mensual",
        "💵 Efectivo / Transferencia",
    ]

    c1, c2, c3 = st.columns(3)
    with c1:
        monto_base = st.number_input(
            "Monto ($):",
            min_value=0.0,
            value=sug_monto if encontrado else 0.0,
            step=0.01,
            key="g_monto",
        )
        idx_m = medios_opciones.index(sug_medio) if sug_medio in medios_opciones else 0
        medio_pago = st.selectbox("Medio de pago:", medios_opciones, index=idx_m, key="g_medio")

        tarjeta_recurrente = ""
        if medio_pago == "🔄 Pago Recurrente Mensual":
            nombres_t = [t["nombre"] for t in st.session_state["tarjetas"]] + ["Débito / Cuenta"]
            tarjeta_recurrente = st.selectbox(
                "Tarjeta / origen del pago recurrente:",
                nombres_t,
                key="g_tarj_rec",
            )

    with c2:
        es_efectivo = medio_pago == "💵 Efectivo / Transferencia"
        es_recurrente = medio_pago == "🔄 Pago Recurrente Mensual"

        if es_efectivo:
            cuotas_totales = 1
            cuota_actual = 1
            st.caption("Pago directo (1 cuota).")
        else:
            cuotas_totales = st.number_input(
                "Número total de cuotas:",
                min_value=1,
                max_value=120,
                value=sug_cuota_tot if encontrado else (40 if es_recurrente else 1),
                key="g_ctot",
            )
            cuota_actual = st.number_input(
                "Cuota actual:",
                min_value=1,
                max_value=int(cuotas_totales),
                value=min(sug_cuota_act, int(cuotas_totales)) if encontrado else 1,
                key="g_cact",
            )
        proyectar_meses = st.checkbox(
            "Proyectar cuotas automáticamente en meses siguientes",
            value=True,
            key="g_proy",
        )

    with c3:
        modo_iva = st.radio(
            "IVA (15%):",
            ["Sin IVA / Exento", "Ya incluye IVA", "Sumar IVA (15%)"],
            key="g_iva",
        )
        aplica_solca = False
        if not es_efectivo:
            aplica_solca = st.checkbox("Aplicar 0.5% SOLCA", key="g_solca")
        interes_pct = st.number_input("Interés adicional (%):", min_value=0.0, value=0.0, step=0.5, key="g_int")

    if st.button("💾 Guardar Gasto", type="primary", key="btn_gasto"):
        if not concepto.strip() or monto_base <= 0:
            st.error("Ingresa un concepto y un monto mayor a $0.00.")
        else:
            if modo_iva == "Sumar IVA (15%)":
                subtotal = monto_base
                iva = subtotal * 0.15
                total_con_iva = subtotal + iva
            elif modo_iva == "Ya incluye IVA":
                subtotal = monto_base / 1.15
                iva = monto_base - subtotal
                total_con_iva = monto_base
            else:
                subtotal = monto_base
                iva = 0.0
                total_con_iva = monto_base

            solca = (subtotal * 0.005) if aplica_solca else 0.0
            total_operacion = (total_con_iva + solca) * (1.0 + (interes_pct / 100.0))

            if es_efectivo or es_recurrente:
                cuota_a_pagar = total_operacion
            else:
                cuota_a_pagar = total_operacion / max(1, int(cuotas_totales))

            medio_final = (
                f"{medio_pago} [{tarjeta_recurrente}]"
                if (es_recurrente and tarjeta_recurrente)
                else medio_pago
            )

            nuevo_gasto = {
                "id": int(datetime.now().timestamp() * 1000),
                "Mes": mes_nombre,
                "Año": int(anio_sel),
                "fecha_inicio": date(int(anio_sel), mes_numero, 1).strftime("%Y-%m-%d") if proyectar_meses else "",
                "Concepto": concepto.strip(),
                "Medio de Pago": medio_final,
                "Recurrente": bool(es_recurrente),
                "Cuota Actual": int(cuota_actual),
                "Cuotas Totales": int(cuotas_totales),
                "Monto Base": round(float(monto_base), 2),
                "Subtotal": round(float(subtotal), 2),
                "IVA (15%)": round(float(iva), 2),
                "SOLCA (0.5%)": round(float(solca), 2),
                "Cuota a Pagar": round(float(cuota_a_pagar), 2),
            }
            st.session_state["gastos"].append(nuevo_gasto)
            st.session_state["respuesta_capu"] = ""
            st.session_state["gesto_gemini"] = ""
            guardar_datos()
            st.rerun()

with tab_ingreso:
    ci1, ci2, ci3 = st.columns(3)
    with ci1:
        fuente = st.text_input("Origen / Fuente:", placeholder="Ej. Sueldo, Video y fotografía, Empresa", key="i_fuente")
    with ci2:
        monto_ing = st.number_input("Monto ($):", min_value=0.0, value=0.0, step=10.0, key="i_monto")
    with ci3:
        tipo_ing = st.selectbox("Tipo:", ["Trabajo Extra / Freelance", "Ingreso Base / Sueldo"], key="i_tipo")

    fecha_ing = st.date_input("Fecha:", value=date.today(), key="i_fecha")

    if st.button("💾 Guardar Ingreso", type="primary", key="btn_ingreso"):
        if not fuente.strip() or monto_ing <= 0:
            st.error("Ingresa una fuente y un monto mayor a $0.00.")
        else:
            nuevo_ing = {
                "id": int(datetime.now().timestamp() * 1000),
                "Mes": mes_nombre,
                "Año": int(anio_sel),
                "Fuente": fuente.strip(),
                "Tipo": tipo_ing,
                "Monto": round(float(monto_ing), 2),
                "Fecha": fecha_ing.strftime("%Y-%m-%d"),
            }
            st.session_state["ingresos"].append(nuevo_ing)
            st.session_state["respuesta_capu"] = ""
            st.session_state["gesto_gemini"] = ""
            guardar_datos()
            st.rerun()

with tab_tarjetas:
    st.subheader("💳 Tarjetas de Crédito (Nombre, Corte, Pago y Máximo a Pagar)")
    num_t = st.number_input(
        "Cantidad de tarjetas configuradas:",
        min_value=1,
        max_value=10,
        value=max(1, len(st.session_state["tarjetas"])),
        key="num_tarjetas_cfg",
    )

    nuevas_tarjetas = []
    for idx in range(int(num_t)):
        actual = (
            st.session_state["tarjetas"][idx]
            if idx < len(st.session_state["tarjetas"])
            else {"nombre": f"Tarjeta {idx + 1}", "dia_corte": 19, "dia_pago": 10, "maximo_pagar": 300.0}
        )
        st.markdown(f"**Tarjeta #{idx + 1}**")
        ct1, ct2, ct3, ct4 = st.columns([2, 1, 1, 1.5])
        with ct1:
            t_nom = st.text_input("Nombre de la tarjeta:", value=actual.get("nombre", f"Tarjeta {idx + 1}"), key=f"t_nom_{idx}")
        with ct2:
            t_cor = st.number_input("Día de corte:", min_value=1, max_value=31, value=int(actual.get("dia_corte", 19)), key=f"t_cor_{idx}")
        with ct3:
            t_pag = st.number_input("Día límite pago:", min_value=1, max_value=31, value=int(actual.get("dia_pago", 10)), key=f"t_pag_{idx}")
        with ct4:
            t_max = st.number_input(
                "Máximo a pagar ($):",
                min_value=0.0,
                value=float(actual.get("maximo_pagar", 300.0)),
                step=10.0,
                key=f"t_max_{idx}",
            )
        nuevas_tarjetas.append(
            {
                "nombre": t_nom.strip() or f"Tarjeta {idx + 1}",
                "dia_corte": int(t_cor),
                "dia_pago": int(t_pag),
                "maximo_pagar": round(float(t_max), 2),
            }
        )

    if st.button("💾 Guardar Tarjetas", type="primary", key="btn_save_tarjetas"):
        st.session_state["tarjetas"] = nuevas_tarjetas
        guardar_datos()
        st.success("¡Tarjetas actualizadas en FinanzaPro!")
        st.rerun()

st.markdown("---")


# ---------------------------------------------------------
# 4. EDITAR O ELIMINAR REGISTROS + EXPORTAR EXCEL Y PDF
# ---------------------------------------------------------
st.subheader("✏️ Editar / Eliminar Registros y 📥 Exportar")
e1, e2 = st.columns(2)

with e1:
    st.markdown("**Gastos registrados**")
    if st.session_state["gastos"]:
        mapa_g = {
            f"#{idx + 1} | {g['Concepto']} | ${g['Cuota a Pagar']:.2f} ({g['Cuota Actual']}/{g['Cuotas Totales']})": g["id"]
            for idx, g in enumerate(st.session_state["gastos"])
        }
        sel_g_label = st.selectbox("Selecciona un gasto:", list(mapa_g.keys()), key="sel_edit_g")
        id_g = mapa_g[sel_g_label]
        pos_real = next((i for i, item in enumerate(st.session_state["gastos"]) if item["id"] == id_g), None)

        if pos_real is not None:
            reg_g = st.session_state["gastos"][pos_real]
            n_conc = st.text_input("Concepto:", value=reg_g["Concepto"], key="ed_g_conc")
            n_pagar = st.number_input("Cuota a pagar ($):", min_value=0.0, value=float(reg_g["Cuota a Pagar"]), step=0.01, key="ed_g_pagar")
            c_a, c_b = st.columns(2)
            with c_b:
                n_ctot = st.number_input("Cuotas totales:", min_value=1, max_value=120, value=int(reg_g["Cuotas Totales"]), key="ed_g_ct")
            with c_a:
                n_cact = st.number_input(
                    "Cuota actual:",
                    min_value=1,
                    max_value=int(n_ctot),
                    value=min(int(reg_g["Cuota Actual"]), int(n_ctot)),
                    key="ed_g_ca",
                )

            b_upd, b_del = st.columns(2)
            with b_upd:
                if st.button("Guardar cambio", key="btn_upd_g"):
                    st.session_state["gastos"][pos_real]["Concepto"] = n_conc.strip() or reg_g["Concepto"]
                    st.session_state["gastos"][pos_real]["Cuota a Pagar"] = round(float(n_pagar), 2)
                    st.session_state["gastos"][pos_real]["Cuota Actual"] = int(n_cact)
                    st.session_state["gastos"][pos_real]["Cuotas Totales"] = int(n_ctot)
                    guardar_datos()
                    st.rerun()
            with b_del:
                if st.button("Eliminar gasto", key="btn_del_g"):
                    st.session_state["gastos"].pop(pos_real)
                    guardar_datos()
                    st.rerun()
    else:
        st.caption("Sin gastos registrados todavía.")

with e2:
    st.markdown("**Ingresos registrados**")
    if st.session_state["ingresos"]:
        mapa_i = {
            f"#{idx + 1} | {i['Fuente']} | ${i['Monto']:.2f} ({i['Fecha']})": i["id"]
            for idx, i in enumerate(st.session_state["ingresos"])
        }
        sel_i_label = st.selectbox("Selecciona un ingreso:", list(mapa_i.keys()), key="sel_edit_i")
        id_i = mapa_i[sel_i_label]
        pos_i = next((k for k, item in enumerate(st.session_state["ingresos"]) if item["id"] == id_i), None)

        if pos_i is not None:
            reg_i = st.session_state["ingresos"][pos_i]
            n_fuen = st.text_input("Fuente:", value=reg_i["Fuente"], key="ed_i_fuen")
            n_mont = st.number_input("Monto ($):", min_value=0.0, value=float(reg_i["Monto"]), step=0.01, key="ed_i_mont")

            bi_upd, bi_del = st.columns(2)
            with bi_upd:
                if st.button("Guardar ingreso", key="btn_upd_i"):
                    st.session_state["ingresos"][pos_i]["Fuente"] = n_fuen.strip() or reg_i["Fuente"]
                    st.session_state["ingresos"][pos_i]["Monto"] = round(float(n_mont), 2)
                    guardar_datos()
                    st.rerun()
            with bi_del:
                if st.button("Eliminar ingreso", key="btn_del_i"):
                    st.session_state["ingresos"].pop(pos_i)
                    guardar_datos()
                    st.rerun()
    else:
        st.caption("Sin ingresos registrados todavía.")

st.markdown("---")
ex1, ex2 = st.columns(2)

cols_export_gastos = [
    "Concepto", "Medio de Pago", "Cuota Progreso",
    "Subtotal", "IVA (15%)", "SOLCA (0.5%)", "Monto a Pagar",
]

with ex1:
    buf_xlsx = io.BytesIO()
    hojas_usadas = set()
    with pd.ExcelWriter(buf_xlsx, engine="openpyxl") as writer:
        df_res = pd.DataFrame(
            [
                {
                    "Usuario": st.session_state["usuario"],
                    "Mes": mes_nombre,
                    "Año": int(anio_sel),
                    "Total_Ingresos": round(total_ingresos_mes, 2),
                    "Gastos_Mes": round(total_gastos_mes, 2),
                    "Balance_Neto": round(balance_neto, 2),
                    "Limite_Gasto": round(limite_gasto_mensual, 2),
                    "Disponible_Cupo": round(disponible_mes, 2),
                    "Ahorro_Proyectado": round(ahorro_proyectado_mes, 2),
                    "IVA_15": round(total_iva_mes, 2),
                    "SOLCA_05": round(total_solca_mes, 2),
                }
            ]
        )
        df_res.to_excel(writer, sheet_name=nombre_hoja_excel("Resumen", hojas_usadas), index=False)

        if tarjetas_detalle:
            pd.DataFrame(tarjetas_detalle).to_excel(
                writer, sheet_name=nombre_hoja_excel("Tarjetas", hojas_usadas), index=False
            )

        if gastos_proyectados:
            df_g_all = pd.DataFrame(gastos_proyectados)[cols_export_gastos]
            df_g_all.to_excel(
                writer, sheet_name=nombre_hoja_excel("Gastos_Mes", hojas_usadas), index=False
            )

            # Separación por cada tarjeta configurada + Efectivo/Otros
            indices_asignados = set()
            for t in tarjetas_detalle:
                norm_t = normalizar_texto(t["nombre"])
                filas_t = [
                    gp for idx_gp, gp in enumerate(gastos_proyectados)
                    if norm_t and norm_t in normalizar_texto(gp["Medio de Pago"])
                ]
                for idx_gp, gp in enumerate(gastos_proyectados):
                    if norm_t and norm_t in normalizar_texto(gp["Medio de Pago"]):
                        indices_asignados.add(idx_gp)
                if filas_t:
                    pd.DataFrame(filas_t)[cols_export_gastos].to_excel(
                        writer,
                        sheet_name=nombre_hoja_excel(t["nombre"], hojas_usadas),
                        index=False,
                    )

            filas_otros = [
                gp for idx_gp, gp in enumerate(gastos_proyectados)
                if idx_gp not in indices_asignados
            ]
            if filas_otros:
                pd.DataFrame(filas_otros)[cols_export_gastos].to_excel(
                    writer,
                    sheet_name=nombre_hoja_excel("Efectivo_y_Otros", hojas_usadas),
                    index=False,
                )

        if not df_ingresos.empty:
            df_ingresos.to_excel(
                writer, sheet_name=nombre_hoja_excel("Ingresos_Mes", hojas_usadas), index=False
            )

    st.download_button(
        label="📊 Descargar Reporte Excel (.xlsx)",
        data=buf_xlsx.getvalue(),
        file_name=f"FinanzaPro_{mes_nombre.lower()}_{anio_sel}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

with ex2:
    buf_pdf = io.BytesIO()
    pdf = canvas.Canvas(buf_pdf, pagesize=letter)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(50, 750, f"FinanzaPro - Reporte {mes_nombre} {anio_sel} ({st.session_state['usuario']})")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, 732, f"Ingresos: ${total_ingresos_mes:,.2f} | Gastos: ${total_gastos_mes:,.2f} | Balance Neto: ${balance_neto:,.2f}")
    pdf.drawString(50, 716, f"Cupo mensual: ${limite_gasto_mensual:,.2f} | Disponible: ${disponible_mes:,.2f} | Ahorro: ${ahorro_proyectado_mes:,.2f}")

    y = 696
    if tarjetas_detalle:
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(50, y, "Resumen por Tarjeta:")
        y -= 13
        pdf.setFont("Helvetica", 9)
        for td in tarjetas_detalle:
            pdf.drawString(
                60,
                y,
                f"- {td['nombre']}: ${td['consumo_actual']:,.2f} / Max ${td['maximo_pagar']:,.2f} "
                f"(Corte dia {td['dia_corte']}, Pago dia {td['dia_pago']})",
            )
            y -= 13
        y -= 6

    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(50, y, "Concepto")
    pdf.drawString(230, y, "Medio de Pago")
    pdf.drawString(395, y, "Cuota")
    pdf.drawString(475, y, "A Pagar")
    y -= 14
    pdf.setFont("Helvetica", 9)

    for gp in gastos_proyectados:
        if y < 60:
            pdf.showPage()
            y = 750
        pdf.drawString(50, y, str(gp.get("Concepto", ""))[:26])
        pdf.drawString(230, y, str(gp.get("Medio de Pago", ""))[:24])
        pdf.drawString(395, y, str(gp.get("Cuota Progreso", ""))[:14])
        pdf.drawString(475, y, f"${float(gp.get('Monto a Pagar', 0.0)):.2f}")
        y -= 16

    pdf.save()
    st.download_button(
        label="📄 Descargar Reporte PDF (.pdf)",
        data=buf_pdf.getvalue(),
        file_name=f"FinanzaPro_{mes_nombre.lower()}_{anio_sel}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
