#!/usr/bin/env python3
"""
PDF QR Code Embedding Utility for Wedding Guest Verification System

This module handles embedding QR codes into the wedding invitation PDF.
"""

import os
import io
import base64
from pathlib import Path
import qrcode
from PIL import Image, ImageDraw
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import tempfile

class PDFQRGenerator:
    def __init__(self, base_url="https://doublehaffairs.vercel.app"):
        self.base_url = base_url
        self.pdf_template_path = Path("DoubleHaffairs .pdf")
        
    def create_qr_code_image(self, code_id, size=(100, 100)):
        """Generate QR code image"""
        qr_url = f"{self.base_url}/init?code={code_id}"
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        # Create QR code image
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Resize to specified size
        qr_img = qr_img.resize(size, Image.Resampling.LANCZOS)
        
        return qr_img
    
    def create_qr_overlay_pdf(self, qr_img, page_width, page_height):
        """Create a PDF overlay with the QR code positioned in the middle of the page"""
        # Create a temporary file for the overlay
        overlay_buffer = io.BytesIO()
        
        # Create canvas with same dimensions as the original page
        c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))
        
        # Convert PIL image to reportlab ImageReader
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        qr_image_reader = ImageReader(qr_buffer)
        
        # Calculate position to place QR code lower on page
        qr_width, qr_height = qr_img.size
        x_pos = (page_width - qr_width) / 2
        # Move QR code down by 150 points from center
        y_pos = (page_height - qr_height) / 2 - 67
        
        # Draw QR code on canvas
        c.drawImage(qr_image_reader, x_pos, y_pos, width=qr_width, height=qr_height)
        c.save()
        
        overlay_buffer.seek(0)
        return overlay_buffer
    
    def embed_qr_in_pdf(self, code_id, qr_number=None):
        """
        Embed QR code into the second page of the wedding invitation PDF
        
        Returns:
            dict: Contains success status, file path, and base64 encoded PDF
        """
        try:
            if not self.pdf_template_path.exists():
                return {
                    "success": False,
                    "error": f"Template PDF not found: {self.pdf_template_path}"
                }
            
            # Read the original PDF
            with open(self.pdf_template_path, 'rb') as pdf_file:
                pdf_reader = PdfReader(pdf_file)
                pdf_writer = PdfWriter()
                
                # Check if PDF has at least 2 pages
                if len(pdf_reader.pages) < 2:
                    return {
                        "success": False,
                        "error": "PDF must have at least 2 pages"
                    }
                
                # Copy first page as-is
                pdf_writer.add_page(pdf_reader.pages[0])
                
                # Get second page dimensions
                second_page = pdf_reader.pages[1]
                page_rect = second_page.mediabox
                page_width = float(page_rect.width)
                page_height = float(page_rect.height)
                
                # Generate QR code image
                qr_img = self.create_qr_code_image(code_id, size=(120, 120))
                
                # Create QR overlay PDF
                overlay_buffer = self.create_qr_overlay_pdf(qr_img, page_width, page_height)
                
                # Read overlay PDF
                overlay_reader = PdfReader(overlay_buffer)
                overlay_page = overlay_reader.pages[0]
                
                # Merge second page with QR overlay
                second_page.merge_page(overlay_page)
                pdf_writer.add_page(second_page)
                
                # Add remaining pages if any
                for i in range(2, len(pdf_reader.pages)):
                    pdf_writer.add_page(pdf_reader.pages[i])
                
                # Generate output filename
                output_filename = f"invitation_qr_{qr_number or 'custom'}_{code_id[:8]}.pdf"
                output_path = Path("qr_pdfs") / output_filename
                output_path.parent.mkdir(exist_ok=True)
                
                # Save the modified PDF
                with open(output_path, 'wb') as output_file:
                    pdf_writer.write(output_file)
                
                # Convert to base64 for API response
                with open(output_path, 'rb') as pdf_file:
                    pdf_base64 = base64.b64encode(pdf_file.read()).decode()
                
                return {
                    "success": True,
                    "file_path": str(output_path),
                    "filename": output_filename,
                    "pdf_base64": pdf_base64,
                    "code_id": code_id,
                    "qr_number": qr_number
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to embed QR code in PDF: {str(e)}"
            }
    
    def generate_bulk_pdf_qr_codes(self, codes_data):
        """
        Generate multiple PDF invitations with embedded QR codes
        
        Args:
            codes_data: List of dicts with code_id and qr_number
            
        Returns:
            dict: Results of bulk generation
        """
        results = []
        successful_count = 0
        failed_count = 0
        
        for code_data in codes_data:
            code_id = code_data.get('code_id')
            qr_number = code_data.get('qr_number')
            
            result = self.embed_qr_in_pdf(code_id, qr_number)
            results.append(result)
            
            if result.get('success'):
                successful_count += 1
            else:
                failed_count += 1
        
        return {
            "success": True,
            "total_processed": len(codes_data),
            "successful_count": successful_count,
            "failed_count": failed_count,
            "results": results
        }

def main():
    """Command line interface for PDF QR generation"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate PDF invitations with embedded QR codes")
    parser.add_argument('--code-id', required=True, help='QR code ID')
    parser.add_argument('--qr-number', type=int, help='QR number for filename')
    parser.add_argument('--output-dir', default='qr_pdfs', help='Output directory')
    
    args = parser.parse_args()
    
    generator = PDFQRGenerator()
    result = generator.embed_qr_in_pdf(args.code_id, args.qr_number)
    
    if result['success']:
        print(f"✅ Successfully generated PDF: {result['filename']}")
        print(f"📁 Saved to: {result['file_path']}")
    else:
        print(f"❌ Failed to generate PDF: {result['error']}")

if __name__ == "__main__":
    main()