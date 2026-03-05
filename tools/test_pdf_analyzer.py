#!/usr/bin/env python3
"""
Simple test script to verify PDF analyzer dependencies
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Test if required modules can be imported"""
    print("Testing imports...")
    try:
        from pdf2image import convert_from_path
        print("✓ pdf2image imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import pdf2image: {e}")
        return False
    
    try:
        from PIL import Image
        print("✓ Pillow imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import Pillow: {e}")
        return False
    
    try:
        from tools.llm_api import query_llm, create_llm_client
        print("✓ llm_api imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import llm_api: {e}")
        return False
    
    return True

def test_poppler():
    """Test if poppler is available"""
    print("\nTesting poppler availability...")
    try:
        from pdf2image import convert_from_path
        # Try to get poppler path
        import pdf2image.pdf2image as pdf2img
        # This will raise an error if poppler is not found when actually converting
        print("✓ pdf2image module loaded")
        print("  Note: poppler will be checked when converting a PDF")
        return True
    except Exception as e:
        print(f"✗ Error checking poppler: {e}")
        return False

def test_pdf_analyzer_import():
    """Test if pdf_analyzer can be imported"""
    print("\nTesting pdf_analyzer import...")
    try:
        import tools.pdf_analyzer
        print("✓ pdf_analyzer imported successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to import pdf_analyzer: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("PDF Analyzer Dependency Test")
    print("=" * 60)
    
    all_passed = True
    
    all_passed &= test_imports()
    all_passed &= test_poppler()
    all_passed &= test_pdf_analyzer_import()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All basic tests passed!")
        print("\nNote: To fully test, you need:")
        print("  1. poppler-utils installed (brew install poppler)")
        print("  2. A PDF file to test conversion")
        print("  3. LLM API keys configured in .env file")
    else:
        print("✗ Some tests failed. Please check the errors above.")
    print("=" * 60)
    
    sys.exit(0 if all_passed else 1)
