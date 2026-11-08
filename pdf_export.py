"""PDF export for the LangGraph AI Travel Planner.

Put this file in the project root next to frontend.py.
Install: python -m pip install reportlab

No external services are used to create the PDF.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


BLUE = colors.HexColor("#185fa8")
DARK = colors.HexColor("#14243b")
MUTED = colors.HexColor("#61758a")
PALE = colors.HexColor("#eaf2fa")


def _register_fonts() -> tuple[str, str]:
    """Use fonts already installed on the host; do not package font files."""
    pairs = [
        (Path('C:/Windows/Fonts/arial.ttf'), Path('C:/Windows/Fonts/arialbd.ttf')),
        (Path('C:/Windows/Fonts/calibri.ttf'), Path('C:/Windows/Fonts/calibrib.ttf')),
        (Path('C:/Windows/Fonts/segoeui.ttf'), Path('C:/Windows/Fonts/segoeuib.ttf')),
        (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
         Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')),
    ]
    for normal, bold in pairs:
        if normal.is_file() and bold.is_file():
            pdfmetrics.registerFont(TTFont('TravelBody', str(normal)))
            pdfmetrics.registerFont(TTFont('TravelBold', str(bold)))
            pdfmetrics.registerFontFamily(
                'TravelBody', normal='TravelBody', bold='TravelBold',
                italic='TravelBody', boldItalic='TravelBold',
            )
            return 'TravelBody', 'TravelBold'
    # Fallback is adequate for simple Latin text but may omit the rupee symbol.
    return 'Helvetica', 'Helvetica-Bold'


def _clean(value: object) -> str:
    text = str(value) if value is not None else ''
    # Most color emoji cannot be embedded reliably in ReportLab's TrueType PDF output.
    text = re.sub(r'[\U0001F000-\U0001FAFF\U00002600-\U000027BF]', '', text)
    text = text.replace('\ufe0f', '').replace('\ufe0e', '').replace('\u200d', '')
    return ''.join(c for c in text if c in '\n\t' or ord(c) >= 32)


def _inline_markup(value: str) -> str:
    """Convert common Markdown inline syntax to ReportLab-supported markup.

    Escape original HTML first so API/LLM output cannot inject PDF markup.
    """
    safe = escape(_clean(value), quote=False)

    # Replace Markdown links with readable label + URL. Neither is executable markup.
    safe = re.sub(
        r'\[([^\]]+)\]\((https?://[^\s)]+)\)',
        lambda match: f'{match.group(1)} ({match.group(2)})',
        safe,
    )
    safe = re.sub(r'\*\*([^*\n]+)\*\*', r'<b>\1</b>', safe)
    safe = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<i>\1</i>', safe)
    safe = re.sub(r'`([^`\n]+)`', r'<font color="#185fa8">\1</font>', safe)
    return safe


def _styles():
    normal_font, bold_font = _register_fonts()
    base = getSampleStyleSheet()
    return {
        'Title': ParagraphStyle(
            'TravelTitle', parent=base['Title'], fontName=bold_font,
            fontSize=22, leading=28, alignment=TA_CENTER, textColor=DARK,
            spaceAfter=10,
        ),
        'Subtitle': ParagraphStyle(
            'TravelSubtitle', parent=base['Normal'], fontName=normal_font,
            fontSize=9, leading=14, alignment=TA_CENTER, textColor=MUTED,
            spaceAfter=14,
        ),
        'Heading': ParagraphStyle(
            'TravelHeading', parent=base['Heading2'], fontName=bold_font,
            fontSize=13, leading=19, textColor=BLUE, spaceBefore=17,
            spaceAfter=8, keepWithNext=True,
        ),
        'Subheading': ParagraphStyle(
            'TravelSubheading', parent=base['Heading3'], fontName=bold_font,
            fontSize=10.5, leading=16, textColor=DARK, spaceBefore=11,
            spaceAfter=5, keepWithNext=True,
        ),
        'Body': ParagraphStyle(
            'TravelBodyStyle', parent=base['BodyText'], fontName=normal_font,
            fontSize=9, leading=14.4, textColor=DARK, spaceAfter=6,
            allowWidows=0, allowOrphans=0,
        ),
        'Bullet': ParagraphStyle(
            'TravelBullet', parent=base['BodyText'], fontName=normal_font,
            fontSize=9, leading=14.4, textColor=DARK, leftIndent=16,
            firstLineIndent=-12, spaceAfter=4,
        ),
        'Meta': ParagraphStyle(
            'TravelMeta', parent=base['BodyText'], fontName=normal_font,
            fontSize=9, leading=14.5, textColor=DARK, spaceAfter=6,
        ),
        'Table': ParagraphStyle(
            'TravelTableCell', parent=base['Normal'], fontName=normal_font,
            fontSize=7.5, leading=10.5, textColor=DARK,
        ),
        'TableBold': ParagraphStyle(
            'TravelTableHeader', parent=base['Normal'], fontName=bold_font,
            fontSize=7.5, leading=10.5, textColor=DARK,
        ),
    }


def _table_from_lines(lines: list[str], styles: dict, content_width: float):
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if all(re.fullmatch(r':?-{3,}:?', c or '') for c in cells):
            continue
        rows.append(cells)

    if not rows or len(rows) > 100 or len(rows[0]) > 6:
        return None
    count = len(rows[0])
    if not all(len(row) == count for row in rows):
        return None
    rendered = [
        [Paragraph(_inline_markup(cell), styles['TableBold' if i == 0 else 'Table'])
         for cell in row]
        for i, row in enumerate(rows)
    ]
    table = Table(rendered, colWidths=[content_width / count] * count, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PALE),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#d1dfed')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return table


def _add_markdown(story: list, markdown_text: object, styles: dict, content_width: float) -> None:
    """Render headings, paragraphs, lists and simple tables from agent Markdown."""
    source = _clean(markdown_text).replace('\r\n', '\n').strip()
    if not source:
        story.append(Paragraph('No information returned.', styles['Body']))
        return

    lines = source.split('\n')
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            story.append(Paragraph('<br/>'.join(_inline_markup(x.strip()) for x in buffer), styles['Body']))
            buffer.clear()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            flush()
            i += 1
            continue
        if line.startswith('|') and line.endswith('|'):
            flush()
            start = i
            while i < len(lines) and lines[i].strip().startswith('|') and lines[i].strip().endswith('|'):
                i += 1
            table = _table_from_lines(lines[start:i], styles, content_width)
            if table:
                story.append(table)
                story.append(Spacer(1, 8))
            else:
                for text in lines[start:i]:
                    story.append(Paragraph(_inline_markup(text), styles['Body']))
            continue
        if re.fullmatch(r'[-*_]{3,}', line):
            flush()
            story.append(Spacer(1, 5))
            story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#d1dfed')))
            story.append(Spacer(1, 6))
            i += 1
            continue
        heading = re.match(r'^(#{1,6})\s+(.*)$', line)
        if heading:
            flush()
            story.append(Paragraph(_inline_markup(heading.group(2)),
                                   styles['Heading' if len(heading.group(1)) <= 2 else 'Subheading']))
            i += 1
            continue
        bullet = re.match(r'^\s*[-*+]\s+(.+)$', lines[i])
        number = re.match(r'^\s*(\d+[.)])\s+(.+)$', lines[i])
        if bullet or number:
            flush()
            prefix = '&#8226;' if bullet else escape(number.group(1))
            content = bullet.group(1) if bullet else number.group(2)
            story.append(Paragraph(f'{prefix}  {_inline_markup(content)}', styles['Bullet']))
            i += 1
            continue
        if line.startswith('>'):
            flush()
            story.append(Paragraph(_inline_markup(line.lstrip('> ').strip()), styles['Bullet']))
            i += 1
            continue
        buffer.append(line)
        i += 1
    flush()


def _page_footer(canvas, doc) -> None:
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(colors.HexColor('#d1dfed'))
    canvas.line(16 * mm, 16 * mm, width - 16 * mm, 16 * mm)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(16 * mm, 11 * mm, 'AI Travel Planner - Generated trip plan')
    canvas.drawRightString(width - 16 * mm, 11 * mm, f'Page {doc.page}')
    canvas.restoreState()


def build_travel_pdf(user_query: str, thread_id: str,
                     collected: dict, generated_at: datetime | None = None) -> bytes:
    """Generate an A4 travel-plan PDF and return its bytes for Streamlit download."""
    moment = generated_at or datetime.now()
    buffer = BytesIO()
    margin = 17 * mm
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=margin, leftMargin=margin,
        topMargin=19 * mm, bottomMargin=23 * mm,
        title='AI Travel Planner - Travel Plan', author='AI Travel Planner',
    )
    styles = _styles()
    story = [
        Paragraph('AI TRAVEL PLAN', styles['Title']),
        Paragraph('Human-reviewed itinerary - user-supplied price quotes are not independently verified.',
                  styles['Subtitle']),
        HRFlowable(width='100%', thickness=1.3, color=BLUE),
        Spacer(1, 13),
        Paragraph(f'<b>Created:</b> {_inline_markup(moment.strftime("%d %B %Y, %I:%M %p"))}', styles['Meta']),
        Paragraph(f'<b>Session ID:</b> {_inline_markup(thread_id)}', styles['Meta']),
        Paragraph(f'<b>Travel request:</b> {_inline_markup(user_query)}', styles['Meta']),
    ]
    # Export ONLY the human-approved, sanitized final text; raw tool output can
    # contain unverified prices, so it must not be copied into the PDF.
    sections = [ ('Human-approved travel plan and deterministic cost assessment', 'final_response') ]
    for label, key in sections:
        story.append(Paragraph(label, styles['Heading']))
        _add_markdown(story, collected.get(key) or 'Not available.', styles, doc.width)
    story.extend([
        Spacer(1, 12),
        HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#d1dfed')),
        Spacer(1, 7),
        Paragraph(f'<b>LLM calls (reported):</b> {_inline_markup(collected.get("llm_calls", 0))}', styles['Meta']),
    ])
    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()
