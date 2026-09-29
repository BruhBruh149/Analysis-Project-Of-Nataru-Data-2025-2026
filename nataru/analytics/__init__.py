"""
Subpaket Analitik Transportasi Nataru.
Menyediakan kalkulasi KPI, IPA Matrix, K-Means Persona Clustering, NLP & Topic Modeling,
Early Warning Risk Predictor, dan Analisis Geospasial.
"""

import pandas as pd
from typing import Dict, Any, Tuple

from .kpi_engine import compute_kpi_summary, get_top_routes, export_all_tables_to_csv, generate_terminal_report
from .ipa_matrix import compute_key_drivers_and_ipa
from .clustering import run_passenger_clustering, compute_elbow_and_silhouette
from .sentiment_nlp import (
    extract_word_frequency, analyze_sentiment_indonesian, extract_complaint_topics,
    extract_ngram_frequency, analyze_aspect_based_sentiment
)
from .ml_predictor import predict_dissatisfaction_risks, predict_single_scenario, get_trained_risk_model
from .geo_analytics import get_od_flow_data, get_hub_performance_geo, get_sankey_od_data

class NataruAnalytics:
    """Kelas antarmuka statis terpadu untuk kompatibilitas penuh dengan kode eksisting."""
    
    @staticmethod
    def compute_kpi_summary(df_kepuasan: pd.DataFrame) -> Dict[str, Any]:
        return compute_kpi_summary(df_kepuasan)

    @staticmethod
    def get_top_routes(df_perjalanan: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
        return get_top_routes(df_perjalanan, top_n)

    @staticmethod
    def extract_word_frequency(series_text: pd.Series, top_n: int = 25) -> pd.DataFrame:
        return extract_word_frequency(series_text, top_n)

    @staticmethod
    def extract_ngram_frequency(series_text: pd.Series, n: int = 2, top_n: int = 15) -> pd.DataFrame:
        return extract_ngram_frequency(series_text, n, top_n)

    @staticmethod
    def compute_key_drivers_and_ipa(db_manager) -> Tuple[pd.DataFrame, float, float]:
        return compute_key_drivers_and_ipa(db_manager)

    @staticmethod
    def generate_terminal_report(db_manager, export_file: bool = True) -> str:
        return generate_terminal_report(db_manager, export_file)

    @staticmethod
    def run_passenger_clustering(db_manager, n_clusters: int = 3) -> Tuple[pd.DataFrame, pd.DataFrame]:
        return run_passenger_clustering(db_manager, n_clusters)

    @staticmethod
    def compute_elbow_and_silhouette(db_manager, max_k: int = 5) -> pd.DataFrame:
        return compute_elbow_and_silhouette(db_manager, max_k)

    @staticmethod
    def analyze_sentiment_indonesian(series_text: pd.Series) -> pd.DataFrame:
        return analyze_sentiment_indonesian(series_text)

    @staticmethod
    def analyze_aspect_based_sentiment(series_text: pd.Series) -> pd.DataFrame:
        return analyze_aspect_based_sentiment(series_text)

    @staticmethod
    def extract_complaint_topics(series_text: pd.Series) -> pd.DataFrame:
        return extract_complaint_topics(series_text)

    @staticmethod
    def predict_dissatisfaction_risks(db_manager) -> Dict[str, Any]:
        return predict_dissatisfaction_risks(db_manager)

    @staticmethod
    def predict_single_scenario(input_features: Dict[str, Any], db_manager=None) -> Dict[str, Any]:
        return predict_single_scenario(input_features, db_manager)

    @staticmethod
    def get_od_flow_data(db_manager, top_n: int = 20) -> pd.DataFrame:
        return get_od_flow_data(db_manager, top_n)

    @staticmethod
    def get_sankey_od_data(db_manager, level: str = "provinsi", top_n: int = 15) -> Dict[str, Any]:
        return get_sankey_od_data(db_manager, level, top_n)

    @staticmethod
    def get_hub_performance_geo(db_manager) -> pd.DataFrame:
        return get_hub_performance_geo(db_manager)

    @staticmethod
    def export_all_tables_to_csv(db_manager, output_dir: str = None) -> str:
        return export_all_tables_to_csv(db_manager, output_dir)

    @staticmethod
    def export_visualizations(db_manager, output_dir: str = None) -> str:
        from ..visualization.chart_exporter import export_visualizations
        return export_visualizations(db_manager, output_dir)

__all__ = [
    "NataruAnalytics",
    "compute_kpi_summary",
    "get_top_routes",
    "export_all_tables_to_csv",
    "generate_terminal_report",
    "compute_key_drivers_and_ipa",
    "run_passenger_clustering",
    "compute_elbow_and_silhouette",
    "extract_word_frequency",
    "extract_ngram_frequency",
    "analyze_sentiment_indonesian",
    "analyze_aspect_based_sentiment",
    "extract_complaint_topics",
    "predict_dissatisfaction_risks",
    "predict_single_scenario",
    "get_trained_risk_model",
    "get_od_flow_data",
    "get_sankey_od_data",
    "get_hub_performance_geo"
]

