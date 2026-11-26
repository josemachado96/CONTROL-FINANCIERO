import base64
import io
import json
import os
import unicodedata
from datetime import date, datetime

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
    page_title="Control Financiero — Capu 🐱",
    page_icon="🐱",
    layout="wide",
)

ARCHIVO_DATOS = "finanzas_datos.json"
MODELO_GEMINI = "gemini-3.5-flash-lite"


def normalizar_texto(texto: str) -> str:
    if not texto:
        return ""
    limpio = unicodedata.normalize("NFD", str(texto).lower().strip())
    limpio = "".join(c for c in limpio if unicodedata.category(c) != "Mn")
    return " ".join(limpio.split())


def cargar_datos():
    base = {
        "ingreso_base": 300.0,
        "porcentaje_gasto": 80.0,
        "extras_al_ahorro": True,
        "gastos": [],
        "ingresos": [],
    }
    if os.path.exists(ARCHIVO_DATOS):
        try:
            with open(ARCHIVO_DATOS, "r", encoding="utf-8") as f:
                data = json.load(f)
                base["ingreso_base"] = float(data.get("ingreso_base", 300.0))
                base["porcentaje_gasto"] = float(data.get("porcentaje_gasto", 80.0))
                base["extras_al_ahorro"] = bool(data.get("extras_al_ahorro", True))
                base["gastos"] = data.get("gastos", [])
                base["ingresos"] = data.get("ingresos", [])
        except Exception:
            pass
    return base


def guardar_datos():
    payload = {
        "ingreso_base": st.session_state["ingreso_base"],
        "porcentaje_gasto": st.session_state["porcentaje_gasto"],
        "extras_al_ahorro": st.session_state["extras_al_ahorro"],
        "gastos": st.session_state["gastos"],
        "ingresos": st.session_state["ingresos"],
    }
    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)


