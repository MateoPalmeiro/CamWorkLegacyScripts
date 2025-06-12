#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Este script recorre recursivamente la carpeta CAMERAS y detecta archivos duplicados
dentro de cada cámara basándose en nombre y hash SHA-256.

Flujos principales:
  - Excluye carpetas PRIVATE y aquellas cuyo nombre contiene "Gopro"
    (evitando bloqueos debidos a tamaños enormes de los archivos).
  - Lista el contenido de cada carpeta válida y guarda un fichero de texto.
  - Identifica duplicados por cámara: mismo nombre de archivo + mismo SHA-256.
  - Genera logs detallados en pantalla y en fichero.
  - Produce un PDF compacto y profesional con métricas generales, tabla resumen
    por cámara y detalle de los duplicados.

Cumple estándares profesionales de documentación (ISO/IEC/IEEE 42010:2011,
ISO/IEC/IEEE 12207:2017, ISO/IEC/IEEE 26514:2018).
"""

# -----------------------------------------------------------------------------
# IMPORTACIONES PRINCIPALES
# -----------------------------------------------------------------------------
import os                     # Operaciones con sistema de archivos
import hashlib                # Cálculo de hashes SHA-256
import logging                # Registro de eventos (logs)
import sys                    # Manejo de salidas críticas
from datetime import datetime # Fecha y hora actual
from fpdf import FPDF         # Generación de documentos PDF

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE LOGS (ISO/IEC/IEEE 42010:2011 - Arquitectura de Sistemas)
# -----------------------------------------------------------------------------
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)  # Crear carpeta de logs si no existe

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
MAIN_LOG        = os.path.join(LOGS_DIR, f"scan_sha256_{ts}.log")
CONTENTS_FILE   = os.path.join(LOGS_DIR, f"folder_contents_{ts}.txt")
DUPLICATES_FILE = os.path.join(LOGS_DIR, f"duplicates_sha256_{ts}.txt")

# Configuración básica del logger de raíz
logger = logging.getLogger()
logger.setLevel(logging.INFO)

fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Handler a fichero
fh = logging.FileHandler(MAIN_LOG)
fh.setLevel(logging.INFO)
fh.setFormatter(fmt)
logger.addHandler(fh)

# Handler a consola (stdout)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(fmt)
logger.addHandler(ch)

# -----------------------------------------------------------------------------
# PARÁMETROS GLOBALES (ISO/IEC/IEEE 12207:2017 - Ciclo de Vida del Software)
# -----------------------------------------------------------------------------
CAMERAS_DIR      = "CAMERAS"  # Carpeta raíz con subcarpetas de cámaras
PHOTO_EXTENSIONS = {           # Extensiones a procesar
    ".arw", ".cr2", ".cr3",
    ".jpg", ".mov", ".mp4", ".mts"
}

# Estructuras para acumular datos
files_by_folder    = {}  # {directorio: [archivo1, archivo2, ...]}
camera_to_names    = {}  # {cámara: {nombre_archivo: [rutas...]}}
duplicates_report  = {}  # {cámara: {archivo: {hash: [rutas...]}}}
cameras_scanned    = []  # Cámaras procesadas
cameras_skipped    = []  # Cámaras omitidas (PRIVATE, Gopro)

# -----------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# -----------------------------------------------------------------------------

def sha256_of_file(path, chunk_size=8192):
    """
    Calcula el hash SHA-256 de un archivo leyendo en bloques.
    Devuelve el hash hexadecimal o None si ocurre error.
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

def seleccionar_camaras():
    """
    Enumera subcarpetas de CAMERAS, excluyendo PRIVATE y aquellas con "Gopro",
    para evitar grandes volúmenes que bloqueen el proceso.
    Retorna lista de cámaras a procesar.
    """
    if not os.path.isdir(CAMERAS_DIR):
        logger.critical(f"No existe la carpeta raíz '{CAMERAS_DIR}'.")
        sys.exit(1)

    all_dirs = sorted(os.listdir(CAMERAS_DIR))
    selected = []
    for d in all_dirs:
        full = os.path.join(CAMERAS_DIR, d)
        if not os.path.isdir(full):
            continue
        # Omitir carpetas privadas y GoPro
        if d == "PRIVATE" or "Gopro" in d:
            logger.info(f"Omitida cámara: {d}")
            cameras_skipped.append(d)
        else:
            selected.append(d)
    return selected

