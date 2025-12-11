# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
PSD metadata writer

This module provides metadata writing for PSD files.
PSD files contain metadata in image resources section.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataWriteError
from dnexif.exif_writer import EXIFWriter
from dnexif.xmp_writer import XMPWriter
from dnexif.iptc_writer import IPTCWriter


class PSDWriter:
    """
    Writer for PSD metadata.
    
    PSD files contain metadata in:
    - Image resources section (EXIF, XMP, IPTC)
    - File header (dimensions, color mode)
    """
    
    # Image resource IDs
    RESOURCE_EXIF = 1058
    RESOURCE_XMP = 1060
    RESOURCE_IPTC = 1028
    
    def __init__(self, exif_version: str = '0300'):
        """
        Initialize PSD writer.
        
        Args:
            exif_version: EXIF version to use (default: '0300' for EXIF 3.0)
        """
        self.exif_writer = EXIFWriter(exif_version=exif_version)
        self.xmp_writer = XMPWriter()
        self.iptc_writer = IPTCWriter()
    
    def write_psd(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to PSD file.
        
        Args:
            file_path: Path to input PSD file
            metadata: Dictionary of metadata to write
            output_path: Path to output PSD file
            
        Raises:
            MetadataWriteError: If writing fails
        """
        try:
            with open(file_path, 'rb') as f:
                psd_data = f.read()
            
            if len(psd_data) < 26:
                raise MetadataWriteError("Invalid PSD file: too short")
            
            if psd_data[:4] != b'8BPS':
                raise MetadataWriteError("Invalid PSD file: missing PSD signature")
            
            # Separate metadata by type
            exif_metadata = {}
            xmp_metadata = {}
            iptc_metadata = {}
            psd_metadata = {}
            
            for key, value in metadata.items():
                if key.startswith('EXIF:'):
                    exif_metadata[key[5:]] = value
                elif key.startswith('XMP:'):
                    xmp_metadata[key[4:]] = value
                elif key.startswith('IPTC:'):
                    iptc_metadata[key[5:]] = value
                elif key.startswith('PSD:'):
                    psd_metadata[key[4:]] = value
                else:
                    # Default to EXIF for unknown prefixes
                    exif_metadata[key] = value
            
            # Find image resources section
            # PSD structure: Header (26 bytes) -> Color Mode Data -> Image Resources -> Layers -> Image Data
            header_size = 26
            color_mode_data_size = struct.unpack('>I', psd_data[header_size:header_size+4])[0]
            color_mode_data_start = header_size + 4
            color_mode_data_end = color_mode_data_start + color_mode_data_size
            
            # Image resources section starts after color mode data
            image_resources_start = color_mode_data_end
            if image_resources_start + 4 > len(psd_data):
                raise MetadataWriteError("Invalid PSD file: missing image resources section")
            
            image_resources_size = struct.unpack('>I', psd_data[image_resources_start:image_resources_start+4])[0]
            image_resources_end = image_resources_start + 4 + image_resources_size
            
            # Parse existing image resources
            resources = self._parse_image_resources(psd_data[image_resources_start+4:image_resources_end])
            
            # Update or add resources
            if exif_metadata:
                exif_data = self.exif_writer.build_exif_segment(exif_metadata)
                resources[self.RESOURCE_EXIF] = exif_data
            
            if xmp_metadata:
                xmp_packet = self.xmp_writer.build_xmp_packet(xmp_metadata)
                resources[self.RESOURCE_XMP] = xmp_packet.encode('utf-8')
            
            if iptc_metadata:
                iptc_data = self.iptc_writer.build_iptc_segment(iptc_metadata)
                resources[self.RESOURCE_IPTC] = iptc_data
            
            # Rebuild image resources section
            new_resources_data = self._build_image_resources(resources)
            new_resources_size = len(new_resources_data)
            
            # Rebuild PSD file
            new_psd = (
                psd_data[:image_resources_start] +
                struct.pack('>I', new_resources_size) +
                new_resources_data +
                psd_data[image_resources_end:]
            )
            
            # Write output file
            with open(output_path, 'wb') as f:
                f.write(new_psd)
                
        except Exception as e:
            raise MetadataWriteError(f"Failed to write PSD metadata: {str(e)}")
    
    def _parse_image_resources(self, resources_data: bytes) -> Dict[int, bytes]:
        """
        Parse image resources section.
        
        Args:
            resources_data: Image resources data (without size header)
            
        Returns:
            Dictionary mapping resource ID to resource data
        """
        resources = {}
        offset = 0
        
        while offset < len(resources_data) - 8:
            # Resource structure:
            # Signature (4 bytes, should be '8BIM')
            # Resource ID (2 bytes, big-endian)
            # Name (Pascal string: 1 byte length + name)
            # Data size (4 bytes, big-endian)
            # Data (data_size bytes)
            
            if offset + 4 > len(resources_data):
                break
            
            signature = resources_data[offset:offset+4]
            if signature != b'8BIM':
                break
            
            if offset + 10 > len(resources_data):
                break
            
            resource_id = struct.unpack('>H', resources_data[offset+4:offset+6])[0]
            
            # Read name (Pascal string)
            name_len = resources_data[offset+6]
            name_start = offset + 7
            name_end = name_start + name_len
            if name_len % 2 == 1:  # Pascal strings are padded to even length
                name_end += 1
            
            if name_end > len(resources_data):
                break
            
            # Read data size
            data_start = name_end
            if data_start + 4 > len(resources_data):
                break
            
            data_size = struct.unpack('>I', resources_data[data_start:data_start+4])[0]
            data_start += 4
            
            if data_size % 2 == 1:  # Data is padded to even length
                data_size += 1
            
            data_end = data_start + data_size
            if data_end > len(resources_data):
                break
            
            # Extract resource data
            resource_data = resources_data[data_start:data_end]
            resources[resource_id] = resource_data
            
            offset = data_end
        
        return resources
    
    def _build_image_resources(self, resources: Dict[int, bytes]) -> bytes:
        """
        Build image resources section.
        
        Args:
            resources: Dictionary mapping resource ID to resource data
            
        Returns:
            Image resources data (without size header)
        """
        resources_data = b''
        
        for resource_id, resource_data in sorted(resources.items()):
            # Resource structure
            signature = b'8BIM'
            resource_id_bytes = struct.pack('>H', resource_id)
            
            # Name (empty Pascal string)
            name = b'\x00'
            
            # Data size
            data_size = len(resource_data)
            if data_size % 2 == 1:  # Pad to even length
                resource_data += b'\x00'
                data_size += 1
            
            data_size_bytes = struct.pack('>I', data_size)
            
            # Build resource
            resource = signature + resource_id_bytes + name + data_size_bytes + resource_data
            resources_data += resource
        
        return resources_data

