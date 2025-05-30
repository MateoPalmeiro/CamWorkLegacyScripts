#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
import logging
import subprocess
import json
from datetime import datetime, timedelta
from fpdf import FPDF  # Se usa para el PDF final

# ----------------------------------------------------------------------------
# CARPETAS PARA ORGANIZAR SALIDAS
# ----------------------------------------------------------------------------
LOGS_DIR = "logs"
PDF_DIR = "pdf"
METADATA_DIR = "metadata"

# Creamos las carpetas si no existen
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

# ----------------------------------------------------------------------------
# CONFIGURACIÓN DE LOG EN .TXT
# Formato "organizar_por_fecha_dd-mm-yyyy.log"
# ----------------------------------------------------------------------------
today_str = datetime.now().strftime("%d-%m-%Y")
LOG_FILENAME = os.path.join(LOGS_DIR, f"organizar_por_fecha_{today_str}.log")

logging.basicConfig(
    filename=LOG_FILENAME,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ----------------------------------------------------------------------------
# PARÁMETROS GLOBALES
# ----------------------------------------------------------------------------
CAMERAS_DIR = "CAMARAS"
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".cr2", ".arw", ".nef", ".raf", ".heic"}

folders_report = {}
duplicates = []

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
# Funciones para lectura de EXIF con exiftool
# ----------------------------------------------------------------------------

