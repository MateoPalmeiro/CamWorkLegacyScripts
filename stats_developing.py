#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import logging
from datetime import datetime
import matplotlib.pyplot as plt
from fpdf import FPDF

# ----------------------------------------------------------------------------
# CARPETAS DE SALIDAS
# ----------------------------------------------------------------------------
LOGS_DIR = "logs"
PDF_DIR = "pdf"
METADATA_DIR = "metadata"

os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

# ----------------------------------------------------------------------------
# CONFIGURACIÓN DE LOG
# ----------------------------------------------------------------------------
today_str = datetime.now().strftime("%d-%m-%Y")
LOG_FILENAME = os.path.join(LOGS_DIR, f"collection_stats_{today_str}.log")

logging.basicConfig(
    filename=LOG_FILENAME,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ----------------------------------------------------------------------------
# PARÁMETROS GLOBALES
# ----------------------------------------------------------------------------
CAMERAS_DIR = "CAMARAS"
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".arw", ".cr2", ".nef", ".raf", ".heic"}

# Aquí iremos almacenando info de cada foto
photos_data = []

# ----------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ----------------------------------------------------------------------------

def human_readable_size(size_in_bytes):
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024**2:
        kb = size_in_bytes / 1024
        return f"{kb:.2f} KB"
    elif size_in_bytes < 1024**3:
        mb = size_in_bytes / (1024**2)
        return f"{mb:.2f} MB"
    else:
        gb = size_in_bytes / (1024**3)
        return f"{gb:.2f} GB"

# ----------------------------------------------------------------------------
# SELECCIÓN DE ÁMBITO
# ----------------------------------------------------------------------------

def seleccionar_ambito():
    """
    Pide al usuario si quiere stats de todas las cámaras (1)
    o de una cámara en específico (2). Si es (2), pide mes, etc.
    Devuelve un dict con:
    {
      "all_cameras": bool,
      "camera_name": str|None,
      "all_months": bool,
      "month_name": str|None,
      "all_themes": bool,
      "theme_name": str|None
    }
    """
    scope = {
        "all_cameras": False,
        "camera_name": None,
        "all_months": False,
        "month_name": None,
        "all_themes": False,
        "theme_name": None
    }

    print("¿Quieres estadísticas de:\n 1) Todas las cámaras\n 2) Una cámara específica?")
    opt = input("Selecciona [1/2]: ").strip()
    if opt == "1":
        scope["all_cameras"] = True
        logging.info("Se hará estadística de TODAS las cámaras.")
        return scope
    elif opt == "2":
        if not os.path.isdir(CAMERAS_DIR):
            print(f"No existe '{CAMERAS_DIR}'. Saliendo.")
            return scope
        cameras_list = sorted([
            d for d in os.listdir(CAMERAS_DIR)
            if os.path.isdir(os.path.join(CAMERAS_DIR, d))
        ])
        if not cameras_list:
            print("No hay cámaras en CAMARAS/. Saliendo.")
            return scope

        print("Cámaras disponibles:")
        for i, c in enumerate(cameras_list, start=1):
            print(f"{i}. {c}")
        sel = input("Cámara (p.e. '1'): ").strip()
        if not sel.isdigit():
            print("Selección inválida.")
            return scope
        idx = int(sel)
        if idx < 1 or idx > len(cameras_list):
            print("Fuera de rango.")
            return scope

        scope["camera_name"] = cameras_list[idx - 1]
        logging.info(f"Estadísticas de cámara: {scope['camera_name']}")

        # Preguntar meses
        cam_path = os.path.join(CAMERAS_DIR, scope["camera_name"])
        months_list = sorted([
            d for d in os.listdir(cam_path)
            if os.path.isdir(os.path.join(cam_path, d))
            and re.match(r"^\d{4}\.\d{2}$", d)
        ])
        if not months_list:
            print("No hay carpetas mensuales en esta cámara.")
            scope["all_months"] = True
            return scope

        print("¿Quieres stats de:\n 1) Todas las carpetas mensuales\n 2) Una sola?")
        opt2 = input("[1/2]: ").strip()
        if opt2 == "1":
            scope["all_months"] = True
            return scope
        elif opt2 == "2":
            print("Carpetas mensuales:")
            for i, m in enumerate(months_list, start=1):
                print(f"{i}. {m}")
            sel2 = input("Elige [1..]: ").strip()
            if not sel2.isdigit():
                print("Inválido.")
                return scope
            idx2 = int(sel2)
            if idx2 < 1 or idx2 > len(months_list):
                print("Fuera de rango.")
                return scope
            scope["month_name"] = months_list[idx2 - 1]

            # Temáticas
            month_path = os.path.join(cam_path, scope["month_name"])
            themes_list = sorted([
                d for d in os.listdir(month_path)
                if os.path.isdir(os.path.join(month_path, d))
            ])
            if not themes_list:
                print("No hay carpetas temáticas.")
                scope["all_themes"] = True
                return scope

            print("¿Quieres stats de:\n 1) Todas las temáticas\n 2) Una sola?")
            opt3 = input("[1/2]: ").strip()
            if opt3 == "1":
                scope["all_themes"] = True
                return scope
            elif opt3 == "2":
                print("Temáticas:")
                for i, t in enumerate(themes_list, start=1):
                    print(f"{i}. {t}")
                sel3 = input("Elige [1..]: ").strip()
                if not sel3.isdigit():
                    print("Inválido.")
                    return scope
                idx3 = int(sel3)
                if idx3 < 1 or idx3 > len(themes_list):
                    print("Fuera de rango.")
                    return scope
                scope["theme_name"] = themes_list[idx3 - 1]
                return scope
            else:
                print("Inválido.")
                return scope
        else:
            print("Inválido.")
            return scope
    else:
        print("Selección inválida.")
        return scope

