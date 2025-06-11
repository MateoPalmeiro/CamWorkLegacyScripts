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

import os                      # Operaciones con sistema de archivos
import re                      # Expresiones regulares para validación de nombres
import shutil                  # Movimiento y copia de archivos
import logging                 # Registro de eventos (logs)
import subprocess              # Llamadas a exiftool para metadatos
import json                    # Parseo de salida JSON de exiftool
from datetime import datetime, timedelta
from fpdf import FPDF         # Generación de documentos PDF

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE LOGS (ISO/IEC/IEEE 42010:2011 - Arquitectura de Software)
# -----------------------------------------------------------------------------
LOGS_DIR = "logs"  # Carpeta para almacenar logs de ejecución
os.makedirs(LOGS_DIR, exist_ok=True)

today_str    = datetime.now().strftime("%d-%m-%Y")
LOG_FILENAME = os.path.join(LOGS_DIR, f"organizar_por_fecha_{today_str}.log")

logger = logging.getLogger()         # Logger raíz
logger.setLevel(logging.INFO)

# Formato estándar: timestamp - nivel - mensaje
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Handler para fichero de logs
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
# PARÁMETROS GLOBALES (ISO/IEC/IEEE 12207:2017 - Ciclo de Vida del Software)
# -----------------------------------------------------------------------------
CAMERAS_DIR      = "CAMERAS"   # Carpeta raíz que contiene subcarpetas de cámaras
PHOTO_EXTENSIONS = {            # Extensiones de archivos a procesar
    ".arw", ".cr2", ".cr3",
    ".jpg", ".mov", ".mp4", ".mts"
}

# Estructuras de datos para reporte
folders_report = {}  # Estadísticas: fotos movidas, bytes y conteo por extensión
duplicates     = []  # Rutas de archivos detectados como duplicados

# -----------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# -----------------------------------------------------------------------------

def human_readable_size(size_in_bytes):
    """
    Convierte tamaño en bytes a unidad legible (B, KB, MB, GB).
    """
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    if size_in_bytes < 1024**2:
        return f"{size_in_bytes/1024:.2f} KB"
    if size_in_bytes < 1024**3:
        return f"{size_in_bytes/(1024**2):.2f} MB"
    return f"{size_in_bytes/(1024**3):.2f} GB"


