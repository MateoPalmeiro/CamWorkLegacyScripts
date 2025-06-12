#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Model_Date_Sort_v1: Clasificación por Modelo y Organización por Fecha

Este script unificado ejecuta dos fases:
  1) Clasificación por EXIF 'Model' (migración a carpetas por modelo)
  2) Organización por fecha de captura (creación de subcarpetas YYYY.MM)

Solo se procesan en la fase de fechas los archivos que han sido movidos
durante la fase de clasificación. Se mantiene toda la lógica, casos especiales,
detección de duplicados y el estilo de generación de informes de los scripts
originales.

Cumple estándares ISO/IEC/IEEE para documentación, arquitectura y mantenimiento.
"""

# -----------------------------------------------------------------------------
# IMPORTACIONES PRINCIPALES
# -----------------------------------------------------------------------------
import os                      # Operaciones con sistema de archivos
import re                      # Sanitización de nombres de carpeta
import shutil                  # Movimiento de archivos
import subprocess              # Llamadas a exiftool para metadatos
import logging                 # Registro de eventos (logs)
import hashlib                 # Cálculo de hashes SHA-256
import json                    # Parseo de JSON de exiftool
from datetime import datetime, timedelta
from fpdf import FPDF          # Generación de documentos PDF

# -----------------------------------------------------------------------------
# CONFIGURACIÓN (ISO/IEC/IEEE 12207:2017 - Ciclo de Vida del SW)
# -----------------------------------------------------------------------------
CAMERAS_DIR      = "CAMARAS"    # Carpeta raíz con archivos/media
PHOTO_EXTENSIONS = {             # Extensiones válidas
    ".arw", ".cr2", ".cr3",
    ".jpg", ".mov", ".mp4", ".mts"
}

LOGS_DIR = "logs"
PDF_DIR  = "pdf"
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)

# Timestamp para archivos de log y PDF
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = os.path.join(LOGS_DIR, f"model_date_sort_{ts}.log")
PDF_FILE = os.path.join(PDF_DIR,    f"model_date_sort_{ts}.pdf")

# -----------------------------------------------------------------------------
# LOGGER (ISO/IEC/IEEE 42010:2011 - Arquitectura de Sistemas)
# -----------------------------------------------------------------------------
logger = logging.getLogger("ModelDateSort")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Handler a fichero de log
fh = logging.FileHandler(LOG_FILE)
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)
logger.addHandler(fh)

# Handler a consola
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

# -----------------------------------------------------------------------------
# Mapeo EXIF Model → carpeta destino
# -----------------------------------------------------------------------------
MODEL_TO_FOLDER = {
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
# MEMORIA INTERNA PARA RESULTADOS
# -----------------------------------------------------------------------------
# Fase 1: clasificación por modelo
unmapped = []       # Archivos sin EXIF Model o modelo no mapeado
duplicates = []     # Archivos duplicados (hash iguales)
moved = []          # Rutas finales de archivos movidos
models_used = set() # Carpetas de modelo creadas/empleadas

# Fase 2: organización por fecha
folders_report = {} # {ruta_carpeta_fecha: {'count', 'bytes'}}
dup_date = []       # Duplicados detectados en fase de fecha

# -----------------------------------------------------------------------------
# FUNCIONES AUXILIARES COMUNES
# -----------------------------------------------------------------------------
def sanitize_folder_name(name):
    """
    Reemplaza caracteres inválidos en nombres de carpeta.
    """
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def sha256_of_file(path, chunk_size=8192):
    """
    Calcula el hash SHA-256 de un archivo en bloques.
    """
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        logger.error(f"Error SHA-256 '{path}': {e}")
        return None

# -----------------------------------------------------------------------------
# FASE 1: Clasificación por EXIF 'Model'
# -----------------------------------------------------------------------------
def get_camera_model(filepath):
    """
    Lee el tag EXIF 'Model' usando exiftool.
    Retorna cadena o None.
    """
    try:
        res = subprocess.run(
            ["exiftool", "-Model", "-s3", filepath],
            capture_output=True, text=True
        )
        model = res.stdout.strip() if res.returncode == 0 else ""
        return model or None
    except Exception as e:
        logger.error(f"Exiftool error '{filepath}': {e}")
        return None

def is_duplicate(dest, src):
    """
    Comprueba duplicado bit a bit en 'dest' comparando SHA-256.
    """
    src_hash = sha256_of_file(src)
    if not src_hash:
        unmapped.append(src)
        return True
    for root, _, files in os.walk(dest):
        for fn in files:
            if sha256_of_file(os.path.join(root, fn)) == src_hash:
                return True
    return False

def classify_phase():
    """
    Itera sobre archivos en CAMERAS_DIR, los clasifica por modelo,
    detecta duplicados y mueve los no duplicados.
    """
    processed = 0
    if not os.path.isdir(CAMERAS_DIR):
        logger.critical(f"No existe '{CAMERAS_DIR}'")
        return processed

    for entry in os.listdir(CAMERAS_DIR):
        src = os.path.join(CAMERAS_DIR, entry)
        if not os.path.isfile(src):
            continue
        ext = os.path.splitext(entry)[1].lower()
        if ext not in PHOTO_EXTENSIONS:
            continue

        processed += 1
        model = get_camera_model(src)
        if not model:
            logger.error(f"Sin EXIF 'Model': {src}")
            unmapped.append(src)
            continue

        folder = MODEL_TO_FOLDER.get(model)
        if not folder:
            logger.error(f"Modelo no mapeado '{model}': {src}")
            unmapped.append(src)
            continue

        models_used.add(folder)
        dest_dir = os.path.join(CAMERAS_DIR, sanitize_folder_name(folder))
        os.makedirs(dest_dir, exist_ok=True)

        if is_duplicate(dest_dir, src):
            logger.warning(f"Duplicado detectado: {src}")
            duplicates.append(src)
            continue

        try:
            dest_path = os.path.join(dest_dir, entry)
            shutil.move(src, dest_path)
            moved.append(dest_path)
            logger.info(f"Movido '{entry}' → '{dest_dir}'")
        except Exception as e:
            logger.error(f"Error moviendo '{src}': {e}")
            duplicates.append(src)

    return processed

# -----------------------------------------------------------------------------
# FASE 2: Organización por Fecha de los archivos movidos
# -----------------------------------------------------------------------------
def read_exif_date(filepath):
    """
    Extrae DateTimeOriginal con exiftool -j.
    Devuelve datetime o None.
    """
    try:
        res = subprocess.run(
            ["exiftool", "-j", "-DateTimeOriginal", filepath],
            capture_output=True, text=True
        )
        if res.returncode != 0:
            return None
        arr = json.loads(res.stdout or "[]")
        dtstr = arr[0].get("DateTimeOriginal", "").split(".")[0]
        return datetime.strptime(dtstr, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None

def get_capture_date(path):
    """
    Determina fecha de captura (EXIF o timestamp de sistema).
    """
    dt = read_exif_date(path)
    if dt:
        logger.info(f"[EXIF] {dt} ← {path}")
        return dt
    try:
        fs = datetime.fromtimestamp(os.path.getctime(path))
        logger.info(f"[FS]   {fs} ← {path}")
        return fs
    except Exception as e:
        logger.error(f"Fecha indeterminada '{path}': {e}")
        return None

def adjust_month(dt):
    """
    Ajusta día 1 antes de las 08:00 al mes anterior.
    """
    if dt.day == 1 and dt.hour < 8:
        return dt - timedelta(days=1)
    return dt

def datesort_phase():
    """
    Procesa únicamente los archivos en 'moved', creando subcarpetas YYYY.MM
    y moviendo los archivos según su fecha de captura.
    """
    for src in moved:
        model_dir = os.path.dirname(src)
        name = os.path.basename(src)
        dt = get_capture_date(src)
        if not dt:
            continue
        dt = adjust_month(dt)
        folder = f"{dt.year}.{dt.month:02d}"
        dest_dir = os.path.join(model_dir, folder)
        os.makedirs(dest_dir, exist_ok=True)
        dst = os.path.join(dest_dir, name)
        if os.path.exists(dst):
            logger.warning(f"Duplicado fecha: {src}")
            dup_date.append(src)
            continue
        try:
            size = os.path.getsize(src)
            shutil.move(src, dst)
            rpt = folders_report.setdefault(dest_dir, {'count': 0, 'bytes': 0})
            rpt['count'] += 1
            rpt['bytes'] += size
            logger.info(f"MOVED by date: '{name}' → '{folder}'")
        except Exception as e:
            logger.error(f"Error moviendo por fecha '{src}': {e}")

# -----------------------------------------------------------------------------
# GENERACIÓN DE INFORME PDF ÚNICO (ISO/IEC/IEEE 26514:2018)
# -----------------------------------------------------------------------------
def generate_summary_pdf(processed_count):
    """
    Crea un solo PDF con:
      - Portada y fecha de ejecución.
      - Sección 1: Métricas y resultados de clasificación por modelo.
      - Sección 2: Métricas y resultados de organización por fecha.
      - Listados de archivos sin EXIF, duplicados y colisiones de fecha.
    """
    pdf = FPDF(format='A4', orientation='P', unit='mm')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.set_margins(15, 15, 15)

    # Portada
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "CamWork: Model + Date Sort v1", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 6, f"Fecha: {datetime.now():%d-%m-%Y %H:%M:%S}", ln=True, align='C')
    pdf.ln(10)

    # --- SECCIÓN 1: Clasificación por Modelo ---
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 6, "1. Clasificación por Modelo", ln=True)
    pdf.ln(4)

    # Métricas generales clasificación
    pdf.set_font("Arial", "B", 12); pdf.cell(0, 6, "Métricas Generales", ln=True); pdf.ln(2)
    pdf.set_font("Arial", "", 11)
    pdf.cell(60, 6, "Procesados:", border=0);               pdf.cell(0, 6, str(processed_count), ln=True)
    pdf.cell(60, 6, "Movidos:", border=0);                  pdf.cell(0, 6, str(len(moved)), ln=True)
    pdf.cell(60, 6, "Sin EXIF/No mapeado:", border=0);      pdf.cell(0, 6, str(len(unmapped)), ln=True)
    pdf.cell(60, 6, "Duplicados:", border=0);               pdf.cell(0, 6, str(len(duplicates)), ln=True)
    pdf.ln(6)

    # Resumen por modelo
    pdf.set_font("Arial", "B", 12); pdf.cell(0, 6, "Resumen por Modelo", ln=True); pdf.ln(2)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(80, 7, "Modelo", border=1, align='C')
    pdf.cell(40, 7, "Movidos", border=1, align='C')
    pdf.cell(40, 7, "Duplicados", border=1, align='C'); pdf.ln()
    pdf.set_font("Arial", "", 11)
    for mdl in sorted(models_used):
        disp = mdl if len(mdl) <= 30 else "…" + mdl[-29:]
        moved_c = sum(1 for p in moved if sanitize_folder_name(mdl) in p)
        dup_c   = sum(1 for p in duplicates if sanitize_folder_name(mdl) in p)
        pdf.cell(80, 6, disp, border=1)
        pdf.cell(40, 6, str(moved_c), border=1, align='C')
        pdf.cell(40, 6, str(dup_c), border=1, align='C'); pdf.ln()
    pdf.ln(5)

    # Listado sin EXIF/modelo no mapeado y duplicados
    if unmapped:
        pdf.set_font("Arial", "B", 12); pdf.cell(0, 6, "Archivos sin EXIF 'Model' o no mapeados", ln=True); pdf.ln(2)
        pdf.set_font("Arial", "", 10)
        for p in unmapped: pdf.multi_cell(0, 5, f"- {os.path.basename(p)}")
        pdf.ln(3)
    if duplicates:
        pdf.set_font("Arial", "B", 12); pdf.cell(0, 6, "Duplicados detectados", ln=True); pdf.ln(2)
        pdf.set_font("Arial", "", 10)
        for p in duplicates: pdf.multi_cell(0, 5, f"- {os.path.basename(p)}")
        pdf.ln(5)

    # --- SECCIÓN 2: Organización por Fecha ---
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 6, "2. Organización por Fecha", ln=True)
    pdf.ln(4)

    # Métricas generales fecha
    total_photos = sum(d['count'] for d in folders_report.values())
    total_bytes  = sum(d['bytes'] for d in folders_report.values())
    total_folds  = len(folders_report)
    pdf.set_font("Arial", "B", 12); pdf.cell(0, 6, "Métricas Generales", ln=True); pdf.ln(2)
    pdf.set_font("Arial", "", 11)
    pdf.cell(60,6,"Carpetas fecha:",border=0); pdf.cell(0,6,str(total_folds),ln=True)
    pdf.cell(60,6,"Fotos movidas:",border=0);  pdf.cell(0,6,str(total_photos),ln=True)
    pdf.cell(60,6,"Bytes totales:",border=0); pdf.cell(0,6,str(total_bytes),ln=True)
    pdf.cell(60,6,"Duplicados fecha:",border=0); pdf.cell(0,6,str(len(dup_date)),ln=True)
    pdf.ln(6)

    # Resumen por carpeta de fecha
    pdf.set_font("Arial", "B", 12); pdf.cell(0, 6, "Resumen por Carpeta de Fecha", ln=True); pdf.ln(2)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(80,7,"Carpeta",border=1,align='C')
    pdf.cell(40,7,"Fotos",border=1,align='C')
    pdf.cell(40,7,"Bytes",border=1,align='C'); pdf.ln()
    pdf.set_font("Arial", "", 11)
    for fld, data in folders_report.items():
        name = os.path.basename(fld)
        if len(name) > 30: name = "…" + name[-29:]
        pdf.cell(80,6,name,border=1)
        pdf.cell(40,6,str(data['count']),border=1,align='C')
        pdf.cell(40,6,str(data['bytes']),border=1,align='R'); pdf.ln()
    pdf.ln(5)

    # Listado de duplicados por fecha
    if dup_date:
        pdf.set_font("Arial", "B", 12); pdf.cell(0, 6, "Duplicados en fase de fecha", ln=True); pdf.ln(2)
        pdf.set_font("Arial", "", 10)
        for p in dup_date: pdf.multi_cell(0, 5, f"• {os.path.basename(p)}")
        pdf.ln(3)

    pdf.output(PDF_FILE)
    logger.info(f"PDF resumen generado en {PDF_FILE}")

# -----------------------------------------------------------------------------
# EJECUCIÓN PRINCIPAL (ISO/IEC/IEEE 12207:2017)
# -----------------------------------------------------------------------------
def main():
    """
    Punto de entrada:
      1) Fase de clasificación por modelo.
      2) Fase de organización por fecha (solo archivos movidos).
      3) Generación de único informe PDF.
    """
    processed = classify_phase()
    datesort_phase()
    generate_summary_pdf(processed)
    logger.info("Proceso completado: Model_Date_Sort_v1.")

if __name__ == "__main__":
    main()
