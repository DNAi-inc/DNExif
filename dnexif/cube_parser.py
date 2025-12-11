# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Parser for CUBE (LUT - Look-Up Table) files.

CUBE files are text-based color lookup table files used for color grading.
They contain header information and RGB lookup values.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import re

from dnexif.exceptions import MetadataReadError


class CUBEParser:
    """
    Parser for CUBE (LUT) metadata.
    
    CUBE files are text-based color lookup table files:
    - Header lines with metadata (TITLE, LUT_3D_SIZE, DOMAIN_MIN, DOMAIN_MAX, etc.)
    - RGB lookup values (one per line)
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize CUBE parser.
        
        Args:
            file_path: Path to CUBE file
            file_data: CUBE file data bytes
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
        Parse CUBE metadata.
        
        Returns:
            Dictionary of CUBE metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    file_text = f.read()
            else:
                file_text = self.file_data.decode('utf-8', errors='ignore')
            
            if not file_text.strip():
                raise MetadataReadError("Invalid CUBE file: empty file")
            
            metadata = {}
            metadata['File:FileType'] = 'CUBE'
            metadata['File:FileTypeExtension'] = 'cube'
            metadata['File:MIMEType'] = 'application/x-cube-lut'
            
            lines = file_text.split('\n')
            
            # Parse header lines
            lut_3d_size = None
            lut_1d_size = None
            title = None
            domain_min = None
            domain_max = None
            lut_1d_input_range = None
            lut_1d_output_range = None
            comment_lines = []
            data_start_line = 0
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line or line.startswith('#'):
                    if line.startswith('#'):
                        comment_lines.append(line[1:].strip())
                    continue
                
                # Check for header keywords
                if line.startswith('TITLE'):
                    match = re.match(r'TITLE\s+"([^"]+)"', line)
                    if match:
                        title = match.group(1)
                        metadata['CUBE:Title'] = title
                
                elif line.startswith('LUT_3D_SIZE'):
                    match = re.match(r'LUT_3D_SIZE\s+(\d+)', line)
                    if match:
                        lut_3d_size = int(match.group(1))
                        metadata['CUBE:LUT3DSize'] = lut_3d_size
                
                elif line.startswith('LUT_1D_SIZE'):
                    match = re.match(r'LUT_1D_SIZE\s+(\d+)', line)
                    if match:
                        lut_1d_size = int(match.group(1))
                        metadata['CUBE:LUT1DSize'] = lut_1d_size
                
                elif line.startswith('DOMAIN_MIN'):
                    match = re.match(r'DOMAIN_MIN\s+([\d\.\-\+eE\s]+)', line)
                    if match:
                        values = match.group(1).split()
                        try:
                            domain_min = [float(v) for v in values]
                            metadata['CUBE:DomainMin'] = domain_min
                            if len(domain_min) >= 3:
                                metadata['CUBE:DomainMinR'] = domain_min[0]
                                metadata['CUBE:DomainMinG'] = domain_min[1]
                                metadata['CUBE:DomainMinB'] = domain_min[2]
                        except ValueError:
                            pass
                
                elif line.startswith('DOMAIN_MAX'):
                    match = re.match(r'DOMAIN_MAX\s+([\d\.\-\+eE\s]+)', line)
                    if match:
                        values = match.group(1).split()
                        try:
                            domain_max = [float(v) for v in values]
                            metadata['CUBE:DomainMax'] = domain_max
                            if len(domain_max) >= 3:
                                metadata['CUBE:DomainMaxR'] = domain_max[0]
                                metadata['CUBE:DomainMaxG'] = domain_max[1]
                                metadata['CUBE:DomainMaxB'] = domain_max[2]
                        except ValueError:
                            pass
                
                elif line.startswith('LUT_1D_INPUT_RANGE'):
                    match = re.match(r'LUT_1D_INPUT_RANGE\s+([\d\.\-\+eE\s]+)', line)
                    if match:
                        values = match.group(1).split()
                        try:
                            lut_1d_input_range = [float(v) for v in values]
                            metadata['CUBE:LUT1DInputRange'] = lut_1d_input_range
                            if len(lut_1d_input_range) >= 2:
                                metadata['CUBE:LUT1DInputRangeMin'] = lut_1d_input_range[0]
                                metadata['CUBE:LUT1DInputRangeMax'] = lut_1d_input_range[1]
                        except ValueError:
                            pass
                
                elif line.startswith('LUT_1D_OUTPUT_RANGE'):
                    match = re.match(r'LUT_1D_OUTPUT_RANGE\s+([\d\.\-\+eE\s]+)', line)
                    if match:
                        values = match.group(1).split()
                        try:
                            lut_1d_output_range = [float(v) for v in values]
                            metadata['CUBE:LUT1DOutputRange'] = lut_1d_output_range
                            if len(lut_1d_output_range) >= 2:
                                metadata['CUBE:LUT1DOutputRangeMin'] = lut_1d_output_range[0]
                                metadata['CUBE:LUT1DOutputRangeMax'] = lut_1d_output_range[1]
                        except ValueError:
                            pass
                
                else:
                    # Check if this looks like data (three floating point numbers)
                    # If we've seen header keywords, this might be data
                    if lut_3d_size or lut_1d_size:
                        data_match = re.match(r'^\s*([\d\.\-\+eE]+)\s+([\d\.\-\+eE]+)\s+([\d\.\-\+eE]+)', line)
                        if data_match:
                            data_start_line = i
                            break
            
            # Count data lines
            data_line_count = 0
            for line in lines[data_start_line:]:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('TITLE') and not line.startswith('LUT_'):
                    data_match = re.match(r'^\s*[\d\.\-\+eE]+\s+[\d\.\-\+eE]+\s+[\d\.\-\+eE]+', line)
                    if data_match:
                        data_line_count += 1
            
            if data_line_count > 0:
                metadata['CUBE:DataLineCount'] = data_line_count
            
            if comment_lines:
                metadata['CUBE:CommentCount'] = len(comment_lines)
                for i, comment in enumerate(comment_lines[:10]):  # Limit to first 10 comments
                    metadata[f'CUBE:Comment{i+1}'] = comment
            
            # Determine LUT type
            if lut_3d_size:
                metadata['CUBE:LUTType'] = '3D'
                metadata['CUBE:LUTSize'] = lut_3d_size
            elif lut_1d_size:
                metadata['CUBE:LUTType'] = '1D'
                metadata['CUBE:LUTSize'] = lut_1d_size
            else:
                metadata['CUBE:LUTType'] = 'Unknown'
            
            return metadata
            
        except Exception as e:
            raise MetadataReadError(f"Failed to parse CUBE metadata: {str(e)}")

