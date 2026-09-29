"""
Analisis Data Geospasial Transportasi Nataru.
Mengekstrak arus perjalanan Asal-Tujuan (Origin-Destination Flow)
serta memetakan kinerja simpul transportasi ke koordinat lintang/bujur Indonesia.
"""

from typing import Tuple, Dict, Any
import pandas as pd
from ..config.geo_constants import INDONESIA_REGIONS_GEO, MAJOR_HUBS_GEO
from ..pipeline.text_cleaner import clean_hub_name

def get_od_flow_data(db_manager, top_n: int = 20) -> pd.DataFrame:
    """
    Menghasilkan data arus perjalanan pemudik Asal-Tujuan (OD Matrix Flow)
    lengkap dengan koordinat geografis wilayah Indonesia untuk pemetaan geospasial.
    """
    query = f"""
        SELECT asal_perjalanan, tujuan_perjalanan, COUNT(*) as volume_penumpang
        FROM dim_perjalanan 
        WHERE asal_perjalanan IS NOT NULL AND asal_perjalanan != 'Tidak Diketahui'
          AND tujuan_perjalanan IS NOT NULL AND tujuan_perjalanan != 'Tidak Diketahui'
        GROUP BY asal_perjalanan, tujuan_perjalanan 
        ORDER BY volume_penumpang DESC 
        LIMIT {top_n};
    """
    df = db_manager.query(query)
    if df.empty:
        return pd.DataFrame()

    def resolve_coord(loc_str: str) -> Tuple[float, float]:
        s_up = str(loc_str).upper().strip()
        for k, coord in INDONESIA_REGIONS_GEO.items():
            if k in s_up:
                return coord
        return (-6.2088, 106.8456)

    df['lat_asal'] = df['asal_perjalanan'].apply(lambda x: resolve_coord(x)[0])
    df['lon_asal'] = df['asal_perjalanan'].apply(lambda x: resolve_coord(x)[1])
    df['lat_tujuan'] = df['tujuan_perjalanan'].apply(lambda x: resolve_coord(x)[0])
    df['lon_tujuan'] = df['tujuan_perjalanan'].apply(lambda x: resolve_coord(x)[1])
    df['koridor_rute'] = df['asal_perjalanan'] + " -> " + df['tujuan_perjalanan']
    return df

def get_sankey_od_data(db_manager, level: str = "provinsi", top_n: int = 15) -> Dict[str, Any]:
    """
    Mengekstrak data aliran mobilitas pemudik Asal-Tujuan untuk visualisasi Diagram Sankey (OD Flow Sankey).
    Mendukung level 'provinsi' (makro regional) maupun 'kota' (mikro koridor perjalanan).
    Mengembalikan struktur nodes, links, values, dan palet warna untuk Plotly go.Sankey.
    """
    q = """
        SELECT asal_perjalanan, tujuan_perjalanan, COUNT(*) as volume
        FROM dim_perjalanan
        WHERE asal_perjalanan IS NOT NULL AND asal_perjalanan != 'Tidak Diketahui'
          AND tujuan_perjalanan IS NOT NULL AND tujuan_perjalanan != 'Tidak Diketahui'
        GROUP BY asal_perjalanan, tujuan_perjalanan;
    """
    df = db_manager.query(q)
    if df.empty:
        return {
            "node_labels": [], "source_indices": [], "target_indices": [],
            "values": [], "node_colors": [], "df_flow": pd.DataFrame()
        }

    def extract_prov(text):
        if not text:
            return "Lainnya"
        parts = str(text).split(",")
        if len(parts) > 1:
            clean = parts[-1].strip().title()
        else:
            clean = str(text).strip().title()
        return clean.replace("Provinsi ", "").replace("Prov. ", "").strip()

    if level == "provinsi":
        df["asal_clean"] = df["asal_perjalanan"].apply(extract_prov)
        df["tujuan_clean"] = df["tujuan_perjalanan"].apply(extract_prov)
    else:
        df["asal_clean"] = df["asal_perjalanan"].astype(str).str.title().str.strip()
        df["tujuan_clean"] = df["tujuan_perjalanan"].astype(str).str.title().str.strip()

    df_flow = df.groupby(["asal_clean", "tujuan_clean"])["volume"].sum().reset_index()
    df_flow = df_flow.sort_values("volume", ascending=False).head(top_n).reset_index(drop=True)

    # Buat label node unik dengan pembeda [Asal] dan [Tujuan] agar tidak terjadi loop siklik pada Sankey
    unique_sources = list(df_flow["asal_clean"].unique())
    unique_targets = list(df_flow["tujuan_clean"].unique())

    # Map nama node ke indeks
    source_labels = [f"{s} (Asal)" for s in unique_sources]
    target_labels = [f"{t} (Tujuan)" for t in unique_targets]
    all_node_labels = source_labels + target_labels

    source_idx_map = {s: i for i, s in enumerate(unique_sources)}
    target_idx_map = {t: len(unique_sources) + j for j, t in enumerate(unique_targets)}

    source_indices = [source_idx_map[r["asal_clean"]] for _, r in df_flow.iterrows()]
    target_indices = [target_idx_map[r["tujuan_clean"]] for _, r in df_flow.iterrows()]
    values = [int(r["volume"]) for _, r in df_flow.iterrows()]

    # Skema warna elegan untuk node dan flow
    source_palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
    node_colors = []
    for i in range(len(all_node_labels)):
        if i < len(unique_sources):
            node_colors.append(source_palette[i % len(source_palette)])
        else:
            node_colors.append("#34495e")

    return {
        "node_labels": all_node_labels,
        "source_indices": source_indices,
        "target_indices": target_indices,
        "values": values,
        "node_colors": node_colors,
        "df_flow": df_flow
    }

