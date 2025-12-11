# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
PICON (Personal Icon) image metadata parser

This module handles reading metadata from PICON files.
PICON files are used for personal icons.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class PICONParser:
    """
    Parser for PICON (Personal Icon) metadata.
    
    PICON files have a simple structure.
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize PICON parser.
        
        Args:
            file_path: Path to PICON file
            file_data: PICON file data bytes
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
        Parse PICON metadata.
        
        Returns:
            Dictionary of PICON metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 10:
                raise MetadataReadError("Invalid PICON file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'PICON'
            metadata['File:FileTypeExtension'] = 'picon'
            metadata['File:MIMEType'] = 'image/x-picon'
            
            # PICON files are typically small icon files
            # Try to extract basic information
            try:
                # Common icon sizes: 16x16, 32x32, 48x48, 64x64, 128x128
                # Try to detect from file size or structure
                pass
            except Exception:
                pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse PICON metadata: {str(e)}")

