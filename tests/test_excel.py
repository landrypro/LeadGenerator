from datetime import datetime, timezone
from io import BytesIO

from openpyxl import load_workbook

from backend.app.excel import build_workbook
from backend.app.models import ExportRequest, Lead


def test_excel_export_contains_leads_and_search_summary():
    lead = Lead(
        name="Plomberie Boréale", address="Québec", place_id="abc", zone_index=1,
        zone_latitude=46.8, zone_longitude=-71.2, collected_at=datetime.now(timezone.utc),
    )

    content = build_workbook(ExportRequest(leads=[lead], search={"query": "plombier"}))
    workbook = load_workbook(BytesIO(content))

    assert workbook.sheetnames == ["Leads", "Recherche"]
    assert workbook["Leads"]["A2"].value == "Plomberie Boréale"
    assert workbook["Leads"]["I2"].value == "abc"
    assert workbook["Recherche"]["B2"].value == "plombier"

