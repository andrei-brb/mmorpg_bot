# Icon Display Issue - Notes

## Problem
Icons are showing as "black hearts" (🖤 emoji) instead of PNG images.

## Root Cause
Discord's `edit_message` API doesn't support adding new file attachments. When you click on an item in the inventory, it edits the existing message, so the PNG file can't be attached.

## Current Status
- ✅ PNG files are in `assets/items/` directory
- ✅ Icon helper functions are working
- ✅ Files are being found correctly
- ❌ Files can't be attached when editing messages

## Solution Options

### Option 1: Send New Message for Item Details (Recommended)
When clicking an item, send a followup message instead of editing. This allows attaching the PNG file.

### Option 2: Use Image Hosting/CDN
Host PNG files on a CDN and use URLs instead of file attachments.

### Option 3: Accept Limitation
Icons only show on initial inventory load, not when clicking items.

## Next Steps
The code has been updated to handle file attachments correctly. However, Discord's limitation means icons will only show when:
- Sending a NEW message (initial inventory load)
- NOT when editing an existing message (clicking items)

To fully fix this, we'd need to either:
1. Send followup messages for item details instead of editing
2. Or use a hosted image solution
