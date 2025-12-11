# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
ZIP file metadata parser

Extracts ZIP file comments from the End of Central Directory Record (EOCD).

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class ZIPParser:
    """
    Parser for ZIP file metadata.
    
    Extracts ZIP file comments from the End of Central Directory Record (EOCD).
    """
    
    # ZIP End of Central Directory Record signature
    EOCD_SIGNATURE = b'PK\x05\x06'  # 0x06054b50
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize ZIP parser.
        
        Args:
            file_path: Path to ZIP file
            file_data: Raw file data
        """
        self.file_path = file_path
        self.file_data = file_data
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse ZIP file metadata.
        
        Returns:
            Dictionary of ZIP metadata
        """
        try:
            # Read file data
            if self.file_data is None and self.file_path:
                with open(self.file_path, 'rb') as f:
                    self.file_data = f.read()
            elif self.file_data is None:
                return {}
            
            metadata = {}
            
            # Check if it's a ZIP file (starts with PK signature)
            if not self.file_data.startswith(b'PK'):
                return metadata
            
            # Find End of Central Directory Record (EOCD)
            # EOCD is at the end of the file, search backwards
            eocd_offset = self._find_eocd()
            if eocd_offset == -1:
                return metadata
            
            # Parse EOCD structure
            # EOCD structure (22 bytes minimum):
            # - Signature: 4 bytes (0x06054b50)
            # - Disk number: 2 bytes
            # - Central directory disk: 2 bytes
            # - Number of entries on this disk: 2 bytes
            # - Total number of entries: 2 bytes
            # - Central directory size: 4 bytes
            # - Central directory offset: 4 bytes
            # - Comment length: 2 bytes
            # - Comment: variable length
            
            if eocd_offset + 22 > len(self.file_data):
                return metadata
            
            # Read comment length (offset 20 from EOCD start)
            comment_length = struct.unpack('<H', self.file_data[eocd_offset + 20:eocd_offset + 22])[0]
            
            # Extract comment
            if comment_length > 0:
                comment_start = eocd_offset + 22
                if comment_start + comment_length <= len(self.file_data):
                    comment_bytes = self.file_data[comment_start:comment_start + comment_length]
                    try:
                        # Try to decode as UTF-8, fallback to latin-1
                        comment = comment_bytes.decode('utf-8', errors='replace')
                        # Remove null bytes
                        comment = comment.replace('\x00', '')
                        if comment:
                            metadata['ZIP:Comment'] = comment
                            metadata['ZIP:CommentLength'] = comment_length
                    except Exception:
                        # If decoding fails, store as hex or skip
                        pass
            
            # Extract other EOCD fields for completeness
            if eocd_offset + 22 <= len(self.file_data):
                disk_number = struct.unpack('<H', self.file_data[eocd_offset + 4:eocd_offset + 6])[0]
                cd_disk = struct.unpack('<H', self.file_data[eocd_offset + 6:eocd_offset + 8])[0]
                entries_on_disk = struct.unpack('<H', self.file_data[eocd_offset + 8:eocd_offset + 10])[0]
                total_entries = struct.unpack('<H', self.file_data[eocd_offset + 10:eocd_offset + 12])[0]
                cd_size = struct.unpack('<I', self.file_data[eocd_offset + 12:eocd_offset + 16])[0]
                cd_offset = struct.unpack('<I', self.file_data[eocd_offset + 16:eocd_offset + 20])[0]
                
                metadata['ZIP:EntriesOnDisk'] = entries_on_disk
                metadata['ZIP:TotalEntries'] = total_entries
                metadata['ZIP:CentralDirectorySize'] = cd_size
                metadata['ZIP:CentralDirectoryOffset'] = cd_offset
            
            return metadata
            
        except Exception as e:
            raise MetadataReadError(f"Failed to parse ZIP metadata: {str(e)}") from e
    
    def _find_eocd(self) -> int:
        """
        Find End of Central Directory Record (EOCD) signature.
        
        EOCD is typically at the end of the file, but can be preceded
        by a ZIP64 end of central directory locator.
        
        Returns:
            Offset of EOCD signature, or -1 if not found
        """
        if not self.file_data:
            return -1
        
        # Search backwards from the end (EOCD is at the end)
        # Maximum EOCD size is 65557 bytes (22 bytes + 65535 bytes comment)
        search_start = max(0, len(self.file_data) - 65557)
        
        # Search backwards for EOCD signature
        for i in range(len(self.file_data) - 4, search_start - 1, -1):
            if self.file_data[i:i+4] == self.EOCD_SIGNATURE:
                return i
        
        return -1

