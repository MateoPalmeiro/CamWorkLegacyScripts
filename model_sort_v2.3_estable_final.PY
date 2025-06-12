#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Este script recorre la carpeta CAMERAS y clasifica imágenes y vídeos según el
tag EXIF 'Model'. Algunas cámaras (especialmente en MP4/MTS) no incluyen ese tag;
esos archivos se dejan sin mover para revisión posterior.

Flujos principales:
  - Procesa extensiones definidas en PHOTO_EXTENSIONS.
  - Lee el tag EXIF 'Model' con exiftool.
  - Si no existe el tag, registra la incidencia y deja el archivo sin mover.
  - Mapea el modelo EXIF a una carpeta destino usando MODEL_TO_FOLDER.
  - Si el modelo no está en el mapa, registra la incidencia y deja el archivo sin mover.
  - Detecta duplicados bit a bit comparando hashes SHA-256 dentro de la carpeta
    de ese modelo (incluyendo subcarpetas).
  - Mueve archivos no duplicados a la carpeta destino.
  - Crea un PDF compacto y profesional con métricas y resúmenes.
  - Registra todos los eventos en un log .txt y los imprime por pantalla.

Cumple estándares ISO/IEC/IEEE para documentación y mantenimiento.
"""

# -----------------------------------------------------------------------------
# IMPORTACIONES PRINCIPALES
# -----------------------------------------------------------------------------
import os                      # Operaciones con sistema de archivos
import re                      # Sanitización de nombres de carpeta
import shutil                  # Movimiento de archivos
import subprocess              # Llamadas a exiftool para leer EXIF Model
import logging                 # Registro de eventos (logs)
import hashlib                 # Cálculo de hashes SHA-256
from datetime import datetime  # Fecha y hora actual
from fpdf import FPDF          # Generación de documentos PDF

# -----------------------------------------------------------------------------
# CONFIGURACIÓN (ISO/IEC/IEEE 12207:2017 - Ciclo de Vida del Software)
# -----------------------------------------------------------------------------
CAMERAS_DIR = "CAMERAS"       # Carpeta raíz con archivos a clasificar
PHOTO_EXTENSIONS = {          # Extensiones admitidas
    ".arw", ".cr2", ".cr3",
    ".jpg", ".mov", ".mp4", ".mts"
}
MODEL_TO_FOLDER = {           # Mapeo EXIF Model → carpeta destino
    "Canon EOS 650D":               "Canon EOS 650D",
    "Canon EOS M50m2":              "Canon EOS M50m2",
    "Canon PowerShot G9 X Mark II": "Canon Powershot G9 X Mark II",
    "Canon PowerShot SX230 HS":     "Canon PowerShot SX230 HS",
    "Canon PowerShot SX610 HS":     "Canon PowerShot SX610 HS",
    "DMC-TZ57":                     "Panasonic DCM-TZ57",
    "DV300 / DV300F / DV305F":      "Samsung DV300F",
    "Full HD Camcorder":            "Samsung HMX-H300",
    "HMX-H300":                     "Samsung HMX-H300",
    "HERO7 White":                  "Gopro Hero7 White",
    "HERO10 Black":                 "Gopro Hero10 Black",
    "HERO11 Black":                 "Gopro Hero11 Black",
    "ILCE-6000":                    "Sony ILCE-6000",
    "WB30F":                        "Samsung WB30F",
    "WB30F/WB31F/WB32F":            "Samsung WB30F",
}

# -----------------------------------------------------------------------------
# LOGGING (ISO/IEC/IEEE 42010:2011 - Arquitectura de Sistemas)
# -----------------------------------------------------------------------------
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILENAME = os.path.join(LOGS_DIR, f"clasificar_imagenes_{ts}.log")

# Logger raíz
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Formato estándar: timestamp - nivel - mensaje
fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Handler a fichero de log
fh = logging.FileHandler(LOG_FILENAME)
fh.setLevel(logging.INFO)
fh.setFormatter(fmt)
logger.addHandler(fh)

# Handler a consola (stdout)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(fmt)
logger.addHandler(ch)

# -----------------------------------------------------------------------------
# LISTAS PARA RESUMEN
# -----------------------------------------------------------------------------
unmapped        = []    # Archivos sin EXIF Model o modelo no mapeado
duplicates      = []    # Archivos duplicados detectados (hash iguales)
moved           = []    # Archivos movidos correctamente
scanned_cameras = set() # Carpeta destino usadas

# -----------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# -----------------------------------------------------------------------------

def sanitize_folder_name(name):
    """
    Sustituye caracteres inválidos en nombres de carpeta por '_'.
    """
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def get_camera_model(filepath):
    """
    Lee el tag EXIF 'Model' usando exiftool.
    Retorna la cadena exacta o None si no existe o hay error.
    """
    try:
        res = subprocess.run(
            ["exiftool", "-Model", "-s3", filepath],
            capture_output=True, text=True
        )
        if res.returncode == 0:
            model = res.stdout.strip()
            if model:
                return model
        logger.error(f"No está EXIF 'Model' en: {filepath}")
    except Exception as e:
        logger.error(f"Error exiftool en '{filepath}': {e}")
    return None

def sha256_of_file(path, chunk_size=8192):
    """
    Calcula el hash SHA-256 de un archivo en bloques.
    Devuelve el hash hexadecimal o None si falla la lectura.
    """
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        logger.error(f"Error calculando SHA-256 de '{path}': {e}")
        return None

def is_duplicate(dest_folder, src_path):
    """
    Detecta si src_path está duplicado en dest_folder comparando hashes
    bit a bit (SHA-256) contra todos los archivos presentes en esa carpeta
    y sus subcarpetas.
    """
    src_hash = sha256_of_file(src_path)
    if src_hash is None:
        # No se puede calcular hash: no movemos el archivo y lo marcamos
        logger.error(f"Imposible calcular hash, '{src_path}' queda sin mover")
        unmapped.append(src_path)
        return True
    for root, _, files in os.walk(dest_folder):
        for f in files:
            existing = os.path.join(root, f)
            if sha256_of_file(existing) == src_hash:
                return True
    return False

# -----------------------------------------------------------------------------
# GENERACIÓN DE INFORME PDF PROFESIONAL (ISO/IEC/IEEE 26514:2018)
# -----------------------------------------------------------------------------
def generate_report_pdf(processed_count):
    """
    Crea un PDF compacto y profesional con:
      - Portada con título y fecha
      - Métricas generales
      - Tabla resumen por carpeta destino
      - Listado de sin EXIF Model y duplicados
    """
    if not (moved or unmapped or duplicates):
        logger.info("Sin datos para informe PDF.")
        return

    pdf_path = os.path.join(LOGS_DIR, f"clasificar_report_{ts}.pdf")
    pdf = FPDF(format='A4', orientation='P', unit='mm')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.set_margins(15, 15, 15)

    # ---- Portada ----
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Informe de Clasificación de Archivos", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 6, f"Fecha: {datetime.now():%d-%m-%Y %H:%M:%S}", ln=True, align='C')
    pdf.ln(10)

    # ---- Métricas generales ----
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "Métricas Generales", ln=True)
    pdf.ln(2)
    pdf.set_font("Arial", "", 11)
    pdf.cell(60, 6, "Procesados:", border=0)
    pdf.cell(0, 6, str(processed_count), ln=True)
    pdf.cell(60, 6, "Movidos:", border=0)
    pdf.cell(0, 6, str(len(moved)), ln=True)
    pdf.cell(60, 6, "Sin EXIF Model:", border=0)
    pdf.cell(0, 6, str(len(unmapped)), ln=True)
    pdf.cell(60, 6, "Duplicados:", border=0)
    pdf.cell(0, 6, str(len(duplicates)), ln=True)
    pdf.cell(60, 6, "Carpetas destino:", border=0)
    pdf.cell(0, 6, str(len(scanned_cameras)), ln=True)
    pdf.ln(8)

    # ---- Tabla resumen por carpeta ----
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "Resumen por Carpeta", ln=True)
    pdf.ln(2)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(80, 7, "Carpeta", border=1, align='C')
    pdf.cell(40, 7, "Movidos", border=1, align='C')
    pdf.cell(40, 7, "Duplicados", border=1, align='C')
    pdf.ln()
    pdf.set_font("Arial", "", 11)
    for cam in sorted(scanned_cameras):
        display = cam if len(cam) <= 30 else "…" + cam[-29:]
        moved_cam = sum(1 for p in moved if sanitize_folder_name(cam) in p)
        dup_cam   = sum(1 for p in duplicates if sanitize_folder_name(cam) in p)
        pdf.cell(80, 6, display, border=1)
        pdf.cell(40, 6, str(moved_cam), border=1, align='C')
        pdf.cell(40, 6, str(dup_cam), border=1, align='C')
        pdf.ln()
    pdf.ln(5)

    # ---- Listado sin EXIF 'Model' ----
    if unmapped:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 6, "Sin EXIF 'Model'", ln=True)
        pdf.ln(2)
        pdf.set_font("Arial", "", 10)
        for p in unmapped:
            fn = os.path.basename(p)
            short = fn if len(fn) <= 50 else "…" + fn[-47:]
            pdf.multi_cell(0, 5, f"- {short}")
        pdf.ln(3)

    # ---- Listado de duplicados ----
    if duplicates:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 6, "Duplicados", ln=True)
        pdf.ln(2)
        pdf.set_font("Arial", "", 10)
        for p in duplicates:
            fn = os.path.basename(p)
            short = fn if len(fn) <= 50 else "…" + fn[-47:]
            pdf.multi_cell(0, 5, f"- {short}")
        pdf.ln(3)

    pdf.output(pdf_path)
    logger.info(f"PDF generado: {pdf_path}")

# -----------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL (ISO/IEC/IEEE 12207:2017)
# -----------------------------------------------------------------------------
def classify_images():
    """
    Clasifica cada archivo en CAMERAS_DIR:
      1) Verifica extensión en PHOTO_EXTENSIONS.
      2) Lee tag EXIF 'Model'.
      3) Si no existe, registra y omite.
      4) Mapea modelo a carpeta destino.
      5) Detecta duplicados SHA-256.
      6) Mueve o registra duplicado.
      7) Al final, genera informe PDF.
    """
    if not os.path.isdir(CAMERAS_DIR):
        logger.critical(f"No existe '{CAMERAS_DIR}'")
        return

    processed_count = 0
    for item in os.listdir(CAMERAS_DIR):
        src = os.path.join(CAMERAS_DIR, item)
        if not os.path.isfile(src):
            continue
        _, ext = os.path.splitext(item)
        if ext.lower() not in PHOTO_EXTENSIONS:
            logger.info(f"Omite '{item}' (extensión no soportada)")
            continue

        processed_count += 1

        # Leer tag EXIF 'Model'
        model = get_camera_model(src)
        if model is None:
            logger.error(f"'{item}' sin tag EXIF 'Model'; queda sin mover")
            unmapped.append(src)
            continue

        # Mapear a carpeta destino
        folder = MODEL_TO_FOLDER.get(model)
        if not folder:
            logger.error(f"Modelo '{model}' no mapeado; '{item}' queda sin mover")
            unmapped.append(src)
            continue

        scanned_cameras.add(folder)
        dest = os.path.join(CAMERAS_DIR, sanitize_folder_name(folder))
        os.makedirs(dest, exist_ok=True)

        # Detectar duplicado por hash
        if is_duplicate(dest, src):
            logger.warning(f"Duplicado, no movido: '{src}'")
            duplicates.append(src)
            continue

        # Mover archivo
        try:
            shutil.move(src, os.path.join(dest, item))
            moved.append(src)
            logger.info(f"Movido '{item}' → '{dest}'")
        except Exception as e:
            logger.error(f"Error moviendo '{item}': {e}")
            duplicates.append(src)

    # Resumen final en logs
    if unmapped:
        logger.info("=== Archivos sin EXIF 'Model' o modelo no mapeado ===")
        for p in unmapped:
            logger.info(f"    {p}")
    if duplicates:
        logger.info("=== Archivos duplicados (no movidos) ===")
        for p in duplicates:
            logger.info(f"    {p}")

    # Generar PDF con el resumen
    generate_report_pdf(processed_count)

# -----------------------------------------------------------------------------
# EJECUCIÓN
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    classify_images()
