"""
Modul Pemrosesan Bahasa Alami (NLP) & Analisis Sentimen Masukan Penumpang.
Menyediakan:
1. Ekstraksi frekuensi kata kunci & frasa keluhan (N-gram)
2. Analisis polaritas sentimen Bahasa Indonesia (Positif, Netral, Negatif)
3. Topic Modeling Keluhan Operasional Penumpang (6 Klaster Isu Utama)
"""

import re
from collections import Counter
from typing import Dict, Any, List
import pandas as pd
import numpy as np

STOPWORDS_ID = {
    "yang", "dan", "di", "ke", "dari", "untuk", "pada", "adalah", "ini", "itu",
    "dengan", "agar", "bisa", "lebih", "dapat", "ada", "tidak", "juga", "sudah",
    "saya", "kami", "sangat", "harus", "karena", "saat", "oleh", "dalam", "lagi",
    "bagi", "supaya", "mohon", "tolong", "perlu", "nya", "tetap", "selalu", "kalo",
    "kalau", "mau", "akan", "aja", "saja", "udah", "jadi", "masih", "belum", "apa"
}

def extract_word_frequency(series_text: pd.Series, top_n: int = 25) -> pd.DataFrame:
    """Mengekstrak kata kunci paling sering muncul dalam ulasan responden."""
    all_words = []
    for text in series_text.dropna():
        words = re.findall(r'[a-zA-Z]{3,}', str(text).lower())
        all_words.extend([w for w in words if w not in STOPWORDS_ID])

    counts = Counter(all_words).most_common(top_n)
    return pd.DataFrame(counts, columns=["Kata Kunci", "Frekuensi"])

def analyze_sentiment_indonesian(series_text: pd.Series) -> pd.DataFrame:
    """
    Analisis sentimen berbasis leksikon Bahasa Indonesia yang disesuaikan dengan domain transportasi publik.
    Mengembalikan DataFrame dengan kolom id_entry, sentimen (Positif, Netral, Negatif), dan skor_polaritas.
    """
    pos_words = {
        'baik', 'bagus', 'puas', 'ramah', 'cepat', 'nyaman', 'bersih', 'tertib', 'aman', 'lancar',
        'tepat', 'hebat', 'mantap', 'memuaskan', 'membantu', 'teratur', 'dingin', 'mudah', 'terjangkau',
        'murah', 'luas', 'lengkap', 'menyenangkan', 'profesional', 'responsif', 'terawat', 'terima kasih',
        'makasih', 'siap', 'senang', 'keren', 'jempol', 'top', 'rapi'
    }
    neg_words = {
        'buruk', 'kecewa', 'lambat', 'kotor', 'bau', 'panas', 'sesak', 'sempit', 'macet', 'mahal',
        'rusak', 'antri', 'antrean', 'antrian', 'telat', 'terlambat', 'delay', 'bising', 'berantakan',
        'kasar', 'sulit', 'susah', 'habis', 'kurang', 'kehabisan', 'parah', 'berdesakan', 'bahaya',
        'berbahaya', 'keluhan', 'jelek', 'turunkan', 'minim', 'amburadul', 'pungli', 'calon'
    }
    negation_words = {'tidak', 'tak', 'bukan', 'kurang', 'belum', 'jangan', 'gak', 'nggak'}

    results = []
    for idx, text in series_text.items():
        if pd.isna(text) or str(text).strip().lower() in ('', 'nan', 'none', '-', 'tidak ada', 'nihil', 'tidak diketahui'):
            results.append({'id_entry': idx, 'sentimen': 'Netral', 'skor_polaritas': 0.0, 'kata_positif': 0, 'kata_negatif': 0})
            continue
        
        t = str(text).lower()
        words = re.findall(r'[a-zA-Z]{3,}', t)
        pos_score = 0
        neg_score = 0
        for i, w in enumerate(words):
            is_negated = (i > 0 and words[i-1] in negation_words)
            if w in pos_words:
                if is_negated:
                    neg_score += 1
                else:
                    pos_score += 1
            elif w in neg_words:
                if is_negated:
                    pos_score += 1
                else:
                    neg_score += 1
        
        net = pos_score - neg_score
        if net > 0:
            cat = 'Positif'
        elif net < 0:
            cat = 'Negatif'
        else:
            cat = 'Netral'
        
        results.append({
            'id_entry': idx,
            'sentimen': cat,
            'skor_polaritas': float(net),
            'kata_positif': pos_score,
            'kata_negatif': neg_score
        })
    
    return pd.DataFrame(results)

