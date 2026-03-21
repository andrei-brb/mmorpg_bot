#!/usr/bin/env python3
"""
AI-Powered Icon Batch Processor
Automatically crops, removes backgrounds, and organizes game icons.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Tuple
import argparse

try:
    from PIL import Image, ImageChops
    import cv2
    import numpy as np
except ImportError:
    print("❌ Missing required packages. Installing...")
    os.system("pip install pillow opencv-python numpy")
    from PIL import Image, ImageChops
    import cv2
    import numpy as np

try:
    from rembg import remove
    REMBG_AVAILABLE = True
except ImportError:
    print("⚠️  rembg not installed. Background removal will be disabled.")
    print("   Install with: pip install rembg")
    REMBG_AVAILABLE = False


class IconProcessor:
    """AI-powered icon processor with auto-cropping and background removal."""
    
    def __init__(self, output_size: int = 256, padding: int = 10, remove_bg: bool = True):
        self.output_size = output_size
        self.padding = padding
        self.remove_bg = remove_bg and REMBG_AVAILABLE
        
    def auto_detect_bounds(self, image: Image.Image) -> Tuple[int, int, int, int]:
        """
        Automatically detect the bounding box of the icon content.
        Uses edge detection and contour finding.
        """
        # Convert to numpy array
        img_array = np.array(image.convert('RGB'))
        
        # Convert to grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Apply threshold to get binary image
        _, thresh = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            # Fallback: return full image bounds
            return (0, 0, image.width, image.height)
        
        # Get bounding box of all contours
        x_min = min(c[0][0][0] for c in contours)
        y_min = min(c[0][0][1] for c in contours)
        x_max = max(c[0][0][0] for c in contours)
        y_max = max(c[0][0][1] for c in contours)
        
        # Add padding
        x_min = max(0, x_min - self.padding)
        y_min = max(0, y_min - self.padding)
        x_max = min(image.width, x_max + self.padding)
        y_max = min(image.height, y_max + self.padding)
        
        return (x_min, y_min, x_max, y_max)
    
    def remove_background_ai(self, image: Image.Image) -> Image.Image:
        """Remove background using AI (rembg)."""
        if not REMBG_AVAILABLE:
            return image
        
        try:
            # Convert PIL to bytes
            img_bytes = image.tobytes()
            
            # Remove background
            output_bytes = remove(img_bytes)
            
            # Convert back to PIL Image
            output_img = Image.frombytes('RGBA', image.size, output_bytes)
            
            return output_img
        except Exception as e:
            print(f"   ⚠️  Background removal failed: {e}")
            return image
    
    def crop_to_content(self, image: Image.Image) -> Image.Image:
        """Crop image to content bounds, removing excess whitespace."""
        # Auto-detect bounds
        bounds = self.auto_detect_bounds(image)
        x_min, y_min, x_max, y_max = bounds
        
        # Crop to bounds
        cropped = image.crop((x_min, y_min, x_max, y_max))
        
        return cropped
    
    def resize_to_square(self, image: Image.Image, size: Optional[int] = None) -> Image.Image:
        """Resize image to square while maintaining aspect ratio."""
        if size is None:
            size = self.output_size
        
        # Calculate new size maintaining aspect ratio
        width, height = image.size
        max_dim = max(width, height)
        
        # Scale to fit in square
        scale = size / max_dim
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        # Resize
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create square canvas with transparent background
        canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        
        # Center the image
        x_offset = (size - new_width) // 2
        y_offset = (size - new_height) // 2
        canvas.paste(resized, (x_offset, y_offset), resized if resized.mode == 'RGBA' else None)
        
        return canvas
    
    def process_image(self, input_path: Path, output_path: Path) -> bool:
        """Process a single image."""
        try:
            # Load image
            image = Image.open(input_path).convert('RGBA')
            original_size = image.size
            
            # Step 1: Remove background (if enabled)
            if self.remove_bg:
                image = self.remove_background_ai(image)
            
            # Step 2: Crop to content
            image = self.crop_to_content(image)
            
            # Step 3: Resize to square
            image = self.resize_to_square(image)
            
            # Step 4: Save
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path, 'PNG', optimize=True)
            
            print(f"   ✅ {input_path.name} ({original_size[0]}x{original_size[1]} → {self.output_size}x{self.output_size})")
            return True
            
        except Exception as e:
            print(f"   ❌ Error processing {input_path.name}: {e}")
            return False
    
    def process_folder(self, input_dir: Path, output_dir: Path, pattern: str = "*.png"):
        """Process all images in a folder."""
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        
        # Find all images
        image_files = list(input_dir.glob(pattern))
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


def organize_by_category(base_dir: Path, items_file: Path, mobs_file: Path):
    """
    Organize processed icons into category folders based on the item/mob lists.
    """
    base_dir = Path(base_dir)
    items_file = Path(items_file)
    mobs_file = Path(mobs_file)
    
    # Read item names
    item_names = set()
    if items_file.exists():
        with open(items_file, 'r') as f:
            for line in f:
                if line.strip().startswith('**') or line.strip().startswith('1.'):
                    # Extract item name (remove markdown formatting)
                    name = line.strip().lstrip('*').lstrip('1234567890. ').strip()
                    if name and not name.startswith('#'):
                        item_names.add(name.lower().replace(' ', '_'))
    
    # Read mob/boss names
    mob_names = set()
    boss_names = set()
    if mobs_file.exists():
        with open(mobs_file, 'r') as f:
            content = f.read()
            # Extract regular enemies
            if '**Regular Enemies**' in content:
                section = content.split('**Regular Enemies**')[1].split('**Bosses**')[0]
                for line in section.split('\n'):
                    if line.strip().startswith(('1.', '2.', '3.', '4.', '5.')):
                        name = line.strip().lstrip('1234567890. ').strip()
                        if name:
                            mob_names.add(name.lower().replace(' ', '_'))
            # Extract bosses
            if '**Bosses**' in content:
                section = content.split('**Bosses**')[1]
                for line in section.split('\n'):
                    if line.strip().startswith(('1.', '2.', '3.', '4.', '5.')):
                        name = line.strip().lstrip('1234567890. ').strip()
                        if name:
                            boss_names.add(name.lower().replace(' ', '_'))
    
    # Create category folders
    items_dir = base_dir / 'items'
    mobs_dir = base_dir / 'mobs'
    bosses_dir = base_dir / 'bosses'
    
    items_dir.mkdir(exist_ok=True)
    mobs_dir.mkdir(exist_ok=True)
    bosses_dir.mkdir(exist_ok=True)
    
    # Move files to appropriate folders
    for img_file in base_dir.glob('*.png'):
        name_lower = img_file.stem.lower().replace(' ', '_')
        
        if name_lower in boss_names:
            img_file.rename(bosses_dir / img_file.name)
            print(f"   📁 {img_file.name} → bosses/")
        elif name_lower in mob_names:
            img_file.rename(mobs_dir / img_file.name)
            print(f"   📁 {img_file.name} → mobs/")
        elif name_lower in item_names:
            img_file.rename(items_dir / img_file.name)
            print(f"   📁 {img_file.name} → items/")


def main():
    parser = argparse.ArgumentParser(description='AI-Powered Icon Batch Processor')
    parser.add_argument('input_dir', type=str, help='Input directory with raw icons')
    parser.add_argument('--output', '-o', type=str, default='processed_icons', help='Output directory')
    parser.add_argument('--size', '-s', type=int, default=256, help='Output icon size (default: 256)')
    parser.add_argument('--no-bg-remove', action='store_true', help='Disable background removal')
    parser.add_argument('--organize', action='store_true', help='Organize icons into items/mobs/bosses folders')
    parser.add_argument('--items-list', type=str, default='ITEM_LIST_FOR_ICONS.md', help='Path to items list file')
    parser.add_argument('--mobs-list', type=str, default='MOBS_AND_BOSSES_LIST.md', help='Path to mobs/bosses list file')
    
    args = parser.parse_args()
    
    # Create processor
    processor = IconProcessor(
        output_size=args.size,
        remove_bg=not args.no_bg_remove
    )
    
    # Process images
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output)
    
    processor.process_folder(input_dir, output_dir)
    
    # Organize if requested
    if args.organize:
        print("\n📂 Organizing icons by category...")
        organize_by_category(output_dir, args.items_list, args.mobs_list)
        print("✅ Organization complete!")


if __name__ == '__main__':
    main()
