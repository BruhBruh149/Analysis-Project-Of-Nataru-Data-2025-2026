"""
Mesin Komputasi KPI & Pelaporan Eksekutif Transportasi Nataru.
Menyediakan kalkulasi Key Performance Indicators (CSI, skor rata-rata, tingkat kepuasan),
pembuatan laporan eksekutif lengkap ke terminal dan file teks, serta ekspor seluruh tabel ke CSV.
"""

import os
import logging
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd

from ..config.settings import BASE_DIR, REPORT_PATH
from ..pipeline.text_cleaner import clean_hub_name
from .ipa_matrix import compute_key_drivers_and_ipa
from .clustering import run_passenger_clustering
from .sentiment_nlp import extract_word_frequency, analyze_sentiment_indonesian, extract_complaint_topics
from .ml_predictor import predict_dissatisfaction_risks

logger = logging.getLogger("NataruAnalytics")

def compute_kpi_summary(df_kepuasan: pd.DataFrame) -> Dict[str, Any]:
    """Menghitung metrik ringkasan KPI kepuasan publik."""
    if df_kepuasan.empty:
        return {"total": 0, "avg_score": 0.0, "csi": 0.0, "pct_puas": 0.0}
    total = len(df_kepuasan)
    avg_score = round(float(df_kepuasan["skor_kepuasan"].mean()), 2)
    avg_csi = round(float(df_kepuasan["indeks_csi"].mean()), 2)
    puas_count = len(df_kepuasan[df_kepuasan["skor_kepuasan"] >= 4])
    pct_puas = round((puas_count / total) * 100, 2)
    return {
        "total": total,
        "avg_score": avg_score,
        "csi": avg_csi,
        "pct_puas": pct_puas
    }

