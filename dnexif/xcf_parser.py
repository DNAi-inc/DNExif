# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
XCF (GIMP Image) file metadata parser

This module handles reading metadata from XCF files.
XCF files are the native format of GIMP (GNU Image Manipulation Program).

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class XCFParser:
    """
    Parser for XCF (GIMP Image) metadata.
    
    XCF files have a header structure:
    - Signature: "gimp xcf "
    - Version: "file" or "v001" etc.
    - Width (4 bytes)
    - Height (4 bytes)
    - Color mode (4 bytes)
    """
    
    # XCF signature
    XCF_SIGNATURE = b'gimp xcf '
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize XCF parser.
        
        Args:
            file_path: Path to XCF file
            file_data: XCF file data bytes
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
        Parse XCF metadata.
        
        Returns:
            Dictionary of XCF metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 20:
                raise MetadataReadError("Invalid XCF file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'XCF'
            metadata['File:FileTypeExtension'] = 'xcf'
            metadata['File:MIMEType'] = 'image/x-xcf'
            
            # Check signature
            if file_data[:9] != self.XCF_SIGNATURE:
                raise MetadataReadError("Invalid XCF file: missing XCF signature")
            
            metadata['XCF:HasSignature'] = True
            metadata['XCF:Signature'] = 'gimp xcf '
            
            # Parse version (null-terminated string after signature)
            version_end = file_data.find(b'\x00', 9)
            if version_end != -1:
                version = file_data[9:version_end].decode('ascii', errors='ignore')
                metadata['XCF:Version'] = version
                offset = version_end + 1
            else:
                offset = 9
            
            # Parse width and height (4 bytes each, big-endian)
            if offset + 8 <= len(file_data):
                width = struct.unpack('>I', file_data[offset:offset+4])[0]
                height = struct.unpack('>I', file_data[offset+4:offset+8])[0]
                
                metadata['XCF:Width'] = width
                metadata['XCF:Height'] = height
                metadata['File:ImageWidth'] = width
                metadata['File:ImageHeight'] = height
                
                # Parse color mode (4 bytes, big-endian)
                if offset + 12 <= len(file_data):
                    color_mode = struct.unpack('>I', file_data[offset+8:offset+12])[0]
                    color_modes = {
                        0: 'RGB',
                        1: 'Grayscale',
                        2: 'Indexed'
                    }
                    metadata['XCF:ColorMode'] = color_modes.get(color_mode, f'Unknown ({color_mode})')
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse XCF metadata: {str(e)}")