def extract_complaint_topics(series_text: pd.Series) -> pd.DataFrame:
    """
    Topic Modeling Berbasis Aturan & Pola Leksikal (Rule-Based Operational Topic Modeling).
    Mengelompokkan keluhan penumpang ke dalam 6 domain operasional kebijakan transportasi.
    """
    topic_rules = {
        "Aksesibilitas & Tiket": [
            "tiket", "tarif", "harga", "mahal", "habis", "kehabisan", "beli", "ferizy", "pesan", "aplikasi", "server", "kuota"
        ],
        "Ketepatan Waktu & Delay": [
            "delay", "terlambat", "telat", "jadwal", "waktu", "tunggu", "antri", "antrean", "antrian", "mundur", "lambat"
        ],
        "Kebersihan & Kenyamanan Armada": [
            "toilet", "kotor", "bau", "ac", "panas", "kabin", "gerbong", "kursi", "sempit", "sesak", "berdesakan", "sampah"
        ],
        "Kelancaran Lalin & Jalan Raya": [
            "macet", "jalan", "aspal", "lubang", "contra", "one way", "rest area", "jalur", "rambu", "rekayasa", "truk"
        ],
        "Fasilitas Simpul (Hub Transit)": [
            "terminal", "stasiun", "pelabuhan", "bandara", "ruang tunggu", "fasilitas", "parkir", "mushola", "gate", "eskalator"
        ],
        "Pelayanan Petugas & Keamanan": [
            "petugas", "ramah", "kasar", "keamanan", "copet", "pungli", "calo", "sopir", "crew", "bantuan", "informasi"
        ]
    }

    counts = {t: 0 for t in topic_rules}
    sample_texts = {t: [] for t in topic_rules}

    for text in series_text.dropna():
        t_clean = str(text).lower()
        if t_clean in ('', 'nan', 'none', '-', 'tidak ada', 'nihil'):
            continue
        
        matched_any = False
        for topic, keywords in topic_rules.items():
            if any(k in t_clean for k in keywords):
                counts[topic] += 1
                if len(sample_texts[topic]) < 3 and len(t_clean) > 10:
                    sample_texts[topic].append(str(text).strip())
                matched_any = True

    total_mentions = sum(counts.values()) or 1
    rows = []
    for topic, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        rows.append({
            "topik_masalah": topic,
            "jumlah_keluhan": count,
            "proporsi_pct": round((count / total_mentions) * 100, 1),
            "contoh_masukan": " | ".join(sample_texts[topic][:2]) if sample_texts[topic] else "Tidak ada catatan spesifik"
        })

    return pd.DataFrame(rows)

def extract_ngram_frequency(series_text: pd.Series, n: int = 2, top_n: int = 15) -> pd.DataFrame:
    """
    Ekstraksi Frasa Berulang (N-gram Phrasal Mining, default: Bi-grams / 2 kata).
    Menangkap konteks keluhan operasional yang lebih spesifik dibanding kata tunggal (unigram).
    Contoh: 'jalan rusak', 'ruang tunggu', 'jalan berlubang', 'kurang bersih'.
    """
    all_ngrams = []
    for text in series_text.dropna():
        words = [w for w in re.findall(r'[a-zA-Z]{3,}', str(text).lower()) if w not in STOPWORDS_ID]
        if len(words) >= n:
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i:i+n])
                all_ngrams.append(phrase)

    counts = Counter(all_ngrams).most_common(top_n)
    if not counts:
        return pd.DataFrame(columns=["Frasa Keluhan", "Frekuensi"])
    
    df_ngrams = pd.DataFrame(counts, columns=["Frasa Keluhan", "Frekuensi"])
    return df_ngrams

