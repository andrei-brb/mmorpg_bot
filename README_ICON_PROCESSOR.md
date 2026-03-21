# 🎨 Icon Batch Processor

AI-powered tool to automatically crop, resize, and process game icons.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements_icon_processor.txt
```

**Note:** `rembg` requires additional system dependencies on some platforms. If you encounter issues:

- **macOS:** `brew install python3`
- **Linux:** `sudo apt-get install python3-dev`
- **Windows:** Usually works out of the box

### 2. Prepare Your Icons

Place all your raw icon images in a folder (e.g., `raw_icons/`). Supported formats:
- PNG
- JPG/JPEG
- WebP

### 3. Run the Processor

**Basic usage:**
```bash
python process_icons.py raw_icons/
```

**With custom output folder:**
```bash
python process_icons.py raw_icons/ --output processed_icons/
```

**Custom size (512x512):**
```bash
python process_icons.py raw_icons/ --size 512
```

**Disable background removal:**
```bash
python process_icons.py raw_icons/ --no-bg-remove
```

**Auto-organize into items/mobs/bosses folders:**
```bash
python process_icons.py raw_icons/ --organize
```

## 📋 Features

✅ **Auto-cropping** - Automatically detects icon boundaries and removes excess whitespace  
✅ **AI Background Removal** - Uses `rembg` to intelligently remove backgrounds  
✅ **Square Resizing** - Resizes to consistent square dimensions while maintaining aspect ratio  
✅ **Batch Processing** - Processes entire folders at once  
✅ **Auto-Organization** - Can organize icons into items/mobs/bosses folders  

## 🎯 Example Workflow

```bash
# 1. Install dependencies
pip install -r requirements_icon_processor.txt

# 2. Process all icons
python process_icons.py raw_icons/ --output processed_icons/ --size 256

# 3. Organize by category
python process_icons.py raw_icons/ --output processed_icons/ --organize
```

## 📁 Output Structure

After processing with `--organize`:

```
processed_icons/
├── items/
│   ├── iron_sword.png
│   ├── leather_cap.png
│   └── ...
├── mobs/
│   ├── forest_wolf.png
│   ├── kobold.png
│   └── ...
└── bosses/
    ├── hogger.png
    ├── defias_ringleader.png
    └── ...
```

## ⚙️ Options

- `input_dir` - Directory containing raw icon images (required)
- `--output, -o` - Output directory (default: `processed_icons`)
- `--size, -s` - Output icon size in pixels (default: 256)
- `--no-bg-remove` - Disable AI background removal
- `--organize` - Organize icons into items/mobs/bosses folders
- `--items-list` - Path to items list file (default: `ITEM_LIST_FOR_ICONS.md`)
- `--mobs-list` - Path to mobs/bosses list file (default: `MOBS_AND_BOSSES_LIST.md`)

## 🔧 Troubleshooting

**Issue: `rembg` installation fails**
- Solution: Install system dependencies first (see above)
- Alternative: Use `--no-bg-remove` to skip background removal

**Issue: Icons are cropped incorrectly**
- Solution: Adjust padding with `self.padding` in the script (line 30)
- Or manually crop before processing

**Issue: Background removal is slow**
- Solution: This is normal - AI processing takes time
- Consider processing in smaller batches

## 💡 Tips

1. **Test on a few icons first** before processing hundreds
2. **Keep originals** - the script doesn't modify source files
3. **Use consistent naming** - helps with auto-organization
4. **256x256 is standard** for game icons, but 512x512 works too
