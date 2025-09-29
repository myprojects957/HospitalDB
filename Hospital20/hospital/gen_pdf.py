from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch, mm
from reportlab.lib.pagesizes import A4
from datetime import datetime
import os
import hashlib

class PrescriptionPDF:
    def __init__(self):
        self.width, self.height = A4
        self.margin = 30
        
        self.primary_color = colors.HexColor('#1e40af')  # Deep blue
        self.secondary_color = colors.HexColor('#3b82f6')  # Lighter blue
        self.text_color = colors.HexColor('#1f2937')  # Dark gray
        self.accent_color = colors.HexColor('#0891b2')  # Teal
        self.light_bg = colors.HexColor('#f0f9ff')  # Very light blue
        self.border_color = colors.HexColor('#e2e8f0')  # Light gray

    def generate_prescription(self, data, output_path):
        c = canvas.Canvas(output_path, pagesize=A4)
        
         Box
        c.setFillColor(self.primary_color)
        c.rect(0, self.height - 140, self.width, 140, fill=True)
        
        # Hospital Name
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 32)
        c.drawString(self.margin, self.height - 60, "Hospital Management")
        
        c.setFont("Helvetica", 16)
        c.drawString(self.margin, self.height - 85, "Professional Healthcare Services")
        
        # Contact Info Box
        c.setFillColor(self.light_bg)
        c.setStrokeColor(self.border_color)
        info_box_width = 180
        c.roundRect(self.width - info_box_width - self.margin, self.height - 110, 
                   info_box_width, 90, 8, stroke=1, fill=1)
        
        c.setFillColor(self.text_color)
        c.setFont("Helvetica", 10)
        c.drawString(self.width - info_box_width - self.margin + 10, self.height - 45, "☎ +1 (555) 123-4567")
        c.drawString(self.width - info_box_width - self.margin + 10, self.height - 60, "✉ contact@hospital.com")
        c.drawString(self.width - info_box_width - self.margin + 10, self.height - 75, "🌐 www.hospital.com")
        
        # Prescription Title Box
        c.setFillColor(self.secondary_color)
        c.rect(self.margin, self.height - 190, self.width - (2 * self.margin), 35, fill=True)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(self.margin + 10, self.height - 175, "Medical Prescription")
        
        # Prescription Details Box
        c.setFillColor(self.light_bg)
        details_box_y = self.height - 240
        c.roundRect(self.margin, details_box_y, self.width - (2 * self.margin), 40, 8, fill=True)
        
        c.setFillColor(self.text_color)
        c.setFont("Helvetica", 11)
        c.drawString(self.margin + 10, details_box_y + 25, f"Prescription ID: RX-{data['pres_id']}")
        c.drawString(self.margin + 200, details_box_y + 25, f"Date: {datetime.now().strftime('%B %d, %Y')}")
        c.drawString(self.margin + 400, details_box_y + 25, f"Time: {datetime.now().strftime('%I:%M %p')}")
        
        info_box_y = details_box_y - 100
        c.setFillColor(self.light_bg)
        c.roundRect(self.margin, info_box_y, self.width - (2 * self.margin), 80, 8, fill=True)
        
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(self.margin + 10, info_box_y + 65, "Patient Information")
        
        c.setFillColor(self.text_color)
        c.setFont("Helvetica", 11)
        c.drawString(self.margin + 20, info_box_y + 45, f"Name: {data['patient_name']}")
        c.drawString(self.margin + 20, info_box_y + 25, f"Consulting Doctor: Dr. {data['doctor_name']}")
        c.drawString(self.margin + 20, info_box_y + 5, f"Date of Visit: {datetime.now().strftime('%B %d, %Y')}")
        
        current_y = info_box_y - 40
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(self.margin, current_y, "Diagnosis:")
        
        diag_box_y = current_y - 60
        c.setFillColor(self.light_bg)
        c.roundRect(self.margin, diag_box_y, self.width - (2 * self.margin), 50, 8, fill=True)
        
        c.setFillColor(self.text_color)
        c.setFont("Helvetica", 11)
        y_offset = diag_box_y + 35
        for line in data['diagnosis'].splitlines():
            if line.strip():
                c.drawString(self.margin + 10, y_offset, line)
                y_offset -= 15
        
        current_y = diag_box_y - 40
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(self.margin, current_y, "Prescribed Medicines:")
        
        med_box_y = current_y - 100
        c.setFillColor(self.light_bg)
        c.roundRect(self.margin, med_box_y, self.width - (2 * self.margin), 90, 8, fill=True)
        
        c.setFillColor(self.text_color)
        c.setFont("Helvetica", 11)
        y_offset = med_box_y + 75
        for line in data['medicines'].splitlines():
            if line.strip():
                c.drawString(self.margin + 10, y_offset, "•  " + line)
                y_offset -= 15
        
        footer_y = 80
        c.setStrokeColor(self.border_color)
        c.setFillColor(self.light_bg)
        c.roundRect(self.margin, footer_y - 40, 200, 50, 8, fill=True)
        
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(self.margin + 10, footer_y, f"Dr. {data['doctor_name']}")
        c.setFont("Helvetica", 9)
        c.setFillColor(self.text_color)
        c.drawString(self.margin + 10, footer_y - 20, "Digital Signature")
        
        c.setFillColor(self.light_bg)
        c.roundRect(self.width - 200 - self.margin, footer_y - 40, 200, 50, 8, fill=True)
        
        verification_id = hashlib.sha256(str(data['pres_id']).encode()).hexdigest()[:8]
        c.setFillColor(self.text_color)
        c.setFont("Helvetica", 8)
        c.drawString(self.width - 190 - self.margin, footer_y, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        c.drawString(self.width - 190 - self.margin, footer_y - 15, f"Verification ID: {verification_id}")
        
        c.setFont("Helvetica", 8)
        c.drawString(self.margin, 30, "This is a digitally generated prescription valid for 30 days from the date of issue.")
        c.drawString(self.margin, 20, "Please consult your healthcare provider before making any changes to prescribed medication.")
        
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