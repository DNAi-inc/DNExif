# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
XWD (X Windows Dump) image metadata parser

This module handles reading metadata from XWD files.
XWD files are used to dump X Window System windows to files.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class XWDParser:
    """
    Parser for XWD (X Windows Dump) metadata.
    
    XWD files have a header structure:
    - Header size (4 bytes)
    - File version (4 bytes)
    - Pixmap format (4 bytes)
    - Pixmap depth (4 bytes)
    - Pixmap width (4 bytes)
    - Pixmap height (4 bytes)
    - X offset (4 bytes)
    - Byte order (4 bytes)
    - Bitmap unit (4 bytes)
    - Bitmap bit order (4 bytes)
    - Bitmap pad (4 bytes)
    - Bits per pixel (4 bytes)
    - Bytes per line (4 bytes)
    - Visual class (4 bytes)
    - Red mask (4 bytes)
    - Green mask (4 bytes)
    - Blue mask (4 bytes)
    - Bits per RGB (4 bytes)
    - Colormap entries (4 bytes)
    - Number of colors (4 bytes)
    - Window width (4 bytes)
    - Window height (4 bytes)
    - Window X (4 bytes)
    - Window Y (4 bytes)
    - Window border width (4 bytes)
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize XWD parser.
        
        Args:
            file_path: Path to XWD file
            file_data: XWD file data bytes
        """
        if file_path:
            self.file_path = Path(file_path)
            self.file_data = None
        elif file_data:
            self.file_data = file_data
            self.file_path = None
        else:
            raise ValueError("Either file_path or file_data must be provided")
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse XWD metadata.
        
        Returns:
            Dictionary of XWD metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 100:
                raise MetadataReadError("Invalid XWD file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'XWD'
            metadata['File:FileTypeExtension'] = 'xwd'
            metadata['File:MIMEType'] = 'image/x-xwindowdump'
            
            # Parse header (all 4-byte integers, byte order depends on file)
            # Try both byte orders
            try:
                # Try big-endian first (X11 default)
                header_size = struct.unpack('>I', file_data[0:4])[0]
                if header_size < 100 or header_size > 10000:
                    # Try little-endian
                    header_size = struct.unpack('<I', file_data[0:4])[0]
                    byte_order = '<'
                else:
                    byte_order = '>'
            except:
                byte_order = '>'
            
            if byte_order == '>':
                unpack = lambda data: struct.unpack('>I', data)[0]
            else:
                unpack = lambda data: struct.unpack('<I', data)[0]
            
            file_version = unpack(file_data[4:8])
            pixmap_format = unpack(file_data[8:12])
            pixmap_depth = unpack(file_data[12:16])
            pixmap_width = unpack(file_data[16:20])
            pixmap_height = unpack(file_data[20:24])
            x_offset = unpack(file_data[24:28])
            byte_order_val = unpack(file_data[28:32])
            bitmap_unit = unpack(file_data[32:36])
            bitmap_bit_order = unpack(file_data[36:40])
            bitmap_pad = unpack(file_data[40:44])
            bits_per_pixel = unpack(file_data[44:48])
            bytes_per_line = unpack(file_data[48:52])
            visual_class = unpack(file_data[52:56])
            red_mask = unpack(file_data[56:60])
            green_mask = unpack(file_data[60:64])
            blue_mask = unpack(file_data[64:68])
            bits_per_rgb = unpack(file_data[68:72])
            colormap_entries = unpack(file_data[72:76])
            number_of_colors = unpack(file_data[76:80])
            window_width = unpack(file_data[80:84])
            window_height = unpack(file_data[84:88])
            window_x = unpack(file_data[88:92])
            window_y = unpack(file_data[92:96])
            window_border_width = unpack(file_data[96:100])
            
            metadata['XWD:HeaderSize'] = header_size
            metadata['XWD:FileVersion'] = file_version
            metadata['XWD:PixmapFormat'] = pixmap_format
            metadata['XWD:PixmapDepth'] = pixmap_depth
            metadata['XWD:PixmapWidth'] = pixmap_width
            metadata['XWD:PixmapHeight'] = pixmap_height
            metadata['XWD:XOffset'] = x_offset
            metadata['XWD:ByteOrder'] = 'Big-endian' if byte_order_val == 0 else 'Little-endian'
            metadata['XWD:BitmapUnit'] = bitmap_unit
            metadata['XWD:BitmapBitOrder'] = bitmap_bit_order
            metadata['XWD:BitmapPad'] = bitmap_pad
            metadata['XWD:BitsPerPixel'] = bits_per_pixel
            metadata['XWD:BytesPerLine'] = bytes_per_line
            metadata['XWD:VisualClass'] = visual_class
            metadata['XWD:RedMask'] = hex(red_mask)
            metadata['XWD:GreenMask'] = hex(green_mask)
            metadata['XWD:BlueMask'] = hex(blue_mask)
            metadata['XWD:BitsPerRGB'] = bits_per_rgb
            metadata['XWD:ColormapEntries'] = colormap_entries
            metadata['XWD:NumberOfColors'] = number_of_colors
            metadata['XWD:WindowWidth'] = window_width
            metadata['XWD:WindowHeight'] = window_height
            metadata['XWD:WindowX'] = window_x
            metadata['XWD:WindowY'] = window_y
            metadata['XWD:WindowBorderWidth'] = window_border_width
            
            metadata['File:ImageWidth'] = pixmap_width
            metadata['File:ImageHeight'] = pixmap_height
            metadata['File:BitsPerPixel'] = bits_per_pixel
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse XWD metadata: {str(e)}")

