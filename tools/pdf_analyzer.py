#!/usr/bin/env python3

"""
PDF Analyzer Tool - Convert PDF pages to images and analyze with multimodal LLM
"""

import argparse
import sys
import os
from pathlib import Path
from typing import List, Optional
import tempfile
import shutil
from PIL import Image

# Add parent directory to path to import llm_api
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from pdf2image import convert_from_path
    from pdf2image.exceptions import PDFInfoNotInstalledError
except ImportError:
    print("Error: pdf2image not installed. Install with: pip install pdf2image", file=sys.stderr)
    print("Note: You may also need poppler-utils:", file=sys.stderr)
    print("  macOS: brew install poppler", file=sys.stderr)
    print("  Ubuntu: sudo apt-get install poppler-utils", file=sys.stderr)
    sys.exit(1)

from tools.llm_api import query_llm, create_llm_client


def resize_image(image: Image.Image, max_width: Optional[int] = None, max_height: Optional[int] = None, quality: int = 85) -> Image.Image:
    """
    Resize image to reduce file size while maintaining aspect ratio.
    
    Args:
        image: PIL Image object
        max_width: Maximum width in pixels (None = no limit)
        max_height: Maximum height in pixels (None = no limit)
        quality: JPEG quality (1-100, only used if format is JPEG)
        
    Returns:
        Resized PIL Image
    """
    if max_width is None and max_height is None:
        return image
    
    original_width, original_height = image.size
    new_width, new_height = original_width, original_height
    
    # Calculate new dimensions maintaining aspect ratio
    if max_width and original_width > max_width:
        ratio = max_width / original_width
        new_width = max_width
        new_height = int(original_height * ratio)
    
    if max_height and new_height > max_height:
        ratio = max_height / new_height
        new_height = max_height
        new_width = int(new_width * ratio)
    
    if (new_width, new_height) != (original_width, original_height):
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    return image


def pdf_to_images(
    pdf_path: str, 
    dpi: int = 200, 
    output_dir: Optional[str] = None,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    compress: bool = True
) -> List[str]:
    """
    Convert PDF pages to images with optional resizing and compression.
    
    Args:
        pdf_path: Path to the PDF file
        dpi: Resolution for image conversion (default: 200)
        output_dir: Directory to save images (default: temporary directory)
        max_width: Maximum width in pixels for resizing (None = no limit)
        max_height: Maximum height in pixels for resizing (None = no limit)
        compress: Whether to compress images to reduce file size
        
    Returns:
        List of image file paths
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    # Create output directory
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = Path(tempfile.mkdtemp(prefix="pdf_images_"))
    
    print(f"Converting PDF to images (DPI: {dpi})...", file=sys.stderr)
    if max_width or max_height:
        print(f"Resizing to max: {max_width or 'auto'}x{max_height or 'auto'} pixels", file=sys.stderr)
    print(f"Output directory: {output_dir}", file=sys.stderr)
    
    try:
        # Convert PDF to images
        images = convert_from_path(str(pdf_path), dpi=dpi)
        
        image_paths = []
        for i, image in enumerate(images, start=1):
            # Resize if needed
            if max_width or max_height:
                original_size = image.size
                image = resize_image(image, max_width=max_width, max_height=max_height)
                new_size = image.size
                if original_size != new_size:
                    print(f"  Page {i}: Resized from {original_size} to {new_size}", file=sys.stderr)
            
            # Save image
            image_path = output_dir / f"page_{i:03d}.png"
            
            # Compress if requested (convert to JPEG for better compression)
            if compress and (max_width or max_height):
                # Use JPEG for better compression when resized
                jpeg_path = output_dir / f"page_{i:03d}.jpg"
                image = image.convert('RGB')  # Convert to RGB for JPEG
                image.save(jpeg_path, "JPEG", quality=85, optimize=True)
                image_paths.append(str(jpeg_path))
                
                # Get file sizes for comparison
                original_size_kb = os.path.getsize(image_path) / 1024 if image_path.exists() else 0
                compressed_size_kb = os.path.getsize(jpeg_path) / 1024
                if original_size_kb > 0:
                    reduction = (1 - compressed_size_kb / original_size_kb) * 100
                    print(f"  Page {i}: Compressed to {compressed_size_kb:.1f}KB ({reduction:.1f}% reduction)", file=sys.stderr)
            else:
                # Save as PNG
                image.save(image_path, "PNG", optimize=True)
                image_paths.append(str(image_path))
            
            file_size_kb = os.path.getsize(image_paths[-1]) / 1024
            print(f"Saved page {i}/{len(images)}: {image_paths[-1]} ({file_size_kb:.1f}KB)", file=sys.stderr)
        
        return image_paths
    
    except PDFInfoNotInstalledError:
        error_msg = """
