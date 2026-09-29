"""
Konfigurasi Global & Pengaturan Sistem Analitik Transportasi Nataru.
Mendukung variabel lingkungan (.env) dengan fallback default lokal.
"""

import os
import subprocess
from typing import Dict, Any, Optional

# Direktori Dasar Proyek
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Muat file .env secara manual jika python-dotenv belum terpasang atau langsung dari file
def _load_env_file():
    env_file = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
        except Exception:
            pass

_load_env_file()

# Konfigurasi Koneksi MySQL (Default XAMPP)
MYSQL_CONFIG: Dict[str, Any] = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "database_nataru"),
    "charset": os.getenv("DB_CHARSET", "utf8mb4")
}

# Path File Data & Database
SQLITE_DB_PATH = os.path.join(BASE_DIR, "nataru_analytics.db")

EXCEL_DATA_PATH = os.path.join(BASE_DIR, "Data Asli dan cleaning SurveyNataru20252026_Kirim.xlsx")
SQL_DUMP_PATH = os.path.join(BASE_DIR, "Database_Nataru.sql")

# Direktori & Path Caching Apache Parquet
DATA_CACHE_DIR = os.path.join(BASE_DIR, os.getenv("PARQUET_CACHE_DIR", "data_cache"))
PARQUET_CLEANED_PATH = os.path.join(DATA_CACHE_DIR, "nataru_cleaned.parquet")
PARQUET_KPI_PATH = os.path.join(DATA_CACHE_DIR, "nataru_kpi_cache.parquet")

# Direktori Output Grafik Visual & Laporan
CHARTS_DIR = os.path.join(BASE_DIR, "grafik_analisis_nataru")
REPORT_PATH = os.path.join(BASE_DIR, "Laporan_Analisis_Nataru.txt")

# Pastikan folder penting ada
os.makedirs(DATA_CACHE_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

def find_mysql_cli() -> Optional[str]:
    """Mencari path binary mysql.exe di berbagai direktori XAMPP umum atau PATH sistem."""
    possible_paths = [
        r"d:\for xampp\mysql\bin\mysql.exe",
        r"c:\xampp\mysql\bin\mysql.exe",
        r"d:\xampp\mysql\bin\mysql.exe",
        r"e:\xampp\mysql\bin\mysql.exe",
        r"c:\program files\mysql\mysql server 8.0\bin\mysql.exe"
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return p
    # Cek di PATH sistem
    try:
        res = subprocess.run(["where", "mysql.exe"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            if lines:
                return lines[0].strip()
    except Exception:
        pass
    return None