# ----------------------------------------------------------------------------
# RECOLECCIÓN DE DATOS
# ----------------------------------------------------------------------------

def recolectar_datos(scope):
    if scope["all_cameras"]:
        cameras_list = sorted([
            d for d in os.listdir(CAMERAS_DIR)
            if os.path.isdir(os.path.join(CAMERAS_DIR, d))
        ])
    else:
        if not scope["camera_name"]:
            logging.info("Ninguna cámara seleccionada.")
            return
        cameras_list = [scope["camera_name"]]

    for camera_name in cameras_list:
        camera_path = os.path.join(CAMERAS_DIR, camera_name)
        if not os.path.isdir(camera_path):
            continue

        # Meses
        if scope["all_cameras"] or (scope["camera_name"] and scope["all_months"]):
            months_list = sorted([
                d for d in os.listdir(camera_path)
                if os.path.isdir(os.path.join(camera_path, d))
                and re.match(r"^\d{4}\.\d{2}$", d)
            ])
        else:
            if not scope["month_name"]:
                logging.info(f"No se seleccionó mes en {camera_name}.")
                continue
            months_list = [scope["month_name"]]

        for month_folder in months_list:
            month_path = os.path.join(camera_path, month_folder)
            if not os.path.isdir(month_path):
                continue

            m = re.match(r"^(\d{4})\.(\d{2})$", month_folder)
            if m:
                yyyy = int(m.group(1))
                mm = int(m.group(2))
            else:
                yyyy, mm = (0, 0)

            if scope["all_cameras"] or scope["all_months"] or (scope["camera_name"] and scope["month_name"] and scope["all_themes"]):
                themes_list = sorted([
                    d for d in os.listdir(month_path)
                    if os.path.isdir(os.path.join(month_path, d))
                ])
            else:
                if not scope["theme_name"]:
                    logging.info(f"No se seleccionó temática en {month_path}.")
                    continue
                themes_list = [scope["theme_name"]]

            for theme_folder in themes_list:
                theme_path = os.path.join(month_path, theme_folder)
                if not os.path.isdir(theme_path):
                    continue

                collect_photos_in_theme(camera_name, yyyy, mm, theme_folder, theme_path)

