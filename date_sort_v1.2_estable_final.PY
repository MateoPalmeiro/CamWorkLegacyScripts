#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Este script organiza archivos multimedia de cámaras por fecha de captura y
genera un informe PDF compacto, profesional y fácil de leer.

Flujos principales:
  - Extrae DateTimeOriginal de EXIF como fecha principal.
  - Usa fecha de creación del sistema si EXIF no está disponible.
  - Omite archivos sin fecha fiable y los registra como errores.
  - Mueve cada archivo a subcarpeta YYYY.MM dentro de su carpeta de cámara.
  - Crea un PDF con métricas globales, tabla de resultados y lista de duplicados.

Cumple estándares de documentación ISO/IEC/IEEE para facilitar mantenimiento
y comprensión a futuro.
"""

# -----------------------------------------------------------------------------
# IMPORTACIONES PRINCIPALES
# -----------------------------------------------------------------------------
import os                      # Operaciones con sistema de archivos
import re                      # Validación de patrones de nombre
import shutil                  # Movimiento de archivos
import logging                 # Registro de eventos (logs)
import subprocess              # Llamadas a exiftool para metadatos
import json                    # Parseo de JSON devuelto por exiftool
from datetime import datetime, timedelta  # Fecha y hora
from fpdf import FPDF         # Generación de documentos PDF

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE LOGS (ISO/IEC/IEEE 42010:2011 - Arquitectura de Sistemas)
# -----------------------------------------------------------------------------
LOGS_DIR = "logs"  # Carpeta para logs
os.makedirs(LOGS_DIR, exist_ok=True)

today_str    = datetime.now().strftime("%d-%m-%Y")
LOG_FILENAME = os.path.join(LOGS_DIR, f"organizar_por_fecha_{today_str}.log")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

fh = logging.FileHandler(LOG_FILENAME)
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

# -----------------------------------------------------------------------------
# PARÁMETROS GLOBALES (ISO/IEC/IEEE 12207:2017 - Ciclo de Vida del Software)
# -----------------------------------------------------------------------------
CAMERAS_DIR      = "CAMERAS"   # Carpeta raíz con subcarpetas de cámaras
PDF_DIR          = "pdf"       # Carpeta donde se guardará el informe PDF
PHOTO_EXTENSIONS = {            # Extensiones válidas a procesar
    ".arw", ".cr2", ".cr3",
    ".jpg", ".mov", ".mp4", ".mts"
}

os.makedirs(PDF_DIR, exist_ok=True)

# Estructuras de datos para el informe
folders_report = {}  # {dest_folder: {'photos_count', 'bytes_moved', 'ext_count'}}
duplicates     = []  # Lista de rutas duplicadas detectadas

# -----------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# -----------------------------------------------------------------------------

def human_readable_size(size_in_bytes):
    """
    Convierte un tamaño en bytes a una cadena legible (B, KB, MB, GB).
    """
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    if size_in_bytes < 1024**2:
        return f"{size_in_bytes/1024:.2f} KB"
    if size_in_bytes < 1024**3:
        return f"{size_in_bytes/(1024**2):.2f} MB"
    return f"{size_in_bytes/(1024**3):.2f} GB"

# -----------------------------------------------------------------------------
# EXTRACCIÓN DE FECHA CON EXIFTOOL
# -----------------------------------------------------------------------------

def leer_fecha_con_exiftool(filepath):
    """
    Extrae DateTimeOriginal de EXIF usando exiftool -j.
    Devuelve datetime o None si no está presente o ocurre un error.
    """
    try:
        result = subprocess.run(
            ["exiftool", "-j", filepath],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            logger.warning(f"[EXIFTOOL] fallo: {result.stderr.strip()} ({filepath})")
            return None

        data = json.loads(result.stdout or "[]")
        if not data or "DateTimeOriginal" not in data[0]:
            return None

        dt_str = data[0]["DateTimeOriginal"].split(".")[0]
        try:
            return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            logger.warning(f"[EXIF] formato inesperado: {dt_str} ({filepath})")
            return None

    except FileNotFoundError:
        logger.error("exiftool no encontrado en PATH.")
        return None
    except Exception as e:
        logger.error(f"Error leyendo EXIF de '{filepath}': {e}")
        return None

# -----------------------------------------------------------------------------
# DETERMINACIÓN DE FECHA DE CAPTURA
# -----------------------------------------------------------------------------

def obtener_fecha_captura(filepath):
    """
    Determina la fecha de captura en orden:
      1. EXIF DateTimeOriginal.
      2. Fecha de creación del fichero (getctime).
      3. None si no se puede obtener fecha.
    Registra INFO/WARNING/ERROR según el origen de la fecha.
    """
    fecha_exif = leer_fecha_con_exiftool(filepath)
    if fecha_exif:
        logger.info(f"[EXIF] {fecha_exif} ← {filepath}")
        return fecha_exif

    try:
        ctime = os.path.getctime(filepath)
        fecha_fs = datetime.fromtimestamp(ctime)
        logger.info(f"[FS]   {fecha_fs} ← {filepath}")
        return fecha_fs
    except Exception as e:
        logger.error(f"[FS] error: {e} ({filepath})")

    logger.error(f"Fecha indeterminada; archivo omitido: {filepath}")
    return None

# -----------------------------------------------------------------------------
# AJUSTE DE MES PARA HORARIOS ESPECIALES
# -----------------------------------------------------------------------------

def ajustar_mes_por_horario_especial(fecha):
    """
    Ajusta fechas del día 1 con hora <08:00 al día anterior,
    para agrupar eventos nocturnos al mes adecuado.
    """
    if fecha.day == 1 and fecha.hour < 8:
        return fecha - timedelta(days=1)
    return fecha

# -----------------------------------------------------------------------------
# GENERACIÓN DE NOMBRE DE CARPETA DESTINO
# -----------------------------------------------------------------------------

def generar_nombre_carpeta(fecha):
    """
    Construye el nombre de la carpeta destino en formato 'YYYY.MM'.
    """
    return f"{fecha.year}.{fecha.month:02d}"

# -----------------------------------------------------------------------------
# FUNCIÓN DE SELECCIÓN DE CÁMARAS
# -----------------------------------------------------------------------------

def seleccionar_camaras():
    """
    Muestra las subcarpetas de CAMERAS (excluye PRIVATE),
    permite selección por índices y devuelve la lista seleccionada.
    """
    if not os.path.isdir(CAMERAS_DIR):
        print(f"ERROR: '{CAMERAS_DIR}' no existe.")
        return []

    disponibles = sorted(
        d for d in os.listdir(CAMERAS_DIR)
        if os.path.isdir(os.path.join(CAMERAS_DIR, d)) and d != "PRIVATE"
    )
    if not disponibles:
        print("No hay carpetas de cámara.")
        return []

    print("Cámaras disponibles:")
    for i, cam in enumerate(disponibles, 1):
        print(f"  {i}. {cam}")
    sel = input("Selecciona cámaras (p.ej. '1,2'): ")
    indices = [int(x) for x in sel.split(',') if x.strip().isdigit()]

    return [disponibles[i-1] for i in indices if 1 <= i <= len(disponibles)]

# -----------------------------------------------------------------------------
# ORGANIZACIÓN DE ARCHIVOS POR FECHA
# -----------------------------------------------------------------------------

def organizar_fotos_por_fecha(camaras):
    """
    Para cada cámara:
      - Recorre archivos multimedia.
      - Obtiene fecha de captura fiable.
      - Ajusta mes si aplica horario especial.
      - Crea carpeta destino YYYY.MM.
      - Mueve archivo y actualiza folders_report.
      - Detecta duplicados y los registra.
    """
    for cam in camaras:
        base = os.path.join(CAMERAS_DIR, cam)
        logger.info(f"[INICIO] {base}")

        for nombre in os.listdir(base):
            origen = os.path.join(base, nombre)
            if os.path.isdir(origen):
                continue
            _, ext = os.path.splitext(nombre)
            if ext.lower() not in PHOTO_EXTENSIONS:
                continue

            fecha = obtener_fecha_captura(origen)
            if not fecha:
                continue

            fecha = ajustar_mes_por_horario_especial(fecha)
            carpeta_fecha = generar_nombre_carpeta(fecha)
            destino_dir = os.path.join(base, carpeta_fecha)

            if not os.path.exists(destino_dir):
                try:
                    os.mkdir(destino_dir)
                    logger.info(f"[MKDIR] Creada carpeta: {destino_dir}")
                except OSError as e:
                    logger.error(f"[ERROR] creando carpeta: {e}")
                    continue

            destino = os.path.join(destino_dir, nombre)
            if os.path.exists(destino):
                logger.warning(f"[DUP] {origen}")
                duplicates.append(origen)
                continue

            try:
                size = os.path.getsize(origen)
                shutil.move(origen, destino)
                logger.info(f"[MOVE] {nombre} → {carpeta_fecha}")

                rpt = folders_report.setdefault(destino_dir, {
                    'photos_count': 0,
                    'bytes_moved': 0,
                    'ext_count': {}
                })
                rpt['photos_count'] += 1
                rpt['bytes_moved']   += size
                rpt['ext_count'].setdefault(ext.lower(), 0)
                rpt['ext_count'][ext.lower()] += 1

            except (PermissionError, OSError) as e:
                logger.error(f"[ERROR] moviendo '{nombre}': {e}")

# -----------------------------------------------------------------------------
# GENERACIÓN DE INFORME PDF (ISO/IEC/IEEE 26514:2018 - Documentación de software)
# -----------------------------------------------------------------------------

def generar_resumen_pdf():
    """
    Crea un PDF compacto con:
      - Portada (título y fecha).
      - Métricas globales.
      - Tabla resumen por carpeta.
      - Lista de duplicados.
    """
    if not folders_report and not duplicates:
        logger.info("Sin datos para PDF.")
        return

    pdf_file = os.path.join(PDF_DIR, f"organizar_por_fecha_{today_str}.pdf")
    pdf = FPDF(format='A4', orientation='P', unit='mm')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.set_margins(15, 15, 15)

    # Portada
    pdf.add_page()
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 10, "Informe de Organización de Fotos", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 6, f"Fecha: {datetime.now():%d-%m-%Y %H:%M:%S}", ln=True, align='C')
    pdf.ln(10)

    # Métricas generales
    total_photos      = sum(d['photos_count'] for d in folders_report.values())
    total_bytes_moved = sum(d['bytes_moved']   for d in folders_report.values())
    total_folders     = len(folders_report)
    total_dups        = len(duplicates)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "Métricas Generales", ln=True)
    pdf.ln(2)
    pdf.set_font("Arial", "", 11)
    pdf.cell(60, 6, "Carpetas destino:", border=0)
    pdf.cell(0, 6, str(total_folders), ln=True)
    pdf.cell(60, 6, "Fotos movidas:", border=0)
    pdf.cell(0, 6, str(total_photos), ln=True)
    pdf.cell(60, 6, "Tamaño total:", border=0)
    pdf.cell(0, 6, human_readable_size(total_bytes_moved), ln=True)
    pdf.cell(60, 6, "Duplicados:", border=0)
    pdf.cell(0, 6, str(total_dups), ln=True)
    pdf.ln(8)

    # Tabla resumen
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "Resumen por Carpeta", ln=True)
    pdf.ln(2)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(80, 7, "Carpeta", border=1, align='C')
    pdf.cell(40, 7, "Fotos",  border=1, align='C')
    pdf.cell(40, 7, "Tamaño", border=1, align='C')
    pdf.ln()

    pdf.set_font("Arial", "", 11)
    for folder, data in folders_report.items():
        name = os.path.basename(folder)
        if len(name) > 30:
            name = "…" + name[-29:]
        pdf.cell(80, 6, name, border=1)
        pdf.cell(40, 6, str(data['photos_count']), border=1, align='C')
        pdf.cell(40, 6, human_readable_size(data['bytes_moved']), border=1, align='R')
        pdf.ln()
    pdf.ln(5)

    # Duplicados
    if duplicates:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 6, "Duplicados (no movidos)", ln=True)
        pdf.ln(2)
        pdf.set_font("Arial", "", 10)
        for dup in duplicates:
            line = dup.replace("\\", "/")
            if len(line) > 70:
                line = "…" + line[-69:]
            pdf.multi_cell(0, 5, f"• {line}")
        pdf.ln(3)

    pdf.output(pdf_file)
    logger.info(f"PDF generado: {pdf_file}")

# -----------------------------------------------------------------------------
# EJECUCIÓN PRINCIPAL
# -----------------------------------------------------------------------------

def main():
    """
    Orquesta el flujo completo:
      1) Selección de cámaras.
      2) Organización de archivos por fecha.
      3) Generación del informe PDF.
    """
    cameras = seleccionar_camaras()
    if not cameras:
        print("No se seleccionaron cámaras. Saliendo.")
        return

    organizar_fotos_por_fecha(cameras)
    generar_resumen_pdf()
    logger.info("Ejecución completada correctamente.")

if __name__ == "__main__":
    main()
