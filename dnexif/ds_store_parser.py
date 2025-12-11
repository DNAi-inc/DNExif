# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
macOS DS_Store metadata parser

This module handles reading metadata from macOS DS_Store files.
DS_Store files contain directory metadata used by macOS Finder.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class DSStoreParser:
    """
    Parser for macOS DS_Store (Desktop Services Store) metadata.
    
    DS_Store files contain directory metadata used by macOS Finder.
    Structure:
    - Header: 4 bytes version (0x00000001)
    - Signature: "Bud1" (4 bytes)
    - Block structure with offsets and sizes
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize DS_Store parser.
        
        Args:
            file_path: Path to DS_Store file
            file_data: DS_Store file data bytes
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
        Parse DS_Store metadata.
        
        Returns:
            Dictionary of DS_Store metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 8:
                raise MetadataReadError("Invalid DS_Store file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'DS_Store'
            metadata['File:FileTypeExtension'] = 'ds_store'
            metadata['File:MIMEType'] = 'application/x-apple-ds-store'
            metadata['DSStore:Format'] = 'Apple Desktop Services Store'
            
            # Check DS_Store signature
            # DS_Store files start with version (4 bytes) followed by "Bud1" (4 bytes)
            if len(file_data) >= 8:
                version = struct.unpack('>I', file_data[0:4])[0]
                signature = file_data[4:8]
                
                if signature == b'Bud1':
                    metadata['DSStore:HasSignature'] = True
                    metadata['DSStore:Signature'] = 'Bud1'
                    metadata['DSStore:Version'] = version
                    metadata['DSStore:FormatVersion'] = f'1.{version}'
                    
                    # Parse block structure
                    # After signature, there are block offsets and sizes
                    offset = 8
                    block_count = 0
                    max_blocks = 100  # Limit to avoid parsing very large files
                    
                    while offset < len(file_data) - 16 and block_count < max_blocks:
                        try:
                            # Read block offset (4 bytes, big-endian)
                            if offset + 4 > len(file_data):
                                break
                            block_offset = struct.unpack('>I', file_data[offset:offset+4])[0]
                            offset += 4
                            
                            # Read block size (4 bytes, big-endian)
                            if offset + 4 > len(file_data):
                                break
                            block_size = struct.unpack('>I', file_data[offset:offset+4])[0]
                            offset += 4
                            
                            if block_offset == 0 and block_size == 0:
                                break
                            
                            if block_offset < len(file_data) and block_size > 0 and block_offset + block_size <= len(file_data):
                                block_count += 1
                                metadata[f'DSStore:Block{block_count}:Offset'] = block_offset
                                metadata[f'DSStore:Block{block_count}:Size'] = block_size
                                
                                # Try to extract some metadata from block
                                block_data = file_data[block_offset:block_offset+min(block_size, 1000)]
                                
                                # Look for UTF-16 strings (common in DS_Store)
                                try:
                                    # Try to find file names or keys in the block
                                    if b'\x00' in block_data:
                                        # Might contain UTF-16 strings
                                        parts = block_data.split(b'\x00')
                                        for i, part in enumerate(parts[:10]):  # Limit to first 10 parts
                                            if len(part) > 2 and len(part) < 100:
                                                try:
                                                    text = part.decode('utf-8', errors='ignore')
                                                    if text.isprintable() and len(text) > 1:
                                                        metadata[f'DSStore:Block{block_count}:Text{i}'] = text
                                                except:
                                                    pass
                                except:
                                    pass
                            else:
                                break
                        except:
                            break
                    
                    metadata['DSStore:BlockCount'] = block_count
                    
                    # Extract file size
                    metadata['File:FileSize'] = len(file_data)
                    metadata['File:FileSizeBytes'] = len(file_data)
                    
                else:
                    metadata['DSStore:HasSignature'] = False
                    metadata['DSStore:Format'] = 'Unknown'
            
            return metadata
            
        except Exception as exc:
            raise MetadataReadError(f"Failed to parse DS_Store metadata: {exc}") from exc

