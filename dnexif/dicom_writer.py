# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
DICOM (Digital Imaging and Communications in Medicine) metadata writer

This module handles writing metadata to DICOM files.
DICOM is a standard for medical imaging and related information.

Copyright 2025 DNAi inc.
"""

import struct
import re
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from dnexif.exceptions import MetadataWriteError
from dnexif.dicom_parser import DICOMParser
from dnexif.dicom_data_elements import (
    DICOM_DATA_ELEMENTS,
    get_dicom_element_info,
    DICOM_KEYWORD_TO_TAG
)


class DICOMWriter:
    """
    Writer for DICOM metadata.
    
    DICOM files have a complex structure with:
    - 128-byte preamble (optional, usually all zeros)
    - "DICM" signature
    - File Meta Information (group 0002)
    - Data Set (actual DICOM data elements)
    
    Writing DICOM files requires careful handling of:
    - Transfer Syntax (affects byte order and VR encoding)
    - Explicit vs Implicit VR
    - Sequences and nested structures
    - Undefined length sequences
    """
    
    def __init__(self):
        """Initialize DICOM writer."""
        pass
    
    def write_dicom(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to DICOM file.
        
        Args:
            file_path: Path to input DICOM file
            metadata: Dictionary of metadata to write
            output_path: Path to output DICOM file
            
        Raises:
            MetadataWriteError: If writing fails
        """
        try:
            # Read original file
            with open(file_path, 'rb') as f:
                original_data = f.read()
            
            # Parse original file to get structure
            parser = DICOMParser(file_path=file_path)
            original_metadata = parser.parse()
            
            # Determine transfer syntax and byte order
            transfer_syntax = self._get_transfer_syntax(original_data)
            is_little_endian = self._is_little_endian(transfer_syntax)
            explicit_vr = self._is_explicit_vr(transfer_syntax)
            
            # Merge metadata
            updated_metadata = original_metadata.copy()
            updated_metadata.update(metadata)

            # Sync duplicate tag formats (keyword <-> numeric)
            # When user updates DICOM:PatientName, also update DICOM:(0010,0010)
            self._sync_duplicate_tags(updated_metadata, metadata)

            # Preserve pixel data from original file BEFORE filtering
            # We always use the original binary pixel data, not the parsed representation
            pixel_data = self._extract_pixel_data(original_data)

            # Preserve sequences from original file
            # Sequences have complex nested structures that we preserve as raw bytes
            sequences = self._extract_sequences(original_data, original_metadata)

            # Remove tags marked for deletion (None values) and pixel data tag
            # Pixel data will be appended as raw bytes at the end
            tag_keys_to_skip = sequences.get('_tag_keys', set())

            updated_metadata = {
                k: v for k, v in updated_metadata.items()
                if v is not None and k.startswith('DICOM:') and
                not k.startswith('DICOM:PixelData') and
                not k.startswith('DICOM:(7FE0,0010)') and
                k not in tag_keys_to_skip  # Skip sequence tags (written as raw bytes)
            }

            # Add pixel data marker for later appending (if extracted successfully)
            if pixel_data:
                updated_metadata['_preserve_pixel_data'] = pixel_data

            # Add sequence markers and placeholder entries for proper positioning
            if sequences.get('_sequences'):
                updated_metadata['_preserve_sequences'] = sequences['_sequences']
                # Add placeholder entries so sequences appear in grouped_metadata
                for (group, element) in sequences['_sequences'].keys():
                    tag_key = f'DICOM:({group:04X},{element:04X})'
                    updated_metadata[tag_key] = '__PRESERVED_SEQUENCE__'
            
            # Build new DICOM file
            new_dicom_data = self._build_dicom_file(
                updated_metadata,
                original_data,
                is_little_endian,
                explicit_vr
            )
            
            # Write output file
            with open(output_path, 'wb') as f:
                f.write(new_dicom_data)
                
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to write DICOM file: {str(e)}")
    
    def _sync_duplicate_tags(
        self,
        updated_metadata: Dict[str, Any],
        user_metadata: Dict[str, Any]
    ) -> None:
        """
        Sync duplicate tag formats (keyword <-> numeric) when user updates a tag.

        The parser creates both DICOM:PatientName and DICOM:(0010,0010) for the same tag.
        When a user updates one format, we need to update the other to prevent conflicts.

        IMPORTANT: For UID tags, the numeric format contains the actual UID value,
        while the keyword format may contain a human-readable name. We preserve UIDs.

        Args:
            updated_metadata: Full merged metadata dictionary (modified in place)
            user_metadata: User-provided metadata updates
        """
        for key, value in user_metadata.items():
            if not key.startswith('DICOM:'):
                continue

            tag_name = key[6:]  # Remove 'DICOM:' prefix

            # Skip annotation tags
            if ':' in tag_name:
                continue

            # Parse to get group and element
            group, element = self._parse_tag_key(tag_name)
            if group is None or element is None:
                continue

            # Generate both formats
            numeric_key = f'DICOM:({group:04X},{element:04X})'

            # Find keyword format
            keyword_key = None
            element_info = get_dicom_element_info(group, element)
            if element_info and element_info.keyword:
                keyword_key = f'DICOM:{element_info.keyword}'

            # For UID tags (VR='UI'), prefer numeric format value (actual UID)
            # Keyword format may have human-readable name
            if element_info and element_info.vr == 'UI':
                # Use numeric format value if available
                if numeric_key in updated_metadata:
                    correct_value = updated_metadata[numeric_key]
                    # Update keyword format to match numeric
                    if keyword_key and keyword_key in updated_metadata:
                        updated_metadata[keyword_key] = correct_value
            else:
                # For non-UID tags, update both formats to match user's value
                if numeric_key in updated_metadata:
                    updated_metadata[numeric_key] = value
                if keyword_key and keyword_key in updated_metadata:
                    updated_metadata[keyword_key] = value

    def _get_transfer_syntax(self, data: bytes) -> str:
        """
        Get Transfer Syntax UID from file.
        
        Args:
            data: DICOM file data
            
        Returns:
            Transfer Syntax UID or default
        """
        try:
            # Look for Transfer Syntax UID in File Meta Information (0002,0010)
            parser = DICOMParser(file_data=data)
            metadata = parser.parse()
            transfer_syntax = metadata.get('DICOM:TransferSyntaxUID', '')
            if transfer_syntax:
                return transfer_syntax
        except:
            pass
        
        # Default to Explicit VR Little Endian
        return '1.2.840.10008.1.2.1'
    
    def _is_little_endian(self, transfer_syntax: str) -> bool:
        """Check if transfer syntax uses little endian byte order."""
        # Most transfer syntaxes use little endian
        # Big endian syntaxes: 1.2.840.10008.1.2.2 (Explicit VR Big Endian)
        return transfer_syntax != '1.2.840.10008.1.2.2'
    
    def _is_explicit_vr(self, transfer_syntax: str) -> bool:
        """Check if transfer syntax uses explicit VR."""
        # Implicit VR: 1.2.840.10008.1.2 (Implicit VR Little Endian)
        return transfer_syntax != '1.2.840.10008.1.2'
    
    def _build_dicom_file(
        self,
        metadata: Dict[str, Any],
        original_data: bytes,
        is_little_endian: bool,
        explicit_vr: bool
    ) -> bytes:
        """
        Build new DICOM file with updated metadata.
        
        Args:
            metadata: Updated metadata dictionary
            original_data: Original DICOM file data
            is_little_endian: Byte order
            explicit_vr: Whether to use explicit VR
            
        Returns:
            New DICOM file data
        """
        # Start with preamble (128 bytes of zeros)
        preamble = b'\x00' * 128
        
        # Add DICM signature
        dicm_signature = b'DICM'
        
        # Build File Meta Information (group 0002)
        file_meta = self._build_file_meta_information(metadata, is_little_endian, explicit_vr)
        
        # Update FileMetaInfoGroupLength (0002,0000) - must be first element
        # Calculate length of all file meta elements except the group length itself
        file_meta_length = len(file_meta)
        # Find and update the group length element
        file_meta = self._update_file_meta_group_length(file_meta, file_meta_length, is_little_endian, explicit_vr)
        
        # Build Data Set (all other groups)
        data_set = self._build_data_set(metadata, is_little_endian, explicit_vr)
        
        # Append preserved pixel data if it exists
        pixel_data = metadata.get('_preserve_pixel_data')
        if pixel_data:
            data_set += pixel_data
        
        # Combine all parts
        return preamble + dicm_signature + file_meta + data_set
    
    def _build_file_meta_information(
        self,
        metadata: Dict[str, Any],
        is_little_endian: bool,
        explicit_vr: bool
    ) -> bytes:
        """
        Build File Meta Information group (0002,xxxx).

        Args:
            metadata: Metadata dictionary
            is_little_endian: Byte order
            explicit_vr: Whether to use explicit VR

        Returns:
            File Meta Information bytes
        """
        # Collect all group 0002 tags from metadata (de-duplicated)
        seen_tags = set()  # Track (group, element) to avoid duplicates
        file_meta_tags = []

        # Get all tags that belong to File Meta Information (group 0002)
        for key, value in metadata.items():
            if key.startswith('DICOM:'):
                tag_name = key[6:]

                # Skip internal markers, metadata annotations, and the group length itself
                if (tag_name in ['HasDICOM', 'ElementCount', 'FileMetaInformationGroupLength',
                                'FileMetaInfoGroupLength'] or
                    ':' in tag_name or  # Skip annotation tags like "PatientName:VR"
                    tag_name.startswith('(0002,0000)')):  # Skip numeric format of group length
                    continue

                # Parse the tag to get group/element
                group, element = self._parse_tag_key(tag_name)

                # Only include group 0002 tags, and avoid duplicates
                if group == 0x0002 and element is not None:
                    tag_id = (group, element)
                    if tag_id not in seen_tags:
                        seen_tags.add(tag_id)
                        vr = self._get_vr_for_tag(group, element, tag_name)
                        file_meta_tags.append((group, element, vr, value, tag_name))

        # Sort by element number to maintain proper order
        file_meta_tags.sort(key=lambda x: x[1])

        # Build data elements (without group length element itself)
        data = b''
        for group, element, vr, value, tag_name in file_meta_tags:
            data += self._build_data_element(group, element, vr, value, is_little_endian, explicit_vr)

        return data
    
    def _update_file_meta_group_length(
        self,
        file_meta: bytes,
        total_length: int,
        is_little_endian: bool,
        explicit_vr: bool
    ) -> bytes:
        """
        Prepend File Meta Information Group Length (0002,0000) element.

        Args:
            file_meta: File meta information bytes (without group length element)
            total_length: Total length of file meta information (without group length element)
            is_little_endian: Byte order
            explicit_vr: Whether to use explicit VR

        Returns:
            File meta information with group length element prepended
        """
        # The group length value is the length of all OTHER file meta elements
        # (i.e., the length of file_meta bytes we're passing in)
        group_length_value = total_length

        # Ensure the value is valid (non-negative and fits in 32-bit unsigned)
        if group_length_value < 0 or group_length_value > 0xFFFFFFFF:
            group_length_value = len(file_meta)  # Fallback to actual length

        endian = '<' if is_little_endian else '>'

        # Build the group length element: (0002,0000) UL
        # IMPORTANT: UL uses SHORT VR format (2-byte length), not long format!
        group_length_element = struct.pack(f'{endian}H', 0x0002)  # Group
        group_length_element += struct.pack(f'{endian}H', 0x0000)  # Element
        group_length_element += b'UL'  # VR
        group_length_element += struct.pack(f'{endian}H', 4)  # Length (2 bytes for SHORT VR)
        group_length_element += struct.pack(f'{endian}I', group_length_value)  # Value (4 bytes)

        # Prepend the group length element to file meta
        return group_length_element + file_meta
    
    def _build_data_set(
        self,
        metadata: Dict[str, Any],
        is_little_endian: bool,
        explicit_vr: bool
    ) -> bytes:
        """
        Build Data Set (all groups except 0002).

        Args:
            metadata: Metadata dictionary
            is_little_endian: Byte order
            explicit_vr: Whether to use explicit VR

        Returns:
            Data Set bytes
        """
        data = b''

        # Group metadata by group number (de-duplicated)
        seen_tags = set()  # Track (group, element) to avoid duplicates
        grouped_metadata = {}

        for key, value in metadata.items():
            if key.startswith('DICOM:'):
                tag_name = key[6:]  # Remove 'DICOM:' prefix

                # Skip internal markers and annotation tags
                if (tag_name in ['HasDICOM', 'ElementCount', '_preserve_pixel_data'] or
                    ':' in tag_name):  # Skip annotation tags like "PatientName:VR"
                    continue

                # Handle tag format like "DICOM:(0008,0016)" or "DICOM:SOPClassUID"
                group, element = self._parse_tag_key(tag_name)

                if group and group != 0x0002:  # Skip File Meta Information
                    tag_id = (group, element)
                    if tag_id not in seen_tags:
                        seen_tags.add(tag_id)
                        if group not in grouped_metadata:
                            grouped_metadata[group] = []
                        grouped_metadata[group].append((element, tag_name, value))

        # Get preserved sequences if any
        preserved_sequences = metadata.get('_preserve_sequences', {})

        # Build data elements for each group
        for group in sorted(grouped_metadata.keys()):
            for element, tag_name, value in sorted(grouped_metadata[group]):
                # Check if this is a preserved sequence
                if (group, element) in preserved_sequences:
                    # Write the raw sequence bytes
                    data += preserved_sequences[(group, element)]
                else:
                    # Normal tag - build data element
                    vr = self._get_vr_for_tag(group, element, tag_name)
                    data += self._build_data_element(group, element, vr, value, is_little_endian, explicit_vr)

        return data
    
    def _build_data_element(
        self,
        group: int,
        element: int,
        vr: str,
        value: Any,
        is_little_endian: bool,
        explicit_vr: bool
    ) -> bytes:
        """
        Build a single DICOM data element.
        
        Args:
            group: Group number
            element: Element number
            vr: Value Representation
            value: Element value
            is_little_endian: Byte order
            explicit_vr: Whether to use explicit VR
            
        Returns:
            Data element bytes
        """
        endian = '<' if is_little_endian else '>'
        data = b''
        
        # Write group and element
        data += struct.pack(f'{endian}H', group)
        data += struct.pack(f'{endian}H', element)
        
        # Encode value first
        value_bytes = self._encode_value(value, vr, is_little_endian)

        # Calculate padded length (DICOM requires even-length values)
        value_length = len(value_bytes)
        if value_length % 2 == 1:
            value_length += 1  # Length field includes padding byte

        # Write VR and value length
        if explicit_vr:
            # Explicit VR: 2-byte VR code, then length
            data += vr.encode('ascii')

            # VR-specific length encoding
            if vr in ('OB', 'OD', 'OF', 'OL', 'OV', 'OW', 'SQ', 'UC', 'UR', 'UT', 'UN'):
                # Long VR: 2 bytes reserved (00 00), then 4-byte length
                data += b'\x00\x00'
                data += struct.pack(f'{endian}I', value_length)
            else:
                # Short VR: 2-byte length
                data += struct.pack(f'{endian}H', value_length)
        else:
            # Implicit VR: 4-byte length only
            data += struct.pack(f'{endian}I', value_length)

        # Write value
        data += value_bytes

        # Pad to even length if needed
        if len(value_bytes) % 2 == 1:
            data += b'\x00'
        
        return data
    
    def _encode_value(self, value: Any, vr: str, is_little_endian: bool) -> bytes:
        """
        Encode value according to VR type.
        
        Args:
            value: Value to encode
            vr: Value Representation
            is_little_endian: Byte order
            
        Returns:
            Encoded value bytes
        """
        endian = '<' if is_little_endian else '>'
        
        if vr in ('AE', 'AS', 'CS', 'DA', 'DS', 'DT', 'IS', 'LO', 'LT', 'PN', 'SH', 'ST', 'TM', 'UI', 'UT', 'UC', 'UR'):
            # String types
            if isinstance(value, list):
                # Multi-value strings are backslash-separated
                value = '\\'.join(str(v).strip() for v in value)
            else:
                value = str(value).strip()
            
            # For UI (UID), don't add null terminator
            if vr == 'UI':
                return value.encode('ascii', errors='ignore')
            # For other string types, add null terminator if not already present
            encoded = value.encode('ascii', errors='ignore')
            if not encoded.endswith(b'\x00'):
                encoded += b'\x00'
            return encoded
        elif vr == 'AT':
            # Attribute Tag
            if isinstance(value, str) and ',' in value:
                parts = value.split(',')
                if len(parts) == 2:
                    group = int(parts[0], 16) if parts[0].startswith('0x') else int(parts[0])
                    element = int(parts[1], 16) if parts[1].startswith('0x') else int(parts[1])
                    return struct.pack(f'{endian}HH', group, element)
        elif vr in ('SS', 'US'):
            # Signed/Unsigned Short
            if isinstance(value, list):
                result = b''
                for v in value:
                    try:
                        int_val = int(v)
                        # Clamp to valid range for US (0-65535) or SS (-32768 to 32767)
                        if vr == 'US':
                            int_val = max(0, min(65535, int_val))
                        else:
                            int_val = max(-32768, min(32767, int_val))
                        result += struct.pack(f'{endian}H' if vr == 'US' else f'{endian}h', int_val)
                    except (ValueError, TypeError):
                        # Can't convert to int, use 0 as default
                        result += struct.pack(f'{endian}H', 0)
                return result
            try:
                int_val = int(value)
                # Clamp to valid range
                if vr == 'US':
                    int_val = max(0, min(65535, int_val))
                else:
                    int_val = max(-32768, min(32767, int_val))
                return struct.pack(f'{endian}H' if vr == 'US' else f'{endian}h', int_val)
            except (ValueError, TypeError):
                # Can't convert to int, use 0 as default
                return struct.pack(f'{endian}H', 0)
        elif vr in ('SL', 'UL'):
            # Signed/Unsigned Long
            if isinstance(value, list):
                result = b''
                for v in value:
                    try:
                        int_val = int(v)
                        # Clamp to valid range for UL (0-4294967295) or SL (-2147483648 to 2147483647)
                        if vr == 'UL':
                            int_val = max(0, min(4294967295, int_val))
                        else:
                            int_val = max(-2147483648, min(2147483647, int_val))
                        result += struct.pack(f'{endian}I' if vr == 'UL' else f'{endian}i', int_val)
                    except (ValueError, TypeError):
                        # Can't convert to int, use 0 as default
                        result += struct.pack(f'{endian}I', 0)
                return result
            try:
                int_val = int(value)
                # Clamp to valid range
                if vr == 'UL':
                    int_val = max(0, min(4294967295, int_val))
                else:
                    int_val = max(-2147483648, min(2147483647, int_val))
                return struct.pack(f'{endian}I' if vr == 'UL' else f'{endian}i', int_val)
            except (ValueError, TypeError):
                # Can't convert to int, use 0 as default
                return struct.pack(f'{endian}I', 0)
        elif vr in ('FL', 'FD'):
            # Float/Double
            if vr == 'FL':
                if isinstance(value, list):
                    return b''.join(struct.pack(f'{endian}f', float(v)) for v in value)
                return struct.pack(f'{endian}f', float(value))
            else:
                if isinstance(value, list):
                    return b''.join(struct.pack(f'{endian}d', float(v)) for v in value)
                return struct.pack(f'{endian}d', float(value))
        elif vr == 'SQ':
            # Sequence - complex, would need recursive handling
            # For now, return empty sequence
            return b''
        elif vr in ('OB', 'OD', 'OF', 'OL', 'OV', 'OW', 'UN'):
            # Binary data
            if isinstance(value, str):
                # Try to decode hex string
                try:
                    return bytes.fromhex(value)
                except:
                    return value.encode('ascii', errors='ignore')
            elif isinstance(value, bytes):
                return value
            else:
                return str(value).encode('ascii', errors='ignore')
        
        # Default: encode as string
        return str(value).encode('ascii', errors='ignore')
    
    def _parse_tag_key(self, tag_key: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Parse tag key to get group and element numbers.
        Supports multiple formats:
        - "(0008,0016)" - Tag format
        - "SOPClassUID" - Keyword format
        - "Tag_0008_0016" - Legacy format
        
        Args:
            tag_key: Tag key in various formats
            
        Returns:
            (group, element) tuple or (None, None)
        """
        # Handle tag format like "(0008,0016)"
        tag_match = re.match(r'^\(([0-9A-Fa-f]{4}),([0-9A-Fa-f]{4})\)$', tag_key)
        if tag_match:
            try:
                group = int(tag_match.group(1), 16)
                element = int(tag_match.group(2), 16)
                return (group, element)
            except ValueError:
                pass
        
        # Handle keyword format - use comprehensive registry
        tag = DICOM_KEYWORD_TO_TAG.get(tag_key)
        if tag:
            return tag
        
        # Try to parse from format like "Tag_0008_0016"
        if tag_key.startswith('Tag_'):
            parts = tag_key[4:].split('_')
            if len(parts) == 2:
                try:
                    group = int(parts[0], 16)
                    element = int(parts[1], 16)
                    return (group, element)
                except ValueError:
                    pass
        
        return (None, None)
    
    def _get_tag_from_name(self, tag_name: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Get group and element numbers from tag name (legacy method).
        
        Args:
            tag_name: Tag name
            
        Returns:
            (group, element) tuple or (None, None)
        """
        return self._parse_tag_key(tag_name)
    
    def _get_element_from_name(self, tag_name: str, group: int) -> Optional[int]:
        """
        Get element number from tag name and group.
        
        Args:
            tag_name: Tag name
            group: Group number
            
        Returns:
            Element number or None
        """
        _, element = self._get_tag_from_name(tag_name)
        return element
    
    def _get_vr_for_tag(self, group: int, element: int, tag_name: str) -> str:
        """
        Get Value Representation for a tag.
        Uses comprehensive DICOM registry for accurate VR detection.

        Args:
            group: Group number
            element: Element number
            tag_name: Tag name (for fallback)

        Returns:
            VR code
        """
        # Group length tags (xxxx,0000) always have VR=UL
        if element == 0x0000:
            return 'UL'

        # First, try to get VR from comprehensive registry
        element_info = get_dicom_element_info(group, element)
        if element_info:
            vr = element_info.vr
            # Handle VRs like "OB or OW" - take first one
            if ' or ' in vr:
                vr = vr.split(' or ')[0].strip()
            return vr

        # Fallback to pattern matching if not in registry
        if 'UID' in tag_name:
            return 'UI'
        elif 'Date' in tag_name and 'Time' not in tag_name:
            return 'DA'
        elif 'Time' in tag_name and 'Date' not in tag_name:
            return 'TM'
        elif 'DateTime' in tag_name:
            return 'DT'
        elif 'Sequence' in tag_name:
            return 'SQ'
        elif tag_name in ('Rows', 'Columns', 'BitsAllocated', 'BitsStored', 'HighBit'):
            return 'US'
        elif tag_name in ('PixelData',):
            return 'OW'
        elif 'Name' in tag_name or 'Description' in tag_name:
            return 'LO'
        elif 'Number' in tag_name or 'Count' in tag_name:
            return 'IS'
        elif 'Angle' in tag_name or 'Distance' in tag_name:
            return 'DS'
        
        # Default to LO (Long String)
        return 'LO'
    
    def _extract_pixel_data(self, data: bytes) -> Optional[bytes]:
        """
        Extract complete pixel data element (7FE0,0010) from original DICOM file.
        Returns the complete element (tag + VR + length + value) as raw bytes.

        Args:
            data: Original DICOM file data

        Returns:
            Complete pixel data element as bytes, or None if not found
        """
        try:
            # Find pixel data tag (7FE0,0010) in the raw file
            offset = 132  # Skip preamble and DICM signature
            if len(data) < offset:
                return None

            # Search for pixel data tag
            while offset < len(data) - 8:
                if offset + 4 > len(data):
                    break

                group = struct.unpack('<H', data[offset:offset+2])[0]
                element = struct.unpack('<H', data[offset+2:offset+4])[0]

                if group == 0x7FE0 and element == 0x0010:
                    # Found pixel data! Extract the entire element
                    element_start = offset
                    offset += 4  # Skip tag

                    # Read VR
                    if offset + 2 > len(data):
                        return None
                    vr = data[offset:offset+2]
                    offset += 2

                    # Determine length format and read length
                    if vr in (b'OB', b'OD', b'OF', b'OL', b'OV', b'OW', b'SQ', b'UN'):
                        # Long format: 2 bytes reserved + 4 bytes length
                        if offset + 6 > len(data):
                            return None
                        offset += 2  # Skip reserved
                        value_length = struct.unpack('<I', data[offset:offset+4])[0]
                        offset += 4
                    else:
                        # Short format: 2 bytes length
                        if offset + 2 > len(data):
                            return None
                        value_length = struct.unpack('<H', data[offset:offset+2])[0]
                        offset += 2

                    # Calculate total element length
                    if offset + value_length > len(data):
                        # Pixel data extends beyond file
                        value_length = len(data) - offset

                    element_end = offset + value_length

                    # Extract entire element (tag + VR + length + data)
                    pixel_element = data[element_start:element_end]

                    # Pad to even length if needed
                    if len(pixel_element) % 2 == 1:
                        pixel_element += b'\x00'

                    return pixel_element

                # Not pixel data, skip to next element
                offset += 4  # Skip tag
                if offset + 2 > len(data):
                    break

                vr = data[offset:offset+2]
                offset += 2

                # Skip VR and length, then skip data
                if vr in (b'OB', b'OD', b'OF', b'OL', b'OV', b'OW', b'SQ', b'UN'):
                    if offset + 6 > len(data):
                        break
                    offset += 2  # Skip reserved
                    value_length = struct.unpack('<I', data[offset:offset+4])[0]
                    offset += 4

                    # Handle undefined length (sequences/encapsulated data)
                    if value_length == 0xFFFFFFFF:
                        # Undefined length - search for sequence delimiter (FFFE,E0DD)
                        # or item delimiter (FFFE,E00D) for sequences
                        delimiter_found = False
                        max_search = len(data) - offset
                        search_limit = min(max_search, 1000000)  # Limit search to 1MB

                        for i in range(0, search_limit - 4, 2):
                            check_pos = offset + i
                            if check_pos + 4 > len(data):
                                break

                            # Check for sequence delimiter (FFFE,E0DD)
                            if (data[check_pos:check_pos+2] == b'\xfe\xff' and
                                data[check_pos+2:check_pos+4] == b'\xdd\xe0'):
                                # Found sequence delimiter
                                offset = check_pos + 8  # Skip delimiter tag + length (4+4)
                                delimiter_found = True
                                break

                        if not delimiter_found:
                            # Could not find delimiter, skip this file
                            break
                        continue  # Skip the normal offset advancement
                else:
                    if offset + 2 > len(data):
                        break
                    value_length = struct.unpack('<H', data[offset:offset+2])[0]
                    offset += 2

                # Advance past the value
                offset += value_length
                if offset % 2 == 1:
                    offset += 1

        except Exception:
            pass

        return None

    def _extract_sequences(self, data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract all sequence elements from original DICOM file.
        Sequences are preserved as raw bytes to maintain their complex nested structure.

        Args:
            data: Original DICOM file data
            metadata: Parsed metadata (to identify which tags are sequences)

        Returns:
            Dictionary with '_sequences' (dict of tag->bytes) and '_tag_keys' (set of keys to filter)
        """
        result = {
            '_sequences': {},  # Maps (group, element) -> raw bytes
            '_tag_keys': set()  # Set of metadata keys to filter out
        }

        try:
            # Extract ALL sequences directly from raw file by looking for VR='SQ'
            # We don't rely on metadata because parser converts sequences to Python dicts/lists
            offset = 132  # Skip preamble and DICM
            if len(data) < offset:
                return result

            while offset < len(data) - 8:
                if offset + 4 > len(data):
                    break

                group = struct.unpack('<H', data[offset:offset+2])[0]
                element = struct.unpack('<H', data[offset+2:offset+4])[0]

                # Save tag position
                element_start = offset
                offset += 4  # Skip tag

                if offset + 2 > len(data):
                    break

                vr = data[offset:offset+2]
                offset += 2

                # Check if this is a sequence (VR='SQ')
                if vr == b'SQ':
                    # This is a sequence - extract it
                    # Read sequence length
                    if offset + 6 > len(data):
                        break
                    offset += 2  # Skip reserved
                    seq_length = struct.unpack('<I', data[offset:offset+4])[0]
                    offset += 4

                    if seq_length == 0xFFFFFFFF:
                        # Undefined length - find sequence delimiter (FFFE,E0DD)
                        # Must handle nested sequences by tracking nesting depth
                        max_search = min(len(data) - offset, 10000000)  # 10MB limit
                        delimiter_found = False
                        nesting_depth = 0  # Track nested sequences

                        search_offset = offset
                        while search_offset < offset + max_search - 8:
                            if search_offset + 8 > len(data):
                                break

                            tag_group = struct.unpack('<H', data[search_offset:search_offset+2])[0]
                            tag_elem = struct.unpack('<H', data[search_offset+2:search_offset+4])[0]

                            # Check for nested sequence start (any tag with VR='SQ')
                            if search_offset + 6 <= len(data):
                                vr_check = data[search_offset+4:search_offset+6]
                                if vr_check == b'SQ':
                                    # Entering a nested sequence
                                    nesting_depth += 1
                                    search_offset += 6  # Skip tag + VR
                                    continue

                            # Check for sequence delimiter (FFFE,E0DD)
                            if tag_group == 0xFFFE and tag_elem == 0xE0DD:
                                if nesting_depth == 0:
                                    # This is OUR delimiter!
                                    element_end = search_offset + 8
                                    delimiter_found = True
                                    break
                                else:
                                    # This closes a nested sequence
                                    nesting_depth -= 1
                                    search_offset += 8  # Skip delimiter
                                    continue

                            # Move to next tag
                            search_offset += 2

                        if delimiter_found:
                            # Extract complete sequence
                            sequence_bytes = data[element_start:element_end]
                            result['_sequences'][(group, element)] = sequence_bytes

                            # Add keys to filter list
                            result['_tag_keys'].add(f'DICOM:({group:04X},{element:04X})')
                            from dnexif.dicom_data_elements import get_dicom_element_info
                            element_info = get_dicom_element_info(group, element)
                            if element_info and element_info.keyword:
                                result['_tag_keys'].add(f'DICOM:{element_info.keyword}')

                            # Move offset to after delimiter
                            offset = element_end
                            continue
                    else:
                        # Defined length
                        element_end = offset + seq_length
                        if element_end <= len(data):
                            sequence_bytes = data[element_start:element_end]
                            # Pad to even length if needed
                            if len(sequence_bytes) % 2 == 1:
                                sequence_bytes += b'\x00'
                            result['_sequences'][(group, element)] = sequence_bytes

                            # Add keys to filter list
                            result['_tag_keys'].add(f'DICOM:({group:04X},{element:04X})')
                            from dnexif.dicom_data_elements import get_dicom_element_info
                            element_info = get_dicom_element_info(group, element)
                            if element_info and element_info.keyword:
                                result['_tag_keys'].add(f'DICOM:{element_info.keyword}')

                            # Move offset to after sequence
                            offset = element_end
                            if offset % 2 == 1:
                                offset += 1
                            continue

                # Not a sequence - skip this element's value
                # (we already skipped tag and VR above)

                # Skip based on VR
                if vr in (b'OB', b'OD', b'OF', b'OL', b'OV', b'OW', b'SQ', b'UN'):
                    if offset + 6 > len(data):
                        break
                    offset += 2
                    value_length = struct.unpack('<I', data[offset:offset+4])[0]
                    offset += 4

                    if value_length == 0xFFFFFFFF:
                        # Find delimiter
                        for i in range(0, min(len(data) - offset, 1000000), 2):
                            check_pos = offset + i
                            if check_pos + 4 > len(data):
                                break
                            if (data[check_pos:check_pos+2] == b'\xfe\xff' and
                                data[check_pos+2:check_pos+4] == b'\xdd\xe0'):
                                offset = check_pos + 8
                                break
                        else:
                            break
                        continue
                else:
                    if offset + 2 > len(data):
                        break
                    value_length = struct.unpack('<H', data[offset:offset+2])[0]
                    offset += 2

                offset += value_length
                if offset % 2 == 1:
                    offset += 1

        except Exception:
            pass

        return result

