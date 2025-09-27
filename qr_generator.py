#!/usr/bin/env python3
"""
QR Code Generation Utility for Wedding Guest Verification System

This script provides command-line tools for generating and managing QR codes.
"""

import argparse
import sys
import os
import json
from pathlib import Path
from app import qr_manager, qr_codes_collection
import base64

def generate_qr_codes(count, output_dir="qr_codes", save_images=True, generate_pdfs=False):
    """Generate bulk QR codes and optionally save images and PDFs"""
    print(f"Generating {count} QR codes...")
    
    try:
        codes = qr_manager.generate_bulk_qr_codes(count, generate_pdfs)
        
        if save_images:
            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)
            
            # Save individual QR code images
            for code in codes:
                qr_number = code['qr_number']
                code_id = code['code_id']
                
                # Decode base64 image
                img_data = base64.b64decode(code['qr_image_base64'])
                
                # Save image file
                img_filename = f"qr_{qr_number:03d}_{code_id[:8]}.png"
                img_path = output_path / img_filename
                
                with open(img_path, 'wb') as f:
                    f.write(img_data)
                
                print(f"Saved: {img_filename}")
            
            # Save codes metadata as JSON
            metadata_path = output_path / "codes_metadata.json"
            metadata = {
                "generated_count": len(codes),
                "codes": [
                    {
                        "code_id": code["code_id"],
                        "qr_number": code["qr_number"],
                        "qr_url": code["qr_url"]
                    }
                    for code in codes
                ]
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            print(f"\nGenerated {len(codes)} QR codes in '{output_dir}' directory")
            print(f"Metadata saved to: {metadata_path}")
            
            # Print PDF generation summary
            if generate_pdfs:
                pdf_successful = sum(1 for code in codes if code.get('has_pdf', False))
                pdf_failed = len(codes) - pdf_successful
                print(f"\n📄 PDF Generation Summary:")
                print(f"   ✅ Successful: {pdf_successful}")
                print(f"   ❌ Failed: {pdf_failed}")
                if pdf_successful > 0:
                    print(f"   📁 PDFs saved to: qr_pdfs/ directory")
        
        return codes
        
    except Exception as e:
        print(f"Error generating QR codes: {e}")
        sys.exit(1)

def print_qr_stats():
    """Print current QR code statistics"""
    try:
        total_codes = qr_codes_collection.count_documents({})
        initialized_codes = qr_codes_collection.count_documents({"name": {"$ne": None}})
        used_codes = qr_codes_collection.count_documents({"scan_count": {"$gt": 0}})
        max_used_codes = qr_codes_collection.count_documents({"scan_count": {"$gte": 2}})
        
        print("=== QR Code Statistics ===")
        print(f"Total codes: {total_codes}")
        print(f"Initialized codes: {initialized_codes}")
        print(f"Used codes: {used_codes}")
        print(f"Fully used codes (2+ scans): {max_used_codes}")
        print(f"Unused codes: {total_codes - used_codes}")
        
        return {
            "total_codes": total_codes,
            "initialized_codes": initialized_codes,
            "used_codes": used_codes,
            "max_used_codes": max_used_codes,
            "unused_codes": total_codes - used_codes
        }
        
    except Exception as e:
        print(f"Error fetching statistics: {e}")
        sys.exit(1)

def export_codes_list(output_file="codes_list.json"):
    """Export all QR codes to a JSON file"""
    try:
        codes = list(qr_codes_collection.find({}, {
            "_id": 0,
            "code_id": 1,
            "qr_number": 1,
            "name": 1,
            "scan_count": 1,
            "max_scans": 1,
            "created_at": 1,
            "initialized_at": 1
        }).sort("qr_number", 1))
        
        with open(output_file, 'w') as f:
            json.dump({
                "export_date": str(qr_codes_collection.find_one()["created_at"]) if codes else None,
                "total_codes": len(codes),
                "codes": codes
            }, f, indent=2, default=str)
        
        print(f"Exported {len(codes)} codes to {output_file}")
        
    except Exception as e:
        print(f"Error exporting codes: {e}")
        sys.exit(1)

def clear_all_codes():
    """Clear all QR codes from database (use with caution!)"""
    response = input("Are you sure you want to delete ALL QR codes? This cannot be undone. (yes/no): ")
    
    if response.lower() == 'yes':
        try:
            result = qr_codes_collection.delete_many({})
            print(f"Deleted {result.deleted_count} QR codes")
        except Exception as e:
            print(f"Error clearing codes: {e}")
            sys.exit(1)
    else:
        print("Operation cancelled")

def main():
    parser = argparse.ArgumentParser(
        description="Wedding QR Code Management Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 200 QR codes and save images
  python qr_generator.py generate --count 200 --output-dir wedding_qr_codes

  # Generate codes with PDF invitations
  python qr_generator.py generate --count 50 --generate-pdfs

  # Generate codes without saving images
  python qr_generator.py generate --count 50 --no-images

  # Generate PDFs only (no images)
  python qr_generator.py generate --count 20 --no-images --generate-pdfs

  # Show statistics
  python qr_generator.py stats

  # Export all codes to JSON
  python qr_generator.py export --output codes_backup.json

  # Clear all codes (dangerous!)
  python qr_generator.py clear
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate bulk QR codes')
    gen_parser.add_argument('--count', type=int, default=200, help='Number of QR codes to generate (default: 200)')
    gen_parser.add_argument('--output-dir', default='qr_codes', help='Output directory for images (default: qr_codes)')
    gen_parser.add_argument('--no-images', action='store_true', help="Don't save QR code images")
    gen_parser.add_argument('--generate-pdfs', action='store_true', help='Generate PDF invitations with embedded QR codes')
    
    # Stats command
    subparsers.add_parser('stats', help='Show QR code statistics')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export all QR codes to JSON')
    export_parser.add_argument('--output', default='codes_list.json', help='Output JSON file (default: codes_list.json)')
    
    # Clear command
    subparsers.add_parser('clear', help='Clear all QR codes (DANGER!)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute commands
    if args.command == 'generate':
        generate_qr_codes(
            count=args.count,
            output_dir=args.output_dir,
            save_images=not args.no_images,
            generate_pdfs=args.generate_pdfs
        )
    elif args.command == 'stats':
        print_qr_stats()
    elif args.command == 'export':
        export_codes_list(args.output)
    elif args.command == 'clear':
        clear_all_codes()

if __name__ == "__main__":
    main()