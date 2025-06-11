#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extended Collection Statistics without a built-in camera database.

1) Scans CAMERAS_DIR for all existing subfolders (model folders) and presents them.
2) Only processes files with extensions in PHOTO_EXTENSIONS.
3) Extracts EXIF tags exclusively for all metrics:
     - DateTimeOriginal/CreateDate → datetime
     - FocalLength, Flash, ExposureTime, FNumber
4) Computes per-model-folder and combined:
     • Monthly counts per year
     • Extension, focal, flash, shutter, aperture distributions
     • Total photos & bytes
5) Outputs PNG charts, per-folder PDFs, combined PDF, and global PDF.
6) Logs progress continuously; if you press Ctrl+C, it logs the interruption
   and flushes everything to disk before exiting.
7) Waits for <Enter> before exiting so you can inspect console output/logs.
"""

import os
import sys
import json
import logging
import subprocess
from datetime import datetime
import matplotlib.pyplot as plt
from fpdf import FPDF

# ------------------------------------------------------------------------------
# ACCEPTED EXTENSIONS
# ------------------------------------------------------------------------------
PHOTO_EXTENSIONS = {
    ".arw", ".cr2", ".cr3", ".jpg", ".mov", ".mp4", ".mts"
}

# ------------------------------------------------------------------------------
# DIRECTORIES
# ------------------------------------------------------------------------------
CAMERAS_DIR  = "CAMARAS"
LOGS_DIR     = "logs"
PDF_DIR      = "pdf"
METADATA_DIR = "metadata"
for d in (LOGS_DIR, PDF_DIR, METADATA_DIR):
    os.makedirs(d, exist_ok=True)

# ------------------------------------------------------------------------------
# LOGGER SETUP
# ------------------------------------------------------------------------------
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
logfile = os.path.join(LOGS_DIR, f"collection_stats_{TS}.log")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(logfile, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(file_handler)

console = logging.StreamHandler(sys.stdout)
console.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console)

# ------------------------------------------------------------------------------
# GLOBAL STORAGE FOR PHOTO RECORDS
# ------------------------------------------------------------------------------
photos_data = []  # each entry: {folder, year, month, extension, filesize, focal, flash, shutter, aperture}


# ------------------------------------------------------------------------------
# EXIF EXTRACTION
# ------------------------------------------------------------------------------
def leer_exif_json(path):
    """Run exiftool -j → JSON[0] dict or None."""
    try:
        proc = subprocess.run(
            ["exiftool", "-j", path],
            capture_output=True,
            text=True,
            timeout=30
        )
        if proc.returncode != 0:
            logger.warning(f"exiftool failed on '{path}': {proc.stderr.strip()}")
            return None
        arr = json.loads(proc.stdout)
        return arr[0] if isinstance(arr, list) and arr else None
    except subprocess.TimeoutExpired:
        logger.warning(f"exiftool timed out on '{path}'")
        return None
    except Exception as e:
        logger.warning(f"Error parsing EXIF JSON '{path}': {e}")
        return None

def extract_exif_tags(path):
    """
    Extract:
     - DateTimeOriginal/CreateDate (→ datetime)
     - FocalLength, Flash, ExposureTime, FNumber
    """
    meta = leer_exif_json(path) or {}
    dt_str = meta.get("DateTimeOriginal") or meta.get("CreateDate")
    dt = None
    if dt_str:
        dt_str = dt_str.split(".")[0]
        try:
            dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            logger.warning(f"Unexpected EXIF date '{dt_str}' in '{path}'")
    if not dt:
        try:
            dt = datetime.fromtimestamp(os.stat(path).st_ctime)
        except Exception as e:
            logger.warning(f"Cannot read ctime for '{path}': {e}")
            dt = datetime.now()
    focal    = str(meta.get("FocalLength",   "Unknown"))
    flash    = str(meta.get("Flash",         "Unknown"))
    shutter  = str(meta.get("ExposureTime",  meta.get("ShutterSpeedValue", "Unknown")))
    aperture = str(meta.get("FNumber",       "Unknown"))
    return dt, focal, flash, shutter, aperture


# ------------------------------------------------------------------------------
# LIST MODEL FOLDERS AND SELECT
# ------------------------------------------------------------------------------
def seleccionar_folders():
    """
    Scan CAMERAS_DIR for subfolders, present them for selection.
    0) [All detected folders]
    or comma-separated indices.
    """
    try:
        all_folders = [d for d in sorted(os.listdir(CAMERAS_DIR))
                       if os.path.isdir(os.path.join(CAMERAS_DIR, d))]
    except FileNotFoundError:
        logger.error(f"Directory '{CAMERAS_DIR}' not found.")
        sys.exit(1)

    if not all_folders:
        logger.error(f"No subfolders found in '{CAMERAS_DIR}'.")
        sys.exit(1)

    print("Detected model folders:")
    print("  0) [All folders]")
    for i, f in enumerate(all_folders, 1):
        print(f"  {i}) {f}")

    sel = input("Select folders to process (e.g. 0 or 1,3): ").strip()
    if sel == "0":
        return all_folders

    idxs = [int(x) for x in sel.split(",") if x.strip().isdigit()]
    chosen = [all_folders[i - 1] for i in idxs if 1 <= i <= len(all_folders)]
    if not chosen:
        logger.error("Invalid or out-of-range selection.")
        sys.exit(1)
    return chosen


# ------------------------------------------------------------------------------
# DATA COLLECTION
# ------------------------------------------------------------------------------
def recolectar_datos(folders):
    """
    Walk each selected folder under CAMERAS_DIR and collect EXIF data for valid files.
    """
    for folder in folders:
        base = os.path.join(CAMERAS_DIR, folder)
        logger.info(f"Scanning folder '{folder}'")
        for root, _, files in os.walk(base):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in PHOTO_EXTENSIONS:
                    continue
                fp = os.path.join(root, fn)
                try:
                    dt, focal, flash, shutter, aperture = extract_exif_tags(fp)
                    photos_data.append({
                        "folder":    folder,
                        "year":      dt.year,
                        "month":     dt.month,
                        "extension": ext,
                        "filesize":  os.path.getsize(fp),
                        "focal":     focal,
                        "flash":     flash,
                        "shutter":   shutter,
                        "aperture":  aperture
                    })
                except Exception as e:
                    logger.warning(f"Failed to process '{fp}': {e}")


# ------------------------------------------------------------------------------
# STATISTICS GENERATION
# ------------------------------------------------------------------------------
def generar_estadisticas(subset):
    """
    Returns stats dict:
    total_photos, total_bytes,
    by_year_month, by_extension, by_focal, by_flash, by_shutter, by_aperture
    """
    stats = {
        "total_photos":    0,
        "total_bytes":     0,
        "by_year_month":   {},
        "by_extension":    {},
        "by_focal":        {},
        "by_flash":        {},
        "by_shutter":      {},
        "by_aperture":     {},
    }
    for p in subset:
        stats["total_photos"] += 1
        stats["total_bytes"]  += p["filesize"]
        ym = stats["by_year_month"].setdefault(p["year"], {})
        ym[p["month"]] = ym.get(p["month"], 0) + 1
        stats["by_extension"][p["extension"]] = stats["by_extension"].get(p["extension"], 0) + 1
        stats["by_focal"][p["focal"]]         = stats["by_focal"].get(p["focal"], 0) + 1
        stats["by_flash"][p["flash"]]         = stats["by_flash"].get(p["flash"], 0) + 1
        stats["by_shutter"][p["shutter"]]     = stats["by_shutter"].get(p["shutter"], 0) + 1
        stats["by_aperture"][p["aperture"]]   = stats["by_aperture"].get(p["aperture"], 0) + 1
    return stats


# ------------------------------------------------------------------------------
# CHARTS
# ------------------------------------------------------------------------------
def plot_yearly_monthly(stats, prefix):
    """
    For each year in stats["by_year_month"], produce a bar chart.
    Returns list of saved PNG file paths.
    """
    import matplotlib.pyplot as plt
    paths = []
    for year, months in sorted(stats["by_year_month"].items()):
        counts = [months.get(m, 0) for m in range(1, 13)]
        plt.figure()
        plt.bar(range(1, 13), counts)
        plt.title(f"{year} – Photos by Month")
        plt.xlabel("Month"), plt.ylabel("Count")
        out = os.path.join(METADATA_DIR, f"{prefix}_{year}_monthly.png")
        plt.savefig(out); plt.close()
        paths.append(out)
    return paths

def plot_distribution(dist, title, prefix):
    """
    Generic bar chart for a distribution dictionary.
    Returns the saved PNG file path.
    """
    import matplotlib.pyplot as plt
    labels, values = zip(*sorted(dist.items(), key=lambda x: x[0]))
    plt.figure()
    plt.bar(range(len(labels)), values)
    plt.xticks(range(len(labels)), labels, rotation=45, ha="right")
    plt.title(title); plt.tight_layout()
    out = os.path.join(METADATA_DIR, f"{prefix}.png")
    plt.savefig(out); plt.close()
    return out


# ------------------------------------------------------------------------------
# PDF REPORT
# ------------------------------------------------------------------------------
def generar_pdf(stats, png_lists, pdf_path, title):
    """
    Compose a PDF with:
     - Title and summary text
     - Embedded PNG charts from png_lists
    """
    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, title, ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 6, f"Total photos: {stats['total_photos']}", ln=True)
    size_mb = stats["total_bytes"] / (1024**2)
    pdf.cell(0, 6, f"Total size: {size_mb:.2f} MB", ln=True)
    pdf.ln(5)

    def add_png(path, caption):
        if os.path.exists(path):
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 6, caption, ln=True); pdf.ln(2)
            pdf.image(path, w=pdf.w - 40); pdf.ln(5)

    for p in png_lists["yearly_monthly"]:
        add_png(p, "Photos by Month/Year")
    add_png(png_lists["by_extension"], "By Extension")
    add_png(png_lists["by_focal"],     "By Focal Length")
    add_png(png_lists["by_flash"],     "By Flash Mode")
    add_png(png_lists["by_shutter"],   "By Shutter Speed")
    add_png(png_lists["by_aperture"],  "By Aperture")

    pdf.output(pdf_path)
    logger.info(f"PDF saved: {pdf_path}")


# ------------------------------------------------------------------------------
# MAIN EXECUTION
# ------------------------------------------------------------------------------
def main():
    folders = seleccionar_folders()
    recolectar_datos(folders)
    logger.info(f"Collected {len(photos_data)} photos from {len(folders)} folder(s).")

    # Per-folder reports
    for folder in folders:
        subset = [p for p in photos_data if p["folder"] == folder]
        stats  = generar_estadisticas(subset)
        prefix = f"{folder.replace(' ','_')}_{TS}"
        pngs   = {
            "yearly_monthly": plot_yearly_monthly(stats, prefix),
            "by_extension":   plot_distribution(stats["by_extension"],
                                                 "Extension Distribution", prefix + "_ext"),
            "by_focal":       plot_distribution(stats["by_focal"],
                                                 "Focal Length Distribution", prefix + "_focal"),
            "by_flash":       plot_distribution(stats["by_flash"],
                                                 "Flash Mode Distribution", prefix + "_flash"),
            "by_shutter":     plot_distribution(stats["by_shutter"],
                                                 "Shutter Speed Distribution", prefix + "_shutter"),
            "by_aperture":    plot_distribution(stats["by_aperture"],
                                                 "Aperture Distribution", prefix + "_aperture"),
        }
        pdf_path = os.path.join(PDF_DIR, f"{prefix}_stats.pdf")
        generar_pdf(stats, pngs, pdf_path, f"Stats – Folder: {folder}")

    # Combined across all folders
    combined = generar_estadisticas(photos_data)
    prefix_all = f"ALL_FOLDERS_{TS}"
    pngs_all   = {
        "yearly_monthly": plot_yearly_monthly(combined, prefix_all),
        "by_extension":   plot_distribution(combined["by_extension"],
                                             "Extension Distribution", prefix_all + "_ext"),
        "by_focal":       plot_distribution(combined["by_focal"],
                                             "Focal Length Distribution", prefix_all + "_focal"),
        "by_flash":       plot_distribution(combined["by_flash"],
                                             "Flash Mode Distribution", prefix_all + "_flash"),
        "by_shutter":     plot_distribution(combined["by_shutter"],
                                             "Shutter Speed Distribution", prefix_all + "_shutter"),
        "by_aperture":    plot_distribution(combined["by_aperture"],
                                             "Aperture Distribution", prefix_all + "_aperture"),
    }
    pdf_all = os.path.join(PDF_DIR, f"{prefix_all}_stats.pdf")
    generar_pdf(combined, pngs_all, pdf_all, "Combined Statistics – All Folders")

    # Prevent console from closing until user presses Enter
    input("\nExecution finished. Press <Enter> to exit...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Execution interrupted by user (KeyboardInterrupt).")
    except Exception:
        logger.exception("Unhandled exception during execution")
