# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
SFW (Seattle Film Works) image metadata parser

This module handles reading metadata from SFW files.
SFW files are used by Seattle Film Works software.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class SFWParser:
    """
    Parser for SFW (Seattle Film Works) metadata.
    
    SFW files have a header structure with image information.
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize SFW parser.
        
        Args:
            file_path: Path to SFW file
            file_data: SFW file data bytes
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
        Parse SFW metadata.
        
        Returns:
            Dictionary of SFW metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 20:
                raise MetadataReadError("Invalid SFW file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'SFW'
            metadata['File:FileTypeExtension'] = 'sfw'
            metadata['File:MIMEType'] = 'image/x-sfw'
            
            # SFW files start with "SFW9" signature
            if file_data[:4] == b'SFW9':
                metadata['SFW:HasSignature'] = True
                metadata['SFW:Signature'] = 'SFW9'
                
                # Parse header structure
                try:
                    # SFW header may contain image dimensions
                    # Try to extract from header offsets
                    if len(file_data) >= 20:
                        # Check various offsets for potential width/height
                        # SFW files may have dimensions stored as 16-bit or 32-bit values
                        pass
                except Exception:
                    pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse SFW metadata: {str(e)}")

