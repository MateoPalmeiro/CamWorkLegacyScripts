#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import shutil
import subprocess
import logging
from datetime import datetime

# ----------------------------------------------------------------------------
# CONFIGURACIÓN
# ----------------------------------------------------------------------------
CAMERAS_DIR = "CAMARAS"  # Carpeta raíz donde están las imágenes sueltas
# Actualiza las extensiones de foto/vídeo aquí (sin .ffs_db ni .ini):
PHOTO_EXTENSIONS = {
    ".arw",
    ".cr2",
    ".cr3",
    ".jpg",
    ".mov",
    ".mp4",
    ".mts"
}

# ----------------------------------------------------------------------------
# MAPA MANUAL DE MODELOS EXIF → CARPETA DESTINO
# Rellena con las cadenas exactas que devuelve exiftool -Model y la carpeta
# que ya existe bajo CAMERAS_DIR
# ----------------------------------------------------------------------------
MODEL_TO_FOLDER = {
    "Canon EOS 650D":                   "Canon EOS 650D",
    "Canon EOS M50m2":                  "Canon EOS M50m2",
    "Canon PowerShot G9 X Mark II":     "Canon Powershot G9 X Mark II",
    "Canon PowerShot SX230 HS":         "Canon PowerShot SX230 HS",
    "Canon PowerShot SX610 HS":         "Canon PowerShot SX610 HS",
    "DMC-TZ57":                         "Panasonic DCM-TZ57",
    "DV300":                            "Samsung DV300F",
    "DV300F":                           "Samsung DV300F",
    "DV305F":                           "Samsung DV300F",
    "Full HD Camcorder":                "Samsung HMX-H300",
    "HMX-H300":                         "Samsung HMX-H300",
    "HERO7 White":                      "Gopro Hero7 White",
    "HERO10 Black":                     "Gopro Hero10 Black",
    "HERO11 Black":                     "Gopro Hero11 Black",
    "ILCE-6000":                        "Sony ILCE-6000",
    "WB30F":                            "Samsung WB30F",
    "WB30F/WB31F/WB32F":                "Samsung WB30F",
    # "Unknown" y "PRIVATE" se ignoran
}

# ----------------------------------------------------------------------------
# LOGGING
# ----------------------------------------------------------------------------
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILENAME = os.path.join(LOGS_DIR, f"clasificar_imagenes_{timestamp}.log")

logging.basicConfig(
    filename=LOG_FILENAME,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ----------------------------------------------------------------------------
# LISTAS PARA RESUMEN
# ----------------------------------------------------------------------------
unmapped = []    # fotos cuyo modelo EXIF no está en MODEL_TO_FOLDER
duplicates = []  # fotos duplicadas detectadas

# ----------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ----------------------------------------------------------------------------

def sanitize_folder_name(name):
    """
    Limpia el nombre de la carpeta reemplazando caracteres inválidos para Windows/Linux.
    """
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def get_camera_model(filepath):
    """
    Obtiene el modelo de cámara a partir de los metadatos EXIF con exiftool.
    Devuelve la cadena exacta (por ejemplo "Canon EOS 5D Mark III") o "Unknown".
    """
    try:
        result = subprocess.run(
            ["exiftool", "-Model", "-s3", filepath],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            model = result.stdout.strip()
            if model:
                return model
        logging.warning(f"No se pudo leer el modelo EXIF de '{filepath}'")
    except Exception as e:
        logging.error(f"Error ejecutando exiftool en '{filepath}': {e}")
    return "Unknown"

def is_duplicate(dest_folder, filename):
    """
    Recorre recursivamente dest_folder y devuelve True si encuentra filename
    (en cualquier subcarpeta, incluidas RAW/, temáticas, subtemáticas, etc.).
    """
    for root, dirs, files in os.walk(dest_folder):
        if filename in files:
            return True
    return False

# ----------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL
# ----------------------------------------------------------------------------

def classify_images():
    """
    Para cada archivo en CAMERAS_DIR:
      1. Leer modelo EXIF.
      2. Buscar carpeta en MODEL_TO_FOLDER.
      3. Si no está mapeado, registrar y dejar sin mover.
      4. Si existe carpeta destino, buscar duplicado; si existe, registrar y dejar.
      5. Si no es duplicado, mover a carpeta destino.
    """
    if not os.path.isdir(CAMERAS_DIR):
        logging.critical(f"No existe la carpeta raíz '{CAMERAS_DIR}'")
        return

    for item in os.listdir(CAMERAS_DIR):
        item_path = os.path.join(CAMERAS_DIR, item)

        # Solo procesar archivos con extensiones permitidas
        if not os.path.isfile(item_path):
            continue
        _, ext = os.path.splitext(item)
        if ext.lower() not in PHOTO_EXTENSIONS:
            logging.info(f"'{item}' no es un archivo soportado. Se omite.")
            continue

        # 1) Leer modelo EXIF
        model_exif = get_camera_model(item_path)

        # 2) Buscar carpeta en el mapa manual
        folder_name = MODEL_TO_FOLDER.get(model_exif)
        if not folder_name:
            logging.warning(f"Modelo EXIF '{model_exif}' no mapeado → '{item_path}' se deja sin mover")
            unmapped.append(item_path)
            continue

        # 3) Construir y validar carpeta destino
        dest_folder = os.path.join(CAMERAS_DIR, sanitize_folder_name(folder_name))
        if not os.path.isdir(dest_folder):
            logging.error(f"Carpeta destino '{dest_folder}' no existe para modelo '{model_exif}'")
            unmapped.append(item_path)
            continue

        # 4) Buscar duplicados en toda la jerarquía de dest_folder
        if is_duplicate(dest_folder, item):
            logging.warning(f"Duplicado detectado, no movido: '{item_path}' ya existe en '{dest_folder}'")
            duplicates.append(item_path)
            continue

        # 5) Mover el archivo
        try:
            shutil.move(item_path, os.path.join(dest_folder, item))
            logging.info(f"Movido '{item}' → '{dest_folder}'")
        except Exception as e:
            logging.error(f"Error al mover '{item_path}' → '{dest_folder}': {e}")
            duplicates.append(item_path)

    # Resumen al final
    if unmapped:
        logging.info("=== Fotos sin mapeo EXIF (quedan sin mover) ===")
        for p in unmapped:
            logging.info(f"    {p}")

    if duplicates:
        logging.info("=== Fotos duplicadas detectadas (no movidas) ===")
        for p in duplicates:
            logging.info(f"    {p}")

# ----------------------------------------------------------------------------
# EJECUCIÓN PRINCIPAL
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    classify_images()