def collect_photos_in_theme(camera_name, year, month, theme_folder, theme_path):
    # Procesar fotos en la carpeta temática (directamente)
    base_files = sorted(os.listdir(theme_path))
    # Se ignoran las carpetas (se procesarán aparte las subtemáticas y la RAW)
    for item in base_files:
        item_path = os.path.join(theme_path, item)
        if os.path.isdir(item_path):
            continue
        _, ext = os.path.splitext(item)
        ext = ext.lower()
        if ext in PHOTO_EXTENSIONS:
            size_bytes = os.path.getsize(item_path)
            photos_data.append({
                "camera": camera_name,
                "year": year,
                "month": month,
                "theme": theme_folder,
                "extension": ext,
                "file_size": size_bytes
            })

    # Procesar la carpeta RAW (si existe) en la carpeta temática
    if "RAW" in base_files and os.path.isdir(os.path.join(theme_path, "RAW")):
        raw_path = os.path.join(theme_path, "RAW")
        raw_files = sorted(os.listdir(raw_path))
        for rf in raw_files:
            rf_path = os.path.join(raw_path, rf)
            if os.path.isdir(rf_path):
                continue
            _, ext = os.path.splitext(rf)
            ext = ext.lower()
            if ext in PHOTO_EXTENSIONS:
                size_bytes = os.path.getsize(rf_path)
                photos_data.append({
                    "camera": camera_name,
                    "year": year,
                    "month": month,
                    "theme": theme_folder,
                    "extension": ext,
                    "file_size": size_bytes
                })

    # --- NUEVO: Procesar subcarpetas subetemáticas (excluyendo "RAW") ---
    subtheme_folders = sorted([
        d for d in os.listdir(theme_path)
        if os.path.isdir(os.path.join(theme_path, d)) and d.lower() != "raw"
    ])
    for subtheme in subtheme_folders:
        subtheme_path = os.path.join(theme_path, subtheme)
        subtheme_files = sorted(os.listdir(subtheme_path))
        # Procesar fotos en la subcarpeta subetemática
        for item in subtheme_files:
            item_path = os.path.join(subtheme_path, item)
            if os.path.isdir(item_path):
                continue
            _, ext = os.path.splitext(item)
            ext = ext.lower()
            if ext in PHOTO_EXTENSIONS:
                size_bytes = os.path.getsize(item_path)
                photos_data.append({
                    "camera": camera_name,
                    "year": year,
                    "month": month,
                    "theme": f"{theme_folder}/{subtheme}",
                    "extension": ext,
                    "file_size": size_bytes
                })
        # Procesar la carpeta RAW dentro de la subetemática (si existe)
        if "RAW" in subtheme_files and os.path.isdir(os.path.join(subtheme_path, "RAW")):
            raw_path = os.path.join(subtheme_path, "RAW")
            raw_files = sorted(os.listdir(raw_path))
            for rf in raw_files:
                rf_path = os.path.join(raw_path, rf)
                if os.path.isdir(rf_path):
                    continue
                _, ext = os.path.splitext(rf)
                ext = ext.lower()
                if ext in PHOTO_EXTENSIONS:
                    size_bytes = os.path.getsize(rf_path)
                    photos_data.append({
                        "camera": camera_name,
                        "year": year,
                        "month": month,
                        "theme": f"{theme_folder}/{subtheme}",
                        "extension": ext,
                        "file_size": size_bytes
                    })

# ----------------------------------------------------------------------------
# GENERAR ESTADÍSTICAS
# ----------------------------------------------------------------------------

def generar_estadisticas():
    stats = {
        "total_photos": 0,
        "total_size": 0,
        "distribution_by_extension": {},
        "distribution_by_camera": {},
        "distribution_by_year": {},
    }

    for photo in photos_data:
        stats["total_photos"] += 1
        size_b = photo["file_size"]
        stats["total_size"] += size_b

        ext = photo["extension"]
        stats["distribution_by_extension"].setdefault(ext, 0)
        stats["distribution_by_extension"][ext] += 1

        cam = photo["camera"]
        stats["distribution_by_camera"].setdefault(cam, 0)
        stats["distribution_by_camera"][cam] += 1

        yyyy = photo["year"]
        stats["distribution_by_year"].setdefault(yyyy, 0)
        stats["distribution_by_year"][yyyy] += 1

    return stats

# ----------------------------------------------------------------------------
# GENERAR GRÁFICOS
# ----------------------------------------------------------------------------

def generar_grafico_extension(stats):
    dist = stats["distribution_by_extension"]
    if not dist:
        return None

    labels = list(dist.keys())
    sizes = list(dist.values())

    plt.figure(figsize=(5,5))
    plt.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=140)
    plt.title("Distribución por extensión")
    png_path = os.path.join(METADATA_DIR, "ext_distribution.png")
    plt.savefig(png_path)
    plt.close()
    return png_path

