# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
RAR archive file metadata parser

This module handles reading metadata from RAR archive files.
Supports both RAR v4.x and RAR v5.0 formats.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class RARParser:
    """
    Parser for RAR archive metadata.
    
    RAR files have the following structure:
    - RAR signature (RAR v4.x or v5.0)
    - Archive header
    - File headers
    - File data
    """
    
    # RAR signatures
    RAR_V4_SIGNATURE = b'Rar!\x1A\x07\x00'  # RAR v4.x
    RAR_V5_SIGNATURE = b'Rar!\x1A\x07\x01\x00'  # RAR v5.0
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize RAR parser.
        
        Args:
            file_path: Path to RAR file
            file_data: RAR file data bytes
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
        Parse RAR metadata.
        
        Returns:
            Dictionary of RAR metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read(1024)  # Read first 1KB for header
            else:
                file_data = self.file_data[:1024] if len(self.file_data) >= 1024 else self.file_data
            
            if len(file_data) < 8:
                raise MetadataReadError("Invalid RAR file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'RAR'
            metadata['File:FileTypeExtension'] = 'rar'
            metadata['File:MIMEType'] = 'application/x-rar-compressed'
            metadata['Archive:Format'] = 'RAR'
            metadata['Archive:FormatName'] = 'RAR Archive'
            
            # Check for RAR v5.0 signature
            if file_data.startswith(self.RAR_V5_SIGNATURE):
                metadata['Archive:Version'] = '5.0'
                metadata['Archive:MajorVersion'] = 5
                metadata['Archive:MinorVersion'] = 0
                metadata['Archive:HasSignature'] = True
                metadata['Archive:Signature'] = 'Rar!\x1A\x07\x01\x00'
                
                # RAR v5.0 header structure:
                # - Bytes 0-7: Signature "Rar!\x1A\x07\x01\x00"
                # - Bytes 8-15: CRC32 (8 bytes, little-endian)
                # - Bytes 16-23: Header size (8 bytes, little-endian)
                # - Bytes 24-27: Header type (4 bytes, little-endian)
                # - Bytes 28+: Header flags and data
                
                if len(file_data) >= 32:
                    # Read CRC32 (bytes 8-15)
                    crc32 = struct.unpack('<Q', file_data[8:16])[0]
                    metadata['Archive:CRC32'] = crc32
                    
                    # Read header size (bytes 16-23)
                    header_size = struct.unpack('<Q', file_data[16:24])[0]
                    metadata['Archive:HeaderSize'] = header_size
                    
                    # Read header type (bytes 24-27)
                    header_type = struct.unpack('<I', file_data[24:28])[0]
                    header_type_map = {
                        1: 'Archive Header',
                        2: 'File Header',
                        3: 'Service Header',
                        4: 'Archive Encryption Header',
                        5: 'End of Archive Header',
                    }
                    if header_type in header_type_map:
                        metadata['Archive:HeaderType'] = header_type_map[header_type]
                    else:
                        metadata['Archive:HeaderType'] = f'Unknown ({header_type})'
            
            # Check for RAR v4.x signature
            elif file_data.startswith(self.RAR_V4_SIGNATURE):
                metadata['Archive:Version'] = '4.x'
                metadata['Archive:MajorVersion'] = 4
                metadata['Archive:MinorVersion'] = 0
                metadata['Archive:HasSignature'] = True
                metadata['Archive:Signature'] = 'Rar!\x1A\x07\x00'
                
                # RAR v4.x header structure:
                # - Bytes 0-6: Signature "Rar!\x1A\x07\x00"
                # - Bytes 7-9: Archive header CRC (3 bytes)
                # - Bytes 10-11: Header type (2 bytes)
                # - Bytes 12-13: Header flags (2 bytes)
                # - Bytes 14-15: Header size (2 bytes)
                
                if len(file_data) >= 16:
                    # Read archive header CRC (bytes 7-9)
                    header_crc = struct.unpack('<I', file_data[7:10] + b'\x00')[0]
                    metadata['Archive:HeaderCRC'] = header_crc
                    
                    # Read header type (bytes 10-11)
                    header_type = struct.unpack('<H', file_data[10:12])[0]
                    header_type_map = {
                        0x72: 'Archive Header',
                        0x73: 'File Header',
                        0x74: 'Comment Header',
                        0x75: 'Extra Information Header',
                        0x76: 'Subblock Header',
                        0x77: 'Recovery Record Header',
                        0x78: 'Authenticity Information Header',
                        0x79: 'Subblock Header',
                        0x7A: 'End of Archive Header',
                    }
                    if header_type in header_type_map:
                        metadata['Archive:HeaderType'] = header_type_map[header_type]
                    else:
                        metadata['Archive:HeaderType'] = f'Unknown (0x{header_type:02X})'
                    
                    # Read header flags (bytes 12-13)
                    header_flags = struct.unpack('<H', file_data[12:14])[0]
                    metadata['Archive:HeaderFlags'] = header_flags
                    
                    # Read header size (bytes 14-15)
                    header_size = struct.unpack('<H', file_data[14:16])[0]
                    metadata['Archive:HeaderSize'] = header_size
            
            else:
                raise MetadataReadError("Invalid RAR file: missing signature")
            
            # Try to detect compression method
            # RAR files may use various compression methods
            compression_methods = {
                b'Store': 'Store (no compression)',
                b'Fastest': 'Fastest',
                b'Fast': 'Fast',
                b'Normal': 'Normal',
                b'Good': 'Good',
                b'Best': 'Best',
            }
            
            for method_sig, method_name in compression_methods.items():
                if method_sig in file_data[:512]:
                    metadata['Archive:CompressionMethod'] = method_name
                    break
            
            # Look for volume information (RAR files can be split into volumes)
            if b'.part' in file_data[:256].lower() or b'.r' in file_data[:256].lower():
                metadata['Archive:IsVolume'] = True
            
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
            raise MetadataReadError(f"Failed to parse RAR metadata: {str(e)}")

