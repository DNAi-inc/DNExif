# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
HDR (Radiance HDR) image metadata parser

This module handles reading metadata from HDR files.
HDR files use the Radiance RGBE format for high dynamic range images.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class HDRParser:
    """
    Parser for HDR (Radiance HDR) metadata.
    
    HDR files use Radiance RGBE format:
    - Header starts with "#?RADIANCE" or "#?RGBE"
    - Format line: "FORMAT=32-bit_rle_rgbe" or similar
    - Resolution line: "-Y height +X width" or similar
    - Pixel data: RGBE encoded (4 bytes per pixel: R, G, B, E)
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize HDR parser.
        
        Args:
            file_path: Path to HDR file
            file_data: HDR file data bytes
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
        Parse HDR metadata.
        
        Returns:
            Dictionary of HDR metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 20:
                raise MetadataReadError("Invalid HDR file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'HDR'
            metadata['File:FileTypeExtension'] = 'hdr'
            metadata['File:MIMEType'] = 'image/vnd.radiance'
            
            # Parse header
            try:
                # HDR files are text-based header followed by binary data
                # Find the resolution line (starts with -Y, +Y, -X, or +X)
                header_end = file_data.find(b'\n\n')  # Header ends with double newline
                if header_end == -1:
                    header_end = min(len(file_data), 2048)  # Limit header search
                
                header_text = file_data[:header_end].decode('ascii', errors='ignore')
                lines = header_text.split('\n')
                
                width = None
                height = None
                format_str = None
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('#?RADIANCE') or line.startswith('#?RGBE'):
                        metadata['HDR:Format'] = 'Radiance RGBE'
                    elif line.startswith('FORMAT='):
                        format_str = line.split('=', 1)[1].strip()
                        metadata['HDR:FormatString'] = format_str
                    elif line.startswith('-Y ') or line.startswith('+Y '):
                        # Resolution line: -Y height +X width
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part in ('-Y', '+Y') and i + 1 < len(parts):
                                height = int(parts[i + 1])
                            elif part in ('-X', '+X') and i + 1 < len(parts):
                                width = int(parts[i + 1])
                
                if width and height:
                    metadata['HDR:Width'] = width
                    metadata['HDR:Height'] = height
                    metadata['File:ImageWidth'] = width
                    metadata['File:ImageHeight'] = height
                    metadata['HDR:PixelCount'] = width * height
                
                # HDR uses RGBE encoding (4 bytes per pixel)
                if width and height:
                    expected_data_size = width * height * 4
                    pixel_data_start = header_end + 2  # Skip double newline
                    actual_data_size = len(file_data) - pixel_data_start
                    metadata['HDR:ExpectedDataSize'] = expected_data_size
                    metadata['HDR:ActualDataSize'] = actual_data_size
                    metadata['HDR:BitsPerPixel'] = 32  # RGBE = 4 bytes = 32 bits
                    metadata['File:BitsPerPixel'] = 32
                
            except Exception:
                pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse HDR metadata: {str(e)}")

