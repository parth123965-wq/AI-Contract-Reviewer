from datetime import datetime, timezone
import json
from typing import Literal
from fastapi import HTTPException, status
from app.models.contract import Contract


class ReportExportService:
    """Generates structured executive contract review reports in HTML, Markdown, or JSON formats."""

    def generate_html_report(self, contract: Contract) -> str:
        latest = contract.analyses[-1] if contract.analyses else None
        summary = latest.summary if latest and latest.summary else "No summary available for this contract."
        risk_score = latest.risk_score if latest and latest.risk_score is not None else 0
        risk_level = (latest.risk_level.value if hasattr(latest.risk_level, "value") else str(latest.risk_level or "UNKNOWN")).upper()
        
        # Color coding
        if risk_level == "HIGH":
            badge_color = "#dc2626"
            badge_bg = "#fee2e2"
        elif risk_level == "MEDIUM":
            badge_color = "#d97706"
            badge_bg = "#fef3c7"
        else:
            badge_color = "#16a34a"
            badge_bg = "#dcfce7"

        # Recommendations list
        recommendations_html = ""
        if latest and latest.recommendations:
            lines = [line.strip() for line in latest.recommendations.split("\n") if line.strip()]
            for item in lines:
                recommendations_html += f"<li>{item}</li>\n"
        if not recommendations_html:
            recommendations_html = "<li>No specific action items identified. Standard terms apply.</li>"

        # High risk clauses
        clauses_html = ""
        if latest and latest.high_risk_clause:
            if isinstance(latest.high_risk_clause, list):
                for c in latest.high_risk_clause:
                    clauses_html += f"<div class='clause-box'><strong>Flagged Clause:</strong><p>{c}</p></div>"
            elif isinstance(latest.high_risk_clause, dict):
                for k, v in latest.high_risk_clause.items():
                    clauses_html += f"<div class='clause-box'><strong>{k}:</strong><p>{v}</p></div>"
            else:
                clauses_html += f"<div class='clause-box'><p>{latest.high_risk_clause}</p></div>"

        created_date = contract.created_at.strftime("%B %d, %Y") if contract.created_at else "N/A"
        processed_date = contract.processed_at.strftime("%B %d, %Y %H:%M UTC") if contract.processed_at else "N/A"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Contract Review Audit Report - {contract.original_filename}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #1e293b;
            background-color: #f8fafc;
            line-height: 1.6;
            margin: 0;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 860px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            padding: 48px;
        }}
        .header {{
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 24px;
            margin-bottom: 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .title h1 {{
            margin: 0 0 6px 0;
            font-size: 24px;
            color: #0f172a;
        }}
        .title p {{
            margin: 0;
            color: #64748b;
            font-size: 14px;
        }}
        .risk-badge {{
            padding: 8px 16px;
            border-radius: 9999px;
            font-weight: 700;
            font-size: 14px;
            background-color: {badge_bg};
            color: {badge_color};
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin-bottom: 32px;
        }}
        .metric-card {{
            background: #f1f5f9;
            padding: 16px;
            border-radius: 8px;
            text-align: center;
        }}
        .metric-card .num {{
            font-size: 28px;
            font-weight: 800;
            color: #0f172a;
        }}
        .metric-card .label {{
            font-size: 12px;
            color: #64748b;
            text-transform: uppercase;
        }}
        .section {{
            margin-bottom: 32px;
        }}
        .section h2 {{
            font-size: 18px;
            color: #0f172a;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 8px;
            margin-bottom: 16px;
        }}
        .clause-box {{
            background: #fff7ed;
            border-left: 4px solid #f97316;
            padding: 12px 16px;
            margin-bottom: 12px;
            border-radius: 4px;
        }}
        .clause-box p {{
            margin: 6px 0 0 0;
            font-size: 14px;
            color: #334155;
        }}
        ul {{
            padding-left: 20px;
        }}
        li {{
            margin-bottom: 8px;
        }}
        .footer {{
            border-top: 1px solid #e2e8f0;
            padding-top: 20px;
            font-size: 12px;
            color: #94a3b8;
            text-align: center;
        }}
        @media print {{
            body {{ background: #fff; padding: 0; }}
            .container {{ box-shadow: none; border-radius: 0; padding: 20px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title">
                <h1>Contract Review Audit</h1>
                <p>Document: <strong>{contract.original_filename}</strong></p>
            </div>
            <div class="risk-badge">
                Risk Tier: {risk_level}
            </div>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="num" style="color: {badge_color};">{risk_score}/100</div>
                <div class="label">Overall Risk Score</div>
            </div>
            <div class="metric-card">
                <div class="num">{created_date}</div>
                <div class="label">Uploaded On</div>
            </div>
            <div class="metric-card">
                <div class="num">v{latest.analysis_version if latest else 1}</div>
                <div class="label">Analysis Version</div>
            </div>
        </div>

        <div class="section">
            <h2>Executive Summary</h2>
            <p>{summary}</p>
        </div>

        {f'<div class="section"><h2>Flagged High-Risk Terms</h2>{clauses_html}</div>' if clauses_html else ''}

        <div class="section">
            <h2>Key Action Items & Recommendations</h2>
            <ul>
                {recommendations_html}
            </ul>
        </div>

        <div class="footer">
            Generated by AI Contract Reviewer Platform &bull; {processed_date} &bull; Confidential
        </div>
    </div>
</body>
</html>"""

    def generate_markdown_report(self, contract: Contract) -> str:
        latest = contract.analyses[-1] if contract.analyses else None
        summary = latest.summary if latest and latest.summary else "No summary available."
        risk_score = latest.risk_score if latest and latest.risk_score is not None else 0
        risk_level = (latest.risk_level.value if hasattr(latest.risk_level, "value") else str(latest.risk_level or "UNKNOWN")).upper()
        
        md = f"# Contract Review Audit Report: {contract.original_filename}\n\n"
        md += f"- **Risk Score**: {risk_score}/100 ({risk_level})\n"
        md += f"- **Document ID**: {contract.id}\n"
        md += f"- **File Size**: {contract.file_size or 0} bytes\n"
        md += f"- **Processed At**: {contract.processed_at or 'N/A'}\n\n"
        md += f"## Executive Summary\n\n{summary}\n\n"
        
        if latest and latest.recommendations:
            md += "## Key Recommendations\n\n"
            for line in latest.recommendations.split("\n"):
                if line.strip():
                    md += f"- {line.strip()}\n"
            md += "\n"

        if latest and latest.high_risk_clause:
            md += "## Flagged High-Risk Clauses\n\n"
            if isinstance(latest.high_risk_clause, list):
                for item in latest.high_risk_clause:
                    md += f"> {item}\n\n"
            else:
                md += f"> {latest.high_risk_clause}\n\n"

        md += "---\n*Generated by AI Contract Reviewer Platform*\n"
        return md

    def generate_json_report(self, contract: Contract) -> dict:
        latest = contract.analyses[-1] if contract.analyses else None
        return {
            "contract_id": contract.id,
            "filename": contract.original_filename,
            "status": contract.status.value if hasattr(contract.status, "value") else str(contract.status),
            "created_at": contract.created_at.isoformat() if contract.created_at else None,
            "processed_at": contract.processed_at.isoformat() if contract.processed_at else None,
            "latest_analysis": {
                "version": latest.analysis_version if latest else 1,
                "summary": latest.summary if latest else None,
                "risk_score": latest.risk_score if latest else None,
                "risk_level": latest.risk_level.value if (latest and hasattr(latest.risk_level, "value")) else None,
                "recommendations": latest.recommendations.split("\n") if (latest and latest.recommendations) else [],
                "high_risk_clause": latest.high_risk_clause if latest else None,
                "confidence_score": latest.confidence_score if latest else None,
                "processing_time_ms": latest.processing_time_ms if latest else None,
            }
        }


export_service = ReportExportService()