# ---------------------------------------------------------
# LÓGICA DE GESTOS, GIFS/IMÁGENES Y BURBUJA DE CAPU
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
    gesto_gemini: str = "",
) -> str:
    if disponible_mes < 0:
        return "molesto"

    g_gem = normalizar_texto(gesto_gemini)
    if g_gem in ("caminando", "hablando", "curioso", "molesto"):
        return g_gem

    p = normalizar_texto(pregunta)
    if p:
        palabras_molesto = ["pasado", "excedi", "deuda", "error", "mal", "caro", "problema", "alerta"]
        palabras_curioso = ["cuanto", "como", "que pasa", "iva", "solca", "cuota", "ahorrar", "alcanza", "puedo"]
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

    if "quincena" in p or "quincenal" in p:
        return (
            f"¡Miau, curioso! En {mes} tu tope quincenal de gasto es ${quincena:,.2f} "
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
    """
    Consulta a Gemini con los datos reales del mes y devuelve (respuesta_texto, gesto_sugerido).
    Si no hay API Key o el SDK no está disponible, usa el respaldo local sin interrumpir la app.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key and "GEMINI_API_KEY" in st.secrets:
        api_key = str(st.secrets["GEMINI_API_KEY"]).strip()

    if not genai or not types or not api_key:
        texto_fb = _respuesta_local_respaldo(pregunta, contexto)
        gesto_fb = resolver_gesto_capu(
            pregunta,
            contexto["disponible_mes"],
            contexto["total_gastos_mes"],
            contexto["ingresos_registrados_mes"],
        )
        return texto_fb, gesto_fb

    prompt_usuario = (
        f"Datos financieros del período ({contexto['mes_nombre']} {contexto['anio_sel']}):\n"
        f"- Ingreso base: ${contexto['ingreso_base']:,.2f}\n"
        f"- Ingresos registrados en el mes: ${contexto['ingresos_registrados_mes']:,.2f}\n"
        f"- Trabajos extras del mes: ${contexto['extras_mes']:,.2f}\n"
        f"- Límite de gasto mensual: ${contexto['limite_gasto_mensual']:,.2f}\n"
        f"- Límite de gasto quincenal: ${contexto['limite_gasto_quincenal']:,.2f}\n"
        f"- Gastos acumulados del mes: ${contexto['total_gastos_mes']:,.2f}\n"
        f"- Disponible del cupo mensual: ${contexto['disponible_mes']:,.2f}\n"
        f"- Meta de ahorro proyectada: ${contexto['ahorro_proyectado_mes']:,.2f}\n"
        f"- IVA (15%) acumulado: ${contexto['total_iva_mes']:,.2f}\n"
        f"- SOLCA (0.5%) acumulado: ${contexto['total_solca_mes']:,.2f}\n\n"
        f"Pregunta del usuario: {pregunta}"
    )

    instruccion_sistema = (
        "Eres Capu, un gato siamés asistente de control financiero personal. "
        "Responde en español, de forma clara, amable y práctica, basándote en los números entregados. "
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
        respuesta_txt = str(data.get("respuesta", "")).strip()
        gesto_txt = normalizar_texto(data.get("gesto", "hablando"))
        if not respuesta_txt:
            respuesta_txt = raw_text
        if gesto_txt not in ("caminando", "hablando", "curioso", "molesto"):
            gesto_txt = resolver_gesto_capu(
                pregunta,
                contexto["disponible_mes"],
                contexto["total_gastos_mes"],
                contexto["ingresos_registrados_mes"],
            )
        return respuesta_txt, gesto_txt
    except Exception:
        texto_fb = _respuesta_local_respaldo(pregunta, contexto)
        gesto_fb = resolver_gesto_capu(
            pregunta,
            contexto["disponible_mes"],
            contexto["total_gastos_mes"],
            contexto["ingresos_registrados_mes"],
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
        padding: 18px 22px;
        background: linear-gradient(135deg, #fffbeb 0%, #f8fafc 100%);
        border: 1.5px solid #e2e8f0;
        border-radius: 18px;
        overflow: hidden;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }}
      .capu-carril {{
        width: 150px;
        flex-shrink: 0;
        display: flex;
        align-items: center;
      }}
      .capu-movil {{
        animation: {anim_css};
      }}
      .capu-foto {{
        width: 92px;
        height: 92px;
        border-radius: 50%;
        object-fit: cover;
        border: 3px solid {color_gesto};
        background: #fef3c7;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 46px;
        box-shadow: 0 6px 14px rgba(15, 23, 42, 0.12);
      }}
      .capu-burbuja {{
        position: relative;
        flex: 1;
        background: #ffffff;
        border: 2px solid #0f172a;
        border-radius: 16px;
        padding: 14px 18px;
        color: #0f172a;
        font-size: 15px;
        line-height: 1.45;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
      }}
      .capu-burbuja::before {{
        content: "";
        position: absolute;
        left: -12px;
        top: 24px;
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
        100% {{ transform: translateX(55px) translateY(0px); }}
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
          setTimeout(tipear, 20);
        }}
      }}
      tipear();
    </script>
    """
    components.html(html_capu, height=155)


if "datos_cargados" not in st.session_state:
    datos_ini = cargar_datos()
    st.session_state["ingreso_base"] = datos_ini["ingreso_base"]
    st.session_state["porcentaje_gasto"] = datos_ini["porcentaje_gasto"]
    st.session_state["extras_al_ahorro"] = datos_ini["extras_al_ahorro"]
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
# BARRA LATERAL: CONFIGURACIÓN Y PERÍODO
# ---------------------------------------------------------
st.sidebar.title("⚙️ Configuración y Período")

meses = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
mes_idx = st.sidebar.selectbox(
    "Mes:",
    list(range(12)),
    index=datetime.now().month - 1,
    format_func=lambda i: meses[i],
)
mes_nombre = meses[mes_idx]
anio_sel = st.sidebar.selectbox("Año:", list(range(2026, 2036)), index=0)

st.sidebar.markdown("---")
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
    ingreso_base != st.session_state["ingreso_base"]
    or porcentaje_gasto != st.session_state["porcentaje_gasto"]
    or extras_al_ahorro != st.session_state["extras_al_ahorro"]
):
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

# ---------------------------------------------------------
# CÁLCULOS DEL MES
# ---------------------------------------------------------
gastos_mes = [
    g for g in st.session_state["gastos"]
    if g.get("Mes") == mes_nombre and int(g.get("Año", anio_sel)) == int(anio_sel)
]
ingresos_mes = [
    i for i in st.session_state["ingresos"]
    if i.get("Mes") == mes_nombre and int(i.get("Año", anio_sel)) == int(anio_sel)
]

df_gastos = pd.DataFrame(gastos_mes)
df_ingresos = pd.DataFrame(ingresos_mes)

total_gastos_mes = float(df_gastos["Cuota a Pagar"].sum()) if not df_gastos.empty else 0.0
total_iva_mes = float(df_gastos["IVA (15%)"].sum()) if not df_gastos.empty else 0.0
total_solca_mes = float(df_gastos["SOLCA (0.5%)"].sum()) if not df_gastos.empty else 0.0

