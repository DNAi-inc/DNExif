# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
MakerNote value decoder

This module provides value decoding for MakerNote tags from
various camera manufacturers.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List, Tuple
from dnexif.exceptions import MetadataReadError


class MakerNoteValueDecoder:
    """
    Decodes MakerNote tag values for various camera manufacturers.
    
    MakerNote data is manufacturer-specific and requires custom
    decoding logic for each manufacturer.
    """
    
    def __init__(self, endian: str = '<'):
        """
        Initialize MakerNote value decoder.
        
        Args:
            endian: Byte order ('<' for little-endian, '>' for big-endian)
        """
        self.endian = endian
    
    def decode_canon_value(
        self,
        tag_id: int,
        tag_type: int,
        tag_count: int,
        data: bytes,
        offset: int,
        parent_tag_name: Optional[str] = None
    ) -> Any:
        """
        Decode Canon MakerNote tag value with enum and flag support.
        
        Args:
            tag_id: Tag ID
            tag_type: Tag data type
            tag_count: Number of values
            data: Raw data bytes
            offset: Offset to tag data
            parent_tag_name: Parent tag name for sub-IFD context (e.g., "CanonCameraSettings")
            
        Returns:
            Decoded value (with enum/flag interpretation if applicable)
        """
        # Special handling for Canon FirmwareVersion (tag 0x0007 in main MakerNote)
        # Canon FirmwareVersion is typically stored as BYTE array (type 1) or ASCII string (type 2)
        # Format: "X.Y.Z" (dot-separated) or "X Y Z W" (space-separated) to standard format
        if tag_id == 0x0007 and parent_tag_name is None:  # FirmwareVersion in main MakerNote
            try:
                if tag_type == 1:  # BYTE array
                    if offset + tag_count <= len(data):
                        version_bytes = list(struct.unpack(f'{self.endian}{tag_count}B', data[offset:offset+tag_count]))
                        # Format as "X.Y.Z" if 3-4 bytes, or "X Y Z W" if more
                        if 3 <= len(version_bytes) <= 4:
                            return '.'.join(str(b) for b in version_bytes)
                        else:
                            return ' '.join(str(b) for b in version_bytes)
                elif tag_type == 2:  # ASCII string
                    # Try to decode as ASCII string
                    end = data.find(b'\x00', offset)
                    if end == -1:
                        end = offset + tag_count
                    version_str = data[offset:end].decode('ascii', errors='replace').strip()
                    # If it looks like a version string, return as-is
                    if version_str and len(version_str) > 0:
                        return version_str
            except:
                pass
        
        # Special handling for WB_RGGBLevels tags in Canon ColorBalance sub-IFD (parent tag 0x001A)
        # WB_RGGBLevels tags (0x0018-0x0020) should be formatted as space-separated RGGB values
        # Format: "R G G B" (e.g., "1621 1024 1024 2427")
        # These tags are typically stored as 4 SHORT values (type 3, count 4) or 4 LONG values (type 4, count 4)
        if parent_tag_name and ('ColorBalance' in parent_tag_name or parent_tag_name == 'CanonColorBalance'):
            from dnexif.makernote_tags import CANON_COLOR_BALANCE_TAGS
            # Check if this is a WB_RGGBLevels tag (0x0018-0x0020)
            if tag_id in CANON_COLOR_BALANCE_TAGS:
                tag_name = CANON_COLOR_BALANCE_TAGS.get(tag_id)
                if tag_name and 'WB_RGGBLevels' in tag_name:
                    # WB_RGGBLevels tags should have 4 values (R, G1, G2, B)
                    try:
                        if tag_type == 3 and tag_count == 4:  # SHORT (2 bytes each)
                            if offset + 8 <= len(data):
                                values = list(struct.unpack(f'{self.endian}HHHH', data[offset:offset+8]))
                                # Format as space-separated string: "R G G B"
                                return ' '.join(str(v) for v in values)
                        elif tag_type == 4 and tag_count == 4:  # LONG (4 bytes each)
                            if offset + 16 <= len(data):
                                values = list(struct.unpack(f'{self.endian}IIII', data[offset:offset+16]))
                                # Format as space-separated string: "R G G B"
                                return ' '.join(str(v) for v in values)
                    except:
                        pass
        
        # First decode the raw value (pass parent_tag_name for ASCII type handling)
        raw_value = self._decode_raw_value(tag_type, tag_count, data, offset, parent_tag_name)
        
        # Special post-processing for WB_RGGBLevels tags: format as space-separated RGGB values
        # This handles cases where raw_value is already decoded as a list
        if parent_tag_name and ('ColorBalance' in parent_tag_name or parent_tag_name == 'CanonColorBalance'):
            from dnexif.makernote_tags import CANON_COLOR_BALANCE_TAGS
            if tag_id in CANON_COLOR_BALANCE_TAGS:
                tag_name = CANON_COLOR_BALANCE_TAGS.get(tag_id)
                if tag_name and 'WB_RGGBLevels' in tag_name:
                    # If raw_value is a list with 4 values, format as space-separated string
                    if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 4:
                        return ' '.join(str(v) for v in raw_value[:4])
        
        # Apply enum/flag decoding if available (with sub-IFD context)
        decoded = self._apply_enum_flags('CANON', tag_id, raw_value, parent_tag_name)
        
        # Final check: if decoded value is a list/tuple for WB_RGGBLevels, format it
        if parent_tag_name and ('ColorBalance' in parent_tag_name or parent_tag_name == 'CanonColorBalance'):
            from dnexif.makernote_tags import CANON_COLOR_BALANCE_TAGS
            if tag_id in CANON_COLOR_BALANCE_TAGS:
                tag_name = CANON_COLOR_BALANCE_TAGS.get(tag_id)
                if tag_name and 'WB_RGGBLevels' in tag_name:
                    if isinstance(decoded, (list, tuple)) and len(decoded) >= 4:
                        return ' '.join(str(v) for v in decoded[:4])
        
        return decoded
    
    def _decode_raw_value(
        self,
        tag_type: int,
        tag_count: int,
        data: bytes,
        offset: int,
        parent_tag_name: Optional[str] = None,
        endian: Optional[str] = None
    ) -> Any:
        """
        Decode raw value from binary data.
        
        Args:
            tag_type: Tag data type
            tag_count: Number of values
            data: Raw data bytes
            offset: Offset to tag data
            parent_tag_name: Parent tag name for sub-IFD context (for Canon ASCII handling)
            endian: Byte order to use (if None, uses self.endian)
            
        Returns:
            Raw decoded value
        """
        # Use provided endianness or fall back to self.endian
        use_endian = endian if endian is not None else self.endian
        
        try:
            if tag_type == 1:  # BYTE
                if tag_count == 1:
                    return struct.unpack(f'{use_endian}B', data[offset:offset+1])[0]
                else:
                    return list(struct.unpack(f'{use_endian}{tag_count}B', data[offset:offset+tag_count]))
            elif tag_type == 3:  # SHORT
                if tag_count == 1:
                    return struct.unpack(f'{use_endian}H', data[offset:offset+2])[0]
                else:
                    return list(struct.unpack(f'{use_endian}{tag_count}H', data[offset:offset+tag_count*2]))
            elif tag_type == 4:  # LONG
                if tag_count == 1:
                    return struct.unpack(f'{use_endian}I', data[offset:offset+4])[0]
                else:
                    return list(struct.unpack(f'{use_endian}{tag_count}I', data[offset:offset+tag_count*4]))
            elif tag_type == 5:  # RATIONAL
                if tag_count == 1:
                    numerator = struct.unpack(f'{use_endian}I', data[offset:offset+4])[0]
                    denominator = struct.unpack(f'{use_endian}I', data[offset+4:offset+8])[0]
                    if denominator != 0:
                        return numerator / denominator
                    return f"{numerator}/{denominator}"
                else:
                    values = []
                    for i in range(tag_count):
                        num_offset = offset + (i * 8)
                        numerator = struct.unpack(f'{use_endian}I', data[num_offset:num_offset+4])[0]
                        denominator = struct.unpack(f'{use_endian}I', data[num_offset+4:num_offset+8])[0]
                        if denominator != 0:
                            values.append(numerator / denominator)
                        else:
                            values.append(f"{numerator}/{denominator}")
                    return values
            elif tag_type == 2:  # ASCII
                # Null-terminated string
                end = data.find(b'\x00', offset)
                if end == -1:
                    end = offset + tag_count
                # Check if data contains non-ASCII bytes - if so, it might be binary data
                string_data = data[offset:end]
                # If more than 50% of bytes are non-printable or non-ASCII, treat as binary
                non_printable = sum(1 for b in string_data if b < 32 or b > 126)
                if len(string_data) > 0 and non_printable > len(string_data) * 0.5:
                    # Likely binary data, return as binary indicator
                    return f"(Binary data {tag_count} bytes, use -b option to extract)"
                decoded_str = string_data.decode('ascii', errors='replace')
                # For Canon sub-IFD tags with parent_tag_name, single-byte ASCII values
                # are often actually numeric enum values that should be decoded as integers
                # Check if this is a Canon sub-IFD tag (parent_tag_name contains "Canon" and a sub-IFD name)
                if parent_tag_name and ('Canon' in parent_tag_name or 'CameraSettings' in parent_tag_name or 'ShotInfo' in parent_tag_name or 'FlashInfo' in parent_tag_name):
                    # Try to interpret as BYTE integer first
                    # Canon often uses ASCII type (2) for single-byte enum values in sub-IFDs
                    try:
                        if offset < len(data) and tag_count == 1:
                            byte_val = struct.unpack(f'{self.endian}B', data[offset:offset+1])[0]
                            # Always return as integer for Canon sub-IFD tags with single-byte values
                            # This handles cases where Canon uses ASCII type for numeric enums
                            return byte_val
                    except:
                        pass
                return decoded_str
            elif tag_type == 7:  # UNDEFINED
                # For UNDEFINED type, try to decode as appropriate type based on count
                # If count is small (<= 4), try to decode as numeric value
                if tag_count <= 4:
                    # Try decoding as BYTE, SHORT, or LONG depending on count
                    try:
                        if tag_count == 1:
                            # Single byte - try as BYTE
                            return struct.unpack(f'{use_endian}B', data[offset:offset+1])[0]
                        elif tag_count == 2:
                            # Two bytes - try as SHORT
                            return struct.unpack(f'{use_endian}H', data[offset:offset+2])[0]
                        elif tag_count == 4:
                            # Four bytes - try as LONG
                            return struct.unpack(f'{use_endian}I', data[offset:offset+4])[0]
                    except:
                        pass
                # For larger UNDEFINED values, return as binary data indicator
                if tag_count > 100:
                    return f"(Binary data {tag_count} bytes, use -b option to extract)"
                else:
                    # For smaller UNDEFINED values, return the raw bytes (up to 100 bytes)
                    return data[offset:offset+min(tag_count, 100)]
            else:
                # Unknown type
                if tag_count > 100:
                    return f"(Binary data {tag_count} bytes, use -b option to extract)"
                else:
                    return data[offset:offset+min(tag_count, 100)]
        except Exception:
            if tag_count > 100:
                return f"(Binary data {tag_count} bytes, use -b option to extract)"
            else:
                return f"<binary data: {tag_count} bytes>"
    
    def _apply_enum_flags(
        self,
        manufacturer: str,
        tag_id: int,
        raw_value: Any,
        parent_tag_name: Optional[str] = None
    ) -> Any:
        """
        Apply enum and flag decoding to raw value.
        
        Args:
            manufacturer: Camera manufacturer
            tag_id: Tag ID
            raw_value: Raw decoded value
            parent_tag_name: Parent tag name for sub-IFD context (e.g., "CanonCameraSettings")
            
        Returns:
            Value with enum/flag interpretation if available
        """
        # Get enum/flag definitions for this tag (with sub-IFD context)
        enum_map = self._get_enum_map(manufacturer, tag_id, parent_tag_name)
        flag_map = self._get_flag_map(manufacturer, tag_id, parent_tag_name)
        
        if enum_map and isinstance(raw_value, int):
            # Check if value is in enum map
            if raw_value in enum_map:
                # Return just the enum name to standard format format (no numeric suffix)
                return enum_map[raw_value]
            # Return raw value if not in enum
            return raw_value
        elif flag_map and isinstance(raw_value, int):
            # Decode flags (bitwise)
            flags = []
            for bit, flag_name in flag_map.items():
                if raw_value & (1 << bit):
                    flags.append(flag_name)
            if flags:
                return f"{', '.join(flags)} ({raw_value})"
            return raw_value
        else:
            # No enum/flag mapping, return raw value
            return raw_value
    
    def _get_enum_map(self, manufacturer: str, tag_id: int, parent_tag_name: Optional[str] = None) -> Optional[Dict[int, str]]:
        """
        Get enum mapping for a tag.
        
        Args:
            manufacturer: Camera manufacturer
            tag_id: Tag ID
            parent_tag_name: Parent tag name for sub-IFD context (e.g., "CanonCameraSettings")
            
        Returns:
            Dictionary mapping values to enum names, or None
        """
        # Canon enums
        if manufacturer == 'CANON':
            # Canon CameraSettings sub-IFD enums (tag 0x0001)
            if parent_tag_name and 'CanonCameraSettings' in parent_tag_name:
                # Canon CameraSettings sub-IFD tag enums
                if tag_id == 0x0001:  # MacroMode
                    return {
                        0: "Off",
                        1: "On",
                        2: "Normal",  # Some Canon cameras use 2 for Normal mode
                    }
                elif tag_id == 0x0002:  # SelfTimer
                    return {
                        0: "Off",
                        1: "2 s",
                        2: "10 s",
                        3: "Custom",
                    }
                elif tag_id == 0x0003:  # Quality
                    return {
                        0: "Normal",
                        1: "Fine",
                        2: "RAW",
                        3: "RAW+Fine",
                        4: "RAW+Normal",
                    }
                elif tag_id == 0x000F:  # MeteringMode
                    return {
                        0: "Default",
                        1: "Spot",
                        2: "Average",
                        3: "Evaluative",
                        4: "Partial",
                        5: "Center-weighted average",
                    }
                elif tag_id == 0x0011:  # AFPointSelection
                    return {
                        0: "Manual",
                        1: "Auto",
                    }
                elif tag_id == 0x0003:  # ExposureMode
                    return {
                        0: "Easy Shooting",
                        1: "Program",
                        2: "Tv",
                        3: "Av",
                        4: "Manual",
                        5: "A-DEP",
                    }
                elif tag_id == 0x0004:  # FlashMode
                    return {
                        0: "No Flash",
                        1: "Auto",
                        2: "On",
                        3: "Red-eye Reduction",
                        4: "Slow Sync",
                        5: "Red-eye Reduction + Slow Sync",
                    }
                elif tag_id == 0x0005:  # DriveMode
                    return {
                        0: "Single",
                        1: "Continuous",
                        2: "Timer",
                    }
                elif tag_id == 0x0007:  # FocusMode
                    return {
                        0: "One-Shot AF",
                        1: "AI Servo AF",
                        2: "AI Focus AF",
                        3: "Manual Focus",
                    }
                elif tag_id == 0x0008:  # ImageSize
                    return {
                        0: "Large",
                        1: "Medium",
                        2: "Small",
                    }
                elif tag_id == 0x0009:  # Quality
                    return {
                        0: "Normal",
                        1: "Fine",
                        2: "RAW",
                        3: "RAW+Fine",
                        4: "RAW+Normal",
                    }
                elif tag_id == 0x000A:  # ISO
                    return {
                        0: "Auto",
                        15: "ISO 50",
                        16: "ISO 100",
                        17: "ISO 200",
                        18: "ISO 400",
                        19: "ISO 800",
                        20: "ISO 1600",
                        21: "ISO 3200",
                    }
                elif tag_id == 0x000B:  # MeteringMode (alternative)
                    return {
                        0: "Default",
                        1: "Spot",
                        2: "Average",
                        3: "Evaluative",
                        4: "Partial",
                        5: "Center-weighted average",
                    }
                elif tag_id == 0x000C:  # FocusType
                    return {
                        0: "Manual",
                        1: "Auto",
                        2: "Not Known",
                    }
                elif tag_id == 0x000D:  # AFPoint
                    return {
                        0: "None",
                        1: "Manual",
                        2: "Auto",
                    }
                elif tag_id == 0x000E:  # ExposureCompensation
                    # This is typically a signed value, not an enum
                    return None
                elif tag_id == 0x000F:  # ISOSpeed
                    # ISO speed values (similar to 0x000A)
                    return {
                        0: "Auto",
                        15: "ISO 50",
                        16: "ISO 100",
                        17: "ISO 200",
                        18: "ISO 400",
                        19: "ISO 800",
                        20: "ISO 1600",
                        21: "ISO 3200",
                    }
                elif tag_id == 0x001B:  # FocalLength
                    # FocalLength is typically a RATIONAL value, not an enum
                    # But if it's stored as integer, return None to use raw value
                    return None
                elif tag_id == 0x001C:  # FlashActivity
                    # FlashActivity is typically a numeric value (0 = no flash activity)
                    # Return None to use raw numeric value (not an enum)
                    return None
                elif tag_id == 0x0030:  # FlashGuideNumber
                    # FlashGuideNumber is typically a numeric value, not an enum
                    return None
            
            # Canon FlashInfo sub-IFD enums (tag 0x0003)
            elif parent_tag_name and 'CanonFlashInfo' in parent_tag_name:
                if tag_id == 0x0001:  # FlashMode
                    return {
                        0: "No Flash",
                        1: "Auto",
                        2: "On",
                        3: "Red-eye Reduction",
                        4: "Slow Sync",
                    }
                elif tag_id == 0x0003:  # FlashQuality
                    return {
                        2: "Normal",
                        3: "Fine",
                        5: "SuperFine",
                    }
            
            # Canon ShotInfo sub-IFD enums (tag 0x0004)
            elif parent_tag_name and 'CanonShotInfo' in parent_tag_name:
                if tag_id == 0x0001:  # AutoExposureBracketing
                    return {
                        0: "Off",
                        1: "On",
                    }
                elif tag_id == 0x0002:  # AEBSequence
                    return {
                        0: "0, -, +",
                        1: "-, 0, +",
                        2: "-, +, 0",
                    }
            
            # Canon ImageType (tag 0x0006)
            if tag_id == 0x0006:
                return {
                    0: "Original",
                    1: "Standard",
                    2: "Fine",
                    3: "RAW",
                }
            # Canon DateStampMode (tag 0x0012)
            elif tag_id == 0x0012:
                return {
                    0: "Off",
                    1: "Date",
                    2: "Date and Time",
                }
            # Canon MyColors (tag 0x0013)
            elif tag_id == 0x0013:
                return {
                    0: "Off",
                    1: "Vivid",
                    2: "Neutral",
                    3: "Sepia",
                    4: "B&W",
                    5: "Custom",
                }
            # Canon WhiteBalance (main tag, but also in CameraSettings sub-IFD)
            elif tag_id == 0x0007 and not parent_tag_name:
                return {
                    0: "Auto",
                    1: "Daylight",
                    2: "Cloudy",
                    3: "Tungsten",
                    4: "Fluorescent",
                    5: "Flash",
                    6: "Custom",
                    7: "Color Temperature",
                }
        
        # Nikon enums
        elif manufacturer == 'NIKON':
            # Nikon Quality (tag 0x0004)
            if tag_id == 0x0004:
                return {
                    1: "VGA Basic",
                    2: "VGA Normal",
                    3: "VGA Fine",
                    4: "SXGA Basic",
                    5: "SXGA Normal",
                    6: "SXGA Fine",
                }
            # Nikon WhiteBalance (tag 0x0005)
            elif tag_id == 0x0005:
                return {
                    0: "Auto",
                    1: "Preset",
                    2: "Daylight",
                    3: "Incandescent",
                    4: "Fluorescent",
                    5: "Cloudy",
                    6: "Speedlight",
                    7: "Shade",
                    8: "Color Temperature",
                }
            # Nikon FocusMode (tag 0x0007)
            elif tag_id == 0x0007:
                return {
                    0: "Manual",
                    1: "AF-S",
                    2: "AF-C",
                    3: "AF-A",
                }
            # Nikon ColorMode (tag 0x0003)
            elif tag_id == 0x0003:
                return {
                    1: "Color",
                    2: "Monochrome",
                }
            # Nikon ImageSharpening (tag 0x0006)
            elif tag_id == 0x0006:
                return {
                    0: "None",
                    1: "Low",
                    2: "Normal",
                    3: "High",
                }
            # Nikon FlashMode (tag 0x0009)
            elif tag_id == 0x0009:
                return {
                    0: "No Flash",
                    1: "Flash Fired",
                }
            # Nikon ExposureMode (tag 0x000A)
            elif tag_id == 0x000A:
                return {
                    0: "Program",
                    1: "Aperture Priority",
                    2: "Shutter Priority",
                    3: "Manual",
                }
            # Nikon ColorSpace (tag 0x001A)
            elif tag_id == 0x001A:
                return {
                    1: "sRGB",
                    2: "Adobe RGB",
                }
            # Nikon ActiveD-Lighting (tag 0x001D)
            elif tag_id == 0x001D:
                return {
                    0: "Off",
                    1: "Low",
                    2: "Normal",
                    3: "High",
                    4: "Extra High",
                }
            # Nikon VibrationReduction (tag 0x0024)
            elif tag_id == 0x0024:
                return {
                    0: "Off",
                    1: "On",
                }
            # Nikon PictureControl (tag 0x001E)
            elif tag_id == 0x001E:
                return {
                    0: "Standard",
                    1: "Neutral",
                    2: "Vivid",
                    3: "Monochrome",
                    4: "Portrait",
                    5: "Landscape",
                }
        
        # Sony enums
        elif manufacturer == 'SONY':
            # Sony Quality (tag 0x0102)
            if tag_id == 0x0102:
                return {
                    0: "RAW",
                    1: "RAW+JPEG",
                    2: "Fine",
                    3: "Standard",
                }
            # Sony WhiteBalance (tag 0x0115)
            elif tag_id == 0x0115:
                return {
                    0: "Auto",
                    1: "Daylight",
                    2: "Cloudy",
                    3: "Tungsten",
                    4: "Fluorescent",
                    5: "Flash",
                    6: "Color Temperature",
                    7: "Custom",
                }
            # Sony ColorMode (tag 0x0104)
            elif tag_id == 0x0104:
                return {
                    0: "Standard",
                    1: "Vivid",
                    2: "Portrait",
                    3: "Landscape",
                    4: "Sunset",
                    5: "Night View",
                    6: "B&W",
                    7: "Sepia",
                }
            # Sony SceneMode (tag 0x0107)
            elif tag_id == 0x0107:
                return {
                    0: "Auto",
                    1: "Portrait",
                    2: "Landscape",
                    3: "Macro",
                    4: "Sports",
                    5: "Sunset",
                    6: "Night View",
                    7: "Handheld Twilight",
                    8: "Anti Motion Blur",
                }
            # Sony FlashMode (tag 0x0112)
            elif tag_id == 0x0112:
                return {
                    0: "No Flash",
                    1: "Flash Fired",
                    2: "Fill Flash",
                    3: "Red-eye Reduction",
                    4: "Wireless",
                }
            # Sony ExposureMode (tag 0x0111)
            elif tag_id == 0x0111:
                return {
                    0: "Auto",
                    1: "Program",
                    2: "Aperture Priority",
                    3: "Shutter Priority",
                    4: "Manual",
                    5: "Scene Selection",
                }
            # Sony DynamicRangeOptimizer (tag 0x0102)
            elif tag_id == 0x0102:
                return {
                    0: "Off",
                    1: "Standard",
                    2: "Plus",
                }
            # Sony ImageStabilization (tag 0x0103)
            elif tag_id == 0x0103:
                return {
                    0: "Off",
                    1: "On",
                }
        
        # Olympus enums
        elif manufacturer == 'OLYMPUS':
            # Olympus Quality (tag 0x0101)
            if tag_id == 0x0101:
                return {
                    1: "SQ",
                    2: "HQ",
                    3: "SHQ",
                    4: "RAW",
                }
            # Olympus SpecialMode (tag 0x0100)
            elif tag_id == 0x0100:
                return {
                    0: "Normal",
                    1: "Unknown",
                    2: "Fast",
                    3: "Panorama",
                }
            # Olympus Macro (tag 0x0102)
            elif tag_id == 0x0102:
                return {
                    0: "Off",
                    1: "On",
                }
            # Olympus BWMode (tag 0x0103)
            elif tag_id == 0x0103:
                return {
                    0: "Off",
                    1: "On",
                }
            # Olympus WhiteBalance (tag 0x0104)
            elif tag_id == 0x0104:
                return {
                    0: "Auto",
                    1: "Daylight",
                    2: "Cloudy",
                    3: "Tungsten",
                    4: "Fluorescent",
                }
            # Olympus PictureMode (tag 0x0116)
            elif tag_id == 0x0116:
                return {
                    1: "i-Auto",
                    2: "Program",
                    3: "Aperture Priority",
                    4: "Shutter Priority",
                    5: "Manual",
                }
            # Olympus FlashMode (tag 0x010C)
            elif tag_id == 0x010C:
                return {
                    0: "No Flash",
                    1: "Flash Fired",
                }
            # Olympus FocusMode (tag 0x010D)
            elif tag_id == 0x010D:
                return {
                    0: "Auto",
                    1: "Manual",
                }
        
        # Pentax enums
        elif manufacturer == 'PENTAX':
            # Pentax Quality (tag 0x0009)
            if tag_id == 0x0009:
                return {
                    0: "Good",
                    1: "Better",
                    2: "Best",
                    3: "TIFF",
                    4: "RAW",
                }
            # Pentax Mode (tag 0x0002)
            elif tag_id == 0x0002:
                return {
                    0: "Auto",
                    1: "Program",
                    2: "Aperture Priority",
                    3: "Shutter Priority",
                    4: "Manual",
                    5: "Bulb",
                }
            # Pentax Flash (tag 0x000B)
            elif tag_id == 0x000B:
                return {
                    0: "No Flash",
                    1: "Flash Fired",
                }
            # Pentax WhiteBalance (tag 0x0007)
            elif tag_id == 0x0007:
                return {
                    0: "Auto",
                    1: "Daylight",
                    2: "Shade",
                    3: "Cloudy",
                    4: "Tungsten",
                    5: "Fluorescent",
                    6: "Flash",
                }
            # Pentax ColorSpace (tag 0x0013)
            elif tag_id == 0x0013:
                return {
                    1: "sRGB",
                    2: "Adobe RGB",
                }
            # Pentax FocusMode (tag 0x0008)
            elif tag_id == 0x0008:
                return {
                    0: "Manual",
                    1: "AF-S",
                    2: "AF-C",
                }
        
        # Fujifilm enums
        elif manufacturer == 'FUJIFILM':
            # Fujifilm Quality (tag 0x1002) - Note: 0x1000 is Version, not Quality
            if tag_id == 0x1002:
                return {
                    0: "NORMAL",
                    1: "FINE",
                    2: "RAW",
                    3: "RAW+FINE",
                    4: "RAW+",
                }
            # Fujifilm Sharpness (tag 0x1003) - Note: 0x1001 is SerialNumber, 0x101D is also Sharpness
            elif tag_id == 0x1003 or tag_id == 0x101D:
                return {
                    0: "Soft",
                    1: "Normal",
                    2: "Hard",
                    3: "Medium Soft",
                    4: "Medium Hard",
                }
            # Fujifilm WhiteBalance (tag 0x1004) - Note: 0x1025 is also WhiteBalance
            elif tag_id == 0x1004 or tag_id == 0x1025:
                return {
                    0: "Auto",
                    256: "Daylight",
                    512: "Cloudy",
                    768: "Tungsten",
                    1024: "Fluorescent",
                    1280: "Custom",
                }
            # Fujifilm Color (tag 0x1005) - Saturation
            elif tag_id == 0x1005:
                return {
                    0: "Standard",
                    1: "High",
                    2: "Low",
                }
            # Fujifilm Tone (tag 0x1006)
            elif tag_id == 0x1006:
                return {
                    0: "Standard",
                    1: "High",
                    2: "Low",
                }
            # Fujifilm FlashMode (tag 0x101A)
            elif tag_id == 0x101A:
                return {
                    0: "Off",
                    1: "On",
                    2: "Red-eye Reduction",
                    3: "External",
                }
            # Fujifilm FocusMode (tag 0x1017)
            elif tag_id == 0x1017:
                return {
                    0: "Manual",
                    1: "AF-S",
                    2: "AF-C",
                }
            # Fujifilm ShutterType (tag 0x1020 or 0x1050)
            elif tag_id == 0x1020 or tag_id == 0x1050:
                return {
                    0: "Mechanical",
                    1: "Electronic",
                    2: "Electronic (Front Curtain)",
                }
            # Fujifilm SlowSync (tag 0x1019 or 0x1030)
            elif tag_id == 0x1019 or tag_id == 0x1030:
                return {
                    0: "Off",
                    1: "On",
                }
            # Fujifilm PictureMode (tag 0x1031)
            elif tag_id == 0x1031:
                return {
                    0: "Auto",
                    1: "Program AE",
                    2: "Aperture-priority AE",
                    3: "Shutter-priority AE",
                    4: "Manual",
                    5: "Scene Position",
                    256: "Aperture-priority AE",
                    512: "Shutter-priority AE",
                }
            # Fujifilm DynamicRangeSetting (tag 0x100A)
            elif tag_id == 0x100A:
                return {
                    0: "Auto",
                    1: "Manual",
                }
            # Fujifilm LensModulationOptimizer (tag 0x1045)
            elif tag_id == 0x1045:
                return {
                    0: "Off",
                    1: "On",
                }
            # Fujifilm FileSource (tag 0x1010)
            elif tag_id == 0x1010:
                return {
                    0: "Digital Camera",
                    1: "Film Scanner",
                    2: "Reflection Print Scanner",
                }
            # Fujifilm DynamicRange (tag 0x1008)
            elif tag_id == 0x1008:
                return {
                    0: "Standard",
                    1: "Wide",
                    256: "Standard",
                    512: "Wide",
                }
            # Fujifilm FilmMode (tag 0x1009) - Note: FilmMode can be string or enum
            # Common values: "F0/Standard (Provia)", "F1/Standard (Provia)", etc.
            # For enum values, map common numeric values
            elif tag_id == 0x1009:
                return {
                    0: "F0/Standard (Provia)",
                    1: "F1/Standard (Provia)",
                    2: "F2/Standard (Provia)",
                    3: "F3/Standard (Provia)",
                }
            # Fujifilm NoiseReduction (tag 0x1028)
            elif tag_id == 0x1028:
                return {
                    0: "0 (normal)",
                    1: "1 (low)",
                    2: "2 (normal)",
                    3: "3 (high)",
                    4: "4 (normal+)",
                    5: "5 (low+)",
                    6: "6 (normal++)",
                    7: "7 (high++)",
                }
            # Fujifilm ImageStabilization (tag 0x101F) - Note: Can be complex string format
            # Common values: "Off", "On", "Optical; On (mode 1, continuous); 0"
            elif tag_id == 0x101F:
                return {
                    0: "Off",
                    1: "On",
                    2: "Optical; On (mode 1, continuous); 0",
                }
        
        # Panasonic enums
        elif manufacturer == 'PANASONIC':
            # Panasonic Quality (tag 0x0001)
            if tag_id == 0x0001:
                return {
                    2: "High",
                    3: "Normal",
                    6: "Very High",
                    7: "RAW",
                }
            # Panasonic FirmwareVersion (tag 0x0002) - string, no enum
            # Panasonic WhiteBalance (tag 0x0003)
            elif tag_id == 0x0003:
                return {
                    1: "Auto",
                    2: "Daylight",
                    3: "Cloudy",
                    4: "Tungsten",
                    5: "Fluorescent",
                    6: "Shade",
                    7: "Color Temperature",
                }
            # Panasonic FocusMode (tag 0x0004)
            elif tag_id == 0x0004:
                return {
                    1: "Auto",
                    2: "Manual",
                    4: "AF-S",
                    5: "AF-C",
                }
            # Panasonic AFAreaMode (tag 0x0005)
            elif tag_id == 0x0005:
                return {
                    0: "Off",
                    1: "1-area",
                    2: "Multi-area",
                    3: "Tracking",
                }
            # Panasonic ImageStabilization (tag 0x0006)
            elif tag_id == 0x0006:
                return {
                    0: "Off",
                    1: "On",
                }
            # Panasonic MacroMode (tag 0x0007)
            elif tag_id == 0x0007:
                return {
                    0: "Off",
                    1: "On",
                    2: "Off",  # Some cameras use 2 for Off
                }
            # Panasonic ShootingMode (tag 0x0008)
            elif tag_id == 0x0008:
                return {
                    1: "Program",
                    2: "Aperture Priority",
                    3: "Shutter Priority",
                    4: "Manual",
                }
            # Panasonic Audio (tag 0x0009)
            elif tag_id == 0x0009:
                return {
                    0: "No",
                    1: "Yes",
                }
            # Panasonic FlashMode (tag 0x000C)
            elif tag_id == 0x000C:
                return {
                    0: "No Flash",
                    1: "Flash Fired",
                }
            # Panasonic ColorMode (tag 0x000E)
            elif tag_id == 0x000E:
                return {
                    0: "Standard",
                    1: "Vivid",
                    2: "Natural",
                }
            # Panasonic Sharpness (tag 0x00EC)
            elif tag_id == 0x00EC:
                return {
                    0: "Off",
                    1: "Low",
                    2: "Normal",
                    3: "High",
                    4: "Standard",
                    5: "Medium Low",
                    6: "Medium High",
                }
            # Panasonic FilmMode (tag 0x00A5, 0x00CA)
            elif tag_id in (0x00A5, 0x00CA):
                return {
                    0: "Standard (color)",
                    1: "Dynamic (color)",
                    2: "Nature (color)",
                    3: "Smooth (color)",
                    4: "Standard (B&W)",
                    5: "Dynamic (B&W)",
                    6: "Smooth (B&W)",
                    7: "n/a",
                }
            # Panasonic FocusMode (tag 0x00CE) - alternative tag ID
            elif tag_id == 0x00CE:
                return {
                    1: "Auto",
                    2: "Manual",
                    4: "AF-S",
                    5: "AF-C",
                }
            # Panasonic ImageStabilization (tag 0x00D1) - alternative tag ID
            elif tag_id == 0x00D1:
                return {
                    0: "Off",
                    1: "On",
                    2: "Mode 1",
                    3: "Mode 2",
                }
        
        return None
    
    def _get_flag_map(self, manufacturer: str, tag_id: int, parent_tag_name: Optional[str] = None) -> Optional[Dict[int, str]]:
        """
        Get flag mapping for a tag.
        
        Args:
            manufacturer: Camera manufacturer
            tag_id: Tag ID
            parent_tag_name: Parent tag name for sub-IFD context (e.g., "CanonCameraSettings")
            
        Returns:
            Dictionary mapping bit positions to flag names, or None
        """
        # Canon flags
        if manufacturer == 'CANON':
            # Canon CustomFunctions flags (tag 0x000C)
            if tag_id == 0x000C:
                return {
                    0: "LongExposureNoiseReduction",
                    1: "ShutterAELockButton",
                    2: "MirrorLockup",
                    3: "ExposureLevelIncrements",
                    4: "ISOExpansion",
                    5: "AEBSequence",
                }
            # Canon CameraSettings sub-IFD flags
            elif parent_tag_name and 'CanonCameraSettings' in parent_tag_name:
                if tag_id == 0x0001:  # MeteringMode flags
                    return {
                        0: "Spot",
                        1: "Average",
                        2: "Evaluative",
                        3: "Partial",
                        4: "Center-weighted average",
                    }
                elif tag_id == 0x0004:  # FlashMode flags
                    return {
                        0: "No Flash",
                        1: "Auto",
                        2: "On",
                        3: "Red-eye Reduction",
                        4: "Slow Sync",
                    }
            # Canon CameraSettings flags (main tag)
            elif tag_id == 0x0001 and not parent_tag_name:
                return {
                    0: "MacroMode",
                    1: "SelfTimer",
                    2: "Quality",
                    3: "FlashMode",
                }
        
        # Nikon flags
        elif manufacturer == 'NIKON':
            # Nikon FlashSetting flags (tag 0x0008)
            if tag_id == 0x0008:
                return {
                    0: "FlashFired",
                    1: "FlashMode",
                    2: "FlashCompensation",
                }
            # Nikon ImageProcessing flags (tag 0x0016)
            elif tag_id == 0x0016:
                return {
                    0: "NoiseReduction",
                    1: "ActiveD-Lighting",
                    2: "VignetteControl",
                }
        
        # Sony flags
        elif manufacturer == 'SONY':
            # Sony CameraSettings flags
            if tag_id == 0x0100:
                return {
                    0: "AFMode",
                    1: "AFAreaMode",
                    2: "FocusMode",
                }
        
        # Olympus flags
        elif manufacturer == 'OLYMPUS':
            # Olympus SpecialMode flags (tag 0x0100)
            if tag_id == 0x0100:
                return {
                    0: "Normal",
                    1: "Unknown",
                    2: "Fast",
                    3: "Panorama",
                }
        
        # Pentax flags
        elif manufacturer == 'PENTAX':
            # Pentax Flash flags (tag 0x000B)
            if tag_id == 0x000B:
                return {
                    0: "No Flash",
                    1: "Flash Fired",
                }
        
        # Fujifilm flags
        elif manufacturer == 'FUJIFILM':
            # Fujifilm flags (if any)
            pass
        
        # Panasonic flags
        elif manufacturer == 'PANASONIC':
            # Panasonic ImageStabilization flags (tag 0x0006)
            if tag_id == 0x0006:
                return {
                    0: "Off",
                    1: "On",
                }
        
        # Add more flag mappings as needed
        return None
    
    def decode_nikon_value(
        self,
        tag_id: int,
        tag_type: int,
        tag_count: int,
        data: bytes,
        offset: int,
        tiff_start: Optional[int] = None,
        endian: Optional[str] = None
    ) -> Any:
        """
        Decode Nikon MakerNote tag value with enum and flag support.
        
        Args:
            tag_id: Tag ID
            tag_type: Tag data type
            tag_count: Number of values
            data: Raw data bytes
            offset: Offset to tag data
            tiff_start: TIFF start offset (for offset calculation, unused but kept for compatibility)
            endian: Byte order to use (if None, uses self.endian)
            
        Returns:
            Decoded value (with enum/flag interpretation if applicable)
        """
        # Use provided endianness or fall back to self.endian
        use_endian = endian if endian is not None else self.endian
        raw_value = self._decode_raw_value(tag_type, tag_count, data, offset, endian=use_endian)
        return self._apply_enum_flags('NIKON', tag_id, raw_value, None)
    
    def decode_sony_value(
        self,
        tag_id: int,
        tag_type: int,
        tag_count: int,
        data: bytes,
        offset: int,
        parent_tag_name: Optional[str] = None
    ) -> Any:
        """
        Decode Sony MakerNote tag value with enum and flag support.
        
        Args:
            tag_id: Tag ID
            tag_type: Tag data type
            tag_count: Number of values
            data: Raw data bytes
            offset: Offset to tag data
            parent_tag_name: Parent tag name for sub-IFD context (unused for Sony)
            
        Returns:
            Decoded value (with enum/flag interpretation if applicable)
        """
        raw_value = self._decode_raw_value(tag_type, tag_count, data, offset)
        return self._apply_enum_flags('SONY', tag_id, raw_value, parent_tag_name)
    
    def decode_olympus_value(
        self,
        tag_id: int,
        tag_type: int,
        tag_count: int,
        data: bytes,
        offset: int,
        tiff_start: Optional[int] = None,
        parent_tag_name: Optional[str] = None
    ) -> Any:
        """
        Decode Olympus MakerNote tag value with enum and flag support.
        
        Args:
            tag_id: Tag ID
            tag_type: Tag data type
            tag_count: Number of values
            data: Raw data bytes
            offset: Offset to tag data
            tiff_start: TIFF start offset (for offset calculation, unused but kept for compatibility)
            parent_tag_name: Parent tag name for sub-IFD context (e.g., "CameraSettings", "Equipment", "RawDev")
            
        Returns:
            Decoded value (with enum/flag interpretation if applicable)
        """
        raw_value = self._decode_raw_value(tag_type, tag_count, data, offset, parent_tag_name=parent_tag_name)
        return self._apply_enum_flags('OLYMPUS', tag_id, raw_value, parent_tag_name)
    
    def decode_pentax_value(
        self,
        tag_id: int,
        tag_type: int,
        tag_count: int,
        data: bytes,
        offset: int,
        parent_tag_name: Optional[str] = None
    ) -> Any:
        """
        Decode Pentax/Ricoh MakerNote tag value with enum and flag support.
        
        Args:
            tag_id: Tag ID
            tag_type: Tag data type
            tag_count: Number of values
            data: Raw data bytes
            offset: Offset to tag data
            parent_tag_name: Parent tag name for sub-IFD context (unused for Pentax)
            
        Returns:
            Decoded value (with enum/flag interpretation if applicable)
        """
        # Special handling for PentaxModelID (0x0005) - may be embedded TIFF structure
        # PentaxModelID can be stored as UNDEFINED type (7) with embedded TIFF structure
        if tag_id == 0x0005:  # PentaxModelID
            try:
                if offset + 8 <= len(data):
                    # Check for embedded TIFF structure (II*\x00 or MM\x00*)
                    tiff_sig = data[offset:offset + 4]
                    if tiff_sig in (b'II*\x00', b'MM\x00*'):
                        # Embedded TIFF structure - try to extract model string
                        # The model string is typically in the first IFD
                        # Look for ASCII string in the data
                        # Try to find a readable string in the first 200 bytes
                        search_end = min(offset + 200, len(data))
                        for i in range(offset + 4, search_end - 10):
                            # Look for printable ASCII string (at least 3 characters)
                            if 32 <= data[i] <= 126:  # Printable ASCII
                                # Try to extract string
                                string_bytes = bytearray()
                                j = i
                                while j < search_end and 32 <= data[j] <= 126:
                                    string_bytes.append(data[j])
                                    j += 1
                                if len(string_bytes) >= 3:
                                    model_str = string_bytes.decode('ascii', errors='ignore')
                                    # Check if it looks like a model name (contains letters and possibly numbers/dashes)
                                    if any(c.isalpha() for c in model_str) and len(model_str) >= 3:
                                        return model_str
            except (UnicodeDecodeError, IndexError, ValueError):
                pass
        
        # Special handling for Pentax Date (0x0006) and Time (0x0007) tags
        # These are stored as UNDEFINED type (7) but should be decoded as ASCII strings
        if tag_id in (0x0006, 0x0007) and tag_type == 7:  # UNDEFINED type
            try:
                if offset + tag_count <= len(data):
                    # Read the bytes and decode as ASCII string
                    date_time_bytes = data[offset:offset + tag_count]
                    # Remove null terminators and decode
                    date_time_str = date_time_bytes.rstrip(b'\x00').decode('ascii', errors='replace')
                    if date_time_str:
                        # Format Date as "YYYY:MM:DD" and Time as "HH:MM:SS"
                        if tag_id == 0x0006:  # Date
                            # Date might be stored as "YYYYMMDD" or "YYYY:MM:DD"
                            if len(date_time_str) == 8 and date_time_str.isdigit():
                                # Format as "YYYY:MM:DD"
                                return f"{date_time_str[0:4]}:{date_time_str[4:6]}:{date_time_str[6:8]}"
                            return date_time_str
                        elif tag_id == 0x0007:  # Time
                            # Time might be stored as "HHMMSS" or "HH:MM:SS"
                            if len(date_time_str) == 6 and date_time_str.isdigit():
                                # Format as "HH:MM:SS"
                                return f"{date_time_str[0:2]}:{date_time_str[2:4]}:{date_time_str[4:6]}"
                            return date_time_str
            except (UnicodeDecodeError, IndexError, ValueError):
                pass
        
        raw_value = self._decode_raw_value(tag_type, tag_count, data, offset)
        return self._apply_enum_flags('PENTAX', tag_id, raw_value, parent_tag_name)
    
    def decode_fujifilm_value(
        self,
        tag_id: int,
        tag_type: int,
        tag_count: int,
        data: bytes,
        offset: int,
        parent_tag_name: Optional[str] = None
    ) -> Any:
        """
        Decode Fujifilm MakerNote tag value with enum and flag support.
        
        Args:
            tag_id: Tag ID
            tag_type: Tag data type
            tag_count: Number of values
            data: Raw data bytes
            offset: Offset to tag data
            parent_tag_name: Parent tag name for sub-IFD context (unused for Fujifilm)
            
        Returns:
            Decoded value (with enum/flag interpretation if applicable)
        """
        # Special handling for FilmMode tag (0x1009) - can be stored as ASCII string
        if tag_id == 0x1009:  # FilmMode
            try:
                if tag_type == 2:  # ASCII string
                    # Find null terminator
                    end = data.find(b'\x00', offset)
                    if end == -1:
                        end = offset + tag_count
                    filmmode_str = data[offset:end].decode('ascii', errors='replace').strip()
                    # Remove trailing spaces
                    filmmode_str = filmmode_str.rstrip()
                    if filmmode_str:
                        return filmmode_str
                elif tag_type == 1:  # BYTE array
                    # FilmMode can be stored as BYTE array - decode as ASCII
                    if offset + tag_count <= len(data):
                        filmmode_bytes = data[offset:offset+tag_count]
                        # Remove null bytes and decode
                        filmmode_bytes = filmmode_bytes.rstrip(b'\x00')
                        filmmode_str = filmmode_bytes.decode('ascii', errors='replace').strip()
                        filmmode_str = filmmode_str.rstrip()
                        if filmmode_str:
                            return filmmode_str
                elif tag_type == 7:  # UNDEFINED
                    # FilmMode can be stored as UNDEFINED - decode as ASCII
                    if offset + tag_count <= len(data):
                        filmmode_bytes = data[offset:offset+tag_count]
                        filmmode_bytes = filmmode_bytes.rstrip(b'\x00')
                        filmmode_str = filmmode_bytes.decode('ascii', errors='replace').strip()
                        filmmode_str = filmmode_str.rstrip()
                        if filmmode_str:
                            return filmmode_str
            except:
                pass
        
        # Special handling for Version tags (0x0000 and 0x1000) - decode as ASCII string
        if tag_id == 0x0000 or tag_id == 0x1000:  # Version or FujifilmVersion tag
            try:
                if tag_type == 2:  # ASCII string
                    # Find null terminator
                    end = data.find(b'\x00', offset)
                    if end == -1:
                        end = offset + tag_count
                    version_str = data[offset:end].decode('ascii', errors='replace').strip()
                    # Remove trailing spaces that might come from padding
                    version_str = version_str.rstrip()
                    return version_str
                elif tag_type == 1:  # BYTE array
                    # Version can be stored as BYTE array - decode as ASCII
                    if offset + tag_count <= len(data):
                        version_bytes = data[offset:offset+tag_count]
                        # Remove null bytes and decode
                        version_bytes = version_bytes.rstrip(b'\x00')
                        version_str = version_bytes.decode('ascii', errors='replace').strip()
                        version_str = version_str.rstrip()
                        return version_str
                elif tag_type == 7:  # UNDEFINED
                    # Version can be stored as UNDEFINED - decode as ASCII
                    if offset + tag_count <= len(data):
                        version_bytes = data[offset:offset+tag_count]
                        version_bytes = version_bytes.rstrip(b'\x00')
                        version_str = version_bytes.decode('ascii', errors='replace').strip()
                        version_str = version_str.rstrip()
                        return version_str
                elif tag_type == 3:  # SHORT - sometimes version is stored as SHORT array
                    # Try to decode as ASCII from SHORT values
                    raw_value = self._decode_raw_value(tag_type, tag_count, data, offset)
                    if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 2:
                        # Convert SHORT values to ASCII characters if in printable range
                        version_chars = []
                        for val in raw_value:
                            if 32 <= val <= 126:  # Printable ASCII
                                version_chars.append(chr(val))
                            elif val == 0:  # Null terminator
                                break
                        if version_chars:
                            return ''.join(version_chars).strip()
            except:
                pass
        
        # Special handling for numeric tags that need proper formatting
        raw_value = self._decode_raw_value(tag_type, tag_count, data, offset)
        
        # Handle ISO tag (0x1023) - format as single value
        if tag_id == 0x1023:  # ISO
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                # ISO can be stored as array, take first value
                return str(raw_value[0])
            elif isinstance(raw_value, (list, tuple)) and len(raw_value) >= 2:
                # Some ISO tags have 2 values (base ISO and extended ISO)
                # Format as space-separated if both present
                return ' '.join(str(v) for v in raw_value[:2])
        
        # Handle Aperture tag (0x1022) - format as decimal
        if tag_id == 0x1022:  # Aperture
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                # Aperture is typically stored as RATIONAL - convert to decimal
                aperture_val = raw_value[0]
                if isinstance(aperture_val, (list, tuple)) and len(aperture_val) == 2:
                    # RATIONAL format: numerator/denominator
                    num, den = aperture_val
                    if den != 0:
                        return f"{num / den:.1f}"
                else:
                    return str(aperture_val)
            elif isinstance(raw_value, (int, float)):
                return f"{raw_value:.1f}"
        
        # Handle ShutterSpeed tag (0x1021) - format as fraction (1/X) to standard format
        if tag_id == 0x1021:  # ShutterSpeed
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                # ShutterSpeed is typically stored as RATIONAL - convert to fraction format
                speed_val = raw_value[0]
                if isinstance(speed_val, (list, tuple)) and len(speed_val) == 2:
                    # RATIONAL format: numerator/denominator
                    num, den = speed_val
                    if den != 0:
                        exposure_time = num / den
                        # Format as fraction if < 1 second (matching standard format)
                        if exposure_time < 1 and exposure_time > 0:
                            # Find closest 1/X representation
                            closest_den = round(1.0 / exposure_time)
                            if abs(exposure_time - 1.0/closest_den) < 0.01:  # Allow small tolerance
                                return f"1/{closest_den}"
                        # For >= 1 second, show as decimal
                        elif exposure_time >= 1:
                            if exposure_time == int(exposure_time):
                                return f"{int(exposure_time)}"
                            return f"{exposure_time:.3f}"
                        # Fallback to decimal for very small values
                        return f"{exposure_time:.3f}"
                else:
                    # Not a RATIONAL, try to format as fraction if it's a small decimal
                    if isinstance(speed_val, (int, float)) and 0 < speed_val < 1:
                        closest_den = round(1.0 / speed_val)
                        if abs(speed_val - 1.0/closest_den) < 0.01:
                            return f"1/{closest_den}"
                    return str(speed_val)
            elif isinstance(raw_value, (int, float)):
                # Format as fraction if < 1 second
                if 0 < raw_value < 1:
                    closest_den = round(1.0 / raw_value)
                    if abs(raw_value - 1.0/closest_den) < 0.01:
                        return f"1/{closest_den}"
                # For >= 1 second, show as integer or decimal
                elif raw_value >= 1:
                    if raw_value == int(raw_value):
                        return f"{int(raw_value)}"
                    return f"{raw_value:.3f}"
                return f"{raw_value:.3f}"
        
        # Handle ExposureCompensation tag (0x1024) - format as decimal
        if tag_id == 0x1024:  # ExposureCompensation
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                # ExposureCompensation is typically stored as RATIONAL
                ec_val = raw_value[0]
                if isinstance(ec_val, (list, tuple)) and len(ec_val) == 2:
                    num, den = ec_val
                    if den != 0:
                        return f"{num / den:.1f}"
                else:
                    return str(ec_val)
            elif isinstance(raw_value, (int, float)):
                return f"{raw_value:.1f}"
        
        # Handle DevelopmentDynamicRange tag (0x100B) - format as integer
        if tag_id == 0x100B:  # DevelopmentDynamicRange
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                return str(raw_value[0])
        
        # Handle WhiteBalanceFineTune tag (0x1026) - format as "Red +X, Blue +Y"
        if tag_id == 0x1026:  # WhiteBalanceFineTune
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 2:
                # Format as "Red +X, Blue +Y" (matching standard format)
                red_val = raw_value[0]
                blue_val = raw_value[1]
                # Convert to signed values if needed (subtract 64 for offset)
                red_signed = red_val - 64 if red_val >= 64 else red_val
                blue_signed = blue_val - 64 if blue_val >= 64 else blue_val
                red_str = f"+{red_signed}" if red_signed >= 0 else str(red_signed)
                blue_str = f"+{blue_signed}" if blue_signed >= 0 else str(blue_signed)
                return f"Red {red_str}, Blue {blue_str}"
        
        # Handle ExposureCount tag (0x1032) - format as integer
        if tag_id == 0x1032:  # ExposureCount
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                return str(int(raw_value[0]))
            elif isinstance(raw_value, (int, float)):
                return str(int(raw_value))
        
        # Handle FacesDetected tag (0x102A) - format as integer
        if tag_id == 0x102A:  # FacesDetected
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                return str(int(raw_value[0]))
            elif isinstance(raw_value, (int, float)):
                return str(int(raw_value))
        
        # Handle FlashExposureComp tag (0x101E) - format as decimal
        if tag_id == 0x101E:  # FlashExposureComp
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                # FlashExposureComp is typically stored as RATIONAL
                fec_val = raw_value[0]
                if isinstance(fec_val, (list, tuple)) and len(fec_val) == 2:
                    num, den = fec_val
                    if den != 0:
                        return f"{num / den:.1f}"
                else:
                    return str(fec_val)
            elif isinstance(raw_value, (int, float)):
                return f"{raw_value:.1f}"
        
        # Handle FocusPixel tag (0x1018) - format as space-separated values
        if tag_id == 0x1018:  # FocusPixel
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 2:
                # Format as space-separated values (e.g., "961 641")
                return ' '.join(str(int(v)) for v in raw_value[:2])
            elif isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                return str(int(raw_value[0]))
        
        # Handle MaxApertureAtMaxFocal tag (0x100F) - format as integer or decimal
        if tag_id == 0x100F:  # MaxApertureAtMaxFocal
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                aperture_val = raw_value[0]
                if isinstance(aperture_val, (list, tuple)) and len(aperture_val) == 2:
                    # RATIONAL format
                    num, den = aperture_val
                    if den != 0:
                        val = num / den
                        if val == int(val):
                            return str(int(val))
                        return f"{val:.1f}"
                else:
                    if isinstance(aperture_val, float) and aperture_val == int(aperture_val):
                        return str(int(aperture_val))
                    return str(aperture_val)
            elif isinstance(raw_value, (int, float)):
                if raw_value == int(raw_value):
                    return str(int(raw_value))
                return f"{raw_value:.1f}"
        
        # Handle MaxFocalLength tag (0x100D) - format as integer
        if tag_id == 0x100D:  # MaxFocalLength
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                focal_val = raw_value[0]
                if isinstance(focal_val, (list, tuple)) and len(focal_val) == 2:
                    # RATIONAL format
                    num, den = focal_val
                    if den != 0:
                        return str(int(num / den))
                else:
                    return str(int(focal_val))
            elif isinstance(raw_value, (int, float)):
                return str(int(raw_value))
        
        # Handle MinFocalLength tag (0x100C) - format as integer
        if tag_id == 0x100C:  # MinFocalLength
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                focal_val = raw_value[0]
                if isinstance(focal_val, (list, tuple)) and len(focal_val) == 2:
                    # RATIONAL format
                    num, den = focal_val
                    if den != 0:
                        return str(int(num / den))
                else:
                    return str(int(focal_val))
            elif isinstance(raw_value, (int, float)):
                return str(int(raw_value))
        
        return self._apply_enum_flags('FUJIFILM', tag_id, raw_value, parent_tag_name)
    
    def decode_panasonic_value(
        self,
        tag_id: int,
        tag_type: int,
        tag_count: int,
        data: bytes,
        offset: int,
        parent_tag_name: Optional[str] = None
    ) -> Any:
        """
        Decode Panasonic MakerNote tag value with enum and flag support.
        
        Args:
            tag_id: Tag ID
            tag_type: Tag data type
            tag_count: Number of values
            data: Raw data bytes
            offset: Offset to tag data
            parent_tag_name: Parent tag name for sub-IFD context (unused for Panasonic)
            
        Returns:
            Decoded value (with enum/flag interpretation if applicable)
        """
        # Special handling for FirmwareVersion (tag 0x0002) and LensFirmwareVersion (tag 0x0060) - format as version string
        if tag_id == 0x0002 or tag_id == 0x0060:  # FirmwareVersion or LensFirmwareVersion
            raw_value = self._decode_raw_value(tag_type, tag_count, data, offset)
            # FirmwareVersion is typically a BYTE array (type 1) that should be formatted as "X Y Z W" (space-separated, matching standard format)
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 2:
                # Format as version string: "X Y Z W" (space-separated to standard format)
                version_parts = [str(v) for v in raw_value[:4]]  # Take first 4 bytes
                return ' '.join(version_parts)
            elif isinstance(raw_value, bytes) and len(raw_value) >= 2:
                # If it's bytes, convert to list of integers
                version_parts = [str(b) for b in raw_value[:4]]
                return ' '.join(version_parts)
            elif isinstance(raw_value, str) and len(raw_value) >= 2:
                # If it's a string with binary data, try to extract bytes
                try:
                    version_parts = [str(ord(c)) for c in raw_value[:4]]
                    return ' '.join(version_parts)
                except:
                    pass
            # Fallback: return raw value if we can't format it
            return raw_value
        
        # Special handling for WB_RBLevels tags (0x000F, 0x001C, 0x001D, 0x001E, 0x001F)
        # These should be formatted as "Red Green1 Green2 Blue" (4 values, space-separated)
        if tag_id in (0x000F, 0x001C, 0x001D, 0x001E, 0x001F):  # WB_RBLevels variants
            raw_value = self._decode_raw_value(tag_type, tag_count, data, offset)
            # WB_RBLevels should be 4 unsigned shorts (type 3) or 4 unsigned longs (type 4)
            # Format: "Red Green1 Green2 Blue" (space-separated)
            if isinstance(raw_value, (list, tuple)):
                # If we have 4 values, format as space-separated string
                if len(raw_value) >= 4:
                    return ' '.join(str(v) for v in raw_value[:4])
                # If we have fewer values, pad with zeros or use what we have
                elif len(raw_value) > 0:
                    # Pad to 4 values with zeros if needed
                    padded = list(raw_value) + [0] * (4 - len(raw_value))
                    return ' '.join(str(v) for v in padded[:4])
            elif isinstance(raw_value, (int, float)):
                # Single value - might be a single component, try to read 4 values from data
                # Re-read as array if possible
                try:
                    import struct
                    # Try to read 4 unsigned shorts (little-endian for Panasonic)
                    if offset + 8 <= len(data):
                        values = struct.unpack('<HHHH', data[offset:offset+8])
                        return ' '.join(str(v) for v in values)
                    # Try 4 unsigned longs
                    elif offset + 16 <= len(data):
                        values = struct.unpack('<IIII', data[offset:offset+16])
                        return ' '.join(str(v) for v in values)
                except:
                    pass
                # Fallback: return as single value (will be handled by post-processing)
                return str(raw_value)
            elif isinstance(raw_value, str):
                # Already formatted string - check if it has 4 values
                parts = raw_value.split()
                if len(parts) >= 4:
                    return raw_value  # Already correct format
                elif len(parts) > 0:
                    # Pad to 4 values
                    padded = parts + ['0'] * (4 - len(parts))
                    return ' '.join(padded[:4])
            # Fallback: return raw value (will be handled by post-processing in makernote_parser)
            return raw_value
        
        # Decode raw value first
        raw_value = self._decode_raw_value(tag_type, tag_count, data, offset)
        
        # Special handling for Sharpness tag (0x00EC) - format as enum value
        if tag_id == 0x00EC:  # Sharpness
            if isinstance(raw_value, (int, float)):
                sharpness_map = {
                    0: "Off",
                    1: "Low",
                    2: "Normal",
                    3: "High",
                    4: "Standard",
                    5: "Medium Low",
                    6: "Medium High",
                }
                int_val = int(raw_value)
                if int_val in sharpness_map:
                    return sharpness_map[int_val]
            elif isinstance(raw_value, (list, tuple)) and len(raw_value) > 0:
                sharpness_map = {
                    0: "Off",
                    1: "Low",
                    2: "Normal",
                    3: "High",
                    4: "Standard",
                    5: "Medium Low",
                    6: "Medium High",
                }
                int_val = int(raw_value[0])
                if int_val in sharpness_map:
                    return sharpness_map[int_val]
        
        # Special handling for ExposureCompensation - format as decimal with sign
        # Check multiple possible tag IDs for ExposureCompensation
        if tag_id in (0x000E, 0x0017, 0x0018):  # Possible ExposureCompensation tag IDs
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                # ExposureCompensation is typically stored as RATIONAL or signed value
                ec_val = raw_value[0]
                if isinstance(ec_val, (list, tuple)) and len(ec_val) == 2:
                    num, den = ec_val
                    if den != 0:
                        result = num / den
                        # Format as decimal with 2 decimal places, matching standard format
                        if result == 0:
                            return "0"
                        elif result > 0:
                            return f"+{result:.2f}".rstrip('0').rstrip('.')
                        else:
                            return f"{result:.2f}".rstrip('0').rstrip('.')
                elif isinstance(ec_val, (int, float)):
                    result = float(ec_val)
                    # Panasonic ExposureCompensation may need offset adjustment (check if value > 100, subtract 128)
                    if result > 100:
                        result = result - 128
                    if result == 0:
                        return "0"
                    elif result > 0:
                        return f"+{result:.2f}".rstrip('0').rstrip('.')
                    else:
                        return f"{result:.2f}".rstrip('0').rstrip('.')
            elif isinstance(raw_value, (int, float)):
                result = float(raw_value)
                # Panasonic ExposureCompensation may need offset adjustment
                if result > 100:
                    result = result - 128
                if result == 0:
                    return "0"
                elif result > 0:
                    return f"+{result:.2f}".rstrip('0').rstrip('.')
                else:
                    return f"{result:.2f}".rstrip('0').rstrip('.')
        
        # Special handling for ShutterSpeed tag (0x000B or other possible IDs) - format as fraction (1/X)
        if tag_id == 0x000B:  # ShutterSpeed (possible tag ID)
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                # ShutterSpeed is typically stored as RATIONAL - convert to fraction format
                ss_val = raw_value[0]
                if isinstance(ss_val, (list, tuple)) and len(ss_val) == 2:
                    num, den = ss_val
                    if den != 0:
                        exp_time = num / den
                        # Format as fraction (1/X) for values < 1 second, matching standard format
                        if 0 < exp_time < 1:
                            # Find closest 1/X fraction representation
                            closest_den = round(1.0 / exp_time)
                            if abs(exp_time - (1.0 / closest_den)) < 0.01:  # Tolerance check
                                return f"1/{closest_den}"
                            else:
                                return f"{exp_time:.3f}"
                        elif exp_time >= 1:
                            # For values >= 1 second, format as integer or decimal
                            if exp_time == int(exp_time):
                                return f"{int(exp_time)}"
                            else:
                                return f"{exp_time:.3f}"
                elif isinstance(ss_val, (int, float)):
                    exp_time = float(ss_val)
                    if 0 < exp_time < 1:
                        closest_den = round(1.0 / exp_time)
                        if abs(exp_time - (1.0 / closest_den)) < 0.01:
                            return f"1/{closest_den}"
                        else:
                            return f"{exp_time:.3f}"
                    elif exp_time >= 1:
                        if exp_time == int(exp_time):
                            return f"{int(exp_time)}"
                        else:
                            return f"{exp_time:.3f}"
            elif isinstance(raw_value, (int, float)):
                exp_time = float(raw_value)
                if 0 < exp_time < 1:
                    closest_den = round(1.0 / exp_time)
                    if abs(exp_time - (1.0 / closest_den)) < 0.01:
                        return f"1/{closest_den}"
                    else:
                        return f"{exp_time:.3f}"
                elif exp_time >= 1:
                    if exp_time == int(exp_time):
                        return f"{int(exp_time)}"
                    else:
                        return f"{exp_time:.3f}"
        
        # Special handling for ISO/ProgramISO tags (0x0010, 0x0039, 0x00E5) - format as integer
        if tag_id in (0x0010, 0x0039, 0x00E5):  # ProgramISO variants
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                iso_val = raw_value[0]
                if isinstance(iso_val, (int, float)):
                    return str(int(iso_val))
            elif isinstance(raw_value, (int, float)):
                return str(int(raw_value))
        
        # Apply enum/flag mappings
        return self._apply_enum_flags('PANASONIC', tag_id, raw_value, parent_tag_name)
    
    def decode_kodak_value(
        self,
        tag_id: int,
        tag_type: int,
        tag_count: int,
        data: bytes,
        offset: int,
        parent_tag_name: Optional[str] = None
    ) -> Any:
        """
        Decode Kodak MakerNote tag value with improved formatting.
        
        Args:
            tag_id: Tag ID
            tag_type: Tag data type
            tag_count: Number of values
            data: Raw data bytes
            offset: Offset to tag data
            parent_tag_name: Parent tag name for sub-IFD context (unused for Kodak)
            
        Returns:
            Decoded value (with improved formatting to standard format)
        """
        # Special handling for KodakVersion tag (0x0000) - format as version string
        if tag_id == 0x0000:  # KodakVersion
            raw_value = self._decode_raw_value(tag_type, tag_count, data, offset)
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 2:
                # Version is typically stored as SHORT array - format as "X.Y" (matching standard format)
                major = raw_value[0] if len(raw_value) > 0 else 0
                minor = raw_value[1] if len(raw_value) > 1 else 0
                return f"{major}.{minor}"
            elif isinstance(raw_value, (int, float)):
                # Single value - format as version
                major = (int(raw_value) >> 8) & 0xFF
                minor = int(raw_value) & 0xFF
                return f"{major}.{minor}"
            elif isinstance(raw_value, bytes):
                # Try to decode as ASCII string
                try:
                    version_str = raw_value.decode('utf-8', errors='ignore').strip('\x00')
                    return version_str
                except:
                    pass
        
        # Special handling for OriginalFileName tag (0x0001) - decode as ASCII string
        if tag_id == 0x0001:  # OriginalFileName
            raw_value = self._decode_raw_value(tag_type, tag_count, data, offset)
            if isinstance(raw_value, bytes):
                try:
                    filename = raw_value.decode('utf-8', errors='ignore').strip('\x00')
                    return filename
                except:
                    pass
            elif isinstance(raw_value, str):
                return raw_value.strip('\x00')
        
        # Special handling for ApplicationKeyString tag (0x0038) - decode as ASCII string
        if tag_id == 0x0038:  # ApplicationKeyString
            raw_value = self._decode_raw_value(tag_type, tag_count, data, offset)
            if isinstance(raw_value, bytes):
                try:
                    key_str = raw_value.decode('utf-8', errors='ignore').strip('\x00')
                    return key_str
                except:
                    pass
            elif isinstance(raw_value, str):
                return raw_value.strip('\x00')
        
        # Decode raw value first
        raw_value = self._decode_raw_value(tag_type, tag_count, data, offset)
        
        # Special handling for ShutterSpeed tag (0x000B) - format as fraction (1/X)
        if tag_id == 0x000B:  # ShutterSpeed
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                ss_val = raw_value[0]
                if isinstance(ss_val, (list, tuple)) and len(ss_val) == 2:
                    # RATIONAL format: numerator/denominator
                    num, den = ss_val
                    if den != 0:
                        exp_time = num / den
                        # Format as fraction (1/X) for values < 1 second
                        if 0 < exp_time < 1:
                            closest_den = round(1.0 / exp_time)
                            if abs(exp_time - (1.0 / closest_den)) < 0.01:
                                return f"1/{closest_den}"
                            return f"{exp_time:.3f}"
                        elif exp_time >= 1:
                            if exp_time == int(exp_time):
                                return f"{int(exp_time)}"
                            return f"{exp_time:.3f}"
                elif isinstance(ss_val, (int, float)):
                    exp_time = float(ss_val)
                    if 0 < exp_time < 1:
                        closest_den = round(1.0 / exp_time)
                        if abs(exp_time - (1.0 / closest_den)) < 0.01:
                            return f"1/{closest_den}"
                        return f"{exp_time:.3f}"
                    elif exp_time >= 1:
                        if exp_time == int(exp_time):
                            return f"{int(exp_time)}"
                        return f"{exp_time:.3f}"
            elif isinstance(raw_value, (int, float)):
                exp_time = float(raw_value)
                if 0 < exp_time < 1:
                    closest_den = round(1.0 / exp_time)
                    if abs(exp_time - (1.0 / closest_den)) < 0.01:
                        return f"1/{closest_den}"
                    return f"{exp_time:.3f}"
                elif exp_time >= 1:
                    if exp_time == int(exp_time):
                        return f"{int(exp_time)}"
                    return f"{exp_time:.3f}"
        
        # Special handling for Aperture tag (0x000A) - format as decimal
        if tag_id == 0x000A:  # Aperture
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                aperture_val = raw_value[0]
                if isinstance(aperture_val, (list, tuple)) and len(aperture_val) == 2:
                    # RATIONAL format
                    num, den = aperture_val
                    if den != 0:
                        return f"{num / den:.1f}"
                elif isinstance(aperture_val, (int, float)):
                    return f"{aperture_val:.1f}"
            elif isinstance(raw_value, (int, float)):
                return f"{raw_value:.1f}"
        
        # Special handling for ExposureCompensation tag (0x000E) - format as decimal with sign
        if tag_id == 0x000E:  # ExposureCompensation
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                ec_val = raw_value[0]
                if isinstance(ec_val, (list, tuple)) and len(ec_val) == 2:
                    num, den = ec_val
                    if den != 0:
                        result = num / den
                        if result == 0:
                            return "0"
                        elif result > 0:
                            return f"+{result:.2f}".rstrip('0').rstrip('.')
                        else:
                            return f"{result:.2f}".rstrip('0').rstrip('.')
                elif isinstance(ec_val, (int, float)):
                    result = float(ec_val)
                    if result == 0:
                        return "0"
                    elif result > 0:
                        return f"+{result:.2f}".rstrip('0').rstrip('.')
                    else:
                        return f"{result:.2f}".rstrip('0').rstrip('.')
            elif isinstance(raw_value, (int, float)):
                result = float(raw_value)
                if result == 0:
                    return "0"
                elif result > 0:
                    return f"+{result:.2f}".rstrip('0').rstrip('.')
                else:
                    return f"{result:.2f}".rstrip('0').rstrip('.')
        
        # Special handling for ISO-related tags (0x0024, 0x0025, 0x0046, 0x012F) - format as integer
        # IMPROVEMENT (Build 1282): Added support for ISO tag IDs 0x0046 and 0x012F in addition to BaseISO (0x0024) and AnalogCaptureISO (0x0025)
        if tag_id in (0x0024, 0x0025, 0x0046, 0x012F):  # BaseISO, AnalogCaptureISO, ISO (two variants)
            if isinstance(raw_value, (list, tuple)) and len(raw_value) >= 1:
                iso_val = raw_value[0]
                if isinstance(iso_val, (int, float)):
                    return str(int(iso_val))
            elif isinstance(raw_value, (int, float)):
                return str(int(raw_value))
        
        # Special handling for WB_RGBLevels tag (0x001C) - format as space-separated values
        if tag_id == 0x001C:  # WB_RGBLevels
            if isinstance(raw_value, (list, tuple)):
                # Format as space-separated RGB values
                if len(raw_value) >= 3:
                    return ' '.join(str(v) for v in raw_value[:3])
                elif len(raw_value) > 0:
                    return ' '.join(str(v) for v in raw_value)
        
        # IMPROVEMENT (Build 1210): Enhanced UNDEFINED type handling - many Kodak tags use UNDEFINED (type 7)
        # which may contain ASCII strings, binary data, or numeric arrays
        # Try to decode UNDEFINED types as ASCII strings first, then as numeric arrays
        if tag_type == 7:  # UNDEFINED type
            # Strategy 1: Try decoding as ASCII string (common for Kodak string tags)
            if isinstance(raw_value, bytes):
                try:
                    # Check if bytes contain mostly printable ASCII characters
                    printable_count = sum(1 for b in raw_value[:100] if 32 <= b <= 126 or b in (9, 10, 13))
                    if printable_count > len(raw_value[:100]) * 0.8:  # 80% printable
                        decoded_str = raw_value.decode('utf-8', errors='ignore').strip('\x00').strip()
                        if len(decoded_str) > 0:
                            return decoded_str
                except:
                    pass
            
            # Strategy 2: If raw_value is bytes and looks like it might be a string, try decoding
            if isinstance(raw_value, bytes) and tag_count > 0:
                # For small UNDEFINED values, try decoding as ASCII
                if tag_count <= 1000:  # Reasonable string length
                    try:
                        # Remove null bytes and decode
                        cleaned = raw_value.rstrip(b'\x00')
                        if len(cleaned) > 0:
                            decoded_str = cleaned.decode('utf-8', errors='ignore').strip()
                            # If decoded string has reasonable length and contains mostly printable chars
                            if len(decoded_str) > 0 and len(decoded_str) <= tag_count:
                                printable_ratio = sum(1 for c in decoded_str if c.isprintable() or c.isspace()) / len(decoded_str) if len(decoded_str) > 0 else 0
                                if printable_ratio > 0.7:  # 70% printable
                                    return decoded_str
                    except:
                        pass
        
        # IMPROVEMENT (Build 1207): Enhanced array formatting for all array-type Kodak tags
        # Many Kodak tags are arrays that should be formatted as space-separated values
        # This standard format's output format for array tags
        if isinstance(raw_value, (list, tuple)) and len(raw_value) > 0:
            # For numeric arrays, format as space-separated values
            # Check if all elements are numeric (int, float, or RATIONAL tuples)
            all_numeric = True
            formatted_values = []
            
            for item in raw_value:
                if isinstance(item, (int, float)):
                    formatted_values.append(str(item))
                elif isinstance(item, (list, tuple)) and len(item) == 2:
                    # RATIONAL format (numerator, denominator)
                    num, den = item
                    if den != 0:
                        result = num / den
                        # Format as integer if whole number, otherwise as decimal
                        if result == int(result):
                            formatted_values.append(str(int(result)))
                        else:
                            formatted_values.append(f"{result:.4f}".rstrip('0').rstrip('.'))
                    else:
                        formatted_values.append(str(item))
                else:
                    all_numeric = False
                    break
            
            # If all values are numeric, return space-separated string
            if all_numeric and len(formatted_values) > 0:
                return ' '.join(formatted_values)
        
        # IMPROVEMENT (Build 1210): Enhanced bytes handling - try to decode bytes as ASCII strings
        # Some Kodak tags may return bytes that should be decoded as strings
        if isinstance(raw_value, bytes) and tag_type != 7:  # Not already handled for UNDEFINED
            # For ASCII type (2) or if tag_count suggests string data
            if tag_type == 2 or (tag_count > 0 and tag_count < 1000):
                try:
                    decoded_str = raw_value.decode('utf-8', errors='ignore').strip('\x00').strip()
                    if len(decoded_str) > 0:
                        # Check if it looks like a valid string (mostly printable)
                        printable_ratio = sum(1 for c in decoded_str if c.isprintable() or c.isspace()) / len(decoded_str) if len(decoded_str) > 0 else 0
                        if printable_ratio > 0.7:  # 70% printable
                            return decoded_str
                except:
                    pass
        
        # Apply enum/flag mappings (if any exist for Kodak)
        return self._apply_enum_flags('KODAK', tag_id, raw_value, parent_tag_name)
    
    def decode_value(
        self,
        manufacturer: str,
        tag_id: int,
        tag_type: int,
        tag_count: int,
        data: bytes,
        offset: int
    ) -> Any:
        """
        Decode MakerNote tag value for any manufacturer.
        
        Args:
            manufacturer: Camera manufacturer name
            tag_id: Tag ID
            tag_type: Tag data type
            tag_count: Number of values
            data: Raw data bytes
            offset: Offset to tag data
            
        Returns:
            Decoded value
        """
        manufacturer_upper = manufacturer.upper()
        
        if manufacturer_upper == 'CANON':
            return self.decode_canon_value(tag_id, tag_type, tag_count, data, offset)
        elif manufacturer_upper == 'NIKON':
            return self.decode_nikon_value(tag_id, tag_type, tag_count, data, offset)
        elif manufacturer_upper == 'SONY':
            return self.decode_sony_value(tag_id, tag_type, tag_count, data, offset)
        elif manufacturer_upper == 'OLYMPUS':
            return self.decode_olympus_value(tag_id, tag_type, tag_count, data, offset)
        elif manufacturer_upper in ('PENTAX', 'RICOH'):
            return self.decode_pentax_value(tag_id, tag_type, tag_count, data, offset)
        elif manufacturer_upper in ('FUJIFILM', 'FUJI'):
            return self.decode_fujifilm_value(tag_id, tag_type, tag_count, data, offset)
        elif manufacturer_upper in ('PANASONIC', 'LUMIX'):
            return self.decode_panasonic_value(tag_id, tag_type, tag_count, data, offset)
        elif manufacturer_upper in ('KODAK', 'EASTMAN KODAK', 'EASTMAN KODAK COMPANY'):
            return self.decode_kodak_value(tag_id, tag_type, tag_count, data, offset)
        else:
            # Generic decoder for unknown manufacturers
            return self.decode_canon_value(tag_id, tag_type, tag_count, data, offset)

