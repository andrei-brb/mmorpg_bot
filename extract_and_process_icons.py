#!/usr/bin/env python3
"""
Extract icons from grid images and process them with AI background removal.
Handles both bestiary grids and item grids.
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple, Optional
import argparse

try:
    from PIL import Image
    import cv2
    import numpy as np
except ImportError:
    print("❌ Missing required packages. Installing...")
    os.system("pip install pillow opencv-python numpy")
    from PIL import Image
    import cv2
    import numpy as np

REMBG_AVAILABLE = False
def _check_rembg():
    """Lazy import of rembg to avoid import errors."""
    global REMBG_AVAILABLE
    if REMBG_AVAILABLE:
        return True
    try:
        from rembg import remove
        globals()['remove'] = remove
        REMBG_AVAILABLE = True
        return True
    except Exception:
        REMBG_AVAILABLE = False
        return False


class GridIconExtractor:
    """Extract individual icons from a grid image."""
    
    def __init__(self, grid_image_path: Path, rows: int, cols: int, 
                 start_row: int = 0, start_col: int = 0,
                 skip_header_row: bool = True, skip_header_col: bool = True):
        self.grid_image_path = Path(grid_image_path)
        self.rows = rows
        self.cols = cols
        self.start_row = start_row
        self.start_col = start_col
        self.skip_header_row = skip_header_row
        self.skip_header_col = skip_header_col
        
    def extract_icons(self, output_dir: Path, prefix: str = "icon") -> List[Path]:
        """Extract all icons from the grid."""
        img = Image.open(self.grid_image_path)
        width, height = img.size
        
        # Calculate cell dimensions
        cell_width = width // self.cols
        cell_height = height // self.rows
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        extracted_files = []
        count = 0
        
        start_r = 1 if self.skip_header_row else 0
        start_c = 1 if self.skip_header_col else 0
        
        for row in range(start_r, self.rows):
            for col in range(start_c, self.cols):
                # Calculate crop box
                x1 = col * cell_width
                y1 = row * cell_height
                x2 = x1 + cell_width
                y2 = y1 + cell_height
                
                # Extract cell
                cell = img.crop((x1, y1, x2, y2))
                
                # Save
                filename = f"{prefix}_{row}_{col}.png"
                output_path = output_dir / filename
                cell.save(output_path, 'PNG')
                extracted_files.append(output_path)
                count += 1
        
        print(f"✅ Extracted {count} icons from grid")
        return extracted_files


class IconProcessor:
    """Process icons with AI background removal and auto-cropping."""
    
    def __init__(self, output_size: int = 256, padding: int = 10, remove_bg: bool = True):
        self.output_size = output_size
        self.padding = padding
        self.remove_bg = remove_bg and _check_rembg()
        
    def auto_detect_bounds(self, image: Image.Image) -> Tuple[int, int, int, int]:
        """Auto-detect content boundaries."""
        img_array = np.array(image.convert('RGB'))
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return (0, 0, image.width, image.height)
        
        x_min = min(c[0][0][0] for c in contours)
        y_min = min(c[0][0][1] for c in contours)
        x_max = max(c[0][0][0] for c in contours)
        y_max = max(c[0][0][1] for c in contours)
        
        x_min = max(0, x_min - self.padding)
        y_min = max(0, y_min - self.padding)
        x_max = min(image.width, x_max + self.padding)
        y_max = min(image.height, y_max + self.padding)
        
        return (x_min, y_min, x_max, y_max)
    
    def remove_background_ai(self, image: Image.Image) -> Image.Image:
        """Remove background using AI."""
        if not _check_rembg():
            return image
        
        try:
            from rembg import remove
            # Convert to RGB if needed
            if image.mode != 'RGB':
                rgb_image = image.convert('RGB')
            else:
                rgb_image = image
            
            # Save to bytes buffer
            from io import BytesIO
            buffer = BytesIO()
            rgb_image.save(buffer, format='PNG')
            buffer.seek(0)
            
            # Remove background
            output_bytes = remove(buffer.read())
            
            # Convert back to PIL
            output_img = Image.open(BytesIO(output_bytes))
            return output_img.convert('RGBA')
        except Exception as e:
            print(f"   ⚠️  Background removal failed: {e}")
            return image.convert('RGBA')
    
    def crop_to_content(self, image: Image.Image) -> Image.Image:
        """Crop to content bounds."""
        bounds = self.auto_detect_bounds(image)
        x_min, y_min, x_max, y_max = bounds
        return image.crop((x_min, y_min, x_max, y_max))
    
    def resize_to_square(self, image: Image.Image) -> Image.Image:
        """Resize to square maintaining aspect ratio."""
        width, height = image.size
        max_dim = max(width, height)
        scale = self.output_size / max_dim
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (self.output_size, self.output_size), (0, 0, 0, 0))
        
        x_offset = (self.output_size - new_width) // 2
        y_offset = (self.output_size - new_height) // 2
        canvas.paste(resized, (x_offset, y_offset), resized if resized.mode == 'RGBA' else None)
        
        return canvas
    
    def process_image(self, input_path: Path, output_path: Path) -> bool:
        """Process a single image."""
        try:
            image = Image.open(input_path).convert('RGBA')
            original_size = image.size
            
            # Remove background
            if self.remove_bg:
                print(f"   🎨 Removing background from {input_path.name}...")
                image = self.remove_background_ai(image)
            
            # Crop to content
            image = self.crop_to_content(image)
            
            # Resize to square
            image = self.resize_to_square(image)
            
            # Save
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path, 'PNG', optimize=True)
            
            print(f"   ✅ {input_path.name} ({original_size[0]}x{original_size[1]} → {self.output_size}x{self.output_size})")
            return True
            
        except Exception as e:
            print(f"   ❌ Error processing {input_path.name}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def process_folder(self, input_dir: Path, output_dir: Path):
        """Process all images in folder."""
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        
        image_files = list(input_dir.glob("*.png"))
        image_files.extend(input_dir.glob("*.jpg"))
        image_files.extend(input_dir.glob("*.jpeg"))
        image_files.extend(input_dir.glob("*.webp"))
        
        if not image_files:
            print(f"❌ No images found in {input_dir}")
            return
        
        print(f"\n📦 Processing {len(image_files)} images...")
        print(f"   Input:  {input_dir}")
        print(f"   Output: {output_dir}")
        print(f"   Size:   {self.output_size}x{self.output_size}")
        print(f"   BG Removal: {'✅ Enabled' if self.remove_bg else '❌ Disabled'}\n")
        
        success_count = 0
        for img_path in image_files:
            output_path = output_dir / img_path.name
            if self.process_image(img_path, output_path):
                success_count += 1
        
        print(f"\n✨ Processed {success_count}/{len(image_files)} images successfully!")


def main():
    parser = argparse.ArgumentParser(description='Extract and process icons from grid images')
    parser.add_argument('action', choices=['extract', 'process', 'both'], 
                       help='Action to perform: extract from grid, process existing icons, or both')
    
    # Grid extraction options
    parser.add_argument('--grid-image', type=str, help='Path to grid image (for extract action)')
    parser.add_argument('--rows', type=int, help='Number of rows in grid')
    parser.add_argument('--cols', type=int, help='Number of columns in grid')
    parser.add_argument('--prefix', type=str, default='icon', help='Prefix for extracted icons')
    
    # Processing options
    parser.add_argument('--input', '-i', type=str, help='Input directory with icons')
    parser.add_argument('--output', '-o', type=str, default='processed_icons', help='Output directory')
    parser.add_argument('--size', '-s', type=int, default=256, help='Output icon size')
    parser.add_argument('--no-bg-remove', action='store_true', help='Disable background removal')
    
    args = parser.parse_args()
    
    if args.action in ['extract', 'both']:
        if not args.grid_image:
            print("❌ --grid-image required for extract action")
            return
        
        print(f"\n📐 Extracting icons from grid: {args.grid_image}")
        extractor = GridIconExtractor(
            args.grid_image, 
            args.rows or 10, 
            args.cols or 10
        )
        
        extract_dir = Path(args.output) / 'extracted'
        extracted = extractor.extract_icons(extract_dir, args.prefix)
        print(f"✅ Extracted {len(extracted)} icons to {extract_dir}")
        
        # If 'both', use extracted icons as input
        if args.action == 'both':
            args.input = str(extract_dir)
    
    if args.action in ['process', 'both']:
        if not args.input:
            print("❌ --input required for process action")
            return
        
        print(f"\n🎨 Processing icons...")
        processor = IconProcessor(
            output_size=args.size,
            remove_bg=not args.no_bg_remove
        )
        
        output_dir = Path(args.output) / 'processed' if args.action == 'both' else Path(args.output)
        processor.process_folder(Path(args.input), output_dir)
        
        print(f"\n✅ All done! Processed icons in: {output_dir}")


if __name__ == '__main__':
    if len(sys.argv) == 1:
        print("""
🎨 Icon Grid Extractor & Processor

Usage Examples:

1. Extract icons from a grid image:
   python extract_and_process_icons.py extract --grid-image bestiary.png --rows 8 --cols 8 --prefix mob

2. Process existing icons:
   python extract_and_process_icons.py process --input raw_icons/ --output processed/

3. Extract AND process in one go:
   python extract_and_process_icons.py both --grid-image items.png --rows 10 --cols 10 --output final_icons/

Options:
  --grid-image    Path to grid image
  --rows          Number of rows in grid
  --cols          Number of columns in grid
  --input         Input directory (for process)
  --output        Output directory
  --size          Output icon size (default: 256)
  --no-bg-remove  Disable AI background removal
        """)
    else:
        main()