Error: poppler-utils is not installed or not in PATH.

To install poppler:
  macOS:   brew install poppler
  Ubuntu:  sudo apt-get install poppler-utils
  Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases

After installation, make sure poppler binaries are in your PATH.
You can verify by running: pdftoppm -h
"""
        print(error_msg, file=sys.stderr)
        raise
    
    except Exception as e:
        print(f"Error converting PDF to images: {e}", file=sys.stderr)
        raise


def analyze_pdf_with_llm(
    pdf_path: str,
    prompt: str,
    provider: str = "openai",
    model: Optional[str] = None,
    dpi: int = 200,
    keep_images: bool = False,
    output_dir: Optional[str] = None,
    auto_organize: bool = True,
    max_width: Optional[int] = 800,  # Default: cost-optimized (800px)
    max_height: Optional[int] = None,
    compress: bool = True,
    summary_language: str = "zh"  # Default: Chinese (zh)
) -> tuple[str, str]:
    """
    Convert PDF to images and analyze with multimodal LLM.
    
    Args:
        pdf_path: Path to the PDF file
        prompt: Prompt to send to LLM for analysis
        provider: LLM provider (openai, anthropic, gemini, etc.)
        model: Specific model to use (optional)
        dpi: Resolution for image conversion
        keep_images: Whether to keep converted images after analysis
        output_dir: Directory to save images (optional, if None and auto_organize=True, creates organized structure)
        auto_organize: Whether to automatically organize output in structured directories
        
    Returns:
        Tuple of (combined analysis result, output directory path)
    """
    pdf_path_obj = Path(pdf_path)
    pdf_name = pdf_path_obj.stem  # Get filename without extension
    
    # Auto-organize output directory structure
    if auto_organize and output_dir is None:
        # Create organized structure: output/pdf_analysis/<pdf_name>/
        base_output = Path("output") / "pdf_analysis" / pdf_name
        base_output.mkdir(parents=True, exist_ok=True)
        # Images go in a subdirectory
        images_dir = base_output / "images"
        images_dir.mkdir(exist_ok=True)
        output_dir = str(images_dir)
        print(f"Organizing output in: {base_output}", file=sys.stderr)
    elif output_dir:
        # User specified output_dir, use as-is but ensure it exists
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        if auto_organize:
            # Still organize within user-specified directory
            base_output = output_dir_path
        else:
            base_output = output_dir_path
    
    # Convert PDF to images with optional resizing
    image_paths = pdf_to_images(
        pdf_path, 
        dpi=dpi, 
        output_dir=output_dir,
        max_width=max_width,
        max_height=max_height,
        compress=compress
    )
    
    if not image_paths:
        return "Error: No pages found in PDF"
    
    print(f"\nAnalyzing {len(image_paths)} pages with {provider}...", file=sys.stderr)
    
    # Create LLM client
    client = create_llm_client(provider)
    
    # Analyze each page
    results = []
    for i, image_path in enumerate(image_paths, start=1):
        print(f"\nAnalyzing page {i}/{len(image_paths)}...", file=sys.stderr)
        
        # Create page-specific prompt
        page_prompt = f"{prompt}\n\nThis is page {i} of {len(image_paths)}."
        
        # Query LLM with image
        response = query_llm(
            prompt=page_prompt,
            client=client,
            model=model,
            provider=provider,
            image_path=image_path
        )
        
        if response:
            # Format as Markdown
            results.append(f"## Page {i}\n\n{response}\n")
        else:
            results.append(f"## Page {i}\n\n❌ Error: Failed to get response from LLM\n")
    
    # Combine results with Markdown formatting
    page_analysis_section = "## Page-by-Page Analysis\n\n" + "\n".join(results)
    
    # Optionally, create a summary of all pages
    summary = None
    if len(image_paths) > 1:
        print("\nCreating summary of all pages...", file=sys.stderr)
        
        # Set language for summary
        if summary_language == "zh" or summary_language == "chinese":
            lang_instruction = "请使用中文（繁体）撰写摘要。"
            section_titles = {
                "main_topics": "## 主要主题",
                "key_points": "## 关键要点",
                "structure": "## 整体结构",
                "conclusions": "## 重要结论"
            }
            section_descriptions = {
                "main_topics": "主要主题和核心内容",
                "key_points": "关键要点和发现",
                "structure": "整体结构和流程",
                "conclusions": "重要结论或建议"
            }
        else:
            lang_instruction = "Please write the summary in English."
            section_titles = {
                "main_topics": "## Main Topics and Themes",
                "key_points": "## Key Points and Findings",
                "structure": "## Overall Structure and Flow",
                "conclusions": "## Important Conclusions or Recommendations"
            }
            section_descriptions = {
                "main_topics": "Main topics and themes",
                "key_points": "Key points and findings",
                "structure": "Overall structure and flow",
                "conclusions": "Important conclusions or recommendations"
            }
        
        summary_prompt = f"""Please provide a comprehensive summary of this PDF presentation based on the following page-by-page analysis:

