#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import logging
from datetime import datetime

from fpdf import FPDF  # Para PDF final

# ----------------------------------------------------------------------------
# CARPETAS PARA SALIDAS
# ----------------------------------------------------------------------------
LOGS_DIR = "logs"
PDF_DIR = "pdf"
METADATA_DIR = "metadata"

os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

# ----------------------------------------------------------------------------
# CONFIGURACIÓN DEL LOG
# ----------------------------------------------------------------------------
today_str = datetime.now().strftime("%d-%m-%Y")
LOG_FILENAME = os.path.join(LOGS_DIR, f"organizar_raw_{today_str}.log")

logging.basicConfig(
    filename=LOG_FILENAME,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ----------------------------------------------------------------------------
# PARÁMETROS GLOBALES
# ----------------------------------------------------------------------------
CAMERAS_DIR = "CAMARAS"
RAW_EXTENSIONS = {".cr2", ".arw"}

folders_report = {}

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


def seleccionar_camaras():
    if not os.path.isdir(CAMERAS_DIR):
        print(f"La carpeta '{CAMERAS_DIR}' no existe o no es un directorio.")
        return []

    # Se ordena la lista de cámaras alfabéticamente
    todas_camaras = sorted([
        d for d in os.listdir(CAMERAS_DIR)
        if os.path.isdir(os.path.join(CAMERAS_DIR, d))
    ])

    if not todas_camaras:
        print("No se encontraron carpetas de cámaras en la carpeta CAMARAS.")
        return []

    print("Cámaras disponibles:")
    for i, cam in enumerate(todas_camaras, start=1):
        print(f"{i}. {cam}")

    seleccion = input("Indica las cámaras que quieres procesar (p.e. '1,2,5'): ")
    indices = []
    for x in seleccion.split(','):
        x = x.strip()
        if x.isdigit():
            indices.append(int(x))

    camaras_seleccionadas = [
        todas_camaras[i - 1]
        for i in indices
        if 1 <= i <= len(todas_camaras)
    ]
    return camaras_seleccionadas


def procesar_directorio(directorio):
    # Buscamos archivos RAW en el directorio
    raw_files = [
        f for f in os.listdir(directorio)
        if os.path.isfile(os.path.join(directorio, f))
           and os.path.splitext(f)[1].lower() in RAW_EXTENSIONS
    ]
    if not raw_files:
        logging.info(f"No se encontraron archivos RAW en {directorio}.")
        return

    raw_folder_path = os.path.join(directorio, "RAW")
    created_now = False
    if not os.path.exists(raw_folder_path):
        try:
            os.mkdir(raw_folder_path)
            logging.info(f"Creada subcarpeta 'RAW' en {directorio}")
            created_now = True
        except OSError as e:
            logging.error(f"Error al crear {raw_folder_path}: {e}")
            return

    for rf in raw_files:
        orig = os.path.join(directorio, rf)
        dest = os.path.join(raw_folder_path, rf)
        size_bytes = os.path.getsize(orig)
        try:
            shutil.move(orig, dest)
            logging.info(f"Movido archivo RAW '{rf}' a {raw_folder_path}")

            if raw_folder_path not in folders_report:
                folders_report[raw_folder_path] = {
                    'created': created_now,
                    'files_count': 0,
                    'ext_count': {},
                    'bytes_moved': 0
                }
            else:
                if created_now:
                    folders_report[raw_folder_path]['created'] = True

            folders_report[raw_folder_path]['files_count'] += 1
            folders_report[raw_folder_path]['bytes_moved'] += size_bytes

            ext = os.path.splitext(rf)[1].lower()
            if ext not in folders_report[raw_folder_path]['ext_count']:
                folders_report[raw_folder_path]['ext_count'][ext] = 0
            folders_report[raw_folder_path]['ext_count'][ext] += 1

        except PermissionError as e:
            logging.error(f"Permiso denegado al mover '{rf}': {e}")
        except OSError as e:
            logging.error(f"Error al mover '{rf}' a '{raw_folder_path}': {e}")


def organizar_raw_en_subcarpeta(camaras):
    for camera_name in camaras:
        camera_path = os.path.join(CAMERAS_DIR, camera_name)
        if not os.path.isdir(camera_path):
            continue

        logging.info(f"Procesando cámara: {camera_path}")

        for monthly_folder in os.listdir(camera_path):
            monthly_path = os.path.join(camera_path, monthly_folder)
            if not os.path.isdir(monthly_path):
                continue

            theme_folders = [
                f for f in os.listdir(monthly_path)
                if os.path.isdir(os.path.join(monthly_path, f))
            ]
            if not theme_folders:
                logging.info(f"No se encontraron carpetas temáticas en {monthly_path}. Se omite.")
                continue

            for theme in theme_folders:
                theme_path = os.path.join(monthly_path, theme)
                if not os.path.isdir(theme_path):
                    continue

                # Primero, procesar RAW en la carpeta temática
                procesar_directorio(theme_path)

                # Luego, si existen subtemáticas (ignorando 'RAW'),
                # procesar también cada subcarpeta:
                subtheme_folders = [
                    d for d in os.listdir(theme_path)
                    if os.path.isdir(os.path.join(theme_path, d)) and d.lower() != "raw"
                ]
                for subtheme in subtheme_folders:
                    subtheme_path = os.path.join(theme_path, subtheme)
                    procesar_directorio(subtheme_path)


def generar_resumen_txt():
    logging.info("=== RESUMEN FINAL DE LA EJECUCIÓN ===")

    if not folders_report:
        logging.info("No se movió ningún archivo RAW. No hay cambios.")
        return

    total_bytes = 0
    carpetas_creadas = []
    carpetas_existentes = []

    for folder_key, data in folders_report.items():
        created_now = data['created']
        files_count = data['files_count']
        bytes_moved = data['bytes_moved']
        ext_count = data['ext_count']

        total_bytes += bytes_moved
        if created_now:
            carpetas_creadas.append(folder_key)
        else:
            carpetas_existentes.append(folder_key)

        logging.info(f"- Carpeta RAW: {folder_key}")
        if created_now:
            logging.info("    (Subcarpeta creada en esta ejecución)")
        else:
            logging.info("    (Subcarpeta ya existente)")
        logging.info(f"    Archivos RAW movidos: {files_count}")
        logging.info("    Detalle por extensión:")
        for ext, count in ext_count.items():
            logging.info(f"      {ext}: {count}")
        logging.info(f"    Tamaño total movido: {human_readable_size(bytes_moved)}")

    logging.info("=== Detalle de subcarpetas 'RAW' creadas vs. existentes ===")
    logging.info(f"Subcarpetas 'RAW' creadas en esta ejecución: {len(carpetas_creadas)}")
    for c in carpetas_creadas:
        logging.info(f"   -> {c}")

    logging.info(f"Subcarpetas 'RAW' ya existentes donde se movieron archivos: {len(carpetas_existentes)}")
    for c in carpetas_existentes:
        logging.info(f"   -> {c}")

    logging.info(f"=== Se han movido un total de {human_readable_size(total_bytes)} en esta ejecución ===")


def generar_resumen_pdf():
    if not folders_report:
        return

    pdf_filename = os.path.join(PDF_DIR, f"organizar_raw_{today_str}.pdf")
    pdf = FPDF(format='A4', orientation='P', unit='mm')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Resumen de Organización de Archivos RAW", ln=True, align='C')

    fecha_hoy = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Fecha de ejecución: {fecha_hoy}", ln=True)
    pdf.ln(5)

    total_bytes = 0
    carpetas_creadas = []
    carpetas_existentes = []

    def write_line(text, indent=0, bold=False):
        if bold:
            pdf.set_font("Arial", "B", 12)
        else:
            pdf.set_font("Arial", "", 12)
        if indent:
            pdf.cell(indent)
        pdf.multi_cell(0, 6, text, align='L')
        pdf.ln(0)

    for folder_key, data in folders_report.items():
        created_now = data['created']
        files_count = data['files_count']
        bytes_moved = data['bytes_moved']
        ext_count = data['ext_count']

        total_bytes += bytes_moved
        if created_now:
            carpetas_creadas.append(folder_key)
        else:
            carpetas_existentes.append(folder_key)

        folder_display = folder_key.replace("\\", "/")

        write_line(f"Carpeta RAW: {folder_display}", bold=True)
        if created_now:
            write_line("(Subcarpeta creada en esta ejecución)", indent=5)
        else:
            write_line("(Subcarpeta ya existente)", indent=5)

        write_line(f"Archivos RAW movidos: {files_count}", indent=5)

        write_line("Detalle por extensión:", indent=5)
        for ext, count in ext_count.items():
            write_line(f"- {ext}: {count}", indent=10)

        size_str = human_readable_size(bytes_moved)
        write_line(f"Tamaño total movido: {size_str}", indent=5)
        pdf.ln(5)

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "Resumen Global:", ln=True)
    pdf.set_font("Arial", "", 12)

    write_line(f"Subcarpetas 'RAW' creadas en esta ejecución: {len(carpetas_creadas)}")
    for c in carpetas_creadas:
        c_disp = c.replace("\\", "/")
        write_line(f"   -> {c_disp}", indent=5)

    write_line(f"Subcarpetas 'RAW' ya existentes: {len(carpetas_existentes)}")
    for c in carpetas_existentes:
        c_disp = c.replace("\\", "/")
        write_line(f"   -> {c_disp}", indent=5)

    total_str = human_readable_size(total_bytes)
    write_line(f"Se han movido un total de {total_str} en esta ejecución.")

    pdf.output(pdf_filename)
    logging.info(f"PDF generado correctamente: {pdf_filename}")


def main():
    try:
        camaras_a_procesar = seleccionar_camaras()
        if not camaras_a_procesar:
            print("No se seleccionaron cámaras o no hay cámaras disponibles. Saliendo.")
            return

        organizar_raw_en_subcarpeta(camaras_a_procesar)
        generar_resumen_txt()
        generar_resumen_pdf()

        logging.info("Proceso de organización de archivos RAW finalizado.")
    except Exception as e:
        logging.error(f"Error inesperado: {e}")


if __name__ == "__main__":
    main()
