# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
TIFF file structure utilities

This module provides utilities for parsing and rebuilding TIFF file structures.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List, Tuple
from dnexif.exceptions import MetadataReadError


class TIFFStructure:
    """
    TIFF file structure parser and builder.
    
    Provides utilities for parsing TIFF structures and rebuilding
    them with updated metadata.
    """
    
    def __init__(self, file_data: bytes):
        """
        Initialize TIFF structure parser.
        
        Args:
            file_data: TIFF file data
        """
        self.file_data = file_data
        self.endian: Optional[str] = None
        self.ifd0_offset: int = 0
        self.ifds: List[Dict[str, Any]] = []
        self.image_strips: List[bytes] = []
        self.image_tiles: List[bytes] = []
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse TIFF file structure.
        
        Returns:
            Dictionary containing parsed structure
        """
        if len(self.file_data) < 8:
            raise MetadataReadError("Invalid TIFF file: too short")
        
        # Determine endianness
        if self.file_data[:2] == b'II':
            self.endian = '<'
        elif self.file_data[:2] == b'MM':
            self.endian = '>'
        else:
            raise MetadataReadError("Invalid TIFF file: bad byte order")
        
        # Check magic number
        magic = struct.unpack(f'{self.endian}H', self.file_data[2:4])[0]
        if magic != 42:
            raise MetadataReadError("Invalid TIFF file: bad magic number")
        
        # Read IFD0 offset
        self.ifd0_offset = struct.unpack(f'{self.endian}I', self.file_data[4:8])[0]
        
        # Parse IFD0
        ifd0 = self._parse_ifd(self.ifd0_offset)
        self.ifds.append(ifd0)
        
        return {
            'endian': self.endian,
            'ifd0_offset': self.ifd0_offset,
            'ifds': self.ifds,
        }
    
    def _parse_ifd(self, offset: int) -> Dict[str, Any]:
        """
        Parse an IFD (Image File Directory).
        
        Args:
            offset: Offset to IFD
            
        Returns:
            Dictionary containing IFD data
        """
        if offset + 2 > len(self.file_data):
            return {'entries': [], 'next_ifd': 0}
        
        # Read number of entries
        num_entries = struct.unpack(f'{self.endian}H', 
                                   self.file_data[offset:offset + 2])[0]
        
        entries = []
        entry_offset = offset + 2
        
        for i in range(min(num_entries, 100)):
            if entry_offset + 12 > len(self.file_data):
                break
            
            # Read tag entry (12 bytes)
            tag_id = struct.unpack(f'{self.endian}H', 
                                  self.file_data[entry_offset:entry_offset + 2])[0]
            tag_type = struct.unpack(f'{self.endian}H', 
                                    self.file_data[entry_offset + 2:entry_offset + 4])[0]
            tag_count = struct.unpack(f'{self.endian}I', 
                                     self.file_data[entry_offset + 4:entry_offset + 8])[0]
            tag_value = struct.unpack(f'{self.endian}I', 
                                     self.file_data[entry_offset + 8:entry_offset + 12])[0]
            
            entries.append({
                'tag_id': tag_id,
                'tag_type': tag_type,
                'tag_count': tag_count,
                'tag_value': tag_value,
                'offset': entry_offset,
            })
            
            entry_offset += 12
        
        # Read next IFD offset
        next_ifd = 0
        if entry_offset + 4 <= len(self.file_data):
            next_ifd = struct.unpack(f'{self.endian}I', 
                                   self.file_data[entry_offset:entry_offset + 4])[0]
        
        return {
            'offset': offset,
            'entries': entries,
            'next_ifd': next_ifd,
        }
    
    def extract_image_data(self) -> Tuple[List[bytes], List[bytes]]:
        """
        Extract image data (strips or tiles) from TIFF file.
        
        Returns:
            Tuple of (strips, tiles)
        """
        # This would extract image strips or tiles based on IFD entries
        # For now, return empty lists
        return [], []

