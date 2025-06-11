#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Este script recorre recursivamente la carpeta CAMERAS y copia todas las subcarpetas
cuyo nombre contiene "(X)" dentro de una carpeta destino llamada PRIVATE,
creando logs detallados de cada acción y mostrando también el progreso por pantalla.
Está diseñado para ser mantenible y cumplir con estándares profesionales de documentación (ISO/IEEE).
"""

import os        # Operaciones con el sistema de archivos
import shutil    # Copia de árboles de directorios
import logging   # Generación de registros de eventos (logs)
from datetime import datetime  # Fecha y hora actual

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE LOGS (ISO/IEC/IEEE 42010:2011 - Arquitectura de Sistemas)
# -----------------------------------------------------------------------------
LOGS_DIR = "logs"
# Asegura que exista el directorio de logs (no lanza excepción si ya existe)
os.makedirs(LOGS_DIR, exist_ok=True)
# Formateo de la fecha actual para incluirla en el nombre del fichero de log
today_str = datetime.now().strftime("%d-%m-%Y")
# Ruta completa del fichero de log, p.ej. logs/copy_private_11-06-2025.log
LOG_FILENAME = os.path.join(LOGS_DIR, f"copy_private_{today_str}.log")

# Configuración básica del logger de raíz
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Formato estándar: timestamp, nivel de importancia y mensaje
t_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Handler para fichero de logsfh = logging.FileHandler(LOG_FILENAME)
fh.setLevel(logging.INFO)
fh.setFormatter(t_formatter)
logger.addHandler(fh)

# Handler para salida por consola (stdout)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(t_formatter)
logger.addHandler(ch)

# -----------------------------------------------------------------------------
# PARÁMETROS GLOBALES (ISO/IEC/IEEE 12207:2017 - Ciclo de vida de software)
# -----------------------------------------------------------------------------
CAMERAS_DIR = "CAMARAS"        # Carpeta raíz con todas las cámaras
DEST_DIR_NAME = "PRIVATE"      # Nombre de la subcarpeta destino
DEST_DIR = os.path.join(CAMERAS_DIR, DEST_DIR_NAME)  # Ruta completa destino

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
# Utilizamos os.walk en modo top-down para poder filtrar subdirectorios antes de bajar en ellos.
for dirpath, dirnames, filenames in os.walk(CAMERAS_DIR, topdown=True):
    # 1. Excluir la carpeta PRIVATE del recorrido, evitando bucles o copias redundantes
    dirnames[:] = [d for d in dirnames if d != DEST_DIR_NAME]

    # 2. Determinar si la carpeta actual es candidata: su nombre contiene "(X)"
    current_basename = os.path.basename(dirpath)
    if "(X)" in current_basename:
        # 2.1 Calcular ruta relativa desde CAMERAS_DIR para mantener jerarquía
        rel_path = os.path.relpath(dirpath, CAMERAS_DIR)
        # 2.2 Construir la ruta destino dentro de PRIVATE
        dest_path = os.path.join(DEST_DIR, rel_path)

        # 3. Verificar existencia previa para evitar sobrescritura
        if os.path.exists(dest_path):
            logger.info(f"El destino ya existe, se omite: {dest_path}")
        else:
            try:
                # 4. Copia recursiva completa del árbol de directorios
                shutil.copytree(dirpath, dest_path)
                logger.info(f"Se copió '{dirpath}' a '{dest_path}'")
            except Exception as e:
                # 5. En caso de error (permiso, espacio, etc.), registrar con nivel ERROR
                logger.error(f"Error al copiar '{dirpath}' a '{dest_path}': {e}")

# Nota: Los mensajes de log se registran en el fichero y se imprimen en consola,
# facilitando el seguimiento en tiempo real y la detección de posibles bloqueos.

