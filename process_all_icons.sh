#!/bin/bash
# Quick script to process all icons with background removal

echo "🎨 Icon Processing Script"
echo "========================"
echo ""

# Check if rembg is installed
if ! python3 -c "import rembg" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -r requirements_icon_processor.txt
fi

# Process items grid (10x10)
if [ -f "items_grid.png" ]; then
    echo "📐 Extracting items from grid..."
    python3 extract_and_process_icons.py both \
        --grid-image items_grid.png \
        --rows 10 \
        --cols 10 \
        --prefix item \
        --output items_processed \
        --size 256
fi

# Process bestiary grid (mobs and bosses)
if [ -f "bestiary_grid.png" ]; then
    echo "📐 Extracting mobs/bosses from grid..."
    python3 extract_and_process_icons.py both \
        --grid-image bestiary_grid.png \
        --rows 8 \
        --cols 8 \
        --prefix mob \
        --output mobs_processed \
        --size 256
fi

# Process individual icon folders if they exist
if [ -d "raw_items" ]; then
    echo "🎨 Processing raw items..."
    python3 extract_and_process_icons.py process \
        --input raw_items \
        --output items_processed \
        --size 256
fi

if [ -d "raw_mobs" ]; then
    echo "🎨 Processing raw mobs..."
    python3 extract_and_process_icons.py process \
        --input raw_mobs \
        --output mobs_processed \
        --size 256
fi

echo ""
echo "✅ All processing complete!"
echo "📁 Check the *_processed folders for your final icons"
