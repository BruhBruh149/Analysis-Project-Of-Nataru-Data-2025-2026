"""
Konstanta Geografis Wilayah & Simpul Transportasi Utama Indonesia.
Digunakan untuk geocoding, pemetaan rute asal-tujuan (OD Flow),
dan visualisasi peta sebaran simpul transportasi nasional.
"""

# Koordinat Lintang-Bujur Wilayah / Provinsi / Kota Utama di Indonesia
INDONESIA_REGIONS_GEO = {
    "JAWA TENGAH": (-7.1509, 110.1402), "KENDAL": (-6.9248, 110.2038), "SEMARANG": (-6.9667, 110.4167),
    "SUMATERA SELATAN": (-3.3194, 104.9147), "PALEMBANG": (-2.9909, 104.7566), "OGAN KOMERING ILIR": (-3.3833, 105.1500),
    "SUMATERA BARAT": (-0.7399, 100.8000), "PADANG": (-0.9471, 100.4172), "SOLOK": (-0.7989, 100.6536),
    "JAWA BARAT": (-6.9175, 107.6191), "TASIKMALAYA": (-7.3274, 108.2207), "CIAMIS": (-7.3256, 108.3533),
    "PANGANDARAN": (-7.6833, 108.6500), "BANDUNG": (-6.9175, 107.6191), "GARUT": (-7.2278, 107.9086),
    "RIAU": (0.5071, 101.4478), "PEKANBARU": (0.5071, 101.4478), "PELALAWAN": (0.3333, 102.0000),
    "BANTEN": (-6.4058, 106.0640), "SERANG": (-6.1104, 106.1640), "PANDEGLANG": (-6.3083, 106.1067), "CILEGON": (-6.0028, 106.0539),
    "DKI JAKARTA": (-6.2088, 106.8456), "JAKARTA": (-6.2088, 106.8456), "BOGOR": (-6.5971, 106.8060),
    "KARAWANG": (-6.3072, 107.3072), "CIKAMPEK": (-6.4167, 107.4500),
    "BANYUMAS": (-7.5147, 109.2942), "CILACAP": (-7.7279, 109.0059),
    "MAGELANG": (-7.4706, 110.2178), "DI YOGYAKARTA": (-7.7956, 110.3695), "SLEMAN": (-7.7156, 110.3556), "YOGYAKARTA": (-7.7956, 110.3695),
    "JAWA TIMUR": (-7.5361, 112.2384), "SURABAYA": (-7.2575, 112.7521), "MALANG": (-7.9839, 112.6214),
    "BALI": (-8.4095, 115.1889), "DENPASAR": (-8.6705, 115.2126), "BADUNG": (-8.5833, 115.1833), "JEMBRANA": (-8.3000, 114.6667),
    "SULAWESI SELATAN": (-3.6687, 119.9740), "MAKASSAR": (-5.1477, 119.4327),
    "SULAWESI TENGAH": (-1.4300, 121.4456), "MOROWALI": (-2.6500, 121.9000),
    "SUMATERA UTARA": (2.1154, 99.5451), "MEDAN": (3.5952, 98.6722),
    "LAMPUNG": (-4.5586, 105.4068), "BANDAR LAMPUNG": (-5.4500, 105.2667)
}

# Koordinat dan Metadata Simpul Transportasi Utama Nasional (Bandara, Stasiun KA, Pelabuhan, Terminal)
# Format: (lat, lon, kategori, lokasi_deskripsi)
MAJOR_HUBS_GEO = {
    # Bandara Udara
    "Soekarno-Hatta": (-6.1256, 106.6558, "Bandara", "Cengkareng / Banten"),
    "Halim Perdanakusuma": (-6.2655, 106.8906, "Bandara", "Jakarta Timur"),
    "Juanda": (-7.3798, 112.7874, "Bandara", "Sidoarjo / Surabaya"),
    "I Gusti Ngurah Rai": (-8.7482, 115.1672, "Bandara", "Badung / Bali"),
    "Kualanamu": (3.6422, 98.8853, "Bandara", "Deli Serdang / Medan"),
    "Sultan Hasanuddin": (-5.0617, 119.5540, "Bandara", "Maros / Makassar"),
    "YIA": (-7.9072, 110.0565, "Bandara", "Kulon Progo / Yogyakarta"),
    "Ahmad Yani": (-6.9744, 110.3744, "Bandara", "Kota Semarang"),
    "Morowali": (-2.6500, 121.9000, "Bandara", "Morowali, Sulawesi Tengah"),

    # Stasiun Kereta Api
    "Gambir": (-6.1767, 106.8306, "Stasiun KA", "Jakarta Pusat"),
    "Pasar Senen": (-6.1744, 106.8447, "Stasiun KA", "Jakarta Pusat"),
    "Halim": (-6.2447, 106.8856, "Stasiun KA", "Jakarta Timur (Whoosh)"),
    "Bandung": (-6.9128, 107.6025, "Stasiun KA", "Kota Bandung"),
    "Tegalluar": (-6.9667, 107.7167, "Stasiun KA", "Kab. Bandung (Whoosh)"),
    "Semarang Tawang": (-6.9644, 110.4281, "Stasiun KA", "Kota Semarang"),
    "Yogyakarta": (-7.7892, 110.3633, "Stasiun KA", "Kota Yogyakarta"),
    "Surabaya Gubeng": (-7.2653, 112.7525, "Stasiun KA", "Kota Surabaya"),
    "Surabaya Pasar Turi": (-7.2478, 112.7314, "Stasiun KA", "Kota Surabaya"),
    "Solo Balapan": (-7.5572, 110.8214, "Stasiun KA", "Kota Surakarta"),

    # Pelabuhan ASDP & Laut
    "Merak": (-5.9325, 105.9989, "Pelabuhan ASDP", "Cilegon, Banten"),
    "Bakauheni": (-5.8692, 105.7539, "Pelabuhan ASDP", "Lampung Selatan"),
    "Ketapang": (-8.1481, 114.3986, "Pelabuhan ASDP", "Banyuwangi, Jatim"),
    "Gilimanuk": (-8.1633, 114.4367, "Pelabuhan ASDP", "Jembrana, Bali"),
    "Tanjung Priok": (-6.1039, 106.8825, "Pelabuhan Laut", "Jakarta Utara"),
    "Tanjung Perak": (-7.2025, 112.7336, "Pelabuhan Laut", "Surabaya"),
    "Pulau Tidung": (-5.8033, 106.5233, "Pelabuhan ASDP", "Kepulauan Seribu"),

    # Terminal Bus
    "Pulo Gebang": (-6.2125, 106.9536, "Terminal Bus", "Jakarta Timur"),
    "Kampung Rambutan": (-6.3092, 106.8828, "Terminal Bus", "Jakarta Timur"),
    "Purabaya": (-7.3528, 112.7247, "Terminal Bus", "Sidoarjo / Surabaya"),
    "Tirtonadi": (-7.5511, 110.8197, "Terminal Bus", "Surakarta"),
    "Giwangan": (-7.8344, 110.3917, "Terminal Bus", "Yogyakarta"),
    "Daya": (-5.1200, 119.5050, "Terminal Bus", "Kota Makassar"),
    "Halte Jakarta Pusat": (-6.1800, 106.8300, "Terminal Bus", "Jakarta Pusat")
}
