#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Este script recorre la carpeta CAMARAS y extrae modelos EXIF y extensiones de archivo,
saltando los archivos con extensiones no deseadas (.ffs_db, .ini), registrando en log y
consola, detecta vídeos (MP4/MTS) sin tag EXIF 'Model', y genera un informe PDF
profesional con métricas y listas finales.

Cumple estándares profesionales de documentación ISO/IEC/IEEE.
"""

import os                      # Operaciones con sistema de archivos
import subprocess              # Llamadas a exiftool para EXIF 'Model'
import logging                 # Registro de eventos (logs)
import sys                     # Salida del script en casos críticos
from datetime import datetime  # Fecha y hora actuales
from fpdf import FPDF          # Generación de documentos PDF

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE DIRECTORIOS
# -----------------------------------------------------------------------------
CAMERAS_DIR    = "CAMARAS"    # Carpeta raíz a recorrer
LOGS_DIR       = "logs"       # Carpeta para logs
PDF_DIR        = "pdf"        # Carpeta para informes PDF

os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(PDF_DIR,  exist_ok=True)

# -----------------------------------------------------------------------------
# 2. CONFIGURACIÓN DE LOGGING (ISO/IEC/IEEE 42010:2011)
# -----------------------------------------------------------------------------
timestamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILENAME = os.path.join(LOGS_DIR, f"scan_models_ext_{timestamp}.log")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Handler para fichero de log
fh = logging.FileHandler(LOG_FILENAME)
fh.setLevel(logging.INFO)
fh.setFormatter(fmt)
logger.addHandler(fh)

# Handler para consola (stdout)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(fmt)
logger.addHandler(ch)

# -----------------------------------------------------------------------------
# 3. ESTRUCTURAS DE DATOS PARA RESULTADOS
# -----------------------------------------------------------------------------
models          = set()    # Modelos EXIF únicos
extensions      = set()    # Extensiones de archivo únicas (válidas)
video_no_model  = []       # Vídeos MP4/MTS sin tag EXIF 'Model'
processed_count = 0        # Total de archivos procesados

# Extensiones a omitir completamente
SKIP_EXTENSIONS = {".ffs_db", ".ini"}

# -----------------------------------------------------------------------------
# 4. FUNCIONES AUXILIARES
# -----------------------------------------------------------------------------

def get_exif_model(path):
    """
    Extrae el tag EXIF 'Model' usando exiftool.
    Retorna la cadena del modelo o None si no existe o hay error.
    """
    try:
        res = subprocess.run(
            ["exiftool", "-Model", "-s3", path],
            capture_output=True, text=True
        )
        if res.returncode != 0:
            logger.error(f"exiftool falló en '{path}': {res.stderr.strip()}")
            return None
        model = res.stdout.strip()
        return model if model else None
    except FileNotFoundError:
        logger.critical("exiftool no está instalado o no está en PATH.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error leyendo EXIF de '{path}': {e}")
        return None

def process_file(path):
    """
    Procesa un archivo individual:
      - Registra su extensión (si no está en SKIP_EXTENSIONS).
      - Intenta extraer EXIF 'Model'.
      - Si es vídeo (MP4/MTS) y modelo no encontrado, lo anota.
      - Si modelo hallado, lo agrega a 'models'.
      - Loggea la acción.
    """
    global processed_count
    processed_count += 1

    _, fname = os.path.split(path)
    ext = os.path.splitext(fname)[1].lower()

    # Registrar extensión válida
    extensions.add(ext)

    # Extraer modelo EXIF
    model = get_exif_model(path)
    if model is None and ext in {".mp4", ".mts"}:
        logger.error(f"Vídeo sin tag EXIF 'Model': '{path}'")
        video_no_model.append(path)
    elif model:
        models.add(model)
        logger.info(f"Procesado: '{path}' | Modelo: '{model}' | Extensión: '{ext}'")
    else:
        logger.info(f"Procesado: '{path}' | Sin tag EXIF 'Model' relevante | Extensión: '{ext}'")

# -----------------------------------------------------------------------------
# 5. FASE 1: Archivos en la raíz de CAMERAS_DIR
# -----------------------------------------------------------------------------
logger.info(f"Iniciando escaneo en raíz de '{CAMERAS_DIR}'")
if not os.path.isdir(CAMERAS_DIR):
    logger.critical(f"No existe la carpeta raíz '{CAMERAS_DIR}'")
    sys.exit(1)

for entry in os.listdir(CAMERAS_DIR):
    full = os.path.join(CAMERAS_DIR, entry)
    if not os.path.isfile(full):
        continue
    ext = os.path.splitext(entry)[1].lower()
    if ext in SKIP_EXTENSIONS:
        logger.info(f"Omitido '{full}' (extensión omitida)")
        continue
    process_file(full)

# -----------------------------------------------------------------------------
# 6. FASE 2: Archivos en subcarpetas de modelo (un archivo por extensión)
# -----------------------------------------------------------------------------
for entry in os.listdir(CAMERAS_DIR):
    model_dir = os.path.join(CAMERAS_DIR, entry)
    if not os.path.isdir(model_dir):
        continue

    logger.info(f"Escaneando carpeta de modelo: '{model_dir}'")
    seen_exts = set()
    for root, dirs, files in os.walk(model_dir):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            full = os.path.join(root, fname)
            if ext in SKIP_EXTENSIONS:
                logger.info(f"Omitido '{full}' (extensión omitida)")
                continue
            if ext in seen_exts:
                continue
            seen_exts.add(ext)
            process_file(full)

logger.info("Escaneo completado")

# -----------------------------------------------------------------------------
# 7. GENERACIÓN DE RESUMEN EN TXT
# -----------------------------------------------------------------------------
SUMMARY_TXT = os.path.join(LOGS_DIR, f"resumen_models_ext_{timestamp}.txt")
try:
    with open(SUMMARY_TXT, "w", encoding="utf-8") as out:
        out.write("Modelos EXIF únicos encontrados:\n")
        for m in sorted(models):
            out.write(f"{m}\n")
        out.write("\nExtensiones únicas encontradas:\n")
        for e in sorted(extensions):
            out.write(f"{e}\n")
        if video_no_model:
            out.write("\nEs posible que haya archivos de vídeo sin tag EXIF de modelo.\n")
    logger.info(f"Resumen .txt guardado en '{SUMMARY_TXT}'")
except Exception as e:
    logger.error(f"Error escribiendo resumen '{SUMMARY_TXT}': {e}")

# -----------------------------------------------------------------------------
# 8. GENERACIÓN DE INFORME PDF PROFESIONAL
# -----------------------------------------------------------------------------
def generate_report_pdf():
    """
    Crea un PDF compacto y profesional con:
      - Portada
      - Métricas generales
      - Listado de modelos, extensiones y aviso de vídeos sin tag
    """
    if not (models or extensions or video_no_model):
        logger.info("No hay datos para generar PDF.")
        return

    pdf_path = os.path.join(PDF_DIR, f"models_ext_report_{timestamp}.pdf")
    pdf = FPDF(format='A4', orientation='P', unit='mm')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.set_margins(20, 15, 20)
    pdf.add_page()

    # Portada
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Informe de Modelos y Extensiones", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 6, f"Fecha: {datetime.now():%d-%m-%Y %H:%M:%S}", ln=True, align='C')
    pdf.ln(10)

    # Métricas generales
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "Métricas Generales", ln=True)
    pdf.ln(2)
    pdf.set_font("Arial", "", 11)
    pdf.cell(60, 6, "Archivos procesados:", border=0)
    pdf.cell(0, 6, str(processed_count), ln=True)
    pdf.cell(60, 6, "Modelos únicos:", border=0)
    pdf.cell(0, 6, str(len(models)), ln=True)
    pdf.cell(60, 6, "Extensiones únicas:", border=0)
    pdf.cell(0, 6, str(len(extensions)), ln=True)
    pdf.cell(60, 6, "Vídeos sin EXIF 'Model':", border=0)
    pdf.cell(0, 6, str(len(video_no_model)), ln=True)
    pdf.ln(8)

    # Modelos
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "Modelos EXIF", ln=True)
    pdf.ln(2)
    pdf.set_font("Arial", "", 11)
    for m in sorted(models):
        pdf.multi_cell(0, 6, f"- {m}")
    pdf.ln(5)

    # Extensiones
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "Extensiones de archivo", ln=True)
    pdf.ln(2)
    pdf.set_font("Arial", "", 11)
    for e in sorted(extensions):
        pdf.multi_cell(0, 6, f"- {e}")
    pdf.ln(5)

    # Aviso de vídeos sin tag
    if video_no_model:
        pdf.set_font("Arial", "I", 11)
        pdf.multi_cell(0, 6, "Es posible que haya archivos de vídeo sin tag EXIF de modelo.")
        pdf.ln(5)

    pdf.output(pdf_path)
    logger.info(f"Informe PDF generado: {pdf_path}")

# -----------------------------------------------------------------------------
# 9. PUNTO DE ENTRADA
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    generate_report_pdf()
