# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
DDS (DirectDraw Surface) image metadata parser

This module handles reading metadata from DDS files.
DDS files are used for storing compressed textures, commonly used in games.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class DDSParser:
    """
    Parser for DDS (DirectDraw Surface) metadata.
    
    DDS files have a DDS header structure:
    - Magic number: "DDS " (4 bytes)
    - DDS_HEADER structure (124 bytes)
    - Pixel data
    """
    
    # DDS magic number
    DDS_MAGIC = b'DDS '
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize DDS parser.
        
        Args:
            file_path: Path to DDS file
            file_data: DDS file data bytes
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
        Parse DDS metadata.
        
        Returns:
            Dictionary of DDS metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 128:
                raise MetadataReadError("Invalid DDS file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'DDS'
            metadata['File:FileTypeExtension'] = 'dds'
            metadata['File:MIMEType'] = 'image/vnd.ms-dds'
            
            # Check magic number
            if file_data[:4] != self.DDS_MAGIC:
                raise MetadataReadError("Invalid DDS file: missing DDS magic number")
            
            metadata['DDS:HasSignature'] = True
            metadata['DDS:Signature'] = 'DDS '
            
            # Parse DDS header (starts at offset 4)
            # DDS_HEADER structure (124 bytes)
            header = file_data[4:128]
            
            # dwSize (4 bytes) - should be 124
            dw_size = struct.unpack('<I', header[0:4])[0]
            metadata['DDS:HeaderSize'] = dw_size
            
            # dwFlags (4 bytes)
            dw_flags = struct.unpack('<I', header[4:8])[0]
            metadata['DDS:Flags'] = dw_flags
            
            # dwHeight (4 bytes)
            height = struct.unpack('<I', header[8:12])[0]
            metadata['DDS:Height'] = height
            metadata['File:ImageHeight'] = height
            
            # dwWidth (4 bytes)
            width = struct.unpack('<I', header[12:16])[0]
            metadata['DDS:Width'] = width
            metadata['File:ImageWidth'] = width
            
            # dwPitchOrLinearSize (4 bytes)
            pitch = struct.unpack('<I', header[16:20])[0]
            metadata['DDS:PitchOrLinearSize'] = pitch
            
            # dwDepth (4 bytes) - for volume textures
            depth = struct.unpack('<I', header[20:24])[0]
            if depth > 0:
                metadata['DDS:Depth'] = depth
            
            # dwMipMapCount (4 bytes)
            mipmap_count = struct.unpack('<I', header[24:28])[0]
            if mipmap_count > 0:
                metadata['DDS:MipMapCount'] = mipmap_count
            
            # Parse pixel format (DDPIXELFORMAT structure, 32 bytes)
            # dwSize (4 bytes) - should be 32
            pf_size = struct.unpack('<I', header[72:76])[0]
            metadata['DDS:PixelFormatSize'] = pf_size
            
            # dwFlags (4 bytes)
            pf_flags = struct.unpack('<I', header[76:80])[0]
            metadata['DDS:PixelFormatFlags'] = pf_flags
            
            # dwFourCC (4 bytes) - compression format
            fourcc = header[80:84]
            if fourcc != b'\x00\x00\x00\x00':
                fourcc_str = fourcc.decode('ascii', errors='ignore').strip('\x00')
                metadata['DDS:FourCC'] = fourcc_str
                metadata['DDS:CompressionFormat'] = fourcc_str
            
            # dwRGBBitCount (4 bytes)
            rgb_bit_count = struct.unpack('<I', header[84:88])[0]
            if rgb_bit_count > 0:
                metadata['DDS:RGBBitCount'] = rgb_bit_count
                metadata['File:BitsPerPixel'] = rgb_bit_count
            
            # dwRBitMask, dwGBitMask, dwBBitMask, dwABitMask (4 bytes each)
            r_mask = struct.unpack('<I', header[88:92])[0]
            g_mask = struct.unpack('<I', header[92:96])[0]
            b_mask = struct.unpack('<I', header[96:100])[0]
            a_mask = struct.unpack('<I', header[100:104])[0]
            
            if r_mask > 0:
                metadata['DDS:RBitMask'] = hex(r_mask)
            if g_mask > 0:
                metadata['DDS:GBitMask'] = hex(g_mask)
            if b_mask > 0:
                metadata['DDS:BBitMask'] = hex(b_mask)
            if a_mask > 0:
                metadata['DDS:ABitMask'] = hex(a_mask)
            
            # dwCaps, dwCaps2, dwCaps3, dwCaps4 (4 bytes each)
            caps = struct.unpack('<I', header[104:108])[0]
            caps2 = struct.unpack('<I', header[108:112])[0]
            caps3 = struct.unpack('<I', header[112:116])[0]
            caps4 = struct.unpack('<I', header[116:120])[0]
            
            metadata['DDS:Caps'] = caps
            if caps2 > 0:
                metadata['DDS:Caps2'] = caps2
            if caps3 > 0:
                metadata['DDS:Caps3'] = caps3
            if caps4 > 0:
                metadata['DDS:Caps4'] = caps4
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse DDS metadata: {str(e)}")

