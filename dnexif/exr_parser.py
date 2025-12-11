# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
EXR (OpenEXR) image metadata parser

This module handles reading metadata from EXR files.
EXR files are used for high dynamic range images with floating-point pixel values.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class EXRParser:
    """
    Parser for EXR (OpenEXR) metadata.
    
    EXR files have the following structure:
    - Magic number: 0x762f3101 (4 bytes)
    - Version and flags (4 bytes)
    - Header (attributes)
    - Pixel data
    """
    
    # EXR magic number
    EXR_MAGIC = 0x762f3101
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize EXR parser.
        
        Args:
            file_path: Path to EXR file
            file_data: EXR file data bytes
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
        Parse EXR metadata.
        
        Returns:
            Dictionary of EXR metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 8:
                raise MetadataReadError("Invalid EXR file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'EXR'
            metadata['File:FileTypeExtension'] = 'exr'
            metadata['File:MIMEType'] = 'image/x-exr'
            
            # Check magic number (EXR uses big-endian)
            magic = struct.unpack('>I', file_data[0:4])[0]
            if magic != self.EXR_MAGIC:
                raise MetadataReadError(f"Invalid EXR file: invalid magic number {hex(magic)}")
            
            metadata['EXR:HasSignature'] = True
            metadata['EXR:Signature'] = hex(magic)
            
            # Parse version and flags (4 bytes, big-endian)
            version_flags = struct.unpack('>I', file_data[4:8])[0]
            version = version_flags & 0xFF
            flags = (version_flags >> 8) & 0xFF
            
            metadata['EXR:Version'] = version
            metadata['EXR:Flags'] = flags
            
            # Parse header attributes
            # EXR headers are null-terminated strings with key-value pairs
            try:
                header_start = 8
                header_end = file_data.find(b'\x00', header_start)
                if header_end == -1:
                    header_end = min(len(file_data), 2048)  # Limit header search
                
                # Try to extract dimensions from header
                # EXR headers contain "displayWindow" and "dataWindow" with x, y, width, height
                header_text = file_data[header_start:header_end].decode('ascii', errors='ignore')
                
                # Look for displayWindow or dataWindow
                if 'displayWindow' in header_text or 'dataWindow' in header_text:
                    # Try to extract width and height
                    import re
                    # Look for patterns like "xMax 1919" or "yMax 1279"
                    x_max_match = re.search(r'xMax\s+(\d+)', header_text)
                    y_max_match = re.search(r'yMax\s+(\d+)', header_text)
                    x_min_match = re.search(r'xMin\s+(\d+)', header_text)
                    y_min_match = re.search(r'yMin\s+(\d+)', header_text)
                    
                    if x_max_match and x_min_match and y_max_match and y_min_match:
                        x_max = int(x_max_match.group(1))
                        x_min = int(x_min_match.group(1))
                        y_max = int(y_max_match.group(1))
                        y_min = int(y_min_match.group(1))
                        
                        width = x_max - x_min + 1
                        height = y_max - y_min + 1
                        
                        metadata['EXR:Width'] = width
                        metadata['EXR:Height'] = height
                        metadata['File:ImageWidth'] = width
                        metadata['File:ImageHeight'] = height
                        metadata['EXR:XMin'] = x_min
                        metadata['EXR:YMin'] = y_min
                        metadata['EXR:XMax'] = x_max
                        metadata['EXR:YMax'] = y_max
                
                # Extract compression type if present
                compression_match = re.search(r'compression\s+(\w+)', header_text)
                if compression_match:
                    metadata['EXR:Compression'] = compression_match.group(1)
                
            except Exception:
                pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse EXR metadata: {str(e)}")

