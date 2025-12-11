# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
MNG (Multiple-image Network Graphics) image metadata parser

This module handles reading metadata from MNG files.
MNG is an extension of PNG that supports multiple images and animations.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class MNGParser:
    """
    Parser for MNG (Multiple-image Network Graphics) metadata.
    
    MNG files use a chunk-based structure similar to PNG:
    - Signature: 8A 4D 4E 47 0D 0A 1A 0A
    - Chunks: IHDR, MEND, etc.
    """
    
    # MNG signature
    MNG_SIGNATURE = b'\x8aMNG\r\n\x1a\n'
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize MNG parser.
        
        Args:
            file_path: Path to MNG file
            file_data: MNG file data bytes
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
        Parse MNG metadata.
        
        Returns:
            Dictionary of MNG metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 8:
                raise MetadataReadError("Invalid MNG file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'MNG'
            metadata['File:FileTypeExtension'] = 'mng'
            metadata['File:MIMEType'] = 'video/x-mng'
            
            # Check signature
            if file_data[:8] != self.MNG_SIGNATURE:
                raise MetadataReadError("Invalid MNG file: missing MNG signature")
            
            metadata['MNG:HasSignature'] = True
            
            # Parse chunks (similar to PNG)
            offset = 8
            chunk_count = 0
            
            while offset < len(file_data) - 8:
                if offset + 8 > len(file_data):
                    break
                
                # Read chunk length (4 bytes, big-endian)
                chunk_length = struct.unpack('>I', file_data[offset:offset+4])[0]
                offset += 4
                
                # Read chunk type (4 bytes)
                if offset + 4 > len(file_data):
                    break
                chunk_type = file_data[offset:offset+4]
                offset += 4
                
                chunk_type_str = chunk_type.decode('ascii', errors='ignore')
                
                # Check for MEND chunk (end of file)
                if chunk_type_str == 'MEND':
                    break
                
                # Parse IHDR chunk (Image Header)
                if chunk_type_str == 'IHDR' and chunk_length >= 13:
                    if offset + 13 <= len(file_data):
                        width = struct.unpack('>I', file_data[offset:offset+4])[0]
                        height = struct.unpack('>I', file_data[offset+4:offset+8])[0]
                        bit_depth = file_data[offset+8]
                        color_type = file_data[offset+9]
                        compression = file_data[offset+10]
                        filter_method = file_data[offset+11]
                        interlace = file_data[offset+12]
                        
                        metadata['MNG:Width'] = width
                        metadata['MNG:Height'] = height
                        metadata['MNG:BitDepth'] = bit_depth
                        metadata['MNG:ColorType'] = color_type
                        metadata['MNG:Compression'] = compression
                        metadata['MNG:FilterMethod'] = filter_method
                        metadata['MNG:Interlace'] = interlace
                        
                        metadata['File:ImageWidth'] = width
                        metadata['File:ImageHeight'] = height
                        metadata['File:BitsPerPixel'] = bit_depth
                
                chunk_count += 1
                offset += chunk_length + 4  # Skip chunk data and CRC
            
            metadata['MNG:ChunkCount'] = chunk_count
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse MNG metadata: {str(e)}")

