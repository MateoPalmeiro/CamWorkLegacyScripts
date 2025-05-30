#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import hashlib
import logging
import sys
from datetime import datetime

# ----------------------------------------------------------------------------
# CONFIGURACIÓN
# ----------------------------------------------------------------------------
CAMERAS_DIR = "CAMARAS"  # Carpeta raíz a escanear
LOGS_DIR    = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)
ts          = datetime.now().strftime("%Y%m%d_%H%M%S")

# Solo extensiones de imagen
IMAGE_EXTENSIONS = {".arw", ".cr2", ".cr3", ".jpg"}

# Paths de log y salidas
MAIN_LOG        = os.path.join(LOGS_DIR, f"scan_sha256_{ts}.log")
CONTENTS_FILE   = os.path.join(LOGS_DIR, f"folder_contents_{ts}.txt")
DUPLICATES_FILE = os.path.join(LOGS_DIR, f"duplicates_sha256_{ts}.txt")

# ----------------------------------------------------------------------------
# CONFIGURAR LOGGING A ARCHIVO Y CONSOLA
# ----------------------------------------------------------------------------
logger = logging.getLogger()
logger.setLevel(logging.INFO)
fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

fh = logging.FileHandler(MAIN_LOG)
fh.setLevel(logging.INFO)
fh.setFormatter(fmt)
logger.addHandler(fh)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(fmt)
logger.addHandler(ch)

# ----------------------------------------------------------------------------
# Función para calcular SHA256 de un archivo
# ----------------------------------------------------------------------------
def sha256_of_file(path, chunk_size=8192):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
    except Exception as e:
        logger.error(f"Error calculando SHA256 de '{path}': {e}")
        return None
    return h.hexdigest()

# ----------------------------------------------------------------------------
# FASE 1: Recopilar contenidos por carpeta (ignorando PRIVATE)
# ----------------------------------------------------------------------------
logger.info(f"Escaneo iniciado de '{CAMERAS_DIR}' (ignorando PRIVATE)")

if not os.path.isdir(CAMERAS_DIR):
    logger.critical(f"No existe la carpeta raíz '{CAMERAS_DIR}'")
    sys.exit(1)

files_by_folder = {}
for root, dirs, files in os.walk(CAMERAS_DIR):
    if 'PRIVATE' in dirs:
        dirs.remove('PRIVATE')
    valid = [f for f in files
             if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS]
    if valid:
        files_by_folder[root] = sorted(valid)
        logger.info(f"Encontrados {len(valid)} archivos en '{root}'")

logger.info(f"Escribiendo listado de contenidos en '{CONTENTS_FILE}'")
with open(CONTENTS_FILE, "w", encoding="utf-8") as cf:
    cf.write(f"CONTENIDOS POR CARPETA - Escaneo {ts}\n\n")
    for folder in sorted(files_by_folder):
        rel = os.path.relpath(folder, CAMERAS_DIR)
        cf.write(f"[{rel}]\n")
        for fname in files_by_folder[folder]:
            cf.write(f"  - {fname}\n")
        cf.write("\n")

# ----------------------------------------------------------------------------
# FASE 2: Comparar solo dentro de cada cámara, por nombre+extensión y SHA256
# ----------------------------------------------------------------------------
logger.info("Iniciando detección de duplicados por cámara + SHA256")

# Agrupar rutas por cámara y luego por nombre de archivo
camera_to_name_paths = {}
for folder, fnames in files_by_folder.items():
    # identificamos la cámara como primer subdirectorio tras CAMERAS_DIR
    rel = os.path.relpath(folder, CAMERAS_DIR)
    camera = rel.split(os.sep, 1)[0]
    if camera == "" or camera == "PRIVATE":
        continue
    for fname in fnames:
        key = fname.lower()
        full = os.path.join(folder, fname)
        camera_to_name_paths.setdefault(camera, {}).setdefault(key, []).append(full)

with open(DUPLICATES_FILE, "w", encoding="utf-8") as df:
    df.write(f"DUPLICADOS SHA256 POR CÁMARA - {ts}\n\n")
    any_dup = False

    for camera, name_paths in sorted(camera_to_name_paths.items()):
        logger.info(f"Buscando duplicados en cámara '{camera}'")
        df.write(f"## Cámara: {camera}\n")
        for name, paths in sorted(name_paths.items()):
            if len(paths) < 2:
                continue

            # Mostrar en consola qué dos archivos se comparan (o varios)
            if len(paths) == 2:
                logger.info(f"Comparando SHA256: '{paths[0]}' vs '{paths[1]}'")
            else:
                logger.info(f"Comparando SHA256 de {len(paths)} archivos en {camera}: {paths}")

            # Calcular hash para cada ruta
            hash_to_paths = {}
            for p in paths:
                logger.info(f"  -> Hashing '{p}'")
                h = sha256_of_file(p)
                if h is None:
                    continue
                hash_to_paths.setdefault(h, []).append(p)

            # Registrar duplicados exactos
            for h, hp in hash_to_paths.items():
                if len(hp) > 1:
                    any_dup = True
                    df.write(f"ARCHIVO: {name}\n")
                    df.write(f" SHA256: {h}\n")
                    df.write(" RUTAS:\n")
                    for p in sorted(hp):
                        relp = os.path.relpath(p, CAMERAS_DIR)
                        df.write(f"  - {p}  (Carpeta: {camera})\n")
                    df.write("\n")
                    logger.warning(f"Duplicado exacto en '{camera}': '{name}' ({len(hp)} ubicaciones)")

        df.write("\n")

    if not any_dup:
        df.write("No se encontraron duplicados SHA256 en ninguna cámara.\n")

logger.info(f"Detección completada. Resultados en '{DUPLICATES_FILE}'")
