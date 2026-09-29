"""
Matriks Key Driver Analysis & Importance-Performance Analysis (IPA).
Menghitung korelasi Pearson, bobot regresi OLS, serta klasifikasi 4 Kuadran IPA.
"""

from typing import Tuple, Dict, Any, List
import pandas as pd
import numpy as np

def compute_key_drivers_and_ipa(db_manager) -> Tuple[pd.DataFrame, float, float]:
    """
    Menghitung Key Driver Analysis (Korelasi Pearson & OLS Regression) serta Kuadran IPA.
    Mengembalikan DataFrame IPA, Grand Mean Performance, dan Grand Mean Importance.
    """
    df_eval = db_manager.query("SELECT * FROM fakta_evaluasi_moda;")
    df_kep = db_manager.query("SELECT id_responden, skor_kepuasan FROM fakta_kepuasan_keseluruhan;")
    df_merged = pd.merge(df_eval, df_kep, on="id_responden")

    dim_configs = [
        ("skor_fasilitas_simpul", "Fasilitas Simpul (Terminal/Stasiun/Bandara/SPBU)", "Prasarana"),
        ("skor_keamanan", "Keamanan Simpul & Lingkungan Perjalanan", "Prasarana"),
        ("skor_aksesibilitas", "Aksesibilitas & Kemudahan Transportasi Penghubung", "Prasarana"),
        ("skor_kenyamanan_armada", "Kenyamanan Armada (Kabin/Gerbong/Kapal/Rest Area)", "Sarana"),
        ("skor_keselamatan_armada", "Standar Keselamatan Fisik Sarana Armada", "Sarana"),
        ("skor_ketepatan_waktu", "Ketepatan Waktu Operasional (Punctuality)", "Manajemen Operasional"),
        ("skor_petugas", "Keramahan & Kesiapan Petugas Lapangan/Gate", "Manajemen Operasional"),
        ("skor_layanan_awak", "Kualitas Layanan Sopir / Awak Kendaraan / Crew", "Manajemen Operasional")
    ]

    results = []
    for col, label, pilar in dim_configs:
        valid_idx = df_merged[col].notnull() & df_merged["skor_kepuasan"].notnull()
        sub = df_merged[valid_idx]
        x_sub = sub[col].values
        y_sub = sub["skor_kepuasan"].values
        r = float(np.corrcoef(x_sub, y_sub)[0, 1]) if len(x_sub) > 1 else 0.0
        mean_perf = float(np.mean(x_sub)) if len(x_sub) > 0 else 0.0

        # OLS slope b
        var_x = np.var(x_sub)
        slope = (np.cov(x_sub, y_sub)[0, 1] / var_x) if var_x > 0 else 0.0

        results.append({
            "kode_atribut": col,
            "indikator_layanan": label,
            "pilar_layanan": pilar,
            "kinerja_performance": round(mean_perf, 3),
            "kepentingan_importance": round(r, 4),
            "koefisien_regresi_beta": round(slope, 3)
        })

    df_ipa = pd.DataFrame(results)
    grand_perf = round(float(df_ipa["kinerja_performance"].mean()), 3)
    grand_imp = round(float(df_ipa["kepentingan_importance"].mean()), 4)

    def assign_quadrant(row):
        p = row["kinerja_performance"]
        i = row["kepentingan_importance"]
        if p < grand_perf and i >= grand_imp:
            return "Kuadran I (Prioritas Utama / Concentrate Here)"
        elif p >= grand_perf and i >= grand_imp:
            return "Kuadran II (Pertahankan Prestasi / Keep Up Good Work)"
        elif p < grand_perf and i < grand_imp:
            return "Kuadran III (Prioritas Rendah / Low Priority)"
        else:
            return "Kuadran IV (Berlebihan / Possible Overkill)"

    df_ipa["kuadran_ipa"] = df_ipa.apply(assign_quadrant, axis=1)
    return df_ipa, grand_perf, grand_imp
