# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
iWork file metadata parser

This module handles reading metadata from iWork files (Pages, Numbers, Keynote).
iWork files are ZIP-based formats that contain preview images.

Copyright 2025 DNAi inc.
"""

import struct
import zipfile
from typing import Dict, Any, Optional, List
from pathlib import Path
from io import BytesIO

from dnexif.exceptions import MetadataReadError


class IWorkParser:
    """
    Parser for iWork file metadata.
    
    iWork files (Pages, Numbers, Keynote) are ZIP-based formats.
    They contain preview images in various locations:
    - Preview/ directory
    - QuickLook/ directory
    - Thumbnails/ directory
    - preview.jpg, preview.png files
    """
    
    # iWork file extensions
    IWORK_EXTENSIONS = {'.pages', '.numbers', '.key'}
    
    # Common preview image paths in iWork files
    PREVIEW_PATHS = [
        'Preview/',
        'QuickLook/',
        'Thumbnails/',
        'preview.jpg',
        'preview.png',
        'Preview.jpg',
        'Preview.png',
        'thumbnail.jpg',
        'thumbnail.png',
    ]
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize iWork parser.
        
        Args:
            file_path: Path to iWork file
            file_data: iWork file data bytes
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
        Parse iWork metadata and extract preview images.
        
        Returns:
            Dictionary of iWork metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 4:
                raise MetadataReadError("Invalid iWork file: too short")
            
            metadata = {}
            
            # Detect iWork format
            iwork_type = self._detect_iwork_type()
            if not iwork_type:
                return metadata
            
            metadata['File:FileType'] = iwork_type
            metadata['File:FileTypeExtension'] = self.file_path.suffix.lower() if self.file_path else ''
            metadata['File:MIMEType'] = self._get_mime_type(iwork_type)
            
            # Parse ZIP structure to find preview images
            preview_info = self._extract_preview_images(file_data)
            if preview_info:
                metadata.update(preview_info)
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse iWork metadata: {str(e)}")
    
    def _detect_iwork_type(self) -> Optional[str]:
        """
        Detect iWork file type.
        
        Returns:
            iWork type ('Pages', 'Numbers', 'Keynote') or None
        """
        if self.file_path:
            ext = self.file_path.suffix.lower()
            if ext == '.pages':
                return 'Pages'
            elif ext == '.numbers':
                return 'Numbers'
            elif ext == '.key':
                return 'Keynote'
        
        return None
    
    def _get_mime_type(self, iwork_type: str) -> str:
        """
        Get MIME type for iWork file.
        
        Args:
            iwork_type: iWork type ('Pages', 'Numbers', 'Keynote')
            
        Returns:
            MIME type string
        """
        mime_types = {
            'Pages': 'application/vnd.apple.pages',
            'Numbers': 'application/vnd.apple.numbers',
            'Keynote': 'application/vnd.apple.keynote',
        }
        return mime_types.get(iwork_type, 'application/zip')
    
    def _extract_preview_images(self, file_data: bytes) -> Dict[str, Any]:
        """
        Extract preview images from iWork ZIP structure.
        
        Args:
            file_data: iWork file data bytes
            
        Returns:
            Dictionary of preview image metadata
        """
        metadata = {}
        
        try:
            # Check if it's a ZIP file
            if not file_data.startswith(b'PK'):
                return metadata
            
            # Open as ZIP file
            zip_file = zipfile.ZipFile(BytesIO(file_data), 'r')
            
            # Get list of files in ZIP
            file_list = zip_file.namelist()
            
            # Look for preview images
            preview_images = []
            
            for file_path in file_list:
                # Check if it's a preview image path
                is_preview = False
                preview_type = None
                
                # Check common preview paths
                if any(file_path.startswith(path) for path in self.PREVIEW_PATHS):
                    is_preview = True
                    if 'Preview' in file_path or 'preview' in file_path.lower():
                        preview_type = 'Preview'
                    elif 'QuickLook' in file_path or 'quicklook' in file_path.lower():
                        preview_type = 'QuickLook'
                    elif 'Thumbnail' in file_path or 'thumbnail' in file_path.lower():
                        preview_type = 'Thumbnail'
                    else:
                        preview_type = 'Preview'
                
                # Check file extension for image files
                if not is_preview:
                    file_ext = Path(file_path).suffix.lower()
                    if file_ext in ('.jpg', '.jpeg', '.png', '.gif', '.tiff', '.tif'):
                        # Check if it's in a preview-related directory
                        if any(prev_path in file_path for prev_path in ['Preview', 'preview', 'QuickLook', 'quicklook', 'Thumbnail', 'thumbnail']):
                            is_preview = True
                            preview_type = 'Preview'
                
                if is_preview:
                    try:
                        # Extract preview image info
                        preview_data = zip_file.read(file_path)
                        
                        # Get image dimensions if possible
                        dimensions = self._get_image_dimensions(preview_data, file_path)
                        
                        preview_info = {
                            'path': file_path,
                            'size': len(preview_data),
                            'type': preview_type,
                        }
                        
                        if dimensions:
                            preview_info['width'] = dimensions.get('width')
                            preview_info['height'] = dimensions.get('height')
                            preview_info['format'] = dimensions.get('format')
                        
                        preview_images.append(preview_info)
                        
                    except Exception:
                        # Skip files that can't be read
                        continue
            
            # Store preview image information
            if preview_images:
                metadata['IWork:PreviewImageCount'] = len(preview_images)
                
                # Store information about each preview image
                for i, preview_info in enumerate(preview_images[:10], 1):  # Limit to 10 previews
                    prefix = f'IWork:PreviewImage{i}'
                    metadata[f'{prefix}:Path'] = preview_info['path']
                    metadata[f'{prefix}:Size'] = preview_info['size']
                    metadata[f'{prefix}:Type'] = preview_info['type']
                    
                    if 'width' in preview_info:
                        metadata[f'{prefix}:Width'] = preview_info['width']
                    if 'height' in preview_info:
                        metadata[f'{prefix}:Height'] = preview_info['height']
                    if 'format' in preview_info:
                        metadata[f'{prefix}:Format'] = preview_info['format']
                
                # Store summary
                metadata['IWork:HasPreviewImages'] = True
                metadata['IWork:PreviewImageTypes'] = list(set(p['type'] for p in preview_images))
            
            zip_file.close()
        
        except Exception:
            pass
        
        return metadata
    
    def _get_image_dimensions(self, image_data: bytes, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get image dimensions from image data.
        
        Args:
            image_data: Image data bytes
            file_path: File path (for format detection)
            
        Returns:
            Dictionary with 'width', 'height', and 'format' keys, or None
        """
        try:
            file_ext = Path(file_path).suffix.lower()
            
            # JPEG
            if file_ext in ('.jpg', '.jpeg'):
                if image_data[:2] == b'\xff\xd8':
                    # Look for SOF marker
                    offset = 2
                    while offset < len(image_data) - 8:
                        if image_data[offset:offset+2] in (b'\xff\xc0', b'\xff\xc1', b'\xff\xc2'):
                            # SOF marker found
                            height = struct.unpack('>H', image_data[offset+5:offset+7])[0]
                            width = struct.unpack('>H', image_data[offset+7:offset+9])[0]
                            return {'width': width, 'height': height, 'format': 'JPEG'}
                        offset += 1
            
            # PNG
            elif file_ext == '.png':
                if image_data[:8] == b'\x89PNG\r\n\x1a\n':
                    # PNG IHDR chunk contains dimensions
                    width = struct.unpack('>I', image_data[16:20])[0]
                    height = struct.unpack('>I', image_data[20:24])[0]
                    return {'width': width, 'height': height, 'format': 'PNG'}
            
            # TIFF
            elif file_ext in ('.tiff', '.tif'):
                if image_data[:2] in (b'II', b'MM'):
                    endian = '<' if image_data[0] == ord('I') else '>'
                    # Check magic number
                    if struct.unpack(f'{endian}H', image_data[2:4])[0] == 42:
                        # Read IFD offset
                        ifd_offset = struct.unpack(f'{endian}I', image_data[4:8])[0]
                        if ifd_offset + 2 < len(image_data):
                            # Read IFD entry count
                            entry_count = struct.unpack(f'{endian}H', image_data[ifd_offset:ifd_offset+2])[0]
                            # Look for ImageWidth (tag 256) and ImageLength (tag 257)
                            for i in range(entry_count):
                                entry_offset = ifd_offset + 2 + (i * 12)
                                if entry_offset + 12 <= len(image_data):
                                    tag = struct.unpack(f'{endian}H', image_data[entry_offset:entry_offset+2])[0]
                                    if tag == 256:  # ImageWidth
                                        width = struct.unpack(f'{endian}I', image_data[entry_offset+8:entry_offset+12])[0]
                                    elif tag == 257:  # ImageLength
                                        height = struct.unpack(f'{endian}I', image_data[entry_offset+8:entry_offset+12])[0]
                            if 'width' in locals() and 'height' in locals():
                                return {'width': width, 'height': height, 'format': 'TIFF'}
        
        except Exception:
            pass
        
        return None

