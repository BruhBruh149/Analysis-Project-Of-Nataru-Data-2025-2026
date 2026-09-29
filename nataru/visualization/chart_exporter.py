"""
Modul Pengekspor Visualisasi Grafis Resolusi Tinggi.
Menghasilkan 12 grafik publikasi format PNG (300 DPI) dan HTML interaktif
mencakup seluruh dimensi evaluasi operasional, 3 pilar mutu, wait-time decay,
matriks prioritas IPA, K-Means clustering, dan analisis sentimen NLP.
"""

import os
import logging
from typing import List, Optional
import pandas as pd
import numpy as np

from ..config.settings import BASE_DIR, CHARTS_DIR
from ..pipeline.text_cleaner import clean_hub_name

logger = logging.getLogger("NataruAnalytics")

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

def export_visualizations(db_manager, output_dir: Optional[str] = None) -> str:
    """
    Menghasilkan 12 chart visualisasi grafis analitis lengkap (format PNG 300-DPI dan HTML interaktif)
    langsung dari script/terminal mencakup seluruh sasaran analitis yang diprioritaskan.
    """
    out_dir = output_dir or CHARTS_DIR
    os.makedirs(out_dir, exist_ok=True)
    print(f"\n[CHARTS] Menghasilkan 12 visualisasi grafis analitis ke direktori: {out_dir}")

    generated_files = []

    # Import circular safely
    from ..analytics.ipa_matrix import compute_key_drivers_and_ipa
    from ..analytics.clustering import run_passenger_clustering
    from ..analytics.sentiment_nlp import extract_word_frequency, analyze_sentiment_indonesian

    # 1. Chart: CSI Kepuasan Multi-Moda
    try:
        df_csi = db_manager.query("SELECT * FROM v_ringkasan_kepuasan_moda WHERE moda_transportasi IS NOT NULL AND moda_transportasi != '' AND moda_transportasi != 'None' AND moda_transportasi != 'nan' ORDER BY rata_rata_csi DESC;")
        if not df_csi.empty:
            df_csi["moda_transportasi"] = df_csi["moda_transportasi"].astype(str)
            df_csi["rata_rata_csi"] = pd.to_numeric(df_csi["rata_rata_csi"], errors='coerce')
            df_csi["rata_rata_kepuasan"] = pd.to_numeric(df_csi["rata_rata_kepuasan"], errors='coerce')

        if not df_csi.empty and MATPLOTLIB_AVAILABLE:
            fig, ax1 = plt.subplots(figsize=(10, 6), dpi=300)
            colors = ['#1e3c72', '#2a5298', '#20c997', '#17a2b8', '#fd7e14', '#6c757d']
            bars = ax1.bar(df_csi["moda_transportasi"], df_csi["rata_rata_csi"], color=colors[:len(df_csi)], width=0.55, edgecolor='black', linewidth=0.8)
            ax1.set_title("Customer Satisfaction Index (CSI) per Moda Transportasi Nataru", fontsize=13, fontweight='bold', pad=15)
            ax1.set_ylabel("CSI (%)", fontsize=11, fontweight='bold')
            ax1.set_ylim(0, 110)
            ax1.grid(axis='y', linestyle='--', alpha=0.5)
            for bar, skor in zip(bars, df_csi["rata_rata_kepuasan"]):
                yval = float(bar.get_height())
                ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 1.5, f"{yval:.1f}%\n({skor:.2f}/5)", ha='center', va='bottom', fontsize=9, fontweight='bold')
            plt.xticks(rotation=15, ha='right', fontsize=9)
            plt.tight_layout()
            p1 = os.path.join(out_dir, "01_csi_kepuasan_multi_moda.png")
            plt.savefig(p1)
            plt.close()
            generated_files.append("01_csi_kepuasan_multi_moda.png")

        if not df_csi.empty and PLOTLY_AVAILABLE:
            fig_p1 = px.bar(
                df_csi, x="moda_transportasi", y="rata_rata_csi", color="rata_rata_csi",
                color_continuous_scale="Tealgrn", text="rata_rata_csi",
                title="Customer Satisfaction Index (CSI) per Moda Transportasi",
                labels={"moda_transportasi": "Moda Transportasi", "rata_rata_csi": "CSI (%)"}
            )
            fig_p1.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig_p1.write_html(os.path.join(out_dir, "01_csi_kepuasan_multi_moda.html"))
    except Exception as e:
        logger.warning(f"Gagal Chart 1: {e}")

    # 2. Chart: Benchmarking 3 Pilar
    try:
        df_pilar = db_manager.query("SELECT * FROM v_benchmarking_3_pilar ORDER BY skor_komposit_layanan DESC;")
        if not df_pilar.empty and MATPLOTLIB_AVAILABLE:
            fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
            x = np.arange(len(df_pilar))
            width = 0.25
            ax.bar(x - width, df_pilar["avg_prasarana"], width, label="Pilar Prasarana", color="#1f77b4", edgecolor='black', linewidth=0.6)
            ax.bar(x, df_pilar["avg_sarana"], width, label="Pilar Sarana", color="#2ca02c", edgecolor='black', linewidth=0.6)
            ax.bar(x + width, df_pilar["avg_manajemen"].fillna(0), width, label="Pilar Manajemen Operasional", color="#ff7f0e", edgecolor='black', linewidth=0.6)
            ax.set_title("Benchmarking Evaluasi 3 Pilar Mutu Layanan Antarmoda Transportasi", fontsize=13, fontweight='bold', pad=15)
            ax.set_ylabel("Skor Evaluasi (1 - 5)", fontsize=11, fontweight='bold')
            ax.set_ylim(3.0, 5.2)
            ax.set_xticks(x)
            ax.set_xticklabels(df_pilar["moda_transportasi"], rotation=15, ha='right', fontsize=9)
            ax.legend(frameon=True, facecolor='white', loc='upper right')
            ax.grid(axis='y', linestyle='--', alpha=0.5)
            plt.tight_layout()
            p2 = os.path.join(out_dir, "02_benchmarking_3_pilar_moda.png")
            plt.savefig(p2)
            plt.close()
            generated_files.append("02_benchmarking_3_pilar_moda.png")
    except Exception as e:
        logger.warning(f"Gagal Chart 2: {e}")

    # 3. Chart: Literasi Kebijakan (Skala 6)
    try:
        df_lit = db_manager.query("SELECT * FROM fakta_literasi_kebijakan ORDER BY tingkat_kesadaran_pct ASC;")
        if not df_lit.empty and MATPLOTLIB_AVAILABLE:
            fig, ax = plt.subplots(figsize=(12, 8), dpi=300)
            y_pos = np.arange(len(df_lit))
            ax.barh(y_pos, df_lit["tingkat_kesadaran_pct"], color="#28a745", label="Mengetahui Kebijakan (Skala 1-5)", edgecolor='black', linewidth=0.5)
            ax.barh(y_pos, df_lit["tingkat_tidak_tahu_pct"], left=df_lit["tingkat_kesadaran_pct"], color="#dc3545", label="Tidak Tahu / Skala 6", edgecolor='black', linewidth=0.5)
            ax.set_yticks(y_pos)
            ax.set_yticklabels(df_lit["program_kebijakan"], fontsize=9)
            ax.set_xlabel("Proporsi Literasi Publik (%)", fontsize=11, fontweight='bold')
            ax.set_title("Rasio Kesadaran Kebijakan Publik (Awareness Rate) vs Tidak Tahu (Skala 6)", fontsize=13, fontweight='bold', pad=15)
            ax.legend(loc='lower left', frameon=True)
            ax.grid(axis='x', linestyle='--', alpha=0.5)
            plt.tight_layout()
            p3 = os.path.join(out_dir, "03_efektivitas_dan_literasi_kebijakan.png")
            plt.savefig(p3)
            plt.close()
            generated_files.append("03_efektivitas_dan_literasi_kebijakan.png")
    except Exception as e:
        logger.warning(f"Gagal Chart 3: {e}")

    # 4. Chart: Wait-Time Decay Curve
    try:
        df_wait = db_manager.query("SELECT * FROM v_analisis_waktu_tunggu;")
        if not df_wait.empty and MATPLOTLIB_AVAILABLE:
            order_map = {'< 30 menit': 1, '30 menit - 1 jam': 2, '1 - 3 jam': 3, '3 - 6 jam': 4, '> 6 jam': 5}
            df_wait['sort_order'] = df_wait['waktu_menunggu_moda'].map(order_map).fillna(99)
            df_wait = df_wait.sort_values('sort_order').reset_index(drop=True)
            fig, ax1 = plt.subplots(figsize=(10, 6), dpi=300)
            ax2 = ax1.twinx()
            ax1.plot(df_wait["waktu_menunggu_moda"], df_wait["avg_skor_kepuasan"], marker='o', linewidth=2.5, color='#d9534f', label="Skor Kepuasan Keseluruhan")
            ax1.plot(df_wait["waktu_menunggu_moda"], df_wait["avg_ketepatan_waktu"], marker='s', linewidth=2, linestyle='--', color='#0275d8', label="Skor Ketepatan Waktu")
            ax2.bar(df_wait["waktu_menunggu_moda"], df_wait["total_responden"], alpha=0.2, color='#6c757d', width=0.4, label="Jumlah Responden")
            ax1.set_title("Ambang Batas Waktu Tunggu (Wait-Time Decay Curve & Inflection Point)", fontsize=13, fontweight='bold', pad=15)
            ax1.set_ylabel("Skor Evaluasi (1 - 5)", fontsize=11, fontweight='bold')
            ax2.set_ylabel("Volume Responden", fontsize=11, fontweight='bold')
            ax1.set_ylim(3.5, 5.1)
            ax1.grid(True, linestyle=':', alpha=0.6)
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
            plt.tight_layout()
            p4 = os.path.join(out_dir, "04_wait_time_decay_curve.png")
            plt.savefig(p4)
            plt.close()
            generated_files.append("04_wait_time_decay_curve.png")  
    except Exception as e:
        logger.warning(f"Gagal Chart 4: {e}")

    # 5. Chart: Matriks Rantai Antarmoda First-Mile
    try:
        df_fm = db_manager.query("SELECT moda_first_mile, COUNT(*) as cnt, AVG(e.skor_aksesibilitas) as avg_akses FROM dim_perjalanan p JOIN fakta_evaluasi_moda e ON p.id_responden = e.id_responden WHERE moda_first_mile NOT IN ('Tidak Diketahui', 'Tidak Menggunakan / Pribadi') GROUP BY moda_first_mile ORDER BY cnt DESC LIMIT 7;")
        if not df_fm.empty and MATPLOTLIB_AVAILABLE:
            fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
            bars = ax.bar(df_fm["moda_first_mile"], df_fm["cnt"], color='#17a2b8', edgecolor='black', linewidth=0.7)
            ax.set_title("Distribusi Proporsi Moda Akses First-Mile Menuju Simpul Transportasi", fontsize=13, fontweight='bold', pad=15)
            ax.set_ylabel("Volume Penumpang", fontsize=11, fontweight='bold')
            plt.xticks(rotation=20, ha='right', fontsize=9)
            ax.grid(axis='y', linestyle='--', alpha=0.5)
            for bar, akses in zip(bars, df_fm["avg_akses"]):
                yval = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2.0, yval + 20, f"{yval:,}\n(Akses: {akses:.2f})", ha='center', va='bottom', fontsize=8, fontweight='bold')
            plt.tight_layout()
            p5 = os.path.join(out_dir, "05_matriks_rantai_antarmoda.png")
            plt.savefig(p5)
            plt.close()
            generated_files.append("05_matriks_rantai_antarmoda.png")
    except Exception as e:
        logger.warning(f"Gagal Chart 5: {e}")

    # 6. Chart: Captive vs Choice Riders
    try:
        df_cap = db_manager.query("SELECT * FROM v_analisis_captive_riders;")
        if not df_cap.empty and MATPLOTLIB_AVAILABLE:
            fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
            colors = ['#28a745', '#dc3545'] if len(df_cap) == 2 else ['#007bff', '#6c757d']
            bars = ax.bar(df_cap["segmen_pengguna"], df_cap["avg_csi"], color=colors, width=0.45, edgecolor='black', linewidth=0.8)
            ax.set_title("Disparitas Indeks Kepuasan: Pilihan Utama (Choice) vs Terpaksa (Captive)", fontsize=12, fontweight='bold', pad=15)
            ax.set_ylabel("CSI (%)", fontsize=11, fontweight='bold')
            ax.set_ylim(0, 105)
            ax.grid(axis='y', linestyle='--', alpha=0.5)
            for bar, skor in zip(bars, df_cap["avg_skor_kepuasan"]):
                yval = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2.0, yval + 1.5, f"{yval:.2f}%\n(Skor: {skor:.2f}/5)", ha='center', va='bottom', fontsize=10, fontweight='bold')
            plt.tight_layout()
            p6 = os.path.join(out_dir, "06_captive_vs_choice_riders.png")
            plt.savefig(p6)
            plt.close()
            generated_files.append("06_captive_vs_choice_riders.png")
    except Exception as e:
        logger.warning(f"Gagal Chart 6: {e}")

    # 7. Chart: Matriks IPA
    try:
        df_ipa, grand_perf, grand_imp = compute_key_drivers_and_ipa(db_manager)
        if not df_ipa.empty and MATPLOTLIB_AVAILABLE:
            fig, ax = plt.subplots(figsize=(11, 8), dpi=300)
            ax.axvline(x=grand_perf, color='red', linestyle='--', linewidth=1.5, label=f"Rerata Kinerja ({grand_perf:.2f})")
            ax.axhline(y=grand_imp, color='blue', linestyle='--', linewidth=1.5, label=f"Rerata Kepentingan ({grand_imp:.3f})")

            colors_map = {
                "Kuadran I": "#d9534f",
                "Kuadran II": "#5cb85c",
                "Kuadran III": "#f0ad4e",
                "Kuadran IV": "#5bc0de"
            }

            for _, r in df_ipa.iterrows():
                q_prefix = r["kuadran_ipa"].split("(")[0].strip()
                c = colors_map.get(q_prefix, "#333333")
                ax.scatter(r["kinerja_performance"], r["kepentingan_importance"], color=c, s=160, edgecolor='black', zorder=5)
                ax.annotate(r["indikator_layanan"].split("(")[0].strip(), (r["kinerja_performance"] + 0.003, r["kepentingan_importance"] + 0.003), fontsize=8.5, fontweight='bold')

            ax.text(grand_perf - 0.08, grand_imp + 0.04, "KUADRAN I\n(Prioritas Utama / Perbaikan Segera)", fontsize=10, color='#d9534f', fontweight='bold', ha='center', bbox=dict(boxstyle='round,pad=0.3', facecolor='#ffebee', edgecolor='#d9534f', alpha=0.8))
            ax.text(grand_perf + 0.08, grand_imp + 0.04, "KUADRAN II\n(Pertahankan Prestasi)", fontsize=10, color='#2e7d32', fontweight='bold', ha='center', bbox=dict(boxstyle='round,pad=0.3', facecolor='#e8f5e9', edgecolor='#2e7d32', alpha=0.8))
            ax.text(grand_perf - 0.08, grand_imp - 0.04, "KUADRAN III\n(Prioritas Rendah)", fontsize=10, color='#e65100', fontweight='bold', ha='center', bbox=dict(boxstyle='round,pad=0.3', facecolor='#fff3e0', edgecolor='#e65100', alpha=0.8))
            ax.text(grand_perf + 0.08, grand_imp - 0.04, "KUADRAN IV\n(Berlebihan / Overkill)", fontsize=10, color='#0277bd', fontweight='bold', ha='center', bbox=dict(boxstyle='round,pad=0.3', facecolor='#e1f5fe', edgecolor='#0277bd', alpha=0.8))

            ax.set_title("Matriks Prioritas Intervensi Layanan (Importance-Performance Analysis / IPA)", fontsize=13, fontweight='bold', pad=15)
            ax.set_xlabel("Kinerja Layanan (Performance: 1 - 5)", fontsize=11, fontweight='bold')
            ax.set_ylabel("Tingkat Kepentingan (Derived Importance / Korelasi r)", fontsize=11, fontweight='bold')
            ax.grid(True, linestyle=':', alpha=0.5)
            ax.legend(loc='lower right', frameon=True)
            plt.tight_layout()
            p7 = os.path.join(out_dir, "07_importance_performance_analysis_ipa.png")
            plt.savefig(p7)
            plt.close()
            generated_files.append("07_importance_performance_analysis_ipa.png")
    except Exception as e:
        logger.warning(f"Gagal Chart 7: {e}")

    # 8. Chart: Peringkat Bandara Udara
    try:
        q_hubs = "SELECT udara_bandara_asal as simpul, AVG(k.skor_kepuasan) as avg_skor FROM data_asli a JOIN fakta_kepuasan_keseluruhan k ON a.id = k.id_responden WHERE udara_bandara_asal IS NOT NULL AND udara_bandara_asal != '' GROUP BY udara_bandara_asal HAVING COUNT(*) >= 15 ORDER BY avg_skor DESC LIMIT 8;"
        df_hub_air = db_manager.query(q_hubs)
        if not df_hub_air.empty and MATPLOTLIB_AVAILABLE:
            fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
            y_pos = np.arange(len(df_hub_air))
            ax.barh(y_pos, df_hub_air["avg_skor"], color='#4a90e2', edgecolor='black', linewidth=0.6)
            ax.set_yticks(y_pos)
            ax.set_yticklabels([s[:35] for s in df_hub_air["simpul"]], fontsize=8.5)
            ax.set_xlabel("Rata-Rata Skor Kepuasan (1 - 5)", fontsize=11, fontweight='bold')
            ax.set_xlim(3.0, 5.2)
            ax.set_title("Peringkat Kepuasan Penumpang Antar-Bandara Udara Utama", fontsize=13, fontweight='bold', pad=15)
            ax.grid(axis='x', linestyle='--', alpha=0.5)
            plt.tight_layout()
            p8 = os.path.join(out_dir, "08_peringkat_simpul_transportasi.png")
            plt.savefig(p8)
            plt.close()
            generated_files.append("08_peringkat_simpul_transportasi.png")
    except Exception as e:
        logger.warning(f"Gagal Chart 8: {e}")

    # 9. Chart: Key Driver Ranking
    try:
        df_ipa, _, _ = compute_key_drivers_and_ipa(db_manager)
        if not df_ipa.empty and MATPLOTLIB_AVAILABLE:
            df_drivers = df_ipa.sort_values("kepentingan_importance", ascending=True)
            fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
            y_pos = np.arange(len(df_drivers))
            ax.barh(y_pos, df_drivers["kepentingan_importance"], color='#2b580c', edgecolor='black', linewidth=0.6)
            ax.set_yticks(y_pos)
            ax.set_yticklabels([s[:38] for s in df_drivers["indikator_layanan"]], fontsize=9)
            ax.set_xlabel("Korelasi dengan Kepuasan Keseluruhan (Pearson r)", fontsize=11, fontweight='bold')
            ax.set_title("Key Driver Analysis: Faktor Penentu Utama Kepuasan Penumpang", fontsize=13, fontweight='bold', pad=15)
            ax.grid(axis='x', linestyle='--', alpha=0.5)
            plt.tight_layout()
            p9 = os.path.join(out_dir, "09_key_driver_analysis.png")
            plt.savefig(p9)
            plt.close()
            generated_files.append("09_key_driver_analysis.png")
    except Exception as e:
        logger.warning(f"Gagal Chart 9: {e}")

    # 10. Chart: Frekuensi Kata Kunci Masukan
    try:
        df_sar = db_manager.query("SELECT masalah_dan_evaluasi, kategori_isu FROM fakta_masukan_saran;")
        wf = extract_word_frequency(df_sar["masalah_dan_evaluasi"], top_n=10)
        if not wf.empty and MATPLOTLIB_AVAILABLE:
            fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
            ax.bar(wf["Kata Kunci"], wf["Frekuensi"], color='#6c5ce7', edgecolor='black', linewidth=0.6)
            ax.set_title("Frekuensi Kata Kunci Keluhan & Masukan Penumpang (Analisis NLP)", fontsize=13, fontweight='bold', pad=15)
            ax.set_ylabel("Frekuensi Muncul", fontsize=11, fontweight='bold')
            plt.xticks(rotation=20, ha='right', fontsize=9)
            ax.grid(axis='y', linestyle='--', alpha=0.5)
            plt.tight_layout()
            p10 = os.path.join(out_dir, "10_analisis_nlp_isu_keluhan.png")
            plt.savefig(p10)
            plt.close()
            generated_files.append("10_analisis_nlp_isu_keluhan.png")
    except Exception as e:
        logger.warning(f"Gagal Chart 10: {e}")

    # 11. Chart: Segmentasi Persona Penumpang (K-Means)
    try:
        _, df_pers_sum = run_passenger_clustering(db_manager, n_clusters=3)
        if not df_pers_sum.empty and MATPLOTLIB_AVAILABLE:
            fig, ax = plt.subplots(figsize=(11, 6), dpi=300)
            labels = [p.split('(')[0].strip() for p in df_pers_sum['persona_label']]
            x = np.arange(len(labels))
            width = 0.35

            bars1 = ax.bar(x - width/2, df_pers_sum['avg_csi'], width, label='CSI (%)', color='#1e3c72', edgecolor='black', linewidth=0.7)
            ax2 = ax.twinx()
            bars2 = ax2.bar(x + width/2, df_pers_sum['avg_waktu_tunggu_menit'], width, label='Waktu Tunggu (Menit)', color='#e67e22', edgecolor='black', linewidth=0.7)

            ax.set_title("Segmentasi Persona Penumpang Nataru (K-Means Clustering): CSI vs Waktu Tunggu", fontsize=13, fontweight='bold', pad=15)
            ax.set_ylabel("Customer Satisfaction Index (CSI %)", fontsize=11, fontweight='bold', color='#1e3c72')
            ax2.set_ylabel("Rata-Rata Waktu Menunggu (Menit)", fontsize=11, fontweight='bold', color='#e67e22')
            ax.set_xticks(x)
            ax.set_xticklabels(labels, fontsize=9, fontweight='bold')
            ax.set_ylim(60, 105)

            for b in bars1:
                yval = b.get_height()
                ax.text(b.get_x() + b.get_width()/2.0, yval + 1.0, f"{yval:.1f}%", ha='center', va='bottom', fontsize=9, fontweight='bold')
            for b in bars2:
                yval = b.get_height()
                ax2.text(b.get_x() + b.get_width()/2.0, yval + 2.0, f"{yval:.0f}m", ha='center', va='bottom', fontsize=9, fontweight='bold')

            ax.grid(axis='y', linestyle='--', alpha=0.4)
            lines1, l1 = ax.get_legend_handles_labels()
            lines2, l2 = ax2.get_legend_handles_labels()
            ax.legend(lines1 + lines2, l1 + l2, loc='upper left')
            plt.tight_layout()
            p11 = os.path.join(out_dir, "11_segmentasi_persona_kmeans.png")
            plt.savefig(p11)
            plt.close()
            generated_files.append("11_segmentasi_persona_kmeans.png")
    except Exception as e:
        logger.warning(f"Gagal Chart 11: {e}")

    # 12. Chart: Distribusi Sentimen NLP Bahasa Indonesia
    try:
        df_sar_all = db_manager.query("SELECT masalah_dan_evaluasi FROM fakta_masukan_saran;")
        df_sent_all = analyze_sentiment_indonesian(df_sar_all["masalah_dan_evaluasi"])
        if not df_sent_all.empty and MATPLOTLIB_AVAILABLE:
            counts = df_sent_all["sentimen"].value_counts()
            labels = list(counts.index)
            vals = list(counts.values)
            colors_sent = {"Positif": "#28a745", "Netral": "#6c757d", "Negatif": "#dc3545"}
            chart_colors = [colors_sent.get(l, "#17a2b8") for l in labels]

            fig, (ax_donut, ax_bar) = plt.subplots(1, 2, figsize=(13, 6), dpi=300)

            # Donut Chart
            wedges, texts, autotexts = ax_donut.pie(
                vals, labels=labels, autopct='%1.1f%%', startangle=140,
                colors=chart_colors, wedgeprops=dict(width=0.45, edgecolor='black', linewidth=0.8)
            )
            for t in texts:
                t.set_fontsize(10)
                t.set_weight('bold')
            for at in autotexts:
                at.set_fontsize(10)
                at.set_color('white')
                at.set_weight('bold')
            ax_donut.set_title("Proporsi Polaritas Sentimen Masukan", fontsize=12, fontweight='bold')

            # Bar Chart Volume
            bars = ax_bar.bar(labels, vals, color=chart_colors, edgecolor='black', linewidth=0.8, width=0.5)
            ax_bar.set_title("Volume Ulasan per Kategori Sentimen", fontsize=12, fontweight='bold')
            ax_bar.set_ylabel("Jumlah Ulasan Responden", fontsize=11, fontweight='bold')
            for b in bars:
                yval = b.get_height()
                ax_bar.text(b.get_x() + b.get_width()/2.0, yval + 100, f"{yval:,}", ha='center', va='bottom', fontsize=9, fontweight='bold')
            ax_bar.grid(axis='y', linestyle='--', alpha=0.4)

            fig.suptitle("Analisis Sentimen Leksikon NLP Ulasan & Evaluasi Penumpang Nataru", fontsize=14, fontweight='bold')
            plt.tight_layout()
            p12 = os.path.join(out_dir, "12_analisis_sentimen_distribusi.png")
            plt.savefig(p12)
            plt.close()
            generated_files.append("12_analisis_sentimen_distribusi.png")
    except Exception as e:
        logger.warning(f"Gagal Chart 12: {e}")

    print(f"[CHARTS] Sukses menghasilkan {len(generated_files)} file gambar & interaktif ke folder {out_dir}.\n")
    return out_dir
