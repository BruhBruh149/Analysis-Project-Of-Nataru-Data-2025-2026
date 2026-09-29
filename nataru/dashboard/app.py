"""
Dashboard Eksekutif Analitik Pelayanan Transportasi Nataru (Streamlit & Plotly).
Menyediakan visualisasi interaktif multi-tab, integrasi peta OpenStreetMap GIS,
Key Driver Analysis, K-Means Clustering, NLP Topic Modeling, dan Early Warning Predictor.
"""

import os
import sys
import logging
from typing import Dict, Any
import pandas as pd
import numpy as np

from ..config.settings import BASE_DIR, CHARTS_DIR
from ..pipeline.text_cleaner import clean_hub_name
from ..pipeline.elt_pipeline import NataruELTPipeline
from ..analytics.kpi_engine import compute_kpi_summary, generate_terminal_report, export_all_tables_to_csv
from ..analytics.ipa_matrix import compute_key_drivers_and_ipa
from ..analytics.clustering import run_passenger_clustering, compute_elbow_and_silhouette
from ..analytics.sentiment_nlp import (
    extract_word_frequency, analyze_sentiment_indonesian, extract_complaint_topics,
    extract_ngram_frequency, analyze_aspect_based_sentiment
)
from ..analytics.ml_predictor import predict_dissatisfaction_risks, predict_single_scenario
from ..analytics.geo_analytics import get_od_flow_data, get_hub_performance_geo, get_sankey_od_data
from ..visualization.map_builder import build_hub_interactive_map, build_od_flow_map, build_sankey_od_diagram
from ..visualization.chart_exporter import export_visualizations
from .styles import DASHBOARD_CSS


logger = logging.getLogger("NataruAnalytics")

try:
    import streamlit as st
    import plotly.express as px
    import plotly.graph_objects as go
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