def leer_fecha_con_exiftool(filepath):
    try:
        result = subprocess.run(
            ["exiftool", "-j", filepath],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            logging.warning(f"Exiftool falló para '{filepath}': {result.stderr}")
            return None

        data = json.loads(result.stdout)
        if not data or not isinstance(data, list):
            return None

        metadata = data[0]
        dt_str = metadata.get("DateTimeOriginal")
        if not dt_str:
            dt_str = metadata.get("CreateDate") or metadata.get("SubSecDateTimeOriginal")

        if dt_str:
            dt_str = dt_str.split(".")[0]
            try:
                return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                logging.warning(f"Formato de fecha EXIF inesperado en '{filepath}': {dt_str}")
                return None

    except FileNotFoundError:
        logging.error("exiftool no está en el PATH o no existe.")
        return None
    except Exception as e:
        logging.warning(f"Error usando exiftool en '{filepath}': {e}")
        return None

    return None

def obtener_fecha_captura(filepath):
    fecha = leer_fecha_con_exiftool(filepath)
    if fecha:
        return fecha

    try:
        stat_info = os.stat(filepath)
        creation_time = datetime.fromtimestamp(stat_info.st_ctime)
        return creation_time
    except Exception as e:
        logging.warning(f"No se pudo obtener fecha de creación de '{filepath}': {e}")

    try:
        stat_info = os.stat(filepath)
        modification_time = datetime.fromtimestamp(stat_info.st_mtime)
        return modification_time
    except Exception as e:
        logging.error(f"No se pudo obtener fecha de modificación de '{filepath}': {e}")

    return datetime.now()

def ajustar_mes_por_horario_especial(fecha):
    if fecha.day == 1 and fecha.hour < 8:
        return fecha - timedelta(days=1)
    return fecha

def generar_nombre_carpeta(fecha):
    return f"{fecha.year}.{fecha.month:02d}"

def es_carpeta_yyyy_mm(nombre_carpeta):
    return re.match(r"^\d{4}\.\d{2}$", nombre_carpeta) is not None

# ----------------------------------------------------------------------------
# Selección de cámaras (excluyendo "PRIVATE")
# ----------------------------------------------------------------------------

def seleccionar_camaras():
    if not os.path.isdir(CAMERAS_DIR):
        print(f"La carpeta '{CAMERAS_DIR}' no existe o no es un directorio.")
        return []

    todas_camaras = sorted([
        d for d in os.listdir(CAMERAS_DIR)
        if os.path.isdir(os.path.join(CAMERAS_DIR, d)) and d != "PRIVATE"
    ])

    if not todas_camaras:
        print("No se encontraron carpetas de cámaras en la carpeta CAMERAS.")
        return []

    print("Cámaras disponibles:")
    for i, camara in enumerate(todas_camaras, start=1):
        print(f"{i}. {camara}")

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

# ----------------------------------------------------------------------------
# Lógica principal de organización (saltando "PRIVATE")
# ----------------------------------------------------------------------------

def organizar_fotos_por_fecha(camaras):
    for camera_folder in camaras:
        if camera_folder == "PRIVATE":
            continue
        camera_path = os.path.join(CAMERAS_DIR, camera_folder)
        if not os.path.isdir(camera_path):
            continue
        
        logging.info(f"Procesando carpeta de cámara: {camera_path}")

        for item in os.listdir(camera_path):
            item_path = os.path.join(camera_path, item)
            if os.path.isdir(item_path):
                continue

            _, ext = os.path.splitext(item)
            ext = ext.lower()
            if ext not in PHOTO_EXTENSIONS:
                continue

            fecha_captura = obtener_fecha_captura(item_path)
            fecha_captura_ajustada = ajustar_mes_por_horario_especial(fecha_captura)
            carpeta_destino = generar_nombre_carpeta(fecha_captura_ajustada)
            destino_path = os.path.join(camera_path, carpeta_destino)

            if not os.path.exists(destino_path):
                try:
                    os.mkdir(destino_path)
                    logging.info(f"Creada carpeta: {destino_path}")
                except OSError as e:
                    logging.error(f"Error al crear carpeta '{destino_path}': {e}")
                    continue

            nuevo_path = os.path.join(destino_path, item)
            # --- Saltar archivos duplicados ---
            if os.path.exists(nuevo_path):
                logging.warning(f"Duplicado detectado, no movido: '{item_path}' ya existe en '{destino_path}'")
                duplicates.append(item_path)
                continue
            # -------------------------------------

            try:
                size_bytes = os.path.getsize(item_path)
                shutil.move(item_path, nuevo_path)
                logging.info(f"Movida foto '{item}' a '{destino_path}'")

                folder_key = destino_path
                if folder_key not in folders_report:
                    folders_report[folder_key] = {
                        'created': True,
                        'photos_count': 0,
                        'ext_count': {},
                        'bytes_moved': 0
                    }
                folders_report[folder_key]['photos_count'] += 1
                folders_report[folder_key]['bytes_moved'] += size_bytes
                folders_report[folder_key]['ext_count'].setdefault(ext, 0)
                folders_report[folder_key]['ext_count'][ext] += 1

            except PermissionError as e:
                logging.error(f"Permiso denegado al mover '{item}': {e}")
            except OSError as e:
                logging.error(f"Error al mover '{item}' a '{destino_path}': {e}")

# ----------------------------------------------------------------------------
# Generar resumen en el .txt
# ----------------------------------------------------------------------------

def generar_resumen_txt():
    logging.info("=== RESUMEN FINAL DE LA EJECUCIÓN ===")

    if not folders_report and not duplicates:
        logging.info("No se movió ninguna foto. No hay cambios.")
        return

    total_bytes = 0
    carpetas_creadas = []
    carpetas_existentes = []

    for folder_key, data in folders_report.items():
        created_now = data['created']
        photos_count = data['photos_count']
        bytes_moved = data['bytes_moved']
        ext_count = data['ext_count']

        total_bytes += bytes_moved
        if created_now:
            carpetas_creadas.append(folder_key)
        else:
            carpetas_existentes.append(folder_key)

        logging.info(f"- Carpeta: {folder_key}")
        logging.info("    (Carpeta creada en esta ejecución)" if created_now else "    (Carpeta ya existente)")
        logging.info(f"    Fotos movidas: {photos_count}")
        logging.info("    Detalle por extensión:")
        for ext, count in ext_count.items():
            logging.info(f"      {ext}: {count}")
        logging.info(f"    Tamaño total movido: {human_readable_size(bytes_moved)}")

    logging.info("=== Detalle de carpetas creadas vs. existentes ===")
    logging.info(f"Carpetas creadas en esta ejecución: {len(carpetas_creadas)}")
    for c in carpetas_creadas:
        logging.info(f"   -> {c}")
    logging.info(f"Carpetas ya existentes donde se movieron fotos: {len(carpetas_existentes)}")
    for c in carpetas_existentes:
        logging.info(f"   -> {c}")

    if duplicates:
        logging.info("=== Archivos duplicados no movidos ===")
        for dup in duplicates:
            logging.info(f"   - {dup}")

    total_size_str = human_readable_size(total_bytes)
    logging.info(f"=== Se han movido un total de {total_size_str} en esta ejecución ===")

# ----------------------------------------------------------------------------
# Generar resumen en PDF
# ----------------------------------------------------------------------------

def generar_resumen_pdf():
    if not folders_report and not duplicates:
        return

    pdf_filename = os.path.join(PDF_DIR, f"organizar_por_fecha_{today_str}.pdf")
    pdf = FPDF(format='A4', orientation='P', unit='mm')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Resumen de Organización de Fotos por Fecha", ln=True, align='C')
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Fecha de ejecución: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}", ln=True)
    pdf.ln(5)

    total_bytes = 0
    carpetas_creadas = []
    carpetas_existentes = []

    def write_line(text, indent=0, bold=False):
        pdf.set_font("Arial", "B", 12 if bold else "Arial", "")
        if indent: pdf.cell(indent)
        pdf.multi_cell(0, 6, text)
        pdf.ln(0)

    for folder_key, data in folders_report.items():
        created_now = data['created']
        photos_count = data['photos_count']
        bytes_moved = data['bytes_moved']
        ext_count = data['ext_count']

        total_bytes += bytes_moved
        (carpetas_creadas if created_now else carpetas_existentes).append(folder_key)

        write_line(f"Carpeta: {folder_key}", bold=True)
        write_line("(Creada en esta ejecución)" if created_now else "(Ya existía)", indent=5)
        write_line(f"Fotos movidas: {photos_count}", indent=5)
        write_line("Detalle por extensión:", indent=5)
        for ext, cnt in ext_count.items():
            write_line(f"- {ext}: {cnt}", indent=10)
        write_line(f"Tamaño movido: {human_readable_size(bytes_moved)}", indent=5)
        pdf.ln(5)

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "Resumen Global:", ln=True)
    pdf.set_font("Arial", "", 12)
    write_line(f"Carpetas creadas: {len(carpetas_creadas)}")
    for c in carpetas_creadas: write_line(f"-> {c}", indent=5)
    write_line(f"Carpetas existentes: {len(carpetas_existentes)}")
    for c in carpetas_existentes: write_line(f"-> {c}", indent=5)

    if duplicates:
        write_line("Duplicados no movidos:", bold=True)
        for dup in duplicates:
            write_line(f"- {dup}", indent=5)

    write_line(f"Total movido: {human_readable_size(total_bytes)}")
    pdf.output(pdf_filename)
    logging.info(f"PDF generado correctamente: {pdf_filename}")

# ----------------------------------------------------------------------------
# EJECUCIÓN PRINCIPAL
# ----------------------------------------------------------------------------

def main():
    try:
        camaras_a_procesar = seleccionar_camaras()
        if not camaras_a_procesar:
            print("No se seleccionaron cámaras o no hay cámaras disponibles. Saliendo.")
            return

        organizar_fotos_por_fecha(camaras_a_procesar)
        generar_resumen_txt()
        generar_resumen_pdf()
        logging.info("Proceso de organización de fotos finalizado correctamente.")
    except Exception as e:
        logging.error(f"Error inesperado: {e}")

if __name__ == "__main__":
    main()
