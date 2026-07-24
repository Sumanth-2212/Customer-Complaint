"""PDF generation for saved complaints (ReportLab)."""
from __future__ import annotations

import io
import os
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


IMAGE_MIME_PREFIXES = ("image/",)


def _row_or_dash(value):
    if value is None or value == "":
        return "—"
    return str(value)


def build_complaint_pdf(complaint: dict, evidence: list[dict] | None = None) -> bytes:
    evidence = evidence or []
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "SubStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=16,
    )
    section_style = ParagraphStyle(
        "SectionStyle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.HexColor("#334155"),
        spaceBefore=14,
        spaceAfter=6,
    )
    para_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#0f172a"),
    )

    story = []
    story.append(Paragraph("Customer Complaint Record", title_style))
    story.append(
        Paragraph(
            f"API &amp; FDF Quality Assurance Module · "
            f"Complaint #{complaint.get('id', '—')} · "
            f"Status: {complaint.get('status', 'Pending Triage')}",
            sub_style,
        )
    )

    def kv_table(rows):
        table = Table(rows, colWidths=[2.0 * inch, 4.6 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#64748b")),
                    ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#0f172a")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    (
                        "LINEBELOW",
                        (0, 0),
                        (-1, -2),
                        0.25,
                        colors.HexColor("#e2e8f0"),
                    ),
                ]
            )
        )
        return table

    story.append(Paragraph("1. Origin &amp; Customer Details", section_style))
    story.append(
        kv_table(
            [
                ["Complaint Source", _row_or_dash(complaint.get("complaint_source"))],
                ["Customer Name", _row_or_dash(complaint.get("customer_name"))],
            ]
        )
    )

    story.append(Paragraph("2. Product &amp; Batch Identification", section_style))
    story.append(
        kv_table(
            [
                ["Product Name", _row_or_dash(complaint.get("product_name"))],
                [
                    "Product Strength/Grade",
                    _row_or_dash(complaint.get("product_strength")),
                ],
                ["Batch / Lot Number", _row_or_dash(complaint.get("batch_number"))],
                [
                    "Manufacturing Date",
                    _row_or_dash(complaint.get("manufacturing_date")),
                ],
                ["Expiry Date", _row_or_dash(complaint.get("expiry_date"))],
                [
                    "Quantity Affected",
                    _row_or_dash(complaint.get("quantity_affected")),
                ],
            ]
        )
    )

    story.append(Paragraph("3. Complaint Details", section_style))
    story.append(
        kv_table(
            [
                ["Complaint Type", _row_or_dash(complaint.get("complaint_type"))],
                ["Complaint Date", _row_or_dash(complaint.get("complaint_date"))],
            ]
        )
    )
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Detailed Description</b>", para_style))
    story.append(Spacer(1, 4))
    story.append(
        Paragraph(
            _row_or_dash(complaint.get("complaint_description")).replace("\n", "<br/>"),
            para_style,
        )
    )

    story.append(Paragraph("4. Initial Assessment &amp; Priority", section_style))
    story.append(
        kv_table(
            [
                ["Initial Severity", _row_or_dash(complaint.get("initial_severity"))],
                ["Priority", _row_or_dash(complaint.get("priority"))],
            ]
        )
    )

    story.append(Spacer(1, 22))
    story.append(Paragraph("Signatures", section_style))
    sig_table = Table(
        [
            ["QA Reviewer", "", "Date"],
            ["", "", ""],
            ["QA Manager", "", "Date"],
            ["", "", ""],
        ],
        colWidths=[2.4 * inch, 0.4 * inch, 3.8 * inch],
    )
    sig_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#64748b")),
                ("LINEBELOW", (0, 1), (0, 1), 0.75, colors.HexColor("#0f172a")),
                ("LINEBELOW", (2, 1), (2, 1), 0.75, colors.HexColor("#0f172a")),
                ("LINEBELOW", (0, 3), (0, 3), 0.75, colors.HexColor("#0f172a")),
                ("LINEBELOW", (2, 3), (2, 3), 0.75, colors.HexColor("#0f172a")),
                ("TOPPADDING", (0, 1), (-1, 1), 22),
                ("TOPPADDING", (0, 3), (-1, 3), 22),
            ]
        )
    )
    story.append(sig_table)

    story.append(Spacer(1, 24))
    footer = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        textColor=colors.HexColor("#94a3b8"),
    )
    story.append(
        Paragraph(
            f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
            "Confidential — Pharmaceutical Quality Assurance",
            footer,
        )
    )

    # ---- Evidence appendix ----
    if evidence:
        story.append(PageBreak())
        story.append(Paragraph("Evidence Attachments", section_style))
        story.append(
            Paragraph(
                f"{len(evidence)} file(s) attached to this complaint.",
                para_style,
            )
        )
        story.append(Spacer(1, 8))
        for ev in evidence:
            label_style = ParagraphStyle(
                "EvLabel",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=10,
                textColor=colors.HexColor("#0f172a"),
                spaceBefore=10,
                spaceAfter=2,
            )
            meta_style = ParagraphStyle(
                "EvMeta",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=8,
                textColor=colors.HexColor("#64748b"),
                spaceAfter=6,
            )
            story.append(Paragraph(ev.get("filename", "attachment"), label_style))
            story.append(
                Paragraph(
                    f"{ev.get('mime_type', '')} · "
                    f"{(ev.get('size_bytes') or 0) // 1024} KB",
                    meta_style,
                )
            )
            path = ev.get("storage_path")
            mime = (ev.get("mime_type") or "").lower()
            if (
                path
                and os.path.exists(path)
                and any(mime.startswith(p) for p in IMAGE_MIME_PREFIXES)
            ):
                try:
                    img = Image(path)
                    max_w = 6.5 * inch
                    max_h = 4.0 * inch
                    w, h = img.wrap(0, 0)
                    if w > max_w:
                        h = h * (max_w / w)
                        w = max_w
                    if h > max_h:
                        w = w * (max_h / h)
                        h = max_h
                    img._restrictSize(max_w, max_h)
                    img.drawWidth = w
                    img.drawHeight = h
                    story.append(img)
                except Exception:
                    story.append(
                        Paragraph(
                            "<i>(Unable to render preview — file attached to record.)</i>",
                            para_style,
                        )
                    )
            else:
                story.append(
                    Paragraph(
                        "<i>(Non-image attachment — see original file in the system.)</i>",
                        para_style,
                    )
                )

    doc.build(story)
    return buf.getvalue()
