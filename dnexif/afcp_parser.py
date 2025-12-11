# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
AFCP (Audio/Video File Content Profile) metadata parser

This module handles reading AFCP metadata from JPEG APP2 segments.
AFCP is a metadata format used for audio/video content profiles.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class AFCPParser:
    """
    Parser for AFCP (Audio/Video File Content Profile) metadata.
    
    AFCP metadata is typically embedded in JPEG APP2 segments
    with identifier "AFCP\x00\x00\x00\x00".
    """
    
    # AFCP identifier
    AFCP_IDENTIFIER = b'AFCP\x00\x00\x00\x00'
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize AFCP parser.
        
        Args:
            file_path: Path to file
            file_data: File data bytes
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
        Parse AFCP metadata.
        
        Returns:
            Dictionary of AFCP metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            metadata = {}
            
            # Check if it's a JPEG file
            if not file_data.startswith(b'\xff\xd8'):
                return metadata
            
            # Search for AFCP in APP2 segments
            offset = 2  # Skip JPEG signature
            
            while offset < len(file_data) - 4:
                # Look for APP2 marker (0xFFE2)
                if file_data[offset:offset+2] == b'\xff\xe2':
                    # Read segment length
                    length = struct.unpack('>H', file_data[offset+2:offset+4])[0]
                    
                    # Check for AFCP identifier
                    if file_data[offset+4:offset+12] == self.AFCP_IDENTIFIER:
                        # Extract AFCP data
                        afcp_data = file_data[offset+12:offset+2+length]
                        
                        # Parse AFCP structure
                        parsed = self._parse_afcp_data(afcp_data)
                        metadata.update(parsed)
                    
                    offset += length
                else:
                    offset += 1
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse AFCP metadata: {str(e)}")
    
    def _parse_afcp_data(self, data: bytes) -> Dict[str, Any]:
        """
        Parse AFCP data structure.
        
        Args:
            data: AFCP data bytes
            
        Returns:
            Dictionary of parsed AFCP metadata
        """
        metadata = {}
        
        try:
            # AFCP uses a structured format
            # This is a simplified parser - full implementation would
            # require parsing the complete AFCP structure
            
            if len(data) < 4:
                return metadata
            
            # Check for AFCP version
            if data[:4] == b'AFCP':
                metadata['AFCP:Version'] = 'AFCP'
            
            # Try to extract basic information
            # AFCP structure is complex and would require full implementation
            # For now, we'll mark that AFCP data was found
            metadata['AFCP:HasAFCP'] = True
            metadata['AFCP:DataSize'] = len(data)
            
            # Try to parse AFCP header if present
            if len(data) >= 8:
                # AFCP header typically contains version and other info
                try:
                    # Look for text-based metadata
                    text_data = data.decode('utf-8', errors='ignore')
                    if 'AFCP' in text_data:
                        metadata['AFCP:HasTextData'] = True
                except Exception:
                    pass
        
        except Exception:
            pass
        
        return metadata

