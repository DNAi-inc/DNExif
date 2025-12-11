# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
WOFF (Web Open Font Format) file metadata parser

This module handles reading metadata from WOFF font files.
WOFF files contain compressed font data with metadata tables.

Copyright 2025 DNAi inc.
"""

import struct
import zlib
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class WOFFParser:
    """
    Parser for WOFF (Web Open Font Format) metadata.
    
    WOFF files have the following structure:
    - WOFF header (44 bytes)
    - Table directory
    - Font data tables (compressed)
    - Extended metadata (optional)
    """
    
    # WOFF signature
    WOFF_SIGNATURE = b'wOFF'
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize WOFF parser.
        
        Args:
            file_path: Path to WOFF file
            file_data: WOFF file data bytes
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
        Parse WOFF metadata.
        
        Returns:
            Dictionary of WOFF metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 44:
                raise MetadataReadError("Invalid WOFF file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'WOFF'
            metadata['File:FileTypeExtension'] = 'woff'
            metadata['File:MIMEType'] = 'font/woff'
            
            # Check WOFF signature
            if file_data[:4] != self.WOFF_SIGNATURE:
                raise MetadataReadError("Invalid WOFF file: missing signature")
            
            # Parse WOFF header (44 bytes)
            header_data = self._parse_header(file_data)
            if header_data:
                metadata.update(header_data)
            
            # Parse table directory and extract font metadata
            font_metadata = self._extract_font_metadata(file_data)
            if font_metadata:
                metadata.update(font_metadata)
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse WOFF metadata: {str(e)}")
    
    def _parse_header(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse WOFF header.
        
        WOFF header structure (44 bytes):
        - Signature: 4 bytes ('wOFF')
        - Flavor: 4 bytes (SFNT version, e.g., 'OTTO' for OpenType, 'ttcf' for TTC)
        - Length: 4 bytes (total file size)
        - NumTables: 2 bytes (number of tables)
        - Reserved: 2 bytes (should be 0)
        - TotalSfntSize: 4 bytes (uncompressed size)
        - MajorVersion: 2 bytes
        - MinorVersion: 2 bytes
        - MetaOffset: 4 bytes (offset to metadata block)
        - MetaLength: 4 bytes (length of metadata block)
        - PrivOffset: 4 bytes (offset to private data)
        - PrivLength: 4 bytes (length of private data)
        
        Args:
            file_data: WOFF file data bytes
            
        Returns:
            Dictionary of header metadata
        """
        metadata = {}
        
        try:
            if len(file_data) < 44:
                return metadata
            
            # Parse header fields
            signature = file_data[0:4]
            flavor = file_data[4:8]
            length = struct.unpack('>I', file_data[8:12])[0]
            num_tables = struct.unpack('>H', file_data[12:14])[0]
            reserved = struct.unpack('>H', file_data[14:16])[0]
            total_sfnt_size = struct.unpack('>I', file_data[16:20])[0]
            major_version = struct.unpack('>H', file_data[20:22])[0]
            minor_version = struct.unpack('>H', file_data[22:24])[0]
            meta_offset = struct.unpack('>I', file_data[24:28])[0]
            meta_length = struct.unpack('>I', file_data[28:32])[0]
            priv_offset = struct.unpack('>I', file_data[32:36])[0]
            priv_length = struct.unpack('>I', file_data[36:40])[0]
            
            metadata['WOFF:Signature'] = signature.decode('ascii', errors='ignore')
            metadata['WOFF:Flavor'] = flavor.decode('ascii', errors='ignore')
            metadata['WOFF:Length'] = length
            metadata['WOFF:NumTables'] = num_tables
            metadata['WOFF:TotalSfntSize'] = total_sfnt_size
            metadata['WOFF:Version'] = f'{major_version}.{minor_version}'
            metadata['WOFF:MajorVersion'] = major_version
            metadata['WOFF:MinorVersion'] = minor_version
            
            # Check for extended metadata
            if meta_offset > 0 and meta_length > 0:
                metadata['WOFF:HasMetadata'] = True
                metadata['WOFF:MetadataOffset'] = meta_offset
                metadata['WOFF:MetadataLength'] = meta_length
            
            # Check for private data
            if priv_offset > 0 and priv_length > 0:
                metadata['WOFF:HasPrivateData'] = True
                metadata['WOFF:PrivateDataOffset'] = priv_offset
                metadata['WOFF:PrivateDataLength'] = priv_length
            
        except Exception:
            pass
        
        return metadata
    
    def _extract_font_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """
        Extract font metadata from WOFF tables.
        
        Font metadata is typically in the 'name' table which contains:
        - Font family name
        - Font subfamily (weight, style)
        - Full font name
        - Version
        - Copyright
        - etc.
        
        Args:
            file_data: WOFF file data bytes
            
        Returns:
            Dictionary of font metadata
        """
        metadata = {}
        
        try:
            if len(file_data) < 44:
                return metadata
            
            # Read number of tables from header
            num_tables = struct.unpack('>H', file_data[12:14])[0]
            
            # Table directory starts at offset 44
            table_dir_offset = 44
            table_dir_size = num_tables * 20  # Each table entry is 20 bytes
            
            if table_dir_offset + table_dir_size > len(file_data):
                return metadata
            
            # Parse table directory
            name_table_info = None
            
            for i in range(num_tables):
                table_offset = table_dir_offset + (i * 20)
                
                # Parse table entry (20 bytes):
                # - Tag: 4 bytes (table name)
                # - Offset: 4 bytes (offset in WOFF file)
                # - CompLength: 4 bytes (compressed length)
                # - OrigLength: 4 bytes (original length)
                # - OrigChecksum: 4 bytes (original checksum)
                
                tag = file_data[table_offset:table_offset+4]
                offset = struct.unpack('>I', file_data[table_offset+4:table_offset+8])[0]
                comp_length = struct.unpack('>I', file_data[table_offset+8:table_offset+12])[0]
                orig_length = struct.unpack('>I', file_data[table_offset+12:table_offset+16])[0]
                
                # Look for 'name' table
                if tag == b'name':
                    name_table_info = {
                        'offset': offset,
                        'comp_length': comp_length,
                        'orig_length': orig_length,
                    }
                    break
            
            # Extract name table data if found
            if name_table_info:
                name_offset = name_table_info['offset']
                comp_length = name_table_info['comp_length']
                orig_length = name_table_info['orig_length']
                
                if name_offset + comp_length <= len(file_data):
                    # Read compressed name table data
                    comp_data = file_data[name_offset:name_offset+comp_length]
                    
                    # Decompress (WOFF uses zlib compression)
                    try:
                        name_data = zlib.decompress(comp_data)
                        
                        # Parse name table
                        name_metadata = self._parse_name_table(name_data)
                        if name_metadata:
                            metadata.update(name_metadata)
                    except Exception:
                        # Decompression failed, skip
                        pass
            
            # Extract extended metadata if present
            meta_offset = struct.unpack('>I', file_data[24:28])[0]
            meta_length = struct.unpack('>I', file_data[28:32])[0]
            
            if meta_offset > 0 and meta_length > 0 and meta_offset + meta_length <= len(file_data):
                meta_data = file_data[meta_offset:meta_offset+meta_length]
                # Extended metadata is XML, but we'll just mark it as present
                metadata['WOFF:ExtendedMetadata'] = 'Present'
                metadata['WOFF:ExtendedMetadataSize'] = meta_length
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_name_table(self, name_data: bytes) -> Dict[str, Any]:
        """
        Parse OpenType/SFNT name table.
        
        Name table structure:
        - Format: 2 bytes
        - Count: 2 bytes (number of name records)
        - StringOffset: 2 bytes (offset to string data)
        - Name records (6 bytes each)
        - String data
        
        Args:
            name_data: Decompressed name table data
            
        Returns:
            Dictionary of name table metadata
        """
        metadata = {}
        
        try:
            if len(name_data) < 6:
                return metadata
            
            format = struct.unpack('>H', name_data[0:2])[0]
            count = struct.unpack('>H', name_data[2:4])[0]
            string_offset = struct.unpack('>H', name_data[4:6])[0]
            
            metadata['WOFF:NameTableFormat'] = format
            metadata['WOFF:NameTableCount'] = count
            
            # Parse name records
            name_records = {}
            
            for i in range(count):
                record_offset = 6 + (i * 12)
                if record_offset + 12 > len(name_data):
                    break
                
                # Name record structure (12 bytes):
                # - PlatformID: 2 bytes
                # - EncodingID: 2 bytes
                # - LanguageID: 2 bytes
                # - NameID: 2 bytes
                # - Length: 2 bytes
                # - Offset: 2 bytes
                
                platform_id = struct.unpack('>H', name_data[record_offset:record_offset+2])[0]
                encoding_id = struct.unpack('>H', name_data[record_offset+2:record_offset+4])[0]
                language_id = struct.unpack('>H', name_data[record_offset+4:record_offset+6])[0]
                name_id = struct.unpack('>H', name_data[record_offset+6:record_offset+8])[0]
                length = struct.unpack('>H', name_data[record_offset+8:record_offset+10])[0]
                offset = struct.unpack('>H', name_data[record_offset+10:record_offset+12])[0]
                
                # Extract string data
                string_start = string_offset + offset
                if string_start + length <= len(name_data):
                    string_data = name_data[string_start:string_start+length]
                    
                    # Try to decode as UTF-16-BE (common for name table)
                    try:
                        if encoding_id == 1:  # Unicode
                            string_value = string_data.decode('utf-16-be', errors='ignore')
                        else:
                            string_value = string_data.decode('utf-8', errors='ignore')
                        
                        # Map name IDs to common names
                        name_id_map = {
                            1: 'FontFamily',
                            2: 'FontSubfamily',
                            3: 'UniqueID',
                            4: 'FullName',
                            5: 'Version',
                            6: 'PostScriptName',
                            7: 'Trademark',
                            8: 'Manufacturer',
                            9: 'Designer',
                            10: 'Description',
                            11: 'VendorURL',
                            12: 'DesignerURL',
                            13: 'License',
                            14: 'LicenseURL',
                            16: 'TypographicFamily',
                            17: 'TypographicSubfamily',
                            18: 'CompatibleFullName',
                            19: 'SampleText',
                        }
                        
                        name_key = name_id_map.get(name_id, f'Name{name_id}')
                        
                        # Prefer Unicode platform (3) or Mac platform (1)
                        if platform_id == 3 or (platform_id == 1 and name_key not in name_records):
                            name_records[name_key] = string_value
                    
                    except Exception:
                        pass
            
            # Store name records
            for key, value in name_records.items():
                metadata[f'WOFF:{key}'] = value
            
            # Set common font metadata tags
            if 'FontFamily' in name_records:
                metadata['WOFF:FontFamily'] = name_records['FontFamily']
            if 'FontSubfamily' in name_records:
                metadata['WOFF:FontSubfamily'] = name_records['FontSubfamily']
            if 'FullName' in name_records:
                metadata['WOFF:FullName'] = name_records['FullName']
            if 'Version' in name_records:
                metadata['WOFF:Version'] = name_records['Version']
        
        except Exception:
            pass
        
        return metadata

