"""
Skrip Pengujian Unit Otomatis & Verifikasi Integritas Sistem Analitik Nataru.
"""

import os
import sys

# Tambahkan direktori root ke path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from nataru.config.settings import CHARTS_DIR, PARQUET_CLEANED_PATH
from nataru.database.db_manager import NataruDBManager
from nataru.pipeline.elt_pipeline import NataruELTPipeline
from nataru.analytics import (
    compute_kpi_summary,
    compute_key_drivers_and_ipa,
    run_passenger_clustering,
    compute_elbow_and_silhouette,
    extract_complaint_topics,
    extract_ngram_frequency,
    analyze_aspect_based_sentiment,
    predict_dissatisfaction_risks,
    predict_single_scenario,
    get_sankey_od_data
)
from nataru.visualization.chart_exporter import export_visualizations
from nataru.visualization.map_builder import build_sankey_od_diagram

# Pastikan encoding UTF-8 aman untuk konsol Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def run_self_tests(db_manager: NataruDBManager) -> bool:
    """Menjalankan rangkaian pengujian otomatis internal untuk memverifikasi fungsionalitas sistem."""
    passed = 0
    total = 0

    def check(condition: bool, test_name: str):
        nonlocal passed, total
        total += 1
        status = "BERHASIL (PASS)" if condition else "GAGAL (FAIL)"
        symbol = "[V]" if condition else "[X]"
        print(f"  {symbol} [{total:02d}] {test_name:<65}: {status}")
        if condition:
            passed += 1

    print("\n" + "="*80)
    print("      MEMULAI PENGUJIAN INTEGRITAS & UNIT TEST SISTEM NATARU ANALYTICS")
    print("="*80)

    # 1. Test Koneksi Basis Data
    print("\n1. Menguji Konektivitas Basis Data Multi-Engine:")
    check(db_manager.engine_type in ["MYSQL", "SQLITE"], f"Engine Database Terdeteksi: {db_manager.engine_type}")
    try:
        df_ping = db_manager.query("SELECT 1 AS ping;")
        check(not df_ping.empty and df_ping['ping'].iloc[0] == 1, "Eksekusi Kueri Ping SQL Berhasil")
    except Exception as e:
        check(False, f"Eksekusi Kueri Ping SQL Berhasil ({e})")

    # 2. Test Skema Data & Star Schema
    print("\n2. Menguji Integritas Skema Data (Star Schema & Dimensions):")
    req_tables = [
        "dim_responden", "dim_perjalanan", "fakta_evaluasi_moda",
        "fakta_kebijakan_nataru", "fakta_literasi_kebijakan", "fakta_kepuasan_keseluruhan"
    ]
    for tbl in req_tables:
        try:
            df_t = db_manager.query(f"SELECT COUNT(*) as n FROM `{tbl}`;")
            count_val = df_t['n'].iloc[0] if not df_t.empty else 0
            check(count_val > 0, f"Tabel `{tbl}` terisi data ({count_val:,} baris)")
        except Exception:
            check(False, f"Tabel `{tbl}` terisi data")

    # 3. Test K-Means Passenger Clustering & PCA
    print("\n3. Menguji Algoritma K-Means Persona Clustering & PCA 2D:")
    df_clustered, df_summary = run_passenger_clustering(db_manager, n_clusters=3)
    check(not df_clustered.empty, "Dataframe clustering terisi data responden")
    check('persona_label' in df_clustered.columns, "Kolom persona_label terbentuk")
    check(len(df_summary) == 3, "Tepat 3 segmen persona terbentuk")
    check('pca_x' in df_clustered.columns and 'pca_y' in df_clustered.columns, "Proyeksi 2D PCA (pca_x, pca_y) berhasil dihitung")
    
    df_elbow = compute_elbow_and_silhouette(db_manager, max_k=4)
    check(not df_elbow.empty and len(df_elbow) >= 3, f"Elbow Method & Silhouette dihitung untuk k={len(df_elbow)} nilai")

    # 4. Test Key Driver & IPA Matrix
    print("\n4. Menguji Mesin Key Drivers & Matriks Prioritas IPA:")
    df_ipa, gp, gi = compute_key_drivers_and_ipa(db_manager)
    check(not df_ipa.empty, "Matriks evaluasi IPA berhasil dihitung")
    check(gp > 0 and gi > 0, "Grand mean kinerja dan kepentingan bernilai valid")

    # 5. Test Topic Modeling, N-gram, ABSA, & Sankey OD Flow
    print("\n5. Menguji NLP N-gram, Sentimen ABSA, & Diagram Alir Sankey:")
    try:
        df_sar = db_manager.query("SELECT masalah_dan_evaluasi FROM fakta_masukan_saran;")
        df_topics = extract_complaint_topics(df_sar["masalah_dan_evaluasi"])
        check(not df_topics.empty and len(df_topics) >= 5, f"Topic Modeling mendeteksi {len(df_topics)} klaster keluhan")
        
        df_bg = extract_ngram_frequency(df_sar["masalah_dan_evaluasi"], n=2, top_n=10)
        check(not df_bg.empty and len(df_bg) >= 5, f"Bi-gram Mining menghasilkan {len(df_bg)} frasa keluhan spesifik")

        df_absa = analyze_aspect_based_sentiment(df_sar["masalah_dan_evaluasi"])
        check(not df_absa.empty and len(df_absa) == 3, "ABSA berhasil mengevaluasi sentimen pada 3 Pilar Layanan")

        sankey_data = get_sankey_od_data(db_manager, level="provinsi", top_n=12)
        check(len(sankey_data.get("node_labels", [])) > 0, f"Sankey OD Matrix membentuk {len(sankey_data.get('values', []))} koneksi aliran")
    except Exception as e:
        check(False, f"Pengujian NLP & Sankey lanjutan ({e})")

    # 6. Test Supervised Machine Learning & Early Warning Predictor
    print("\n6. Menguji Model Supervised Machine Learning (Random Forest):")
    try:
        pred_risk = predict_dissatisfaction_risks(db_manager)
        check(pred_risk["total_responden"] > 0, f"Model ML menghitung risiko responden ({pred_risk['high_risk_pct']}% high-risk)")
        metrics = pred_risk.get("model_metrics", {})
        check(metrics.get("roc_auc", 0) > 0.80, f"Evaluasi ML mencapai ROC-AUC: {metrics.get('roc_auc', 0):.3f} (> 0.80)")

        # Test single scenario prediction
        scen_out = predict_single_scenario({"wait_min": 120, "is_captive_rider": 1, "skor_fasilitas": 2.0}, db_manager)
        check(scen_out.get("risk_percentage", 0) > 40.0, f"Kalkulator Skenario Individual memprediksi risiko ({scen_out.get('risk_percentage')}% - {scen_out.get('risk_category')})")
    except Exception as e:
        check(False, f"Pengujian ML Random Forest ({e})")

    # 7. Test Visualizer Engine (12 Charts)
    print("\n7. Menguji Mesin Visualisasi Grafis (12 Chart Publikasi):")
    out_charts = export_visualizations(db_manager)
    png_list = [f for f in os.listdir(out_charts) if f.endswith(".png")]
    check(len(png_list) >= 12, f"Terbentuk {len(png_list)} file grafik resolusi tinggi (minimal 12)")

    print("\n" + "="*80)
    print(f"  HASIL AKHIR: {passed} DARI {total} PENGUJIAN BERHASIL ({'SEMUA LULUS 100%' if passed == total else 'ADA KEGAGALAN'})")
    print("="*80 + "\n")
    return passed == total


if __name__ == "__main__":
    db = NataruDBManager()
    success = run_self_tests(db)
    sys.exit(0 if success else 1)