def get_hub_performance_geo(db_manager) -> pd.DataFrame:
    """
    Menghasilkan data peringkat simpul transportasi yang dipetakan ke koordinat geografis
    lengkap dengan status kepuasan (Hijau = Sangat Puas >=85%, Kuning = 75-84.9%, Merah = <75%).
    """
    hub_queries = [
        ("Bandara Udara", "udara_bandara_asal"),
        ("Stasiun Kereta Api", "ka_stasiun_asal"),
        ("Pelabuhan ASDP", "asdp_pelabuhan_asal"),
        ("Terminal Bus", "bus_terminal_asal")
    ]
    all_hubs = []
    for cat_label, col_name in hub_queries:
        q = f"""
            SELECT a.{col_name} as raw_simpul, COUNT(*) as n, 
                   AVG(k.skor_kepuasan) as avg_skor, AVG(k.indeks_csi) as avg_csi
            FROM data_asli a
            JOIN fakta_kepuasan_keseluruhan k ON a.id = k.id_responden
            WHERE a.{col_name} IS NOT NULL AND a.{col_name} != ''
            GROUP BY a.{col_name}
            HAVING COUNT(*) >= 8;
        """
        try:
            df_sub = db_manager.query(q)
            for _, r in df_sub.iterrows():
                c_name = clean_hub_name(r['raw_simpul'])
                if c_name == "-":
                    continue
                
                lat, lon, loc_desc = -6.2088, 106.8456, "Indonesia"
                found = False
                for k_hub, (h_lat, h_lon, h_type, h_loc) in MAJOR_HUBS_GEO.items():
                    if k_hub.lower() in c_name.lower() or k_hub.lower() in str(r['raw_simpul']).lower():
                        lat, lon, loc_desc = h_lat, h_lon, h_loc
                        found = True
                        break
                
                if not found:
                    for k_reg, (r_lat, r_lon) in INDONESIA_REGIONS_GEO.items():
                        if k_reg.lower() in c_name.lower() or k_reg.lower() in str(r['raw_simpul']).lower():
                            lat, lon, loc_desc = r_lat, r_lon, k_reg.title()
                            found = True
                            break

                csi_val = round(float(r['avg_csi']), 2)
                status = "Sangat Puas / Unggul" if csi_val >= 85.0 else ("Baik / Cukup" if csi_val >= 75.0 else "Perlu Perbaikan Segera")
                color = "#28a745" if csi_val >= 85.0 else ("#ffc107" if csi_val >= 75.0 else "#dc3545")

                all_hubs.append({
                    "kategori": cat_label,
                    "nama_simpul": c_name,
                    "total_sampel": int(r['n']),
                    "avg_skor": round(float(r['avg_skor']), 2),
                    "avg_csi": csi_val,
                    "status_mutu": status,
                    "warna_marker": color,
                    "wilayah": loc_desc,
                    "lat": lat,
                    "lon": lon
                })
        except Exception:
            pass

    return pd.DataFrame(all_hubs)