{page_analysis_section}

{lang_instruction}

Please summarize in Markdown format (do NOT include a main title, start directly with sections):
1. {section_titles['main_topics']} - {section_descriptions['main_topics']}
2. {section_titles['key_points']} - {section_descriptions['key_points']}
3. {section_titles['structure']} - {section_descriptions['structure']}
4. {section_titles['conclusions']} - {section_descriptions['conclusions']}

Use proper Markdown formatting with ## headers for sections, lists, and emphasis. Start with "{section_titles['main_topics']}" (do not add a main # title). All section titles must be in {summary_language.upper()} language.
"""
        summary = query_llm(
            prompt=summary_prompt,
            client=client,
            model=model,
            provider=provider
        )
        if summary:
            # Format combined result as Markdown with language-appropriate title
            if summary_language == "zh" or summary_language == "chinese":
                title = "# PDF 分析摘要"
            else:
                title = "# PDF Analysis Summary"
            combined_result = f"{title}\n\n{summary}\n\n---\n\n{page_analysis_section}"
        else:
            if summary_language == "zh" or summary_language == "chinese":
                title = "# PDF 分析"
            else:
                title = "# PDF Analysis"
            combined_result = f"{title}\n\n{page_analysis_section}"
    else:
        # Single page, no summary needed
        combined_result = f"# PDF Analysis\n\n{page_analysis_section}"
    
    # Determine output directory for saving results
    if auto_organize:
        if output_dir and Path(output_dir).name == "images":
            # Images are in a subdirectory, use parent as base
            base_output = Path(output_dir).parent
        elif output_dir:
            base_output = Path(output_dir)
        else:
            # Auto-organized structure
            base_output = Path("output") / "pdf_analysis" / pdf_name
    else:
        # Not auto-organizing, use output_dir or default
        base_output = Path(output_dir) if output_dir else Path("output")
    
    # Save analysis results as Markdown
    analysis_file = base_output / "analysis.md"
    with open(analysis_file, 'w', encoding='utf-8') as f:
        f.write(combined_result)
    print(f"\nAnalysis saved to: {analysis_file}", file=sys.stderr)
    
    # Save summary separately if available (as Markdown)
    if summary:
        summary_file = base_output / "summary.md"
        # Clean up summary: remove duplicate titles and ensure proper formatting
        summary_clean = summary.strip()
        # Remove common duplicate title patterns (both English and Chinese)
        summary_clean = summary_clean.replace('# Summary of the PDF Presentation', '')
        summary_clean = summary_clean.replace('# PDF Analysis Summary', '')
        summary_clean = summary_clean.replace('# PDF 分析摘要', '')
        summary_clean = summary_clean.strip()
        # Ensure it starts with proper header based on language
        if summary_language == "zh" or summary_language == "chinese":
            title = "# PDF 分析摘要"
        else:
            title = "# PDF Analysis Summary"
        
        if not summary_clean.startswith('#'):
            summary_content = f"{title}\n\n{summary_clean}"
        elif summary_clean.startswith('##'):
            # Starts with section header, add main title
            summary_content = f"{title}\n\n{summary_clean}"
        else:
            # Already has main title, use as-is
            summary_content = summary_clean
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(summary_content)
        print(f"Summary saved to: {summary_file}", file=sys.stderr)
    
    # Clean up images if not keeping them
    if not keep_images and output_dir:
        output_path = Path(output_dir)
        if output_path.exists() and output_path.is_dir() and "pdf_images_" in str(output_path):
            print(f"Cleaning up temporary images...", file=sys.stderr)
            shutil.rmtree(output_path)
    
    return combined_result, str(base_output)


def main():
    parser = argparse.ArgumentParser(
        description='Convert PDF to images and analyze with multimodal LLM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a PDF with default prompt
  venv/bin/python3 tools/pdf_analyzer.py document.pdf
  
  # Analyze with custom prompt
  venv/bin/python3 tools/pdf_analyzer.py document.pdf --prompt "What are the main points in this slide?"
  
  # Use Anthropic Claude
  venv/bin/python3 tools/pdf_analyzer.py document.pdf --provider anthropic
  
  # Keep converted images
  venv/bin/python3 tools/pdf_analyzer.py document.pdf --keep-images --output-dir ./pdf_images
  
  # Default: cost-optimized (max-width 800px, Chinese summary)
  venv/bin/python3 tools/pdf_analyzer.py document.pdf --provider openai
  
  # Use English summary instead
  venv/bin/python3 tools/pdf_analyzer.py document.pdf --summary-language en --provider openai
  
  # Higher quality (if needed)
  venv/bin/python3 tools/pdf_analyzer.py document.pdf --max-width 1536 --provider openai
  
  # Disable image resizing (highest quality, highest cost)
  venv/bin/python3 tools/pdf_analyzer.py document.pdf --max-width None --provider openai
        """
    )
    
    parser.add_argument('pdf_path', type=str, help='Path to the PDF file')
    parser.add_argument(
        '--prompt',
        type=str,
        default='Please analyze this slide/page and provide: 1) Main topic, 2) Key points, 3) Visual elements, 4) Any important details.',
        help='Prompt for LLM analysis (default: general analysis prompt)'
    )
    parser.add_argument(
        '--provider',
        choices=['openai', 'anthropic', 'gemini', 'local', 'deepseek', 'azure', 'siliconflow'],
        default='openai',
        help='LLM provider to use (default: openai)'
    )
    parser.add_argument(
        '--model',
        type=str,
        help='Specific model to use (optional, uses provider default if not specified)'
    )
    parser.add_argument(
        '--dpi',
        type=int,
        default=200,
        help='DPI for image conversion (default: 200, higher = better quality but larger files)'
    )
    parser.add_argument(
        '--max-width',
        type=int,
        default=800,
        help='Maximum image width in pixels (default: 800, cost-optimized. Set to None to disable)'
    )
    parser.add_argument(
        '--max-height',
        type=int,
        help='Maximum image height in pixels (reduces cost and speeds up processing)'
    )
    parser.add_argument(
        '--summary-language',
        type=str,
        choices=['zh', 'en', 'chinese', 'english'],
        default='zh',
        help='Language for summary output (default: zh/Chinese)'
    )
    parser.add_argument(
        '--no-compress',
        action='store_true',
        help='Disable image compression (default: compress when resizing)'
    )
    parser.add_argument(
        '--keep-images',
        action='store_true',
        help='Keep converted images after analysis'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        help='Directory to save converted images (default: temporary directory)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output file to save analysis results (optional, auto-organized by default)'
    )
    parser.add_argument(
        '--no-auto-organize',
        action='store_true',
        help='Disable automatic directory organization'
    )
    
    args = parser.parse_args()
    
    try:
        # Analyze PDF
        result, output_base_dir = analyze_pdf_with_llm(
            pdf_path=args.pdf_path,
            prompt=args.prompt,
            provider=args.provider,
            model=args.model,
            dpi=args.dpi,
            keep_images=args.keep_images,
            output_dir=args.output_dir,
            auto_organize=not args.no_auto_organize,
            max_width=args.max_width if args.max_width is not None else 800,
            max_height=args.max_height,
            compress=not args.no_compress,
            summary_language=args.summary_language
        )
        
        # Output results
        if args.output:
            # User specified custom output file
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"\nAnalysis also saved to: {output_path}", file=sys.stderr)
        else:
            # Print to stdout
            print("\n" + "="*80)
            print(result)
            print("="*80)
            print(f"\nResults organized in: {output_base_dir}", file=sys.stderr)
    
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
