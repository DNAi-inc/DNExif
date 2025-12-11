# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Leica LIF (Leica Image File) metadata parser

This module handles reading metadata from Leica LIF image files.
LIF files are used by Leica cameras and may be TIFF-based or proprietary format.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class LIFParser:
    """
    Parser for Leica LIF (Leica Image File) metadata.
    
    LIF files may be:
    - TIFF-based format (common for Leica cameras)
    - Proprietary Leica format
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize LIF parser.
        
        Args:
            file_path: Path to LIF file
            file_data: LIF file data bytes
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
        Parse LIF metadata.
        
        Returns:
            Dictionary of LIF metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 8:
                raise MetadataReadError("Invalid LIF file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'LIF'
            metadata['File:FileTypeExtension'] = 'lif'
            metadata['File:MIMEType'] = 'image/x-lif'
            metadata['Leica:Format'] = 'LIF'
            
            # Check if it's TIFF-based (common for Leica files)
            if file_data[:2] in (b'II', b'MM'):
                metadata['Leica:FormatType'] = 'TIFF-based'
                
                # Check for TIFF magic number
                if len(file_data) >= 4:
                    endian = '<' if file_data[:2] == b'II' else '>'
                    magic = struct.unpack(f'{endian}H', file_data[2:4])[0]
                    
                    if magic == 42:  # TIFF magic number
                        metadata['Leica:HasTIFFStructure'] = True
                        
                        # Try to read IFD0 offset
                        if len(file_data) >= 8:
                            ifd0_offset = struct.unpack(f'{endian}I', file_data[4:8])[0]
                            metadata['Leica:IFD0Offset'] = ifd0_offset
                            
                            # Try to read IFD entry count
                            if ifd0_offset < len(file_data) - 2:
                                ifd_entry_count = struct.unpack(f'{endian}H', file_data[ifd0_offset:ifd0_offset+2])[0]
                                metadata['Leica:IFD0EntryCount'] = ifd_entry_count
                        
                        # Look for Leica-specific markers
                        if b'Leica' in file_data[:1024] or b'LEICA' in file_data[:1024]:
                            metadata['Leica:HasLeicaMarker'] = True
                        
                        # Look for MakerNote (Leica cameras use MakerNote)
                        if b'MakerNote' in file_data[:2048] or b'MAKERNOTE' in file_data[:2048]:
                            metadata['Leica:HasMakerNote'] = True
            
            # Check for Leica-specific header patterns
            # Some Leica formats may have proprietary headers
            if file_data[:4] == b'LIF\x00' or file_data[:4] == b'LEIC':
                metadata['Leica:HasProprietaryHeader'] = True
                metadata['Leica:FormatType'] = 'Proprietary'
            
            # Search for Leica camera model identifiers
            leica_models = [
                b'M8', b'M9', b'M10', b'M11', b'M240', b'M262', b'M-P',
                b'SL', b'SL2', b'Q', b'Q2', b'Q3',
                b'X1', b'X2', b'X-U', b'X-Vario',
                b'D-Lux', b'V-Lux', b'C-Lux',
                b'S', b'S2', b'S3',
            ]
            
            for model in leica_models:
                if model in file_data[:4096]:
                    metadata['Leica:DetectedModel'] = model.decode('utf-8', errors='ignore')
                    break
            
            # Try to extract image dimensions
            # LIF files may store dimensions in various locations
            if len(file_data) >= 16:
                # Try common dimension storage patterns
                for offset in [8, 12, 16, 20, 24, 28]:
                    if offset + 8 <= len(file_data):
                        try:
                            # Try little-endian
                            width = struct.unpack('<I', file_data[offset:offset+4])[0]
                            height = struct.unpack('<I', file_data[offset+4:offset+8])[0]
                            
                            # Validate dimensions
                            if 10 < width < 65535 and 10 < height < 65535:
                                # Check if ratio is reasonable
                                ratio = width / height if height > 0 else 0
                                if 0.1 < ratio < 10:
                                    metadata['Leica:Width'] = width
                                    metadata['Leica:Height'] = height
                                    metadata['Image:ImageWidth'] = width
                                    metadata['Image:ImageHeight'] = height
                                    break
                        except Exception:
                            continue
                        
                        try:
                            # Try big-endian
                            width = struct.unpack('>I', file_data[offset:offset+4])[0]
                            height = struct.unpack('>I', file_data[offset+4:offset+8])[0]
                            
                            # Validate dimensions
                            if 10 < width < 65535 and 10 < height < 65535:
                                # Check if ratio is reasonable
                                ratio = width / height if height > 0 else 0
                                if 0.1 < ratio < 10:
                                    if 'Leica:Width' not in metadata:
                                        metadata['Leica:Width'] = width
                                        metadata['Leica:Height'] = height
                                        metadata['Image:ImageWidth'] = width
                                        metadata['Image:ImageHeight'] = height
                                        break
                        except Exception:
                            continue
            
            # File size
            if self.file_path:
                try:
                    file_size = self.file_path.stat().st_size
                    metadata['File:FileSize'] = file_size
                except Exception:
                    pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse LIF metadata: {str(e)}")

