# StocX — Demo Backup & Portable Package Guide

**Prepared by:** Anay Tiwari (Data Engineer)  
**Date:** 2026-10-30  
**Version:** 1.0.0 (Phase 2 Demo Package)  

---

## 1. What is in this `demo_backup/` Folder?

This directory is an isolated, self-contained demonstration package for presentations, judge pitches, and backup purposes:

```text
demo_backup/
├── data/                         # Complete offline dataset archive (24 historical CSVs, fundamentals, lot sizes)
├── screenshots/                  # High-resolution screenshots of the dashboard
│   └── dashboard_main.png        # Full-page Streamlit application view
├── recordings/                   # Dedicated destination for demo screen recordings
│   └── stocx_demo_run.mp4        # Saved recording from Win + Alt + R
├── OFFLINE_TEST_REPORT.md        # Complete offline & Wi-Fi resilience audit report
├── DEMO_RECORDING_SCRIPT.md      # 60-second live presentation & recording script
├── BACKUP_README.md              # This instruction manual
└── run_offline_demo.bat          # One-click Windows batch launcher for live presentation
```

---

## 2. Security & Exclusions

To ensure zero risk of credential exposure during portability, the following are **strictly excluded**:
- ❌ `.env` (Zero API keys, zero secrets).
- ❌ `.venv/` (Excluded; virtual environments must not be copied across machines).
- ❌ `.git/` (Excluded to save storage space on USB / mobile).
- ❌ Temporary caches (`__pycache__`, `.pytest_cache`).

---

## 3. How to Copy to USB Drive

1. Insert your USB flash drive into your machine.
2. Open PowerShell and run:
   ```powershell
   Copy-Item -Recurse -Path "demo_backup" -Destination "E:\StocX_Demo_Backup"
   ```
   *(Replace `E:\` with your USB drive letter).*
3. Verify that `demo_backup/data/` contains all 24 CSVs and `demo_backup/screenshots/` contains the screenshot.

---

## 4. How to Copy to Phone

### For Android:
1. Connect your phone via USB cable and select **File Transfer / MTP mode**.
2. Open Windows File Explorer and navigate to your phone's internal storage (e.g. `This PC\Pixel\Internal storage\Documents`).
3. Drag and drop the `demo_backup/` folder (or just `demo_backup/screenshots/` and `demo_backup/recordings/` to view charts/videos directly on your phone).

### For iPhone:
1. AirDrop / iCloud Drive / Google Drive the `demo_backup/screenshots/` and `demo_backup/recordings/` folder for rapid review during the hackathon pitch.

---

## 5. How to Run on a New Presentation Laptop

If you need to run the demo live on a judge's or team member's laptop:
1. Ensure Python 3.11+ is installed.
2. In terminal:
   ```bash
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
3. Run the one-click launcher:
   ```cmd
   demo_backup\run_offline_demo.bat
   ```
4. Access the dashboard at `http://localhost:8501`.
