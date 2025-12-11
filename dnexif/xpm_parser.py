# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
XPM (X PixMap) image metadata parser

This module handles reading metadata from XPM files.
XPM files are C source code files containing color pixmap definitions.

Copyright 2025 DNAi inc.
"""

import re
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class XPMParser:
    """
    Parser for XPM (X PixMap) metadata.
    
    XPM files are C source code files containing:
    - Static char * declarations
    - Array definitions with width, height, colors, chars_per_pixel
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize XPM parser.
        
        Args:
            file_path: Path to XPM file
            file_data: XPM file data bytes
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
        Parse XPM metadata.
        
        Returns:
            Dictionary of XPM metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 10:
                raise MetadataReadError("Invalid XPM file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'XPM'
            metadata['File:FileTypeExtension'] = 'xpm'
            metadata['File:MIMEType'] = 'image/x-xpixmap'
            
            # XPM files are ASCII text
            try:
                text = file_data.decode('utf-8', errors='ignore')
                
                # XPM format: "width height ncolors chars_per_pixel"
                # Look for pattern in static char declarations
                # Pattern: "1280 853 256 1" or similar
                xpm_header_match = re.search(r'"\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', text)
                
                if xpm_header_match:
                    width = int(xpm_header_match.group(1))
                    height = int(xpm_header_match.group(2))
                    ncolors = int(xpm_header_match.group(3))
                    chars_per_pixel = int(xpm_header_match.group(4))
                    
                    metadata['XPM:Width'] = width
                    metadata['XPM:Height'] = height
                    metadata['XPM:ColorCount'] = ncolors
                    metadata['XPM:CharsPerPixel'] = chars_per_pixel
                    metadata['File:ImageWidth'] = width
                    metadata['File:ImageHeight'] = height
                    
                    # Estimate bits per pixel based on color count
                    if ncolors <= 2:
                        bpp = 1
                    elif ncolors <= 16:
                        bpp = 4
                    elif ncolors <= 256:
                        bpp = 8
                    else:
                        bpp = 24  # Full color
                    
                    metadata['XPM:BitsPerPixel'] = bpp
                    metadata['File:BitsPerPixel'] = bpp
                
            except UnicodeDecodeError:
                pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse XPM metadata: {str(e)}")