# -----------------------------------------------------------------------------
# FASE 1: LISTADO DE CONTENIDOS POR CARPETA
# -----------------------------------------------------------------------------

def listar_contenidos(cameras):
    """
    Recorre cada cámara válida y lista archivos con extensiones válidas.
    Guarda el listado completo en un fichero de texto.
    """
    logger.info(f"Listando contenidos (omitidas: {cameras_skipped})")
    total = 0

    for cam in cameras:
        cameras_scanned.append(cam)
        cam_path = os.path.join(CAMERAS_DIR, cam)
        # Recorrido recursivo, filtrando PRIVATE y Gopro
        for root, dirs, files in os.walk(cam_path):
            dirs[:] = [d for d in dirs if d != "PRIVATE" and "Gopro" not in d]
            valid = [f for f in files
                     if os.path.splitext(f)[1].lower() in PHOTO_EXTENSIONS]
            if valid:
                files_by_folder[root] = sorted(valid)
                count = len(valid)
                total += count
                logger.info(f"{count} archivos en '{root}'")

    # Escribir listado a fichero
    with open(CONTENTS_FILE, "w", encoding="utf-8") as cf:
        cf.write(f"LISTADO DE CONTENIDOS - {ts}\n\n")
        for folder, fnames in files_by_folder.items():
            cf.write(f"{folder}:\n")
            for f in fnames:
                cf.write(f"  - {f}\n")
            cf.write("\n")
    logger.info(f"Listado guardado en: {CONTENTS_FILE}")
    return total

# -----------------------------------------------------------------------------
# FASE 2: DETECCIÓN DE DUPLICADOS POR SHA-256
# -----------------------------------------------------------------------------

def detectar_duplicados():
    """
    Agrupa rutas por cámara y nombre de archivo, calcula hashes y detecta
    duplicados reales (mismo hash). Guarda informe de texto y almacena
    en duplicates_report para el PDF.
    """
    logger.info("Detectando duplicados (SHA-256)...")

    # Agrupar por cámara y nombre
    for folder, fnames in files_by_folder.items():
        rel = os.path.relpath(folder, CAMERAS_DIR)
        cam = rel.split(os.sep, 1)[0]
        for name in fnames:
            camera_to_names.setdefault(cam, {}).setdefault(name, []).append(
                os.path.join(folder, name)
            )

    # Abrir informe de duplicados
    with open(DUPLICATES_FILE, "w", encoding="utf-8") as df:
        df.write(f"DUPLICADOS SHA-256 - {ts}\n\n")
        # Para cada cámara
        for cam, name_dict in camera_to_names.items():
            for name, paths in name_dict.items():
                if len(paths) < 2:
                    continue  # No hay posible duplicado
                # Calcular hash de cada ruta
                hash_to_paths = {}
                for p in paths:
                    h = sha256_of_file(p)
                    if h:
                        hash_to_paths.setdefault(h, []).append(p)
                # Registrar verdaderos duplicados
                for h, ps in hash_to_paths.items():
                    if len(ps) > 1:
                        duplicates_report.setdefault(cam, {}) \
                                         .setdefault(name, {})[h] = ps
                        df.write(f"CÁMARA: {cam}    ARCHIVO: {name}\n")
                        df.write(f"  SHA-256: {h}\n")
                        for p in ps:
                            df.write(f"    - {p}\n")
                        df.write("\n")
                        logger.warning(f"Duplicado: {cam}/{name} (SHA-256={h})")
        if not duplicates_report:
            df.write("No se encontraron duplicados.\n")
    logger.info(f"Informe duplicados guardado en: {DUPLICATES_FILE}")

# -----------------------------------------------------------------------------
# FASE 3: GENERACIÓN DE INFORME PDF PROFESIONAL
# -----------------------------------------------------------------------------

