#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified image organiser:

1) sort_by_model:  
   - Reads EXIF Model tag  
   - Maps known models to predefined folders (others are skipped)  
   - Skips files whose SHA-256 hash already exists in the destination  

2) sort_by_date:  
   - Reads EXIF DateTimeOriginal/CreateDate (falls back to ctime/mtime)  
   - Applies “day 1 before 08:00 → previous month” rule  
   - Moves into ‘YYYY.MM’ subfolders, skipping SHA-256 duplicates  

3) Reporting:  
   - TXT and PDF summary of date sorting  
   - Full folder contents listing  
   - Per-camera SHA-256 duplicate scan  

Only files whose extensions are listed in PHOTO_EXTENSIONS are processed.
"""

import os
import sys
import shutil
import subprocess
import logging
import json
import hashlib
from datetime import datetime, timedelta
from fpdf import FPDF

# ------------------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------------------
CAMERAS_DIR = "CAMERAS"
LOGS_DIR    = "logs"
PDF_DIR     = "pdf"

# Only these extensions are handled
PHOTO_EXTENSIONS = {
    ".arw", ".cr2", ".cr3", ".jpg", ".mov", ".mp4", ".mts"
}

# Ensure output directories exist
for d in (CAMERAS_DIR, LOGS_DIR, PDF_DIR):
    os.makedirs(d, exist_ok=True)

# Timestamp for all outputs
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

# ------------------------------------------------------------------------------
# LOGGER: file + console
# ------------------------------------------------------------------------------
log_path = os.path.join(LOGS_DIR, f"unified_sort_{TS}.log")
logger   = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(log_path, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console_handler)

# ------------------------------------------------------------------------------
# GLOBAL CACHES & REPORT DATA
# ------------------------------------------------------------------------------
_hash_cache    = {}   # dest_dir → set of SHA-256 hashes
duplicates     = []   # list of source file paths skipped as duplicates
folders_report = {}   # YYYY.MM → {created, photos, bytes, exts}

# ------------------------------------------------------------------------------
# MODEL → DESTINATION FOLDER MAPPING
# ------------------------------------------------------------------------------
MODEL_TO_FOLDER = {
    "Canon EOS 650D":                   "Canon EOS 650D",
    "Canon EOS M50m2":                  "Canon EOS M50m2",
    "Canon PowerShot G9 X Mark II":     "Canon Powershot G9 X Mark II",
    "Canon PowerShot SX230 HS":         "Canon PowerShot SX230 HS",
    "Canon PowerShot SX610 HS":         "Canon PowerShot SX610 HS",
    "DMC-TZ57":                         "Panasonic DCM-TZ57",
    "DV300 / DV300F / DV305F":          "Samsung DV300F",
    "Full HD Camcorder":                "Samsung HMX-H300",
    "HMX-H300":                         "Samsung HMX-H300",
    "HERO7 White":                      "Gopro Hero7 White",
    "HERO10 Black":                     "Gopro Hero10 Black",
    "HERO11 Black":                     "Gopro Hero11 Black",
    "ILCE-6000":                        "Sony ILCE-6000",
    "WB30F":                            "Samsung WB30F",
    "WB30F/WB31F/WB32F":                "Samsung WB30F",
}

def map_model_to_folder(tag: str) -> str:
    """Return destination folder for an EXIF Model tag, or None."""
    return MODEL_TO_FOLDER.get(tag)


# ------------------------------------------------------------------------------
# UTILITY FUNCTIONS
# ------------------------------------------------------------------------------
def compute_sha256(path: str, chunk_size: int = 8192) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()

def is_duplicate(src: str, dest_dir: str) -> bool:
    """
    Return True if src file's hash already exists in dest_dir.
    Caches hashes per destination directory for performance.
    """
    if not os.path.isdir(dest_dir):
        return False
    if dest_dir not in _hash_cache:
        seen = set()
        for fn in os.listdir(dest_dir):
            fp = os.path.join(dest_dir, fn)
            if os.path.isfile(fp):
                try:
                    seen.add(compute_sha256(fp))
                except Exception as e:
                    logger.warning(f"Failed to hash existing file '{fp}': {e}")
        _hash_cache[dest_dir] = seen
    h = compute_sha256(src)
    if h in _hash_cache[dest_dir]:
        return True
    _hash_cache[dest_dir].add(h)
    return False

def human_readable_size(n: int) -> str:
    """Convert bytes to human-readable string."""
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n/1024:.2f} KB"
    if n < 1024**3:
        return f"{n/1024**2:.2f} MB"
    return f"{n/1024**3:.2f} GB"


# ------------------------------------------------------------------------------
# SORT BY MODEL
# ------------------------------------------------------------------------------
def extract_model(filepath: str) -> str:
    """Run exiftool to get the Model tag, plain output (-s3)."""
    try:
        res = subprocess.run(
            ["exiftool", "-Model", "-s3", filepath],
            capture_output=True, text=True
        )
        if res.returncode == 0:
            return res.stdout.strip() or None
    except Exception as e:
        logger.warning(f"exiftool Model error on '{filepath}': {e}")
    return None

def sort_by_model():
    """Move all loose files in CAMERAS_DIR into model-based folders."""
    logger.info(">>> Starting model sort")
    for fname in os.listdir(CAMERAS_DIR):
        src = os.path.join(CAMERAS_DIR, fname)
        if not os.path.isfile(src):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext not in PHOTO_EXTENSIONS:
            continue

        tag = extract_model(src)
        if not tag:
            logger.info(f"Skipped (no Model EXIF): {fname}")
            continue

        folder = map_model_to_folder(tag)
        if not folder:
            logger.info(f"Skipped (model not in map): '{tag}' → {fname}")
            continue

        dest = os.path.join(CAMERAS_DIR, folder)
        os.makedirs(dest, exist_ok=True)

        if is_duplicate(src, dest):
            logger.warning(f"Duplicate in model sort, skipped: {fname}")
            duplicates.append(src)
            continue

        try:
            shutil.move(src, os.path.join(dest, fname))
            logger.info(f"Moved by model: {fname} → {folder}")
        except Exception as e:
            logger.error(f"Error moving {fname}: {e}")
    logger.info("<<< Finished model sort\n")


# ------------------------------------------------------------------------------
# SORT BY DATE
# ------------------------------------------------------------------------------
def leer_exif_json(fp: str) -> dict:
    """Run exiftool -j and parse JSON metadata."""
    try:
        proc = subprocess.run(
            ["exiftool", "-j", fp],
            capture_output=True, text=True
        )
        if proc.returncode != 0:
            logger.warning(f"exiftool JSON failed on '{fp}'")
            return None
        arr = json.loads(proc.stdout)
        return arr[0] if isinstance(arr, list) and arr else None
    except Exception as e:
        logger.warning(f"Error parsing EXIF JSON '{fp}': {e}")
    return None

def obtener_fecha(fp: str) -> datetime:
    """
    Extract capture date from EXIF DateTimeOriginal/CreateDate.
    Fallback to ctime, then mtime.
    """
    meta = leer_exif_json(fp)
    if meta:
        for tag in ("DateTimeOriginal", "CreateDate"):
            dt = meta.get(tag)
            if dt:
                dt = dt.split(".")[0]
                try:
                    return datetime.strptime(dt, "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    logger.warning(f"Unexpected EXIF date format '{dt}' in '{fp}'")
    # fallback to creation time
    try:
        return datetime.fromtimestamp(os.stat(fp).st_ctime)
    except Exception:
        pass
    # fallback to modification time
    try:
        return datetime.fromtimestamp(os.path.getmtime(fp))
    except Exception as e:
        logger.error(f"No date found for '{fp}': {e}")
    return None

def ajustar_mes(dt: datetime) -> datetime:
    """If day==1 and hour<8, attribute to previous day/month."""
    if dt.day == 1 and dt.hour < 8:
        return dt - timedelta(days=1)
    return dt

def carpeta_mes(dt: datetime) -> str:
    """Return 'YYYY.MM' folder name."""
    return f"{dt.year}.{dt.month:02d}"

def seleccionar_camaras() -> list:
    """Prompt user to select which model folders to process by date."""
    cams = [
        d for d in sorted(os.listdir(CAMERAS_DIR))
        if os.path.isdir(os.path.join(CAMERAS_DIR, d)) and d.upper() != "PRIVATE"
    ]
    if not cams:
        print("No camera folders found.")
        return []
    print("Available camera folders:")
    for i, c in enumerate(cams, 1):
        print(f"  {i}. {c}")
    sel = input("Select (e.g. 1,3): ")
    idxs = [int(x) for x in sel.split(",") if x.strip().isdigit()]
    return [cams[i-1] for i in idxs if 1 <= i <= len(cams)]

def sort_by_date(cams: list):
    """Group files in each camera folder into 'YYYY.MM' based on capture date."""
    logger.info(">>> Starting date sort")
    for cam in cams:
        base = os.path.join(CAMERAS_DIR, cam)
        logger.info(f"→ Processing camera: {cam}")
        for fname in os.listdir(base):
            src = os.path.join(base, fname)
            if not os.path.isfile(src):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in PHOTO_EXTENSIONS:
                continue

            dt = obtener_fecha(src) or datetime.now()
            dt = ajustar_mes(dt)
            folder = carpeta_mes(dt)
            dest = os.path.join(base, folder)
            os.makedirs(dest, exist_ok=True)

            if is_duplicate(src, dest):
                logger.warning(f"Duplicate in date sort, skipped: {cam}/{fname}")
                duplicates.append(src)
                continue

            try:
                size = os.path.getsize(src)
                shutil.move(src, os.path.join(dest, fname))
                logger.info(f"Moved by date: {cam}/{fname} → {folder}")
                info = folders_report.setdefault(folder, {
                    "created": not os.path.exists(dest),
                    "photos": 0,
                    "bytes": 0,
                    "exts": {}
                })
                info["photos"] += 1
                info["bytes"]  += size
                info["exts"][ext] = info["exts"].get(ext, 0) + 1
            except Exception as e:
                logger.error(f"Error moving {cam}/{fname}: {e}")
    logger.info("<<< Finished date sort\n")

# ------------------------------------------------------------------------------
# REPORT GENERATION FOR DATE SORT
# ------------------------------------------------------------------------------
def generar_resumen_txt():
    path = os.path.join(LOGS_DIR, f"summary_date_{TS}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("DATE SORT SUMMARY\n\n")
        total_ph = sum(v["photos"] for v in folders_report.values())
        total_b  = sum(v["bytes"]  for v in folders_report.values())
        f.write(f"Total photos moved: {total_ph}\n")
        f.write(f"Total bytes moved: {total_b} ({human_readable_size(total_b)})\n\n")
        for month, v in folders_report.items():
            f.write(f"- {month}: {v['photos']} photos, {human_readable_size(v['bytes'])}\n")
        if duplicates:
            f.write("\nDuplicates skipped:\n")
            for d in duplicates:
                f.write(f"  * {d}\n")
    logger.info(f"Date sort TXT summary saved to {path}")

def generar_resumen_pdf():
    path = os.path.join(PDF_DIR, f"summary_date_{TS}.pdf")
    pdf  = FPDF()
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Date Sort Summary", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", "", 12)
    for month, v in folders_report.items():
        line = f"{month}: {v['photos']} photos, {human_readable_size(v['bytes'])}"
        pdf.cell(0, 6, line, ln=True)
    if duplicates:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 6, "Duplicates skipped:", ln=True)
        pdf.set_font("Arial", "", 12)
        for d in duplicates:
            pdf.cell(0, 6, d, ln=True)
    pdf.output(path)
    logger.info(f"Date sort PDF summary saved to {path}")

# ------------------------------------------------------------------------------
# FOLDER CONTENTS & SHA-256 DUPLICATE SCAN
# ------------------------------------------------------------------------------
CONTENTS_FILE   = os.path.join(LOGS_DIR, f"folder_contents_{TS}.txt")
DUPLICATES_FILE = os.path.join(LOGS_DIR, f"duplicates_sha256_{TS}.txt")

def scan_folder_contents():
    logger.info("Generating folder contents listing...")
    files_by_folder = {}
    for root, dirs, files in os.walk(CAMERAS_DIR):
        if "PRIVATE" in dirs:
            dirs.remove("PRIVATE")
        valid = [f for f in files if os.path.splitext(f)[1].lower() in PHOTO_EXTENSIONS]
        if valid:
            files_by_folder[root] = sorted(valid)
    with open(CONTENTS_FILE, "w", encoding="utf-8") as cf:
        cf.write(f"FOLDER CONTENTS - {TS}\n\n")
        for folder, lst in sorted(files_by_folder.items()):
            rel = os.path.relpath(folder, CAMERAS_DIR)
            cf.write(f"[{rel}]\n")
            for fn in lst:
                cf.write(f"  - {fn}\n")
            cf.write("\n")
    logger.info(f"Folder contents written to {CONTENTS_FILE}")

def scan_duplicates_by_camera():
    logger.info("Scanning SHA-256 duplicates per camera...")
    camera_map = {}
    for root, dirs, files in os.walk(CAMERAS_DIR):
        if "PRIVATE" in dirs:
            dirs.remove("PRIVATE")
        cam = os.path.relpath(root, CAMERAS_DIR).split(os.sep)[0]
        for fn in files:
            if os.path.splitext(fn)[1].lower() not in PHOTO_EXTENSIONS:
                continue
            camera_map.setdefault(cam, {}).setdefault(fn.lower(), []).append(os.path.join(root, fn))

    any_dup = False
    with open(DUPLICATES_FILE, "w", encoding="utf-8") as df:
        df.write(f"SHA-256 DUPLICATES BY CAMERA - {TS}\n\n")
        for cam, name_map in sorted(camera_map.items()):
            df.write(f"## Camera: {cam}\n")
            for name, paths in sorted(name_map.items()):
                if len(paths) < 2:
                    continue
                # group by hash
                hash_map = {}
                for p in paths:
                    h = compute_sha256(p)
                    hash_map.setdefault(h, []).append(p)
                for h, grp in hash_map.items():
                    if len(grp) > 1:
                        any_dup = True
                        df.write(f"{name}  SHA256={h}\n")
                        for p in grp:
                            df.write(f"  - {p}\n")
                        df.write("\n")
                        logger.warning(f"Exact duplicate in {cam}: {name}")
        if not any_dup:
            df.write("No duplicates found.\n")
    logger.info(f"Duplicate report saved to {DUPLICATES_FILE}")

# ------------------------------------------------------------------------------
# MAIN EXECUTION
# ------------------------------------------------------------------------------
def main():
    # 1) Model sort: only loose files in CAMERAS_DIR
    loose = [
        f for f in os.listdir(CAMERAS_DIR)
        if os.path.isfile(os.path.join(CAMERAS_DIR, f))
        and os.path.splitext(f)[1].lower() in PHOTO_EXTENSIONS
    ]
    if not loose:
        logger.info("No loose files in CAMERAS_DIR; exiting.")
        return

    sort_by_model()

    # 2) Date sort: select camera folders
    cams = seleccionar_camaras()
    if not cams:
        logger.info("No cameras selected; exiting.")
        return
    sort_by_date(cams)

    # 3) Generate date-sort reports
    generar_resumen_txt()
    generar_resumen_pdf()

    # 4) Global folder contents & duplicates
    scan_folder_contents()
    scan_duplicates_by_camera()

    logger.info("=== All tasks completed successfully ===")

if __name__ == "__main__":
    main()
