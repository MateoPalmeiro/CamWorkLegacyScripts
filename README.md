
# CamWork: Professional Photo Processing Suite

CamWork is a suite of Python scripts designed to automate and document the organization of photo and video collections. Leveraging EXIF metadata, it enables:

- **Model-based classification**: Sort by camera model.  
- **Date-based organization**: Create `YYYY.MM` folders based on capture dates.  
- **RAW file grouping**: Isolate RAW files into `RAW/` subfolders.  
- **Exact duplicate detection**: Identify bit-wise duplicates via SHA-256.  
- **Comprehensive reporting**: Generate detailed logs and PDF summaries for each operation.

---

## Folder Layout

```

/
├── CAMARAS/                            ← Root for all media
│   ├── <CameraModel>/                  ← Manually created per model
│   │   ├── photo1.JPG
│   │   ├── 2024.05/                    ← Created by date_sort
│   │   │   ├── Theme1/                 ← Manually created thematic folder
│   │   │   │   ├── image.JPG
│   │   │   │   ├── RAW/                ← Created by raw_sort
│   │   │   │   └── Subtheme1/          ← Manual sub-folder
│   │   │   │       ├── image2.JPG
│   │   │   │       └── RAW/
│   │   │   └── …
│   │   └── …
│   ├── PRIVATE/                        ← Destination for “(X)” folders
├── scan_exif_v2.1_estable_final.PY
├── model_sort_v2.3_estable_final.PY
├── date_sor_v1.2_estable_final.PY
├── raw_sort_v1.3_estable_final.PY
├── dup_search_v2.4_estable_tested_final.PY
├── copiar_private_v1.4_estable_final.py
└── stats_developing.py            ← Experimental statistics (use with caution)

````

> **Note:** The `CAMARAS/<Model>/` hierarchy and any thematic or sub-thematic folders must be created manually before running the relevant scripts.

---

## Prerequisites

- **Python**: 3.6 or newer  
- **ExifTool**: Installed and available in `PATH`  
- **Python dependencies**:
  ```bash
  pip install fpdf pillow

---

## Script Reference

1. **Scan EXIF & Extensions**

   ```bash
   python3 scripts/scan_exif_v2.1_estable_final.PY
   ```

   * Recurses through `CAMARAS/` (including subfolders).
   * Extracts `Model` EXIF tag and file extensions, noting videos without EXIF.
   * Outputs `.txt` summary in `logs/` and a PDF report in `pdf/`.

2. **Model-Based Sorting**

   ```bash
   python3 scripts/model_sort_v2.3_estable_final.PY
   ```

   * Reads `MODEL_TO_FOLDER` mapping in the script.
   * Moves files into `CAMARAS/<Model>/` based on EXIF `Model`.
   * Logs unmapped or missing-destination items.
   * Detects intra-folder SHA-256 duplicates and skips them.
   * Generates full metrics and duplicate lists in both `logs/` and `pdf/`.

3. **Date-Based Organization**

   ```bash
   python3 scripts/date_sort_v1.2_estable_final.PY
   ```

   * Select target camera model folders.
   * Creates `YYYY.MM/` subfolders per capture date (EXIF `DateTimeOriginal` or file timestamp).
   * Treats files captured on the 1st before 08:00 as belonging to the previous month.
   * Skips and logs filename collisions.
   * Produces operation logs and a PDF summary.

4. **RAW File Grouping**

   ```bash
   python3 scripts/raw_sort_v1.3_estable_final.PY
   ```

   * Processes each thematic and sub-thematic folder under selected camera model(s).
   * Moves RAW files (`.cr2`, `.cr3`, `.arw`) into a `RAW/` subfolder.
   * Skips folders without RAW content.
   * Logs actions and errors; outputs a TXT and PDF report.

5. **Exact Duplicate Detection**

   ```bash
   python3 scripts/dup_search_v2.4_estable_tested_final.PY
   ```

   * Ignores the `PRIVATE/` directory.
   * Within each model folder, groups by filename and extension.
   * Calculates SHA-256 only for repeated names to identify real duplicates.
   * Generates a detailed duplicates list in `logs/` and a formatted PDF.

6. **Copy “(X)”-Marked Folders**

   ```bash
   python3 scripts/copiar_private_v1.4_estable_final.py
   ```

   * Creates `CAMARAS/PRIVATE/` if absent.
   * Recursively copies any folder whose name contains `(X)`, preserving the path.
   * Does not overwrite existing destinations.
   * Logs copy operations, skips, and errors; produces TXT and PDF summaries.

7. **Global Statistics (Experimental)**

   ```bash
   python3 scripts/stats_developing.py
   ```

   * Generates charts and a PDF report covering the entire media collection.
   * Functionality under development—use with caution.

---

## Recommended Workflow

1. **Setup**

   * Create `CAMARAS/` and `scripts/` at project root.
   * Install prerequisites.

2. **Import Media**

   * Copy all files from camera SD cards into `CAMARAS/` (no subfolders).

3. **Inventory**

   * Run **scan\_exif\_v2.1** to catalog models and extensions.

4. **Model Classification**

   * Update `MODEL_TO_FOLDER` in **model\_sort\_v2.3**, then execute it.

5. **Date Organization**

   * Run **date\_sort\_v1.2** to generate monthly folders.

6. **Folder Structure**

   * Manually create thematic and sub-thematic folders inside each `YYYY.MM/`.

7. **RAW Consolidation**

   * Execute **raw\_sort\_v1.3** to collect RAW files into `RAW/` subfolders.

8. **Duplicate Cleanup**

   * Run **dup\_search\_v2.4** to identify and review true duplicates.

9. **Private Extraction**

   * Use **copiar\_private\_v1.4** to move `(X)`-tagged folders into `PRIVATE/`.

10. **Full Statistics (Optional)**

    * Run **stats\_developing.py** for a global overview.

---

## Error Handling & Logging

* **Missing ExifTool**: EXIF-based scripts will terminate with an error.
* **Permission Denied**: Affected files/folders are skipped and logged.
* **Unmapped EXIF Model**: Files remain in place; entries appear in logs.
* **Detected Duplicates**: Files are skipped to prevent overwrites; duplicates listed in reports.
* **Missing Destination Folder**: The item is skipped and recorded in the log.
* **No Movements**: date\_sort logs “no changes” if no files qualify.

All operations write detailed logs under `logs/` and generate styled PDF summaries under `pdf/` for audit and record-keeping.
