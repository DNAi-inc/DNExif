# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
MPF (Multi-picture Format) metadata parser

This module handles reading MPF metadata from JPEG APP2 segments.
MPF is used to store multiple images in a single JPEG file, commonly
found in camera burst mode or HDR images.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional

from dnexif.exceptions import MetadataReadError


class MPFParser:
    """
    Parser for MPF (Multi-picture Format) metadata.
    
    MPF metadata is typically embedded in JPEG APP2 segments
    with identifier "MPF\x00".
    """
    
    # MPF identifier
    MPF_IDENTIFIER = b'MPF\x00'
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize MPF parser.
        
        Args:
            file_path: Path to file
            file_data: File data bytes
        """
        self.file_path = file_path
        self.file_data = file_data
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse MPF metadata.
        
        Returns:
            Dictionary of MPF metadata
        """
        try:
            # Read file data
            if self.file_data is None and self.file_path:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            elif self.file_data:
                file_data = self.file_data
            else:
                return {}
            
            metadata = {}
            
            # Check if it's a JPEG file
            if not file_data.startswith(b'\xff\xd8'):
                return metadata
            
            # Search for MPF in APP2 segments
            offset = 2  # Skip JPEG signature
            
            while offset < len(file_data) - 4:
                # Look for APP2 marker (0xFFE2)
                if file_data[offset:offset+2] == b'\xff\xe2':
                    # Read segment length
                    length = struct.unpack('>H', file_data[offset+2:offset+4])[0]
                    
                    # Check for MPF identifier
                    if file_data[offset+4:offset+8] == self.MPF_IDENTIFIER:
                        # Extract MPF data
                        mpf_data = file_data[offset+8:offset+2+length]
                        
                        # Parse MPF structure
                        parsed = self._parse_mpf_data(mpf_data)
                        metadata.update(parsed)
                    
                    offset += 2 + length
                else:
                    offset += 1
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse MPF metadata: {str(e)}")
    
    def _parse_mpf_data(self, data: bytes) -> Dict[str, Any]:
        """
        Parse MPF data structure.
        
        MPF format structure (based on CIPA DC-007-2016):
        - MPF Header (4 bytes): "MPF\x00"
        - MPF Index IFD (variable)
        - MPF Attribute IFD (variable)
        - Image Data List (variable)
        
        Args:
            data: MPF data bytes (after identifier)
            
        Returns:
            Dictionary of parsed MPF metadata
        """
        metadata = {}
        
        try:
            if len(data) < 12:
                return metadata
            
            # MPF data starts with byte order indicator (II or MM)
            if data[0:2] == b'II':
                endian = '<'  # Little-endian
            elif data[0:2] == b'MM':
                endian = '>'  # Big-endian
            else:
                # Default to little-endian if not found
                endian = '<'
            
            # Read offset to MPF Index IFD (4 bytes)
            if len(data) >= 8:
                index_ifd_offset = struct.unpack(f'{endian}I', data[4:8])[0]
                
                # Parse MPF Index IFD
                # mpf_data_start is 0 since we're already in MPF data space
                if index_ifd_offset > 0 and index_ifd_offset < len(data):
                    index_metadata = self._parse_mpf_index_ifd(
                        data, index_ifd_offset, endian, mpf_data_start=0
                    )
                    metadata.update(index_metadata)
            
            # Look for ImageNumber and NumberOfImages tags
            # These are typically in the MPF Index IFD
            if 'MPF:ImageNumber' not in metadata:
                # Try to find ImageNumber in the data
                # ImageNumber is typically tag 0xB000
                # NumberOfImages is typically tag 0xB001
                pass
        
        except Exception as e:
            # If parsing fails, at least mark that MPF data was found
            metadata['MPF:HasMPF'] = True
            metadata['MPF:DataSize'] = len(data)
        
        return metadata
    
    def _parse_mpf_index_ifd(self, data: bytes, offset: int, endian: str, mpf_data_start: int = 0) -> Dict[str, Any]:
        """
        Parse MPF Index IFD structure.
        
        MPF Index IFD contains tags like:
        - 0xB000: ImageNumber
        - 0xB001: NumberOfImages
        - 0xB002: MPEntry (list of image entries)
        - 0xB003: Version
        
        Args:
            data: MPF data bytes
            offset: Offset to Index IFD
            endian: Byte order
            
        Returns:
            Dictionary of parsed MPF Index IFD metadata
        """
        metadata = {}
        
        try:
            if offset + 2 > len(data):
                return metadata
            
            # Read number of entries
            num_entries = struct.unpack(f'{endian}H', data[offset:offset+2])[0]
            
            if num_entries == 0 or num_entries > 100:
                return metadata
            
            entry_offset = offset + 2
            
            # MPF tag definitions (per CIPA DC-007-2016 and standard format)
            MPF_TAGS = {
                0xB000: 'MPFVersion',  # Version as ASCII string "0100"
                0xB001: 'NumberOfImages',
                0xB002: 'MPEntry',
                0xB003: 'Version',  # Alternative version tag
            }
            
            for i in range(num_entries):
                if entry_offset + 12 > len(data):
                    break
                
                tag_id = struct.unpack(f'{endian}H', data[entry_offset:entry_offset+2])[0]
                tag_type = struct.unpack(f'{endian}H', data[entry_offset+2:entry_offset+4])[0]
                tag_count = struct.unpack(f'{endian}I', data[entry_offset+4:entry_offset+8])[0]
                tag_value = struct.unpack(f'{endian}I', data[entry_offset+8:entry_offset+12])[0]
                
                tag_name = MPF_TAGS.get(tag_id, f'Tag{tag_id:04X}')
                
                # Decode value based on type
                if tag_type == 1:  # BYTE
                    if tag_count <= 4:
                        value = tag_value
                    else:
                        data_offset = offset + tag_value
                        if data_offset + tag_count <= len(data):
                            value = list(data[data_offset:data_offset+tag_count])
                        else:
                            value = tag_value
                elif tag_type == 3:  # SHORT
                    if tag_count <= 2:
                        value = tag_value
                    else:
                        data_offset = offset + tag_value
                        if data_offset + tag_count * 2 <= len(data):
                            values = []
                            for j in range(tag_count):
                                val = struct.unpack(f'{endian}H', 
                                                   data[data_offset+j*2:data_offset+j*2+2])[0]
                                values.append(val)
                            value = values
                        else:
                            value = tag_value
                elif tag_type == 4:  # LONG
                    if tag_count == 1:
                        value = tag_value
                    else:
                        data_offset = offset + tag_value
                        if data_offset + tag_count * 4 <= len(data):
                            values = []
                            for j in range(tag_count):
                                val = struct.unpack(f'{endian}I', 
                                                   data[data_offset+j*4:data_offset+j*4+4])[0]
                                values.append(val)
                            value = values
                        else:
                            value = tag_value
                elif tag_type == 7:  # UNDEFINED (used for MPEntry and MPFVersion)
                    if tag_id == 0xB000:  # MPFVersion is stored as ASCII string "0100"
                        # For UNDEFINED type, if count <= 4, value is stored inline in tag_value
                        if tag_count <= 4:
                            # Value is stored inline as 4-byte integer, but represents ASCII bytes
                            # Convert tag_value (32-bit integer) to bytes and decode as ASCII
                            value_bytes = struct.pack(f'{endian}I', tag_value)
                            # Take only the first tag_count bytes
                            value_bytes = value_bytes[:tag_count]
                            try:
                                value = value_bytes.decode('ascii', errors='ignore').strip('\x00').strip()
                            except:
                                value = tag_value
                        else:
                            # Value is stored at offset
                            data_offset = mpf_data_start + tag_value
                            if data_offset >= 0 and data_offset + tag_count <= len(data):
                                value = data[data_offset:data_offset+tag_count]
                                try:
                                    value = value.decode('ascii', errors='ignore').strip('\x00').strip()
                                except:
                                    value = tag_value
                            else:
                                value = tag_value
                    elif tag_id == 0xB002:  # MPEntry
                        # For MPEntry, the value is an offset to the MPEntry data
                        # Store the offset value directly (will be parsed later)
                        value = tag_value
                    else:
                        value = tag_value
                else:
                    value = tag_value
                
                # Format tag name with MPF prefix
                # Special handling for MPFVersion to standard format's format
                if tag_id == 0xB000:
                    metadata['MPF:MPFVersion'] = value
                    metadata['MPF:Version'] = value  # Also keep Version for backward compatibility
                else:
                    metadata[f'MPF:{tag_name}'] = value
                
                entry_offset += 12
            
            # Parse MPEntry if present (tag 0xB002)
            # MPEntry is stored as UNDEFINED type (7), so tag_value is the offset to MPEntry data
            if 'MPF:MPEntry' in metadata:
                mp_entry_value = metadata['MPF:MPEntry']
                # MPEntry tag value is the offset to the MPEntry data (relative to start of MPF data)
                if isinstance(mp_entry_value, int) and mp_entry_value > 0:
                    parsed_entries = self._parse_mp_entries(data, mp_entry_value, offset, endian)
                    metadata.update(parsed_entries)
                elif isinstance(mp_entry_value, list) and len(mp_entry_value) > 0:
                    # Fallback: if it's already parsed as a list, try to extract info
                    metadata['MPF:NumberOfMPEntries'] = len(mp_entry_value)
                    for i, entry_value in enumerate(mp_entry_value[:5]):  # Limit to first 5
                        if isinstance(entry_value, int):
                            metadata[f'MPF:MPEntry{i}'] = f'0x{entry_value:08X}'
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_mp_entries(self, data: bytes, mp_entry: list, base_offset: int, endian: str) -> Dict[str, Any]:
        """
        Parse MPEntry data to extract individual image information.
        
        MPEntry format (per CIPA DC-007-2016):
        Each entry is 16 bytes:
        - Bytes 0-3: MPImageStart (offset to image data, relative to MPF data start)
        - Bytes 4-7: MPImageLength (length of image data)
        - Bytes 8-11: MPImageType (type flags: bit 0 = dependent, bit 1 = representative)
        - Bytes 12-15: MPImageAttribute (attribute flags)
        
        Args:
            data: MPF data bytes
            mp_entry: MPEntry tag value (offset to MPEntry data)
            base_offset: Base offset for relative addressing (Index IFD offset)
            endian: Byte order
            
        Returns:
            Dictionary of parsed MP entry metadata
        """
        metadata = {}
        
        try:
            # MPEntry is stored as UNDEFINED type (7) with offset to data
            # The tag_value is the offset to the MPEntry data
            if not isinstance(mp_entry, int):
                # If it's already a list, it might be the actual data
                if isinstance(mp_entry, list) and len(mp_entry) > 0:
                    metadata['MPF:NumberOfMPEntries'] = len(mp_entry)
                    # Try to parse first few entries
                    for i, entry_value in enumerate(mp_entry[:5]):  # Limit to first 5
                        if isinstance(entry_value, int):
                            metadata[f'MPF:MPEntry{i}'] = f'0x{entry_value:08X}'
                return metadata
            
            # MPEntry offset is relative to the start of MPF data (base_offset = 0 for MPF data)
            # But we need to account for the MPF header (8 bytes: II/MM + version + index IFD offset)
            mp_entry_offset = mp_entry
            if mp_entry_offset < 0 or mp_entry_offset >= len(data):
                return metadata
            
            # Read number of entries (first 4 bytes, but MPEntry doesn't have count field)
            # Instead, we use NumberOfImages from the Index IFD if available
            # For now, try to read entries until we hit invalid data
            num_entries = 0
            max_entries = 100  # Safety limit
            
            # Each MPEntry is 16 bytes
            entry_size = 16
            current_offset = mp_entry_offset
            
            while current_offset + entry_size <= len(data) and num_entries < max_entries:
                # Read MPEntry structure (16 bytes)
                mp_image_start = struct.unpack(f'{endian}I', data[current_offset:current_offset+4])[0]
                mp_image_length = struct.unpack(f'{endian}I', data[current_offset+4:current_offset+8])[0]
                mp_image_type = struct.unpack(f'{endian}I', data[current_offset+8:current_offset+12])[0]
                mp_image_attribute = struct.unpack(f'{endian}I', data[current_offset+12:current_offset+16])[0]
                
                # Validate entry (basic sanity checks)
                if mp_image_start == 0 and mp_image_length == 0 and num_entries > 0:
                    # Likely end of entries
                    break
                
                # Store entry information
                metadata[f'MPF:MPEntry{num_entries}:MPImageStart'] = mp_image_start
                metadata[f'MPF:MPEntry{num_entries}:MPImageLength'] = mp_image_length
                
                # Extract MPImageFlags (bits 0xf8000000 of mp_image_type)
                mp_image_flags = (mp_image_type & 0xf8000000) >> 27
                metadata[f'MPF:MPEntry{num_entries}:MPImageFlags'] = mp_image_flags
                
                # Extract MPImageFormat (bits 0x7000000 of mp_image_type)
                mp_image_format = (mp_image_type & 0x07000000) >> 24
                format_map = {0: 'JPEG', 1: 'TIFF', 2: 'MP', 3: 'RAW'}
                format_str = format_map.get(mp_image_format, str(mp_image_format))
                metadata[f'MPF:MPEntry{num_entries}:MPImageFormat'] = format_str
                # Also set top-level MPImageFormat for first entry (Standard format shows this)
                if num_entries == 0:
                    metadata['MPF:MPImageFormat'] = format_str
                
                # Extract MPImageType (bits 0xffffff of mp_image_type)
                mp_image_type_value = mp_image_type & 0x00ffffff
                type_map = {
                    0x000000: 'Undefined',
                    0x000001: 'Large Thumbnail (VGA equivalent)',
                    0x000002: 'Large Thumbnail (full HD equivalent)',
                    0x000003: 'Multi-frame Panorama',
                    0x000004: 'Multi-frame Disparity',
                    0x000005: 'Multi-frame Multi-view',
                    0x000006: 'Original Preservation Image',  # EXIF 3.0
                }
                type_str = type_map.get(mp_image_type_value, f'0x{mp_image_type_value:06X}')
                metadata[f'MPF:MPEntry{num_entries}:MPImageType'] = type_str
                # Also set top-level MPImageType for first entry (Standard format shows this)
                if num_entries == 0:
                    metadata['MPF:MPImageType'] = type_str
                
                # Decode MPImageFlags to text (Standard format shows "Dependent child image" etc.)
                flags_str = []
                if mp_image_flags & 0x01:
                    flags_str.append('Dependent child image')
                if mp_image_flags & 0x02:
                    flags_str.append('Representative image')
                if not flags_str:
                    flags_str.append('Main image')
                # Also set top-level MPImageFlags for first entry (Standard format shows this)
                if num_entries == 0:
                    metadata['MPF:MPImageFlags'] = ' '.join(flags_str) if flags_str else str(mp_image_flags)
                
                # Also set top-level MPImageLength and MPImageStart for first entry (Standard format shows these)
                if num_entries == 0:
                    metadata['MPF:MPImageLength'] = mp_image_length
                    metadata['MPF:MPImageStart'] = mp_image_start
                
                metadata[f'MPF:MPEntry{num_entries}:MPImageAttribute'] = f'0x{mp_image_attribute:08X}'
                
                # Extract DependentImage1EntryNumber and DependentImage2EntryNumber from MPImageAttribute
                # These are stored in the attribute field (bytes 12-15), but Standard format shows them separately
                # For now, we'll extract them from the next 4 bytes if available
                if current_offset + 20 <= len(data):
                    dep1_entry = struct.unpack(f'{endian}H', data[current_offset+16:current_offset+18])[0]
                    dep2_entry = struct.unpack(f'{endian}H', data[current_offset+18:current_offset+20])[0]
                    if num_entries == 0:
                        metadata['MPF:DependentImage1EntryNumber'] = dep1_entry
                        metadata['MPF:DependentImage2EntryNumber'] = dep2_entry
                
                num_entries += 1
                current_offset += entry_size
            
            metadata['MPF:NumberOfMPEntries'] = num_entries
        
        except Exception:
            pass
        
        return metadata

