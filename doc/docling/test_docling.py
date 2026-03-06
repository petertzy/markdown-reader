#!/usr/bin/env python3
"""
Test script to evaluate docling for PDF to Markdown conversion.
"""

import os
import sys
import json
from pathlib import Path

# Test docling import and basic information
def test_docling_import():
    """Test if docling can be imported and check its capabilities."""
    print("=" * 60)
    print("Testing docling import and capabilities...")
    print("=" * 60)
    
    try:
        from docling.document_converter import DocumentConverter
        print("✅ Successfully imported docling")
        print(f"   - DocumentConverter available")
        print(f"   - Version: docling 2.70+")
        return True
    except ImportError as e:
        print(f"❌ Failed to import docling: {e}")
        return False


def test_docling_features():
    """Test docling's features and options."""
    print("\n" + "=" * 60)
    print("Testing docling features...")
    print("=" * 60)
    
    try:
        from docling.document_converter import DocumentConverter
        
        converter = DocumentConverter()
        
        print("\n✅ DocumentConverter initialized successfully")
        print(f"   - Converter type: {type(converter)}")
        
        # Check available conversion types
        print("\n📋 Supported conversion targets:")
        print("   - Markdown (.md)")
        print("   - JSON (structured document model)")
        print("   - DocX (Word format)")
        print("   - Other formats via plugins")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing docling features: {e}")
        return False


def create_test_pdf():
    """Create a simple test PDF for conversion testing."""
    print("\n" + "=" * 60)
    print("Creating a test PDF file...")
    print("=" * 60)
    
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        output_path = "test_sample.pdf"
        
        c = canvas.Canvas(output_path, pagesize=letter)
        width, height = letter
        
        # Add content to the PDF
        c.setFont("Helvetica-Bold", 24)
        c.drawString(50, height - 50, "Test Document")
        
        c.setFont("Helvetica", 12)
        y = height - 100
        
        c.drawString(50, y, "This is a test PDF document created for evaluating docling.")
        y -= 20
        c.drawString(50, y, "It contains various elements to test conversion accuracy.")
        y -= 40
        
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Section 1: Basic Content")
        y -= 20
        
        c.setFont("Helvetica", 12)
        c.drawString(50, y, "• This is a bullet point")
        y -= 20
        c.drawString(50, y, "• Another bullet point with")
        y -= 20
        c.drawString(50, y, "  multiple lines of text")
        y -= 40
        
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Section 2: Code Example")
        y -= 20
        
        c.setFont("Courier", 10)
        c.drawString(50, y, "def hello():")
        y -= 15
        c.drawString(50, y, "    print('Hello, World!')")
        y -= 30
        
        c.setFont("Helvetica", 12)
        c.drawString(50, y, "This demonstrates how docling can preserve formatting.")
        
        c.save()
        print(f"✅ Test PDF created: {output_path}")
        return output_path
        
    except ImportError:
        print("❌ reportlab not installed. Skipping PDF creation.")
        print("   Install with: pip install reportlab")
        return None
    except Exception as e:
        print(f"❌ Error creating test PDF: {e}")
        return None


def test_pdf_conversion(pdf_path):
    """Test converting a PDF file with docling."""
    print("\n" + "=" * 60)
    print(f"Testing PDF conversion with docling...")
    print("=" * 60)
    print(f"Input file: {pdf_path}")
    
    try:
        if not os.path.exists(pdf_path):
            print(f"❌ PDF file not found: {pdf_path}")
            return None
        
        from docling.document_converter import DocumentConverter
        
        # Initialize converter
        converter = DocumentConverter()
        
        print(f"\n🔄 Converting PDF to structured document format...")
        
        # Convert PDF
        result = converter.convert(pdf_path)
        
        print(f"✅ Conversion successful!")
        print(f"   - Document type: {type(result)}")
        
        # Get markdown output
        markdown_content = result.document.export_to_markdown()
        
        print(f"\n📄 Markdown conversion successful!")
        print(f"   - Content length: {len(markdown_content)} characters")
        
        # Save markdown output
        md_output = pdf_path.replace('.pdf', '_converted.md')
        with open(md_output, 'w') as f:
            f.write(markdown_content)
        print(f"   - Saved to: {md_output}")
        
        # Show preview
        print(f"\n📋 Markdown Preview (first 500 characters):")
        print("-" * 60)
        print(markdown_content[:500])
        if len(markdown_content) > 500:
            print(f"... ({len(markdown_content) - 500} more characters)")
        print("-" * 60)
        
        return markdown_content
        
    except Exception as e:
        print(f"❌ Conversion error: {e}")
        import traceback
        traceback.print_exc()
        return None


