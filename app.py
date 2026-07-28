import streamlit as st
import pandas as pd
import json
import os
import io
from datetime import datetime

# Importación de ReportLab para exportar a PDF
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

st.set_page_config(
    page_title="Control Financiero Personal",
    page_icon="💰",
    layout="wide"
)

# ---------------------------------------------------------
# FUNCIONES DE ALMACENAMIENTO MULTI-PERFIL
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
            return json.load(f)
    return []

def guardar_datos_perfil(nombre_perfil, datos):
    archivo = obtener_nombre_archivo_perfil(nombre_perfil)
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)

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
if "datos_gastos" not in st.session_state or st.session_state.get("perfil_actual") != perfil_seleccionado:
    st.session_state["perfil_actual"] = perfil_seleccionado
    st.session_state["datos_gastos"] = cargar_datos_perfil(perfil_seleccionado)

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
# FORMULARIO PARA REGISTRAR NUEVO GASTO / COMPRA
# ---------------------------------------------------------
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

btn_guardar = st.button("💾 Guardar Registro", type="primary")

if btn_guardar:
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
        guardar_datos_perfil(perfil_seleccionado, st.session_state["datos_gastos"])
        st.success(f"✅ ¡Registro '{descripcion}' guardado para {perfil_seleccionado}!")
        st.rerun()

st.markdown("---")

# ---------------------------------------------------------
# DESGLOSE Y MÉTRICAS POR PERIODO / CICLO DE CORTE
# ---------------------------------------------------------
st.subheader(f"📌 Resumen Financiero: {mes_ciclo} {anio_ciclo}")

gastos_filtrados = [
    g for g in st.session_state["datos_gastos"]
    if g.get("Ciclo_Mes") == mes_ciclo and g.get("Año") == anio_ciclo
]

df_gastos = pd.DataFrame(gastos_filtrados)