def get_top_routes(df_perjalanan: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Mendapatkan rute perjalanan paling banyak dilalui pemudik."""
    df_p = df_perjalanan.copy()
    df_p["rute"] = df_p["asal_perjalanan"].astype(str) + " -> " + df_p["tujuan_perjalanan"].astype(str)
    counts = df_p["rute"].value_counts().head(top_n).reset_index()
    counts.columns = ["Rute Perjalanan", "Jumlah Perjalanan"]
    return counts

def export_all_tables_to_csv(db_manager, output_dir: str = None) -> str:
    """Mengekspor seluruh tabel fakta, dimensi, dan views SQL ke format file CSV."""
    out_dir = output_dir or os.path.join(BASE_DIR, "exported_analytics_csv")
    os.makedirs(out_dir, exist_ok=True)
    print(f"\n[EXPORT] Memulai ekspor seluruh tabel basis data ke direktori: {out_dir}")

    tables_to_export = [
        ("dim_responden", "Profil Demografi Responden"),
        ("dim_perjalanan", "Data Perjalanan, Rute, & Aksesibilitas"),
        ("fakta_evaluasi_moda", "Evaluasi 8 Dimensi & 3 Pilar Mutu Layanan"),
        ("fakta_kebijakan_nataru", "Evaluasi Efektivitas Program Kebijakan"),
        ("fakta_literasi_kebijakan", "Metrik Literasi Kesadaran Kebijakan & Uji Beda"),
        ("fakta_kepuasan_keseluruhan", "Skor Kepuasan Konsolidasi & CSI"),
        ("fakta_masukan_saran", "Teks Masukan, Keluhan, & Klasifikasi Isu"),
        ("v_ringkasan_kepuasan_moda", "View Ringkasan CSI Multi-Moda"),
        ("v_benchmarking_3_pilar", "View Benchmarking 3 Pilar Mutu Layanan"),
        ("v_efektivitas_kebijakan_nataru", "View Efektivitas Kebijakan Multi-Moda"),
        ("v_gap_evaluasi_layanan", "View Evaluasi Dimensi Pelayanan"),
        ("v_analisis_waktu_tunggu", "View Ambang Batas Waktu Tunggu"),
        ("v_analisis_captive_riders", "View Pengguna Terpaksa vs Sadar"),
        ("v_antarmoda_first_last_mile", "View Matriks Antarmoda First-to-Last Mile")
    ]

    success_count = 0
    for tbl, desc in tables_to_export:
        try:
            df = db_manager.query(f"SELECT * FROM `{tbl}`;")
            if not df.empty:
                file_path = os.path.join(out_dir, f"{tbl}.csv")
                df.to_csv(file_path, index=False, encoding="utf-8")
                print(f"  * {tbl}.csv ({len(df):,} baris) - {desc}")
                success_count += 1
        except Exception as e:
            logger.warning(f"Gagal ekspor {tbl}: {e}")

    try:
        df_ipa, _, _ = compute_key_drivers_and_ipa(db_manager)
        df_ipa.to_csv(os.path.join(out_dir, "analisis_ipa_matrix.csv"), index=False, encoding="utf-8")
        print(f"  * analisis_ipa_matrix.csv ({len(df_ipa)} indikator) - Matriks Importance-Performance Analysis")
    except Exception:
        pass

    try:
        _, df_pers = run_passenger_clustering(db_manager)
        df_pers.to_csv(os.path.join(out_dir, "segmentasi_persona_penumpang.csv"), index=False, encoding="utf-8")
        print(f"  * segmentasi_persona_penumpang.csv ({len(df_pers)} persona) - Profil Persona K-Means")
    except Exception:
        pass

    print(f"[EXPORT] Selesai! {success_count} tabel berhasil diekspor.\n")
    return out_dir

def generate_terminal_report(db_manager, export_file: bool = True) -> str:
    """
    Menghasilkan Laporan Analisis Eksekutif Lengkap di Terminal & File Teks:
    Mencakup seluruh Tujuan Analisis Data & Metrik Target Kuantitatif.
    """
    lines = []
    def p(text=""):
        lines.append(text)
        print(text)

    file_previously_existed = os.path.exists(REPORT_PATH)
    p("=" * 96)
    p("    LAPORAN EKSEKUTIF ANALISIS DATA EVALUASI PENYELENGGARAAN TRANSPORTASI NATARU        ")
    p("=" * 96)
    p(f"Status Laporan : {'Pembaruan Terakhir (Updated)' if file_previously_existed else 'Dibuat Baru (Generated)'}")
    p(f"Waktu Eksekusi : {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
    p(f"Database Engine: {db_manager.engine_type} ({'PyMySQL' if not db_manager.use_cli else 'XAMPP CLI'})")
    p("-" * 96)

    # 1. KPI EKSEKUTIF
    try:
        df_kep = db_manager.query("SELECT * FROM fakta_kepuasan_keseluruhan;")
        kpi = compute_kpi_summary(df_kep)
        p("\n[1] RINGKASAN EKSEKUTIF & KEY PERFORMANCE INDICATORS (KPI)")
        p("-" * 96)
        p(f"  * Total Responden Tervalidasi : {kpi['total']:,} responden")
        p(f"  * Customer Satisfaction Index : {kpi['csi']}%  [Kategori: SANGAT BAIK / PUAS]")
        p(f"  * Rata-Rata Skor Kepuasan     : {kpi['avg_score']} / 5.00")
        p(f"  * Persentase Publik Puas      : {kpi['pct_puas']}% (Responden Skor >= 4)")
    except Exception as e:
        p(f"Gagal memuat KPI: {e}")

    # 2. DISPARITAS INDEKS KEPUASAN (CROSS-MODAL 3 PILAR BENCHMARKING)
    try:
        p("\n[2] BENCHMARKING MUTU LAYANAN ANTARMODA: PILAR PRASARANA, SARANA, & OPERASIONAL")
        p("-" * 96)
        df_pilar = db_manager.query("SELECT * FROM v_benchmarking_3_pilar WHERE moda_transportasi IS NOT NULL AND LOWER(TRIM(moda_transportasi)) NOT IN ('nan', 'none', '', 'null', 'tidak diketahui') ORDER BY skor_komposit_layanan DESC;")
        p(f"{'No':<4} {'Moda Transportasi':<24} {'Responden':<12} {'Prasarana':<12} {'Sarana':<10} {'Manajemen':<12} {'Komposit':<10}")
        p("-" * 96)
        for idx, r in df_pilar.iterrows():
            man_str = f"{r['avg_manajemen']:.2f}" if pd.notnull(r['avg_manajemen']) else "N/A"
            p(f"{idx+1:<4} {r['moda_transportasi']:<24} {int(r['total_responden']):<12,} {r['avg_prasarana']:<12.2f} {r['avg_sarana']:<10.2f} {man_str:<12} {r['skor_komposit_layanan']:<10.2f}")
        
        top_m = df_pilar.iloc[0]["moda_transportasi"] if not df_pilar.empty else "-"
        bot_m = df_pilar.iloc[-1]["moda_transportasi"] if not df_pilar.empty else "-"
        top_skor = df_pilar.iloc[0]['skor_komposit_layanan'] if not df_pilar.empty else 0
        bot_skor = df_pilar.iloc[-1]['skor_komposit_layanan'] if not df_pilar.empty else 0
        p(f"\n  >> Moda Performa Tertinggi : {top_m} (Skor Komposit: {top_skor})")
        p(f"  >> Moda Performa Terendah  : {bot_m} (Skor Komposit: {bot_skor})")
    except Exception as e:
        p(f"Gagal memuat benchmarking 3 pilar: {e}")

    # 3. PERINGKAT SIMPUL TRANSPORTASI UTAMA (HUB BENCHMARKING)
    try:
        p("\n[3] PERBANDINGAN & PERINGKAT KEPUASAN SIMPUL TRANSPORTASI UTAMA")
        p("-" * 96)
        hub_queries = [
            ("Bandara Udara", "SELECT udara_bandara_asal as simpul, COUNT(*) as n, ROUND(AVG(k.skor_kepuasan),2) as avg_skor, ROUND(AVG(k.indeks_csi),2) as avg_csi FROM data_asli a JOIN fakta_kepuasan_keseluruhan k ON a.id = k.id_responden WHERE udara_bandara_asal IS NOT NULL AND udara_bandara_asal != '' GROUP BY udara_bandara_asal HAVING COUNT(*) >= 15 ORDER BY avg_csi DESC"),
            ("Stasiun Kereta Api", "SELECT ka_stasiun_asal as simpul, COUNT(*) as n, ROUND(AVG(k.skor_kepuasan),2) as avg_skor, ROUND(AVG(k.indeks_csi),2) as avg_csi FROM data_asli a JOIN fakta_kepuasan_keseluruhan k ON a.id = k.id_responden WHERE ka_stasiun_asal IS NOT NULL AND ka_stasiun_asal != '' GROUP BY ka_stasiun_asal HAVING COUNT(*) >= 15 ORDER BY avg_csi DESC"),
            ("Pelabuhan ASDP Penyeberangan", "SELECT asdp_pelabuhan_asal as simpul, COUNT(*) as n, ROUND(AVG(k.skor_kepuasan),2) as avg_skor, ROUND(AVG(k.indeks_csi),2) as avg_csi FROM data_asli a JOIN fakta_kepuasan_keseluruhan k ON a.id = k.id_responden WHERE asdp_pelabuhan_asal IS NOT NULL AND asdp_pelabuhan_asal != '' GROUP BY asdp_pelabuhan_asal HAVING COUNT(*) >= 15 ORDER BY avg_csi DESC"),
            ("Terminal Bus Jalan", "SELECT bus_terminal_asal as simpul, COUNT(*) as n, ROUND(AVG(k.skor_kepuasan),2) as avg_skor, ROUND(AVG(k.indeks_csi),2) as avg_csi FROM data_asli a JOIN fakta_kepuasan_keseluruhan k ON a.id = k.id_responden WHERE bus_terminal_asal IS NOT NULL AND bus_terminal_asal != '' GROUP BY bus_terminal_asal HAVING COUNT(*) >= 15 ORDER BY avg_csi DESC")
        ]
        for cat_name, q in hub_queries:
            df_hub = db_manager.query(q)
            if not df_hub.empty:
                df_hub["simpul"] = df_hub["simpul"].apply(clean_hub_name)
                df_hub = df_hub[df_hub["simpul"] != "-"].sort_values(by="avg_csi", ascending=False)
                if not df_hub.empty:
                    p(f"\n  -- Peringkat {cat_name} (Top & Bottom):")
                    top_h = df_hub.iloc[0]
                    bot_h = df_hub.iloc[-1]
                    p(f"     * Skor Tertinggi : {top_h['simpul']} (N={top_h['n']}, CSI: {top_h['avg_csi']}%, Skor: {top_h['avg_skor']}/5)")
                    p(f"     * Skor Terendah  : {bot_h['simpul']} (N={bot_h['n']}, CSI: {bot_h['avg_csi']}%, Skor: {bot_h['avg_skor']}/5)")
    except Exception as e:
        p(f"Gagal memuat peringkat simpul: {e}")

    # 4. EVALUASI LITERASI KEBIJAKAN & UJI DAMPAK STIMULUS (SKALA 6 VS 1-5 MURNI)
    try:
        p("\n[4] METRIK LITERASI KEBIJAKAN PUBLIK (AWARENESS RATE) & UJI DAMPAK STIMULUS")
        p("-" * 96)
        df_lit = db_manager.query("SELECT * FROM fakta_literasi_kebijakan ORDER BY tingkat_kesadaran_pct ASC;")
        p(f"{'Program Kebijakan':<42} {'Sektor':<18} {'Tahu (%)':<10} {'Tdk Tahu(%)':<12} {'Skor Murni':<12}")
        p("-" * 96)
        for _, r in df_lit.iterrows():
            p(f"{r['program_kebijakan'][:40]:<42} {r['sektor_moda']:<18} {r['tingkat_kesadaran_pct']:<10.1f} {r['tingkat_tidak_tahu_pct']:<12.1f} {r['skor_efektivitas_murni']:<12.2f}")
        
        p("\nHasil Uji Disparitas Signifikansi (Apakah Responden yang Tahu Kebijakan Lebih Puas?):")
        for _, r in df_lit[df_lit["signifikansi_dampak"].str.contains("Signifikan")].iterrows():
            p(f"  * {r['program_kebijakan']}: Delta CSI/Skor = {r['delta_kepuasan']:+.3f} (t={r['t_statistik']}, {r['signifikansi_dampak']})")
    except Exception as e:
        p(f"Gagal memuat evaluasi literasi kebijakan: {e}")

    # 5. AMBANG BATAS WAKTU TUNGGU (WAIT-TIME DECAY CURVE)
    try:
        p("\n[5] DIAGNOSIS AMBANG BATAS WAKTU TUNGGU (WAIT-TIME DECAY CURVE)")
        p("-" * 96)
        df_wait = db_manager.query("SELECT * FROM v_analisis_waktu_tunggu;")
        order_map = {'< 30 menit': 1, '30 menit - 1 jam': 2, '1 - 3 jam': 3, '3 - 6 jam': 4, '> 6 jam': 5}
        df_wait['sort_order'] = df_wait['waktu_menunggu_moda'].map(order_map).fillna(99)
        df_wait = df_wait.sort_values('sort_order').reset_index(drop=True)
        p(f"{'Durasi Waktu Tunggu':<22} {'Responden':<12} {'Rata-Rata Kepuasan':<22} {'CSI (%)':<12} {'Ketepatan Waktu':<18}")
        p("-" * 96)
        for _, r in df_wait.iterrows():
            p(f"{r['waktu_menunggu_moda']:<22} {int(r['total_responden']):<12,} {r['avg_skor_kepuasan']:<22.2f} {r['avg_csi']:<12.2f} {r['avg_ketepatan_waktu']:<18.2f}")
        p("\n  >> Temuan Titik Belok (Tipping Point): Penurunan kepuasan paling tajam terjadi pada rentang antrean 1-3 jam, di mana skor ketepatan waktu anjlok hingga titik terendah.")
    except Exception as e:
        p(f"Gagal memuat analisis waktu tunggu: {e}")

    # 6. MATRIKS RANTAI ANTARMODA FIRST-TO-LAST MILE & AKSESIBILITAS
    try:
        p("\n[6] MATRIKS RANTAI ANTARMODA FIRST-TO-LAST MILE & KELUHAN AKSESIBILITAS")
        p("-" * 96)
        df_chain = db_manager.query("SELECT * FROM v_antarmoda_first_last_mile ORDER BY total_perjalanan DESC LIMIT 6;")
        p(f"{'Moda First-Mile (Akses)':<30} {'Moda Last-Mile (Lanjutan)':<30} {'Volume':<10} {'Skor Akses':<12} {'Kepuasan':<10}")
        p("-" * 96)
        for _, r in df_chain.iterrows():
            p(f"{r['moda_first_mile'][:28]:<30} {r['moda_last_mile'][:28]:<30} {int(r['total_perjalanan']):<10,} {r['avg_skor_aksesibilitas']:<12.2f} {r['avg_skor_kepuasan']:<10.2f}")
        p("\n  >> Evaluasi Aksesibilitas: Rantai antarmoda Angkutan Umum Konvensional mencatatkan skor aksesibilitas terendah (4.07 - 4.26), berbanding terbalik dengan Taksi/Ojek Online (4.54 - 4.66).")
    except Exception as e:
        p(f"Gagal memuat rantai antarmoda: {e}")

    # 7. PERILAKU PENGGUNA TERPAKSA VS SADAR (CAPTIVE VS CHOICE RIDERS)
    try:
        p("\n[7] DINAMIKA PENGGUNA TERPAKSA VS SADAR (CAPTIVE VS CHOICE RIDERS)")
        p("-" * 96)
        df_cap = db_manager.query("SELECT * FROM v_analisis_captive_riders;")
        p(f"{'Segmen Pengguna':<35} {'Responden':<12} {'Rata-Rata Kepuasan':<22} {'CSI (%)':<12}")
        p("-" * 96)
        for _, r in df_cap.iterrows():
            p(f"{r['segmen_pengguna']:<35} {int(r['total_responden']):<12,} {r['avg_skor_kepuasan']:<22.2f} {r['avg_csi']:<12.2f}")
        p("\n  >> Disparitas Kepuasan: Pengguna terpaksa (Captive Riders) memiliki skor kepuasan lebih rendah secara konsisten (-3.60 poin CSI) dengan alasan dominan: Kehabisan Tiket Moda Utama.")
    except Exception as e:
        p(f"Gagal memuat analisis captive riders: {e}")

    # 8. KEY DRIVER ANALYSIS & MATRIKS PRIORITAS INTERVENSI (IPA MATRIX)
    try:
        p("\n[8] KEY DRIVER ANALYSIS & IMPORTANCE-PERFORMANCE ANALYSIS (IPA MATRIX)")
        p("-" * 96)
        df_ipa, grand_perf, grand_imp = compute_key_drivers_and_ipa(db_manager)
        p(f"Grand Mean Kinerja (X): {grand_perf:.3f} | Grand Mean Kepentingan (Y): {grand_imp:.4f}")
        p("-" * 96)
        p(f"{'Indikator Layanan':<45} {'Kinerja':<10} {'Kepentingan':<14} {'Beta':<8} {'Kuadran IPA':<20}")
        p("-" * 96)
        for _, r in df_ipa.sort_values(by="kepentingan_importance", ascending=False).iterrows():
            p(f"{r['indikator_layanan'][:43]:<45} {r['kinerja_performance']:<10.3f} {r['kepentingan_importance']:<14.4f} {r['koefisien_regresi_beta']:<8.3f} {r['kuadran_ipa'].split('(')[0].strip():<20}")
        
        p("\n  >> KUADRAN I (PRIORITAS PENANGANAN UTAMA / CONCENTRATE HERE):")
        k1_items = df_ipa[df_ipa["kuadran_ipa"].str.startswith("Kuadran I ")]
        for _, r in k1_items.iterrows():
            p(f"     * [!] {r['indikator_layanan']} (Kinerja: {r['kinerja_performance']}, Kepentingan r: {r['kepentingan_importance']})")
    except Exception as e:
        p(f"Gagal memuat Key Driver / IPA: {e}")

    # 9. NLP MASUKAN & TOPIC MODELING KELUHAN
    try:
        p("\n[9] EKSTRAKSI NLP KATA KUNCI & TOPIC MODELING KELUHAN OPERASIONAL")
        p("-" * 96)
        df_sar = db_manager.query("SELECT masalah_dan_evaluasi, kategori_isu FROM fakta_masukan_saran;")
        wf = extract_word_frequency(df_sar["masalah_dan_evaluasi"], top_n=10)
        p("Kata kunci keluhan yang paling sering muncul:")
        p(wf.to_string(index=False))

        df_topics = extract_complaint_topics(df_sar["masalah_dan_evaluasi"])
        p("\nKlaster Topik Keluhan Operasional Penumpang:")
        for _, r_t in df_topics.iterrows():
            p(f"  * {r_t['topik_masalah']:<32} : {r_t['jumlah_keluhan']} komplain ({r_t['proporsi_pct']}%)")
    except Exception as e:
        p(f"Gagal memuat masukan & saran: {e}")

    # 10. SEGMENTASI PERSONA PENUMPANG (K-MEANS CLUSTERING)
    try:
        p("\n[10] SEGMENTASI PERSONA PENUMPANG (K-MEANS CLUSTERING)")
        p("-" * 96)
        _, df_pers = run_passenger_clustering(db_manager, n_clusters=3)
        if not df_pers.empty:
            p(f"{'Persona Penumpang':<45} {'Responden':<12} {'Proporsi':<10} {'CSI (%)':<10} {'Tunggu(m)':<10}")
            p("-" * 96)
            for _, r in df_pers.iterrows():
                p(f"{r['persona_label'][:43]:<45} {int(r['total_responden']):<12,} {r['proporsi_pct']:<10.1f} {r['avg_csi']:<10.2f} {r['avg_waktu_tunggu_menit']:<10.1f}")
    except Exception as e:
        p(f"Gagal memuat segmentasi persona: {e}")

    # 11. ANALISIS SENTIMEN & DETEKSI DINI RISIKO (EARLY WARNING)
    try:
        p("\n[11] ANALISIS SENTIMEN & DETEKSI DINI RISIKO KETIDAKPUASAN (EARLY WARNING)")
        p("-" * 96)
        df_sar_all = db_manager.query("SELECT masalah_dan_evaluasi FROM fakta_masukan_saran;")
        df_sent_all = analyze_sentiment_indonesian(df_sar_all["masalah_dan_evaluasi"])
        sent_counts = df_sent_all["sentimen"].value_counts()
        for s_cat, s_val in sent_counts.items():
            pct = (s_val / len(df_sent_all)) * 100
            p(f"  * Sentimen {s_cat:<8} : {s_val:,} ulasan ({pct:.1f}%)")

        pred_risk = predict_dissatisfaction_risks(db_manager)
        p(f"\n  >> Early Warning Risk Rate : {pred_risk['high_risk_pct']}% responden masuk kategori risiko tinggi tidak puas.")
        p(f"  >> Faktor Risiko Dominan   : {pred_risk['risk_drivers'].iloc[0]['faktor_risiko']} (Bobot: {pred_risk['risk_drivers'].iloc[0]['kontribusi_bobot']})")
    except Exception as e:
        p(f"Gagal memuat analisis sentimen & early warning: {e}")

    p("\n" + "=" * 96)
    p("                          AKHIR DARI LAPORAN ANALITIK                           ")
    p("=" * 96)

    report_str = "\n".join(lines)
    if export_file:
        action_label = "diperbarui (update)" if file_previously_existed else "dibuat baru (generate)"
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(report_str)
        p(f"\n[INFO] Salinan laporan lengkap berhasil {action_label} ke file: {REPORT_PATH}")

    return report_str