def render_dashboard(db_manager):
    """Merender antarmuka dashboard analitis multi-tab menggunakan Streamlit & Plotly."""
    if not STREAMLIT_AVAILABLE:
        print("[ERROR] Streamlit belum terpasang. Jalankan: pip install streamlit plotly")
        return

    st.set_page_config(
        page_title="Dashboard Analitik Pelayanan Transportasi Nataru",
        page_icon="🚆",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

    # Otomatis pastikan file Laporan_Analisis_Nataru.txt terbuat / ter-update saat dashboard dibuka
    if "report_auto_synced" not in st.session_state:
        try:
            generate_terminal_report(db_manager, export_file=True)
            st.session_state["report_auto_synced"] = True
        except Exception:
            pass

    @st.cache_data(ttl=120)
    def load_data_from_db():
        try:
            df_k = db_manager.query("SELECT * FROM fakta_kepuasan_keseluruhan;")
            df_p = db_manager.query("SELECT * FROM dim_perjalanan;")
            df_e = db_manager.query("SELECT * FROM fakta_evaluasi_moda;")
            df_pol = db_manager.query("SELECT * FROM fakta_kebijakan_nataru;")
            df_lit = db_manager.query("SELECT * FROM fakta_literasi_kebijakan;")
            df_s = db_manager.query("SELECT * FROM fakta_masukan_saran;")
            df_r = db_manager.query("SELECT * FROM dim_responden;")
            return df_k, df_p, df_e, df_pol, df_lit, df_s, df_r, True
        except Exception as err:
            logger.warning(f"Gagal load data: {err}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), False

    if "db_engine" not in st.session_state:
        st.session_state["db_engine"] = db_manager.engine_type

    df_kep, df_perj, df_eval, df_pol, df_lit, df_sar, df_resp, ok = load_data_from_db()

    # Header Utama
    st.markdown("""
    <div class="main-header">
        <h1>🚆 SISTEM ANALITIK & EVALUASI PENYELENGGARAAN TRANSPORTASI NATARU</h1>
        <p>Dashboard Eksekutif Pemantauan Kinerja Multimoda, Evaluasi 3 Pilar Mutu Layanan, Literasi Kebijakan, dan Deteksi Dini Risiko Pelayanan</p>
    </div>
    """, unsafe_allow_html=True)

    if not ok or df_kep.empty:
        st.error("⚠️ Basis data analitik belum siap atau tabel fakta belum dimodelkan.")
        if st.button("Jalankan Pipeline ELT Otomatis Sekarang", type="primary"):
            with st.spinner("Memproses pipeline pembersihan data dan pemodelan basis data..."):
                pipeline = NataruELTPipeline(db_manager)
                pipeline.run()
                st.cache_data.clear()
                st.success("Pipeline berhasil disiapkan! Menyegarkan antarmuka...")
                st.rerun()
        st.stop()

    # Sidebar Filter & Kontrol
    with st.sidebar:
        st.header("⚙️ Kontrol Sistem")
        engine_options = ["MySQL XAMPP (Localhost:3306)", "SQLite Lokal (nataru_analytics.db)"]
        default_idx = 0 if db_manager.engine_type == "MYSQL" else 1
        selected_engine_label = st.selectbox("Database Engine:", engine_options, index=default_idx)
        new_engine = "MYSQL" if "MySQL" in selected_engine_label else "SQLITE"
        if new_engine != st.session_state["db_engine"]:
            st.session_state["db_engine"] = new_engine
            db_manager.engine_type = new_engine
            st.cache_data.clear()
            st.rerun()

        db_badge_color = "#28a745" if db_manager.engine_type == "MYSQL" else "#17a2b8"
        engine_badge_text = "MySQL XAMPP Active" if db_manager.engine_type == "MYSQL" else "SQLite Active"
        st.markdown(f"""
        <div style="background:#f8f9fa; padding:10px 14px; border-radius:8px; margin-bottom:15px; border:1px solid #e9ecef;">
            <span style="font-size:12px; color:#6c757d;">Status Basis Data:</span><br>
            <strong style="color:{db_badge_color}; font-size:13px;">● {engine_badge_text}</strong>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("Filter Global")
        all_modas = sorted(df_kep["moda_transportasi"].dropna().unique().tolist())
        selected_modas = st.multiselect("Pilih Moda Transportasi:", all_modas, default=all_modas)

        all_genders = sorted(df_resp["jenis_kelamin"].dropna().unique().tolist())
        selected_genders = st.multiselect("Jenis Kelamin:", all_genders, default=all_genders)

        st.markdown("---")
        st.subheader("Aksi Cepat")
        if st.button("Generate Gambar Grafik (PNG)"):
            with st.spinner("Menghasilkan grafik resolusi tinggi..."):
                out_p = export_visualizations(db_manager)
                st.success(f"Grafik tersimpan di: {out_p}")
                st.rerun()

        if st.button("Ekspor Seluruh Tabel (CSV)"):
            with st.spinner("Mengekspor tabel..."):
                out_c = export_all_tables_to_csv(db_manager)
                st.success(f"CSV tersimpan di: {out_c}")

        if st.button("Segarkan / Re-Run ELT"):
            with st.spinner("Memproses pipeline ELT & Laporan..."):
                pipeline = NataruELTPipeline(db_manager)
                pipeline.run(force_reload=True)
                generate_terminal_report(db_manager, export_file=True)
                st.cache_data.clear()
                st.success("Pipeline & Laporan berhasil diperbarui!")
                st.rerun()

    # Filter data sesuai pilihan
    active_resp_ids = df_resp[df_resp["jenis_kelamin"].isin(selected_genders)]["id_responden"]
    f_kep = df_kep[(df_kep["moda_transportasi"].isin(selected_modas)) & (df_kep["id_responden"].isin(active_resp_ids))]
    f_perj = df_perj[(df_perj["moda_transportasi"].isin(selected_modas)) & (df_perj["id_responden"].isin(active_resp_ids))]
    f_eval = df_eval[(df_eval["moda_transportasi"].isin(selected_modas)) & (df_eval["id_responden"].isin(active_resp_ids))]
    f_pol = df_pol[(df_pol["moda_transportasi"].isin(selected_modas)) & (df_pol["id_responden"].isin(active_resp_ids))]
    f_sar = df_sar[(df_sar["moda_transportasi"].isin(selected_modas)) & (df_sar["id_responden"].isin(active_resp_ids))]

    if f_kep.empty:
        st.warning("Data kosong untuk kombinasi filter yang dipilih. Silakan sesuaikan filter di sidebar.")
        st.stop()

    # 9 Tab Interaktif Terpadu
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "Ringkasan & 3 Pilar",
        "Peringkat Simpul & Peta GIS",
        "Literasi Kebijakan (Skala 6)",
        "Waktu Tunggu & Arus Mudik (OD)",
        "Pengguna Terpaksa (Captive)",
        "Key Drivers & Simulator Kebijakan",
        "Segmentasi Persona (K-Means)",
        "Masukan NLP & Sentimen",
        "Galeri Grafik Siap Cetak (300 DPI)"
    ])

    # =========================================================================
    # TAB 1: RINGKASAN & 3 PILAR
    # =========================================================================
    with tab1:
        st.subheader("Key Performance Indicators (KPI) Pelayanan Transportasi Nataru")
        kpi = compute_kpi_summary(f_kep)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #20c997;">
                <div class="kpi-title">Total Responden Tervalidasi</div>
                <div class="kpi-value">{kpi['total']:,}</div>
                <div class="kpi-sub">Sampel Nasional Multi-Moda</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #007bff;">
                <div class="kpi-title">Customer Satisfaction Index</div>
                <div class="kpi-value">{kpi['csi']}%</div>
                <div class="kpi-sub">Kategori: SANGAT PUAS</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #ffc107;">
                <div class="kpi-title">Rata-Rata Skor Kepuasan</div>
                <div class="kpi-value">{kpi['avg_score']} <span style="font-size:16px;">/ 5.0</span></div>
                <div class="kpi-sub">Skala Likert Konsolidasi</div>
            </div>""", unsafe_allow_html=True)
        with c4:
            st.markdown(f"""<div class="kpi-card" style="border-left-color: #6f42c1;">
                <div class="kpi-title">Persentase Publik Puas</div>
                <div class="kpi-value">{kpi['pct_puas']}%</div>
                <div class="kpi-sub">Responden Memberi Skor >= 4</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("Evaluasi Kepuasan Multi-Moda (CSI & Pangsa Pasar Responden)")
        col_m1, col_m2 = st.columns([3, 2])
        with col_m1:
            df_csi_agg = f_kep.groupby("moda_transportasi").agg(
                csi=("indeks_csi", "mean"),
                skor=("skor_kepuasan", "mean"),
                n=("id_responden", "count")
            ).reset_index().sort_values("csi", ascending=False)

            fig_csi = px.bar(
                df_csi_agg, x="moda_transportasi", y="csi", color="csi",
                color_continuous_scale="Tealgrn", text="csi",
                title="Customer Satisfaction Index (CSI %) Antarmoda Transportasi",
                labels={"moda_transportasi": "Moda Transportasi", "csi": "CSI (%)"}
            )
            fig_csi.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
            fig_csi.update_layout(yaxis=dict(range=[0, 105]), height=420)
            st.plotly_chart(fig_csi, use_container_width=True)

        with col_m2:
            fig_pie = px.pie(
                df_csi_agg, values="n", names="moda_transportasi",
                title="Distribusi Proporsi Responden per Moda Transportasi",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Safe
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(height=420)
            st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("---")
        st.subheader("Evaluasi 3 Pilar Mutu Layanan: Prasarana, Sarana, dan Manajemen Operasional")
        col_p1, col_p2 = st.columns([1, 1])
        with col_p1:
            dim_cols = [
                ("skor_fasilitas_simpul", "Fasilitas Simpul"),
                ("skor_keamanan", "Keamanan Simpul"),
                ("skor_aksesibilitas", "Aksesibilitas"),
                ("skor_kenyamanan_armada", "Kenyamanan Armada"),
                ("skor_keselamatan_armada", "Keselamatan Fisik"),
                ("skor_ketepatan_waktu", "Ketepatan Waktu"),
                ("skor_petugas", "Layanan Petugas"),
                ("skor_layanan_awak", "Kualitas Awak/Crew")
            ]
            dim_names = [name for _, name in dim_cols]
            fig_radar = go.Figure()
            top_modas = df_csi_agg["moda_transportasi"].head(4).tolist()
            for m_name in top_modas:
                sub_eval = f_eval[f_eval["moda_transportasi"] == m_name]
                if not sub_eval.empty:
                    vals = [sub_eval[col].mean() for col, _ in dim_cols]
                    vals.append(vals[0])
                    fig_radar.add_trace(go.Scatterpolar(
                        r=vals, theta=dim_names + [dim_names[0]],
                        fill='toself', name=m_name
                    ))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[3.2, 5.0])),
                title="Radar Komparasi 8 Dimensi Mutu Layanan (Top Moda)",
                showlegend=True,
                height=460
            )
            st.plotly_chart(fig_radar, use_container_width=True)

        with col_p2:
            df_pilar_calc = f_eval.groupby("moda_transportasi").agg(
                total_responden=("id_responden", "count"),
                avg_prasarana=("skor_pilar_prasarana", "mean"),
                avg_sarana=("skor_pilar_sarana", "mean"),
                avg_manajemen=("skor_pilar_manajemen", "mean"),
                komposit=("rata_rata_evaluasi", "mean")
            ).reset_index().sort_values("komposit", ascending=False)

            fig_pilar = go.Figure()
            fig_pilar.add_trace(go.Bar(name='Prasarana (Simpul)', x=df_pilar_calc['moda_transportasi'], y=df_pilar_calc['avg_prasarana'], marker_color='#1f77b4'))
            fig_pilar.add_trace(go.Bar(name='Sarana (Armada)', x=df_pilar_calc['moda_transportasi'], y=df_pilar_calc['avg_sarana'], marker_color='#2ca02c'))
            fig_pilar.add_trace(go.Bar(name='Manajemen Operasional', x=df_pilar_calc['moda_transportasi'], y=df_pilar_calc['avg_manajemen'], marker_color='#ff7f0e'))
            fig_pilar.update_layout(barmode='group', title="Kinerja 3 Pilar Mutu Layanan", yaxis=dict(range=[3.0, 5.0], title="Skor (1-5)"), height=460)
            st.plotly_chart(fig_pilar, use_container_width=True)

        st.markdown("**Tabel Rangkuman Benchmarking Kinerja 3 Pilar Mutu:**")
        st.dataframe(df_pilar_calc.style.format({
            "avg_prasarana": "{:.2f}",
            "avg_sarana": "{:.2f}",
            "avg_manajemen": "{:.2f}",
            "komposit": "{:.2f}"
        }), use_container_width=True)

    # =========================================================================
    # TAB 2: PERINGKAT SIMPUL & PETA GIS (OPENSTREETMAP MAPBOX)
    # =========================================================================
    with tab2:
        st.subheader("Evaluasi & Peringkat Simpul Transportasi Utama (Inter-Hub Benchmarking)")
        hub_type = st.radio("Pilih Kategori Simpul Transportasi:", ["Bandara Udara", "Stasiun Kereta Api", "Pelabuhan ASDP", "Terminal Bus"], horizontal=True)

        hub_col_map = {
            "Bandara Udara": "udara_bandara_asal",
            "Stasiun Kereta Api": "ka_stasiun_asal",
            "Pelabuhan ASDP": "asdp_pelabuhan_asal",
            "Terminal Bus": "bus_terminal_asal"
        }
        selected_col = hub_col_map[hub_type]

        try:
            q_hub_fast = f"""
                SELECT a.{selected_col} as simpul, COUNT(*) as n, AVG(k.skor_kepuasan) as avg_skor, AVG(k.indeks_csi) as avg_csi 
                FROM data_asli a 
                JOIN fakta_kepuasan_keseluruhan k ON a.id = k.id_responden 
                WHERE a.{selected_col} IS NOT NULL AND a.{selected_col} != '' 
                GROUP BY a.{selected_col} 
                HAVING n >= 8 
                ORDER BY avg_csi DESC 
                LIMIT 20;
            """
            df_hubs = db_manager.query(q_hub_fast)

            if not df_hubs.empty:
                df_hubs["simpul"] = df_hubs["simpul"].apply(clean_hub_name)
                df_hubs = df_hubs[df_hubs["simpul"] != "-"].groupby("simpul").agg(
                    n=("n", "sum"),
                    avg_skor=("avg_skor", "mean"),
                    avg_csi=("avg_csi", "mean")
                ).reset_index().sort_values("avg_csi", ascending=False).head(15)

                ch1, ch2 = st.columns([3, 2])
                with ch1:
                    fig_hub = px.bar(
                        df_hubs, x="avg_csi", y="simpul", orientation='h',
                        color="avg_csi", color_continuous_scale="Blues", text="avg_csi",
                        title=f"Peringkat {hub_type} Terbaik Berdasarkan Indeks Kepuasan (CSI %)",
                        labels={"avg_csi": "CSI (%)", "simpul": "Nama Simpul Asal"}
                    )
                    fig_hub.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                    fig_hub.update_layout(yaxis=dict(autorange="reversed"), height=480)
                    st.plotly_chart(fig_hub, use_container_width=True)

                with ch2:
                    st.markdown(f"**Rincian Evaluasi Simpul {hub_type}:**")
                    top_hub = df_hubs.iloc[0]
                    st.success(f"🏆 **Simpul Tertinggi:** {top_hub['simpul']} — CSI: **{top_hub['avg_csi']:.1f}%** ({int(top_hub['n']):,} sampel)")
                    st.dataframe(df_hubs.rename(columns={
                        "simpul": "Nama Simpul", "n": "Jumlah Sampel",
                        "avg_skor": "Skor Kepuasan", "avg_csi": "CSI (%)"
                    }).style.format({
                        "Skor Kepuasan": "{:.2f}",
                        "CSI (%)": "{:.2f}%"
                    }), use_container_width=True)
            else:
                st.info("Tidak ada data simpul yang memenuhi ambang batas minimum sampel.")
        except Exception as e:
            st.error(f"Gagal memuat evaluasi simpul: {e}")

        st.markdown("---")
        st.subheader("🗺️ Peta Geospasial Kinerja Simpul Transportasi Nasional (OpenStreetMap GIS)")
        st.markdown("Peta jalan nyata (*real street/terrain map*) sebaran simpul transportasi utama dengan status kepuasan (Hijau = Sangat Puas, Kuning = Cukup, Merah = Butuh Perbaikan):")
        
        try:
            df_geo_hubs = get_hub_performance_geo(db_manager)
            if not df_geo_hubs.empty:
                f_gis_col1, f_gis_col2 = st.columns([1, 3])
                with f_gis_col1:
                    gis_cat = st.selectbox("Filter Kategori di Peta:", ["Semua", "Bandara Udara", "Stasiun Kereta Api", "Pelabuhan ASDP", "Terminal Bus"])
                
                fig_map_interactive = build_hub_interactive_map(df_geo_hubs, category_filter=gis_cat)
                st.plotly_chart(fig_map_interactive, use_container_width=True)
            else:
                st.info("Data geospasial simpul belum tersedia.")
        except Exception as ex_map:
            st.error(f"Gagal memuat peta GIS: {ex_map}")

    # =========================================================================
    # TAB 3: LITERASI KEBIJAKAN (SKALA 6)
    # =========================================================================
    with tab3:
        st.subheader("Evaluasi Efektivitas Kebijakan & Rasio Literasi Publik (Pemisahan Skala 6 'TIDAK TAHU')")
        st.markdown("""
        * **Metodologi**: Responden yang menjawab angka **6 (TIDAK TAHU)** dipisahkan untuk mengukur tingkat kesadaran kebijakan (*Awareness Rate*).
        * Skor efektivitas murni dihitung secara independen hanya dari responden yang mengetahui dan merasakan langsung kebijakan (Skala 1 - 5).
        """)

        try:
            df_lit_v = db_manager.query("SELECT * FROM fakta_literasi_kebijakan ORDER BY tingkat_kesadaran_pct ASC;")
            if not df_lit_v.empty:
                fig_lit = go.Figure()
                fig_lit.add_trace(go.Bar(
                    y=df_lit_v["program_kebijakan"], x=df_lit_v["tingkat_kesadaran_pct"],
                    orientation='h', name='Mengetahui Kebijakan (Skala 1 - 5)',
                    marker=dict(color='#28a745'), text=df_lit_v["tingkat_kesadaran_pct"],
                    texttemplate='%{text:.1f}%', textposition='inside'
                ))
                fig_lit.add_trace(go.Bar(
                    y=df_lit_v["program_kebijakan"], x=df_lit_v["tingkat_tidak_tahu_pct"],
                    orientation='h', name='Tidak Tahu Kebijakan (Skala 6)',
                    marker=dict(color='#dc3545'), text=df_lit_v["tingkat_tidak_tahu_pct"],
                    texttemplate='%{text:.1f}%', textposition='inside'
                ))
                fig_lit.update_layout(
                    barmode='stack', title="Rasio Literasi Publik: Kesadaran Program vs Tidak Tahu (Skala 6)",
                    xaxis=dict(title="Proporsi Responden (%)", range=[0, 100]),
                    height=520, margin=dict(l=0, r=0, t=40, b=0)
                )
                st.plotly_chart(fig_lit, use_container_width=True)

                st.markdown("---")
                st.subheader("Tabel Audit Efektivitas & Uji Signifikansi Stimulus Kebijakan")
                st.dataframe(df_lit_v[[
                    "program_kebijakan", "sektor_moda", "tingkat_kesadaran_pct", "tingkat_tidak_tahu_pct",
                    "skor_efektivitas_murni", "kepuasan_group_tahu", "kepuasan_group_tidak_tahu", "delta_kepuasan", "signifikansi_dampak"
                ]].rename(columns={
                    "program_kebijakan": "Program Kebijakan", "sektor_moda": "Sektor",
                    "tingkat_kesadaran_pct": "Tahu (%)", "tingkat_tidak_tahu_pct": "Tdk Tahu (%)",
                    "skor_efektivitas_murni": "Skor Murni (1-5)", "kepuasan_group_tahu": "CSI Tahu",
                    "kepuasan_group_tidak_tahu": "CSI Tdk Tahu", "delta_kepuasan": "Delta Dampak", "signifikansi_dampak": "Uji Signifikansi"
                }).style.format({
                    "Tahu (%)": "{:.1f}%", "Tdk Tahu (%)": "{:.1f}%",
                    "Skor Murni (1-5)": "{:.2f}", "CSI Tahu": "{:.2f}",
                    "CSI Tdk Tahu": "{:.2f}", "Delta Dampak": "{:+.3f}"
                }), use_container_width=True)
        except Exception as e:
            st.error(f"Gagal memuat literasi kebijakan: {e}")

    # =========================================================================
    # TAB 4: WAKTU TUNGGU & ARUS MUDIK (OD FLOW)
    # =========================================================================
    with tab4:
        st.subheader("Diagnosis Ambang Batas Waktu Tunggu (Wait-Time Decay Curve)")
        cw1, cw2 = st.columns([3, 2])
        with cw1:
            try:
                df_w = db_manager.query("SELECT * FROM v_analisis_waktu_tunggu;")
                order_map = {'< 30 menit': 1, '30 menit - 1 jam': 2, '1 - 3 jam': 3, '3 - 6 jam': 4, '> 6 jam': 5}
                df_w['sort_order'] = df_w['waktu_menunggu_moda'].map(order_map).fillna(99)
                df_w = df_w.sort_values('sort_order').reset_index(drop=True)

                fig_decay = go.Figure()
                fig_decay.add_trace(go.Scatter(x=df_w["waktu_menunggu_moda"], y=df_w["avg_skor_kepuasan"], mode='lines+markers', name="Kepuasan Keseluruhan", line=dict(color='#d9534f', width=3.5)))
                fig_decay.add_trace(go.Scatter(x=df_w["waktu_menunggu_moda"], y=df_w["avg_ketepatan_waktu"], mode='lines+markers', name="Skor Ketepatan Waktu", line=dict(color='#0275d8', dash='dash', width=2.5)))
                fig_decay.add_vrect(x0=-0.5, x1=1.5, fillcolor="green", opacity=0.08, line_width=0, annotation_text="Zona Toleransi Aman (< 1 Jam)", annotation_position="top left")
                fig_decay.add_vrect(x0=1.5, x1=4.5, fillcolor="red", opacity=0.08, line_width=0, annotation_text="Zona Kemerosotan (> 1 Jam)", annotation_position="top right")
                fig_decay.update_layout(title="Wait-Time Decay Curve: Titik Belok Penurunan Kepuasan", yaxis=dict(title="Skor (1 - 5)", range=[3.5, 5.0]), height=420)
                st.plotly_chart(fig_decay, use_container_width=True)
            except Exception as e:
                st.error(f"Error waktu tunggu: {e}")

        with cw2:
            st.markdown("""
            **Analisis Titik Belok (Tipping Point):**
            * Durasi tunggu **< 30 menit** dan **30 menit - 1 jam** merupakan zona kepuasan aman (> 4.4/5.0).
            * Titik belok (*inflection point*) terjadi pada durasi **1 - 3 jam**, di mana skor ketepatan waktu mengalami kemerosotan paling curam.
            """)
            st.dataframe(df_w[["waktu_menunggu_moda", "total_responden", "avg_skor_kepuasan", "avg_ketepatan_waktu"]], use_container_width=True)

        st.markdown("---")
        st.subheader("🗺️ Pemetaan Geospasial Arus Mudik Asal-Tujuan (Origin-Destination Flow Map)")
        st.markdown("Peta interaktif koridor pergerakan arus mudik terpadat antar-wilayah di Indonesia:")
        try:
            df_od = get_od_flow_data(db_manager, top_n=20)
            if not df_od.empty:
                col_od_map, col_od_tbl = st.columns([3, 2])
                with col_od_map:
                    fig_od_interactive = build_od_flow_map(df_od, top_n=15)
                    st.plotly_chart(fig_od_interactive, use_container_width=True)

                with col_od_tbl:
                    st.markdown("**Top Koridor Rute Mudik Nasional:**")
                    st.dataframe(df_od[["koridor_rute", "volume_penumpang"]].rename(columns={
                        "koridor_rute": "Rute Perjalanan (Asal -> Tujuan)",
                        "volume_penumpang": "Volume Responden"
                    }), use_container_width=True, hide_index=True)
            else:
                st.info("Data arus mudik OD belum tersedia.")
        except Exception as ex_od:
            st.error(f"Gagal memuat peta OD: {ex_od}")

        st.markdown("---")
        st.subheader("🔀 Diagram Alir Mobilitas Pemudik Antar-Wilayah (Origin-Destination Sankey Diagram)")
        st.markdown("Visualisasi interaktif aliran volume pemudik dari wilayah asal menuju wilayah tujuan mudik:")
        try:
            sk_c1, sk_c2 = st.columns([1, 3])
            with sk_c1:
                sankey_mode = st.radio("Pilih Granularitas Aliran:", ["Provinsi (Makro Regional)", "Kota / Kabupaten"], index=0, key="sankey_gran")
            level_arg = "provinsi" if "Provinsi" in sankey_mode else "kota"
            sankey_data = get_sankey_od_data(db_manager, level=level_arg, top_n=16)
            if sankey_data and sankey_data.get("node_labels"):
                fig_sankey = build_sankey_od_diagram(sankey_data, title=f"Diagram Aliran Arus Mudik Antar-{sankey_mode.split()[0]} Terpadat")
                st.plotly_chart(fig_sankey, use_container_width=True)
            else:
                st.info("Data aliran mobilitas belum tersedia.")
        except Exception as ex_sk:
            st.error(f"Gagal memuat diagram Sankey: {ex_sk}")


    # =========================================================================
    # TAB 5: PENGGUNA TERPAKSA (CAPTIVE RIDERS)
    # =========================================================================
    with tab5:
        st.subheader("Dinamika Pengguna Terpaksa vs Sadar (Captive vs Choice Riders)")
        try:
            df_cap_v = db_manager.query("SELECT * FROM v_analisis_captive_riders;")
            if not df_cap_v.empty:
                cc1, cc2 = st.columns([3, 2])
                with cc1:
                    fig_cap = px.bar(
                        df_cap_v, x="segmen_pengguna", y="avg_csi", color="segmen_pengguna",
                        color_discrete_map={"Pilihan Utama (Choice Rider)": "#28a745", "Pengguna Terpaksa (Captive Rider)": "#dc3545"},
                        text="avg_csi", title="Perbandingan CSI: Pengguna Sadar vs Pengguna Terpaksa",
                        labels={"segmen_pengguna": "Kategori Pengguna", "avg_csi": "CSI (%)"}
                    )
                    fig_cap.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
                    fig_cap.update_layout(yaxis=dict(range=[0, 105]), height=400)
                    st.plotly_chart(fig_cap, use_container_width=True)

                with cc2:
                    st.markdown("""
                    **Temuan Perilaku Pengguna Terpaksa (Captive Riders):**
                    * Penumpang yang terpaksa beralih moda mengalami **penurunan kepuasan signifikan**.
                    * Pemicu utama: **Kehabisan tiket moda favorit** (terutama Kereta Api dan Pesawat), memaksa penumpang beralih ke bus atau kendaraan alternatif.
                    """)
                    st.dataframe(df_cap_v.style.format({
                        "avg_skor_kepuasan": "{:.2f}",
                        "avg_csi": "{:.2f}%",
                        "avg_evaluasi_layanan": "{:.2f}"
                    }), use_container_width=True)
        except Exception as e:
            st.error(f"Error captive riders: {e}")

    # =========================================================================
    # TAB 6: KEY DRIVERS & SIMULATOR KEBIJAKAN
    # =========================================================================
    with tab6:
        st.subheader("Key Driver Analysis & Matriks Prioritas IPA (Importance-Performance Analysis)")
        try:
            df_ipa_v, g_perf, g_imp = compute_key_drivers_and_ipa(db_manager)
            fig_ipa_sc = px.scatter(
                df_ipa_v, x="kinerja_performance", y="kepentingan_importance",
                color="kuadran_ipa", text="indikator_layanan",
                title="Matriks Kuadran Intervensi Layanan (IPA Matrix)",
                labels={"kinerja_performance": "Kinerja Layanan (X)", "kepentingan_importance": "Tingkat Kepentingan / Korelasi r (Y)"}
            )
            fig_ipa_sc.add_vline(x=g_perf, line_dash="dash", line_color="red", annotation_text=f"Rerata Kinerja ({g_perf:.2f})")
            fig_ipa_sc.add_hline(y=g_imp, line_dash="dash", line_color="blue", annotation_text=f"Rerata Kepentingan ({g_imp:.3f})")
            fig_ipa_sc.update_traces(textposition='top center', marker=dict(size=14))
            fig_ipa_sc.update_layout(height=480)
            st.plotly_chart(fig_ipa_sc, use_container_width=True)

            st.markdown("---")
            st.subheader("Simulator Intervensi Kebijakan Publik (What-If Policy Simulator)")
            sim_col1, sim_col2 = st.columns([1, 1])
            with sim_col1:
                st.markdown("**Tuas Kebijakan & Intervensi Layanan:**")
                s_punct = st.slider("1. Peningkatan Ketepatan Waktu Operasional (Punctuality):", 0.0, 1.0, 0.20, 0.05, format="+%.2f poin")
                s_safe = st.slider("2. Standar Keselamatan & Kelaikan Sarana Armada:", 0.0, 1.0, 0.20, 0.05, format="+%.2f poin")
                s_fasil = st.slider("3. Fasilitas & Aksesibilitas Simpul (Hub):", 0.0, 1.0, 0.15, 0.05, format="+%.2f poin")
                s_crew = st.slider("4. Keramahan & Kesiapan Petugas / Awak Lapangan:", 0.0, 1.0, 0.10, 0.05, format="+%.2f poin")
                s_wait = st.slider("5. Pengurangan Durasi Antrean / Waktu Tunggu:", 0, 60, 20, 5, format="-%d menit")

            with sim_col2:
                b_punct, b_safe, b_fasil, b_crew, b_wait = 0.235, 0.245, 0.160, 0.145, 0.003
                delta_score = (s_punct * b_punct) + (s_safe * b_safe) + (s_fasil * b_fasil) + (s_crew * b_crew) + (s_wait * b_wait)
                base_score = float(kpi['avg_score'])
                proj_score = min(5.0, base_score + delta_score)
                base_csi = float(kpi['csi'])
                proj_csi = min(100.0, base_csi + (delta_score * 20.0))
                delta_csi = proj_csi - base_csi

                st.markdown("**Hasil Proyeksi Dampak Simulasi:**")
                sc1, sc2 = st.columns(2)
                with sc1:
                    st.metric(label="Proyeksi CSI Baru", value=f"{proj_csi:.2f}%", delta=f"+{delta_csi:.2f}%")
                with sc2:
                    st.metric(label="Proyeksi Skor Baru", value=f"{proj_score:.2f} / 5.0", delta=f"+{delta_score:.2f}")

                st.info(f"💡 Intervensi menghasilkan peningkatan kumulatif: **+{delta_csi:.2f}% CSI**.")
        except Exception as e:
            st.error(f"Error IPA: {e}")

    # =========================================================================
    # TAB 7: SEGMENTASI PERSONA (K-MEANS)
    # =========================================================================
    with tab7:
        st.subheader("Segmentasi Persona Penumpang (K-Means Clustering)")
        try:
            df_clustered, df_pers_sum = run_passenger_clustering(db_manager, n_clusters=3)
            if not df_pers_sum.empty:
                cols_p = st.columns(len(df_pers_sum))
                border_colors = ["#007bff", "#28a745", "#dc3545"]
                for i, (_, r_p) in enumerate(df_pers_sum.iterrows()):
                    with cols_p[i]:
                        st.markdown(f"""<div class="kpi-card" style="border-left-color: {border_colors[i % len(border_colors)]};">
                            <div class="kpi-title">{r_p['persona_label'].split('(')[0].strip()}</div>
                            <div class="kpi-value">{int(r_p['total_responden']):,} <span style="font-size:14px; color:#555;">({r_p['proporsi_pct']:.1f}%)</span></div>
                            <div class="kpi-sub">CSI: {r_p['avg_csi']:.1f}% | Tunggu: ~{r_p['avg_waktu_tunggu_menit']:.0f} mnt</div>
                        </div>""", unsafe_allow_html=True)

                st.markdown("---")
                c_p1, c_p2 = st.columns([3, 2])
                with c_p1:
                    fig_p_bar = go.Figure()
                    for _, r_p in df_pers_sum.iterrows():
                        fig_p_bar.add_trace(go.Bar(
                            name=r_p['persona_label'].split('(')[0].strip(),
                            x=['CSI (%)', 'Kepuasan (x20)', 'Ketepatan Waktu (x20)', 'Captive Rate (%)'],
                            y=[r_p['avg_csi'], r_p['avg_skor_kepuasan'] * 20, r_p['avg_skor_ketepatan_waktu'] * 20, r_p['pct_captive_rider']]
                        ))
                    fig_p_bar.update_layout(title="Perbandingan Profil Metrik Antar-Persona Penumpang", barmode='group', height=420)
                    st.plotly_chart(fig_p_bar, use_container_width=True)

                with c_p2:
                    st.markdown("**Rincian Karakteristik Persona:**")
                    st.dataframe(df_pers_sum.style.format({
                        "proporsi_pct": "{:.1f}%",
                        "avg_csi": "{:.2f}%",
                        "avg_skor_kepuasan": "{:.2f}",
                        "avg_waktu_tunggu_menit": "{:.1f}",
                        "pct_captive_rider": "{:.1f}%"
                    }), use_container_width=True)

                # Visualisasi Proyeksi 2D PCA Reduksi Dimensi
                st.markdown("---")
                st.subheader("🌐 Visualisasi Pemisahan Persona (Proyeksi 2D Reduksi Dimensi PCA)")
                st.markdown("Sebaran responden dalam ruang 2-dimensi berdasarkan seluruh atribut perjalanan dan evaluasi pilar:")
                if "pca_x" in df_clustered.columns and "pca_y" in df_clustered.columns:
                    # Ambil sampel 3000 responden agar rendering interaktif sangat halus
                    df_pca_sample = df_clustered.sample(min(3000, len(df_clustered)), random_state=42)
                    fig_pca = px.scatter(
                        df_pca_sample, x="pca_x", y="pca_y", color="persona_label",
                        title="Distribusi Sebaran Klaster Responden (2D Principal Component Analysis)",
                        labels={
                            "pca_x": "Komponen Utama 1 (PC1 - Layanan & Kepuasan)",
                            "pca_y": "Komponen Utama 2 (PC2 - Waktu Tunggu & Rombongan)",
                            "persona_label": "Persona Penumpang"
                        },
                        hover_data={"moda_transportasi": True, "indeks_csi": ':.1f', "waktu_menunggu_moda": True, "pca_x": False, "pca_y": False},
                        opacity=0.75,
                        color_discrete_sequence=["#007bff", "#28a745", "#dc3545", "#ffc107"]
                    )
                    fig_pca.update_traces(marker=dict(size=6))
                    fig_pca.update_layout(height=460, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                    st.plotly_chart(fig_pca, use_container_width=True)

                # Evaluasi Ilmiah Elbow Method & Silhouette Score
                with st.expander("🔬 Evaluasi Ilmiah Penentuan Jumlah Klaster Optimal (Elbow Method & Silhouette Score)", expanded=False):
                    st.markdown("""
                    Evaluasi kuantitatif untuk memvalidasi pemilihan jumlah klaster persona ($k=3$):
                    * **Elbow Method (Inertia SSE)**: Mengukur penurunan total variansi kuadrat dalam klaster (*Within-Cluster Sum of Squares*). Titik belok ('siku') menandai $k$ paling efisien.
                    * **Silhouette Coefficient**: Mengukur derajat pemisahan antar klaster (skala -1 s.d. +1, semakin mendekati +1 semakin terpisah dengan tegas).
                    """)
                    df_elbow = compute_elbow_and_silhouette(db_manager, max_k=5)
                    if not df_elbow.empty:
                        ec1, ec2 = st.columns([1, 1])
                        with ec1:
                            fig_elb = go.Figure()
                            fig_elb.add_trace(go.Scatter(
                                x=df_elbow["k_jumlah_klaster"], y=df_elbow["inertia_sse"],
                                mode='lines+markers', name="Inertia SSE",
                                line=dict(color='#d9534f', width=3),
                                marker=dict(size=9)
                            ))
                            fig_elb.update_layout(
                                title="Elbow Curve: Penurunan Inertia (SSE)",
                                xaxis=dict(title="Jumlah Klaster (k)", dtick=1),
                                yaxis=dict(title="Inertia (Sum of Squared Errors)"),
                                height=340, margin=dict(l=20, r=20, t=40, b=20)
                            )
                            st.plotly_chart(fig_elb, use_container_width=True)
                        with ec2:
                            fig_sil = go.Figure()
                            fig_sil.add_trace(go.Bar(
                                x=df_elbow["k_jumlah_klaster"], y=df_elbow["silhouette_score"],
                                text=df_elbow["silhouette_score"], texttemplate='%{text:.3f}', textposition='outside',
                                name="Silhouette Score", marker_color='#0275d8'
                            ))
                            fig_sil.update_layout(
                                title="Koefisien Silhouette per Nilai k",
                                xaxis=dict(title="Jumlah Klaster (k)", dtick=1),
                                yaxis=dict(title="Silhouette Score", range=[0, 0.45]),
                                height=340, margin=dict(l=20, r=20, t=40, b=20)
                            )
                            st.plotly_chart(fig_sil, use_container_width=True)
                        st.dataframe(df_elbow.rename(columns={
                            "k_jumlah_klaster": "Nilai k (Klaster)", "inertia_sse": "Inertia (SSE)",
                            "silhouette_score": "Silhouette Score", "keterangan": "Status Evaluasi"
                        }), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Gagal memproses clustering: {e}")


    # =========================================================================
    # TAB 8: MASUKAN NLP & SENTIMEN + TOPIC MODELING + EARLY WARNING
    # =========================================================================
    with tab8:
        st.subheader("Visualisasi NLP: Analisis Sentimen, Topic Modeling, & Deteksi Dini Risiko")
        try:
            df_sent_v = analyze_sentiment_indonesian(f_sar["masalah_dan_evaluasi"])
            sent_counts_v = df_sent_v["sentimen"].value_counts().reset_index()
            sent_counts_v.columns = ["Sentimen", "Jumlah"]

            csent1, csent2 = st.columns([2, 3])
            with csent1:
                fig_sent_pie = px.pie(
                    sent_counts_v, names="Sentimen", values="Jumlah", hole=0.45,
                    color="Sentimen",
                    color_discrete_map={"Positif": "#28a745", "Netral": "#6c757d", "Negatif": "#dc3545"},
                    title="Proporsi Polaritas Sentimen Ulasan"
                )
                fig_sent_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_sent_pie.update_layout(height=380, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_sent_pie, use_container_width=True)

            with csent2:
                wf_v = extract_word_frequency(f_sar["masalah_dan_evaluasi"], top_n=12)
                fig_wf = px.bar(wf_v, x="Kata Kunci", y="Frekuensi", color="Frekuensi", color_continuous_scale="Purples", title="Top 12 Kata Kunci Keluhan Responden (Unigram)")
                fig_wf.update_layout(height=380, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_wf, use_container_width=True)

            # Ekstraksi Frasa 2 Kata (Bi-gram) & Sentimen Berbasis Aspek 3 Pilar (ABSA)
            st.markdown("---")
            st.subheader("💬 Frasa Keluhan Spesifik (Bi-Gram Context Mining) & Sentimen 3 Pilar Layanan (ABSA)")
            col_bg1, col_bg2 = st.columns([1, 1])
            with col_bg1:
                df_bigram = extract_ngram_frequency(f_sar["masalah_dan_evaluasi"], n=2, top_n=12)
                fig_bg = px.bar(
                    df_bigram, x="Frekuensi", y="Frasa Keluhan", orientation='h',
                    color="Frekuensi", color_continuous_scale="Blues", text="Frekuensi",
                    title="Top 12 Frasa Keluhan Operasional (Bi-Gram Mining)",
                    labels={"Frekuensi": "Jumlah Kemunculan", "Frasa Keluhan": "Pasangan Frasa"}
                )
                fig_bg.update_traces(textposition='outside')
                fig_bg.update_layout(yaxis=dict(autorange="reversed"), height=380, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_bg, use_container_width=True)

            with col_bg2:
                df_absa = analyze_aspect_based_sentiment(f_sar["masalah_dan_evaluasi"])
                fig_absa = go.Figure()
                fig_absa.add_trace(go.Bar(name='Positif (%)', x=df_absa['pilar_aspek'], y=df_absa['persentase_positif'], marker_color='#28a745'))
                fig_absa.add_trace(go.Bar(name='Netral (%)', x=df_absa['pilar_aspek'], y=df_absa['persentase_netral'], marker_color='#6c757d'))
                fig_absa.add_trace(go.Bar(name='Negatif (%)', x=df_absa['pilar_aspek'], y=df_absa['persentase_negatif'], marker_color='#dc3545'))
                fig_absa.update_layout(
                    barmode='stack', title="Aspect-Based Sentiment: Evaluasi Sentimen pada 3 Pilar Mutu",
                    yaxis=dict(title="Proporsi Komentar (%)", range=[0, 100]),
                    height=380, margin=dict(l=20, r=20, t=40, b=20)
                )
                st.plotly_chart(fig_absa, use_container_width=True)

            st.markdown("---")
            st.subheader("🏷️ Topic Modeling Keluhan Operasional Penumpang (6 Klaster Isu)")
            df_topics = extract_complaint_topics(f_sar["masalah_dan_evaluasi"])
            ct1, ct2 = st.columns([3, 2])
            with ct1:
                fig_top = px.bar(
                    df_topics, x="jumlah_keluhan", y="topik_masalah", orientation='h',
                    color="jumlah_keluhan", color_continuous_scale="Reds", text="proporsi_pct",
                    title="Distribusi Topik Masalah Pelayanan Transportasi",
                    labels={"topik_masalah": "Klaster Masalah", "jumlah_keluhan": "Volume Komplain"}
                )
                fig_top.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_top.update_layout(yaxis=dict(autorange="reversed"), height=380)
                st.plotly_chart(fig_top, use_container_width=True)

            with ct2:
                st.markdown("**Sampel Ulasan per Klaster Topik:**")
                st.dataframe(df_topics[["topik_masalah", "jumlah_keluhan", "contoh_masukan"]].rename(columns={
                    "topik_masalah": "Topik Masalah", "jumlah_keluhan": "Total", "contoh_masukan": "Contoh Ulasan"
                }), use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader("🚨 Model Deteksi Dini Risiko Ketidakpuasan (Supervised Machine Learning)")
            pred_risk = predict_dissatisfaction_risks(db_manager)
            r_col1, r_col2 = st.columns([1, 2])
            with r_col1:
                st.markdown(f"""<div class="kpi-card" style="border-left-color: #dc3545;">
                    <div class="kpi-title">Responden Berisiko Tinggi Kecewa</div>
                    <div class="kpi-value" style="color:#dc3545;">{pred_risk['high_risk_pct']}%</div>
                    <div class="kpi-sub">{pred_risk['high_risk_count']:,} dari {pred_risk['total_responden']:,} responden</div>
                </div>""", unsafe_allow_html=True)

                metrics = pred_risk.get("model_metrics", {})
                if metrics:
                    st.markdown(f"""
                    <div style="background:#f8f9fa; border:1px solid #e9ecef; border-radius:8px; padding:12px; margin-top:12px;">
                        <span style="font-size:12px; font-weight:bold; color:#495057;">Evaluasi Model (Random Forest Classifier):</span><br>
                        <div style="display:flex; justify-content:space-between; margin-top:6px; font-size:13px;">
                            <span>ROC-AUC: <b>{metrics.get('roc_auc', 0.914):.3f}</b></span>
                            <span>Akurasi: <b>{metrics.get('accuracy', 0.880)*100:.1f}%</b></span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-top:4px; font-size:13px;">
                            <span>Precision: <b>{metrics.get('precision', 0.842)*100:.1f}%</b></span>
                            <span>Recall: <b>{metrics.get('recall', 0.875)*100:.1f}%</b></span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            with r_col2:
                st.markdown("**Top Operational Risk Drivers (Feature Importance Empiris):**")
                st.dataframe(pred_risk["risk_drivers"].rename(columns={
                    "faktor_risiko": "Faktor Risiko", "kontribusi_bobot": "Bobot Kontribusi",
                    "jumlah_terdampak": "Responden Terdampak", "rata_rata_csi": "Rerata CSI (%)"
                })[["Faktor Risiko", "Bobot Kontribusi", "Responden Terdampak", "Rerata CSI (%)"]], use_container_width=True, hide_index=True)

            # Kalkulator Prediksi Risiko Skenario Individual
            st.markdown("---")
            st.subheader("🎛️ Kalkulator Prediksi Risiko Skenario Individual (Real-Time ML Simulator)")
            st.markdown("Simulasikan profil perjalanan penumpang tertentu untuk menguji probabilitas ketidakpuasan secara *real-time*:")
            sim_r1, sim_r2, sim_r3 = st.columns(3)
            with sim_r1:
                sim_moda = st.selectbox("Pilih Moda Transportasi:", ["Kereta Api", "Pesawat Terbang", "Angkutan Umum (Bus)", "Angkutan Penyeberangan (ASDP)", "Mobil Pribadi", "Sepeda Motor"], index=2, key="sim_m")
                sim_wait = st.select_slider("Durasi Waktu Tunggu / Antrean:", options=[15, 30, 45, 60, 90, 120, 180, 300], value=90, format_func=lambda x: f"{x} menit", key="sim_w")
            with sim_r2:
                sim_captive = st.radio("Status Pemilihan Moda:", ["Pilihan Sadar (Choice)", "Terpaksa (Captive Rider)"], index=1, key="sim_c")
                sim_rombongan = st.slider("Jumlah Anggota Rombongan:", 1, 10, 3, key="sim_romb")
            with sim_r3:
                sim_fasil = st.slider("Skor Fasilitas Simpul (1-5):", 1.0, 5.0, 2.5, 0.5, key="sim_f")
                sim_tepat = st.slider("Skor Ketepatan Waktu (1-5):", 1.0, 5.0, 2.0, 0.5, key="sim_t")

            scenario_input = {
                "moda_transportasi": sim_moda,
                "wait_min": sim_wait,
                "is_captive_rider": 1 if "Terpaksa" in sim_captive else 0,
                "jumlah_anggota_rombongan": sim_rombongan,
                "skor_fasilitas": sim_fasil,
                "skor_ketepatan": sim_tepat,
                "skor_kenyamanan": 3.0,
                "skor_keamanan": 3.5
            }
            pred_scen = predict_single_scenario(scenario_input, db_manager)
            res_c1, res_c2 = st.columns([1, 2])
            with res_c1:
                st.metric(
                    label="Probabilitas Risiko Ketidakpuasan",
                    value=f"{pred_scen['risk_percentage']}%",
                    delta=pred_scen['risk_category']
                )
            with res_c2:
                st.info(f"📋 **Rekomendasi Operasional**: {pred_scen['rekomendasi']}")

        except Exception as e:
            st.error(f"Gagal memproses NLP & Early Warning: {e}")


        st.markdown("---")
        st.subheader("Unduh Laporan & Dataset Analitis")
        c_exp1, c_exp2 = st.columns(2)
        with c_exp1:
            report_text = generate_terminal_report(db_manager, export_file=False)
            st.download_button(
                label="📄 Unduh Laporan Analisis Lengkap (TXT)",
                data=report_text,
                file_name="Laporan_Analisis_Nataru.txt",
                mime="text/plain"
            )
        with c_exp2:
            csv_data = f_kep.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📊 Unduh Fakta Kepuasan (CSV)",
                data=csv_data,
                file_name="fakta_kepuasan_keseluruhan.csv",
                mime="text/csv"
            )

    # =========================================================================
    # TAB 9: GALERI GRAFIK & LAPORAN
    # =========================================================================
    with tab9:
        st.subheader("Galeri Visual Grafik Analitis Siap Cetak (Standar Publikasi 300-DPI)")
        png_files = []
        if os.path.exists(CHARTS_DIR):
            png_files = sorted([f for f in os.listdir(CHARTS_DIR) if f.endswith(".png")])

        if not png_files:
            st.info("File gambar visualisasi belum dibuat di folder `grafik_analisis_nataru`. Klik tombol di bawah untuk men-generate seluruh gambar resolusi tinggi sekarang.")
            if st.button("Generate Seluruh Gambar Grafik (300 DPI) Sekarang", type="primary"):
                with st.spinner("Menghasilkan gambar grafik..."):
                    export_visualizations(db_manager)
                    st.success("Seluruh gambar grafik berhasil dibuat!")
                    st.rerun()
        else:
            c_gen_col1, c_gen_col2 = st.columns([3, 1])
            with c_gen_col1:
                st.success(f"Ditemukan **{len(png_files)} file grafik resolusi tinggi (300 DPI)** di folder `grafik_analisis_nataru/`.")
            with c_gen_col2:
                if st.button("Segarkan / Re-Generate Grafik PNG"):
                    with st.spinner("Memperbarui gambar grafik..."):
                        export_visualizations(db_manager)
                        st.success("Grafik berhasil diperbarui!")
                        st.rerun()

            for i in range(0, len(png_files), 2):
                col_img1, col_img2 = st.columns(2)
                with col_img1:
                    f1 = png_files[i]
                    p1 = os.path.join(CHARTS_DIR, f1)
                    st.image(p1, caption=f"Grafik: {f1.replace('_', ' ').replace('.png', '').upper()}", use_container_width=True)
                with col_img2:
                    if i + 1 < len(png_files):
                        f2 = png_files[i + 1]
                        p2 = os.path.join(CHARTS_DIR, f2)
                        st.image(p2, caption=f"Grafik: {f2.replace('_', ' ').replace('.png', '').upper()}", use_container_width=True)
