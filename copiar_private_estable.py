#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import logging
from datetime import datetime

# ----------------------------------------------------------------------------
# CONFIGURACIÓN DE LOG
# ----------------------------------------------------------------------------
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)
today_str = datetime.now().strftime("%d-%m-%Y")
LOG_FILENAME = os.path.join(LOGS_DIR, f"copy_private_{today_str}.log")
logging.basicConfig(
    filename=LOG_FILENAME,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ----------------------------------------------------------------------------
# PARÁMETROS GLOBALES
# ----------------------------------------------------------------------------
CAMERAS_DIR = "CAMARAS"
DEST_DIR_NAME = "PRIVATE"
DEST_DIR = os.path.join(CAMERAS_DIR, DEST_DIR_NAME)

# Crear la carpeta PRIVATE en CAMERAS si no existe (sin sobreescribirla si ya existe)
if not os.path.exists(DEST_DIR):
    os.makedirs(DEST_DIR)
    logging.info(f"Se creó la carpeta destino: {DEST_DIR}")
else:
    logging.info(f"La carpeta destino ya existe: {DEST_DIR}")

# ----------------------------------------------------------------------------
# RECORRER CAMERAS Y COPIAR CARPETAS CANDIDATAS
# ----------------------------------------------------------------------------

# Recorremos CAMERAS de forma recursiva; usamos topdown=True para poder modificar la lista de subdirectorios
for dirpath, dirnames, filenames in os.walk(CAMERAS_DIR, topdown=True):
    # Ignorar la carpeta PRIVATE en la búsqueda (evitar descender en ella)
    dirnames[:] = [d for d in dirnames if d != DEST_DIR_NAME]

    # Comprobar si el directorio actual es candidato: su nombre contiene "(X)"
    current_basename = os.path.basename(dirpath)
    if "(X)" in current_basename:
        # Calcular la ruta relativa desde CAMERAS_DIR
        rel_path = os.path.relpath(dirpath, CAMERAS_DIR)
        # Construir la ruta destino dentro de PRIVATE
        dest_path = os.path.join(DEST_DIR, rel_path)
        if os.path.exists(dest_path):
            logging.info(f"El destino ya existe, se omite: {dest_path}")
        else:
            try:
                shutil.copytree(dirpath, dest_path)
                logging.info(f"Se copió '{dirpath}' a '{dest_path}'")
            except Exception as e:
                logging.error(f"Error al copiar '{dirpath}' a '{dest_path}': {e}")
