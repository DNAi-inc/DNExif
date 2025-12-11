# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
WOFF2 (Web Open Font Format 2) file metadata parser

This module handles reading metadata from WOFF2 font files.
WOFF2 files contain Brotli-compressed font data with metadata tables.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError

# Try to import Brotli (optional dependency)
try:
    import brotli
    BROTLI_AVAILABLE = True
except ImportError:
    BROTLI_AVAILABLE = False
    brotli = None


class WOFF2Parser:
    """
    Parser for WOFF2 (Web Open Font Format 2) metadata.
    
    WOFF2 files have the following structure:
    - WOFF2 header (48 bytes)
    - Table directory
    - Font data tables (Brotli-compressed)
    - Extended metadata (optional)
    """
    
    # WOFF2 signature
    WOFF2_SIGNATURE = b'wOF2'
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize WOFF2 parser.
        
        Args:
            file_path: Path to WOFF2 file
            file_data: WOFF2 file data bytes
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
        Parse WOFF2 metadata.
        
        Returns:
            Dictionary of WOFF2 metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 48:
                raise MetadataReadError("Invalid WOFF2 file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'WOFF2'
            metadata['File:FileTypeExtension'] = 'woff2'
            metadata['File:MIMEType'] = 'font/woff2'
            
            # Check WOFF2 signature
            if file_data[:4] != self.WOFF2_SIGNATURE:
                raise MetadataReadError("Invalid WOFF2 file: missing signature")
            
            # Parse WOFF2 header (48 bytes)
            header_data = self._parse_header(file_data)
            if header_data:
                metadata.update(header_data)
            
            # Parse table directory and extract font metadata
            font_metadata = self._extract_font_metadata(file_data)
            if font_metadata:
                metadata.update(font_metadata)
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse WOFF2 metadata: {str(e)}")
    
    def _parse_header(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse WOFF2 header.
        
        WOFF2 header structure (48 bytes):
        - Signature: 4 bytes ('wOF2')
        - Flavor: 4 bytes (SFNT version, e.g., 'OTTO' for OpenType, 'ttcf' for TTC)
        - Length: 4 bytes (total file size)
        - NumTables: 2 bytes (number of tables)
        - Reserved: 2 bytes (should be 0)
        - TotalSfntSize: 4 bytes (uncompressed size)
        - TotalCompressedSize: 4 bytes (compressed size)
        - MajorVersion: 2 bytes
        - MinorVersion: 2 bytes
        - MetaOffset: 4 bytes (offset to metadata block)
        - MetaLength: 4 bytes (length of metadata block)
        - PrivOffset: 4 bytes (offset to private data)
        - PrivLength: 4 bytes (length of private data)
        
        Args:
            file_data: WOFF2 file data bytes
            
        Returns:
            Dictionary of header metadata
        """
        metadata = {}
        
        try:
            if len(file_data) < 48:
                return metadata
            
            # Parse header fields
            signature = file_data[0:4]
            flavor = file_data[4:8]
            length = struct.unpack('>I', file_data[8:12])[0]
            num_tables = struct.unpack('>H', file_data[12:14])[0]
            reserved = struct.unpack('>H', file_data[14:16])[0]
            total_sfnt_size = struct.unpack('>I', file_data[16:20])[0]
            total_compressed_size = struct.unpack('>I', file_data[20:24])[0]
            major_version = struct.unpack('>H', file_data[24:26])[0]
            minor_version = struct.unpack('>H', file_data[26:28])[0]
            meta_offset = struct.unpack('>I', file_data[28:32])[0]
            meta_length = struct.unpack('>I', file_data[32:36])[0]
            priv_offset = struct.unpack('>I', file_data[36:40])[0]
            priv_length = struct.unpack('>I', file_data[40:44])[0]
            
            metadata['WOFF2:Signature'] = signature.decode('ascii', errors='ignore')
            metadata['WOFF2:Flavor'] = flavor.decode('ascii', errors='ignore')
            metadata['WOFF2:Length'] = length
            metadata['WOFF2:NumTables'] = num_tables
            metadata['WOFF2:TotalSfntSize'] = total_sfnt_size
            metadata['WOFF2:TotalCompressedSize'] = total_compressed_size
            metadata['WOFF2:Version'] = f'{major_version}.{minor_version}'
            metadata['WOFF2:MajorVersion'] = major_version
            metadata['WOFF2:MinorVersion'] = minor_version
            
            # Check for extended metadata
            if meta_offset > 0 and meta_length > 0:
                metadata['WOFF2:HasMetadata'] = True
                metadata['WOFF2:MetadataOffset'] = meta_offset
                metadata['WOFF2:MetadataLength'] = meta_length
            
            # Check for private data
            if priv_offset > 0 and priv_length > 0:
                metadata['WOFF2:HasPrivateData'] = True
                metadata['WOFF2:PrivateDataOffset'] = priv_offset
                metadata['WOFF2:PrivateDataLength'] = priv_length
            
        except Exception:
            pass
        
        return metadata
    
    def _extract_font_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """
        Extract font metadata from WOFF2 tables.
        
        Font metadata is typically in the 'name' table which contains:
        - Font family name
        - Font subfamily (weight, style)
        - Full font name
        - Version
        - Copyright
        - etc.
        
        Args:
            file_data: WOFF2 file data bytes
            
        Returns:
            Dictionary of font metadata
        """
        metadata = {}
        
        try:
            if len(file_data) < 48:
                return metadata
            
            # Read number of tables from header
            num_tables = struct.unpack('>H', file_data[12:14])[0]
            
            # WOFF2 table directory starts at offset 48
            # Each table entry is variable-length (compressed table directory)
            # For simplicity, we'll try to extract basic info without full decompression
            
            # Check if Brotli is available for decompression
            if not BROTLI_AVAILABLE:
                metadata['WOFF2:BrotliAvailable'] = False
                metadata['WOFF2:Note'] = 'Brotli library not available - limited metadata extraction'
                return metadata
            
            metadata['WOFF2:BrotliAvailable'] = True
            
            # WOFF2 uses a compressed table directory
            # The table directory is Brotli-compressed and starts after the header
            # For now, we'll extract what we can without full table directory parsing
            
            # Extract extended metadata if present
            meta_offset = struct.unpack('>I', file_data[28:32])[0]
            meta_length = struct.unpack('>I', file_data[32:36])[0]
            
            if meta_offset > 0 and meta_length > 0 and meta_offset + meta_length <= len(file_data):
                meta_data = file_data[meta_offset:meta_offset+meta_length]
                # Extended metadata is XML, but we'll just mark it as present
                metadata['WOFF2:ExtendedMetadata'] = 'Present'
                metadata['WOFF2:ExtendedMetadataSize'] = meta_length
                
                # Try to parse XML metadata if it's text-based
                try:
                    meta_text = meta_data.decode('utf-8', errors='ignore')
                    if '<?xml' in meta_text or '<metadata' in meta_text:
                        metadata['WOFF2:ExtendedMetadataFormat'] = 'XML'
                except Exception:
                    pass
        
        except Exception:
            pass
        
        return metadata

