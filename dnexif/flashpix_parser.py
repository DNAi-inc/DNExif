# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
FlashPix metadata parser

This module handles reading FlashPix metadata from JPEG APP2 segments.
FlashPix is a Microsoft image format that can be embedded in JPEG files.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class FlashPixParser:
    """
    Parser for FlashPix metadata.
    
    FlashPix metadata is typically embedded in JPEG APP2 segments
    with identifier "FPXR\x00\x00\x00\x00".
    """
    
    # FlashPix identifier
    FLASHPIX_IDENTIFIER = b'FPXR\x00\x00\x00\x00'
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize FlashPix parser.
        
        Args:
            file_path: Path to file
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
        Parse FlashPix metadata.
        
        Returns:
            Dictionary of FlashPix metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            metadata = {}
            
            # Check if it's a JPEG file
            if not file_data.startswith(b'\xff\xd8'):
                return metadata
            
            # Search for FlashPix in APP2 segments
            offset = 2  # Skip JPEG signature
            
            while offset < len(file_data) - 4:
                # Look for APP2 marker (0xFFE2)
                if file_data[offset:offset+2] == b'\xff\xe2':
                    # Read segment length
                    length = struct.unpack('>H', file_data[offset+2:offset+4])[0]
                    
                    # Check for FlashPix identifier
                    if file_data[offset+4:offset+12] == self.FLASHPIX_IDENTIFIER:
                        # Extract FlashPix data
                        flashpix_data = file_data[offset+12:offset+2+length]
                        
                        # Parse FlashPix structure
                        parsed = self._parse_flashpix_data(flashpix_data)
                        metadata.update(parsed)
                    
                    offset += length
                else:
                    offset += 1
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse FlashPix metadata: {str(e)}")
    
    def _parse_flashpix_data(self, data: bytes) -> Dict[str, Any]:
        """
        Parse FlashPix data structure and extract embedded images.
        
        FlashPix files can contain multiple embedded images:
        - Thumbnail images
        - Preview images
        - Subsampled images at different resolutions
        - Storage objects with image data
        
        Args:
            data: FlashPix data bytes
            
        Returns:
            Dictionary of parsed FlashPix metadata
        """
        metadata = {}
        
        try:
            if len(data) < 4:
                return metadata
            
            # Check for FlashPix version
            if data[:4] == b'FPXR':
                metadata['FlashPix:Version'] = 'FlashPix'
            
            # Mark that FlashPix data was found
            metadata['FlashPix:HasFlashPix'] = True
            metadata['FlashPix:DataSize'] = len(data)
            
            # Extract embedded images from FlashPix data
            # FlashPix can contain multiple JPEG images embedded within the structure
            embedded_images = self._extract_embedded_images(data)
            if embedded_images:
                metadata.update(embedded_images)
            
            # Look for FlashPix storage objects
            # FlashPix uses OLE2 compound file format internally
            # Storage objects can contain image data
            storage_info = self._extract_storage_objects(data)
            if storage_info:
                metadata.update(storage_info)
        
        except Exception:
            pass
        
        return metadata
    
    def _extract_embedded_images(self, data: bytes) -> Dict[str, Any]:
        """
        Extract embedded images from FlashPix data.
        
        FlashPix files can contain multiple embedded JPEG images:
        - Thumbnail images (typically small JPEG)
        - Preview images (medium-sized JPEG)
        - Subsampled images (different resolutions)
        
        Args:
            data: FlashPix data bytes
            
        Returns:
            Dictionary of embedded image metadata
        """
        metadata = {}
        
        try:
            # Look for JPEG signatures within FlashPix data
            # JPEG images start with 0xFFD8
            jpeg_signatures = []
            offset = 0
            
            while offset < len(data) - 2:
                if data[offset:offset+2] == b'\xff\xd8':
                    # Found JPEG signature
                    jpeg_start = offset
                    
                    # Try to find JPEG end marker (0xFFD9)
                    jpeg_end = -1
                    search_offset = offset + 2
                    while search_offset < len(data) - 1:
                        if data[search_offset:search_offset+2] == b'\xff\xd9':
                            jpeg_end = search_offset + 2
                            break
                        search_offset += 1
                    
                    if jpeg_end > jpeg_start:
                        jpeg_size = jpeg_end - jpeg_start
                        jpeg_signatures.append({
                            'offset': jpeg_start,
                            'size': jpeg_size,
                            'end': jpeg_end
                        })
                        offset = jpeg_end  # Skip past this JPEG
                    else:
                        offset += 1
                else:
                    offset += 1
            
            if jpeg_signatures:
                metadata['FlashPix:EmbeddedImageCount'] = len(jpeg_signatures)
                
                # Extract information about each embedded image
                for i, jpeg_info in enumerate(jpeg_signatures):
                    jpeg_offset = jpeg_info['offset']
                    jpeg_size = jpeg_info['size']
                    
                    # Try to extract JPEG dimensions from the embedded image
                    jpeg_data = data[jpeg_offset:jpeg_offset+min(jpeg_size, 65536)]  # Read up to 64KB
                    
                    # Extract JPEG dimensions (from SOF marker)
                    dimensions = self._extract_jpeg_dimensions(jpeg_data)
                    if dimensions:
                        metadata[f'FlashPix:EmbeddedImage{i+1}:Width'] = dimensions['width']
                        metadata[f'FlashPix:EmbeddedImage{i+1}:Height'] = dimensions['height']
                    
                    metadata[f'FlashPix:EmbeddedImage{i+1}:Offset'] = jpeg_offset
                    metadata[f'FlashPix:EmbeddedImage{i+1}:Size'] = jpeg_size
                    
                    # Classify image type based on size and position
                    if i == 0:
                        metadata[f'FlashPix:EmbeddedImage{i+1}:Type'] = 'Thumbnail'
                    elif jpeg_size < 50000:  # Less than 50KB, likely thumbnail
                        metadata[f'FlashPix:EmbeddedImage{i+1}:Type'] = 'Thumbnail'
                    elif jpeg_size < 500000:  # Less than 500KB, likely preview
                        metadata[f'FlashPix:EmbeddedImage{i+1}:Type'] = 'Preview'
                    else:
                        metadata[f'FlashPix:EmbeddedImage{i+1}:Type'] = 'Subsampled'
        
        except Exception:
            pass
        
        return metadata
    
    def _extract_jpeg_dimensions(self, jpeg_data: bytes) -> Optional[Dict[str, int]]:
        """
        Extract JPEG image dimensions from JPEG data.
        
        Args:
            jpeg_data: JPEG image data bytes
            
        Returns:
            Dictionary with 'width' and 'height' keys, or None if not found
        """
        try:
            # Look for SOF (Start of Frame) markers
            # SOF0 (0xFFC0), SOF1 (0xFFC1), SOF2 (0xFFC2), etc.
            sof_markers = [b'\xff\xc0', b'\xff\xc1', b'\xff\xc2', b'\xff\xc3',
                          b'\xff\xc5', b'\xff\xc6', b'\xff\xc7', b'\xff\xc9',
                          b'\xff\xca', b'\xff\xcb', b'\xff\xcd', b'\xff\xce', b'\xff\xcf']
            
            for sof_marker in sof_markers:
                sof_pos = jpeg_data.find(sof_marker)
                if sof_pos >= 0 and sof_pos + 7 < len(jpeg_data):
                    # SOF structure: marker (2) + length (2) + precision (1) + height (2) + width (2)
                    # Height is at offset sof_pos + 5
                    # Width is at offset sof_pos + 7
                    height = struct.unpack('>H', jpeg_data[sof_pos+5:sof_pos+7])[0]
                    width = struct.unpack('>H', jpeg_data[sof_pos+7:sof_pos+9])[0]
                    return {'width': width, 'height': height}
        except Exception:
            pass
        
        return None
    
    def _extract_storage_objects(self, data: bytes) -> Dict[str, Any]:
        """
        Extract FlashPix storage object information.
        
        FlashPix uses OLE2 compound file format internally.
        Storage objects can contain image data and metadata.
        
        Args:
            data: FlashPix data bytes
            
        Returns:
            Dictionary of storage object metadata
        """
        metadata = {}
        
        try:
            # FlashPix/OLE2 compound file signature
            # OLE2 files start with specific header structure
            # Look for OLE2 signature patterns
            
            # OLE2 header signature: D0CF11E0A1B11AE1 (little-endian)
            ole2_sig = bytes.fromhex('d0cf11e0a1b11ae1')
            
            if data[:8] == ole2_sig:
                metadata['FlashPix:StorageFormat'] = 'OLE2'
                metadata['FlashPix:HasOLE2Header'] = True
                
                # Try to extract storage object count
                # OLE2 structure: header (512 bytes) + directory entries
                if len(data) >= 512:
                    # Directory entries start after header
                    # Each directory entry is 128 bytes
                    # First byte of directory entry indicates type
                    dir_offset = 512
                    storage_count = 0
                    stream_count = 0
                    
                    while dir_offset + 128 <= len(data) and storage_count < 100:
                        dir_entry = data[dir_offset:dir_offset+128]
                        
                        # Check entry type (byte 66)
                        if len(dir_entry) >= 67:
                            entry_type = dir_entry[66]
                            
                            if entry_type == 1:  # Storage object
                                storage_count += 1
                            elif entry_type == 2:  # Stream object
                                stream_count += 1
                                # Stream objects can contain image data
                                # Extract stream name (first 64 bytes, null-terminated)
                                stream_name = dir_entry[0:64].split(b'\x00')[0].decode('utf-16-le', errors='ignore')
                                if stream_name:
                                    metadata[f'FlashPix:Stream{stream_count}:Name'] = stream_name
                            
                            # Check for end of directory (empty entry)
                            if entry_type == 0 and all(b == 0 for b in dir_entry[:64]):
                                break
                        
                        dir_offset += 128
                    
                    if storage_count > 0:
                        metadata['FlashPix:StorageObjectCount'] = storage_count
                    if stream_count > 0:
                        metadata['FlashPix:StreamCount'] = stream_count
            
            # Also look for FlashPix-specific storage object identifiers
            # FlashPix uses specific GUIDs and object names
            flashpix_objects = [
                (b'\x00Image', 'Image'),
                (b'\x00Thumbnail', 'Thumbnail'),
                (b'\x00Preview', 'Preview'),
                (b'Image', 'Image'),
                (b'Thumbnail', 'Thumbnail'),
                (b'Preview', 'Preview'),
            ]
            
            for obj_pattern, obj_name in flashpix_objects:
                if obj_pattern in data:
                    obj_pos = data.find(obj_pattern)
                    metadata[f'FlashPix:Has{obj_name}Object'] = True
                    metadata[f'FlashPix:{obj_name}ObjectOffset'] = obj_pos
        
        except Exception:
            pass
        
        return metadata

