# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
ICO/CUR (Icon/Cursor) metadata parser

This module handles reading metadata from ICO and CUR files.
ICO/CUR files have limited metadata support, primarily in the file header.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class ICOParser:
    """
    Parser for ICO/CUR metadata.
    
    ICO/CUR files have very limited metadata support:
    - File header with image count
    - Image directory entries (width, height, color depth, etc.)
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize ICO/CUR parser.
        
        Args:
            file_path: Path to ICO/CUR file
            file_data: File data bytes
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
        Parse ICO/CUR metadata.
        
        Returns:
            Dictionary of ICO/CUR metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 6:
                raise MetadataReadError("Invalid ICO/CUR file: too short")
            
            metadata = {}
            
            # Check ICO/CUR signature
            reserved = struct.unpack('<H', file_data[0:2])[0]
            if reserved != 0:
                raise MetadataReadError("Invalid ICO/CUR file: invalid reserved field")
            
            # Type: 1 = ICO, 2 = CUR
            file_type = struct.unpack('<H', file_data[2:4])[0]
            if file_type == 1:
                metadata['ICO:Type'] = 'ICO'
            elif file_type == 2:
                metadata['ICO:Type'] = 'CUR'
            else:
                raise MetadataReadError("Invalid ICO/CUR file: invalid type")
            
            # Image count
            image_count = struct.unpack('<H', file_data[4:6])[0]
            metadata['ICO:ImageCount'] = image_count
            
            # Parse image directory entries
            if len(file_data) < 6 + (image_count * 16):
                return metadata
            
            images = []
            offset = 6
            first_image_width = None
            first_image_height = None
            first_image_bits_per_pixel = None
            first_image_color_planes = None
            first_image_num_colors = None
            first_image_size_bytes = None
            
            for i in range(image_count):
                if offset + 16 > len(file_data):
                    break
                
                # Parse directory entry
                width = file_data[offset]
                height = file_data[offset + 1]
                color_palette = file_data[offset + 2]
                reserved_byte = file_data[offset + 3]
                color_planes = struct.unpack('<H', file_data[offset + 4:offset + 6])[0]
                bits_per_pixel = struct.unpack('<H', file_data[offset + 6:offset + 8])[0]
                image_size = struct.unpack('<I', file_data[offset + 8:offset + 12])[0]
                image_offset = struct.unpack('<I', file_data[offset + 12:offset + 16])[0]
                
                # Handle width/height: 0 means 256
                actual_width = width if width != 0 else 256
                actual_height = height if height != 0 else 256
                
                # Calculate number of colors from color palette (if palette is used)
                # For indexed color modes, num_colors = 2^bits_per_pixel
                # For direct color modes, num_colors = 0 (not applicable)
                num_colors = 0
                if color_palette != 0 and bits_per_pixel <= 8:
                    # Indexed color mode
                    num_colors = 2 ** bits_per_pixel
                elif bits_per_pixel > 8:
                    # Direct color mode (16-bit, 24-bit, 32-bit)
                    num_colors = 0
                
                images.append({
                    'Width': actual_width,
                    'Height': actual_height,
                    'ColorPalette': color_palette,
                    'ColorPlanes': color_planes,
                    'BitsPerPixel': bits_per_pixel,
                    'ImageSize': image_size,
                    'ImageOffset': image_offset,
                    'NumColors': num_colors,
                })
                
                # Store first image properties for File tags
                if i == 0:
                    first_image_width = actual_width
                    first_image_height = actual_height
                    first_image_bits_per_pixel = bits_per_pixel
                    first_image_color_planes = color_planes
                    first_image_num_colors = num_colors
                    first_image_size_bytes = image_size
                
                offset += 16
            
            metadata['ICO:Images'] = images
            metadata['ICO:ImageCount'] = len(images)
            
            # Extract File tags from first image (Standard format shows File tags for first/largest image)
            if first_image_width is not None:
                metadata['File:ImageWidth'] = first_image_width
                metadata['File:ImageHeight'] = first_image_height
                # For ICO, standard format reports File:ImageLength as the image data size in bytes,
                # taken from the directory entry's image size field.
                # Use first image's ImageSize when available, and fall back to height if not.
                if first_image_size_bytes is not None and first_image_size_bytes > 0:
                    metadata['File:ImageLength'] = first_image_size_bytes
                else:
                    metadata['File:ImageLength'] = first_image_height
                metadata['File:ImageCount'] = len(images)
                metadata['File:ColorPlanes'] = first_image_color_planes
                metadata['File:BitsPerPixel'] = first_image_bits_per_pixel
                # standard format always reports File:NumColors, even when it is 0
                # (0 indicates that the image does not use a color palette / direct color mode).
                # Use the computed NumColors from the first image directory entry.
                if first_image_num_colors is not None:
                    metadata['File:NumColors'] = first_image_num_colors
                
                # Also set ICO-specific tags for first image
                metadata['ICO:ImageWidth'] = first_image_width
                metadata['ICO:ImageHeight'] = first_image_height
                # Do NOT calculate Composite:Megapixels here; this is handled centrally in
                # the core metadata layer so that all formats use the same logic and
                # standard precision, including tiny icons like 16x16.
            
            return metadata
            
        except Exception as e:
            raise MetadataReadError(f"Failed to parse ICO/CUR metadata: {str(e)}")

