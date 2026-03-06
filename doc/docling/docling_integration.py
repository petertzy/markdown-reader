"""
Docling Integration Example Code

This module demonstrates how to integrate Docling into the MarkdownReader project.
You can copy these functions into markdown_reader/logic.py.

Usage examples:
    # Standard conversion (PyMuPDF)
    markdown = convert_pdf_to_markdown(pdf_path)
    
    # Advanced conversion (Docling)
    markdown = convert_pdf_to_markdown_advanced(pdf_path)
    
    # Smart conversion (automatic selection)
    markdown = convert_pdf_to_markdown_smart(pdf_path, use_docling_preference=True)
"""

import os
import logging
from pathlib import Path
from tkinter import messagebox

# Configure logging
logger = logging.getLogger(__name__)


def convert_pdf_to_markdown_advanced(pdf_path):
    """
    Perform advanced PDF to Markdown conversion using Docling.
    
    Features:
    - Uses deep learning models to understand document structure
    - Better handling of complex layouts, tables, multi-column text
    - Automatically recognizes headings, code blocks, lists, etc.
    - Supports OCR for scanned PDFs
    - More accurate image extraction
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        str: Markdown formatted string
        
    Raises:
        ImportError: If Docling is not installed
        Exception: If conversion fails
    """
    
    try:
        from docling.document_converter import DocumentConverter
        
        # Ensure absolute path
        abs_path = os.path.abspath(pdf_path)
        
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"PDF file not found: {abs_path}")
        
        logger.info(f"Starting advanced PDF conversion with Docling: {abs_path}")
        
        # Initialize converter
        converter = DocumentConverter()
        
        # Perform conversion
        result = converter.convert(abs_path)
        
        # Export to Markdown
        markdown_text = result.document.export_to_markdown()
        
        logger.info(f"Advanced conversion completed successfully. Output length: {len(markdown_text)} chars")
        
        return markdown_text.strip()
        
    except ImportError as e:
        logger.warning(f"Docling not installed. Falling back to standard converter. Error: {e}")
        raise ImportError(
            "Docling is not installed. Install it using: pip install docling\n"
            "Falling back to standard PDF converter."
        ) from e
        
    except Exception as e:
        logger.error(f"Advanced PDF conversion failed: {e}")
        raise Exception(f"Failed to convert PDF with Docling: {e}") from e


def convert_pdf_to_markdown_with_error_handling(pdf_path, use_advanced=False):
    """
    PDF conversion with error handling and fallback.
    
    Tries the requested method first and automatically falls back on failure.
    
    Args:
        pdf_path (str): Path to the PDF file
        use_advanced (bool): Whether to use Docling (default: False)
        
    Returns:
        str: Markdown string, or empty string if conversion fails
    """
    
    try:
        if use_advanced:
            try:
                logger.info("Attempting advanced PDF conversion with Docling...")
                return convert_pdf_to_markdown_advanced(pdf_path)
            except ImportError:
                logger.info("Docling not available, falling back to PyMuPDF...")
                # Fall back to standard method
                from markdown_reader.logic import convert_pdf_to_markdown
                return convert_pdf_to_markdown(pdf_path)
        else:
            from markdown_reader.logic import convert_pdf_to_markdown
            return convert_pdf_to_markdown(pdf_path)
            
    except Exception as e:
        logger.error(f"PDF conversion failed: {e}")
        messagebox.showerror(
            "PDF Conversion Error",
            f"Failed to convert PDF:\n{str(e)}\n\n"
            f"Tips:\n"
            f"- Ensure the file is a valid PDF\n"
            f"- Try the standard converter\n"
            f"- Check file permissions"
        )
        return ""


def is_docling_available():
    """
    Check whether Docling is installed and importable.
    
    Returns:
        bool: True if Docling is available, False otherwise
    """
    try:
        from docling.document_converter import DocumentConverter
        return True
    except ImportError:
        return False


def get_pdf_converter_info():
    """
    Get information about available PDF converters.
    
    Returns:
        dict: Dictionary containing converter details
    """
    
    return {
        "default": {
            "name": "PyMuPDF",
            "available": True,
            "speed": "fast",
            "quality": "good",
            "memory": "low",
            "features": ["text extraction", "images", "basic structure"]
        },
        "advanced": {
            "name": "Docling",
            "available": is_docling_available(),
            "speed": "medium",
            "quality": "excellent",
            "memory": "high",
            "features": [
                "ML-based structure understanding",
                "table detection",
                "multi-column layout",
                "formula recognition",
                "OCR support",
                "image classification"
            ]
        }
    }


# =============================================================================
# Usage examples for markdown_reader/ui.py
# =============================================================================

