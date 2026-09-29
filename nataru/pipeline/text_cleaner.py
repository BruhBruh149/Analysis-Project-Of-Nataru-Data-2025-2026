"""
Fungsi Utilitas Pembersihan & Standarisasi Teks.
Merapikan nama simpul transportasi, normalisasi teks survei, dan perlakuan khusus singkatan transportasi.
"""

import re
from typing import Any
import pandas as pd

def clean_hub_name(text: Any) -> str:
    """
    Membersihkan, menstandarisasi, dan merapikan penamaan simpul transportasi ke format Title Case.
    Menghilangkan duplikasi kata berulang dan menjaga singkatan resmi (KAI, ASDP, YIA, dll).
    """
    if not text or pd.isna(text):
        return "-"
    s = str(text).strip()
    if s.lower() in ("nan", "none", "null", "-", "", "tidak diketahui"):
        return "-"
    s = re.sub(r'\s*,\s*', ', ', s)
    s = re.sub(r'\s+', ' ', s)
    parts = [p.strip() for p in s.split(',') if p.strip()]
    cleaned_parts = []
    for p in parts:
        words = p.split(' ')
        c_words = []
        for w in words:
            if w.upper() in ("DKI", "DIY", "ASDP", "KA", "SPBU", "UPT", "PT", "II", "III", "IV", "V", "KAI", "KRL", "MRT", "LRT", "BRT", "YIA"):
                c_words.append(w.upper())
            elif w.lower() in ("prov.", "prov"):
                c_words.append("Prov.")
            elif w.lower() in ("kota", "kab.", "kab"):
                c_words.append(w.capitalize())
            else:
                c_words.append(w.capitalize())
        part_title = " ".join(c_words)
        if not cleaned_parts or part_title.lower() != cleaned_parts[-1].lower():
            cleaned_parts.append(part_title)
    res = ", ".join(cleaned_parts)
    return res if res else "-"

def clean_column_name(text: Any) -> str:
    """Menghasilkan nama kolom SQL yang aman (alphanumeric dan underscore)."""
    h_clean = re.sub(r'[^a-zA-Z0-9_]', '_', str(text).strip().lower())
    h_clean = re.sub(r'_+', '_', h_clean).strip('_')
    return h_clean if h_clean else "kolom"