if not df_gastos.empty:
    # --- PREVENCIÓN DE KEYERROR: ASEGURAR TODAS LAS COLUMNAS ---
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

    # Si falta la columna Cuota_Progreso en registros antiguos, construirla
    if "Cuota_Progreso" not in df_gastos.columns or df_gastos["Cuota_Progreso"].isnull().any():
        df_gastos["Cuota_Progreso"] = df_gastos.apply(
            lambda r: f"{int(r.get('Cuota_Actual', 1))}/{int(r.get('Cuota_Total', 1))}", axis=1
        )

    # Totales Periodo 19 al 18 (Diners + Efectivo asignado)
    df_p19_18 = df_gastos[df_gastos["Periodo_Asignado"] == "Periodo 19 al 18 (Diners)"]
    p19_diners = df_p19_18[df_p19_18["Medio_Pago"].str.contains("Diners", na=False)]["Monto_Cuota_Mensual"].sum() if not df_p19_18.empty else 0.0
    p19_efectivo = df_p19_18[~df_p19_18["Medio_Pago"].str.contains("Diners", na=False)]["Monto_Cuota_Mensual"].sum() if not df_p19_18.empty else 0.0
    total_p19_18 = p19_diners + p19_efectivo

    # Totales Periodo 24 al 23 (Pacificard + Efectivo asignado)
    df_p24_23 = df_gastos[df_gastos["Periodo_Asignado"] == "Periodo 24 al 23 (Pacificard)"]
    p24_pacificard = df_p24_23[df_p24_23["Medio_Pago"].str.contains("Pacificard", na=False)]["Monto_Cuota_Mensual"].sum() if not df_p24_23.empty else 0.0
    p24_efectivo = df_p24_23[~df_p24_23["Medio_Pago"].str.contains("Pacificard", na=False)]["Monto_Cuota_Mensual"].sum() if not df_p24_23.empty else 0.0
    total_p24_23 = p24_pacificard + p24_efectivo

    total_general = total_p19_18 + total_p24_23

    col_m1, col_m2, col_m3 = st.columns(3)

    with col_m1:
        st.metric("💳 Período 19 al 18 (Diners + Efectivo)", f"${total_p19_18:,.2f}")
        st.caption(f"🔹 Diners Club: **${p19_diners:,.2f}** | Efectivo/Transf: **${p19_efectivo:,.2f}**")

    with col_m2:
        st.metric("💳 Período 24 al 23 (Pacificard + Efectivo)", f"${total_p24_23:,.2f}")
        st.caption(f"🔹 Pacificard: **${p24_pacificard:,.2f}** | Efectivo/Transf: **${p24_efectivo:,.2f}**")

    with col_m3:
        st.metric("💰 TOTAL GENERAL DEL CICLO", f"${total_general:,.2f}")

    st.markdown("---")

    # Columnas visibles garantizadas
    cols_vis = ["Descripcion", "Medio_Pago", "Periodo_Asignado", "Cuota_Progreso", "Subtotal", "IVA_15", "SOLCA_05", "Monto_Cuota_Mensual"]

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Consolidado General", 
        "💳 Periodo 19 al 18 (Diners)", 
        "💳 Periodo 24 al 23 (Pacificard)",
        "🔄 Pagos Recurrentes / Efectivo"
    ])

    with tab1:
        st.dataframe(df_gastos[cols_vis], use_container_width=True)

    with tab2:
        st.dataframe(df_p19_18[cols_vis] if not df_p19_18.empty else df_p19_18, use_container_width=True)

    with tab3:
        st.dataframe(df_p24_23[cols_vis] if not df_p24_23.empty else df_p24_23, use_container_width=True)

    with tab4:
        df_rec = df_gastos[df_gastos["Medio_Pago"].str.contains("Recurrente|Efectivo", na=False)]
        st.dataframe(df_rec[cols_vis] if not df_rec.empty else df_rec, use_container_width=True)

    st.markdown("---")

    # ---------------------------------------------------------
    # ⚙️ MODIFICAR O ELIMINAR REGISTROS
    # ---------------------------------------------------------
    st.subheader(f"⚙️ Modificar o Eliminar Registros de {perfil_seleccionado}")

    opciones_edit = {
        f"{r.get('Descripcion', 'Gasto')} | {r.get('Medio_Pago', '')} | Cuota {r.get('Cuota_Progreso', '1/1')} | ${float(r.get('Monto_Cuota_Mensual', 0)):.2f}": idx
        for idx, r in enumerate(st.session_state["datos_gastos"])
        if r.get("Ciclo_Mes") == mes_ciclo and r.get("Año") == anio_ciclo
    }

    if opciones_edit:
        sel_label = st.selectbox("Selecciona la transacción a modificar o borrar:", list(opciones_edit.keys()))
        idx_real = opciones_edit[sel_label]
        item = st.session_state["datos_gastos"][idx_real]

        col_ed1, col_ed2 = st.columns(2)

        with col_ed1:
            with st.expander("✏️ Editar Registro"):
                edit_desc = st.text_input("Concepto / Local", value=item.get("Descripcion", ""), key="edit_desc")
                edit_monto = st.number_input("Cuota Mensual a Pagar ($)", min_value=0.01, value=float(item.get("Monto_Cuota_Mensual", 0.01)), step=0.5, key="edit_monto")
                edit_c_tot = st.number_input("Cuotas Totales", min_value=1, max_value=120, value=int(item.get("Cuota_Total", 1)), key="edit_c_tot")
                edit_c_act = st.number_input("Cuota Actual", min_value=1, max_value=120, value=int(item.get("Cuota_Actual", 1)), key="edit_c_act")
                
                if st.button("💾 Guardar Cambios"):
                    st.session_state["datos_gastos"][idx_real]["Descripcion"] = edit_desc
                    st.session_state["datos_gastos"][idx_real]["Monto_Cuota_Mensual"] = round(edit_monto, 2)
                    st.session_state["datos_gastos"][idx_real]["Cuota_Actual"] = int(edit_c_act)
                    st.session_state["datos_gastos"][idx_real]["Cuota_Total"] = int(edit_c_tot)
                    st.session_state["datos_gastos"][idx_real]["Cuota_Progreso"] = f"{edit_c_act}/{edit_c_tot}"
                    
                    guardar_datos_perfil(perfil_seleccionado, st.session_state["datos_gastos"])
                    st.success("¡Registro actualizado exitosamente!")
                    st.rerun()

        with col_ed2:
            with st.expander("🗑️ Eliminar Registro"):
                st.warning(f"¿Confirmas borrar '{item.get('Descripcion', '')}' (${item.get('Monto_Cuota_Mensual', 0)})?")
                if st.button("❌ Confirmar Eliminación", type="primary"):
                    st.session_state["datos_gastos"].pop(idx_real)
                    guardar_datos_perfil(perfil_seleccionado, st.session_state["datos_gastos"])
                    st.success("Registro eliminado correctamente.")
                    st.rerun()

    st.markdown("---")

    # ---------------------------------------------------------
    # 📥 EXPORTACIÓN A EXCEL Y PDF
    # ---------------------------------------------------------
    st.subheader("📥 Exportar Reporte de este Perfil")

    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        output_excel = io.BytesIO()
        with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
            df_gastos[cols_vis].to_excel(writer, sheet_name="Consolidado", index=False)
            if not df_p19_18.empty:
                df_p19_18[cols_vis].to_excel(writer, sheet_name="Periodo_19_18", index=False)
            if not df_p24_23.empty:
                df_p24_23[cols_vis].to_excel(writer, sheet_name="Periodo_24_23", index=False)

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
        p.drawString(100, 750, f"Reporte Financiero — {perfil_seleccionado} ({mes_ciclo} {anio_ciclo})")
        p.line(50, 740, 550, 740)

        y = 710
        p.setFont("Helvetica-Bold", 9)
        p.drawString(50, y, "Concepto")
        p.drawString(200, y, "Medio Pago")
        p.drawString(350, y, "Cuota")
        p.drawString(450, y, "Monto Mensual")
        y -= 15

        p.setFont("Helvetica", 8)
        for _, row in df_gastos.iterrows():
            p.drawString(50, y, str(row['Descripcion'])[:24])
            p.drawString(200, y, str(row['Medio_Pago'])[:22])
            p.drawString(350, y, str(row['Cuota_Progreso']))
            p.drawString(450, y, f"${row['Monto_Cuota_Mensual']:.2f}")
            y -= 18

            if y < 60:
                p.showPage()
                y = 750

        p.line(50, y + 5, 550, y + 5)
        p.setFont("Helvetica-Bold", 10)
        p.drawString(300, y - 10, "TOTAL GENERAL:")
        p.drawString(450, y - 10, f"${total_general:,.2f}")

        p.save()

        st.download_button(
            label="🔴 Descargar Reporte PDF (.pdf)",
            data=buffer_pdf.getvalue(),
            file_name=f"Reporte_{perfil_seleccionado}_{mes_ciclo.replace(' / ', '_')}_{anio_ciclo}.pdf",
            mime="application/pdf"
        )

else:
    st.info(f"No hay registros guardados aún para **{perfil_seleccionado}** en el ciclo seleccionado.")