# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Parrot Bebop-Pro Thermal image metadata parser

This module handles reading metadata from Parrot Bebop-Pro Thermal images.
Parrot thermal images are JPEG files with embedded thermal camera metadata
and raw thermal image data.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class ParrotParser:
    """
    Parser for Parrot Bebop-Pro Thermal image metadata.
    
    Parrot thermal images are JPEG files with embedded Parrot thermal camera metadata
    and raw thermal image data typically stored in APP segments or EXIF data.
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize Parrot parser.
        
        Args:
            file_path: Path to Parrot thermal image file
            file_data: File data bytes
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
        Parse Parrot Bebop-Pro Thermal image metadata.
        
        Returns:
            Dictionary of Parrot metadata including raw thermal image data
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 2:
                raise MetadataReadError("Invalid Parrot thermal image: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'JPEG'
            metadata['File:FileTypeExtension'] = 'jpg'
            metadata['File:MIMEType'] = 'image/jpeg'
            metadata['Parrot:Format'] = 'Parrot Bebop-Pro Thermal'
            metadata['Parrot:HasParrotMetadata'] = True
            
            # Check if it's a JPEG file
            if not file_data.startswith(b'\xFF\xD8'):
                raise MetadataReadError("Invalid Parrot thermal image: not a JPEG file")
            
            # Detect Parrot thermal image by searching for Parrot-specific patterns
            is_parrot_thermal = False
            parrot_patterns = [
                b'Parrot',
                b'PARROT',
                b'Bebop',
                b'BEBOP',
                b'Bebop-Pro',
                b'thermal',
                b'Thermal',
                b'THERMAL',
            ]
            
            for pattern in parrot_patterns:
                if pattern in file_data[:50000]:  # Check first 50KB
                    is_parrot_thermal = True
                    metadata['Parrot:IsParrotThermal'] = True
                    break
            
            if not is_parrot_thermal:
                # Still try to parse, might be a Parrot image without obvious markers
                metadata['Parrot:IsParrotThermal'] = False
            
            # Parse JPEG segments to find Parrot metadata and raw thermal image data
            offset = 2  # Skip JPEG SOI marker
            thermal_data_found = False
            
            while offset < len(file_data) - 1:
                # Check for segment marker
                if file_data[offset] != 0xFF:
                    break
                
                marker = file_data[offset + 1]
                
                # End of Image
                if marker == 0xD9:
                    break
                
                # APP segments (0xE0-0xEF)
                if 0xE0 <= marker <= 0xEF:
                    if offset + 4 > len(file_data):
                        break
                    
                    # Read segment length
                    segment_length = struct.unpack('>H', file_data[offset + 2:offset + 4])[0]
                    
                    if offset + 2 + segment_length > len(file_data):
                        break
                    
                    # Extract segment data
                    segment_data = file_data[offset + 4:offset + 2 + segment_length]
                    
                    # Check for Parrot-specific markers
                    if len(segment_data) > 0:
                        # Look for Parrot identifiers
                        segment_str = segment_data[:200].decode('utf-8', errors='ignore').lower()
                        
                        if any(pattern.lower() in segment_str for pattern in ['parrot', 'bebop', 'thermal']):
                            metadata['Parrot:HasThermalMetadata'] = True
                            
                            # Try to extract thermal metadata
                            try:
                                # Look for temperature values
                                if b'temp' in segment_data.lower() or b'temperature' in segment_data.lower():
                                    metadata['Parrot:HasTemperatureData'] = True
                                
                                # Look for raw thermal image data
                                # Parrot thermal images may contain raw thermal data in APP segments
                                # Raw thermal data is typically binary data (not JPEG)
                                # Look for patterns that might indicate raw thermal data
                                if len(segment_data) > 1000:  # Raw thermal data is typically large
                                    # Check if this might be raw thermal image data
                                    # Raw thermal data is usually 16-bit or 8-bit grayscale
                                    # Look for patterns that suggest raw thermal data
                                    thermal_data_offset = offset + 4
                                    thermal_data_size = len(segment_data)
                                    
                                    # Store raw thermal image information
                                    metadata['Parrot:RawThermalImage:HasRawThermalImage'] = True
                                    metadata['Parrot:RawThermalImage:Offset'] = thermal_data_offset
                                    metadata['Parrot:RawThermalImage:Size'] = thermal_data_size
                                    metadata['Parrot:RawThermalImage:Length'] = f"{thermal_data_size} bytes"
                                    metadata['Parrot:RawThermalImage:Segment'] = f'APP{marker - 0xE0}'
                                    thermal_data_found = True
                                
                                # Store segment metadata
                                metadata['Parrot:MetadataSegment'] = f'APP{marker - 0xE0}'
                                metadata['Parrot:MetadataLength'] = len(segment_data)
                            
                            except Exception:
                                pass
                        
                        # Check for EXIF data (may contain Parrot metadata)
                        if segment_data.startswith(b'Exif\x00\x00'):
                            metadata['Parrot:HasEXIF'] = True
                            
                            # Look for Parrot-specific EXIF tags
                            exif_data = segment_data[6:]  # Skip "Exif\x00\x00"
                            
                            # Check for TIFF header
                            if exif_data[:2] in (b'II', b'MM'):
                                # Try to find Parrot-specific IFD entries
                                if b'Parrot' in exif_data or b'PARROT' in exif_data or b'Bebop' in exif_data:
                                    metadata['Parrot:HasMakerNote'] = True
                    
                    offset += 2 + segment_length
                    continue
                
                # Skip other segments
                if offset + 4 > len(file_data):
                    break
                
                try:
                    segment_length = struct.unpack('>H', file_data[offset + 2:offset + 4])[0]
                    offset += 2 + segment_length
                except Exception:
                    offset += 1
            
            # Search for raw thermal image data in the file
            # Parrot thermal images may contain raw thermal data as separate binary blocks
            # Raw thermal data is typically 16-bit grayscale (temperature values)
            # Look for large binary blocks that might be raw thermal data
            
            if not thermal_data_found:
                # Search for potential raw thermal image data blocks
                # Raw thermal data blocks are typically:
                # - Large binary blocks (not JPEG compressed)
                # - Located after JPEG image data
                # - May have specific size patterns (e.g., 160x120 = 19200 pixels * 2 bytes = 38400 bytes)
                
                # Find JPEG end marker
                jpeg_end = file_data.rfind(b'\xFF\xD9')
                if jpeg_end > 0:
                    # Check if there's data after JPEG end (potential raw thermal data)
                    remaining_data = file_data[jpeg_end + 2:]
                    
                    if len(remaining_data) > 1000:  # Significant amount of data after JPEG
                        # This might be raw thermal image data
                        thermal_data_offset = jpeg_end + 2
                        thermal_data_size = len(remaining_data)
                        
                        # Check if size matches common thermal image resolutions
                        # Common resolutions: 160x120 (38400 bytes for 16-bit), 320x240 (153600 bytes), etc.
                        common_sizes = [
                            160 * 120 * 2,  # 16-bit grayscale
                            320 * 240 * 2,
                            640 * 480 * 2,
                            160 * 120,      # 8-bit grayscale
                            320 * 240,
                            640 * 480,
                        ]
                        
                        if thermal_data_size in common_sizes or (thermal_data_size > 10000 and thermal_data_size < 1000000):
                            metadata['Parrot:RawThermalImage:HasRawThermalImage'] = True
                            metadata['Parrot:RawThermalImage:Offset'] = thermal_data_offset
                            metadata['Parrot:RawThermalImage:Size'] = thermal_data_size
                            metadata['Parrot:RawThermalImage:Length'] = f"{thermal_data_size} bytes"
                            metadata['Parrot:RawThermalImage:Location'] = 'After JPEG data'
                            thermal_data_found = True
            
            # Search for thermal imaging parameters
            temp_range_patterns = [
                b'TempRange',
                b'TemperatureRange',
                b'TempMin',
                b'TempMax',
                b'RangeMin',
                b'RangeMax',
            ]
            
            for pattern in temp_range_patterns:
                if pattern in file_data:
                    metadata['Parrot:HasTemperatureRange'] = True
                    break
            
            # File size
            if self.file_path:
                try:
                    file_size = self.file_path.stat().st_size
                    metadata['File:FileSize'] = file_size
                except Exception:
                    pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse Parrot thermal image metadata: {str(e)}")

