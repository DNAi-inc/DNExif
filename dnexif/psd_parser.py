# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
PSD (Photoshop Document) metadata parser

This module handles reading metadata from PSD files.
PSD files contain metadata in various formats including EXIF, XMP, and IPTC.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class PSDParser:
    """
    Parser for PSD (Photoshop Document) metadata.
    
    PSD files contain:
    - File header with image dimensions and color mode
    - Color mode data section
    - Image resources section (including EXIF, XMP, IPTC)
    - Layer and mask information
    - Image data
    """
    
    # PSD signature
    PSD_SIGNATURE = b'8BPS'
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize PSD parser.
        
        Args:
            file_path: Path to PSD file
            file_data: PSD file data bytes
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
        Parse PSD metadata.
        
        Returns:
            Dictionary of PSD metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 26:
                raise MetadataReadError("Invalid PSD file: too short")
            
            metadata = {}
            
            # Check PSD signature
            if file_data[:4] != self.PSD_SIGNATURE:
                raise MetadataReadError("Invalid PSD file: missing PSD signature")
            
            # Parse PSD header (26 bytes)
            # Offset 4: Version (2 bytes, should be 1)
            version = struct.unpack('>H', file_data[4:6])[0]
            metadata['PSD:Version'] = version
            
            # Offset 6: Reserved (6 bytes, should be zeros)
            reserved = file_data[6:12]
            if any(reserved):
                metadata['PSD:Reserved'] = reserved.hex()
            
            # Offset 12: Channels (2 bytes)
            channels = struct.unpack('>H', file_data[12:14])[0]
            metadata['PSD:Channels'] = channels
            
            # Offset 14: Height (4 bytes, big-endian)
            height = struct.unpack('>I', file_data[14:18])[0]
            metadata['PSD:ImageHeight'] = height
            
            # Offset 18: Width (4 bytes, big-endian)
            width = struct.unpack('>I', file_data[18:22])[0]
            metadata['PSD:ImageWidth'] = width
            
            # Offset 22: Depth (2 bytes)
            depth = struct.unpack('>H', file_data[22:24])[0]
            metadata['PSD:BitsPerChannel'] = depth
            
            # Offset 24: Color mode (2 bytes)
            color_mode = struct.unpack('>H', file_data[24:26])[0]
            color_modes = {
                0: 'Bitmap',
                1: 'Grayscale',
                2: 'Indexed',
                3: 'RGB',
                4: 'CMYK',
                7: 'Multichannel',
                8: 'Duotone',
                9: 'Lab'
            }
            metadata['PSD:ColorMode'] = color_modes.get(color_mode, f'Unknown ({color_mode})')
            
            # Parse color mode data section
            offset = 26
            if offset + 4 <= len(file_data):
                color_mode_data_length = struct.unpack('>I', file_data[offset:offset+4])[0]
                offset += 4 + color_mode_data_length
            
            # Parse image resources section
            if offset + 4 <= len(file_data):
                image_resources_length = struct.unpack('>I', file_data[offset:offset+4])[0]
                offset += 4
                
                # Parse image resources
                resources_end = offset + image_resources_length
                while offset < resources_end and offset + 8 <= len(file_data):
                    # Resource signature (4 bytes, should be '8BIM')
                    if file_data[offset:offset+4] != b'8BIM':
                        break
                    
                    offset += 4
                    
                    # Resource ID (2 bytes)
                    resource_id = struct.unpack('>H', file_data[offset:offset+2])[0]
                    offset += 2
                    
                    # Resource name (Pascal string: 1 byte length + name)
                    name_length = file_data[offset]
                    offset += 1
                    if name_length > 0:
                        # Name is padded to even length
                        name_padded = (name_length + 1) & ~1
                        resource_name = file_data[offset:offset+name_length].decode('ascii', errors='ignore')
                        offset += name_padded
                    else:
                        # Empty name, still need padding
                        offset += 1
                    
                    # Resource data size (4 bytes)
                    if offset + 4 > len(file_data):
                        break
                    resource_data_size = struct.unpack('>I', file_data[offset:offset+4])[0]
                    offset += 4
                    
                    # Resource data (padded to even length)
                    resource_data_padded = (resource_data_size + 1) & ~1
                    if offset + resource_data_size > len(file_data):
                        break
                    
                    resource_data = file_data[offset:offset+resource_data_size]
                    offset += resource_data_padded
                    
                    # Parse specific resource types
                    if resource_id in (1033, 1058):  # EXIF data (legacy + standard)
                        try:
                            exif_metadata = self._parse_exif_resource(resource_data)
                            metadata.update(exif_metadata)
                        except Exception:
                            pass
                    elif resource_id == 1028:  # IPTC data
                        try:
                            iptc_metadata = self._parse_iptc_resource(resource_data)
                            metadata.update(iptc_metadata)
                        except Exception:
                            pass
                    elif resource_id == 1060:  # XMP data
                        try:
                            xmp_metadata = self._parse_xmp_resource(resource_data)
                            metadata.update(xmp_metadata)
                        except Exception:
                            pass
                    elif resource_id == 1039:  # ICC profile
                        try:
                            icc_metadata = self._parse_icc_resource(resource_data)
                            metadata.update(icc_metadata)
                        except Exception:
                            pass
                    elif resource_id == 1005:  # Resolution info
                        try:
                            res_metadata = self._parse_resolution_resource(resource_data)
                            metadata.update(res_metadata)
                        except Exception:
                            pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse PSD metadata: {str(e)}")
    
    def _parse_exif_resource(self, data: bytes) -> Dict[str, Any]:
        """Parse EXIF data from image resource."""
        metadata = {}
        try:
            # EXIF data in PSD is typically in TIFF format (resource 1058).
            exif_data = data
            if data.startswith(b'\xFF\xE1') and len(data) > 10 and data[4:10] == b'Exif\x00\x00':
                exif_data = data[10:]
            elif data.startswith(b'Exif\x00\x00') and len(data) > 6:
                exif_data = data[6:]

            from dnexif.exif_parser import ExifParser
            if exif_data[:2] in (b'II', b'MM'):
                exif_parser = ExifParser(file_data=exif_data)
                exif_metadata = exif_parser.read()
                for key, value in exif_metadata.items():
                    if key.startswith('EXIF:'):
                        metadata[key] = value
                    else:
                        metadata[f'EXIF:{key}'] = value
            metadata['PSD:HasEXIF'] = True
            metadata['PSD:EXIFSize'] = len(data)
        except Exception:
            pass
        return metadata
    
    def _parse_iptc_resource(self, data: bytes) -> Dict[str, Any]:
        """Parse IPTC data from image resource."""
        metadata = {}
        try:
            from dnexif.iptc_parser import IPTCParser
            # IPTC data in PSD is typically in IIM format
            metadata['PSD:HasIPTC'] = True
            metadata['PSD:IPTCSize'] = len(data)
        except Exception:
            pass
        return metadata
    
    def _parse_xmp_resource(self, data: bytes) -> Dict[str, Any]:
        """Parse XMP data from image resource."""
        metadata = {}
        try:
            # XMP data is typically XML
            if data.startswith(b'<?xml') or data.startswith(b'<x:xmpmeta') or b'<?xpacket' in data:
                from dnexif.xmp_parser import XMPParser
                xmp_parser = XMPParser(file_data=data)
                xmp_metadata = xmp_parser.read()
                metadata.update(xmp_metadata)
                metadata['PSD:HasXMP'] = True
                metadata['PSD:XMPSize'] = len(data)
        except Exception:
            pass
        return metadata
    
    def _parse_icc_resource(self, data: bytes) -> Dict[str, Any]:
        """Parse ICC profile from image resource."""
        metadata = {}
        try:
            # ICC profile signature
            if len(data) >= 4 and data[:4] == b'acsp':
                metadata['PSD:HasICC'] = True
                metadata['PSD:ICCSize'] = len(data)
        except Exception:
            pass
        return metadata
    
    def _parse_resolution_resource(self, data: bytes) -> Dict[str, Any]:
        """Parse resolution info from image resource."""
        metadata = {}
        try:
            if len(data) >= 16:
                # Resolution info: 2 x 4-byte fixed-point numbers (numerator/denominator)
                # Horizontal resolution
                h_res_num = struct.unpack('>I', data[0:4])[0]
                h_res_den = struct.unpack('>I', data[4:8])[0]
                if h_res_den > 0:
                    h_resolution = h_res_num / h_res_den
                    metadata['PSD:HorizontalResolution'] = h_resolution
                    metadata['PSD:XResolution'] = h_resolution
                
                # Vertical resolution
                v_res_num = struct.unpack('>I', data[8:12])[0]
                v_res_den = struct.unpack('>I', data[12:16])[0]
                if v_res_den > 0:
                    v_resolution = v_res_num / v_res_den
                    metadata['PSD:VerticalResolution'] = v_resolution
                    metadata['PSD:YResolution'] = v_resolution
                
                # Unit (2 bytes)
                if len(data) >= 18:
                    unit = struct.unpack('>H', data[16:18])[0]
                    units = {1: 'inches', 2: 'cm'}
                    metadata['PSD:ResolutionUnit'] = units.get(unit, f'Unknown ({unit})')
        except Exception:
            pass
        return metadata
