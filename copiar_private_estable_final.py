#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Este script recorre recursivamente la carpeta CAMERAS y copia todas las subcarpetas
cuyo nombre contiene "(X)" dentro de una carpeta destino llamada PRIVATE,
creando logs detallados de cada acción y mostrando también el progreso por pantalla.
Además genera un informe PDF con métricas y detalles de la ejecución.
Está diseñado para ser mantenible y cumplir con estándares profesionales de documentación (ISO/IEEE).
"""

import os        # Operaciones con el sistema de archivos
import shutil    # Copia de árboles de directorios
import logging   # Generación de registros de eventos (logs)
from datetime import datetime  # Fecha y hora actual
from fpdf import FPDF          # Generación de documentos PDF

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE LOGS (ISO/IEC/IEEE 42010:2011 - Arquitectura de Sistemas)
# -----------------------------------------------------------------------------
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)
today_str = datetime.now().strftime("%d-%m-%Y")
LOG_FILENAME = os.path.join(LOGS_DIR, f"copy_private_{today_str}.log")

logger = logging.getLogger()
logger.setLevel(logging.INFO)
t_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

fh = logging.FileHandler(LOG_FILENAME)
fh.setLevel(logging.INFO)
fh.setFormatter(t_formatter)
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(t_formatter)
logger.addHandler(ch)

# -----------------------------------------------------------------------------
# PARÁMETROS GLOBALES (ISO/IEC/IEEE 12207:2017 - Ciclo de vida de software)
# -----------------------------------------------------------------------------
CAMERAS_DIR   = "CAMARAS"        # Carpeta raíz con todas las cámaras
DEST_DIR_NAME = "PRIVATE"        # Nombre de la subcarpeta destino
DEST_DIR      = os.path.join(CAMERAS_DIR, DEST_DIR_NAME)  # Ruta completa destino

# Estadísticas para el informe
report_data   = []   # Lista de (rel_path, status, bytes)
copied_count  = 0
skipped_count = 0
error_count   = 0
total_bytes   = 0

def human_readable(size):
    """Convierte bytes a B, KB, MB o GB con dos decimales."""
    if size < 1024:
        return f"{size} B"
    if size < 1024**2:
        return f"{size/1024:.2f} KB"
    if size < 1024**3:
        return f"{size/(1024**2):.2f} MB"
    return f"{size/(1024**3):.2f} GB"

# -----------------------------------------------------------------------------
# CREACIÓN DE LA CARPETA DESTINO
# -----------------------------------------------------------------------------
if not os.path.exists(DEST_DIR):
    os.makedirs(DEST_DIR)
    logger.info(f"Se creó la carpeta destino: {DEST_DIR}")
else:
    logger.info(f"La carpeta destino ya existe: {DEST_DIR}")

# -----------------------------------------------------------------------------
# RECORRIDO RECURSIVO Y COPIA DE DIRECTORIOS CANDIDATOS
# -----------------------------------------------------------------------------
for dirpath, dirnames, filenames in os.walk(CAMERAS_DIR, topdown=True):
    # 1. Excluir la carpeta PRIVATE del recorrido (evitar bucles)
    dirnames[:] = [d for d in dirnames if d != DEST_DIR_NAME]

    # 2. Determinar si la carpeta actual es candidata: su nombre contiene "(X)"
    current_basename = os.path.basename(dirpath)
    if "(X)" in current_basename:
        # 2.1 Ruta relativa desde CAMERAS_DIR para mantener jerarquía
        rel_path = os.path.relpath(dirpath, CAMERAS_DIR)
        # 2.2 Ruta destino dentro de PRIVATE
        dest_path = os.path.join(DEST_DIR, rel_path)

        # 3. Verificar existencia previa para evitar sobrescritura
        if os.path.exists(dest_path):
            logger.info(f"El destino ya existe, se omite: {dest_path}")
            report_data.append((rel_path, 'skipped', 0))
            skipped_count += 1
        else:
            # calcular tamaño de la carpeta a copiar
            dir_size = 0
            for r, _, files in os.walk(dirpath):
                for f in files:
                    try:
                        dir_size += os.path.getsize(os.path.join(r, f))
                    except OSError:
                        pass
            try:
                # 4. Copia recursiva completa del árbol de directorios
                shutil.copytree(dirpath, dest_path)
                logger.info(f"Se copió '{dirpath}' a '{dest_path}' ({human_readable(dir_size)})")
                report_data.append((rel_path, 'copied', dir_size))
                copied_count  += 1
                total_bytes   += dir_size
            except Exception as e:
                # 5. En caso de error, registrar con nivel ERROR
                logger.error(f"Error al copiar '{dirpath}' a '{dest_path}': {e}")
                report_data.append((rel_path, 'error', 0))
                error_count += 1

# -----------------------------------------------------------------------------
# GENERACIÓN DE INFORME PDF (ISO/IEC/IEEE 26514:2018 - Documentación de software)
# -----------------------------------------------------------------------------
def generar_reporte_pdf():
    """
    Crea un PDF compacto con:
      - Portada con título y fecha.
      - Métricas generales.
      - Tabla resumen por carpeta (estado y bytes movidos).
    """
    if not report_data:
        logger.info("No hay datos para generar el PDF.")
        return

    pdf_path = os.path.join(PDF_DIR, f"copy_private_report_{today_str}.pdf")
    pdf = FPDF(format='A4', orientation='P', unit='mm')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.set_margins(15, 15, 15)

    # -- Portada --
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Informe de Copia de Carpetas PRIVATE", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 6, f"Fecha: {datetime.now():%d-%m-%Y %H:%M:%S}", ln=True, align='C')
    pdf.ln(10)

    # -- Métricas generales --
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "Métricas Generales", ln=True)
    pdf.ln(2)
    pdf.set_font("Arial", "", 11)
    pdf.cell(60, 6, "Carpetas copiadas:", border=0)
    pdf.cell(0, 6, str(copied_count), ln=True)
    pdf.cell(60, 6, "Carpetas omitidas:", border=0)
    pdf.cell(0, 6, str(skipped_count), ln=True)
    pdf.cell(60, 6, "Errores de copia:", border=0)
    pdf.cell(0, 6, str(error_count), ln=True)
    pdf.cell(60, 6, "Tamaño total copiado:", border=0)
    pdf.cell(0, 6, human_readable(total_bytes), ln=True)
    pdf.ln(8)

    # -- Tabla resumen por carpeta --
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "Resumen por Carpeta", ln=True)
    pdf.ln(2)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(80, 7, "Carpeta", border=1, align='C')
    pdf.cell(40, 7, "Estado", border=1, align='C')
    pdf.cell(40, 7, "Bytes",  border=1, align='R')
    pdf.ln()

    pdf.set_font("Arial", "", 11)
    for rel, status, b in report_data:
        name = rel if len(rel) <= 40 else "…" + rel[-39:]
        pdf.cell(80, 6, name, border=1)
        pdf.cell(40, 6, status, border=1, align='C')
        pdf.cell(40, 6, human_readable(b), border=1, align='R')
        pdf.ln()

    pdf.output(pdf_path)
    logger.info(f"Informe PDF generado: {pdf_path}")

# -----------------------------------------------------------------------------
# EJECUCIÓN DEL INFORME
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    generar_reporte_pdf()
