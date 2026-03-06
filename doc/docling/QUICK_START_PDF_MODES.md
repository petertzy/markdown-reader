Quick Start - PDF Conversion Modes

GETTING STARTED IN 2 MINUTES
=============================

1. INSTALLATION
   
   Basic setup (PyMuPDF only):
   $ python3 -m venv venv
   $ source venv/bin/activate  # on Windows: venv\Scripts\activate
   $ pip install -r requirements.txt
   
   Advanced setup (with Docling):
   $ pip install docling

2. LAUNCHING THE APP
   
   $ python app.py


3. CONVERTING A PDF
   
   Method 1: Open in current version (PyMuPDF)
   - File > Open File
   - Select your PDF
   - PDF automatically converts to Markdown
   
   Method 2: Open with Docling (Advanced)
   - Tools > Use Advanced PDF Conversion (Docling) [enable checkbox]
   - File > Open File
   - Select your PDF
   - PDF converts using Docling (intelligent conversion)


QUICK COMPARISON
================

Need speed?                    → Use PyMuPDF (default)
Need quality?                  → Enable Docling mode
Processing scientific paper?   → Enable Docling mode
Processing simple report?      → Use PyMuPDF (fast & sufficient)
First time using?              → Start with PyMuPDF


CHECKING STATUS
===============

Want to see which converter is active?
  Tools > PDF Converter Info
  
Shows:
- Available converters
- Current active mode
- Recommended use cases


TROUBLESHOOTING
===============

"Docling not installed" message?
  $ pip install docling

Docling too slow?
  This is normal on first use. Models are cached after first run.

Want to switch converters?
  Tools > Use Advanced PDF Conversion (Docling)
  Toggle checkbox to switch


SWITCHING BETWEEN MODES
=======================

At any time you can:

1. Click Tools menu
2. Click "Use Advanced PDF Conversion (Docling)"
3. Checkbox appears next to the option
   [✓] = Docling enabled (advanced mode)
   [ ] = PyMuPDF enabled (fast mode)
4. Open your next PDF - it will use the selected mode


NEXT STEPS
==========

1. Open a PDF to test both converters
2. Compare results for your specific use case
3. Choose the default mode that works best for you
4. See PDF_CONVERSION_MODES.md for detailed information


COMMON SCENARIOS
================

Scenario 1: Processing a technical paper with equations
  1. Enable Docling: Tools > Use Advanced PDF Conversion (Docling)
  2. Open the PDF file
  3. Result: Equations and formatting preserved well

Scenario 2: Processing your research notes (text only)
  1. Keep default PyMuPDF mode
  2. Open the PDF file
  3. Result: Fast conversion, complete content

Scenario 3: Testing both modes on same document
  1. Open PDF with PyMuPDF (default mode)
  2. Save the result
  3. Enable Docling mode
  4. Open same PDF again
  5. Compare results side by side
  6. Choose preferred result


TIPS
====

✓ Docling first-time users: First run takes 2-5 seconds (models loading)
✓ After that, Docling runs faster (models cached)
✓ Switch modes anytime - no restart needed
✓ Both converters handle images (different quality)
✓ Tables work better with Docling
✓ Simple text works fine with PyMuPDF


SYSTEM REQUIREMENTS
===================

Minimum (PyMuPDF only):
- Python 3.9+
- 1GB RAM
- 200MB disk space

Recommended (with Docling support):
- Python 3.12+
- 2GB+ RAM
- 500MB disk space (models)


ADVANCED USAGE
==============

Command line PDF test:
  $ source venv/bin/activate
  $ python docling_integration.py your_file.pdf --advanced

Check converter availability:
  $ python -c "from docling.document_converter import DocumentConverter; print('Docling available')"


DOCUMENTATION
==============

For more details:
- PDF_CONVERSION_MODES.md - Complete feature documentation
- README_DOCLING_TEST.md - Detailed evaluation report
- docling_integration.py - Source code examples


SUPPORT
=======

Issue: PDF conversion not working?
  1. Check error message
  2. Ensure PDF file is valid
  3. Try switching converters
  4. Check Tools > PDF Converter Info

Issue: Docling not found?
  1. Install: pip install docling
  2. Verify: python -c "import docling; print('OK')"
  3. Restart application

Issue: Memory problems?
  1. Close other applications
  2. Switch to PyMuPDF mode (less memory)
  3. Process files one at a time


VERSION
=======

Feature introduced: Version 2.0.0
Last updated: 2026-03-06
Python minimum: 3.12 (for Docling: 3.10+)
PyMuPDF: 1.27.1
Docling: 2.76.0 (optional)