"""
Example 1: Modify load_file() to support both conversion methods

def load_file(self, file_path):
    # ... existing code ...
    
    if is_pdf:
        # Check user preference
        use_advanced = self.preferences.get('use_advanced_pdf', False)
        
        try:
            if use_advanced:
                content = convert_pdf_to_markdown_with_error_handling(
                    abs_path, 
                    use_advanced=True
                )
            else:
                content = convert_pdf_to_markdown(abs_path)
                
            if content:
                text_area.delete('1.0', 'end')
                text_area.insert('end', content)
        except Exception as e:
            messagebox.showerror("Conversion Error", str(e))
            
    # ... continue processing ...


Example 2: Add preference menu item

def create_menus(self):
    # ... existing code ...
    
    # Add Tools menu
    tools_menu = tk.Menu(self.menu_bar)
    self.menu_bar.add_cascade(label="Tools", menu=tools_menu)
    
    # PDF conversion options
    tools_menu.add_checkbutton(
        label="Use Advanced PDF Conversion (Docling)",
        variable=self.use_advanced_pdf_var,
        command=self.save_preferences
    )
    
    tools_menu.add_command(
        label="PDF Converter Info",
        command=self.show_converter_info
    )


Example 3: Show converter information dialog

def show_converter_info(self):
    info = get_pdf_converter_info()
    
    message = "Available PDF Converters:\n\n"
    
    for converter_type, details in info.items():
        status = "✅ Available" if details['available'] else "❌ Not installed"
        message += f"{details['name']} - {status}\n"
        message += f"  Speed: {details['speed']}\n"
        message += f"  Quality: {details['quality']}\n"
        message += f"  Memory: {details['memory']}\n"
        message += f"  Features: {', '.join(details['features'])}\n\n"
    
    messagebox.showinfo("PDF Converter Info", message)


Example 4: Basic PDF complexity detection (for smart mode)

def detect_pdf_complexity(pdf_path):
    '''
    Simple PDF complexity detection.
    Can be extended with more sophisticated logic.
    '''
    try:
        import fitz
        doc = fitz.open(pdf_path)
        
        complexity_score = 0
        
        # Check for tables
        page = doc[0]
        tables = page.find_tables()
        complexity_score += len(tables) * 10
        
        # Check for images
        images = page.get_images()
        complexity_score += len(images) * 5
        
        # Check text block count
        text_dict = page.get_text("dict")
        blocks = text_dict.get("blocks", [])
        complexity_score += len(blocks)
        
        doc.close()
        
        return complexity_score > 20  # threshold
        
    except Exception as e:
        logger.warning(f"Could not detect PDF complexity: {e}")
        return False


Example 5: Conversion with timing (for performance monitoring)

import time

def convert_with_timing(pdf_path, use_advanced=False):
    '''
    Perform conversion and log execution time.
    '''
    start_time = time.time()
    
    try:
        result = convert_pdf_to_markdown_with_error_handling(
            pdf_path, 
            use_advanced=use_advanced
        )
        elapsed = time.time() - start_time
        
        converter = "Docling" if use_advanced else "PyMuPDF"
        logger.info(f"{converter} conversion took {elapsed:.2f} seconds")
        
        return result
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Conversion failed after {elapsed:.2f} seconds: {e}")
        raise
"""


# =============================================================================
# Standalone test / debug script
# =============================================================================

if __name__ == "__main__":
    """
    Run this file standalone for quick testing:
    
    python docling_integration.py
    python docling_integration.py example.pdf --advanced
    """
    
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*60)
    print("Docling Integration Test")
    print("="*60)
    
    # Check availability
    print("\n1. Converter availability check:")
    info = get_pdf_converter_info()
    for converter_type, details in info.items():
        status = "✅" if details['available'] else "❌"
        print(f"   {status} {details['name']}")
    
    # Conversion test
    print("\n2. To test conversion, provide a PDF file via command line:")
    print("   python docling_integration.py <pdf_file.pdf> [--advanced]")
    
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
        use_advanced = "--advanced" in sys.argv
        
        if os.path.exists(pdf_file):
            print(f"\n3. Converting file: {pdf_file}")
            print(f"   Method: {'Docling (advanced)' if use_advanced else 'PyMuPDF (standard)'}")
            
            try:
                result = convert_pdf_to_markdown_with_error_handling(
                    pdf_file,
                    use_advanced=use_advanced
                )
                
                if result:
                    print(f"\n✅ Conversion successful!")
                    print(f"   Output length: {len(result)} characters")
                    print(f"\n   Preview (first 300 chars):")
                    print("   " + "-"*56)
                    preview = result[:300].replace("\n", "\n   ")
                    print(f"   {preview}")
                    if len(result) > 300:
                        print(f"   ... ({len(result)-300} more characters)")
                else:
                    print("\n❌ Conversion returned empty result")
                    
            except Exception as e:
                print(f"\n❌ Conversion failed: {e}")
        else:
            print(f"\n❌ File not found: {pdf_file}")
    
    print("\n" + "="*60)
