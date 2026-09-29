"""
Komponen Styling & CSS untuk Dashboard Analitik Transportasi Nataru.
Menyediakan tata letak visual modern, kartu KPI, dan box chart.
"""

DASHBOARD_CSS = """
<style>
    .main-header {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        padding: 24px 30px;
        border-radius: 12px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .main-header h1 { color: #ffffff; font-size: 26px; font-weight: 700; margin: 0 0 6px 0; }
    .main-header p { color: #dcdde1; font-size: 14px; margin: 0; }
    .kpi-card {
        background: white;
        padding: 18px 20px;
        border-radius: 10px;
        border-left: 5px solid #20c997;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        margin-bottom: 15px;
    }
    .kpi-title { font-size: 13px; color: #6c757d; font-weight: 600; text-transform: uppercase; margin-bottom: 4px; }
    .kpi-value { font-size: 26px; color: #1e3c72; font-weight: 700; }
    .kpi-sub { font-size: 12px; color: #28a745; font-weight: 500; }
    .chart-box {
        background: #ffffff;
        border-radius: 10px;
        padding: 12px;
        border: 1px solid #edf2f7;
        margin-bottom: 20px;
    }
</style>
"""
