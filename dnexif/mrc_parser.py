# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
MRC (Medical Research Council) image metadata parser

This module handles reading metadata from MRC files.
MRC files are used for electron microscopy data.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class MRCParser:
    """
    Parser for MRC (Medical Research Council) metadata.
    
    MRC files have a 1024-byte header containing:
    - Image dimensions (nx, ny, nz)
    - Data mode (0=byte, 1=short, 2=float, 3=complex short, 4=complex float)
    - Cell dimensions
    - Various other metadata fields
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize MRC parser.
        
        Args:
            file_path: Path to MRC file
            file_data: MRC file data bytes
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
        Parse MRC metadata.
        
        Returns:
            Dictionary of MRC metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read(1024)  # MRC header is 1024 bytes
            else:
                file_data = self.file_data[:1024] if len(self.file_data) >= 1024 else self.file_data
            
            if len(file_data) < 56:
                raise MetadataReadError("Invalid MRC file: header too short")
            
            metadata = {}
            metadata['File:FileType'] = 'MRC'
            metadata['File:FileTypeExtension'] = 'mrc'
            metadata['File:MIMEType'] = 'image/x-mrc'
            
            # Parse MRC header (little-endian integers)
            # Offset 0-3: nx (columns)
            nx = struct.unpack('<i', file_data[0:4])[0]
            # Offset 4-7: ny (rows)
            ny = struct.unpack('<i', file_data[4:8])[0]
            # Offset 8-11: nz (sections)
            nz = struct.unpack('<i', file_data[8:12])[0]
            
            metadata['MRC:NX'] = nx
            metadata['MRC:NY'] = ny
            metadata['MRC:NZ'] = nz
            
            # Image dimensions (for 2D images, nz=1)
            if nz == 1:
                metadata['File:ImageWidth'] = nx
                metadata['File:ImageHeight'] = ny
            else:
                # 3D volume
                metadata['File:ImageWidth'] = nx
                metadata['File:ImageHeight'] = ny
                metadata['MRC:ImageDepth'] = nz
            
            # Offset 12-15: mode (data type)
            mode = struct.unpack('<i', file_data[12:16])[0]
            mode_map = {
                0: 'Byte (8-bit)',
                1: 'Short (16-bit)',
                2: 'Float (32-bit)',
                3: 'Complex Short (16-bit)',
                4: 'Complex Float (32-bit)',
                6: 'Unsigned Short (16-bit)',
            }
            metadata['MRC:Mode'] = mode
            metadata['MRC:DataType'] = mode_map.get(mode, f'Unknown ({mode})')
            
            # Bits per pixel based on mode
            bits_map = {
                0: 8,
                1: 16,
                2: 32,
                3: 32,  # Complex short = 2 * 16-bit
                4: 64,  # Complex float = 2 * 32-bit
                6: 16,
            }
            bits_per_pixel = bits_map.get(mode, 8)
            metadata['MRC:BitsPerPixel'] = bits_per_pixel
            metadata['File:BitsPerPixel'] = bits_per_pixel
            
            # Offset 16-19: nxstart
            nxstart = struct.unpack('<i', file_data[16:20])[0]
            # Offset 20-23: nystart
            nystart = struct.unpack('<i', file_data[20:24])[0]
            # Offset 24-27: nzstart
            nzstart = struct.unpack('<i', file_data[24:28])[0]
            
            metadata['MRC:NXStart'] = nxstart
            metadata['MRC:NYStart'] = nystart
            metadata['MRC:NZStart'] = nzstart
            
            # Offset 28-31: mx (cell dimensions)
            mx = struct.unpack('<i', file_data[28:32])[0]
            # Offset 32-35: my
            my = struct.unpack('<i', file_data[32:36])[0]
            # Offset 36-39: mz
            mz = struct.unpack('<i', file_data[36:40])[0]
            
            metadata['MRC:MX'] = mx
            metadata['MRC:MY'] = my
            metadata['MRC:MZ'] = mz
            
            # Offset 40-43: cella (cell dimension in x, Angstroms)
            cella_x = struct.unpack('<f', file_data[40:44])[0]
            # Offset 44-47: cella_y
            cella_y = struct.unpack('<f', file_data[44:48])[0]
            # Offset 48-51: cella_z
            cella_z = struct.unpack('<f', file_data[48:52])[0]
            
            metadata['MRC:CellA:X'] = cella_x
            metadata['MRC:CellA:Y'] = cella_y
            metadata['MRC:CellA:Z'] = cella_z
            
            # Offset 52-55: cellb (cell angles, degrees)
            cellb_alpha = struct.unpack('<f', file_data[52:56])[0]
            # Offset 56-59: cellb_beta
            if len(file_data) >= 60:
                cellb_beta = struct.unpack('<f', file_data[56:60])[0]
                # Offset 60-63: cellb_gamma
                if len(file_data) >= 64:
                    cellb_gamma = struct.unpack('<f', file_data[60:64])[0]
                    
                    metadata['MRC:CellB:Alpha'] = cellb_alpha
                    metadata['MRC:CellB:Beta'] = cellb_beta
                    metadata['MRC:CellB:Gamma'] = cellb_gamma
            
            # Extract file size
            if self.file_path:
                import os
                file_size = os.path.getsize(self.file_path)
                metadata['File:FileSize'] = file_size
                metadata['File:FileSizeBytes'] = file_size
                
                # Calculate expected data size
                header_size = 1024
                pixel_size = bits_per_pixel // 8
                if mode == 3:  # Complex short
                    pixel_size = 4
                elif mode == 4:  # Complex float
                    pixel_size = 8
                expected_data_size = nx * ny * nz * pixel_size
                metadata['MRC:ExpectedDataSize'] = expected_data_size
                metadata['MRC:HeaderSize'] = header_size
            else:
                metadata['File:FileSize'] = len(file_data)
                metadata['File:FileSizeBytes'] = len(file_data)
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse MRC metadata: {str(e)}")

