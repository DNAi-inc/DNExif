# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
7z archive file metadata parser

This module handles reading metadata from 7z archive files.
7z files are compressed archives with embedded metadata.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class SevenZParser:
    """
    Parser for 7z archive metadata.
    
    7z files have the following structure:
    - Signature header (6 bytes): "7z\xBC\xAF\x27\x1C"
    - Archive properties
    - Additional streams
    - Main stream
    """
    
    # 7z signature
    SEVENZ_SIGNATURE = b'7z\xBC\xAF\x27\x1C'
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize 7z parser.
        
        Args:
            file_path: Path to 7z file
            file_data: 7z file data bytes
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
        Parse 7z metadata.
        
        Returns:
            Dictionary of 7z metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read(1024)  # Read first 1KB for header
            else:
                file_data = self.file_data[:1024] if len(self.file_data) >= 1024 else self.file_data
            
            if len(file_data) < 6:
                raise MetadataReadError("Invalid 7z file: too short")
            
            metadata = {}
            metadata['File:FileType'] = '7Z'
            metadata['File:FileTypeExtension'] = '7z'
            metadata['File:MIMEType'] = 'application/x-7z-compressed'
            metadata['Archive:Format'] = '7z'
            metadata['Archive:FormatName'] = '7-Zip Archive'
            
            # Check for 7z signature
            if file_data.startswith(self.SEVENZ_SIGNATURE):
                metadata['Archive:HasSignature'] = True
                metadata['Archive:Signature'] = '7z\xBC\xAF\x27\x1C'
                
                # 7z header structure:
                # - Bytes 0-5: Signature "7z\xBC\xAF\x27\x1C"
                # - Bytes 6-9: Archive version (major, minor)
                # - Bytes 10+: Archive properties
                
                if len(file_data) >= 10:
                    # Read archive version
                    major_version = file_data[6]
                    minor_version = file_data[7]
                    metadata['Archive:Version'] = f'{major_version}.{minor_version}'
                    metadata['Archive:MajorVersion'] = major_version
                    metadata['Archive:MinorVersion'] = minor_version
                
                # Try to detect compression method from header
                # Common 7z compression methods have signatures
                compression_methods = {
                    b'LZMA': 'LZMA',
                    b'LZMA2': 'LZMA2',
                    b'PPMD': 'PPMD',
                    b'BCJ': 'BCJ',
                    b'BCJ2': 'BCJ2',
                    b'BZip2': 'BZip2',
                    b'Deflate': 'Deflate',
                }
                
                for method_sig, method_name in compression_methods.items():
                    if method_sig in file_data[:512]:
                        metadata['Archive:CompressionMethod'] = method_name
                        break
                
                # If no specific method found, check for common patterns
                if 'Archive:CompressionMethod' not in metadata:
                    # LZMA is the default for 7z
                    metadata['Archive:CompressionMethod'] = 'LZMA (default)'
            
            else:
                raise MetadataReadError("Invalid 7z file: missing signature")
            
            # Try to extract file count and size information
            # 7z files store this in the header, but parsing requires full format knowledge
            # For now, we'll extract what we can from the header
            
            # Look for file count patterns (may be stored as uint64)
            if len(file_data) >= 32:
                # Try to find file count (often stored early in header)
                for offset in range(10, min(100, len(file_data) - 8), 1):
                    try:
                        # Try little-endian uint64
                        value = struct.unpack('<Q', file_data[offset:offset+8])[0]
                        if 0 < value < 1000000:  # Reasonable file count
                            metadata['Archive:EstimatedFileCount'] = value
                            break
                    except Exception:
                        continue
            
            # File size
            if self.file_path:
                try:
                    file_size = self.file_path.stat().st_size
                    metadata['File:FileSize'] = file_size
                    metadata['Archive:ArchiveSize'] = file_size
                except Exception:
                    pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse 7z metadata: {str(e)}")

