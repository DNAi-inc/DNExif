# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
IPTC metadata writer

This module handles writing IPTC metadata to JPEG files.
IPTC data is typically embedded in JPEG APP13 segments in Photoshop format.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List
from dnexif.exceptions import MetadataWriteError
from dnexif.iptc_parser import IPTC_TAG_NAMES


class IPTCWriter:
    """
    Writes IPTC metadata to image files.
    
    IPTC data is embedded in JPEG APP13 segments, typically in Photoshop format.
    """
    
    def __init__(self):
        """Initialize IPTC writer."""
        # Build mapping from tag names to dataset numbers
        # IPTC format: Record marker (0x1C) + Dataset number (1 byte, 0-255) + Data type + Length + Data
        # The parser doesn't read record numbers, so we only need dataset numbers
        # Dataset numbers must be 0-255
        self.tag_names_to_dataset = {}
        
        # Build reverse lookup from IPTC_TAG_NAMES
        # Only use dataset numbers < 256 (valid byte range)
        # For duplicate tag names, prefer Record 2 (Application Record) values
        for dataset, tag_name in IPTC_TAG_NAMES.items():
            if dataset < 256:
                # Only add if not already present (prefer first occurrence, which is usually Record 2)
                if tag_name not in self.tag_names_to_dataset:
                    self.tag_names_to_dataset[tag_name] = dataset
    
    def build_iptc_data(self, metadata: Dict[str, Any]) -> bytes:
        """
        Build IPTC data block from metadata dictionary.
        
        Args:
            metadata: Dictionary of IPTC tags (e.g., {'IPTC:Keywords': 'nature, landscape'})
            
        Returns:
            IPTC data block as bytes
        """
        # Filter IPTC tags
        iptc_tags = {
            k.split(':', 1)[1] if ':' in k else k: v
            for k, v in metadata.items()
            if k.startswith('IPTC:') or (':' not in k and k in self.tag_names_to_dataset)
        }
        
        if not iptc_tags:
            return b''
        
        # Build IPTC data block
        iptc_data = bytearray()
        
        for tag_name, value in iptc_tags.items():
            # Get dataset number
            dataset = self.tag_names_to_dataset.get(tag_name)
            if dataset is None:
                continue  # Unknown tag, skip
            
            # Ensure dataset is in valid range (0-255)
            if dataset < 0 or dataset > 255:
                continue  # Invalid dataset number, skip
            
            # Handle multiple values (lists)
            values = value if isinstance(value, (list, tuple)) else [value]
            
            for val in values:
                # Convert value to string
                if isinstance(val, (int, float)):
                    val = str(val)
                elif not isinstance(val, str):
                    val = str(val)
                
                # Encode as UTF-8
                data_bytes = val.encode('utf-8', errors='replace')
                
                # IPTC record structure (matching parser format):
                # - 1 byte: Record marker (0x1C)
                # - 1 byte: Dataset number (0-255)
                # - 1 byte: Data type (2 = String)
                # - 2 bytes: Data length (big-endian)
                # - N bytes: Data
                iptc_data.append(0x1C)  # Record marker
                iptc_data.append(dataset)  # Dataset number
                iptc_data.append(2)  # Data type: String
                iptc_data.extend(struct.pack('>H', len(data_bytes)))  # Length
                iptc_data.extend(data_bytes)  # Data
        
        return bytes(iptc_data)
    
    def build_photoshop_app13_segment(self, iptc_data: bytes) -> bytes:
        """
        Build JPEG APP13 segment containing IPTC data in Photoshop format.
        
        Args:
            iptc_data: Raw IPTC data block
            
        Returns:
            Complete APP13 segment
        """
        if not iptc_data:
            return b''
        
        # Build Photoshop format segment
        segment = bytearray()
        
        # APP13 marker
        segment.extend(b'\xFF\xED')
        
        # Photoshop header: "Photoshop 3.0\x00"
        photoshop_header = b'Photoshop 3.0\x00'
        
        # IPTC resource block:
        # - 4 bytes: "8BIM"
        # - 2 bytes: Resource ID (0x0404 for IPTC)
        # - Variable: Resource name (pascal string, padded to even length)
        # - 4 bytes: Resource size
        # - N bytes: Resource data (IPTC)
        
        resource_id = 0x0404  # IPTC-NAA resource
        resource_name_len = 0  # Empty name
        resource_name = b'\x00'  # Name length byte (0 = empty name)
        # Name must be padded to even length - if name_len is even (including 0), add 1 byte padding
        if resource_name_len % 2 == 0:
            resource_name += b'\x00'  # Add padding byte
        resource_size = len(iptc_data)
        
        # Calculate segment length
        # 2 (length field) + header + 4 (8BIM) + 2 (ID) + name (1 byte len + padding) + 4 (size) + data
        segment_length = (
            2 +  # Length field itself
            len(photoshop_header) +
            4 +  # 8BIM
            2 +  # Resource ID
            len(resource_name) +  # Resource name (length byte + padding if needed)
            4 +  # Resource size
            resource_size
        )
        
        # Write length (big-endian)
        segment.extend(struct.pack('>H', segment_length))
        
        # Write Photoshop header
        segment.extend(photoshop_header)
        
        # Write resource block
        segment.extend(b'8BIM')  # Resource signature
        segment.extend(struct.pack('>H', resource_id))  # Resource ID
        segment.extend(resource_name)  # Resource name (length byte + padding)
        segment.extend(struct.pack('>I', resource_size))  # Resource size
        segment.extend(iptc_data)  # IPTC data
        
        return bytes(segment)

