# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
XBM (X Bitmap) image metadata parser

This module handles reading metadata from XBM files.
XBM files are ASCII text files containing C code that defines bitmap images.

Copyright 2025 DNAi inc.
"""

import re
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class XBMParser:
    """
    Parser for XBM (X Bitmap) metadata.
    
    XBM files are C source code files containing:
    - #define statements for width and height
    - Array data defining the bitmap
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize XBM parser.
        
        Args:
            file_path: Path to XBM file
            file_data: XBM file data bytes
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
        Parse XBM metadata.
        
        Returns:
            Dictionary of XBM metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 10:
                raise MetadataReadError("Invalid XBM file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'XBM'
            metadata['File:FileTypeExtension'] = 'xbm'
            metadata['File:MIMEType'] = 'image/x-xbitmap'
            
            # XBM files are ASCII text
            try:
                text = file_data.decode('utf-8', errors='ignore')
                
                # Look for width and height definitions
                # Pattern: #define name_width 1280 or #define name_height 853
                width_match = re.search(r'#define\s+\S+_width\s+(\d+)', text, re.IGNORECASE)
                height_match = re.search(r'#define\s+\S+_height\s+(\d+)', text, re.IGNORECASE)
                
                if width_match:
                    width = int(width_match.group(1))
                    metadata['XBM:Width'] = width
                    metadata['File:ImageWidth'] = width
                
                if height_match:
                    height = int(height_match.group(1))
                    metadata['XBM:Height'] = height
                    metadata['File:ImageHeight'] = height
                
                # XBM is monochrome (1 bit per pixel)
                if 'XBM:Width' in metadata and 'XBM:Height' in metadata:
                    metadata['XBM:BitsPerPixel'] = 1
                    metadata['File:BitsPerPixel'] = 1
                
            except UnicodeDecodeError:
                pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse XBM metadata: {str(e)}")

