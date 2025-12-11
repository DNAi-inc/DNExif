# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
TGA (Targa) metadata parser

This module handles reading metadata from TGA files.
TGA files have limited metadata support in the file header.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError

FOOTER_SIGNATURE = b'TRUEVISION-XFILE.\x00'


class TGAParser:
    """
    Parser for TGA metadata.
    
    TGA files have limited metadata support:
    - File header with image dimensions, color depth, compression
    - Image ID field (optional text)
    - Color map information
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize TGA parser.
        
        Args:
            file_path: Path to TGA file
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
        Parse TGA metadata.
        
        Returns:
            Dictionary of TGA metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 18:
                raise MetadataReadError("Invalid TGA file: too short")
            
            metadata = {}
            
            # Parse TGA header (18 bytes)
            id_length = file_data[0]
            color_map_type = file_data[1]
            image_type = file_data[2]
            
            metadata['TGA:IDLength'] = id_length
            metadata['TGA:ColorMapType'] = color_map_type
            metadata['TGA:ImageType'] = image_type
            
            # Color map specification (5 bytes)
            color_map_start = struct.unpack('<H', file_data[3:5])[0]
            color_map_length = struct.unpack('<H', file_data[5:7])[0]
            color_map_entry_size = file_data[7]
            
            metadata['TGA:ColorMapStart'] = color_map_start
            metadata['TGA:ColorMapLength'] = color_map_length
            metadata['TGA:ColorMapEntrySize'] = color_map_entry_size
            
            # Image specification (10 bytes)
            x_origin = struct.unpack('<H', file_data[8:10])[0]
            y_origin = struct.unpack('<H', file_data[10:12])[0]
            width = struct.unpack('<H', file_data[12:14])[0]
            height = struct.unpack('<H', file_data[14:16])[0]
            pixel_depth = file_data[16]
            image_descriptor = file_data[17]
            
            metadata['TGA:Width'] = width
            metadata['TGA:Height'] = height
            metadata['TGA:XOrigin'] = x_origin
            metadata['TGA:YOrigin'] = y_origin
            metadata['TGA:PixelDepth'] = pixel_depth
            metadata['TGA:ImageDescriptor'] = image_descriptor
            
            # TGA files: Standard format shows ImageCount as 0 (not 1)
            metadata['File:ImageCount'] = 0
            
            # Image ID field (optional)
            if id_length > 0 and len(file_data) >= 18 + id_length:
                image_id = file_data[18:18+id_length]
                try:
                    metadata['TGA:ImageID'] = image_id.decode('ascii', errors='ignore').strip('\x00')
                except:
                    metadata['TGA:ImageID'] = image_id.hex()
            
            # Footer (optional, TGA 2.0)
            if len(file_data) >= 26:
                footer_start = len(file_data) - 26
                signature = file_data[footer_start+8:footer_start+26]
                if signature == FOOTER_SIGNATURE:
                    # TGA 2.0 footer found
                    extension_area_offset = struct.unpack('<I', file_data[footer_start:footer_start+4])[0]
                    developer_area_offset = struct.unpack('<I', file_data[footer_start+4:footer_start+8])[0]
                    
                    metadata['TGA:Version'] = '2.0'
                    metadata['TGA:ExtensionAreaOffset'] = extension_area_offset
                    metadata['TGA:DeveloperAreaOffset'] = developer_area_offset
                    
                    # Parse extension area if present
                    if 0 < extension_area_offset < footer_start:
                        ext_metadata = self._parse_extension_area(file_data, extension_area_offset)
                        metadata.update(ext_metadata)
            
            return metadata
            
        except Exception as e:
            raise MetadataReadError(f"Failed to parse TGA metadata: {str(e)}")
    
    def _parse_extension_area(self, file_data: bytes, offset: int) -> Dict[str, Any]:
        """
        Parse TGA 2.0 extension area.
        
        Args:
            file_data: TGA file data
            offset: Offset to extension area
            
        Returns:
            Dictionary of extension area metadata
        """
        metadata = {}
        
        try:
            if offset + 495 > len(file_data):
                return metadata
            
            # Extension area is 495 bytes
            # Author name (41 bytes)
            base_offset = offset
            data_start = offset
            
            # Extension size (first 2 bytes in TGA 2.0 spec)
            if offset + 2 <= len(file_data):
                ext_size = struct.unpack('<H', file_data[offset:offset+2])[0]
                # TGA extension area is typically 495 bytes. If size matches, skip size field.
                if 200 <= ext_size <= 1024:
                    data_start = offset + 2
            
            author_name = file_data[data_start:data_start+41]
            if author_name:
                try:
                    author = author_name.decode('ascii', errors='ignore').strip('\x00')
                    if author:
                        metadata['TGA:AuthorName'] = author
                        metadata.setdefault('XMP:Title', author)
                        metadata['EXIF:Artist'] = author
                        metadata['Artist'] = author
                except:
                    pass
            
            # Comments (324 bytes, 4 lines of 81 bytes each)
            comments = []
            for i in range(4):
                comment_start = data_start + 41 + (i * 81)
                comment = file_data[comment_start:comment_start+81]
                try:
                    comment_str = comment.decode('ascii', errors='ignore').strip('\x00')
                    if comment_str:
                        comments.append(comment_str)
                except:
                    pass
            
            if comments:
                metadata['TGA:Comments'] = comments
                if 'XMP:Title' not in metadata:
                    metadata['XMP:Title'] = comments[0]
                if 'EXIF:Artist' not in metadata:
                    metadata['EXIF:Artist'] = comments[0]
                    metadata['Artist'] = comments[0]
            
            # Date/time stamp (12 bytes)
            date_time = file_data[data_start+365:data_start+377]
            if date_time:
                try:
                    # TGA date format: month, day, year, hour, minute, second (2 bytes each)
                    month = struct.unpack('<H', date_time[0:2])[0]
                    day = struct.unpack('<H', date_time[2:4])[0]
                    year = struct.unpack('<H', date_time[4:6])[0]
                    hour = struct.unpack('<H', date_time[6:8])[0]
                    minute = struct.unpack('<H', date_time[8:10])[0]
                    second = struct.unpack('<H', date_time[10:12])[0]
                    
                    if year > 0:
                        metadata['TGA:DateTime'] = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
                except:
                    pass
            
            # Job name (41 bytes)
            job_name = file_data[data_start+377:data_start+418]
            if job_name:
                try:
                    job = job_name.decode('ascii', errors='ignore').strip('\x00')
                    if job:
                        metadata['TGA:JobName'] = job
                except:
                    pass
            
        except Exception:
            pass
        
        return metadata

