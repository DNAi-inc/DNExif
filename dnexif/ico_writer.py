# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
ICO/CUR (Icon/Cursor) metadata writer

This module handles writing metadata to ICO and CUR files.
ICO/CUR files have very limited metadata support, so this writer
primarily preserves the file structure.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any
from pathlib import Path

from dnexif.exceptions import MetadataWriteError


class ICOWriter:
    """
    Writer for ICO/CUR files.
    
    ICO/CUR files have very limited metadata support.
    This writer preserves the file structure but cannot store
    standard metadata in a way that can be read back.
    """
    
    def __init__(self):
        """Initialize ICO writer."""
        pass
    
    def write_ico(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write ICO/CUR file, preserving structure.
        
        Note: ICO/CUR files don't support standard metadata storage.
        This method preserves the file structure but metadata cannot
        be read back in a standard way.
        
        Args:
            file_path: Original ICO/CUR file path
            metadata: Metadata dictionary (not used, but preserved for API consistency)
            output_path: Output file path
        """
        try:
            with open(file_path, 'rb') as f:
                original_data = f.read()
            
            if len(original_data) < 6:
                raise MetadataWriteError("Invalid ICO/CUR file: too short")
            
            # Verify ICO/CUR signature
            reserved = struct.unpack('<H', original_data[0:2])[0]
            if reserved != 0:
                raise MetadataWriteError("Invalid ICO/CUR file: invalid reserved field")
            
            file_type = struct.unpack('<H', original_data[2:4])[0]
            if file_type not in (1, 2):
                raise MetadataWriteError("Invalid ICO/CUR file: invalid type")
            
            # For now, just copy the file as-is since ICO doesn't support metadata
            # In the future, we could potentially modify embedded PNG images if present
            with open(output_path, 'wb') as f:
                f.write(original_data)
                
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to write ICO/CUR file: {str(e)}")

