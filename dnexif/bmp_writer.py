# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
BMP metadata writer

This module provides metadata writing for BMP files.
BMP files have limited metadata support, primarily in the file header.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any
from pathlib import Path

from dnexif.exceptions import MetadataWriteError


class BMPWriter:
    """
    Writer for BMP metadata.
    
    BMP files have very limited metadata support:
    - File header information (size, width, height, color depth)
    - Some BMP variants may support additional metadata in DIB header
    """
    
    def write_bmp(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to BMP file.
        
        Note: BMP format has very limited metadata support.
        Only basic header information can be modified.
        
        Args:
            file_path: Path to input BMP file
            metadata: Dictionary of metadata to write
            output_path: Path to output BMP file
            
        Raises:
            MetadataWriteError: If writing fails
        """
        try:
            with open(file_path, 'rb') as f:
                bmp_data = f.read()
            
            if len(bmp_data) < 14:
                raise MetadataWriteError("Invalid BMP file: too short")
            
            if bmp_data[:2] != b'BM':
                raise MetadataWriteError("Invalid BMP file: missing BMP signature")
            
            # BMP metadata is very limited - we can only modify header values
            # Extract current header values
            file_size = struct.unpack('<I', bmp_data[2:6])[0]
            data_offset = struct.unpack('<I', bmp_data[10:14])[0]
            
            # Parse DIB header if present
            if len(bmp_data) >= 18:
                dib_header_size = struct.unpack('<I', bmp_data[14:18])[0]
                
                # Update file size if metadata changed
                # (This is a simplified approach - full implementation would
                #  need to handle actual image data size changes)
                new_file_size = file_size
                if 'BMP:FileSize' in metadata:
                    new_file_size = int(metadata['BMP:FileSize'])
                
                # Update header
                new_bmp = bytearray(bmp_data)
                new_bmp[2:6] = struct.pack('<I', new_file_size)
                
                # Update DIB header values if specified
                if dib_header_size >= 40:  # BITMAPINFOHEADER
                    if 'BMP:Width' in metadata:
                        width = int(metadata['BMP:Width'])
                        new_bmp[18:22] = struct.pack('<i', width)
                    
                    if 'BMP:Height' in metadata:
                        height = int(metadata['BMP:Height'])
                        new_bmp[22:26] = struct.pack('<i', height)
                    
                    if 'BMP:ColorDepth' in metadata or 'BMP:BitsPerPixel' in metadata:
                        bits_per_pixel = int(metadata.get('BMP:ColorDepth', metadata.get('BMP:BitsPerPixel', 24)))
                        new_bmp[28:30] = struct.pack('<H', bits_per_pixel)
                    
                    if 'BMP:Compression' in metadata:
                        compression = int(metadata['BMP:Compression'])
                        new_bmp[30:34] = struct.pack('<I', compression)
                
                # Write output file
                with open(output_path, 'wb') as f:
                    f.write(bytes(new_bmp))
            else:
                # File too short, just copy
                with open(output_path, 'wb') as f:
                    f.write(bmp_data)
                
        except Exception as e:
            raise MetadataWriteError(f"Failed to write BMP metadata: {str(e)}")