def generar_reporte_pdf(total_files):
    """
    Crea un PDF con:
      - Portada (título y fecha).
      - Métricas generales.
      - Tabla resumen por cámara.
      - Detalle de duplicados encontrados.
    """
    if not duplicates_report:
        logger.info("No hay duplicados para el PDF.")
        return

    pdf_file = os.path.join(LOGS_DIR, f"dup_report_{ts}.pdf")
    pdf = FPDF(format='A4', orientation='P', unit='mm')
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.set_margins(15, 15, 15)

    # ---- Portada ----
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Informe de Detección de Duplicados", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 6, f"Fecha: {datetime.now():%d-%m-%Y %H:%M:%S}", ln=True, align='C')
    pdf.ln(10)

    # ---- Métricas Generales ----
    total_cameras = len(cameras_scanned)
    total_skipped = len(cameras_skipped)
    total_groups  = sum(len(g) for g in duplicates_report.values())
    total_dups    = sum(len(ps) for cam in duplicates_report.values() for ps in cam.values())

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "Métricas Generales", ln=True)
    pdf.ln(2)
    pdf.set_font("Arial", "", 11)
    pdf.cell(60, 6, "Cámaras escaneadas:", border=0)
    pdf.cell(0, 6, str(total_cameras), ln=True)
    pdf.cell(60, 6, "Archivos procesados:", border=0)
    pdf.cell(0, 6, str(total_files), ln=True)
    pdf.cell(60, 6, "Grupos de duplicados:", border=0)
    pdf.cell(0, 6, str(total_groups), ln=True)
    pdf.cell(60, 6, "Archivos duplicados:", border=0)
    pdf.cell(0, 6, str(total_dups), ln=True)
    pdf.cell(60, 6, "Cámaras omitidas:", border=0)
    pdf.cell(0, 6, ", ".join(cameras_skipped) or "-", ln=True)
    pdf.ln(8)

    # ---- Tabla resumen por cámara ----
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "Resumen por Cámara", ln=True)
    pdf.ln(2)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(50, 7, "Cámara", border=1, align='C')
    pdf.cell(40, 7, "Archivos", border=1, align='C')
    pdf.cell(40, 7, "Grupos dup.", border=1, align='C')
    pdf.cell(40, 7, "Archivos dup.", border=1, align='C')
    pdf.ln()

    pdf.set_font("Arial", "", 11)
    for cam in cameras_scanned:
        scanned = sum(
            len(files_by_folder.get(root, []))
            for root in files_by_folder
            if os.path.relpath(root, CAMERAS_DIR).split(os.sep, 1)[0] == cam
        )
        groups = len(duplicates_report.get(cam, {}))
        dup_files = sum(len(ps) for ps in duplicates_report.get(cam, {}).values())
        pdf.cell(50, 6, cam, border=1)
        pdf.cell(40, 6, str(scanned), border=1, align='C')
        pdf.cell(40, 6, str(groups), border=1, align='C')
        pdf.cell(40, 6, str(dup_files), border=1, align='C')
        pdf.ln()
    pdf.ln(5)

    # ---- Detalle de duplicados ----
    for cam, name_dict in duplicates_report.items():
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 6, f"Cámara: {cam}", ln=True)
        pdf.ln(2)
        pdf.set_font("Arial", "", 10)
        for name, hash_dict in name_dict.items():
            pdf.multi_cell(0, 5, f"Archivo: {name}")
            for h, paths in hash_dict.items():
                pdf.cell(5)
                pdf.multi_cell(0, 5, f"SHA-256: {h}")
                for p in paths:
                    pdf.cell(10)
                    line = p.replace("\\", "/")
                    if len(line) > 70:
                        line = "…" + line[-69:]
                    pdf.multi_cell(0, 5, f"- {line}")
                pdf.ln(1)
        pdf.ln(3)

    pdf.output(pdf_file)
    logger.info(f"PDF generado: {pdf_file}")

# -----------------------------------------------------------------------------
# PUNTO DE ENTRADA
# -----------------------------------------------------------------------------

def main():
    """
    Orquesta el flujo completo:
      1) Selección de cámaras.
      2) Listado de contenidos.
      3) Detección de duplicados.
      4) Generación de informe PDF.
    """
    cams = seleccionar_camaras()
    total = listar_contenidos(cams)
    detectar_duplicados()
    generar_reporte_pdf(total)
    logger.info("Ejecución completada correctamente.")

if __name__ == "__main__":
    main()