ingresos_registrados_mes = float(df_ingresos["Monto"].sum()) if not df_ingresos.empty else 0.0
extras_mes = (
    float(df_ingresos[df_ingresos["Tipo"] == "Trabajo Extra / Freelance"]["Monto"].sum())
    if not df_ingresos.empty
    else 0.0
)

base_efectivo_mes = ingresos_registrados_mes if ingresos_registrados_mes > 0 else ingreso_base
disponible_mes = limite_gasto_mensual - total_gastos_mes
ahorro_proyectado_mes = ahorro_base_mensual + (extras_mes if extras_al_ahorro else 0.0)
balance_flujo = base_efectivo_mes - total_gastos_mes

contexto_mes = {
    "mes_nombre": mes_nombre,
    "anio_sel": anio_sel,
    "ingreso_base": ingreso_base,
    "ingresos_registrados_mes": ingresos_registrados_mes,
    "total_gastos_mes": total_gastos_mes,
    "limite_gasto_mensual": limite_gasto_mensual,
    "limite_gasto_quincenal": limite_gasto_quincenal,
    "disponible_mes": disponible_mes,
    "ahorro_proyectado_mes": ahorro_proyectado_mes,
    "extras_mes": extras_mes,
    "total_iva_mes": total_iva_mes,
    "total_solca_mes": total_solca_mes,
}

# ---------------------------------------------------------
# ENCABEZADO + CAPU CON BURBUJA Y CONSULTA A GEMINI
# ---------------------------------------------------------
st.title("💰 Control Financiero Personal")
st.caption(f"Período activo: **{mes_nombre} {anio_sel}**")

if st.session_state["respuesta_capu"]:
    mensaje_burbuja = st.session_state["respuesta_capu"]
elif disponible_mes < 0:
    mensaje_burbuja = (
        f"¡Miau! Llevas ${total_gastos_mes:,.2f} de gastos en {mes_nombre} y te pasaste "
        f"por ${abs(disponible_mes):,.2f} de tu cupo mensual (${limite_gasto_mensual:,.2f})."
    )
elif total_gastos_mes > 0 or ingresos_registrados_mes > 0:
    mensaje_burbuja = (
        f"¡Miau! En {mes_nombre} llevas ${total_gastos_mes:,.2f} gastados, te quedan "
        f"${disponible_mes:,.2f} disponibles y tu ahorro proyectado es ${ahorro_proyectado_mes:,.2f}."
    )
else:
    mensaje_burbuja = (
        f"¡Miau! Aquí Capu revisando {mes_nombre} {anio_sel}. Tu tope mensual es "
        f"${limite_gasto_mensual:,.2f} (${limite_gasto_quincenal:,.2f} por quincena)."
    )

gesto_activo = resolver_gesto_capu(
    st.session_state["consulta_capu"],
    disponible_mes,
    total_gastos_mes,
    ingresos_registrados_mes,
    st.session_state["gesto_gemini"],
)
mostrar_capu_burbuja(mensaje_burbuja, gesto_activo)

