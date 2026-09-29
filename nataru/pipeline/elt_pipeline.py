"""
Pipeline ELT Terpadu (Extract, Load, Transform) Nataru.
Mendukung pembersihan data, standarisasi, pemisahan skala 6 "TIDAK TAHU",
pemodelan Star Schema, pembuatan SQL Views, serta Caching Format Apache Parquet.
"""

import os
import re
import time
import logging
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd
import numpy as np

from ..config.settings import (
    EXCEL_DATA_PATH, SQL_DUMP_PATH, PARQUET_CLEANED_PATH, DATA_CACHE_DIR
)
from ..database.db_manager import NataruDBManager
from .text_cleaner import clean_hub_name

logger = logging.getLogger("NataruAnalytics")

try:
    import openpyxl
    from openpyxl import load_workbook
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

class NataruELTPipeline:
    """
    Arsitektur Pipeline ELT End-to-End:
    - Extract: Mengambil data dari Parquet Cache (jika ada), Excel (openpyxl), MySQL `data_asli`, atau SQLite.
    - Transform: Pembersihan data, imputasi, standardisasi teks/tanggal, validasi Likert,
      pemisahan skala 6 ("TIDAK TAHU") untuk analisis literasi kebijakan, dan perhitungan CSI.
    - Load & Modeling: Pembentukan tabel relasional terstruktur (Star Schema), SQL Views, dan Parquet Caching.
    """

    def __init__(self, db_manager: NataruDBManager):
        self.db = db_manager
        self.raw_df = pd.DataFrame()
        self.cleaned_df = pd.DataFrame()
        self.quality_report: Dict[str, Any] = {}

    def extract(self, force_reload: bool = False) -> pd.DataFrame:
        """Tahap Ekstraksi (Extract): Membaca data mentah dari Cache Parquet, Excel, atau basis data."""
        logger.info("Memulai Tahap 1: Ekstraksi Data Mentah (Extract)...")

        # 1. Cek Apache Parquet Cache jika tidak diminta force_reload
        if not force_reload and os.path.exists(PARQUET_CLEANED_PATH):
            try:
                df_pq = pd.read_parquet(PARQUET_CLEANED_PATH)
                if not df_pq.empty and len(df_pq) > 100:
                    logger.info(f"Ekstraksi instan dari Apache Parquet Cache: {len(df_pq):,} baris data.")
                    self.raw_df = df_pq
                    return self.raw_df
            except Exception as e_pq:
                logger.warning(f"Catatan membaca cache Parquet: {e_pq}")

        # 2. Baca langsung dari Excel agar skala 6 'TIDAK TAHU' terjaga sempurna
        if os.path.exists(EXCEL_DATA_PATH) and OPENPYXL_AVAILABLE:
            logger.info(f"Mengekstrak data mentah langsung dari file Excel: {EXCEL_DATA_PATH}")
            try:
                t0 = time.time()
                wb = load_workbook(EXCEL_DATA_PATH, read_only=True, data_only=True)
                sheet = wb.active
                rows = list(sheet.iter_rows(values_only=True))
                header_excel = rows[0]
                data_rows = rows[1:]

                # Dapatkan mapping kolom standar dari kamus_data jika tersedia
                kamus_cols = None
                try:
                    df_kamus = self.db.query("SELECT nomor_kolom, nama_kolom_sql FROM kamus_data ORDER BY nomor_kolom;")
                    if not df_kamus.empty and len(df_kamus) == len(header_excel):
                        kamus_cols = df_kamus["nama_kolom_sql"].tolist()
                except Exception:
                    pass

                if not kamus_cols and os.path.exists(SQL_DUMP_PATH):
                    try:
                        with open(SQL_DUMP_PATH, 'r', encoding='utf-8', errors='ignore') as f_sql:
                            sql_chunk = f_sql.read(150000)
                        start_k = sql_chunk.find('INSERT INTO\n    `kamus_data`')
                        semi_k = sql_chunk.find(';', start_k)
                        if start_k != -1 and semi_k != -1:
                            self.db.execute("DROP TABLE IF EXISTS kamus_data;")
                            self.db.execute("CREATE TABLE IF NOT EXISTS kamus_data (nomor_kolom INTEGER PRIMARY KEY, kategori TEXT, nama_kolom_sql TEXT, tipe_data TEXT, label_asli_excel TEXT);")
                            self.db.execute(sql_chunk[start_k:semi_k+1])
                            df_kamus = self.db.query("SELECT nomor_kolom, nama_kolom_sql FROM kamus_data ORDER BY nomor_kolom;")
                            if not df_kamus.empty and len(df_kamus) == len(header_excel):
                                kamus_cols = df_kamus["nama_kolom_sql"].tolist()
                    except Exception as e_k:
                        logger.warning(f"Catatan inisialisasi kamus_data: {e_k}")

                if kamus_cols and len(kamus_cols) == len(header_excel):
                    col_names = kamus_cols
                else:
                    col_names = []
                    seen = {}
                    for h in header_excel:
                        h_clean = re.sub(r'[^a-zA-Z0-9_]', '_', str(h).strip().lower())
                        h_clean = re.sub(r'_+', '_', h_clean).strip('_')
                        if not h_clean:
                            h_clean = "kolom"
                        seen[h_clean] = seen.get(h_clean, 0) + 1
                        if seen[h_clean] > 1:
                            col_names.append(f"{h_clean}_{seen[h_clean]}")
                        else:
                            col_names.append(h_clean)

                self.raw_df = pd.DataFrame(data_rows, columns=col_names)
                if "id" not in self.raw_df.columns:
                    self.raw_df.insert(0, "id", range(1, len(self.raw_df) + 1))

                elapsed = round(time.time() - t0, 2)
                logger.info(f"Ekstraksi Excel sukses: {len(self.raw_df):,} baris dalam {elapsed} detik.")
                return self.raw_df
            except Exception as e:
                logger.warning(f"Gagal membaca langsung file Excel ({e}), mencoba membaca dari database...")

        # 2. Coba baca dari MySQL (tabel `data_asli`)
        if self.db.engine_type == "MYSQL":
            try:
                df = self.db.query("SELECT * FROM data_asli;")
                if not df.empty and len(df) > 100:
                    logger.info(f"Ekstraksi sukses dari MySQL `data_asli`: {len(df):,} baris data.")
                    self.raw_df = df
                    return self.raw_df
            except Exception as e:
                logger.warning(f"Gagal mengekstrak dari tabel MySQL `data_asli`: {e}")

        # 3. Coba baca dari SQLite
        try:
            df_sq = self.db._query_sqlite("SELECT * FROM data_asli;")
            if not df_sq.empty and len(df_sq) > 100:
                logger.info(f"Ekstraksi sukses dari SQLite `data_asli`: {len(df_sq):,} baris data.")
                self.raw_df = df_sq
                return self.raw_df
        except Exception:
            pass

        # 4. Coba baca dari Parquet jika ada
        if os.path.exists(PARQUET_CLEANED_PATH):
            try:
                df_pq = pd.read_parquet(PARQUET_CLEANED_PATH)
                if not df_pq.empty:
                    logger.info(f"Ekstraksi sukses dari Apache Parquet Cache: {len(df_pq):,} baris.")
                    self.raw_df = df_pq
                    return self.raw_df
            except Exception:
                pass

        raise FileNotFoundError("Data sumber survei Nataru tidak dapat diekstrak dari file Excel maupun basis data!")

    def clean_and_transform(self) -> pd.DataFrame:
        """
        Tahap Transformasi & Pembersihan Data (Clean & Transform):
        - Mengatasi missing values (imputasi / null handling)
        - Standarisasi nama moda dan teks kategori
        - Konversi tipe data tanggal & waktu
        - Pemisahan nilai skala 6 (TIDAK TAHU) pada kebijakan publik guna mengukur literasi
        - Validasi dan penyesuaian batas Skala Likert (1 - 5) untuk kinerja murni
        - Pemetaan rantai antarmoda first-mile, last-mile, waktu tunggu, dan captive riders
        - Perhitungan Customer Satisfaction Index (CSI) per individu
        - Audit kualitas data
        """
        logger.info("Memulai Tahap 2: Pembersihan Data & Transformasi (Clean & Transform)...")
        if self.raw_df.empty:
            self.extract()

        df = self.raw_df.copy()
        
        # Filter baris kosong/invalid di bagian akhir sheet excel
        if "moda_transportasi" in df.columns:
            df = df[df["moda_transportasi"].notnull() & 
                    (df["moda_transportasi"].astype(str).str.strip().str.lower() != "nan") & 
                    (df["moda_transportasi"].astype(str).str.strip() != "") &
                    (df["moda_transportasi"].astype(str).str.strip().str.lower() != "none")].copy()

        initial_nulls = int(df.isnull().sum().sum())

        # 1. Standarisasi Teks Kategori Utama
        string_cols = [
            "moda_transportasi", "asal_perjalanan", "tujuan_perjalanan",
            "domisili_asal", "domisili_tujuan_nataru", "jenis_kelamin",
            "pendidikan_terakhir", "pekerjaan", "pendapatan_per_bulan",
            "biaya_transportasi", "maksud_utama_perjalanan"
        ]
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].replace({"nan": "Tidak Diketahui", "None": "Tidak Diketahui", "NULL": "Tidak Diketahui", "": "Tidak Diketahui"})

        # Normalisasi nama moda transportasi
        if "moda_transportasi" in df.columns:
            moda_clean_map = {
                "Kendaraan Pribadi": "Kendaraan Pribadi",
                "Angkutan Umum (Jalan)": "Angkutan Umum (Bus)",
                "Angkutan Udara": "Angkutan Udara",
                "Kereta Api": "Kereta Api",
                "Angkutan Laut": "Angkutan Laut",
                "ASDP (Penyeberangan)": "ASDP (Penyeberangan)"
            }
            df["moda_transportasi"] = df["moda_transportasi"].map(lambda x: moda_clean_map.get(x, x))

        # 2. Standarisasi Tanggal dan Waktu
        date_cols = ["tanggal_keberangkatan", "tanggal_kedatangan", "waktu_survei"]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        # Standarisasi jumlah rombongan
        if "jumlah_anggota_rombongan" in df.columns:
            df["jumlah_anggota_rombongan"] = pd.to_numeric(df["jumlah_anggota_rombongan"], errors='coerce').fillna(1)
            df["jumlah_anggota_rombongan"] = df["jumlah_anggota_rombongan"].apply(lambda x: int(max(1, min(x, 50))))

        # 3. Penanganan Skala Evaluasi Layanan (eval_*) dan Kepuasan -> Strictly 1 to 5
        eval_cols = [c for c in df.columns if c.startswith("eval_")]
        kepuasan_cols = [c for c in df.columns if c.startswith("kepuasan_keseluruhan_")]
        for col in eval_cols + kepuasan_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                df.loc[(df[col] < 1) | (df[col] > 5), col] = np.nan

        # 4. Penanganan Kebijakan Publik (kebijakan_*) -> Jaga Skala 6 (TIDAK TAHU)
        kebijakan_cols = [c for c in df.columns if c.startswith("kebijakan_")]
        for col in kebijakan_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                df.loc[(df[col] < 1) | (df[col] > 6), col] = np.nan

        # 5. Konstruksi Skor Kepuasan Keseluruhan Gabungan
        def get_unified_satisfaction(row):
            moda = str(row.get("moda_transportasi", ""))
            if "Pribadi" in moda or "Jalan" in moda:
                val = row.get("kepuasan_keseluruhan_jalan")
                if pd.notnull(val): return float(val)
            if "Bus" in moda:
                val = row.get("kepuasan_keseluruhan_bus")
                if pd.notnull(val): return float(val)
            if "Kereta" in moda:
                val = row.get("kepuasan_keseluruhan_ka")
                if pd.notnull(val): return float(val)
            if "ASDP" in moda:
                val = row.get("kepuasan_keseluruhan_asdp")
                if pd.notnull(val): return float(val)
            if "Laut" in moda:
                val = row.get("kepuasan_keseluruhan_laut")
                if pd.notnull(val): return float(val)
            if "Udara" in moda:
                val = row.get("kepuasan_keseluruhan_udara")
                if pd.notnull(val): return float(val)

            for k in kepuasan_cols:
                v = row.get(k)
                if pd.notnull(v): return float(v)
            return np.nan

        df["skor_kepuasan_konsolidasi"] = df.apply(get_unified_satisfaction, axis=1)

        # Imputasi jika skor kepuasan kosong dengan rata-rata evaluasi layanan
        for idx, row in df[df["skor_kepuasan_konsolidasi"].isnull()].iterrows():
            row_evals = [row[c] for c in eval_cols if pd.notnull(row[c])]
            if row_evals:
                df.at[idx, "skor_kepuasan_konsolidasi"] = round(float(np.mean(row_evals)), 1)
            else:
                df.at[idx, "skor_kepuasan_konsolidasi"] = 3.5

        # Hitung CSI (Customer Satisfaction Index) Individu (%)
        df["indeks_csi_individu"] = (df["skor_kepuasan_konsolidasi"] / 5.0) * 100.0

        # Klasifikasi Kategori Kepuasan
        def categorize_csi(csi):
            if csi >= 85: return "Sangat Puas"
            elif csi >= 70: return "Puas"
            elif csi >= 55: return "Cukup Puas"
            elif csi >= 40: return "Kurang Puas"
            else: return "Tidak Puas"

        df["kategori_kepuasan"] = df["indeks_csi_individu"].apply(categorize_csi)

        # 6. Pembersihan Aksesibilitas First-Mile & Last-Mile
        fm_col = "laut_moda_first_mile" if "laut_moda_first_mile" in df.columns else None
        lm_col = "laut_moda_last_mile" if "laut_moda_last_mile" in df.columns else None

        df["moda_first_mile"] = df[fm_col].fillna("Tidak Menggunakan / Pribadi") if fm_col else "Tidak Diketahui"
        df["moda_last_mile"] = df[lm_col].fillna("Tidak Menggunakan / Pribadi") if lm_col else "Tidak Diketahui"

        # Standarisasi Waktu Menunggu
        if "waktu_menunggu_moda_jam" in df.columns:
            df["waktu_menunggu_moda"] = df["waktu_menunggu_moda_jam"].fillna("Tidak Ada / Pribadi")
        else:
            df["waktu_menunggu_moda"] = "Tidak Diketahui"

        # Standarisasi Captive vs Choice Riders
        if "is_moda_pilihan_utama" in df.columns:
            df["is_captive_rider"] = df["is_moda_pilihan_utama"].apply(lambda x: 1 if str(x).strip().lower() == "tidak" else 0)
        else:
            df["is_captive_rider"] = 0

        # Standarisasi masukan keluhan & saran perbaikan
        if "masalah_dan_evaluasi" not in df.columns:
            for c in df.columns:
                if any(k in c.lower() for k in ["permasalahan", "kurang_dan_perlu_diperbaiki", "keluhan"]):
                    df["masalah_dan_evaluasi"] = df[c]
                    break
            if "masalah_dan_evaluasi" not in df.columns:
                df["masalah_dan_evaluasi"] = "-"

        if "saran_perbaikan" not in df.columns:
            for c in df.columns:
                if any(k in c.lower() for k in ["saran_untuk_perbaikan", "saran_perbaikan"]):
                    df["saran_perbaikan"] = df[c]
                    break
            if "saran_perbaikan" not in df.columns:
                df["saran_perbaikan"] = "-"

        # 7. Audit Kualitas Data
        completeness_rate = round((1 - (df.isnull().sum().sum() / (len(df) * len(df.columns)))) * 100, 2)
        validity_rate = round((df["skor_kepuasan_konsolidasi"].notnull().sum() / len(df)) * 100, 2)

        self.quality_report = {
            "total_records": len(df),
            "total_columns": len(df.columns),
            "initial_nulls": initial_nulls,
            "completeness_score": completeness_rate,
            "validity_score": validity_rate,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        self.cleaned_df = df
        logger.info(f"Transformasi selesai. Kualitas Data: {completeness_rate}% Completeness, {validity_rate}% Validity.")

        # Simpan Cache Parquet untuk pemuatan cepat
        try:
            os.makedirs(DATA_CACHE_DIR, exist_ok=True)
            # Konversi kolom object yang memiliki tipe campuran ke string sebelum simpan parquet
            df_parquet = df.copy()
            for col in df_parquet.select_dtypes(include=['object']).columns:
                df_parquet[col] = df_parquet[col].astype(str)
            df_parquet.to_parquet(PARQUET_CLEANED_PATH, index=False)
            logger.info(f"Cache Parquet berhasil disimpan di: {PARQUET_CLEANED_PATH}")
        except Exception as e:
            logger.warning(f"Catatan penyimpanan cache Parquet: {e}")

        return df

    def create_database_models_and_load(self):
        """Membangun Star Schema relasional & Analytical SQL Views."""
        logger.info("Memulai Tahap 3: Pemodelan Basis Data Terstruktur & Load...")
        if self.cleaned_df.empty:
            self.clean_and_transform()

        df = self.cleaned_df.copy()
        if "id" not in df.columns:
            df["id"] = range(1, len(df) + 1)

        # 1. Tabel Dimensi Responden (dim_responden)
        dim_resp = pd.DataFrame({
            "id_responden": df["id"].astype(int),
            "domisili_asal": df.get("domisili_asal", "Tidak Diketahui"),
            "domisili_tujuan": df.get("domisili_tujuan_nataru", "Tidak Diketahui"),
            "rentang_usia": df.get("rentang_usia", "Tidak Diketahui"),
            "jenis_kelamin": df.get("jenis_kelamin", "Tidak Diketahui"),
            "pendidikan_terakhir": df.get("pendidikan_terakhir", "Tidak Diketahui"),
            "pekerjaan": df.get("pekerjaan", "Tidak Diketahui"),
            "pendapatan_per_bulan": df.get("pendapatan_per_bulan", "Tidak Diketahui"),
            "biaya_transportasi": df.get("biaya_transportasi", "Tidak Diketahui"),
            "biaya_non_transportasi": df.get("biaya_non_transportasi", "Tidak Diketahui")
        })

        # 2. Tabel Dimensi Perjalanan (dim_perjalanan)
        def get_simpul(row, is_asal=True):
            moda = str(row.get("moda_transportasi", ""))
            if "Bus" in moda:
                return row.get("bus_terminal_asal" if is_asal else "bus_terminal_tujuan", "")
            elif "Kereta" in moda:
                return row.get("ka_stasiun_asal" if is_asal else "ka_stasiun_tujuan", "")
            elif "ASDP" in moda:
                return row.get("asdp_pelabuhan_asal" if is_asal else "asdp_pelabuhan_tujuan", "")
            elif "Laut" in moda:
                return row.get("laut_pelabuhan_asal" if is_asal else "laut_pelabuhan_tujuan", "")
            elif "Udara" in moda:
                return row.get("udara_bandara_asal" if is_asal else "udara_bandara_tujuan", "")
            return "-"

        dim_perj = pd.DataFrame({
            "id_perjalanan": dim_resp["id_responden"],
            "id_responden": dim_resp["id_responden"],
            "moda_transportasi": df.get("moda_transportasi", "Lainnya"),
            "asal_perjalanan": df.get("asal_perjalanan", "Tidak Diketahui"),
            "tujuan_perjalanan": df.get("tujuan_perjalanan", "Tidak Diketahui"),
            "maksud_utama_perjalanan": df.get("maksud_utama_perjalanan", "Mudik / Liburan"),
            "jumlah_anggota_rombongan": df.get("jumlah_anggota_rombongan", 1),
            "tanggal_keberangkatan": pd.to_datetime(df["tanggal_keberangkatan"]).dt.strftime("%Y-%m-%d").fillna(""),
            "waktu_keberangkatan": df.get("waktu_keberangkatan", "").astype(str),
            "tanggal_kedatangan": pd.to_datetime(df["tanggal_kedatangan"]).dt.strftime("%Y-%m-%d").fillna(""),
            "waktu_kedatangan": df.get("waktu_kedatangan", "").astype(str),
            "is_moda_pilihan_utama": df.get("is_moda_pilihan_utama", "Ya"),
            "is_captive_rider": df.get("is_captive_rider", 0),
            "alasan_tidak_pilih_moda_utama": df.get("alasan_tidak_pilih_moda_utama", "-"),
            "moda_utama_sebenarnya": df.get("moda_utama_sebenarnya", "-"),
            "waktu_menunggu_moda": df.get("waktu_menunggu_moda", "Tidak Diketahui"),
            "moda_first_mile": df.get("moda_first_mile", "Tidak Diketahui"),
            "moda_last_mile": df.get("moda_last_mile", "Tidak Diketahui"),
            "simpul_asal": df.apply(lambda r: clean_hub_name(get_simpul(r, True)), axis=1),
            "simpul_tujuan": df.apply(lambda r: clean_hub_name(get_simpul(r, False)), axis=1)
        })

        # 3. Tabel Fakta Evaluasi Mutu Pelayanan Multi-Moda (fakta_evaluasi_moda)
        def extract_eval_metrics(row):
            m = str(row.get("moda_transportasi", ""))
            if "Kereta" in m:
                fasil = row.get("eval_ka_stasiun_fasilitas")
                aman = row.get("eval_ka_stasiun_keamanan")
                akses = row.get("eval_ka_stasiun_aksesibilitas")
                petugas = row.get("eval_ka_stasiun_petugas")
                tepat = row.get("eval_ka_ketepatan_waktu")
                nyaman = row.get("eval_ka_gerbong_kenyamanan")
                selamat = row.get("eval_ka_gerbong_keselamatan")
                awak = row.get("eval_ka_crew_layanan")
            elif "Bus" in m:
                fasil = row.get("eval_bus_terminal_fasilitas")
                aman = row.get("eval_bus_terminal_keamanan")
                akses = row.get("eval_bus_terminal_aksesibilitas")
                petugas = row.get("eval_bus_terminal_petugas")
                tepat = row.get("eval_bus_ketepatan_waktu")
                nyaman = row.get("eval_bus_armada_kenyamanan")
                selamat = row.get("eval_bus_armada_keselamatan")
                awak = row.get("eval_bus_sopir_awak")
            elif "ASDP" in m:
                fasil = row.get("eval_asdp_pelabuhan_fasilitas")
                aman = row.get("eval_asdp_pelabuhan_keamanan")
                akses = row.get("eval_asdp_pelabuhan_akses")
                petugas = row.get("eval_asdp_pelabuhan_petugas")
                tepat = row.get("eval_asdp_ketepatan_waktu")
                nyaman = row.get("eval_asdp_kapal_fasilitas")
                selamat = row.get("eval_asdp_kapal_keselamatan")
                awak = row.get("eval_asdp_crew_kapal")
            elif "Laut" in m:
                fasil = row.get("eval_laut_pelabuhan_fasilitas")
                aman = row.get("eval_laut_pelabuhan_keamanan")
                akses = row.get("eval_laut_pelabuhan_akses")
                petugas = row.get("eval_laut_pelabuhan_petugas")
                tepat = row.get("eval_laut_ketepatan_waktu")
                nyaman = row.get("eval_laut_kapal_fasilitas")
                selamat = row.get("eval_laut_kapal_keselamatan")
                awak = row.get("eval_laut_crew_kapal")
            elif "Udara" in m:
                fasil = row.get("eval_udara_terminal_fasilitas")
                aman = row.get("eval_udara_bandara_keamanan")
                akses = row.get("eval_udara_bandara_akses")
                petugas = row.get("eval_udara_gate_petugas")
                tepat = row.get("eval_udara_ketepatan_waktu")
                nyaman = row.get("eval_udara_pesawat_kenyamanan")
                selamat = row.get("eval_udara_pesawat_keselamatan")
                awak = row.get("eval_udara_crew_pesawat")
            else: # Kendaraan Pribadi
                fasil = row.get("eval_pribadi_spbu_spklu")
                aman = row.get("eval_pribadi_rambu_marka")
                akses = row.get("eval_pribadi_rest_area")
                petugas = np.nan
                tepat = np.nan
                nyaman = row.get("eval_pribadi_rest_area")
                selamat = row.get("eval_pribadi_rambu_marka")
                awak = np.nan

            p_prasarana = [v for v in [fasil, aman, akses] if pd.notnull(v)]
            p_sarana = [v for v in [nyaman, selamat] if pd.notnull(v)]
            p_manajemen = [v for v in [tepat, petugas, awak] if pd.notnull(v)]

            skor_prasarana = round(float(np.mean(p_prasarana)), 2) if p_prasarana else np.nan
            skor_sarana = round(float(np.mean(p_sarana)), 2) if p_sarana else np.nan
            skor_manajemen = round(float(np.mean(p_manajemen)), 2) if p_manajemen else np.nan

            all_vals = [v for v in [fasil, aman, akses, petugas, tepat, nyaman, selamat, awak] if pd.notnull(v)]
            avg_eval = round(float(np.mean(all_vals)), 2) if all_vals else np.nan

            return pd.Series([
                fasil, aman, akses, petugas, tepat, nyaman, selamat, awak,
                skor_prasarana, skor_sarana, skor_manajemen, avg_eval
            ])

        eval_series = df.apply(extract_eval_metrics, axis=1)
        eval_series.columns = [
            "skor_fasilitas_simpul", "skor_keamanan", "skor_aksesibilitas",
            "skor_petugas", "skor_ketepatan_waktu", "skor_kenyamanan_armada",
            "skor_keselamatan_armada", "skor_layanan_awak",
            "skor_pilar_prasarana", "skor_pilar_sarana", "skor_pilar_manajemen",
            "rata_rata_evaluasi"
        ]

        fakta_eval = pd.concat([
            pd.DataFrame({"id_evaluasi": dim_resp["id_responden"], "id_responden": dim_resp["id_responden"], "moda_transportasi": df["moda_transportasi"]}),
            eval_series
        ], axis=1)

        # 4. Tabel Fakta Efektivitas Kebijakan Sektor Transportasi (fakta_kebijakan_nataru)
        def extract_policy_metrics(row):
            m = str(row.get("moda_transportasi", ""))
            if "Kereta" in m:
                t_online = row.get("kebijakan_ka_tiket_online")
                tarif = row.get("kebijakan_ka_tarif_terjangkau")
                jadwal = row.get("kebijakan_ka_manajemen_jadwal")
                selamat = row.get("kebijakan_ka_sosialisasi_keselamatan")
                info = row.get("kebijakan_ka_akurasi_info_jadwal")
                rekayasa = np.nan
                diskon = row.get("kebijakan_ka_diskon_tiket")
                posko = row.get("kebijakan_ka_posko_nataru")
            elif "Bus" in m:
                t_online = row.get("kebijakan_bus_tiket_online")
                tarif = row.get("kebijakan_bus_tarif_terjangkau")
                jadwal = row.get("kebijakan_bus_manajemen_jadwal")
                selamat = row.get("kebijakan_bus_sosialisasi_keselamatan")
                info = row.get("kebijakan_bus_akurasi_info_jadwal")
                rekayasa = row.get("kebijakan_bus_one_way") or row.get("kebijakan_bus_contra_flow")
                diskon = row.get("kebijakan_bus_mudik_gratis")
                posko = row.get("kebijakan_bus_posko_nataru")
            elif "ASDP" in m:
                t_online = row.get("kebijakan_asdp_tiket_online")
                tarif = row.get("kebijakan_asdp_tarif_terjangkau")
                jadwal = row.get("kebijakan_asdp_manajemen_jadwal")
                selamat = row.get("kebijakan_asdp_sosialisasi_keselamatan")
                info = row.get("kebijakan_asdp_akurasi_info_jadwal")
                rekayasa = row.get("kebijakan_asdp_rekayasa_lalin_pelabuhan")
                diskon = row.get("kebijakan_asdp_diskon_15")
                posko = row.get("kebijakan_asdp_posko_nataru")
            elif "Laut" in m:
                t_online = row.get("kebijakan_laut_tiket_online")
                tarif = row.get("kebijakan_laut_tarif_terjangkau")
                jadwal = row.get("kebijakan_laut_manajemen_jadwal")
                selamat = row.get("kebijakan_laut_sosialisasi_keselamatan")
                info = row.get("kebijakan_laut_akurasi_info_jadwal")
                rekayasa = row.get("kebijakan_laut_rerouting_kapal")
                diskon = row.get("kebijakan_laut_diskon_20_dan_gratis")
                posko = row.get("kebijakan_laut_posko_nataru")
            elif "Udara" in m:
                t_online = row.get("kebijakan_udara_tiket_online")
                tarif = row.get("kebijakan_udara_tarif_terjangkau")
                jadwal = row.get("kebijakan_udara_manajemen_jadwal")
                selamat = row.get("kebijakan_udara_sosialisasi_keselamatan")
                info = row.get("kebijakan_udara_akurasi_info_penerbangan")
                rekayasa = row.get("kebijakan_udara_extra_flight")
                diskon = row.get("kebijakan_udara_penurunan_harga_tiket")
                posko = row.get("kebijakan_udara_posko_nataru")
            else: # Kendaraan Pribadi
                t_online = np.nan
                tarif = np.nan
                jadwal = np.nan
                selamat = row.get("kebijakan_jalan_sosialisasi_keselamatan")
                info = row.get("kebijakan_jalan_info_rekayasa_lalin")
                rekayasa = row.get("kebijakan_jalan_one_way") or row.get("kebijakan_jalan_contra_flow")
                diskon = row.get("kebijakan_jalan_mudik_gratis")
                posko = row.get("kebijakan_jalan_posko_nataru")

            raw_policies = [t_online, tarif, jadwal, selamat, info, rekayasa, diskon, posko]
            clean_policies = [v for v in raw_policies if pd.notnull(v) and v <= 5]
            avg_pol = round(float(np.mean(clean_policies)), 2) if clean_policies else np.nan

            tahu_cnt = sum(1 for v in raw_policies if pd.notnull(v) and v <= 5)
            ttahu_cnt = sum(1 for v in raw_policies if pd.notnull(v) and v == 6)

            def mask6(v):
                return v if (pd.notnull(v) and v <= 5) else np.nan

            return pd.Series([
                mask6(t_online), mask6(tarif), mask6(jadwal), mask6(selamat),
                mask6(info), mask6(rekayasa), mask6(diskon), mask6(posko),
                avg_pol, tahu_cnt, ttahu_cnt
            ])

        pol_series = df.apply(extract_policy_metrics, axis=1)
        pol_series.columns = [
            "skor_tiket_online", "skor_tarif_terjangkau", "skor_manajemen_jadwal",
            "skor_sosialisasi_keselamatan", "skor_akurasi_info", "skor_rekayasa_lalin",
            "skor_diskon_tiket", "skor_posko_nataru", "rata_rata_kebijakan_murni",
            "jumlah_kebijakan_tahu", "jumlah_kebijakan_tidak_tahu"
        ]

        fakta_kebijakan = pd.concat([
            pd.DataFrame({"id_kebijakan": dim_resp["id_responden"], "id_responden": dim_resp["id_responden"], "moda_transportasi": df["moda_transportasi"]}),
            pol_series
        ], axis=1)

        # 5. Tabel Fakta Literasi & Dampak Kebijakan Publik (fakta_literasi_kebijakan)
        key_policies_config = [
            ("kebijakan_ka_diskon_tiket", "Diskon Tiket Kereta Api", "Kereta Api"),
            ("kebijakan_ka_fakultatif_ekstra", "Armada Ekstra KA Fakultatif", "Kereta Api"),
            ("kebijakan_asdp_ferizy_radius_larangan", "Radius Tiket Online Ferizy 4,24 km", "ASDP (Penyeberangan)"),
            ("kebijakan_asdp_diskon_15", "Diskon Tarif ASDP 15%", "ASDP (Penyeberangan)"),
            ("kebijakan_asdp_penambahan_armada", "Penambahan Armada Kapal ASDP", "ASDP (Penyeberangan)"),
            ("kebijakan_asdp_rekayasa_lalin_pelabuhan", "Rekayasa Lalin Pelabuhan Penyeberangan", "ASDP (Penyeberangan)"),
            ("kebijakan_laut_diskon_20_dan_gratis", "Diskon Tiket Laut 20% & Tiket Gratis Timur", "Angkutan Laut"),
            ("kebijakan_laut_rerouting_kapal", "Perubahan Rute Kapal (Rerouting)", "Angkutan Laut"),
            ("kebijakan_udara_penurunan_harga_tiket", "Penurunan Harga Tiket Pesawat", "Angkutan Udara"),
            ("kebijakan_udara_extra_flight", "Penambahan Kapasitas Extra Flight", "Angkutan Udara"),
            ("kebijakan_jalan_contra_flow", "Penerapan Contra Flow Jalan Raya", "Kendaraan Pribadi"),
            ("kebijakan_jalan_one_way", "Penerapan One Way Jalan Raya", "Kendaraan Pribadi"),
            ("kebijakan_jalan_mudik_gratis", "Mudik Gratis Penumpang & Sepeda Motor", "Kendaraan Pribadi"),
            ("kebijakan_jalan_posko_nataru", "Pelayanan Posko Terpadu Nataru (Jalan)", "Kendaraan Pribadi"),
            ("kebijakan_bus_posko_nataru", "Pelayanan Posko Terpadu Nataru (Bus)", "Angkutan Umum (Bus)"),
            ("kebijakan_ka_posko_nataru", "Pelayanan Posko Terpadu Nataru (KA)", "Kereta Api"),
            ("kebijakan_asdp_posko_nataru", "Pelayanan Posko Terpadu Nataru (ASDP)", "ASDP (Penyeberangan)"),
            ("kebijakan_udara_posko_nataru", "Pelayanan Posko Terpadu Nataru (Udara)", "Angkutan Udara")
        ]

        lit_rows = []
        for col_name, pol_label, moda_lbl in key_policies_config:
            if col_name in df.columns:
                s_pol = pd.to_numeric(df[col_name], errors='coerce')
                valid_resp = s_pol.isin([1, 2, 3, 4, 5, 6])
                n_tot = int(valid_resp.sum())
                if n_tot > 0:
                    tahu_m = s_pol.isin([1, 2, 3, 4, 5])
                    ttahu_m = (s_pol == 6)
                    n_tahu = int(tahu_m.sum())
                    n_ttahu = int(ttahu_m.sum())
                    pct_aware = round((n_tahu / n_tot) * 100, 2)
                    pct_unaware = round((n_ttahu / n_tot) * 100, 2)
                    pure_score = round(float(s_pol[tahu_m].mean()), 2) if n_tahu > 0 else np.nan

                    sat_tahu = df.loc[tahu_m, "skor_kepuasan_konsolidasi"].dropna()
                    sat_ttahu = df.loc[ttahu_m, "skor_kepuasan_konsolidasi"].dropna()
                    mean_tahu = round(float(sat_tahu.mean()), 3) if not sat_tahu.empty else np.nan
                    mean_ttahu = round(float(sat_ttahu.mean()), 3) if not sat_ttahu.empty else np.nan
                    delta_sat = round(float(mean_tahu - mean_ttahu), 3) if (pd.notnull(mean_tahu) and pd.notnull(mean_ttahu)) else 0.0

                    s1, s2 = sat_tahu.std(), sat_ttahu.std()
                    n1, n2 = len(sat_tahu), len(sat_ttahu)
                    if n1 > 1 and n2 > 1 and (s1 > 0 or s2 > 0):
                        se = np.sqrt((s1**2 / n1) + (s2**2 / n2))
                        t_stat = round(float(delta_sat / se), 2) if se > 0 else 0.0
                    else:
                        t_stat = 0.0

                    sig_lbl = "Signifikan (p < 0.05)" if abs(t_stat) >= 1.96 else "Tidak Signifikan"

                    lit_rows.append({
                        "id_kebijakan": len(lit_rows) + 1,
                        "program_kebijakan": pol_label,
                        "sektor_moda": moda_lbl,
                        "total_responden": n_tot,
                        "jumlah_tahu": n_tahu,
                        "jumlah_tidak_tahu": n_ttahu,
                        "tingkat_kesadaran_pct": pct_aware,
                        "tingkat_tidak_tahu_pct": pct_unaware,
                        "skor_efektivitas_murni": pure_score,
                        "kepuasan_group_tahu": mean_tahu,
                        "kepuasan_group_tidak_tahu": mean_ttahu,
                        "delta_kepuasan": delta_sat,
                        "t_statistik": t_stat,
                        "signifikansi_dampak": sig_lbl
                    })

        fakta_literasi = pd.DataFrame(lit_rows)

        # 6. Tabel Fakta Kepuasan Keseluruhan & CSI (fakta_kepuasan_keseluruhan)
        fakta_kepuasan = pd.DataFrame({
            "id_kepuasan": dim_resp["id_responden"],
            "id_responden": dim_resp["id_responden"],
            "moda_transportasi": df["moda_transportasi"],
            "skor_kepuasan": df["skor_kepuasan_konsolidasi"],
            "indeks_csi": df["indeks_csi_individu"],
            "kategori_kepuasan": df["kategori_kepuasan"]
        })

        # 7. Tabel Fakta Masukan & Saran (fakta_masukan_saran)
        def categorize_feedback(text):
            t = str(text).lower()
            if any(k in t for k in ["jalan", "aspal", "stasiun", "toilet", "ruang tunggu", "fasilitas", "prasarana", "ac"]):
                return "Prasarana & Fasilitas"
            elif any(k in t for k in ["tiket", "harga", "tarif", "mahal", "diskon", "ferizy", "beli"]):
                return "Tiket & Tarif"
            elif any(k in t for k in ["macet", "delay", "jadwal", "antri", "antrean", "penumpukan", "waktu"]):
                return "Operasional & Ketepatan Waktu"
            elif any(k in t for k in ["petugas", "ramah", "keamanan", "sopir", "pelayanan"]):
                return "Layanan Petugas & Keamanan"
            return "Umum & Lainnya"

        masalah_s = df["masalah_dan_evaluasi"] if "masalah_dan_evaluasi" in df.columns else pd.Series(["-"] * len(df), index=df.index)
        saran_s = df["saran_perbaikan"] if "saran_perbaikan" in df.columns else pd.Series(["-"] * len(df), index=df.index)

        fakta_saran = pd.DataFrame({
            "id_masukan": dim_resp["id_responden"],
            "id_responden": dim_resp["id_responden"],
            "moda_transportasi": df["moda_transportasi"],
            "masalah_dan_evaluasi": masalah_s.fillna("-"),
            "saran_perbaikan": saran_s.fillna("-"),
            "kategori_isu": masalah_s.fillna("").apply(categorize_feedback)
        })

        # Simpan tabel ke database
        logger.info("Menulis tabel-tabel terstruktur ke database...")
        self.db.save_dataframe(dim_resp, "dim_responden")
        self.db.save_dataframe(dim_perj, "dim_perjalanan")
        self.db.save_dataframe(fakta_eval, "fakta_evaluasi_moda")
        self.db.save_dataframe(fakta_kebijakan, "fakta_kebijakan_nataru")
        self.db.save_dataframe(fakta_literasi, "fakta_literasi_kebijakan")
        self.db.save_dataframe(fakta_kepuasan, "fakta_kepuasan_keseluruhan")
        self.db.save_dataframe(fakta_saran, "fakta_masukan_saran")
        self.db.save_dataframe(df, "data_asli")

        # Buat SQL Views analitis terintegrasi
        views_script = """
        DROP VIEW IF EXISTS v_ringkasan_kepuasan_moda;
        CREATE VIEW v_ringkasan_kepuasan_moda AS
        SELECT 
            moda_transportasi,
            COUNT(*) AS total_responden,
            ROUND(AVG(skor_kepuasan), 2) AS rata_rata_kepuasan,
            ROUND(AVG(indeks_csi), 2) AS rata_rata_csi,
            ROUND((SUM(CASE WHEN skor_kepuasan >= 4 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 2) AS persentase_puas
        FROM fakta_kepuasan_keseluruhan
        WHERE moda_transportasi IS NOT NULL 
          AND LOWER(TRIM(moda_transportasi)) NOT IN ('nan', 'none', '', 'null', 'tidak diketahui')
        GROUP BY moda_transportasi;

        DROP VIEW IF EXISTS v_benchmarking_3_pilar;
        CREATE VIEW v_benchmarking_3_pilar AS
        SELECT
            moda_transportasi,
            COUNT(*) AS total_responden,
            ROUND(AVG(skor_pilar_prasarana), 2) AS avg_prasarana,
            ROUND(AVG(skor_pilar_sarana), 2) AS avg_sarana,
            ROUND(AVG(skor_pilar_manajemen), 2) AS avg_manajemen,
            ROUND(AVG(rata_rata_evaluasi), 2) AS skor_komposit_layanan
        FROM fakta_evaluasi_moda
        WHERE moda_transportasi IS NOT NULL 
          AND LOWER(TRIM(moda_transportasi)) NOT IN ('nan', 'none', '', 'null', 'tidak diketahui')
        GROUP BY moda_transportasi;

        DROP VIEW IF EXISTS v_efektivitas_kebijakan_nataru;
        CREATE VIEW v_efektivitas_kebijakan_nataru AS
        SELECT
            moda_transportasi,
            ROUND(AVG(skor_tiket_online), 2) AS avg_tiket_online,
            ROUND(AVG(skor_tarif_terjangkau), 2) AS avg_tarif_terjangkau,
            ROUND(AVG(skor_manajemen_jadwal), 2) AS avg_manajemen_jadwal,
            ROUND(AVG(skor_sosialisasi_keselamatan), 2) AS avg_sosialisasi_keselamatan,
            ROUND(AVG(skor_akurasi_info), 2) AS avg_akurasi_info,
            ROUND(AVG(skor_rekayasa_lalin), 2) AS avg_rekayasa_lalin,
            ROUND(AVG(skor_diskon_tiket), 2) AS avg_diskon_tiket,
            ROUND(AVG(skor_posko_nataru), 2) AS avg_posko_nataru,
            ROUND(AVG(rata_rata_kebijakan_murni), 2) AS indeks_efektivitas_murni
        FROM fakta_kebijakan_nataru
        WHERE moda_transportasi IS NOT NULL 
          AND LOWER(TRIM(moda_transportasi)) NOT IN ('nan', 'none', '', 'null', 'tidak diketahui')
        GROUP BY moda_transportasi;

        DROP VIEW IF EXISTS v_gap_evaluasi_layanan;
        CREATE VIEW v_gap_evaluasi_layanan AS
        SELECT
            moda_transportasi,
            ROUND(AVG(skor_fasilitas_simpul), 2) AS avg_fasilitas,
            ROUND(AVG(skor_keamanan), 2) AS avg_keamanan,
            ROUND(AVG(skor_aksesibilitas), 2) AS avg_aksesibilitas,
            ROUND(AVG(skor_petugas), 2) AS avg_petugas,
            ROUND(AVG(skor_ketepatan_waktu), 2) AS avg_ketepatan_waktu,
            ROUND(AVG(skor_kenyamanan_armada), 2) AS avg_kenyamanan,
            ROUND(AVG(skor_keselamatan_armada), 2) AS avg_keselamatan,
            ROUND(AVG(skor_layanan_awak), 2) AS avg_awak
        FROM fakta_evaluasi_moda
        WHERE moda_transportasi IS NOT NULL 
          AND LOWER(TRIM(moda_transportasi)) NOT IN ('nan', 'none', '', 'null', 'tidak diketahui')
        GROUP BY moda_transportasi;

        DROP VIEW IF EXISTS v_analisis_waktu_tunggu;
        CREATE VIEW v_analisis_waktu_tunggu AS
        SELECT
            p.waktu_menunggu_moda,
            COUNT(*) AS total_responden,
            ROUND(AVG(k.skor_kepuasan), 2) AS avg_skor_kepuasan,
            ROUND(AVG(k.indeks_csi), 2) AS avg_csi,
            ROUND(AVG(e.skor_ketepatan_waktu), 2) AS avg_ketepatan_waktu
        FROM dim_perjalanan p
        JOIN fakta_kepuasan_keseluruhan k ON p.id_responden = k.id_responden
        LEFT JOIN fakta_evaluasi_moda e ON p.id_responden = e.id_responden
        WHERE p.waktu_menunggu_moda IS NOT NULL AND p.waktu_menunggu_moda != 'Tidak Diketahui'
        GROUP BY p.waktu_menunggu_moda;

        DROP VIEW IF EXISTS v_analisis_captive_riders;
        CREATE VIEW v_analisis_captive_riders AS
        SELECT
            CASE WHEN p.is_captive_rider = 1 THEN 'Pengguna Terpaksa (Captive Rider)' ELSE 'Pilihan Utama (Choice Rider)' END AS segmen_pengguna,
            COUNT(*) AS total_responden,
            ROUND(AVG(k.skor_kepuasan), 2) AS avg_skor_kepuasan,
            ROUND(AVG(k.indeks_csi), 2) AS avg_csi,
            ROUND(AVG(e.rata_rata_evaluasi), 2) AS avg_evaluasi_layanan
        FROM dim_perjalanan p
        JOIN fakta_kepuasan_keseluruhan k ON p.id_responden = k.id_responden
        LEFT JOIN fakta_evaluasi_moda e ON p.id_responden = e.id_responden
        GROUP BY p.is_captive_rider;

        DROP VIEW IF EXISTS v_antarmoda_first_last_mile;
        CREATE VIEW v_antarmoda_first_last_mile AS
        SELECT
            p.moda_first_mile,
            p.moda_last_mile,
            COUNT(*) AS total_perjalanan,
            ROUND(AVG(e.skor_aksesibilitas), 2) AS avg_skor_aksesibilitas,
            ROUND(AVG(k.skor_kepuasan), 2) AS avg_skor_kepuasan
        FROM dim_perjalanan p
        JOIN fakta_kepuasan_keseluruhan k ON p.id_responden = k.id_responden
        LEFT JOIN fakta_evaluasi_moda e ON p.id_responden = e.id_responden
        WHERE p.moda_first_mile IS NOT NULL 
          AND p.moda_first_mile != 'Tidak Diketahui' 
          AND p.moda_first_mile != 'Tidak Menggunakan / Pribadi'
        GROUP BY p.moda_first_mile, p.moda_last_mile;
        """
        try:
            self.db.execute_script(views_script)
            logger.info("Seluruh SQL Views analitis berhasil dimodelkan dan diperbarui.")
        except Exception as e:
            logger.warning(f"Catatan saat membuat SQL views: {e}")

    def run(self, force_reload: bool = False) -> Dict[str, Any]:
        """Menjalankan siklus Pipeline ELT secara otomatis dari awal hingga akhir."""
        start_time = time.time()
        logger.info("=== MEMULAI EKSEKUSI PIPELINE ELT NATARU OTOMATIS ===")
        self.extract(force_reload=force_reload)
        self.clean_and_transform()
        self.create_database_models_and_load()
        elapsed = round(time.time() - start_time, 2)
        logger.info(f"=== PIPELINE ELT SUKSES SELESAI DALAM {elapsed} DETIK ===")
        self.quality_report["elapsed_time_seconds"] = elapsed
        return self.quality_report
