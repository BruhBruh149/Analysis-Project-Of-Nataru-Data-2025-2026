"""
========================================================================================================
SISTEM ANALITIK TRANSPORTASI PUBLIK & PIPELINE ELT NATARU
========================================================================================================
Entrypoint Utama (CLI Runner & Dashboard Launcher).
Seluruh logika inti telah dimodularisasi ke dalam paket `nataru`:
- nataru.config: Pengaturan basis data, environment, dan koordinat geospasial
- nataru.database: Manajer basis data multi-engine (MySQL XAMPP & SQLite fallback)
- nataru.pipeline: Pipeline ELT, pembersihan data, star schema, dan Apache Parquet caching
- nataru.analytics: Kalkulasi KPI, IPA Matrix, K-Means Clustering, NLP & Early Warning
- nataru.visualization: Generator grafik publikasi (300 DPI) & peta interaktif OpenStreetMap GIS
- nataru.dashboard: Antarmuka visual analitis berbasis Streamlit & Plotly
========================================================================================================
"""

import os
import sys
import argparse
import subprocess

# Pastikan direktori root berada di sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Impor modul dari paket modular nataru
from nataru.config import (
    MYSQL_CONFIG, SQLITE_DB_PATH, EXCEL_DATA_PATH, SQL_DUMP_PATH,
    CHARTS_DIR, REPORT_PATH, find_mysql_cli,
    INDONESIA_REGIONS_GEO, MAJOR_HUBS_GEO
)
from nataru.database import NataruDBManager
from nataru.pipeline import NataruELTPipeline, clean_hub_name
from nataru.analytics import (
    NataruAnalytics, compute_kpi_summary, compute_key_drivers_and_ipa,
    run_passenger_clustering, generate_terminal_report, export_all_tables_to_csv
)
from nataru.visualization import export_visualizations
from nataru.dashboard import render_dashboard
from tests.run_tests import run_self_tests