with st.form("form_pregunta_capu", clear_on_submit=False):
    col_p1, col_p2, col_p3 = st.columns([4, 1, 1])
    with col_p1:
        pregunta_in = st.text_input(
            "Pregúntale a Capu sobre tus cuentas:",
            value=st.session_state["consulta_capu"],
            placeholder="Ej. ¿Cómo reparte un extra de $80? ¿Cuánto me queda disponible?",
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
# MÉTRICAS CLAVE
# ---------------------------------------------------------
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Gastos del Mes", f"${total_gastos_mes:,.2f}", f"Límite: ${limite_gasto_mensual:,.2f}")
with m2:
    st.metric("Disponible del Cupo", f"${disponible_mes:,.2f}", f"Quincenal: ${limite_gasto_quincenal:,.2f}")
with m3:
    st.metric("Meta de Ahorro", f"${ahorro_proyectado_mes:,.2f}", f"Extras: ${extras_mes:,.2f}")
with m4:
    st.metric("IVA (15%) Acumulado", f"${total_iva_mes:,.2f}", f"SOLCA: ${total_solca_mes:,.2f}")

if disponible_mes < 0:
    st.warning(
        f"Te pasaste del límite mensual de gasto en **${abs(disponible_mes):,.2f}** "
        f"(flujo neto del mes: ${balance_flujo:,.2f})."
    )

st.markdown("---")

# ---------------------------------------------------------
# FORMULARIOS: REGISTRAR GASTO / REGISTRAR INGRESO
# ---------------------------------------------------------
tab_gasto, tab_ingreso = st.tabs(["🛍️ Registrar Gasto", "💵 Registrar Ingreso / Extra"])

with tab_gasto:
    concepto = st.text_input(
        "Concepto / Establecimiento:",
        placeholder="Ej. GanaVacaciones, Uber, Gasolina, Supermaxi",
        key="g_concepto",
    )

    sug_cuota_tot = 1
    sug_cuota_act = 1
    sug_monto = 0.0
    sug_medio = "💳 Diners Club (Corte 19 al 18)"
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
                sug_medio = prev.get("Medio de Pago", sug_medio)
                break

    if encontrado:
        st.info(f"Registro previo de **{concepto}** detectado: cuota sugerida **{sug_cuota_act}/{sug_cuota_tot}**.")

    c1, c2, c3 = st.columns(3)
    with c1:
        monto_base = st.number_input(
            "Monto ($):",
            min_value=0.0,
            value=sug_monto if encontrado else 0.0,
            step=0.01,
            key="g_monto",
        )
        medios = [
            "💳 Diners Club (Corte 19 al 18)",
            "💳 Pacificard (Corte 24 al 23)",
            "🔄 Pago Recurrente Mensual",
            "💵 Efectivo / Transferencia",
        ]
        idx_m = medios.index(sug_medio) if sug_medio in medios else 0
        medio_pago = st.selectbox("Medio de pago:", medios, index=idx_m, key="g_medio")

        tarjeta_recurrente = ""
        if medio_pago == "🔄 Pago Recurrente Mensual":
            tarjeta_recurrente = st.selectbox(
                "Tarjeta / origen del pago recurrente:",
                ["Pacificard", "Diners Club", "Débito / Cuenta"],
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

            medio_final = f"{medio_pago} [{tarjeta_recurrente}]" if (es_recurrente and tarjeta_recurrente) else medio_pago

            nuevo_gasto = {
                "id": int(datetime.now().timestamp() * 1000),
                "Mes": mes_nombre,
                "Año": int(anio_sel),
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
        tipo_ing = st.selectbox("Tipo:", ["Ingreso Base / Sueldo", "Trabajo Extra / Freelance"], key="i_tipo")

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

st.markdown("---")

# ---------------------------------------------------------
# TABLAS DEL MES
# ---------------------------------------------------------
st.subheader(f"📋 Detalle de {mes_nombre} {anio_sel}")
t_g, t_i = st.tabs(["Gastos y Cuotas", "Ingresos y Extras"])

cols_g = [
    "Concepto",
    "Medio de Pago",
    "Cuota Actual",
    "Cuotas Totales",
    "Subtotal",
    "IVA (15%)",
    "SOLCA (0.5%)",
    "Cuota a Pagar",
]

with t_g:
    if not df_gastos.empty:
        df_g_ord = df_gastos.sort_values(by="Cuotas Totales", ascending=False)
        for c in cols_g:
            if c not in df_g_ord.columns:
                df_g_ord[c] = ""
        st.dataframe(df_g_ord[cols_g], use_container_width=True, hide_index=True)
    else:
        st.info("No hay gastos registrados en este mes.")

with t_i:
    if not df_ingresos.empty:
        st.dataframe(df_ingresos[["Fecha", "Tipo", "Fuente", "Monto"]], use_container_width=True, hide_index=True)
    else:
        st.info("No hay ingresos registrados en este mes.")

# ---------------------------------------------------------
# EDITAR O ELIMINAR REGISTROS
# ---------------------------------------------------------
st.markdown("---")
st.subheader("✏️ Editar o Eliminar Registros")

e1, e2 = st.columns(2)

with e1:
    st.markdown("**Gastos del mes**")
    if gastos_mes:
        mapa_g = {
            f"#{idx + 1} | {g['Concepto']} | ${g['Cuota a Pagar']:.2f} ({g['Cuota Actual']}/{g['Cuotas Totales']})": g["id"]
            for idx, g in enumerate(gastos_mes)
        }
        sel_g_label = st.selectbox("Selecciona un gasto:", list(mapa_g.keys()), key="sel_edit_g")
        id_g = mapa_g[sel_g_label]
        pos_real = next((i for i, item in enumerate(st.session_state["gastos"]) if item["id"] == id_g), None)

        if pos_real is not None:
            reg_g = st.session_state["gastos"][pos_real]
            n_conc = st.text_input("Concepto:", value=reg_g["Concepto"], key="ed_g_conc")
            n_pagar = st.number_input("Cuota a pagar ($):", min_value=0.0, value=float(reg_g["Cuota a Pagar"]), step=0.01, key="ed_g_pagar")
            c_a, c_b = st.columns(2)
            with c_a:
                n_cact = st.number_input("Cuota actual:", min_value=1, max_value=120, value=int(reg_g["Cuota Actual"]), key="ed_g_ca")
            with c_b:
                n_ctot = st.number_input("Cuotas totales:", min_value=1, max_value=120, value=int(reg_g["Cuotas Totales"]), key="ed_g_ct")

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
        st.caption("Sin gastos para editar en este mes.")

with e2:
    st.markdown("**Ingresos del mes**")
    if ingresos_mes:
        mapa_i = {
            f"#{idx + 1} | {i['Fuente']} | ${i['Monto']:.2f} ({i['Fecha']})": i["id"]
            for idx, i in enumerate(ingresos_mes)
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
        st.caption("Sin ingresos para editar en este mes.")

# ---------------------------------------------------------
# EXPORTAR A EXCEL Y PDF
# ---------------------------------------------------------
st.markdown("---")
st.subheader("📥 Exportar Reporte")

ex1, ex2 = st.columns(2)

with ex1:
    buf_xlsx = io.BytesIO()
    with pd.ExcelWriter(buf_xlsx, engine="openpyxl") as writer:
        df_res = pd.DataFrame(
            [
                {
                    "Mes": mes_nombre,
                    "Año": int(anio_sel),
                    "Gastos_Mes": round(total_gastos_mes, 2),
                    "Limite_Gasto": round(limite_gasto_mensual, 2),
                    "Disponible": round(disponible_mes, 2),
                    "Ahorro_Proyectado": round(ahorro_proyectado_mes, 2),
                    "IVA_15": round(total_iva_mes, 2),
                    "SOLCA_05": round(total_solca_mes, 2),
                }
            ]
        )
        df_res.to_excel(writer, sheet_name="Resumen", index=False)
        if not df_gastos.empty:
            df_gastos.to_excel(writer, sheet_name="Gastos", index=False)
        if not df_ingresos.empty:
            df_ingresos.to_excel(writer, sheet_name="Ingresos", index=False)

    st.download_button(
        label="📊 Descargar Excel (.xlsx)",
        data=buf_xlsx.getvalue(),
        file_name=f"finanzas_{mes_nombre.lower()}_{anio_sel}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with ex2:
    buf_pdf = io.BytesIO()
    pdf = canvas.Canvas(buf_pdf, pagesize=letter)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(50, 750, f"Reporte Financiero - {mes_nombre} {anio_sel}")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, 728, f"Gastos del mes: ${total_gastos_mes:,.2f} | Limite: ${limite_gasto_mensual:,.2f} | Disponible: ${disponible_mes:,.2f}")
    pdf.drawString(50, 712, f"Meta ahorro: ${ahorro_proyectado_mes:,.2f} | IVA (15%): ${total_iva_mes:,.2f} | SOLCA: ${total_solca_mes:,.2f}")

    y = 682
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(50, y, "Concepto")
    pdf.drawString(240, y, "Cuota")
    pdf.drawString(310, y, "IVA")
    pdf.drawString(380, y, "A Pagar")
    y -= 14
    pdf.setFont("Helvetica", 9)

    for g in gastos_mes:
        if y < 60:
            pdf.showPage()
            y = 750
        pdf.drawString(50, y, str(g.get("Concepto", ""))[:28])
        pdf.drawString(240, y, f"{g.get('Cuota Actual', 1)}/{g.get('Cuotas Totales', 1)}")
        pdf.drawString(310, y, f"${float(g.get('IVA (15%)', 0.0)):.2f}")
        pdf.drawString(380, y, f"${float(g.get('Cuota a Pagar', 0.0)):.2f}")
        y -= 16

    pdf.save()
    st.download_button(
        label="📄 Descargar PDF (.pdf)",
        data=buf_pdf.getvalue(),
        file_name=f"finanzas_{mes_nombre.lower()}_{anio_sel}.pdf",
        mime="application/pdf",
    )
