from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.core.config import get_settings


class PdfExportService:
    def __init__(self):
        self.settings = get_settings()
        registerFont(UnicodeCIDFont("STSong-Light"))
        self.styles = getSampleStyleSheet()
        self.styles.add(ParagraphStyle(name="ChineseTitle", fontName="STSong-Light", fontSize=18, leading=24))
        self.styles.add(ParagraphStyle(name="ChineseBody", fontName="STSong-Light", fontSize=10.5, leading=17))

    def export(self, report_id: int, title: str, sections: list[str]) -> str:
        output_path = self.settings.pdf_path / f"report_{report_id}.pdf"
        doc = SimpleDocTemplate(str(output_path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm)
        story = [Paragraph(title, self.styles["ChineseTitle"]), Spacer(1, 8)]
        for section in sections:
            story.append(Paragraph(section.replace("\n", "<br/>"), self.styles["ChineseBody"]))
            story.append(Spacer(1, 8))
        doc.build(story)
        return str(output_path)