def generar_grafico_camaras(stats):
    dist = stats["distribution_by_camera"]
    if not dist:
        return None

    labels = list(dist.keys())
    values = list(dist.values())

    plt.figure(figsize=(6,4))
    plt.bar(labels, values, color='skyblue')
    plt.title("Fotos por cámara")
    plt.xlabel("Cámara")
    plt.ylabel("Cantidad de fotos")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    png_path = os.path.join(METADATA_DIR, "camera_distribution.png")
    plt.savefig(png_path)
    plt.close()
    return png_path

def generar_grafico_year(stats):
    dist = stats["distribution_by_year"]
    if not dist:
        return None

    years = sorted(dist.keys())
    values = [dist[y] for y in years]

    plt.figure(figsize=(5,4))
    plt.bar([str(y) for y in years], values, color='green')
    plt.title("Fotos por año")
    plt.xlabel("Año")
    plt.ylabel("Cantidad de fotos")

    png_path = os.path.join(METADATA_DIR, "year_distribution.png")
    plt.savefig(png_path)
    plt.close()
    return png_path

# ----------------------------------------------------------------------------
# GENERAR PDF
# ----------------------------------------------------------------------------

def generar_pdf(stats, pdf_filename, scope):
    pdf = FPDF(format='A4', orientation='P', unit='mm')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Estadísticas de Colección Fotográfica", ln=True, align='C')

    fecha_hoy = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Fecha de ejecución: {fecha_hoy}", ln=True)
    pdf.ln(5)

    # Mostrar el 'scope'
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Ámbito de análisis:", ln=True)
    pdf.set_font("Arial", "", 12)
    if scope["all_cameras"]:
        pdf.multi_cell(0, 6, " - TODAS las cámaras", align='L')
    else:
        pdf.multi_cell(0, 6, f" - Cámara específica: {scope['camera_name']}", align='L')
        if scope["all_months"]:
            pdf.multi_cell(0, 6, " - TODAS las carpetas mensuales", align='L')
        else:
            pdf.multi_cell(0, 6, f" - Mes específico: {scope['month_name']}", align='L')
            if scope["all_themes"]:
                pdf.multi_cell(0, 6, " - TODAS las temáticas", align='L')
            else:
                pdf.multi_cell(0, 6, f" - Temática específica: {scope['theme_name']}", align='L')
    pdf.ln(10)

    # Estadísticas
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "Estadísticas Generales:", ln=True)
    pdf.set_font("Arial", "", 12)

    total_photos = stats["total_photos"]
    total_size_b = stats["total_size"]
    size_str = human_readable_size(total_size_b)
    pdf.multi_cell(0, 6, f"- Total de fotos: {total_photos}", align='L')
    pdf.multi_cell(0, 6, f"- Tamaño total: {size_str}", align='L')
    pdf.ln(5)

    # Insertar gráficos
    ext_png = generar_grafico_extension(stats)
    cam_png = generar_grafico_camaras(stats)
    year_png = generar_grafico_year(stats)

    def insertar_imagen_en_pdf(img_path, titulo):
        if img_path and os.path.exists(img_path):
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, titulo, ln=True)
            pdf.set_font("Arial", "", 12)
            pdf.ln(2)
            pdf.image(img_path, w=120)
            pdf.ln(10)

    insertar_imagen_en_pdf(ext_png, "Distribución por Extensión")
    insertar_imagen_en_pdf(cam_png, "Distribución por Cámara")
    insertar_imagen_en_pdf(year_png, "Distribución por Año")

    pdf.output(pdf_filename)
    logging.info(f"PDF generado: {pdf_filename}")

# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

def main():
    try:
        scope = seleccionar_ambito()
        if not scope["all_cameras"] and not scope["camera_name"]:
            print("No se pudo determinar la cámara. Saliendo.")
            return

        logging.info("Iniciando recolección de datos.")
        recolectar_datos(scope)
        logging.info(f"Se han encontrado {len(photos_data)} fotos en total.")

        stats = generar_estadisticas()

        # Pequeño resumen en el log
        logging.info("=== RESUMEN DE DATOS RECOLECTADOS ===")
        logging.info(f"Total de fotos: {stats['total_photos']}")
        logging.info(f"Tamaño total: {human_readable_size(stats['total_size'])}")

        pdf_name = os.path.join(PDF_DIR, f"collection_stats_{today_str}.pdf")
        generar_pdf(stats, pdf_name, scope)

        logging.info("Proceso de estadísticas finalizado correctamente.")
    except Exception as e:
        logging.error(f"Error inesperado: {e}")


if __name__ == "__main__":
    main()
