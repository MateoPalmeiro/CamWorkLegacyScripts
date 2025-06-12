#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Este script organiza archivos RAW (.cr2, .cr3, .arw) en subcarpeta 'RAW' dentro de
cada carpeta temática de CAMERAS, detecta duplicados por hash SHA-256, imprime
en consola el mismo contenido que guarda en log, y genera un informe PDF
compacto y profesional.

Cumple estándares profesionales de documentación (ISO/IEC/IEEE).
"""

# -----------------------------------------------------------------------------
# IMPORTACIONES PRINCIPALES
# -----------------------------------------------------------------------------
import os                      # Operaciones con sistema de archivos
import shutil                  # Movimiento de archivos y directorios
import logging                 # Registro de eventos
import hashlib                 # Cálculo de hashes SHA-256
from datetime import datetime  # Fecha y hora actual
from fpdf import FPDF          # Generación de documentos PDF

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE DIRECTORIOS DE SALIDA
# -----------------------------------------------------------------------------
LOGS_DIR     = "logs"      # Carpeta para archivos de log
PDF_DIR      = "pdf"       # Carpeta para informes PDF
METADATA_DIR = "metadata"  # Carpeta para posibles metadatos

# Asegura existencia de carpetas sin lanzar excepción si ya existen
os.makedirs(LOGS_DIR,     exist_ok=True)
os.makedirs(PDF_DIR,      exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# 2. CONFIGURACIÓN DE LOGGING (ISO/IEC/IEEE 42010:2011 - Arquitectura de Sistemas)
# -----------------------------------------------------------------------------
today_str    = datetime.now().strftime("%d-%m-%Y")
LOG_FILENAME = os.path.join(LOGS_DIR, f"organizar_raw_{today_str}.log")

# Logger raíz con nivel INFO
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Formato uniforme para fichero y consola
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Handler para fichero de log
fh = logging.FileHandler(LOG_FILENAME)
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)
logger.addHandler(fh)

# Handler para consola (stdout)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

# -----------------------------------------------------------------------------
# 3. PARÁMETROS GLOBALES (ISO/IEC/IEEE 12207:2017 - Ciclo de Vida del Software)
# -----------------------------------------------------------------------------
CAMERAS_DIR    = "CAMERAS"                 # Carpeta raíz con cámaras
RAW_EXTENSIONS = {".cr2", ".cr3", ".arw"}   # Extensiones RAW a procesar

# Estructuras para estadísticas y duplicados
folders_report = {}   # {ruta_RAW: {'created':bool, 'files':int, 'ext':{}, 'bytes':int}}
duplicates     = []   # Rutas de archivos duplicados detectados

# -----------------------------------------------------------------------------
# 4. FUNCIONES AUXILIARES
# -----------------------------------------------------------------------------

def human_readable_size(size):
    """
    Convierte tamaño en bytes a B, KB, MB o GB con dos decimales.
    """
    if size < 1024:
        return f"{size} B"
    if size < 1024**2:
        return f"{size/1024:.2f} KB"
    if size < 1024**3:
        return f"{size/(1024**2):.2f} MB"
    return f"{size/(1024**3):.2f} GB"

def sha256_of_file(path, chunk_size=8192):
    """
    Calcula SHA-256 de un archivo en bloques.
    Devuelve hash hexadecimal o None si ocurre error.
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
    Comprueba duplicados bit a bit (SHA-256) comparando src_path contra
    todos los archivos en dest_folder y subcarpetas.
    """
    src_hash = sha256_of_file(src_path)
    if src_hash is None:
        # No podemos calcular hash; prevenimos pérdida omitiendo el movimiento
        logger.error(f"No se pudo calcular hash de '{src_path}'; queda sin mover")
        duplicates.append(src_path)
        return True

    for root, _, files in os.walk(dest_folder):
        for fname in files:
            if sha256_of_file(os.path.join(root, fname)) == src_hash:
                return True
    return False

def seleccionar_camaras():
    """
    Lista carpetas en CAMERAS_DIR y solicita selección por índices.
    Retorna lista de nombres seleccionados.
    """
    if not os.path.isdir(CAMERAS_DIR):
        logger.critical(f"No existe la carpeta '{CAMERAS_DIR}'.")
        return []

    cams = sorted(d for d in os.listdir(CAMERAS_DIR)
                  if os.path.isdir(os.path.join(CAMERAS_DIR, d)))
    if not cams:
        logger.info("No hay subcarpetas en CAMERAS.")
        return []

    # Mostrar opciones
    print("Cámaras disponibles:")
    for i, cam in enumerate(cams, 1):
        print(f"  {i}. {cam}")
    sel = input("Selecciona cámaras (e.g. '1,3,5'): ")
    indices = [int(x) for x in sel.split(',') if x.strip().isdigit()]
    return [cams[i-1] for i in indices if 1 <= i <= len(cams)]

# -----------------------------------------------------------------------------
# 5. PROCESAMIENTO DE DIRECTORIOS TEMÁTICOS
# -----------------------------------------------------------------------------

def procesar_directorio(directorio):
    """
    Mueve archivos RAW en 'directorio' a subcarpeta 'RAW',
    detecta duplicados por SHA-256 y actualiza folders_report.
    """
    # Listado de RAW en el directorio
    raw_files = [f for f in os.listdir(directorio)
                 if os.path.isfile(os.path.join(directorio, f))
                 and os.path.splitext(f)[1].lower() in RAW_EXTENSIONS]
    if not raw_files:
        logger.info(f"No hay RAW en {directorio}.")
        return

    # Crear subcarpeta RAW si no existe
    raw_dir = os.path.join(directorio, "RAW")
    created = False
    if not os.path.exists(raw_dir):
        try:
            os.makedirs(raw_dir)
            created = True
            logger.info(f"Creada carpeta RAW en {directorio}")
        except Exception as e:
            logger.error(f"Error creando {raw_dir}: {e}")
            return

    # Mover cada archivo RAW
    for rf in raw_files:
        src = os.path.join(directorio, rf)
        dst = os.path.join(raw_dir, rf)
        size = os.path.getsize(src)

        # Detección de duplicado
        if is_duplicate(raw_dir, src):
            logger.warning(f"Duplicado RAW no movido: {src}")
            continue

        try:
            shutil.move(src, dst)
            logger.info(f"Movido RAW '{rf}' → {raw_dir}")

            # Actualizar estadísticas
            rpt = folders_report.setdefault(raw_dir, {
                'created': created,
                'files': 0,
                'ext': {},
                'bytes': 0
            })
            if created:
                rpt['created'] = True
            rpt['files'] += 1
            rpt['bytes'] += size
            ext = os.path.splitext(rf)[1].lower()
            rpt['ext'][ext] = rpt['ext'].get(ext, 0) + 1

        except Exception as e:
            logger.error(f"Error moviendo '{rf}': {e}")

def organizar_raw_en_subcarpeta(camaras):
    """
    Recorre cada cámara y subdirectorios temáticos/subtemáticos,
    aplicando 'procesar_directorio' en cada uno.
    """
    for cam in camaras:
        cam_path = os.path.join(CAMERAS_DIR, cam)
        logger.info(f"Procesando cámara: {cam_path}")
        # Primer nivel: carpetas mensuales o temáticas
        for month in os.listdir(cam_path):
            month_path = os.path.join(cam_path, month)
            if not os.path.isdir(month_path):
                continue
            themes = [d for d in os.listdir(month_path)
                      if os.path.isdir(os.path.join(month_path, d))]
            if not themes:
                logger.info(f"No hay carpetas temáticas en {month_path}")
                continue
            # Procesar cada carpeta temática
            for theme in themes:
                theme_path = os.path.join(month_path, theme)
                procesar_directorio(theme_path)
                # Procesar subtemáticas (excluyendo RAW)
                subs = [d for d in os.listdir(theme_path)
                        if os.path.isdir(os.path.join(theme_path, d))
                        and d.lower() != "raw"]
                for sub in subs:
                    procesar_directorio(os.path.join(theme_path, sub))

# -----------------------------------------------------------------------------
# 6. RESÚMENES: TXT Y PDF
# -----------------------------------------------------------------------------

def generar_resumen_txt():
    """
    Escribe en el log un resumen detallado de la ejecución:
      - Estadísticas por subcarpeta RAW.
      - Carpeta nuevas vs existentes.
      - Total movido.
    """
    logger.info("=== RESUMEN FINAL ===")
    if not folders_report:
        logger.info("No se movió ningún RAW.")
        return

    total_bytes = 0
    created = []
    existed = []

    for folder, data in folders_report.items():
        total_bytes += data['bytes']
        (created if data['created'] else existed).append(folder)
        logger.info(f"Carpeta: {folder} ({'nueva' if data['created'] else 'existente'})")
        logger.info(f"  Archivos: {data['files']}")
        for ext, cnt in data['ext'].items():
            logger.info(f"    {ext}: {cnt}")
        logger.info(f"  Bytes movidos: {human_readable_size(data['bytes'])}")

    logger.info(f"Subcarpetas RAW nuevas: {len(created)}")
    for c in created:
        logger.info(f"  - {c}")
    logger.info(f"Subcarpetas RAW existentes: {len(existed)}")
    for e in existed:
        logger.info(f"  - {e}")
    logger.info(f"Total movido: {human_readable_size(total_bytes)}")

def generar_resumen_pdf():
    """
    Genera un PDF profesional con:
      - Portada.
      - Detalle por subcarpeta RAW.
      - Resumen global.
    """
    if not folders_report:
        return

    pdf_path = os.path.join(PDF_DIR, f"organizar_raw_{today_str}.pdf")
    pdf = FPDF(format='A4', orientation='P', unit='mm')
    pdf.set_auto_page_break(True, 10)
    pdf.set_margins(20, 15, 20)
    pdf.add_page()

    # Portada
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Resumen de Organización RAW", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 6, f"Fecha: {datetime.now():%d-%m-%Y %H:%M:%S}", ln=True)
    pdf.ln(8)

    # Detalles por carpeta
    for folder, data in folders_report.items():
        pdf.set_font("Arial", "B", 12)
        pdf.multi_cell(0, 6, f"Carpeta: {folder}")
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 6, f"- Estado: {'nueva' if data['created'] else 'existente'}")
        pdf.multi_cell(0, 6, f"- Archivos: {data['files']}")
        for ext, cnt in data['ext'].items():
            pdf.multi_cell(0, 6, f"  {ext}: {cnt}")
        pdf.multi_cell(0, 6, f"- Bytes movidos: {human_readable_size(data['bytes'])}")
        pdf.ln(4)

    # Resumen global
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "Resumen Global:", ln=True)
    pdf.set_font("Arial", "", 11)
    total_bytes = sum(d['bytes'] for d in folders_report.values())
    pdf.multi_cell(0, 6, f"Total movido: {human_readable_size(total_bytes)}")
    pdf.multi_cell(0, 6, f"Subcarpetas nuevas: {sum(1 for d in folders_report if folders_report[d]['created'])}")
    pdf.multi_cell(0, 6, f"Subcarpetas existentes: {sum(1 for d in folders_report if not folders_report[d]['created'])}")

    pdf.output(pdf_path)
    logger.info(f"PDF generado: {pdf_path}")

# -----------------------------------------------------------------------------
# 7. EJECUCIÓN PRINCIPAL
# -----------------------------------------------------------------------------

def main():
    """
    Orquesta el flujo completo:
      1) Selección de cámaras.
      2) Organización de RAW en subcarpeta.
      3) Generación de resúmenes TXT y PDF.
    """
    try:
        cams = seleccionar_camaras()
        if not cams:
            print("No se seleccionaron cámaras. Saliendo.")
            return
        organizar_raw_en_subcarpeta(cams)
        generar_resumen_txt()
        generar_resumen_pdf()
        logger.info("Proceso de organización RAW finalizado.")
    except Exception as e:
        logger.error(f"Error inesperado: {e}")

if __name__ == "__main__":
    main()
