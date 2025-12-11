# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
DJI RJPEG thermal image metadata parser

This module handles reading thermal information from DJI RJPEG images.
DJI RJPEG files are JPEG files with embedded DJI thermal camera metadata
and thermal imaging data.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class DJIRJPEGParser:
    """
    Parser for DJI RJPEG thermal image metadata.
    
    DJI RJPEG files are JPEG files with embedded DJI thermal camera metadata
    and thermal imaging data typically stored in APP segments or EXIF data.
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize DJI RJPEG parser.
        
        Args:
            file_path: Path to DJI RJPEG file
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
        Parse DJI RJPEG thermal image metadata.
        
        Returns:
            Dictionary of DJI RJPEG metadata including thermal information
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 2:
                raise MetadataReadError("Invalid DJI RJPEG file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'RJPEG'
            metadata['File:FileTypeExtension'] = 'rjpeg'
            metadata['File:MIMEType'] = 'image/jpeg'
            metadata['DJI:Format'] = 'DJI RJPEG'
            metadata['DJI:HasDJIMetadata'] = True
            
            # Check if it's a JPEG file
            if not file_data.startswith(b'\xFF\xD8'):
                raise MetadataReadError("Invalid DJI RJPEG file: not a JPEG file")
            
            # Detect DJI RJPEG by searching for DJI-specific patterns
            is_dji_rjpeg = False
            dji_patterns = [
                b'DJI',
                b'dji',
                b'DJI_',
                b'DJI-',
                b'DJI ',
                b'RJPEG',
                b'rjpeg',
                b'R-JPEG',
            ]
            
            for pattern in dji_patterns:
                if pattern in file_data[:50000]:  # Check first 50KB
                    is_dji_rjpeg = True
                    metadata['DJI:IsDJIRJPEG'] = True
                    break
            
            if not is_dji_rjpeg:
                # Still try to parse, might be a DJI RJPEG without obvious markers
                metadata['DJI:IsDJIRJPEG'] = False
            
            # Parse JPEG segments to find DJI thermal metadata
            offset = 2  # Skip JPEG SOI marker
            thermal_info_found = False
            
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
                    
                    # Check for DJI-specific markers
                    if len(segment_data) > 0:
                        # Look for DJI identifiers
                        segment_str = segment_data[:200].decode('utf-8', errors='ignore').lower()
                        
                        if any(pattern.lower() in segment_str for pattern in ['dji', 'rjpeg', 'thermal', 'temperature']):
                            metadata['DJI:HasThermalMetadata'] = True
                            thermal_info_found = True
                            
                            # Try to extract thermal information
                            try:
                                segment_lower = segment_data.lower()
                                
                                # Look for temperature values
                                if b'temp' in segment_lower or b'temperature' in segment_lower:
                                    metadata['DJI:HasTemperatureData'] = True
                                
                                # Look for thermal calibration data
                                if b'calibration' in segment_lower or b'calib' in segment_lower:
                                    metadata['DJI:HasCalibrationData'] = True
                                
                                # Look for emissivity
                                if b'emissivity' in segment_lower or b'emiss' in segment_lower:
                                    metadata['DJI:HasEmissivityData'] = True
                                
                                # Look for distance
                                if b'distance' in segment_lower or b'dist' in segment_lower:
                                    metadata['DJI:HasDistanceData'] = True
                                
                                # Look for humidity
                                if b'humidity' in segment_lower or b'humid' in segment_lower:
                                    metadata['DJI:HasHumidityData'] = True
                                
                                # Look for atmospheric temperature
                                if b'atmospheric' in segment_lower or b'atm' in segment_lower:
                                    metadata['DJI:HasAtmosphericData'] = True
                                
                                # Look for thermal range
                                if b'range' in segment_lower or b'min' in segment_lower or b'max' in segment_lower:
                                    metadata['DJI:HasTemperatureRange'] = True
                                
                                # Store segment metadata
                                metadata['DJI:ThermalMetadataSegment'] = f'APP{marker - 0xE0}'
                                metadata['DJI:ThermalMetadataLength'] = len(segment_data)
                            
                            except Exception:
                                pass
                        
                        # Check for EXIF data (may contain DJI thermal metadata)
                        if segment_data.startswith(b'Exif\x00\x00'):
                            metadata['DJI:HasEXIF'] = True
                            
                            # Look for DJI-specific EXIF tags
                            exif_data = segment_data[6:]  # Skip "Exif\x00\x00"
                            
                            # Check for TIFF header
                            if exif_data[:2] in (b'II', b'MM'):
                                # Try to find DJI-specific IFD entries
                                if b'DJI' in exif_data or b'dji' in exif_data or b'RJPEG' in exif_data:
                                    metadata['DJI:HasMakerNote'] = True
                                    
                                    # Look for thermal-related EXIF tags
                                    if b'thermal' in exif_data.lower() or b'temperature' in exif_data.lower():
                                        metadata['DJI:HasThermalEXIF'] = True
                    
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
            
            # Search for thermal imaging parameters in the file
            # DJI RJPEG files may contain thermal calibration data
            
            # Search for temperature range values
            temp_range_patterns = [
                b'TempRange',
                b'TemperatureRange',
                b'TempMin',
                b'TempMax',
                b'RangeMin',
                b'RangeMax',
                b'MinTemp',
                b'MaxTemp',
            ]
            
            for pattern in temp_range_patterns:
                if pattern in file_data:
                    metadata['DJI:HasTemperatureRange'] = True
                    thermal_info_found = True
                    break
            
            # Search for thermal image resolution
            resolution_patterns = [
                b'Resolution',
                b'ImageWidth',
                b'ImageHeight',
                b'Width',
                b'Height',
            ]
            
            for pattern in resolution_patterns:
                if pattern in file_data:
                    metadata['DJI:HasResolutionData'] = True
                    break
            
            # Search for palette/colormap information
            palette_patterns = [
                b'Palette',
                b'ColorMap',
                b'Colormap',
                b'LUT',
                b'LookupTable',
            ]
            
            for pattern in palette_patterns:
                if pattern in file_data:
                    metadata['DJI:HasPalette'] = True
                    break
            
            # If thermal information was found, mark it
            if thermal_info_found:
                metadata['DJI:HasThermalInformation'] = True
            
            # File size
            if self.file_path:
                try:
                    file_size = self.file_path.stat().st_size
                    metadata['File:FileSize'] = file_size
                except Exception:
                    pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse DJI RJPEG metadata: {str(e)}")