def leer_fecha_con_exiftool(filepath):
    """
    Extrae DateTimeOriginal de EXIF usando exiftool.
    Retorna datetime o None si no está disponible o ocurre error.
    """
    try:
        result = subprocess.run(
            ["exiftool", "-j", filepath],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            logger.warning(f"Exiftool falló: {result.stderr.strip()} ({filepath})")
            return None

        data = json.loads(result.stdout or "[]")
        if not isinstance(data, list) or not data:
            return None

        dt_str = data[0].get("DateTimeOriginal")
        if not dt_str:
            return None

        # Quitar fracciones de segundo
        dt_str = dt_str.split(".")[0]
        try:
            return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            logger.warning(f"Formato EXIF inesperado: {dt_str} ({filepath})")
            return None

    except FileNotFoundError:
        logger.error("exiftool no encontrado en PATH.")
        return None
    except Exception as e:
        logger.error(f"Error leyendo EXIF de '{filepath}': {e}")
        return None


def obtener_fecha_captura(filepath):
    """
    Determina la fecha de captura en este orden:
      1) EXIF DateTimeOriginal
      2) Fecha de creación del fichero en sistema (getctime)
      3) Si falla, devuelve None (archivo omitido)
    """
    # 1) Prueba EXIF
    fecha_exif = leer_fecha_con_exiftool(filepath)
    if fecha_exif:
        logger.info(f"[EXIF] {fecha_exif} ← {filepath}")
        return fecha_exif

    # 2) Fallback: fecha de creación del sistema
    try:
        ctime = os.path.getctime(filepath)
        fecha_sistema = datetime.fromtimestamp(ctime)
        logger.info(f"[FS]   {fecha_sistema} ← {filepath}")
        return fecha_sistema
    except Exception as e:
        logger.error(f"No se obtuvo fecha FS: {e} ({filepath})")

    # 3) Indeterminado
    logger.error(f"Fecha indeterminada. Se omite archivo: {filepath}")
    return None


def ajustar_mes_por_horario_especial(fecha):
    """
    Ajusta fechas con día 1 y hora <08:00 al día anterior
    para agrupar eventos nocturnos en el mes correcto.
    """
    if fecha.day == 1 and fecha.hour < 8:
        return fecha - timedelta(days=1)
    return fecha


def generar_nombre_carpeta(fecha):
    """
    Retorna nombre de carpeta destino en formato 'YYYY.MM'.
    """
    return f"{fecha.year}.{fecha.month:02d}"


def es_carpeta_yyyy_mm(nombre):
    """
    Valida si un string sigue el patrón 'YYYY.MM'.
    """
    return re.match(r"^\d{4}\.\d{2}$", nombre) is not None

# -----------------------------------------------------------------------------
# SELECCIÓN DE CÁMARAS A PROCESAR
# -----------------------------------------------------------------------------

def seleccionar_camaras():
    """
    Lista carpetas en CAMERAS (excluye PRIVATE) y permite selección
    por índices separados por coma. Retorna lista de nombres seleccionados.
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
    for i, cam in enumerate(disponibles, start=1):
        print(f"  {i}. {cam}")
    sel = input("Selecciona cámaras (p.ej. '1,2'): ")
    indices = [int(x) for x in sel.split(',') if x.strip().isdigit()]

    seleccionadas = [
        disponibles[i-1]
        for i in indices
        if 1 <= i <= len(disponibles)
    ]
    return seleccionadas

# -----------------------------------------------------------------------------
# ORGANIZACIÓN DE ARCHIVOS POR FECHA
# -----------------------------------------------------------------------------

def organizar_fotos_por_fecha(camaras):
    """
    Para cada cámara seleccionada:
      - Itera archivos multimedia
      - Obtiene fecha de captura fiable
      - Ajusta mes si es horario especial
      - Mueve a subcarpeta 'YYYY.MM'
      - Registra estadísticas y duplicados
    """
    for cam in camaras:
        if cam == "PRIVATE":
            continue
        base = os.path.join(CAMERAS_DIR, cam)
        if not os.path.isdir(base):
            continue

        logger.info(f"Iniciando: {base}")
        for nombre in os.listdir(base):
            origen = os.path.join(base, nombre)
            if os.path.isdir(origen):
                continue

            _, ext = os.path.splitext(nombre)
            if ext.lower() not in PHOTO_EXTENSIONS:
                continue

            # Obtener fecha de captura
            fecha = obtener_fecha_captura(origen)
            if not fecha:
                continue

            fecha = ajustar_mes_por_horario_especial(fecha)
            destino_dir = os.path.join(base, generar_nombre_carpeta(fecha))

            # Crear carpeta destino si no existe
            if not os.path.exists(destino_dir):
                try:
                    os.mkdir(destino_dir)
                    logger.info(f"Carpeta creada: {destino_dir}")
                except OSError as e:
                    logger.error(f"Error creando carpeta: {e}")
                    continue

            destino = os.path.join(destino_dir, nombre)
            if os.path.exists(destino):
                logger.warning(f"Duplicado: {origen}")
                duplicates.append(origen)
                continue

            # Mover archivo
            try:
                size = os.path.getsize(origen)
                shutil.move(origen, destino)
                logger.info(f"Movido: {nombre} → {destino_dir}")

                rpt = folders_report.setdefault(destino_dir, {
                    'created': not os.path.exists(destino_dir),
                    'photos_count': 0,
                    'ext_count': {},
                    'bytes_moved': 0
                })
                rpt['photos_count'] += 1
                rpt['bytes_moved']   += size
                rpt['ext_count'].setdefault(ext.lower(), 0)
                rpt['ext_count'][ext.lower()] += 1

            except (PermissionError, OSError) as e:
                logger.error(f"Error moviendo '{nombre}': {e}")

# -----------------------------------------------------------------------------
# GENERACIÓN DE INFORME PDF COMPACTO
# -----------------------------------------------------------------------------

def generar_resumen_pdf():
    """
    Crea un PDF con:
      - Portada con título y fecha de ejecución
      - Métricas globales
      - Tabla resumen por carpeta
      - Listado de duplicados
    """
    if not folders_report and not duplicates:
        return

    archivo_pdf = os.path.join(PDF_DIR, f"organizar_por_fecha_{today_str}.pdf")
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
    total_photos     = sum(d['photos_count'] for d in folders_report.values())
    total_bytes      = sum(d['bytes_moved']   for d in folders_report.values())
    total_folders    = len(folders_report)
    total_duplicates = len(duplicates)
    cameras_proc     = ", ".join(globals().get('seleccionadas', [])) or "—"

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "Métricas Generales", ln=True)
    pdf.ln(2)
    pdf.set_font("Arial", "", 11)
    pdf.cell(60, 6, "Cámaras:", border=0)
    pdf.cell(0, 6, cameras_proc, ln=True)
    pdf.cell(60, 6, "Carpetas destino:", border=0)
    pdf.cell(0, 6, str(total_folders), ln=True)
    pdf.cell(60, 6, "Fotos movidas:", border=0)
    pdf.cell(0, 6, str(total_photos), ln=True)
    pdf.cell(60, 6, "Tamaño total:", border=0)
    pdf.cell(0, 6, human_readable_size(total_bytes), ln=True)
    pdf.cell(60, 6, "Duplicados:", border=0)
    pdf.cell(0, 6, str(total_duplicates), ln=True)
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
        nombre = folder.replace("\\", "/").split("/")[-1]
        if len(nombre) > 30:
            nombre = "…" + nombre[-29:]
        pdf.cell(80, 6, nombre, border=1)
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
            linea = dup.replace("\\", "/")
            if len(linea) > 70:
                linea = "…" + linea[-69:]
            pdf.multi_cell(0, 5, f"• {linea}")
        pdf.ln(3)

    pdf.output(archivo_pdf)
    logger.info(f"PDF generado: {archivo_pdf}")

# -----------------------------------------------------------------------------
# PUNTO DE ENTRADA
# -----------------------------------------------------------------------------

def main():
    """
    Orquesta todo el flujo:
      1) Selección de cámaras
      2) Organización de archivos por fecha
      3) Generación de informe PDF
    """
    try:
        selec = seleccionar_camaras()
        if not selec:
            print("No se seleccionaron cámaras. Terminando.")
            return
        globals()['seleccionadas'] = selec

        organizar_fotos_por_fecha(selec)
        generar_resumen_pdf()
        logger.info("Ejecución completada con éxito.")
    except Exception as e:
        logger.error(f"Error inesperado en main(): {e}")


if __name__ == "__main__":
    main()
