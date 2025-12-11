# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
EXIF metadata writer

This module handles writing EXIF metadata to JPEG and TIFF files.
It rebuilds the EXIF APP1 segment with modified metadata.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List, Tuple
from enum import IntEnum
from dnexif.exceptions import MetadataWriteError
from dnexif.exif_parser import ExifTagType, TAG_SIZES
from dnexif.exif_tags import EXIF_TAG_NAMES


class EXIFWriter:
    """
    Writes EXIF metadata to image files.
    
    This class handles the complex task of rebuilding EXIF structures
    and embedding them into JPEG APP1 segments or TIFF files.
    
    Supports EXIF 2.3 and EXIF 3.0 specifications, including UTF-8 encoding
    for text fields in EXIF 3.0.
    """
    
    def __init__(self, endian: str = '<', exif_version: str = '0300'):
        """
        Initialize EXIF writer.
        
        Args:
            endian: Byte order ('<' for little-endian, '>' for big-endian)
            exif_version: EXIF version to use ('0230' for 2.30, '0300' for 3.0)
                          Defaults to '0300' (EXIF 3.0) for UTF-8 support
        """
        self.endian = endian
        # Build tag_names_to_ids, prioritizing standard IFD0 tags first
        # Standard IFD0 tags are in range 0x0100-0x01FF, then standard EXIF tags < 0x9000
        # Manufacturer tags are usually >= 0x9000
        self.tag_names_to_ids = {}
        
        # Standard IFD0 tag mappings (most common tags)
        # These are the standard EXIF IFD0 tags that should take precedence
        standard_ifd0_tags = {
            'Artist': 0x013B,  # Standard IFD0 Artist tag
            'Make': 0x010F,
            'Model': 0x0110,
            'Orientation': 0x0112,
            'XResolution': 0x011A,
            'YResolution': 0x011B,
            'ResolutionUnit': 0x0128,
            'Software': 0x0131,
            'DateTime': 0x0132,
            'HostComputer': 0x013C,
        }
        
        # First pass: add standard IFD0 tags (these take highest priority)
        for tag_name, tag_id in standard_ifd0_tags.items():
            self.tag_names_to_ids[tag_name] = tag_id
        
        # Second pass: add all standard tags (ID < 0x9000) if not already present
        for tag_id, tag_name in EXIF_TAG_NAMES.items():
            if tag_id < 0x9000:  # Standard EXIF tags
                if tag_name not in self.tag_names_to_ids:
                    self.tag_names_to_ids[tag_name] = tag_id
        
        # Third pass: add manufacturer tags only if not already present
        for tag_id, tag_name in EXIF_TAG_NAMES.items():
            if tag_id >= 0x9000:  # Manufacturer-specific tags
                if tag_name not in self.tag_names_to_ids:
                    self.tag_names_to_ids[tag_name] = tag_id
        self.exif_version = exif_version
        self.supports_utf8 = exif_version >= '0300'  # EXIF 3.0+ supports UTF-8
    
    def build_exif_segment(
        self,
        metadata: Dict[str, Any],
        existing_data: Optional[bytes] = None
    ) -> bytes:
        """
        Build a complete EXIF APP1 segment from metadata dictionary.
        
        Args:
            metadata: Dictionary of EXIF tags (e.g., {'EXIF:Make': 'Canon'})
            existing_data: Optional existing EXIF data to preserve structure
            
        Returns:
            Complete EXIF APP1 segment as bytes
        """
        # Filter EXIF tags from metadata
        exif_tags = {}
        for key, value in metadata.items():
            if key.startswith('EXIF:') or key.startswith('IFD0:') or key.startswith('GPS:'):
                exif_tags[key] = value
        
        if not exif_tags:
            return b''
        
        # Build TIFF header
        tiff_header = self._build_tiff_header()
        
        # Build IFD0 (Image IFD)
        ifd0_tags, ifd0_data = self._build_ifd(exif_tags, ifd_type='IFD0')
        
        # Build EXIF IFD
        exif_ifd_tags, exif_ifd_data = self._build_ifd(exif_tags, ifd_type='EXIF')
        
        # Ensure ExifVersion tag is present (required for EXIF compliance)
        # Add ExifVersion if not already present
        has_exif_version = any(tag.get('id') == 0x9000 for tag in exif_ifd_tags)
        if not has_exif_version:
            # ExifVersion is stored as ASCII string (e.g., "0300" for EXIF 3.0, "0230" for 2.30)
            # Format: 4 ASCII characters representing major.minor version
            version_bytes = self.exif_version.encode('ascii') + b'\x00'
            exif_version_tag = {
                'id': 0x9000,  # ExifVersion
                'type': ExifTagType.ASCII.value,
                'count': len(version_bytes),
                'value': len(exif_ifd_data),  # Offset to data
                'data': b''
            }
            exif_ifd_tags.append(exif_version_tag)
            exif_ifd_data = exif_ifd_data + version_bytes
        
        # Build GPS IFD
        gps_ifd_tags, gps_ifd_data = self._build_ifd(exif_tags, ifd_type='GPS')
        
        # Recalculate offsets after adding ExifVersion tag
        base_offset = len(tiff_header)
        ifd0_offset = base_offset
        ifd0_data_offset = ifd0_offset + 2 + (len(ifd0_tags) * 12) + 4
        exif_ifd_offset = ifd0_data_offset + len(ifd0_data)
        exif_ifd_data_offset = exif_ifd_offset + 2 + (len(exif_ifd_tags) * 12) + 4
        gps_ifd_offset = exif_ifd_data_offset + len(exif_ifd_data)
        gps_ifd_data_offset = gps_ifd_offset + 2 + (len(gps_ifd_tags) * 12) + 4
        
        # Build complete EXIF structure
        exif_data = bytearray()
        exif_data.extend(tiff_header)
        
        # Write IFD0
        exif_data.extend(self._write_ifd(ifd0_tags, ifd0_data, ifd0_data_offset))
        exif_data.extend(ifd0_data)
        
        # Write EXIF IFD
        exif_data.extend(self._write_ifd(exif_ifd_tags, exif_ifd_data, exif_ifd_data_offset))
        exif_data.extend(exif_ifd_data)
        
        # Write GPS IFD if present
        if gps_ifd_tags:
            exif_data.extend(self._write_ifd(gps_ifd_tags, gps_ifd_data, gps_ifd_data_offset))
            exif_data.extend(gps_ifd_data)
        
        # Build JPEG APP1 segment
        app1_segment = self._build_app1_segment(exif_data)
        
        return app1_segment
    
    def _build_tiff_header(self) -> bytes:
        """
        Build TIFF header (required for EXIF).
        
        Returns:
            TIFF header bytes
        """
        # Byte order
        if self.endian == '<':
            header = b'II'
        else:
            header = b'MM'
        
        # TIFF magic number (42)
        header += struct.pack(f'{self.endian}H', 42)
        
        # Offset to first IFD (will be updated)
        header += struct.pack(f'{self.endian}I', 8)
        
        return header
    
    def _build_ifd(
        self,
        metadata: Dict[str, Any],
        ifd_type: str = 'IFD0'
    ) -> Tuple[List[Dict[str, Any]], bytes]:
        """
        Build an IFD (Image File Directory) structure.
        
        Args:
            metadata: Dictionary of metadata tags
            ifd_type: Type of IFD ('IFD0', 'EXIF', 'GPS', 'Interop')
            
        Returns:
            Tuple of (list of tag entries, data bytes)
        """
        tags = []
        data = bytearray()
        data_offset = 0
        
        for key, value in metadata.items():
            namespace = key.split(':', 1)[0]
            tag_name = key.split(':', 1)[1] if ':' in key else key
            
            # Filter by IFD type
            if ifd_type == 'IFD0' and namespace not in ('IFD0', 'EXIF'):
                continue
            elif ifd_type == 'EXIF' and namespace != 'EXIF':
                continue
            elif ifd_type == 'GPS' and namespace != 'GPS':
                continue
            
            # Get tag ID
            if namespace == 'IFD0':
                tag_id = self.tag_names_to_ids.get(tag_name)
            elif namespace == 'EXIF':
                tag_id = self.tag_names_to_ids.get(tag_name)
            elif namespace == 'GPS':
                tag_id = self.tag_names_to_ids.get(f'GPS{tag_name}')
            else:
                continue
            
            if tag_id is None:
                continue  # Unknown tag, skip
            
            # Determine tag type and encode value
            tag_type, encoded_value, count = self._encode_tag_value(value)
            
            if tag_type is None:
                continue
            
            # If value fits in 4 bytes, store inline
            value_size = TAG_SIZES.get(ExifTagType(tag_type), 1) * count
            if value_size <= 4:
                # Store inline - keep bytes directly in the tag entry
                inline_value = encoded_value
                data_bytes = b''
                is_inline = True
            else:
                # Store at offset - remember the offset within the data area
                inline_value = data_offset
                data_bytes = encoded_value
                data_offset += len(encoded_value)
                is_inline = False
            
            tags.append({
                'id': tag_id,
                'type': tag_type,
                'count': count,
                'value': inline_value,  # Either inline bytes or offset within the data section
                'data': data_bytes,     # Actual data bytes if stored out-of-line
                'inline': is_inline
            })
            
            if data_bytes:
                data.extend(data_bytes)
        
        return tags, bytes(data)
    
    def _encode_tag_value(self, value: Any) -> Tuple[Optional[int], bytes, int]:
        """
        Encode a tag value to binary format.
        
        Args:
            value: Tag value (various types)
            
        Returns:
            Tuple of (tag_type, encoded_bytes, count)
        """
        if isinstance(value, str):
            # EXIF 3.0 supports UTF-8, earlier versions use ASCII
            if self.supports_utf8:
                # Try to encode as UTF-8
                # Check if string contains non-ASCII characters
                try:
                    value.encode('ascii')
                    # Pure ASCII - encode as ASCII for compatibility
                    encoded = value.encode('ascii', errors='replace') + b'\x00'
                except UnicodeEncodeError:
                    # Contains non-ASCII - encode as UTF-8 (EXIF 3.0)
                    encoded = value.encode('utf-8', errors='replace') + b'\x00'
            else:
                # EXIF 2.3 and earlier: ASCII only
                encoded = value.encode('ascii', errors='replace') + b'\x00'
            return ExifTagType.ASCII.value, encoded, len(encoded)
        
        elif isinstance(value, int):
            # Try to fit in SHORT (unsigned, 0-65535) first, then LONG
            if 0 <= value <= 65535:
                return ExifTagType.SHORT.value, struct.pack(f'{self.endian}H', value), 1
            else:
                return ExifTagType.LONG.value, struct.pack(f'{self.endian}I', value), 1
        
        elif isinstance(value, float):
            # RATIONAL (numerator/denominator)
            # Convert to rational approximation
            numerator = int(value * 10000)
            denominator = 10000
            encoded = struct.pack(f'{self.endian}II', numerator, denominator)
            return ExifTagType.RATIONAL.value, encoded, 1
        
        elif isinstance(value, (list, tuple)):
            if not value:
                return None, b'', 0
            
            # Determine type from first element
            first = value[0]
            if isinstance(first, int):
                # Check if all values fit in unsigned short (0-65535) for SHORT type
                if all(0 <= v <= 65535 for v in value):
                    encoded = struct.pack(f'{self.endian}{len(value)}H', *value)
                    return ExifTagType.SHORT.value, encoded, len(value)
                # For negative values or values > 65535, use LONG
                # Clamp values to 32-bit unsigned int range
                else:
                    clamped_values = [v & 0xFFFFFFFF for v in value]
                    encoded = struct.pack(f'{self.endian}{len(clamped_values)}I', *clamped_values)
                    return ExifTagType.LONG.value, encoded, len(clamped_values)
            elif isinstance(first, str):
                # Array of strings - join with null separator
                # EXIF 3.0 supports UTF-8, earlier versions use ASCII
                if self.supports_utf8:
                    # Check if any string contains non-ASCII
                    has_non_ascii = any(not all(ord(c) < 128 for c in v) for v in value)
                    if has_non_ascii:
                        # Use UTF-8 encoding
                        encoded = b'\x00'.join(v.encode('utf-8', errors='replace') for v in value) + b'\x00'
                    else:
                        # Pure ASCII - use ASCII for compatibility
                        encoded = b'\x00'.join(v.encode('ascii', errors='replace') for v in value) + b'\x00'
                else:
                    # EXIF 2.3 and earlier: ASCII only
                    encoded = b'\x00'.join(v.encode('ascii', errors='replace') for v in value) + b'\x00'
                return ExifTagType.ASCII.value, encoded, len(encoded)
            else:
                return None, b'', 0
        
        else:
            return None, b'', 0
    
    def _write_ifd(
        self,
        tags: List[Dict[str, Any]],
        data: bytes,
        data_offset: int
    ) -> bytes:
        """
        Write an IFD structure.
        
        Args:
            tags: List of tag dictionaries
            data: Additional data bytes
            data_offset: Offset where data starts
            
        Returns:
            IFD bytes
        """
        ifd = bytearray()
        
        # Number of entries
        ifd.extend(struct.pack(f'{self.endian}H', len(tags)))
        
        # Write tag entries
        for tag in tags:
            # Ensure tag ID and type are within unsigned short range (0-65535)
            tag_id = int(tag['id']) & 0xFFFF  # Clamp to 16 bits
            tag_type = int(tag['type']) & 0xFFFF  # Clamp to 16 bits
            tag_count = int(tag['count']) & 0xFFFFFFFF  # Clamp to 32 bits (unsigned int)
            
            ifd.extend(struct.pack(f'{self.endian}H', tag_id))  # Tag ID
            ifd.extend(struct.pack(f'{self.endian}H', tag_type))  # Type
            ifd.extend(struct.pack(f'{self.endian}I', tag_count))  # Count
            
            is_inline = tag.get('inline', False)
            
            if not is_inline:
                # Value stored at offset - tag['value'] is the offset into the data area
                offset_value = tag['value'] if isinstance(tag['value'], int) else 0
                # Clamp offset to 32-bit unsigned int range
                final_offset = (data_offset + offset_value) & 0xFFFFFFFF
                ifd.extend(struct.pack(f'{self.endian}I', final_offset))
            else:
                # Inline value - tag['value'] contains the actual bytes
                value_bytes = tag['value'] if isinstance(tag['value'], bytes) else b''
                # Pad to 4 bytes for inline storage
                if len(value_bytes) < 4:
                    value_bytes = value_bytes.ljust(4, b'\x00')
                ifd.extend(value_bytes[:4])
        
        # Offset to next IFD (0 = no more IFDs)
        ifd.extend(struct.pack(f'{self.endian}I', 0))
        
        return bytes(ifd)
    
    def _build_app1_segment(self, exif_data: bytes) -> bytes:
        """
        Build JPEG APP1 segment containing EXIF data.
        
        Args:
            exif_data: EXIF data bytes
            
        Returns:
            Complete APP1 segment
        """
        # APP1 marker
        app1 = bytearray()
        app1.extend(b'\xFF\xE1')
        
        # Length (2 bytes for length + EXIF data)
        length = 2 + len(b'Exif\x00\x00') + len(exif_data)
        app1.extend(struct.pack('>H', length))
        
        # EXIF identifier
        app1.extend(b'Exif\x00\x00')
        
        # EXIF data
        app1.extend(exif_data)
        
        return bytes(app1)

