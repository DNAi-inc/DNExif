# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
PES (Embrid Embroidery) file metadata parser

This module handles reading metadata from PES files.
PES files are used by embroidery machines and software.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class PESParser:
    """
    Parser for PES (Embrid Embroidery) metadata.
    
    PES files have a header structure with embroidery information.
    """
    
    # PES signature
    PES_SIGNATURE = b'#PES'
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize PES parser.
        
        Args:
            file_path: Path to PES file
            file_data: PES file data bytes
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
        Parse PES metadata.
        
        Returns:
            Dictionary of PES metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 8:
                raise MetadataReadError("Invalid PES file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'PES'
            metadata['File:FileTypeExtension'] = 'pes'
            metadata['File:MIMEType'] = 'application/x-pes'
            
            # Check for PES signature
            if file_data[:4] == self.PES_SIGNATURE:
                metadata['PES:HasSignature'] = True
                metadata['PES:Signature'] = '#PES'
                
                # PES files may have version information after signature
                if len(file_data) >= 8:
                    # Try to read version or other header info
                    try:
                        # PES files may have version number
                        version_bytes = file_data[4:8]
                        # Try to interpret as version
                        pass
                    except Exception:
                        pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse PES metadata: {str(e)}")

