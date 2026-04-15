from __future__ import annotations

import io
import os
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.schemas import TranscriptSchema

FONT_NAME = "Helvetica"
FONT_NAME_BOLD = "Helvetica-Bold"


def _register_fonts() -> None:
    global FONT_NAME, FONT_NAME_BOLD
    if os.path.exists("msyh.ttc"):
        pdfmetrics.registerFont(TTFont("MicrosoftYaHei", "msyh.ttc"))
        FONT_NAME = "MicrosoftYaHei"
    if os.path.exists("msyhbd.ttc"):
        pdfmetrics.registerFont(TTFont("MicrosoftYaHei-Bold", "msyhbd.ttc"))
        FONT_NAME_BOLD = "MicrosoftYaHei-Bold"
    elif FONT_NAME == "MicrosoftYaHei":
        FONT_NAME_BOLD = FONT_NAME


def _safe_text(value) -> str:
    return escape(str(value)) if value not in (None, "") else "-"


def _footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont(FONT_NAME, 8)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawString(18 * mm, 12 * mm, "AI-assisted transcript output. Verify against source records before official use.")
    canvas.drawRightString(190 * mm, 12 * mm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def generate_transcript_pdf(transcript: TranscriptSchema) -> io.BytesIO:
    _register_fonts()
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TranscriptTitle",
        parent=styles["Title"],
        fontName=FONT_NAME_BOLD,
        fontSize=18,
        leading=24,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a"),
    )
    subtitle_style = ParagraphStyle(
        "TranscriptSubtitle",
        parent=styles["BodyText"],
        fontName=FONT_NAME,
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
    )
    section_style = ParagraphStyle(
        "TranscriptSection",
        parent=styles["Heading3"],
        fontName=FONT_NAME_BOLD,
        fontSize=11,
        leading=14,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#111827"),
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "TranscriptBody",
        parent=styles["BodyText"],
        fontName=FONT_NAME,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#111827"),
    )
    label_style = ParagraphStyle(
        "TranscriptLabel",
        parent=body_style,
        fontName=FONT_NAME_BOLD,
    )

    story = [
        Paragraph("Academic Transcript", title_style),
        Paragraph(
            f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')} | Review required before official release",
            subtitle_style,
        ),
        Spacer(1, 8),
        Paragraph("Student Information", section_style),
    ]

    student_rows = [
        [Paragraph("Name", label_style), Paragraph(_safe_text(transcript.student_info.name), body_style)],
        [Paragraph("Student ID", label_style), Paragraph(_safe_text(transcript.student_info.student_id), body_style)],
        [Paragraph("Major", label_style), Paragraph(_safe_text(transcript.student_info.major), body_style)],
        [Paragraph("Institution", label_style), Paragraph(_safe_text(transcript.student_info.institution), body_style)],
    ]
    student_table = Table(student_rows, colWidths=[32 * mm, 142 * mm], hAlign="LEFT")
    student_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([student_table, Spacer(1, 10), Paragraph("Course Records", section_style)])

    course_rows = [
        [
            Paragraph("<b>Code</b>", body_style),
            Paragraph("<b>Course Title</b>", body_style),
            Paragraph("<b>Credits</b>", body_style),
            Paragraph("<b>Grade</b>", body_style),
            Paragraph("<b>Semester</b>", body_style),
        ]
    ]
    for course in transcript.courses:
        course_rows.append(
            [
                Paragraph(_safe_text(course.code), body_style),
                Paragraph(_safe_text(course.title), body_style),
                Paragraph(_safe_text(course.credits), body_style),
                Paragraph(_safe_text(course.grade), body_style),
                Paragraph(_safe_text(course.semester), body_style),
            ]
        )

    course_table = Table(
        course_rows,
        colWidths=[24 * mm, 72 * mm, 18 * mm, 18 * mm, 32 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    course_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("FONTNAME", (0, 0), (-1, 0), FONT_NAME_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("LEADING", (0, 0), (-1, -1), 11),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([course_table, Spacer(1, 10), Paragraph("Summary", section_style)])

    summary_table = Table(
        [
            ["Calculated GPA", _safe_text(transcript.gpa_summary.calculated_gpa)],
            ["Counted Credits", _safe_text(transcript.gpa_summary.total_credits)],
            ["Courses Counted", _safe_text(transcript.gpa_summary.counted_courses)],
            ["Courses Skipped", _safe_text(transcript.gpa_summary.skipped_courses)],
            ["Extraction Method", _safe_text(transcript.validation_summary.extraction_method)],
            ["OCR Used", _safe_text(transcript.validation_summary.ocr_used)],
        ],
        colWidths=[45 * mm, 40 * mm],
        hAlign="LEFT",
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                ("FONTNAME", (0, 0), (0, -1), FONT_NAME_BOLD),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(summary_table)

    if transcript.validation_summary.warnings:
        story.extend([Spacer(1, 10), Paragraph("Review Notes", section_style)])
        for warning in transcript.validation_summary.warnings:
            story.append(Paragraph(f"- {_safe_text(warning)}", body_style))

    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buffer.seek(0)
    return buffer
