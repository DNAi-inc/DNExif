# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Netpbm format metadata parser

This module handles reading metadata from Netpbm formats:
- PBM (Portable Bitmap)
- PGM (Portable Graymap)
- PPM (Portable Pixmap)
- PAM (Portable Arbitrary Map)

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class NetPBMParser:
    """
    Parser for Netpbm format metadata.
    
    Netpbm formats are ASCII or binary image formats:
    - PBM (P1/P4): Portable Bitmap (1-bit, black/white)
    - PGM (P2/P5): Portable Graymap (grayscale)
    - PPM (P3/P6): Portable Pixmap (RGB color)
    - PAM (P7): Portable Arbitrary Map (arbitrary channels)
    - PNM: Generic format (can be PBM, PGM, or PPM)
    """
    
    # Netpbm magic numbers
    PBM_ASCII = b'P1'
    PGM_ASCII = b'P2'
    PPM_ASCII = b'P3'
    PBM_BINARY = b'P4'
    PGM_BINARY = b'P5'
    PPM_BINARY = b'P6'
    PAM_FORMAT = b'P7'
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize Netpbm parser.
        
        Args:
            file_path: Path to Netpbm file
            file_data: Netpbm file data bytes
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
        Parse Netpbm metadata.
        
        Returns:
            Dictionary of Netpbm metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 2:
                raise MetadataReadError("Invalid Netpbm file: too short")
            
            metadata = {}
            file_ext = self.file_path.suffix.lower() if self.file_path else ''
            
            # Determine format from extension and magic number
            magic = file_data[:2]
            is_ascii = magic in (self.PBM_ASCII, self.PGM_ASCII, self.PPM_ASCII)
            is_binary = magic in (self.PBM_BINARY, self.PGM_BINARY, self.PPM_BINARY)
            is_pam = magic == self.PAM_FORMAT
            
            if is_pam:
                return self._parse_pam(file_data, metadata)
            elif is_ascii or is_binary:
                return self._parse_pbm_pgm_ppm(file_data, metadata, magic, is_ascii)
            else:
                # Try to determine from extension
                if file_ext == '.pam':
                    return self._parse_pam(file_data, metadata)
                elif file_ext in ('.pbm', '.pgm', '.ppm', '.pnm'):
                    # Default to PPM if unknown
                    return self._parse_pbm_pgm_ppm(file_data, metadata, self.PPM_BINARY, False)
                else:
                    raise MetadataReadError(f"Invalid Netpbm file: unknown magic number '{magic.decode('ascii', errors='ignore')}'")
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse Netpbm metadata: {str(e)}")
    
    def _parse_pam(self, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Parse PAM (Portable Arbitrary Map) format."""
        metadata['File:FileType'] = 'PAM'
        metadata['File:FileTypeExtension'] = 'pam'
        metadata['File:MIMEType'] = 'image/x-portable-arbitrarymap'
        
        # PAM format: P7\nWIDTH width\nHEIGHT height\nDEPTH depth\nMAXVAL maxval\nTUPLTYPE type\nENDHDR\n
        try:
            lines = file_data.split(b'\n')
            width = None
            height = None
            depth = None
            maxval = None
            tupltype = None
            
            for i, line in enumerate(lines):
                line_str = line.decode('ascii', errors='ignore').strip()
                if line_str.startswith('WIDTH'):
                    width = int(line_str.split()[1])
                elif line_str.startswith('HEIGHT'):
                    height = int(line_str.split()[1])
                elif line_str.startswith('DEPTH'):
                    depth = int(line_str.split()[1])
                elif line_str.startswith('MAXVAL'):
                    maxval = int(line_str.split()[1])
                elif line_str.startswith('TUPLTYPE'):
                    tupltype = ' '.join(line_str.split()[1:])
                elif line_str == 'ENDHDR':
                    break
            
            if width and height:
                metadata['PAM:Width'] = width
                metadata['PAM:Height'] = height
                metadata['File:ImageWidth'] = width
                metadata['File:ImageHeight'] = height
            if depth:
                metadata['PAM:Depth'] = depth
            if maxval:
                metadata['PAM:MaxVal'] = maxval
            if tupltype:
                metadata['PAM:TuplType'] = tupltype
            
        except Exception:
            pass
        
        return metadata
    
    def _parse_pbm_pgm_ppm(self, file_data: bytes, metadata: Dict[str, Any], magic: bytes, is_ascii: bool) -> Dict[str, Any]:
        """Parse PBM, PGM, or PPM format."""
        # Determine format type
        if magic in (self.PBM_ASCII, self.PBM_BINARY):
            format_name = 'PBM'
            format_ext = 'pbm'
            mime_type = 'image/x-portable-bitmap'
        elif magic in (self.PGM_ASCII, self.PGM_BINARY):
            format_name = 'PGM'
            format_ext = 'pgm'
            mime_type = 'image/x-portable-graymap'
        elif magic in (self.PPM_ASCII, self.PPM_BINARY):
            format_name = 'PPM'
            format_ext = 'ppm'
            mime_type = 'image/x-portable-pixmap'
        else:
            format_name = 'PNM'
            format_ext = 'pnm'
            mime_type = 'image/x-portable-anymap'
        
        metadata['File:FileType'] = format_name
        metadata['File:FileTypeExtension'] = format_ext
        metadata['File:MIMEType'] = mime_type
        
        try:
            if is_ascii:
                # ASCII format: P1/P2/P3\nwidth height\n[maxval]\n[data]
                lines = file_data.split(b'\n')
                # Skip comments and empty lines
                data_lines = []
                for line in lines[1:]:
                    line_str = line.decode('ascii', errors='ignore').strip()
                    if line_str and not line_str.startswith('#'):
                        data_lines.append(line_str)
                
                if len(data_lines) >= 2:
                    width, height = map(int, data_lines[0].split()[:2])
                    metadata[f'{format_name}:Width'] = width
                    metadata[f'{format_name}:Height'] = height
                    metadata['File:ImageWidth'] = width
                    metadata['File:ImageHeight'] = height
                    
                    if format_name in ('PGM', 'PPM') and len(data_lines) >= 3:
                        maxval = int(data_lines[1])
                        metadata[f'{format_name}:MaxVal'] = maxval
            else:
                # Binary format: P4/P5/P6\nwidth height\n[maxval]\n[data]
                # Find first newline after magic number
                first_nl = file_data.find(b'\n', 2)
                if first_nl == -1:
                    return metadata
                
                # Parse header (skip comments)
                header_start = first_nl + 1
                header_end = header_start
                while header_end < len(file_data):
                    if file_data[header_end:header_end+1] == b'\n':
                        # Check if this line is a comment
                        line = file_data[header_start:header_end].decode('ascii', errors='ignore').strip()
                        if line and not line.startswith('#'):
                            # This is a data line
                            parts = line.split()
                            if len(parts) >= 2:
                                width = int(parts[0])
                                height = int(parts[1])
                                metadata[f'{format_name}:Width'] = width
                                metadata[f'{format_name}:Height'] = height
                                metadata['File:ImageWidth'] = width
                                metadata['File:ImageHeight'] = height
                                
                                if format_name in ('PGM', 'PPM') and len(parts) >= 3:
                                    maxval = int(parts[2])
                                    metadata[f'{format_name}:MaxVal'] = maxval
                                break
                        header_start = header_end + 1
                    header_end += 1
        
        except Exception:
            pass
        
        return metadata

