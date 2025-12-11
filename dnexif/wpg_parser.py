# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
WPG (WordPerfect Graphics) file metadata parser

This module handles reading metadata from WPG graphics files.
WPG files are used by WordPerfect and contain vector and raster graphics.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class WGPParser:
    """
    Parser for WPG (WordPerfect Graphics) metadata.
    
    WPG files have the following structure:
    - File header with signature and version
    - Drawing records containing graphics data
    - Image dimensions and color information
    """
    
    # WPG signature
    WPG_SIGNATURE_V1 = b'\xFFWPG'  # Version 1
    WPG_SIGNATURE_V2 = b'\xFFWPG2'  # Version 2
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize WPG parser.
        
        Args:
            file_path: Path to WPG file
            file_data: WPG file data bytes
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
        Parse WPG metadata.
        
        Returns:
            Dictionary of WPG metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 8:
                raise MetadataReadError("Invalid WPG file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'WPG'
            metadata['File:FileTypeExtension'] = 'wpg'
            metadata['File:MIMEType'] = 'image/x-wpg'
            
            # Check for WPG signature
            if file_data.startswith(self.WPG_SIGNATURE_V2):
                metadata['WPG:Version'] = 2
                metadata['WPG:Format'] = 'WPG2'
                offset = 6  # Skip signature (0xFF + 'WPG2')
            elif file_data.startswith(self.WPG_SIGNATURE_V1):
                metadata['WPG:Version'] = 1
                metadata['WPG:Format'] = 'WPG1'
                offset = 4  # Skip signature (0xFF + 'WPG')
            else:
                # Try to detect WPG by checking for common patterns
                # Some WPG files may have different headers
                if len(file_data) >= 16:
                    # Check for potential WPG header structure
                    # WPG files often start with 0xFF followed by 'WPG'
                    if file_data[0] == 0xFF and file_data[1:4] == b'WPG':
                        metadata['WPG:Version'] = 1
                        metadata['WPG:Format'] = 'WPG1'
                        offset = 4
                    else:
                        # Assume it's a WPG file based on extension
                        metadata['WPG:Version'] = 1
                        metadata['WPG:Format'] = 'WPG1'
                        offset = 0
                else:
                    raise MetadataReadError("Invalid WPG file: missing signature")
            
            # Parse WPG header
            # WPG header structure varies by version
            # Common fields:
            # - Version information
            # - Image dimensions (width, height)
            # - Color depth
            # - Drawing records
            
            # Try to extract image dimensions from header
            # WPG files store dimensions in various locations depending on version
            if len(file_data) >= offset + 16:
                # Try to read dimensions (often stored as 16-bit values)
                # Dimensions may be at different offsets depending on WPG version
                try:
                    # Attempt to read width and height (little-endian, 16-bit)
                    width = struct.unpack('<H', file_data[offset:offset+2])[0]
                    height = struct.unpack('<H', file_data[offset+2:offset+4])[0]
                    
                    # Validate dimensions (reasonable values)
                    if 0 < width < 65535 and 0 < height < 65535:
                        metadata['WPG:Width'] = width
                        metadata['WPG:Height'] = height
                        metadata['Image:ImageWidth'] = width
                        metadata['Image:ImageHeight'] = height
                except Exception:
                    pass
                
                # Try big-endian
                try:
                    width = struct.unpack('>H', file_data[offset:offset+2])[0]
                    height = struct.unpack('>H', file_data[offset+2:offset+4])[0]
                    
                    if 0 < width < 65535 and 0 < height < 65535:
                        if 'WPG:Width' not in metadata:
                            metadata['WPG:Width'] = width
                            metadata['WPG:Height'] = height
                            metadata['Image:ImageWidth'] = width
                            metadata['Image:ImageHeight'] = height
                except Exception:
                    pass
            
            # Try to find dimensions in drawing records
            # WPG files contain drawing records with various opcodes
            # Look for common drawing record patterns
            if 'WPG:Width' not in metadata:
                # Search for dimension patterns in the file
                # WPG drawing records may contain dimension information
                for i in range(min(1024, len(file_data) - 8)):
                    try:
                        # Try to find dimension values (common patterns)
                        val1 = struct.unpack('<H', file_data[i:i+2])[0]
                        val2 = struct.unpack('<H', file_data[i+2:i+4])[0]
                        
                        # Check if values look like dimensions (reasonable aspect ratios)
                        if 10 < val1 < 10000 and 10 < val2 < 10000:
                            # Check if ratio is reasonable (between 0.1 and 10)
                            ratio = val1 / val2 if val2 > 0 else 0
                            if 0.1 < ratio < 10:
                                metadata['WPG:Width'] = val1
                                metadata['WPG:Height'] = val2
                                metadata['Image:ImageWidth'] = val1
                                metadata['Image:ImageHeight'] = val2
                                break
                    except Exception:
                        continue
            
            # Extract color depth information if available
            # WPG files may store color depth in various locations
            if len(file_data) >= offset + 8:
                try:
                    # Try to read color depth (often stored as 8-bit or 16-bit value)
                    color_depth = file_data[offset + 6] if offset + 6 < len(file_data) else 0
                    if color_depth in (1, 2, 4, 8, 16, 24, 32):
                        metadata['WPG:ColorDepth'] = color_depth
                        metadata['Image:BitsPerSample'] = color_depth
                except Exception:
                    pass
            
            # Count drawing records (approximate)
            # WPG files contain drawing records with opcodes
            # Look for common record patterns
            record_count = 0
            for i in range(min(2048, len(file_data) - 2)):
                # WPG records often start with specific byte patterns
                if file_data[i] == 0xFF and i + 1 < len(file_data):
                    # Potential record start
                    record_count += 1
            
            if record_count > 0:
                metadata['WPG:EstimatedRecordCount'] = record_count
            
            # File size
            if self.file_path:
                try:
                    file_size = self.file_path.stat().st_size
                    metadata['File:FileSize'] = file_size
                except Exception:
                    pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse WPG metadata: {str(e)}")

