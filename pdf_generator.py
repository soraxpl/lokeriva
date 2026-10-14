import io
import html
import re
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def safe_xml(text):
    """
    Sanitasi ketat untuk ReportLab XML Paragraph:
    Mencegah ExpatError / PDF Injection / formatting breakout.
    """
    if not text:
        return "-"
    # Hapus karakter kontrol
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(text))
    # Escape karakter XML: &, <, >, ", '
    return html.escape(cleaned, quote=True)


def safe_url(link):
    """Memastikan URL hanya HTTP/HTTPS yang valid dan XML-escaped."""
    if not link or not isinstance(link, str):
        return None
    link = link.strip()
    if link.startswith("https://") or link.startswith("http://"):
        cleaned = re.sub(r"[\r\n\t]", "", link)
        return html.escape(cleaned, quote=True)
    return None


def generate_jobs_pdf(jobs, query="", source_filter="", location_filter=""):
    """
    Menghasilkan dokumen PDF terstruktur dengan hyperlink aktif yang aman 100%.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=28,
        leftMargin=28,
        topMargin=28,
        bottomMargin=28
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    style_title = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1e3a8a')
    )
    style_subtitle = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor('#64748b')
    )
    style_header_cell = ParagraphStyle(
        'HCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#ffffff')
    )
    style_cell = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1e293b')
    )
    style_link = ParagraphStyle(
        'LinkCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#2563eb')
    )

    story = []

    # Header Document
    story.append(Paragraph("Katalog Lowongan Kerja — Lokeriva.vercel.app", style_title))
    
    info_parts = [
        f"Total: <b>{len(jobs)} lowongan</b>",
        f"Diunduh: {datetime.now().strftime('%d-%m-%Y %H:%M WIB')}",
        "Platform: <b>Lokeriva.vercel.app</b>",
        "Created by <b>Xnuvers007</b>"
    ]
    if query:
        info_parts.append(f"Pencarian: <b>'{safe_xml(query)}'</b>")
    if source_filter:
        info_parts.append(f"Sumber: <b>'{safe_xml(source_filter)}'</b>")
    if location_filter:
        info_parts.append(f"Lokasi: <b>'{safe_xml(location_filter)}'</b>")

    info_text = " | ".join(info_parts)
    story.append(Paragraph(info_text, style_subtitle))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cbd5e1'), spaceAfter=12))

    # Table Header
    table_data = [[
        Paragraph("<b>No</b>", style_header_cell),
        Paragraph("<b>Posisi & Perusahaan</b>", style_header_cell),
        Paragraph("<b>Kategori / Sumber</b>", style_header_cell),
        Paragraph("<b>Lokasi & Tanggal</b>", style_header_cell),
        Paragraph("<b>Tautan Lamaran</b>", style_header_cell)
    ]]

    # Batasi maksimal 150 lowongan untuk menjaga ukuran PDF tetap ringan & cepat
    for idx, j in enumerate(jobs[:150], start=1):
        posisi = safe_xml(j.get("posisi", "-"))
        perusahaan = safe_xml(j.get("perusahaan", "-"))
        kategori = safe_xml(j.get("kategori", "-"))
        sumber = safe_xml(j.get("sumber", "-"))
        lokasi = safe_xml(j.get("lokasi", "-"))
        tanggal = safe_xml(j.get("tanggal", "-"))
        link_url = safe_url(j.get("link", ""))

        if link_url:
            link_html = f'<a href="{link_url}" color="#2563eb"><u>Buka Lowongan &rarr;</u></a>'
        else:
            link_html = '<font color="#94a3b8">Tidak tersedia</font>'

        row = [
            Paragraph(str(idx), style_cell),
            Paragraph(f"<b>{posisi}</b><br/><font color='#475569'>{perusahaan}</font>", style_cell),
            Paragraph(f"{kategori}<br/><font color='#64748b'><i>{sumber}</i></font>", style_cell),
            Paragraph(f"{lokasi}<br/><font color='#94a3b8'>{tanggal}</font>", style_cell),
            Paragraph(link_html, style_link)
        ]
        table_data.append(row)

    t = Table(table_data, colWidths=[24, 195, 120, 110, 90], repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#ffffff')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafc')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))

    story.append(t)

    if len(jobs) > 150:
        story.append(Spacer(1, 10))
        story.append(Paragraph(f"<i>Catatan: Menampilkan 150 lowongan pertama dari total {len(jobs)} hasil pencarian. Kunjungi website untuk melihat seluruh daftar lengkap.</i>", style_subtitle))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
