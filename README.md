# CamWork: Professional Photo Processing Suite

CamWork is a collection of Python scripts designed to help you organize your photo and video collections with minimal manual effort. It uses EXIF metadata to:

- Separate files by camera model  
- Group images into date-based folders (`YYYY.MM`)  
- Distinguish JPEG from RAW files and group RAW in `RAW/` subfolders  
- Detect exact bit-wise duplicates using SHA256  

All scripts write detailed logs and generate PDF summaries to document each operation.

---

## Folder Structure

```

/
├── CAMERAS/                        Root folder for all media files
│   ├── <CameraModel>/              Folder you create for each camera model
│   │   ├── photo1.JPG
│   │   ├── 2024.05/                Date folder (created by date_sort)
│   │   │   ├── Theme1/             Thematic folder (created manually)
│   │   │   │   ├── image.JPG
│   │   │   │   ├── RAW/            RAW subfolder (created by raw_sort)
│   │   │   │   └── Subtheme1/      Sub-thematic folder (created manually inside Theme1)
│   │   │   │       ├── image2.JPG
│   │   │   │       └── RAW/        RAW subfolder (raw_sort also processes subthemes)
│   │   │   └── …
│   │   └── …
│   ├── <CameraModel2>/
│   └── PRIVATE/                    Destination for folders marked with “(X)”
└── scripts/                        All Python scripts
├── scan_exif_v1_estable.PY
├── model_sort_v2_estable.PY
├── date_sort_v1.2_estable.PY
├── raw_sort_v1_estable.PY
├── dup_search_v2.4_estable_tested.PY
├── copiar_private_estable.py
└── stats_developing.py         (experimental, use not recommended)

````

> **Notes**  
> - You must create the camera model folders, thematic folders, and any sub-thematic folders manually.  
> - The scripts will process any sub-thematic folder inside a thematic folder exactly as they handle a top-level thematic folder.

---

## Requirements

- **Python 3.6+**  
- **ExifTool** installed and on your system `PATH`  
- Python packages:
  ```bash
  pip install fpdf pillow
  
---

## Usage Guide

1. **Set up folders**

   * In your project root, create `CAMERAS/` and `scripts/`.
   * Place all `.PY` scripts into the `scripts/` folder.

2. **Import media**

   * Copy photos and videos from your camera’s SD card into `CAMERAS/` (no subfolders).

3. **Scan EXIF models & extensions**

   ```bash
   python3 scripts/scan_exif_v1_estable.PY
   ```

   * Produces logs under `logs/` listing all camera models and file extensions found.

4. **Classify by camera model**

   * Edit the `MODEL_TO_FOLDER` mapping in `scripts/model_sort_v2_estable.PY`.

   ```bash
   python3 scripts/model_sort_v2_estable.PY
   ```

   * Files with unmapped EXIF models or missing destination folders are left in place and logged.

5. **Sort by capture date**

   ```bash
   python3 scripts/date_sort_v1.2_estable.PY
   ```

   * Select which camera folders to process.
   * Creates `YYYY.MM/` date folders inside each `CAMERAS/<Model>/`.
   * Moves JPEG/PNG files into the correct month based on EXIF or file timestamps.
   * Photos shot on the 1st before 08:00 are placed in the previous month.
   * Duplicate filenames in the destination folder are skipped and logged.
   * Generates both a log (`logs/`) and a PDF summary (`pdf/`).

6. **Create thematic and sub-thematic folders (manual)**

   * Inside each `CAMERAS/<Model>/YYYY.MM/`, create your thematic folders (e.g. `Birthdays/`).
   * If needed, create sub-thematic folders under each theme (e.g. `Birthdays/Subtheme1/`).

7. **Group RAW files**

   ```bash
   python3 scripts/raw_sort_v1_estable.PY
   ```

   * Select camera folders to process.
   * In each thematic and sub-thematic folder, moves `.cr2` and `.arw` files into a `RAW/` subfolder.
   * Skips folders with no RAW files and logs any errors.

8. **Detect exact duplicates (SHA256)**

   ```bash
   python3 scripts/dup_search_v2.4_estable_tested.PY
   ```

   * Ignores the `CAMERAS/PRIVATE/` folder.
   * Within each camera model folder, groups files by name+extension.
   * Only for names that repeat, calculates SHA256 hashes and lists true duplicates.

9. **Copy folders marked “(X)”**

   ```bash
   python3 scripts/copiar_private_estable.py
   ```

   * Creates `CAMERAS/PRIVATE/` if it does not exist.
   * Recursively copies any folder whose name contains `(X)`, preserving its structure.
   * Skips destinations that already exist (no overwrite, no deletion).

10. **Generate statistics (experimental)**

    ```bash
    python3 scripts/stats_developing.py
    ```

    * Produces graphs and a PDF report of your collection.
    * Early-stage script; functionality may be unreliable.

---

## Recommended Workflow

1. Prepare project root with `CAMERAS/` and `scripts/`.
2. Copy media into `CAMERAS/`.
3. Run **scan\_exif** to catalog models and extensions.
4. Configure and run **model\_sort** to distribute by model.
5. Run **date\_sort** to create monthly folders.
6. Manually create thematic and sub-thematic folders.
7. Run **raw\_sort** to collect RAW files.
8. Run **dup\_search** to detect true duplicates.
9. Run **copiar\_private** to pull out `(X)` folders.
10. (Optional) Run **stats\_developing** for global statistics.

---

## Error Handling

* **ExifTool missing**: EXIF-based scripts will fail with an error.
* **Permission denied**: Affected files or folders are skipped and logged.
* **Unmapped EXIF model**: In model\_sort, files remain in place and are logged.
* **Detected duplicates**: Files are not overwritten, skipped, and logged.
* **Destination folder missing**: In model\_sort and raw\_sort, items are skipped and logged.
* **No monthly folders**: date\_sort logs “no changes” if nothing to move.
