# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
InfiRay IJPEG file metadata parser

This module handles reading metadata from InfiRay IJPEG thermal imaging files.
IJPEG files are JPEG files with embedded InfiRay thermal camera metadata.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class InfiRayParser:
    """
    Parser for InfiRay IJPEG thermal imaging metadata.
    
    IJPEG files are JPEG files with embedded InfiRay thermal camera metadata
    typically stored in APP segments or EXIF data.
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize InfiRay parser.
        
        Args:
            file_path: Path to IJPEG file
            file_data: IJPEG file data bytes
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
        Parse InfiRay IJPEG metadata.
        
        Returns:
            Dictionary of InfiRay metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 2:
                raise MetadataReadError("Invalid IJPEG file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'IJPEG'
            metadata['File:FileTypeExtension'] = 'ijpeg'
            metadata['File:MIMEType'] = 'image/jpeg'
            metadata['InfiRay:Format'] = 'IJPEG'
            metadata['InfiRay:HasInfiRayMetadata'] = True
            
            # Check if it's a JPEG file
            if not file_data.startswith(b'\xFF\xD8'):
                raise MetadataReadError("Invalid IJPEG file: not a JPEG file")
            
            # Parse JPEG segments to find InfiRay metadata
            offset = 2  # Skip JPEG SOI marker
            
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
                    
                    # Check for InfiRay-specific markers
                    # InfiRay metadata may be in APP segments with specific identifiers
                    if len(segment_data) > 0:
                        # Look for InfiRay identifiers
                        segment_str = segment_data[:100].decode('utf-8', errors='ignore').lower()
                        
                        if 'infiray' in segment_str or 'infrared' in segment_str or 'thermal' in segment_str:
                            metadata['InfiRay:HasThermalMetadata'] = True
                            
                            # Try to extract thermal metadata
                            # InfiRay metadata format may vary, try common patterns
                            try:
                                # Look for temperature values
                                if b'temp' in segment_data.lower() or b'temperature' in segment_data.lower():
                                    metadata['InfiRay:HasTemperatureData'] = True
                                
                                # Look for emissivity
                                if b'emissivity' in segment_data.lower() or b'emiss' in segment_data.lower():
                                    metadata['InfiRay:HasEmissivityData'] = True
                                
                                # Look for distance
                                if b'distance' in segment_data.lower() or b'dist' in segment_data.lower():
                                    metadata['InfiRay:HasDistanceData'] = True
                                
                                # Look for humidity
                                if b'humidity' in segment_data.lower() or b'humid' in segment_data.lower():
                                    metadata['InfiRay:HasHumidityData'] = True
                                
                                # Look for atmospheric temperature
                                if b'atmospheric' in segment_data.lower() or b'atm' in segment_data.lower():
                                    metadata['InfiRay:HasAtmosphericData'] = True
                                
                                # Store raw segment data for analysis
                                metadata['InfiRay:MetadataSegment'] = f'APP{marker - 0xE0}'
                                metadata['InfiRay:MetadataLength'] = len(segment_data)
                            
                            except Exception:
                                pass
                        
                        # Check for EXIF data (may contain InfiRay metadata)
                        if segment_data.startswith(b'Exif\x00\x00'):
                            metadata['InfiRay:HasEXIF'] = True
                            
                            # Look for InfiRay-specific EXIF tags
                            # InfiRay may use private EXIF tags for thermal data
                            exif_data = segment_data[6:]  # Skip "Exif\x00\x00"
                            
                            # Check for TIFF header
                            if exif_data[:2] in (b'II', b'MM'):
                                # Try to find InfiRay-specific IFD entries
                                # InfiRay may use MakerNote or private tags
                                if b'InfiRay' in exif_data or b'INFIRAY' in exif_data:
                                    metadata['InfiRay:HasMakerNote'] = True
                    
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
            
            # Try to extract thermal imaging parameters from file
            # InfiRay files may contain thermal calibration data
            # Look for common thermal imaging parameters in the file
            
            # Search for temperature range values
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
                    metadata['InfiRay:HasTemperatureRange'] = True
                    break
            
            # Search for palette/colormap information
            palette_patterns = [
                b'Palette',
                b'ColorMap',
                b'Colormap',
                b'LUT',
            ]
            
            for pattern in palette_patterns:
                if pattern in file_data:
                    metadata['InfiRay:HasPalette'] = True
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
            raise MetadataReadError(f"Failed to parse InfiRay IJPEG metadata: {str(e)}")

