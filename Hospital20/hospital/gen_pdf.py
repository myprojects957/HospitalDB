from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from datetime import datetime
import hashlib
import os

class PrescriptionPDF:
    def __init__(self):
        self.width, self.height = A4
        self.margin = 30
        
        self.primary_color = colors.HexColor('#1e40af')
        self.secondary_color = colors.HexColor('#3b82f6')
        self.text_color = colors.HexColor('#1f2937')
        self.accent_color = colors.HexColor('#0891b2')
        self.light_bg = colors.HexColor('#f0f9ff')
        self.border_color = colors.HexColor('#e2e8f0')

    def generate_prescription(self, data, output_path):
        c = canvas.Canvas(output_path, pagesize=A4)

        # Header
        c.setFillColor(self.primary_color)
        c.rect(0, self.height - 140, self.width, 140, fill=True)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 32)
        c.drawString(self.margin, self.height - 60, "Hospital Management")
        c.setFont("Helvetica", 16)
        c.drawString(self.margin, self.height - 85, "Professional Healthcare Services")

        # Prescription Title
        c.setFillColor(self.secondary_color)
        c.rect(self.margin, self.height - 190, self.width - (2 * self.margin), 35, fill=True)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(self.margin + 10, self.height - 175, "Medical Prescription")

        # Prescription Details
        c.setFillColor(self.text_color)
        c.setFont("Helvetica", 11)
        c.drawString(self.margin + 10, self.height - 230, f"Prescription ID: RX-{data['pres_id']}")
        c.drawString(self.margin + 200, self.height - 230, f"Date: {datetime.now().strftime('%B %d, %Y')}")
        c.drawString(self.margin + 400, self.height - 230, f"Time: {datetime.now().strftime('%I:%M %p')}")

        # Patient Info
        info_box_y = self.height - 330
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(self.margin, info_box_y, "Patient Information")
        c.setFillColor(self.text_color)
        c.setFont("Helvetica", 11)
        c.drawString(self.margin + 10, info_box_y - 20, f"Name: {data['patient_name']}")
        c.drawString(self.margin + 10, info_box_y - 40, f"Consulting Doctor: {data['doctor_name']}")
        c.drawString(self.margin + 10, info_box_y - 60, f"Date of Visit: {datetime.now().strftime('%B %d, %Y')}")

        # Diagnosis
        diag_y = info_box_y - 100
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(self.margin, diag_y, "Diagnosis:")
        c.setFillColor(self.text_color)
        c.setFont("Helvetica", 11)
        y_offset = diag_y - 20
        for line in data['diagnosis'].splitlines():
            c.drawString(self.margin + 10, y_offset, line)
            y_offset -= 15

        # Medicines
        med_y = y_offset - 20
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(self.margin, med_y, "Prescribed Medicines:")
        c.setFillColor(self.text_color)
        c.setFont("Helvetica", 11)
        y_offset = med_y - 20
        for line in data['medicines'].splitlines():
            c.drawString(self.margin + 10, y_offset, "• " + line)
            y_offset -= 15

        # Footer
        footer_y = 50
        c.setFillColor(self.text_color)
        verification_id = hashlib.sha256(str(data['pres_id']).encode()).hexdigest()[:8]
        c.setFont("Helvetica", 8)
        c.drawString(self.margin, footer_y + 20, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        c.drawString(self.margin, footer_y + 5, f"Verification ID: {verification_id}")
        c.drawString(self.margin, 10, "Digitally generated prescription valid for 30 days. Consult your doctor before changing medication.")

        c.save()
        return True

def generate_prescription(pres_id, patient_name, doctor_name, diagnosis, medicines, output_path):
    pdf_generator = PrescriptionPDF()
    data = {
        'pres_id': pres_id,
        'patient_name': patient_name,
        'doctor_name': doctor_name,
        'diagnosis': diagnosis,
        'medicines': medicines
    }
    return pdf_generator.generate_prescription(data, output_path)
