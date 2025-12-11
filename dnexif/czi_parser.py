# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Zeiss CZI (Carl Zeiss Image) file metadata parser

This module handles reading metadata from Zeiss CZI image files.
CZI files are used by Zeiss microscopes and contain microscopy image data.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class CZIParser:
    """
    Parser for Zeiss CZI (Carl Zeiss Image) metadata.
    
    CZI files have a file directory structure with segments containing
    metadata and image data.
    """
    
    # CZI file directory signature
    CZI_DIRECTORY_SIGNATURE = b'ZISRAWFILE'
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize CZI parser.
        
        Args:
            file_path: Path to CZI file
            file_data: CZI file data bytes
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
        Parse CZI metadata.
        
        Returns:
            Dictionary of CZI metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 16:
                raise MetadataReadError("Invalid CZI file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'CZI'
            metadata['File:FileTypeExtension'] = 'czi'
            metadata['File:MIMEType'] = 'image/x-zeiss-czi'
            metadata['Zeiss:Format'] = 'CZI'
            metadata['Zeiss:FormatName'] = 'Carl Zeiss Image'
            
            # Check for CZI directory signature
            if file_data.startswith(self.CZI_DIRECTORY_SIGNATURE):
                metadata['Zeiss:HasDirectorySignature'] = True
                metadata['Zeiss:FormatType'] = 'ZISRAW'
                
                # CZI file directory structure:
                # - Bytes 0-9: "ZISRAWFILE" signature
                # - Bytes 10-13: Major version (uint32, little-endian)
                # - Bytes 14-17: Minor version (uint32, little-endian)
                # - Bytes 18-21: Reserved (uint32)
                # - Bytes 22-29: Primary file directory segment position (int64, little-endian)
                # - Bytes 30-37: Metadata segment position (int64, little-endian)
                # - Bytes 38-45: Update pending segment position (int64, little-endian)
                # - Bytes 46-53: Attachment directory segment position (int64, little-endian)
                
                if len(file_data) >= 54:
                    # Read version
                    major_version = struct.unpack('<I', file_data[10:14])[0]
                    minor_version = struct.unpack('<I', file_data[14:18])[0]
                    metadata['Zeiss:Version'] = f'{major_version}.{minor_version}'
                    metadata['Zeiss:MajorVersion'] = major_version
                    metadata['Zeiss:MinorVersion'] = minor_version
                    
                    # Read segment positions
                    primary_fd_pos = struct.unpack('<q', file_data[22:30])[0]
                    metadata_seg_pos = struct.unpack('<q', file_data[30:38])[0]
                    update_pending_pos = struct.unpack('<q', file_data[38:46])[0]
                    attachment_dir_pos = struct.unpack('<q', file_data[46:54])[0]
                    
                    if primary_fd_pos > 0:
                        metadata['Zeiss:PrimaryFileDirectoryPosition'] = primary_fd_pos
                    if metadata_seg_pos > 0:
                        metadata['Zeiss:MetadataSegmentPosition'] = metadata_seg_pos
                    if update_pending_pos > 0:
                        metadata['Zeiss:UpdatePendingSegmentPosition'] = update_pending_pos
                    if attachment_dir_pos > 0:
                        metadata['Zeiss:AttachmentDirectoryPosition'] = attachment_dir_pos
            
            # Check for alternative CZI signatures
            elif file_data[:4] == b'CZIS' or file_data[:4] == b'CZI\x00':
                metadata['Zeiss:HasAlternativeSignature'] = True
                metadata['Zeiss:FormatType'] = 'CZI Alternative'
            
            # Search for Zeiss-specific metadata
            # CZI files may contain XML metadata
            if b'Zeiss' in file_data[:4096] or b'ZEISS' in file_data[:4096]:
                metadata['Zeiss:HasZeissMarker'] = True
            
            # Look for XML metadata (CZI files often contain XML metadata)
            if b'<?xml' in file_data[:8192] or b'<ImageDocument' in file_data[:8192]:
                metadata['Zeiss:HasXMLMetadata'] = True
                
                # Try to extract XML metadata snippet
                xml_start = file_data.find(b'<?xml')
                if xml_start == -1:
                    xml_start = file_data.find(b'<ImageDocument')
                
                if xml_start >= 0 and xml_start < len(file_data) - 100:
                    xml_snippet = file_data[xml_start:xml_start+200].decode('utf-8', errors='ignore')
                    if len(xml_snippet) > 0:
                        metadata['Zeiss:XMLMetadataSnippet'] = xml_snippet[:100] + '...' if len(xml_snippet) > 100 else xml_snippet
            
            # Look for dimension information
            # CZI files may store dimensions in various locations
            # Try to find common dimension patterns
            if len(file_data) >= 64:
                for offset in range(16, min(1024, len(file_data) - 8), 4):
                    try:
                        # Try little-endian 32-bit integers
                        width = struct.unpack('<I', file_data[offset:offset+4])[0]
                        height = struct.unpack('<I', file_data[offset+4:offset+8])[0]
                        
                        # Validate dimensions (reasonable values for microscopy)
                        if 10 < width < 100000 and 10 < height < 100000:
                            # Check if ratio is reasonable
                            ratio = width / height if height > 0 else 0
                            if 0.1 < ratio < 10:
                                metadata['Zeiss:Width'] = width
                                metadata['Zeiss:Height'] = height
                                metadata['Image:ImageWidth'] = width
                                metadata['Image:ImageHeight'] = height
                                break
                    except Exception:
                        continue
            
            # Look for channel count (microscopy images often have multiple channels)
            if b'Channel' in file_data[:4096] or b'CHANNEL' in file_data[:4096]:
                metadata['Zeiss:HasChannelInformation'] = True
            
            # Look for pixel type information
            pixel_types = [b'uint8', b'uint16', b'uint32', b'float32', b'float64']
            for pixel_type in pixel_types:
                if pixel_type in file_data[:4096]:
                    metadata['Zeiss:PixelType'] = pixel_type.decode('utf-8', errors='ignore')
                    break
            
            # File size
            if self.file_path:
                try:
                    file_size = self.file_path.stat().st_size
                    metadata['File:FileSize'] = file_size
                except Exception:
                    pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse CZI metadata: {str(e)}")