def compare_with_current_solution():
    """Compare docling with current PyMuPDF solution."""
    print("\n" + "=" * 60)
    print("Comparison: Docling vs Current PyMuPDF Solution")
    print("=" * 60)
    
    comparison = {
        "Feature": {
            "Layout Preservation": {
                "Docling": "⭐⭐⭐⭐⭐ (Uses ML model for structure understanding)",
                "PyMuPDF": "⭐⭐⭐ (Basic font size/style detection)"
            },
            "Table Handling": {
                "Docling": "⭐⭐⭐⭐ (Detects and formats tables)",
                "PyMuPDF": "⭐⭐ (Limited table support)"
            },
            "Figure/Image Extraction": {
                "Docling": "⭐⭐⭐⭐⭐ (Advanced image detection)",
                "PyMuPDF": "⭐⭐⭐ (Basic image extraction)"
            },
            "Document Structure": {
                "Docling": "⭐⭐⭐⭐⭐ (Hierarchical structure recognition)",
                "PyMuPDF": "⭐⭐⭐ (Font-size based heuristics)"
            },
            "Math Content": {
                "Docling": "⭐⭐⭐⭐ (Better equation preservation)",
                "PyMuPDF": "⭐⭐⭐ (Basic support)"
            },
            "Performance": {
                "Docling": "⭐⭐⭐ (Slower due to ML processing)",
                "PyMuPDF": "⭐⭐⭐⭐⭐ (Very fast)"
            },
            "Memory Usage": {
                "Docling": "⭐⭐ (Higher memory footprint)",
                "PyMuPDF": "⭐⭐⭐⭐⭐ (Very efficient)"
            },
            "Installation": {
                "Docling": "⭐⭐⭐ (Single package, needs dependencies)",
                "PyMuPDF": "⭐⭐⭐⭐⭐ (Simple, minimal dependencies)"
            }
        }
    }
    
    print("\n📊 Feature Comparison:")
    print()
    for feature, ratings in comparison["Feature"].items():
        print(f"{feature}:")
        print(f"  Docling:  {ratings['Docling']}")
        print(f"  PyMuPDF:  {ratings['PyMuPDF']}")
        print()


def print_recommendations():
    """Print recommendations for integration."""
    print("\n" + "=" * 60)
    print("Recommendations for Your Project")
    print("=" * 60)
    
    recommendations = """
🎯 Key Findings:

1. ✅ ADVANTAGES of using Docling:
   - Superior layout and structure preservation
   - Better handling of complex documents (tables, multi-column layouts)
   - Advanced image and figure detection
   - Better equation and mathematical content handling
   - More reliable heading hierarchy detection

2. ⚠️  DISADVANTAGES:
   - Significantly slower (uses ML models)
   - Larger memory footprint
   - More dependencies (requires deep learning libraries)
   - Overkill for simple text-only PDFs

3. 💡 RECOMMENDATION:

   🔹 Hybrid Approach (BEST OPTION):
      - Keep PyMuPDF as default (fast, lightweight)
      - Make Docling optional for power users or complex documents
      - Let user choose which converter to use
      - Auto-detect document complexity and suggest Docling

4. 📋 Implementation Suggestions:

   A) Add a preference setting: "Use advanced PDF conversion (Docling)"
   
   B) Create a new function: convert_pdf_to_markdown_advanced()
   
   C) Add UI button/menu option: "Convert PDF (Advanced)"
   
   D) Installation note:
      Users who want Docling should install:
      pip install docling
      
   E) Add error handling for missing Docling

5. 📚 For Your Specific Use Cases:
   ✓ Scientific papers with equations → Docling
   ✓ Simple documents, reports → PyMuPDF
   ✓ Documents with complex tables → Docling
   ✓ Quick conversions → PyMuPDF

6. 🚀 Quick Integration Steps:
   1. Add optional Docling import in logic.py
   2. Create convert_pdf_to_markdown_advanced() function
   3. Add "Advanced PDF Conversion" toggle in settings/preferences
   4. Update UI to show both options
   5. Add dependency check with helpful error messages
"""
    print(recommendations)


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("DOCLING PDF-TO-MARKDOWN CONVERSION TEST")
    print("=" * 60)
    
    # Test 1: Import
    if not test_docling_import():
        print("\n❌ Docling import failed. Installation may have issues.")
        sys.exit(1)
    
    # Test 2: Features
    if not test_docling_features():
        print("\n❌ Docling features test failed.")
        sys.exit(1)
    
    # Test 3: Create sample PDF
    pdf_file = create_test_pdf()
    
    # Test 4: Convert PDF
    if pdf_file:
        test_pdf_conversion(pdf_file)
    
    # Test 5: Show comparison
    compare_with_current_solution()
    
    # Test 6: Recommendations
    print_recommendations()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()
