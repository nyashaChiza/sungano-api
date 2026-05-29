from datetime import datetime
from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.round import Round, RoundMember
from app.models.user import User
from app.services import cloudinary_service
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
    Image,
)
from io import BytesIO
from typing import Dict, Any, List


async def generate_contract_json(
    round_id: UUID,
    round_obj: Round,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Generate contract JSON for a round.
    Includes all members, terms, and legal disclaimers.
    """
    # Load members with users
    members_result = await db.execute(
        select(RoundMember)
        .where(RoundMember.round_id == round_id)
        .options(selectinload(RoundMember.user))
    )
    members = members_result.scalars().all()

    member_list = [
        {
            "id": str(member.user_id),
            "name": member.user.full_name,
            "email": member.user.email,
            "phone": member.user.phone,
            "position": member.payout_position,
            "signed_at": member.contract_signed_at.isoformat()
            if member.contract_signed_at
            else None,
        }
        for member in members
    ]

    contract = {
        "version": 1,
        "generated_at": datetime.utcnow().isoformat(),
        "round": {
            "id": str(round_id),
            "name": round_obj.name,
            "creator_id": str(round_obj.created_by),
            "contribution_amount": str(round_obj.contribution_amount),
            "currency": round_obj.currency,
            "cycle_frequency": round_obj.cycle_frequency,
            "total_cycles": round_obj.total_cycles,
            "start_date": round_obj.start_date.isoformat(),
            "grace_period_days": round_obj.grace_period_days,
            "late_penalty": str(round_obj.late_penalty_amount),
        },
        "members": member_list,
        "terms": {
            "title": "SUNGANO ROUND AGREEMENT",
            "summary": "This agreement governs the rights and obligations of all members participating in a Sungano savings round. Each member commits to contribute the agreed amount on their due date. Payments are verified and confirmed before distribution.",
            "detailed_terms": [
                {
                    "section": "1. Contributions",
                    "content": f"Each member agrees to contribute {round_obj.currency} {round_obj.contribution_amount} {round_obj.cycle_frequency}.",
                },
                {
                    "section": "2. Payment Schedule",
                    "content": f"Payments are due every {round_obj.cycle_frequency}. A grace period of {round_obj.grace_period_days} days is granted.",
                },
                {
                    "section": "3. Payout Order",
                    "content": "Members will receive their share in the order specified by the round creator.",
                },
                {
                    "section": "4. Default",
                    "content": "Failure to submit payment within the grace period constitutes a default. Defaults are recorded and affect the member's trust score.",
                },
                {
                    "section": "5. Disputes",
                    "content": "Payment disputes must be raised within 24 hours of confirmation. Sungano mediates disputes fairly.",
                },
            ],
            "fraud_declaration": "By submitting proof of payment, the member declares under their own legal responsibility that the proof is authentic and accurate. Submission of false proof constitutes fraud under applicable law and may be reported to authorities.",
        },
    }

    return contract


async def generate_contract_pdf(
    contract_json: Dict[str, Any],
    round_id: UUID,
) -> bytes:
    """
    Generate a PDF from contract JSON.
    Returns PDF bytes ready for upload.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5 * inch)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#1a1a1a"),
        spaceAfter=12,
        alignment=1,  # CENTER
    )

    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#333333"),
        spaceAfter=10,
        spaceBefore=10,
    )

    normal_style = ParagraphStyle(
        "CustomNormal",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#666666"),
        spaceAfter=8,
    )

    body = []

    # Header with logo placeholder
    body.append(Spacer(1, 0.3 * inch))
    body.append(Paragraph("SUNGANO", title_style))
    body.append(Paragraph("Savings Round Agreement", heading_style))
    body.append(Spacer(1, 0.2 * inch))

    # Round details
    round_data = contract_json.get("round", {})
    round_details = [
        ["Round Name:", round_data.get("name", "N/A")],
        ["Contribution Amount:", f"{round_data.get('currency', 'USD')} {round_data.get('contribution_amount', 'N/A')}"],
        ["Frequency:", round_data.get("cycle_frequency", "N/A")],
        ["Total Cycles:", str(round_data.get("total_cycles", "N/A"))],
        ["Start Date:", round_data.get("start_date", "N/A")],
        ["Grace Period:", f"{round_data.get('grace_period_days', 'N/A')} days"],
    ]

    details_table = Table(round_details, colWidths=[2 * inch, 4 * inch])
    details_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 1, colors.grey),
            ]
        )
    )

    body.append(details_table)
    body.append(Spacer(1, 0.2 * inch))

    # Plain language summary
    body.append(Paragraph("Summary", heading_style))
    summary_text = contract_json.get("terms", {}).get(
        "summary",
        "This agreement governs the rights and obligations of all members.",
    )
    body.append(Paragraph(summary_text, normal_style))
    body.append(Spacer(1, 0.2 * inch))

    # Members list
    body.append(Paragraph("Members", heading_style))
    members = contract_json.get("members", [])
    if members:
        members_data = [["Name", "Position", "Email"]]
        for member in members:
            members_data.append(
                [
                    member.get("name", "N/A"),
                    str(member.get("position", "TBD")),
                    member.get("email", "N/A"),
                ]
            )

        members_table = Table(members_data, colWidths=[2.5 * inch, 1.5 * inch, 2.5 * inch])
        members_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#007bff")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                ]
            )
        )
        body.append(members_table)
    body.append(Spacer(1, 0.2 * inch))

    # Detailed terms
    body.append(Paragraph("Terms and Conditions", heading_style))
    terms = contract_json.get("terms", {}).get("detailed_terms", [])
    for term in terms:
        body.append(
            Paragraph(
                f"<b>{term.get('section', '')}</b>: {term.get('content', '')}",
                normal_style,
            )
        )

    body.append(Spacer(1, 0.2 * inch))

    # Fraud declaration - CRITICAL, always present
    body.append(Paragraph("Legal Declaration", heading_style))
    fraud_text = contract_json.get("terms", {}).get("fraud_declaration", "")
    body.append(Paragraph(fraud_text, normal_style))

    body.append(Spacer(1, 0.3 * inch))

    # Signature blocks
    body.append(Paragraph("Signatures", heading_style))
    sig_text = "By signing below, all members acknowledge that they have read and agree to the terms of this agreement."
    body.append(Paragraph(sig_text, normal_style))
    body.append(Spacer(1, 0.15 * inch))

    sig_lines = []
    for i, member in enumerate(members[:3]):  # Show first 3 on first page
        sig_lines.append([f"{member.get('name', '')}", "___________________", ""])

    if sig_lines:
        sig_table = Table(sig_lines, colWidths=[2 * inch, 2 * inch, 2 * inch])
        sig_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
                ]
            )
        )
        body.append(sig_table)

    body.append(Spacer(1, 0.1 * inch))
    footer = f"Round ID: {round_id} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
    body.append(Paragraph(footer, ParagraphStyle("footer", parent=styles["Normal"], fontSize=8, textColor=colors.grey)))

    # Build PDF
    doc.build(body)
    buffer.seek(0)
    return buffer.read()


async def generate_and_upload_contract(
    round_id: UUID,
    round_obj: Round,
    db: AsyncSession,
) -> str:
    """
    Generate contract JSON and PDF, upload PDF to Cloudinary,
    and return the public_id.
    """
    # Generate JSON
    contract_json = await generate_contract_json(round_id, round_obj, db)

    # Generate PDF
    pdf_bytes = await generate_contract_pdf(contract_json, round_id)

    # Upload to Cloudinary
    public_id = await cloudinary_service.upload_contract_pdf(round_id, pdf_bytes)

    return public_id