def analyze_aspect_based_sentiment(series_text: pd.Series) -> pd.DataFrame:
    """
    Analisis Sentimen Berbasis Aspek (Aspect-Based Sentiment Analysis / ABSA).
    Memetakan polaritas sentimen publik langsung ke dalam 3 Pilar Utama Mutu Layanan:
    1. Prasarana (Simpul Hub Transit, Terminal, Stasiun, Fasilitas, Toilet, Ruang Tunggu)
    2. Sarana (Armada Kendaraan, Kabin, Kereta, Bus, Kursi, AC, Kebersihan Armada)
    3. Manajemen Operasional (Jadwal, Ketepatan Waktu, Delay, Petugas, Loket, Tiket, Antrean)
    """
    aspect_keywords = {
        "Pilar Prasarana (Simpul Transit)": [
            "terminal", "stasiun", "pelabuhan", "bandara", "toilet", "ruang tunggu",
            "parkir", "mushola", "fasilitas", "loket", "gate", "eskalator", "peron", "jalan", "aspal"
        ],
        "Pilar Sarana (Armada & Kabin)": [
            "kabin", "gerbong", "bus", "kapal", "pesawat", "mobil", "kursi", "seat",
            "dingin", "panas", "armada", "kendaraan", "ac", "mesin"
        ],
        "Pilar Manajemen Operasional": [
            "jadwal", "waktu", "delay", "terlambat", "telat", "antri", "antrean",
            "antrian", "petugas", "sopir", "supir", "crew", "awak", "tiket", "tarif", "harga", "aplikasi", "layanan"
        ]
    }

    pos_words = {
        'baik', 'bagus', 'puas', 'ramah', 'cepat', 'nyaman', 'bersih', 'tertib', 'aman', 'lancar',
        'tepat', 'hebat', 'mantap', 'memuaskan', 'membantu', 'teratur', 'dingin', 'mudah', 'terjangkau',
        'murah', 'luas', 'lengkap', 'menyenangkan', 'profesional', 'responsif', 'terawat', 'siap'
    }
    neg_words = {
        'buruk', 'kecewa', 'lambat', 'kotor', 'bau', 'panas', 'sesak', 'sempit', 'macet', 'mahal',
        'rusak', 'antri', 'antrean', 'antrian', 'telat', 'terlambat', 'delay', 'bising', 'berantakan',
        'kasar', 'sulit', 'susah', 'habis', 'kurang', 'kehabisan', 'parah', 'berdesakan', 'bahaya',
        'berbahaya', 'keluhan', 'jelek', 'turunkan', 'minim', 'amburadul', 'lubang'
    }
    negation_words = {'tidak', 'tak', 'bukan', 'kurang', 'belum', 'jangan', 'gak', 'nggak'}

    results = {
        asp: {"positif": 0, "negatif": 0, "netral": 0, "mentions": 0}
        for asp in aspect_keywords
    }

    for text in series_text.dropna():
        t_clean = str(text).lower()
        if t_clean in ('', 'nan', 'none', '-', 'tidak ada', 'nihil'):
            continue

        words = re.findall(r'[a-zA-Z]{3,}', t_clean)
        if not words:
            continue

        # Hitung polaritas kalimat lokal
        pos_cnt = 0
        neg_cnt = 0
        for i, w in enumerate(words):
            is_negated = (i > 0 and words[i-1] in negation_words)
            if w in pos_words:
                if is_negated:
                    neg_cnt += 1
                else:
                    pos_cnt += 1
            elif w in neg_words:
                if is_negated:
                    pos_cnt += 1
                else:
                    neg_cnt += 1

        net = pos_cnt - neg_cnt
        label = "positif" if net > 0 else ("negatif" if net < 0 else "netral")

        # Cek keterkaitan dengan masing-masing pilar aspek
        for asp, kws in aspect_keywords.items():
            if any(k in t_clean for k in kws):
                results[asp]["mentions"] += 1
                results[asp][label] += 1

    summary_rows = []
    for asp, data in results.items():
        total = data["mentions"]
        pos = data["positif"]
        neg = data["negatif"]
        neu = data["netral"]
        pos_ratio = round((pos / total * 100), 1) if total > 0 else 0.0
        neg_ratio = round((neg / total * 100), 1) if total > 0 else 0.0
        neu_ratio = round((neu / total * 100), 1) if total > 0 else 0.0

        summary_rows.append({
            "pilar_aspek": asp,
            "total_komentar": total,
            "positif_count": pos,
            "negatif_count": neg,
            "netral_count": neu,
            "persentase_positif": pos_ratio,
            "persentase_negatif": neg_ratio,
            "persentase_netral": neu_ratio,
            "net_sentiment_score": round(pos_ratio - neg_ratio, 1)
        })

    return pd.DataFrame(summary_rows).sort_values("total_komentar", ascending=False).reset_index(drop=True)

