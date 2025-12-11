# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
AppleDouble (MacOS "._" sidecar) file metadata parser

This module handles reading metadata from AppleDouble files.
AppleDouble files are used by macOS to store extended attributes and resource forks.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class AppleDoubleParser:
    """
    Parser for AppleDouble (MacOS "._" sidecar) metadata.
    
    AppleDouble files have the following structure:
    - Magic number: 0x00051607 (AppleDouble v1) or 0x00051600 (AppleDouble v2)
    - Version: 0x00020000
    - Number of entries
    - Entry descriptors (type, offset, length)
    - Entry data
    """
    
    # AppleDouble magic numbers
    APPLEDOUBLE_V1_MAGIC = 0x00051607
    APPLEDOUBLE_V2_MAGIC = 0x00051600
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize AppleDouble parser.
        
        Args:
            file_path: Path to AppleDouble file
            file_data: AppleDouble file data bytes
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
        Parse AppleDouble metadata.
        
        Returns:
            Dictionary of AppleDouble metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 26:
                raise MetadataReadError("Invalid AppleDouble file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'AppleDouble'
            metadata['File:FileTypeExtension'] = 'appledouble'
            metadata['File:MIMEType'] = 'application/applefile'
            
            # Parse AppleDouble header (big-endian)
            # Offset 0-3: Magic number
            magic = struct.unpack('>I', file_data[0:4])[0]
            
            if magic == self.APPLEDOUBLE_V1_MAGIC:
                metadata['AppleDouble:Version'] = 1
            elif magic == self.APPLEDOUBLE_V2_MAGIC:
                metadata['AppleDouble:Version'] = 2
            else:
                raise MetadataReadError(f"Invalid AppleDouble file: invalid magic number 0x{magic:08X}")
            
            # Offset 4-7: Version (should be 0x00020000)
            version = struct.unpack('>I', file_data[4:8])[0]
            metadata['AppleDouble:FormatVersion'] = version
            
            # Offset 8-11: Filler (should be zeros)
            filler = struct.unpack('>I', file_data[8:12])[0]
            if filler != 0:
                metadata['AppleDouble:Filler'] = filler
            
            # Offset 12-13: Number of entries (2 bytes, big-endian)
            num_entries = struct.unpack('>H', file_data[12:14])[0]
            metadata['AppleDouble:EntryCount'] = num_entries
            
            # Parse entry descriptors
            entries = []
            offset = 14  # Header is 14 bytes (4 magic + 4 version + 4 filler + 2 num_entries)
            
            for i in range(num_entries):
                if offset + 12 > len(file_data):
                    break
                
                # Entry descriptor: type (4 bytes), offset (4 bytes), length (4 bytes)
                entry_type = struct.unpack('>I', file_data[offset:offset+4])[0]
                entry_offset = struct.unpack('>I', file_data[offset+4:offset+8])[0]
                entry_length = struct.unpack('>I', file_data[offset+8:offset+12])[0]
                
                # Entry type mapping
                entry_type_map = {
                    1: 'Data Fork',
                    2: 'Resource Fork',
                    3: 'Real Name',
                    4: 'Comment',
                    5: 'Icon BW',
                    6: 'Icon Color',
                    8: 'File Dates Info',
                    9: 'Finder Info',
                    10: 'Macintosh File Info',
                    11: 'ProDOS File Info',
                    12: 'MS-DOS File Info',
                    13: 'Short Name',
                    14: 'AFP File Info',
                    15: 'Directory ID',
                }
                
                entry_info = {
                    'Type': entry_type,
                    'TypeName': entry_type_map.get(entry_type, f'Unknown ({entry_type})'),
                    'Offset': entry_offset,
                    'Length': entry_length,
                }
                entries.append(entry_info)
                
                metadata[f'AppleDouble:Entry{i+1}:Type'] = entry_type
                metadata[f'AppleDouble:Entry{i+1}:TypeName'] = entry_info['TypeName']
                metadata[f'AppleDouble:Entry{i+1}:Offset'] = entry_offset
                metadata[f'AppleDouble:Entry{i+1}:Length'] = entry_length
                
                offset += 12
            
            metadata['AppleDouble:Entries'] = entries
            
            # Try to parse Finder Info (entry type 9) if present
            finder_info_entry = next((e for e in entries if e['Type'] == 9), None)
            if finder_info_entry:
                finder_offset = finder_info_entry['Offset']
                finder_length = finder_info_entry['Length']
                if finder_offset + finder_length <= len(file_data):
                    finder_data = file_data[finder_offset:finder_offset + finder_length]
                    if len(finder_data) >= 32:
                        # Finder Info is typically 32 bytes
                        metadata['AppleDouble:FinderInfo:Length'] = len(finder_data)
            
            # Extract file size
            if self.file_path:
                import os
                file_size = os.path.getsize(self.file_path)
                metadata['File:FileSize'] = file_size
                metadata['File:FileSizeBytes'] = file_size
            else:
                metadata['File:FileSize'] = len(file_data)
                metadata['File:FileSizeBytes'] = len(file_data)
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse AppleDouble metadata: {str(e)}")

