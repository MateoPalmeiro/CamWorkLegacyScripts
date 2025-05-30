#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import logging
from datetime import datetime
import sys

# ----------------------------------------------------------------------------
# CONFIGURACIÓN
# ----------------------------------------------------------------------------
CAMERAS_DIR = "CAMARAS"      # Carpeta raíz a recorrer
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Nombre de log con timestamp de ejecución: AAAAMMDD_HHMMSS
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILENAME = os.path.join(LOGS_DIR, f"scan_cam_models_ext_{timestamp}.log")

logging.basicConfig(
    filename=LOG_FILENAME,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Conjuntos para resultados únicos
models = set()
extensions = set()

# ----------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ----------------------------------------------------------------------------

def get_exif_model(path):
    """
    Devuelve el campo 'Model' de EXIF usando exiftool -s3,
    o 'Unknown' si no se encuentra o hay error.
    """
    try:
        res = subprocess.run(
            ["exiftool", "-Model", "-s3", path],
            capture_output=True, text=True
        )
        if res.returncode != 0:
            logging.error(f"exiftool fallo en '{path}': {res.stderr.strip()}")
            return "Unknown"
        model = res.stdout.strip()
        return model if model else "Unknown"
    except FileNotFoundError:
        logging.critical("exiftool no está instalado o no está en el PATH")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error al leer EXIF de '{path}': {e}")
        return "Unknown"

def process_file(path):
    """
    Procesa un único archivo:
      - Extrae y registra la extensión.
      - Extrae y registra el modelo EXIF.
      - Deja registro en el log.
    """
    _, fname = os.path.split(path)
    ext = os.path.splitext(fname)[1].lower()
    extensions.add(ext)
    model = get_exif_model(path)
    models.add(model)
    logging.info(f"Procesado: '{path}' | Modelo: '{model}' | Extensión: '{ext}'")

# ----------------------------------------------------------------------------
# FASE 1: Archivos sueltos en la raíz de CAMERAS_DIR
# ----------------------------------------------------------------------------

logging.info(f"Iniciando escaneo de archivos sueltos en '{CAMERAS_DIR}'")
if not os.path.isdir(CAMERAS_DIR):
    logging.critical(f"No existe la carpeta raíz '{CAMERAS_DIR}'")
    sys.exit(1)

for entry in os.listdir(CAMERAS_DIR):
    path = os.path.join(CAMERAS_DIR, entry)
    if os.path.isfile(path):
        process_file(path)

# ----------------------------------------------------------------------------
# FASE 2: Para cada subcarpeta de modelo, procesar una vez por extensión
# ----------------------------------------------------------------------------

for entry in os.listdir(CAMERAS_DIR):
    model_dir = os.path.join(CAMERAS_DIR, entry)
    if not os.path.isdir(model_dir):
        continue

    logging.info(f"Escaneando carpeta de modelo: '{model_dir}'")
    seen_exts = set()
    for root, dirs, files in os.walk(model_dir):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in seen_exts:
                continue
            seen_exts.add(ext)
            process_file(os.path.join(root, fname))

logging.info("Escaneo completado")

# ----------------------------------------------------------------------------
# GENERAR RESUMEN EN TXT
# ----------------------------------------------------------------------------

SUMMARY_TXT = os.path.join(LOGS_DIR, f"resumen_models_ext_{timestamp}.txt")
try:
    with open(SUMMARY_TXT, "w", encoding="utf-8") as out:
        out.write("Modelos de cámara únicos encontrados:\n")
        for m in sorted(models):
            out.write(f"{m}\n")
        out.write("\nExtensiones únicas encontradas:\n")
        for e in sorted(extensions):
            out.write(f"{e}\n")
    logging.info(f"Resumen guardado en '{SUMMARY_TXT}'")
except Exception as e:
    logging.error(f"No se pudo escribir el resumen '{SUMMARY_TXT}': {e}")
