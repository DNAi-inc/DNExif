# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
ICO/CUR (Icon/Cursor) metadata writer

This module handles writing metadata to ICO and CUR files.
ICO/CUR files have very limited metadata support, so this writer
primarily preserves the file structure.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, List
from pathlib import Path

from dnexif.exceptions import MetadataWriteError
from dnexif.png_writer import PNGWriter
from dnexif.xmp_writer import XMPWriter


class ICOWriter:
    """
    Writer for ICO/CUR files.
    
    ICO/CUR files have very limited metadata support.
    This writer preserves the file structure but cannot store
    standard metadata in a way that can be read back.
    """
    
    def __init__(self):
        """Initialize ICO writer."""
        pass
    
    def write_ico(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write ICO/CUR file, preserving structure.
        
        Note: ICO/CUR files don't support standard metadata storage.
        This method preserves the file structure but metadata cannot
        be read back in a standard way.
        
        Args:
            file_path: Original ICO/CUR file path
            metadata: Metadata dictionary (not used, but preserved for API consistency)
            output_path: Output file path
        """
        try:
            with open(file_path, 'rb') as f:
                original_data = f.read()
            
            if len(original_data) < 6:
                raise MetadataWriteError("Invalid ICO/CUR file: too short")
            
            # Verify ICO/CUR signature
            reserved = struct.unpack('<H', original_data[0:2])[0]
            if reserved != 0:
                raise MetadataWriteError("Invalid ICO/CUR file: invalid reserved field")
            
            file_type = struct.unpack('<H', original_data[2:4])[0]
            if file_type not in (1, 2):
                raise MetadataWriteError("Invalid ICO/CUR file: invalid type")
            
            image_count = struct.unpack('<H', original_data[4:6])[0]
            entries = []
            offset = 6
            for _ in range(image_count):
                if offset + 16 > len(original_data):
                    break
                width = original_data[offset]
                height = original_data[offset + 1]
                color_palette = original_data[offset + 2]
                reserved_byte = original_data[offset + 3]
                color_planes = struct.unpack('<H', original_data[offset + 4:offset + 6])[0]
                bits_per_pixel = struct.unpack('<H', original_data[offset + 6:offset + 8])[0]
                image_size = struct.unpack('<I', original_data[offset + 8:offset + 12])[0]
                image_offset = struct.unpack('<I', original_data[offset + 12:offset + 16])[0]
                image_data = original_data[image_offset:image_offset + image_size]
                entries.append({
                    'width': width,
                    'height': height,
                    'color_palette': color_palette,
                    'reserved': reserved_byte,
                    'color_planes': color_planes,
                    'bits_per_pixel': bits_per_pixel,
                    'data': image_data,
                })
                offset += 16

            artist_value = metadata.get('EXIF:Artist') or metadata.get('Artist')
            png_metadata = dict(metadata)
            if artist_value and 'XMP:Creator' not in png_metadata:
                png_metadata['XMP:Creator'] = artist_value

            png_writer = PNGWriter()
            updated_entries: List[Dict[str, Any]] = []
            wrote_png_metadata = False
            for entry in entries:
                data = entry['data']
                if data.startswith(b'\x89PNG\r\n\x1a\n'):
                    chunks = png_writer._parse_png_chunks(data)
                    exif_metadata = {
                        k: v for k, v in png_metadata.items()
                        if k.startswith('EXIF:') or k.startswith('IFD0:') or k.startswith('GPS:')
                    }
                    xmp_metadata = {
                        k: v for k, v in png_metadata.items()
                        if k.startswith('XMP:')
                    }
                    png_text_metadata = {
                        k: v for k, v in png_metadata.items()
                        if k.startswith('PNG:Text:')
                    }
                    stable_diffusion_metadata = {
                        k: v for k, v in png_metadata.items()
                        if k.startswith('PNG:StableDiffusion:')
                    }
                    data = png_writer._build_png_file(
                        chunks,
                        exif_metadata,
                        xmp_metadata,
                        stable_diffusion_metadata,
                        png_text_metadata
                    )
                    wrote_png_metadata = True
                updated_entries.append({**entry, 'data': data})

            # Rebuild ICO file
            header = original_data[:6]
            dir_entries = bytearray()
            data_offset = 6 + (16 * len(updated_entries))
            data_blobs = bytearray()
            for entry in updated_entries:
                data = entry['data']
                image_size = len(data)
                dir_entries.extend(bytes([
                    entry['width'],
                    entry['height'],
                    entry['color_palette'],
                    entry['reserved'],
                ]))
                dir_entries.extend(struct.pack('<H', entry['color_planes']))
                dir_entries.extend(struct.pack('<H', entry['bits_per_pixel']))
                dir_entries.extend(struct.pack('<I', image_size))
                dir_entries.extend(struct.pack('<I', data_offset))
                data_blobs.extend(data)
                data_offset += image_size

            final_data = header + dir_entries + data_blobs
            if not wrote_png_metadata:
                xmp_metadata = {k: v for k, v in png_metadata.items() if k.startswith('XMP:')}
                if xmp_metadata:
                    xmp_packet = XMPWriter().build_xmp_packet(xmp_metadata)
                    if isinstance(xmp_packet, str):
                        xmp_packet = xmp_packet.encode('utf-8')
                    final_data += xmp_packet
            with open(output_path, 'wb') as f:
                f.write(final_data)
                
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to write ICO/CUR file: {str(e)}")