def main():
    parser = argparse.ArgumentParser(description="Sistem Analitik Pipeline ELT & Dashboard Nataru")
    parser.add_argument("--pipeline", action="store_true", help="Jalankan Pipeline ELT Pemrosesan & Pembersihan Data secara otomatis tanpa UI")
    parser.add_argument("--dashboard", action="store_true", help="Buka Dashboard Analitik Interaktif Streamlit")
    parser.add_argument("--status", action="store_true", help="Cek status database dan jumlah data")
    parser.add_argument("--sqlite", action="store_true", help="Paksa gunakan SQLite lokal (nataru_analytics.db) alih-alih MySQL XAMPP")
    parser.add_argument("--analytics", "--report", action="store_true", dest="analytics", help="Jalankan analisis langsung dari script/terminal dan cetak laporan eksekutif lengkap")
    parser.add_argument("--export-csv", action="store_true", help="Ekspor seluruh tabel dimensi, fakta, dan views hasil pemodelan ke folder CSV")
    parser.add_argument("--clustering", action="store_true", help="Jalankan segmentasi persona penumpang K-Means dan tampilkan ringkasan di terminal")
    parser.add_argument("--visualize", "--charts", "--plots", action="store_true", dest="visualize", help="Generate seluruh grafik visual (gambar PNG resolusi tinggi & HTML interaktif) langsung dari script")
    parser.add_argument("--test", action="store_true", help="Jalankan pengujian unit otomatis komprehensif internal (self-test)")
    args = parser.parse_args()

    db_manager = NataruDBManager(force_sqlite=args.sqlite)

    # 0: Self-Tests Internal
    if args.test:
        success = run_self_tests(db_manager)
        sys.exit(0 if success else 1)

    # 1: Status Database
    if args.status:
        print(f"[STATUS] Database Engine: {db_manager.engine_type} (CLI Mode: {db_manager.use_cli})")
        try:
            df_cnt = db_manager.query("SELECT COUNT(*) as total FROM fakta_kepuasan_keseluruhan;")
            print(f"[STATUS] Data Fakta Kepuasan: {df_cnt['total'].iloc[0]:,} baris.")
        except Exception:
            print("[STATUS] Tabel fakta belum terbentuk. Jalankan --pipeline untuk memproses data.")
        return

    #  2: Headless ELT Pipeline
    if args.pipeline:
        print("[PIPELINE] Menjalankan Pipeline ELT Otomatis...")
        pipeline = NataruELTPipeline(db_manager)
        report = pipeline.run(force_reload=True)
        print(f"[PIPELINE] Selesai dengan sukses! Total data: {report.get('total_records', 0):,} baris dalam {report.get('elapsed_time_seconds', 0)} detik.")
        print("[REPORT] Otomatis memperbarui file Laporan_Analisis_Nataru.txt...")
        generate_terminal_report(db_manager, export_file=True)
        return

    # 3: Ekspor Tabel Analitik ke File CSV
    if args.export_csv:
        print("[EXPORT] Mengekspor seluruh tabel analitik ke CSV...")
        export_all_tables_to_csv(db_manager)
        print("[REPORT] Otomatis memperbarui file Laporan_Analisis_Nataru.txt...")
        generate_terminal_report(db_manager, export_file=True)
        return

    # 4: Segmentasi Persona Penumpang K-Means
    if args.clustering:
        print("[CLUSTERING] Menjalankan Segmentasi Persona Penumpang (K-Means Clustering)...")
        _, df_sum = run_passenger_clustering(db_manager, n_clusters=3)
        print("\n" + "="*85)
        print("           HASIL SEGMENTASI PERSONA PENUMPANG NATARU (K-MEANS)          ")
        print("="*85)
        print(df_sum.to_string(index=False))
        print("="*85 + "\n")
        print("[REPORT] Otomatis memperbarui file Laporan_Analisis_Nataru.txt...")
        generate_terminal_report(db_manager, export_file=True)
        return

    # 5: Analitik Langsung via Terminal (Eksekutif Report)
    if args.analytics:
        try:
            db_manager.query("SELECT 1 FROM fakta_kepuasan_keseluruhan LIMIT 1;")
        except Exception:
            print("[INFO] Tabel analitik belum siap. Menjalankan pipeline ELT terlebih dahulu...")
            pipeline = NataruELTPipeline(db_manager)
            pipeline.run()
        generate_terminal_report(db_manager, export_file=True)
        return

    #  6: Generate Visualisasi Grafik (PNG & HTML Interaktif)
    if args.visualize:
        try:
            db_manager.query("SELECT 1 FROM fakta_kepuasan_keseluruhan LIMIT 1;")
        except Exception:
            print("[INFO] Tabel analitik belum siap. Menjalankan pipeline ELT terlebih dahulu...")
            pipeline = NataruELTPipeline(db_manager)
            pipeline.run()
        export_visualizations(db_manager)
        print("[REPORT] Otomatis memperbarui file Laporan_Analisis_Nataru.txt...")
        generate_terminal_report(db_manager, export_file=True)
        return

    # Mode 7: Dashboard Launch vs Default Headless Process & Report
    is_streamlit_runner = os.environ.get("STREAMLIT_SERVER_PORT") is not None or "streamlit" in sys.argv[0]

    if is_streamlit_runner:
        render_dashboard(db_manager)
    elif args.dashboard:
        print("========================================================================")
        print("   MELUNCURKAN DASHBOARD ANALITIK NATARU           ")
        print("========================================================================")
        print(f"-> Database Terkoneksi: {db_manager.engine_type}")
        print("-> Tekan Ctrl + C di terminal ini untuk berhenti.\n")
        cmd = [sys.executable, "-m", "streamlit", "run", os.path.abspath(__file__)]
        if args.sqlite:
            cmd.extend(["--", "--sqlite"])
        subprocess.run(cmd)
        return
    else:
        print("========================================================================")
        print("   SISTEM ANALITIK TRANSPORTASI PUBLIK & PIPELINE ELT NATARU (Main.py)  ")
        print("========================================================================")
        print(f"-> Database Terkoneksi: {db_manager.engine_type}")

        # Cek apakah tabel sudah ada, jika belum jalankan pipeline sekali
        try:
            df_check = db_manager.query("SELECT COUNT(*) as total FROM fakta_kepuasan_keseluruhan;")
            if df_check.empty or df_check['total'].iloc[0] == 0:
                raise ValueError("Tabel kosong atau belum siap")
            print(f"-> Skema data terstruktur telah siap ({df_check['total'].iloc[0]:,} baris data).")
        except Exception:
            print("-> Menginisialisasi Pipeline ELT Otomatis & Pemodelan Data...")
            pipeline = NataruELTPipeline(db_manager)
            pipeline.run()
            print("-> Pipeline ELT berhasil disiapkan!")

        # Cek dan otomatis generate file grafik visual (PNG & HTML) jika belum ada di folder
        png_count = len([f for f in os.listdir(CHARTS_DIR) if f.endswith(".png")]) if os.path.exists(CHARTS_DIR) else 0
        if png_count < 12:
            print("-> [GENERATE] File grafik visual (PNG) belum lengkap, otomatis men-generate 12 grafik resolusi tinggi...")
            try:
                export_visualizations(db_manager)
                print(f"-> Seluruh file gambar grafik berhasil dibuat di: {CHARTS_DIR}")
            except Exception as e:
                print(f"Catatan saat membuat file grafik visual: {e}")
        else:
            print(f"-> [INFO] Grafik visual telah siap ({png_count} file gambar PNG di: {CHARTS_DIR}).")

        # Buat atau perbarui file laporan
        file_existed = os.path.exists(REPORT_PATH)
        status_action = "memperbarui isi" if file_existed else "mengenerate file baru"
        print(f"-> [REPORT] File Laporan_Analisis_Nataru.txt: {status_action}...")

        try:
            generate_terminal_report(db_manager, export_file=True)
            status_text = "berhasil diperbarui (update)" if file_existed else "berhasil dibuat (generate)"
            print(f"-> File hasil analisis {status_text} di: {REPORT_PATH}")
        except Exception as e:
            print(f"Catatan saat memproses laporan analitik: {e}")

        print("\n" + "=" * 80)
        print(" [SELESAI] Seluruh proses telah berhasil dijalankan.")
        print(f" [STATUS] File laporan: {'Diperbarui (Update)' if file_existed else 'Dibuat Baru (Generate)'}")
        print(f" [LOKASI] {REPORT_PATH}")
        print(" [INFO] Untuk membuka Dashboard Interaktif Streamlit di browser, jalankan:")
        print("        python Main.py --dashboard")
        print("=" * 80 + "\n")
        return

if __name__ == "__main__":
    main()