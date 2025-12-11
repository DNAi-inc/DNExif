# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
APP6 (GoPro) metadata parser

This module handles reading APP6 metadata from JPEG APP6 segments.
APP6 is used by GoPro cameras to store camera-specific metadata.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional

from dnexif.exceptions import MetadataReadError


class APP6Parser:
    """
    Parser for APP6 (GoPro) metadata.
    
    APP6 metadata is typically embedded in JPEG APP6 segments (0xFFE6).
    GoPro cameras use APP6 to store camera-specific metadata.
    """
    
    # APP6 marker
    APP6_MARKER = b'\xff\xe6'
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize APP6 parser.
        
        Args:
            file_path: Path to file
            file_data: File data bytes
        """
        self.file_path = file_path
        self.file_data = file_data
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse APP6 metadata.
        
        Returns:
            Dictionary of APP6 metadata
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
            
            # Search for APP6 segments
            offset = 2  # Skip JPEG signature
            
            while offset < len(file_data) - 4:
                # Look for APP6 marker (0xFFE6)
                if file_data[offset:offset+2] == self.APP6_MARKER:
                    # Read segment length
                    length = struct.unpack('>H', file_data[offset+2:offset+4])[0]
                    
                    if length < 4:
                        offset += 1
                        continue
                    
                    # Extract APP6 data (skip 2-byte length field)
                    app6_data = file_data[offset+4:offset+2+length]
                    
                    # Parse APP6 structure
                    parsed = self._parse_app6_data(app6_data)
                    metadata.update(parsed)
                    
                    offset += 2 + length
                else:
                    offset += 1
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse APP6 metadata: {str(e)}")
    
    def _parse_app6_data(self, data: bytes) -> Dict[str, Any]:
        """
        Parse APP6 data structure.
        
        GoPro APP6 format structure:
        - Header (variable): May contain identifier or version
        - Tag-value pairs (variable): Various GoPro-specific tags
        
        Args:
            data: APP6 data bytes
            
        Returns:
            Dictionary of parsed APP6 metadata
        """
        metadata = {}
        
        try:
            if len(data) < 4:
                return metadata
            
            # GoPro APP6 data structure varies by camera model
            # Common structure: tag ID (2 bytes) + data length (2 bytes) + data
            offset = 0
            
            # Try to find GoPro identifier or version
            # Some GoPro files start with version info or model name
            if data.startswith(b'GoPro'):
                # Extract model name if present
                null_pos = data.find(b'\x00', 5)
                if null_pos > 5:
                    model = data[5:null_pos].decode('utf-8', errors='ignore').strip()
                    if model:
                        metadata['APP6:Model'] = model
                    offset = null_pos + 1
            
            # Parse tag-value pairs
            # GoPro APP6 uses a structure similar to EXIF but with different tag IDs
            while offset + 4 < len(data):
                try:
                    # Read tag ID (2 bytes, little-endian for some GoPro formats)
                    tag_id = struct.unpack('<H', data[offset:offset+2])[0]
                    offset += 2
                    
                    # Read data length (2 bytes)
                    if offset + 2 > len(data):
                        break
                    data_length = struct.unpack('<H', data[offset:offset+2])[0]
                    offset += 2
                    
                    if data_length == 0 or data_length > len(data) - offset:
                        break
                    
                    # Read tag data
                    tag_data = data[offset:offset+data_length]
                    offset += data_length
                    
                    # Parse tag based on ID
                    tag_name, tag_value = self._parse_app6_tag(tag_id, tag_data)
                    if tag_name:
                        metadata[f'APP6:{tag_name}'] = tag_value
                
                except (struct.error, IndexError):
                    # Try alternative parsing method
                    # Some GoPro APP6 data uses fixed offsets
                    break
            
            # Alternative parsing: Look for known GoPro tag patterns
            # GoPro cameras often store metadata in specific byte positions
            # Try to extract common tags by searching for known patterns
            
            # AutoRotation (often at specific offset)
            # DigitalZoom (often stored as ratio)
            # Sharpness, ColorMode, TimeZone, SpotMeter, etc.
            
            # Try to extract common GoPro tags from data
            self._extract_common_gopro_tags(data, metadata)
        
        except Exception:
            # If parsing fails, at least mark that APP6 data was found
            if 'APP6:HasAPP6' not in metadata:
                metadata['APP6:HasAPP6'] = True
                metadata['APP6:DataSize'] = len(data)
        
        return metadata
    
    def _parse_app6_tag(self, tag_id: int, tag_data: bytes) -> tuple[Optional[str], Any]:
        """
        Parse individual APP6 tag.
        
        Args:
            tag_id: Tag ID
            tag_data: Tag data bytes
            
        Returns:
            Tuple of (tag_name, tag_value) or (None, None) if unknown
        """
        # GoPro APP6 tag ID mappings (based on reverse engineering)
        # These may vary by camera model
        APP6_TAG_MAP = {
            0x0001: 'AutoRotation',
            0x0002: 'Sharpness',
            0x0003: 'DigitalZoom',
            0x0004: 'DigitalZoomOn',
            0x0005: 'TimeZone',
            0x0006: 'ColorMode',
            0x0007: 'SpotMeter',
            0x0008: 'ScheduleCapture',
            0x0009: 'Model',
            0x000A: 'WhiteBalance',
            0x000B: 'Rate',
            0x000C: 'AutoISOMin',
            0x000D: 'AutoISOMax',
            0x000E: 'ISO',
            0x000F: 'ExposureCompensation',
            # Add more as discovered
        }
        
        tag_name = APP6_TAG_MAP.get(tag_id)
        if not tag_name:
            return None, None
        
            # Parse tag value based on data type
        try:
            if len(tag_data) == 1:
                # Boolean or byte value
                value = struct.unpack('B', tag_data)[0]
                if tag_name in ('AutoRotation', 'DigitalZoomOn', 'SpotMeter'):
                    return tag_name, 'On' if value else 'Off'
                elif tag_name == 'Sharpness':
                    # Sharpness: 0=Low, 1=Medium, 2=High
                    sharpness_map = {0: 'Low', 1: 'Medium', 2: 'High'}
                    return tag_name, sharpness_map.get(value, str(value))
                return tag_name, value
            elif len(tag_data) == 2:
                # Short value
                value = struct.unpack('<H', tag_data)[0]
                if tag_name == 'DigitalZoom':
                    # DigitalZoom is often stored as ratio (e.g., 100 = 1.0x, 200 = 2.0x)
                    return tag_name, f"{value / 100.0:.1f}x" if value > 0 else "1.0x"
                elif tag_name in ('AutoISOMin', 'AutoISOMax', 'ISO'):
                    return tag_name, value
                elif tag_name == 'Rate':
                    # Rate might be frame rate or bit rate
                    return tag_name, value
                return tag_name, value
            elif len(tag_data) == 4:
                # Long value or float
                value = struct.unpack('<I', tag_data)[0]
                if tag_name == 'TimeZone':
                    # TimeZone might be stored as offset in minutes or seconds
                    # Try to format as +/-HH:MM
                    hours = value // 3600 if value > 0 else (value // -3600)
                    minutes = (abs(value) % 3600) // 60
                    sign = '+' if value >= 0 else '-'
                    return tag_name, f"{sign}{abs(hours):02d}:{minutes:02d}"
                return tag_name, value
            elif len(tag_data) > 0:
                # String value
                # Try to decode as UTF-8, removing null terminators
                value = tag_data.rstrip(b'\x00').decode('utf-8', errors='ignore').strip()
                if value:
                    return tag_name, value
        except (struct.error, UnicodeDecodeError):
            pass
        
        return tag_name, tag_data.hex() if len(tag_data) <= 20 else f"(Binary data {len(tag_data)} bytes)"
    
    def _extract_common_gopro_tags(self, data: bytes, metadata: Dict[str, Any]) -> None:
        """
        Extract common GoPro tags by searching for known patterns.
        
        This is a fallback method when structured parsing fails.
        
        Args:
            data: APP6 data bytes
            metadata: Metadata dictionary to update
        """
        try:
            # Search for common GoPro strings
            if b'GoPro' in data:
                # Try to extract model name
                gopro_pos = data.find(b'GoPro')
                if gopro_pos >= 0:
                    # Model name might be after "GoPro"
                    model_start = gopro_pos + 5
                    if model_start < len(data):
                        # Look for null terminator or end of reasonable string
                        model_end = model_start
                        while model_end < len(data) and model_end < model_start + 20:
                            if data[model_end] == 0:
                                break
                            model_end += 1
                        if model_end > model_start:
                            model = data[model_start:model_end].decode('utf-8', errors='ignore').strip()
                            if model and 'APP6:Model' not in metadata:
                                metadata['APP6:Model'] = model
            
            # Search for timezone patterns (e.g., "+00:00", "-05:00")
            import re
            timezone_pattern = re.compile(rb'[+-]\d{2}:\d{2}')
            timezone_match = timezone_pattern.search(data)
            if timezone_match:
                timezone = timezone_match.group(0).decode('utf-8', errors='ignore')
                if timezone and 'APP6:TimeZone' not in metadata:
                    metadata['APP6:TimeZone'] = timezone
            
            # Try to extract digital zoom from common patterns
            # DigitalZoom is often stored as a ratio (e.g., 0x64 = 100 = 1.0x)
            # Look for values that might represent zoom ratios
            for i in range(len(data) - 1):
                if i + 1 < len(data):
                    value = struct.unpack('<H', data[i:i+2])[0]
                    # Common zoom values: 100 (1.0x), 200 (2.0x), 150 (1.5x), etc.
                    if 50 <= value <= 1000 and value % 50 == 0:
                        # Might be a zoom value
                        zoom_ratio = value / 100.0
                        if 0.5 <= zoom_ratio <= 10.0:
                            if 'APP6:DigitalZoom' not in metadata:
                                metadata['APP6:DigitalZoom'] = f"{zoom_ratio:.1f}x"
                            break
        
        except Exception:
            pass

