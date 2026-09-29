"""
Pembangun Peta Geospasial Interaktif Transportasi Nataru (GIS Mapping).
Memanfaatkan OpenStreetMap Tiles via Plotly Mapbox (bebas token API)
untuk memetakan sebaran simpul transportasi nasional dan koridor pergerakan mudik (OD Corridors).
"""

from typing import Dict, Any, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def build_hub_interactive_map(df_geo_hubs: pd.DataFrame, category_filter: Optional[str] = None) -> go.Figure:
    """
    Membangun peta interaktif sebaran simpul transportasi nasional berbasis OpenStreetMap.
    Titik simpul diwarnai berdasarkan status kepuasan (Hijau = Sangat Puas, Kuning = Cukup, Merah = Perlu Perbaikan)
    dan ukuran lingkaran proporsional terhadap jumlah sampel responden.
    """
    if df_geo_hubs.empty:
        fig_empty = go.Figure()
        fig_empty.update_layout(
            title="Data koordinat simpul transportasi tidak tersedia",
            height=450
        )
        return fig_empty

    df = df_geo_hubs.copy()
    if category_filter and category_filter != "Semua":
        df = df[df["kategori"] == category_filter]

    color_map = {
        "Sangat Puas / Unggul": "#28a745",
        "Baik / Cukup": "#ffc107",
        "Perlu Perbaikan Segera": "#dc3545"
    }

    fig = px.scatter_mapbox(
        df,
        lat="lat",
        lon="lon",
        color="status_mutu",
        color_discrete_map=color_map,
        size="total_sampel",
        size_max=24,
        hover_name="nama_simpul",
        hover_data={
            "kategori": True,
            "wilayah": True,
            "avg_csi": ':.1f',
            "avg_skor": ':.2f',
            "total_sampel": ':,',
            "status_mutu": True,
            "lat": False,
            "lon": False
        },
        zoom=4.3,
        center=dict(lat=-2.5, lon=118.0),
        mapbox_style="open-street-map",
        title="Peta Interaktif Sebaran & Kinerja Simpul Transportasi (OpenStreetMap)"
    )

    fig.update_layout(
        height=560,
        margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(
            title="Status Kinerja Simpul",
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    return fig

def build_od_flow_map(df_od_flows: pd.DataFrame, top_n: int = 15) -> go.Figure:
    """
    Membangun peta interaktif koridor pergerakan arus mudik Asal-Tujuan (Origin-Destination Flow Map).
    Menampilkan garis trayek penghubung antar-wilayah dengan ketebalan garis sesuai volume pemudik.
    """
    if df_od_flows.empty:
        fig_empty = go.Figure()
        fig_empty.update_layout(
            title="Data koridor perjalanan Asal-Tujuan tidak tersedia",
            height=450
        )
        return fig_empty

    df = df_od_flows.head(top_n).copy()
    max_vol = df['volume_penumpang'].max() or 1

    fig = go.Figure()

    # 1. Gambar Garis Koridor Trayek (OD Corridors)
    for _, r in df.iterrows():
        vol = r['volume_penumpang']
        line_w = max(1.5, min((vol / max_vol) * 7.0, 8.0))
        
        fig.add_trace(go.Scattermapbox(
            lat=[r['lat_asal'], r['lat_tujuan']],
            lon=[r['lon_asal'], r['lon_tujuan']],
            mode='lines',
            line=dict(width=line_w, color='#0d6efd'),
            opacity=0.7,
            hoverinfo='text',
            text=f"<b>Koridor:</b> {r['koridor_rute']}<br><b>Volume Pemudik:</b> {vol:,} responden",
            name=r['koridor_rute'],
            showlegend=False
        ))

    # 2. Gambar Marker Titik Asal & Tujuan
    all_points = []
    for _, r in df.iterrows():
        all_points.append({"lokasi": r["asal_perjalanan"], "lat": r["lat_asal"], "lon": r["lon_asal"], "tipe": "Titik Keberangkatan"})
        all_points.append({"lokasi": r["tujuan_perjalanan"], "lat": r["lat_tujuan"], "lon": r["lon_tujuan"], "tipe": "Titik Tujuan"})
    
    df_pts = pd.DataFrame(all_points).drop_duplicates(subset=["lokasi", "lat", "lon"])
    
    fig.add_trace(go.Scattermapbox(
        lat=df_pts["lat"],
        lon=df_pts["lon"],
        mode='markers+text',
        marker=dict(size=10, color='#dc3545'),
        text=df_pts["lokasi"],
        textposition="top right",
        hoverinfo='text',
        name="Titik Wilayah OD",
        showlegend=False
    ))

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=-3.0, lon=117.5),
            zoom=4.4
        ),
        title=f"Peta Koridor Arus Mudik Terpadat ({top_n} Rute Utama Nasional)",
        height=560,
        margin=dict(l=0, r=0, t=40, b=0)
    )
    return fig

def build_sankey_od_diagram(sankey_data: Dict[str, Any], title: str = "Diagram Alir Mobilitas Pemudik Antar-Wilayah (Origin-Destination Sankey)") -> go.Figure:
    """
    Membangun diagram aliran interaktif Plotly Sankey untuk visualisasi koridor pergerakan pemudik.
    Menampilkan volume pergerakan antar wilayah asal dan tujuan secara proporsional.
    """
    if not sankey_data or not sankey_data.get("node_labels"):
        fig_empty = go.Figure()
        fig_empty.update_layout(title="Data diagram aliran tidak tersedia", height=450)
        return fig_empty

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=18,
            thickness=20,
            line=dict(color="#2c3e50", width=0.8),
            label=sankey_data["node_labels"],
            color=sankey_data["node_colors"],
            hovertemplate="Wilayah: <b>%{label}</b><br>Volume: <b>%{value:,} responden</b><extra></extra>"
        ),
        link=dict(
            source=sankey_data["source_indices"],
            target=sankey_data["target_indices"],
            value=sankey_data["values"],
            hovertemplate="Arus: <b>%{source.label}</b> &rarr; <b>%{target.label}</b><br>Volume Pemudik: <b>%{value:,} responden</b><extra></extra>",
            color="rgba(41, 128, 185, 0.35)"
        )
    )])

    fig.update_layout(
        title_text=title,
        font=dict(size=12, family="Arial, sans-serif"),
        height=500,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig

