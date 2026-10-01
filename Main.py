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
import time
import socket
import argparse
import subprocess
import webbrowser

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

def is_port_listening(port=8501, host="127.0.0.1"):
    """Mengecek apakah port web server sudah dalam status mendengarkan (listening)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False

def launch_dashboard(force_sqlite=False, foreground=False):
    """Meluncurkan server dashboard Streamlit dan membuka browser."""
    port = 8501
    url = f"http://localhost:{port}"

    if is_port_listening(port):
        print("========================================================================")
        print("   SERVER DASHBOARD SUDAH AKTIF                                         ")
        print("========================================================================")
        print(f"-> Dashboard telah berjalan di: {url}")
        print("-> Membuka antarmuka dashboard di browser Anda...")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        print("-> Terminal Anda tetap bebas dan siap digunakan.")
        print("-> Untuk mematikan server dashboard nantinya, jalankan:")
        print("   python Main.py --stop-dashboard")
        print("========================================================================\n")
        return

    cmd = [sys.executable, "-m", "streamlit", "run", os.path.abspath(__file__), "--server.headless=true"]
    if force_sqlite:
        cmd.extend(["--", "--sqlite"])

    if foreground:
        print("========================================================================")
        print("   MELUNCURKAN DASHBOARD ANALITIK NATARU (MODE LIVE TERMINAL)           ")
        print("========================================================================")
        print(f"-> Server aktif di: {url}")
        print("-> Terminal ini menjaga server tetap aktif untuk melayani browser.")
        print("-> Tekan [Ctrl + C] kapan saja untuk berhenti dan kembali ke prompt terminal.")
        print("========================================================================\n")
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print("\n[INFO] Dashboard dihentikan. Terminal telah kembali bebas.")
        return

    # Mode Latar Belakang (Detached Background) - Standar Default
    print("========================================================================")
    print("   MELUNCURKAN DASHBOARD ANALITIK NATARU                                ")
    print("========================================================================")
    print("-> Menginisialisasi server web Streamlit di latar belakang...")

    log_path = os.path.join(BASE_DIR, "dashboard.log")
    log_file = open(log_path, "a", encoding="utf-8")

    if sys.platform == "win32":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        proc = subprocess.Popen(
            cmd,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.DEVNULL,
            close_fds=True
        )
    else:
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.DEVNULL,
            start_new_session=True
        )

    # Tunggu sebentar hingga server siap merespon
    print("-> Menunggu inisialisasi server...")
    started = False
    for _ in range(12):
        time.sleep(0.5)
        if is_port_listening(port):
            started = True
            break

    print(f"-> Server Dashboard aktif di background (PID: {proc.pid})")
    print(f"-> Alamat URL: {url}")
    print("-> Membuka dashboard otomatis di browser...")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    print(f"-> Catatan log tersimpan di: {log_path}")
    print("-> Terminal Anda telah langsung bebas kembali dan siap menerima perintah baru.")
    print("-> Untuk mematikan server dashboard kapan saja, jalankan:")
    print("   python Main.py --stop-dashboard")
    print("========================================================================\n")

def stop_running_dashboard():
    """Menghentikan seluruh proses server dashboard Streamlit yang berjalan."""
    print("========================================================================")
    print("   MENGHENTIKAN SERVER DASHBOARD STREAMLIT NATARU                       ")
    print("========================================================================")
    stopped = 0
    curr_pid = os.getpid()
    if sys.platform == "win32":
        try:
            ps_cmd = (
                "Get-CimInstance Win32_Process -Filter \"name = 'python.exe'\" | "
                "Where-Object { $_.CommandLine -like '*streamlit*run*' -or $_.CommandLine -like '*Main.py*--dashboard*' } | "
                "Select-Object -ExpandProperty ProcessId"
            )
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
            for line in res.stdout.strip().splitlines():
                line = line.strip()
                if line.isdigit() and int(line) != curr_pid:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", line], capture_output=True)
                    stopped += 1
        except Exception as e:
            print(f"[ERROR] Gagal menghentikan dashboard: {e}")
    else:
        try:
            res = subprocess.run(["pgrep", "-f", "streamlit run"], capture_output=True, text=True)
            for line in res.stdout.strip().splitlines():
                if line.strip().isdigit() and int(line.strip()) != curr_pid:
                    os.kill(int(line.strip()), 9)
                    stopped += 1
        except Exception as e:
            print(f"[ERROR] Gagal menghentikan dashboard: {e}")

    if stopped > 0:
        print(f"[STATUS] Sukses: Berhasil menghentikan {stopped} proses server dashboard.")
    else:
        print("[STATUS] Tidak ditemukan proses server dashboard aktif yang sedang berjalan.")
    print("-> Terminal telah kembali bebas dan siap digunakan.\n")
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Sistem Analitik Pipeline ELT & Dashboard Nataru")
    parser.add_argument("--pipeline", action="store_true", help="Jalankan Pipeline ELT Pemrosesan & Pembersihan Data secara otomatis tanpa UI")
    parser.add_argument("--dashboard", action="store_true", help="Buka Dashboard Analitik Interaktif Streamlit (otomatis latar belakang & buka browser)")
    parser.add_argument("--live", "--foreground", action="store_true", dest="live", help="Jalankan dashboard di mode foreground (live terminal logs)")
    parser.add_argument("--background", "--bg", "--detach", action="store_true", dest="background", help="Jalankan dashboard di latar belakang (default)")
    parser.add_argument("--stop-dashboard", "--kill-dashboard", action="store_true", dest="stop_dashboard", help="Hentikan server dashboard Streamlit yang sedang berjalan")
    parser.add_argument("--status", action="store_true", help="Cek status database dan jumlah data")
    parser.add_argument("--sqlite", action="store_true", help="Paksa gunakan SQLite lokal (nataru_analytics.db) alih-alih MySQL XAMPP")
    parser.add_argument("--analytics", "--report", action="store_true", dest="analytics", help="Jalankan analisis langsung dari script/terminal dan cetak laporan eksekutif lengkap")
    parser.add_argument("--export-csv", action="store_true", help="Ekspor seluruh tabel dimensi, fakta, dan views hasil pemodelan ke folder CSV")
    parser.add_argument("--clustering", action="store_true", help="Jalankan segmentasi persona penumpang K-Means dan tampilkan ringkasan di terminal")
    parser.add_argument("--visualize", "--charts", "--plots", action="store_true", dest="visualize", help="Generate seluruh grafik visual (gambar PNG resolusi tinggi & HTML interaktif) langsung dari script")
    parser.add_argument("--test", action="store_true", help="Jalankan pengujian unit otomatis komprehensif internal (self-test)")
    args = parser.parse_args()

    # Opsi Hentikan Dashboard yang Sedang Berjalan
    if args.stop_dashboard:
        stop_running_dashboard()

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
        sys.exit(0)

    # 2: Headless ELT Pipeline
    if args.pipeline:
        print("[PIPELINE] Menjalankan Pipeline ELT Otomatis...")
        pipeline = NataruELTPipeline(db_manager)
        report = pipeline.run(force_reload=True)
        print(f"[PIPELINE] Selesai dengan sukses! Total data: {report.get('total_records', 0):,} baris dalam {report.get('elapsed_time_seconds', 0)} detik.")
        print("[REPORT] Otomatis memperbarui file Laporan_Analisis_Nataru.txt...")
        generate_terminal_report(db_manager, export_file=True)
        sys.exit(0)

    # 3: Ekspor Tabel Analitik ke File CSV
    if args.export_csv:
        print("[EXPORT] Mengekspor seluruh tabel analitik ke CSV...")
        export_all_tables_to_csv(db_manager)
        print("[REPORT] Otomatis memperbarui file Laporan_Analisis_Nataru.txt...")
        generate_terminal_report(db_manager, export_file=True)
        sys.exit(0)

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
        sys.exit(0)

    # 5: Analitik Langsung via Terminal (Eksekutif Report)
    if args.analytics:
        try:
            db_manager.query("SELECT 1 FROM fakta_kepuasan_keseluruhan LIMIT 1;")
        except Exception:
            print("[INFO] Tabel analitik belum siap. Menjalankan pipeline ELT terlebih dahulu...")
            pipeline = NataruELTPipeline(db_manager)
            pipeline.run()
        generate_terminal_report(db_manager, export_file=True)
        sys.exit(0)

    # 6: Generate Visualisasi Grafik (PNG & HTML Interaktif)
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
        sys.exit(0)

    # Mode 7: Deteksi Runtime Streamlit vs CLI Runner
    try:
        import streamlit as st
        is_streamlit_runner = st.runtime.exists()
    except Exception:
        is_streamlit_runner = False

    if is_streamlit_runner:
        render_dashboard(db_manager)
        return
    elif args.dashboard:
        launch_dashboard(force_sqlite=args.sqlite, foreground=args.live)
        sys.exit(0)
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
        print("        python Main.py --dashboard        (otomatis latar belakang & terminal bebas)")
        print("        python Main.py --dashboard --live (mode live terminal)")
        print("=" * 80 + "\n")
        sys.exit(0)

if __name__ == "__main__":
    main()