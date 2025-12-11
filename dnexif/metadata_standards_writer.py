# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Metadata standards writer

This module provides writing support for additional metadata standards
beyond EXIF, IPTC, and XMP, including JFIF, ICC profiles, Photoshop IRB, and AFCP.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List
from pathlib import Path

from dnexif.exceptions import MetadataWriteError
from dnexif.jpeg_modifier import JPEGModifier


class MetadataStandardsWriter:
    """
    Writer for additional metadata standards.
    
    Supports writing JFIF, ICC profiles, Photoshop IRB, and AFCP metadata.
    """
    
    def __init__(self):
        """Initialize metadata standards writer."""
        # JPEGModifier will be initialized with file data when needed
        pass
    
    def write_jfif(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write JFIF metadata to JPEG file.
        
        Args:
            file_path: Path to input JPEG file
            metadata: Dictionary of JFIF metadata to write
            output_path: Path to output JPEG file
            
        Raises:
            MetadataWriteError: If writing fails
        """
        try:
            with open(file_path, 'rb') as f:
                jpeg_data = f.read()
            
            if not jpeg_data.startswith(b'\xff\xd8'):
                raise MetadataWriteError("Invalid JPEG file: missing JPEG signature")
            
            # Extract JFIF metadata
            jfif_metadata = {}
            for key, value in metadata.items():
                if key.startswith('JFIF:'):
                    jfif_metadata[key[5:]] = value
            
            if not jfif_metadata:
                # No JFIF metadata to write, just copy file
                with open(output_path, 'wb') as f:
                    f.write(jpeg_data)
                return
            
            # Build JFIF APP0 segment
            jfif_segment = self._build_jfif_segment(jfif_metadata)
            
            # Find existing APP0 segment or insert new one
            offset = 2  # After JPEG signature
            app0_pos = -1
            app0_length = 0
            
            while offset < len(jpeg_data) - 4:
                if jpeg_data[offset:offset+2] == b'\xff\xe0':  # APP0
                    app0_pos = offset
                    app0_length = struct.unpack('>H', jpeg_data[offset+2:offset+4])[0]
                    # Check if it's JFIF
                    if jpeg_data[offset+4:offset+9] == b'JFIF\x00':
                        break
                    offset += app0_length
                elif jpeg_data[offset:offset+2] == b'\xff\xd8':  # SOI
                    offset += 2
                elif jpeg_data[offset] == 0xFF and jpeg_data[offset+1] >= 0xE0 and jpeg_data[offset+1] <= 0xEF:
                    # Other APP segment
                    length = struct.unpack('>H', jpeg_data[offset+2:offset+4])[0]
                    offset += 2 + length
                else:
                    offset += 1
            
            # Insert or replace APP0 segment
            if app0_pos != -1 and jpeg_data[app0_pos+4:app0_pos+9] == b'JFIF\x00':
                # Replace existing JFIF segment
                new_jpeg = (
                    jpeg_data[:app0_pos] +
                    jfif_segment +
                    jpeg_data[app0_pos + app0_length:]
                )
            else:
                # Insert new JFIF segment after SOI
                new_jpeg = (
                    jpeg_data[:2] +
                    jfif_segment +
                    jpeg_data[2:]
                )
            
            with open(output_path, 'wb') as f:
                f.write(new_jpeg)
                
        except Exception as e:
            raise MetadataWriteError(f"Failed to write JFIF metadata: {str(e)}")
    
    def _build_jfif_segment(self, metadata: Dict[str, Any]) -> bytes:
        """
        Build JFIF APP0 segment.
        
        Args:
            metadata: JFIF metadata dictionary
            
        Returns:
            JFIF APP0 segment bytes
        """
        # Default values
        version_major = 1
        version_minor = 1
        units = 1  # DPI
        x_density = 72
        y_density = 72
        thumb_width = 0
        thumb_height = 0
        
        # Parse metadata
        if 'Version' in metadata:
            version_str = str(metadata['Version'])
            parts = version_str.split('.')
            if len(parts) >= 1:
                version_major = int(parts[0])
            if len(parts) >= 2:
                version_minor = int(parts[1])
        
        if 'Units' in metadata:
            units_map = {'None': 0, 'DPI': 1, 'DPC': 2}
            units_str = str(metadata['Units'])
            units = units_map.get(units_str, 1)
        
        if 'XResolution' in metadata:
            x_density = int(metadata['XResolution'])
        
        if 'YResolution' in metadata:
            y_density = int(metadata['YResolution'])
        
        if 'ThumbnailWidth' in metadata:
            thumb_width = int(metadata['ThumbnailWidth'])
        
        if 'ThumbnailHeight' in metadata:
            thumb_height = int(metadata['ThumbnailHeight'])
        
        # Build segment
        segment_data = (
            b'JFIF\x00' +
            bytes([version_major, version_minor]) +
            bytes([units]) +
            struct.pack('>H', x_density) +
            struct.pack('>H', y_density) +
            bytes([thumb_width, thumb_height])
        )
        
        # Add thumbnail data if present
        if 'ThumbnailData' in metadata and thumb_width > 0 and thumb_height > 0:
            thumb_data = metadata['ThumbnailData']
            if isinstance(thumb_data, bytes):
                segment_data += thumb_data
        
        # Calculate segment length (including 2-byte length field)
        segment_length = len(segment_data) + 2
        
        # Build APP0 segment
        segment = (
            b'\xff\xe0' +  # APP0 marker
            struct.pack('>H', segment_length) +
            segment_data
        )
        
        return segment
    
    def write_icc_profile(
        self,
        file_path: str,
        icc_data: bytes,
        output_path: str
    ) -> None:
        """
        Write ICC profile to JPEG file.
        
        Args:
            file_path: Path to input JPEG file
            icc_data: ICC profile data bytes
            output_path: Path to output JPEG file
            
        Raises:
            MetadataWriteError: If writing fails
        """
        try:
            with open(file_path, 'rb') as f:
                jpeg_data = f.read()
            
            if not jpeg_data.startswith(b'\xff\xd8'):
                raise MetadataWriteError("Invalid JPEG file: missing JPEG signature")
            
            if not icc_data or len(icc_data) == 0:
                # No ICC data, just copy file
                with open(output_path, 'wb') as f:
                    f.write(jpeg_data)
                return
            
            # Split ICC profile into chunks (max 65504 bytes per chunk)
            max_chunk_size = 65504
            chunks = []
            for i in range(0, len(icc_data), max_chunk_size):
                chunks.append(icc_data[i:i+max_chunk_size])
            
            # Build APP2 segments for each chunk
            app2_segments = []
            for i, chunk in enumerate(chunks):
                segment = self._build_icc_segment(chunk, i + 1, len(chunks))
                app2_segments.append(segment)
            
            # Find existing ICC APP2 segments or insert new ones
            offset = 2
            icc_segments_pos = []
            
            while offset < len(jpeg_data) - 4:
                if jpeg_data[offset:offset+2] == b'\xff\xe2':  # APP2
                    length = struct.unpack('>H', jpeg_data[offset+2:offset+4])[0]
                    if jpeg_data[offset+4:offset+14] == b'ICC_PROFILE':
                        icc_segments_pos.append((offset, length))
                    offset += 2 + length
                elif jpeg_data[offset] == 0xFF and jpeg_data[offset+1] >= 0xE0 and jpeg_data[offset+1] <= 0xEF:
                    length = struct.unpack('>H', jpeg_data[offset+2:offset+4])[0]
                    offset += 2 + length
                else:
                    offset += 1
            
            # Replace or insert ICC segments
            if icc_segments_pos:
                # Replace existing segments
                first_pos, first_len = icc_segments_pos[0]
                last_pos, last_len = icc_segments_pos[-1]
                
                # Calculate total length of existing segments
                total_existing_len = sum(length for _, length in icc_segments_pos)
                total_new_len = sum(len(seg) for seg in app2_segments)
                
                # Replace segments
                new_jpeg = (
                    jpeg_data[:first_pos] +
                    b''.join(app2_segments) +
                    jpeg_data[last_pos + last_len:]
                )
            else:
                # Insert new segments after SOI or first APP segment
                insert_pos = 2
                if len(jpeg_data) > 4:
                    # Find first APP segment
                    pos = 2
                    while pos < len(jpeg_data) - 4:
                        if jpeg_data[pos] == 0xFF and jpeg_data[pos+1] >= 0xE0 and jpeg_data[pos+1] <= 0xEF:
                            length = struct.unpack('>H', jpeg_data[pos+2:pos+4])[0]
                            insert_pos = pos + 2 + length
                            break
                        pos += 1
                
                new_jpeg = (
                    jpeg_data[:insert_pos] +
                    b''.join(app2_segments) +
                    jpeg_data[insert_pos:]
                )
            
            with open(output_path, 'wb') as f:
                f.write(new_jpeg)
                
        except Exception as e:
            raise MetadataWriteError(f"Failed to write ICC profile: {str(e)}")
    
    def _build_icc_segment(self, chunk_data: bytes, chunk_num: int, total_chunks: int) -> bytes:
        """
        Build ICC profile APP2 segment.
        
        Args:
            chunk_data: ICC profile chunk data
            chunk_num: Chunk number (1-based)
            total_chunks: Total number of chunks
            
        Returns:
            APP2 segment bytes
        """
        segment_data = (
            b'ICC_PROFILE' +
            bytes([chunk_num, total_chunks]) +
            chunk_data
        )
        
        segment_length = len(segment_data) + 2
        
        segment = (
            b'\xff\xe2' +  # APP2 marker
            struct.pack('>H', segment_length) +
            segment_data
        )
        
        return segment
    
    def write_photoshop_irb(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write Photoshop IRB metadata to JPEG file.
        
        Args:
            file_path: Path to input JPEG file
            metadata: Dictionary of Photoshop IRB metadata
            output_path: Path to output JPEG file
            
        Raises:
            MetadataWriteError: If writing fails
        """
        try:
            with open(file_path, 'rb') as f:
                jpeg_data = f.read()
            
            if not jpeg_data.startswith(b'\xff\xd8'):
                raise MetadataWriteError("Invalid JPEG file: missing JPEG signature")
            
            # Build Photoshop IRB APP13 segment
            irb_segment = self._build_photoshop_irb_segment(metadata)
            
            # Find existing APP13 segment or insert new one
            offset = 2
            app13_pos = -1
            app13_length = 0
            
            while offset < len(jpeg_data) - 4:
                if jpeg_data[offset:offset+2] == b'\xff\xed':  # APP13
                    app13_pos = offset
                    app13_length = struct.unpack('>H', jpeg_data[offset+2:offset+4])[0]
                    # Check if it's Photoshop format
                    if b'Photoshop 3.0' in jpeg_data[offset+4:offset+4+app13_length] or \
                       b'8BIM' in jpeg_data[offset+4:offset+4+app13_length]:
                        break
                    offset += app13_length
                elif jpeg_data[offset] == 0xFF and jpeg_data[offset+1] >= 0xE0 and jpeg_data[offset+1] <= 0xEF:
                    length = struct.unpack('>H', jpeg_data[offset+2:offset+4])[0]
                    offset += 2 + length
                else:
                    offset += 1
            
            # Insert or replace APP13 segment
            if app13_pos != -1:
                # Replace existing segment
                new_jpeg = (
                    jpeg_data[:app13_pos] +
                    irb_segment +
                    jpeg_data[app13_pos + app13_length:]
                )
            else:
                # Insert new segment after SOI or first APP segment
                insert_pos = 2
                if len(jpeg_data) > 4:
                    pos = 2
                    while pos < len(jpeg_data) - 4:
                        if jpeg_data[pos] == 0xFF and jpeg_data[pos+1] >= 0xE0 and jpeg_data[pos+1] <= 0xEF:
                            length = struct.unpack('>H', jpeg_data[pos+2:pos+4])[0]
                            insert_pos = pos + 2 + length
                            break
                        pos += 1
                
                new_jpeg = (
                    jpeg_data[:insert_pos] +
                    irb_segment +
                    jpeg_data[insert_pos:]
                )
            
            with open(output_path, 'wb') as f:
                f.write(new_jpeg)
                
        except Exception as e:
            raise MetadataWriteError(f"Failed to write Photoshop IRB: {str(e)}")
    
    def _build_photoshop_irb_segment(self, metadata: Dict[str, Any]) -> bytes:
        """
        Build Photoshop IRB APP13 segment.
        
        Args:
            metadata: Photoshop IRB metadata dictionary
            
        Returns:
            APP13 segment bytes
        """
        # Photoshop IRB format: "Photoshop 3.0\x00" + resource blocks
        segment_data = b'Photoshop 3.0\x00'
        
        # Build resource blocks (simplified - full implementation would handle all resource types)
        for key, value in metadata.items():
            if key.startswith('PS:'):
                resource_id = int(key.split(':')[1]) if ':' in key[3:] else 0
                # Build resource block
                resource_block = self._build_resource_block(resource_id, value)
                segment_data += resource_block
        
        segment_length = len(segment_data) + 2
        
        segment = (
            b'\xff\xed' +  # APP13 marker
            struct.pack('>H', segment_length) +
            segment_data
        )
        
        return segment
    
    def _build_resource_block(self, resource_id: int, data: Any) -> bytes:
        """
        Build Photoshop resource block.
        
        Args:
            resource_id: Resource ID
            data: Resource data
            
        Returns:
            Resource block bytes
        """
        # Resource block format: "8BIM" + resource_id (2 bytes) + name (Pascal string) + data_size (4 bytes) + data
        resource_data = bytes(str(data), 'utf-8') if not isinstance(data, bytes) else data
        
        # Name (empty Pascal string)
        name = b'\x00'
        
        # Data size (must be even)
        data_size = len(resource_data)
        if data_size % 2 == 1:
            resource_data += b'\x00'
            data_size += 1
        
        resource_block = (
            b'8BIM' +
            struct.pack('>H', resource_id) +
            name +
            struct.pack('>I', data_size) +
            resource_data
        )
        
        return resource_block
    
    def write_afcp(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write AFCP metadata to JPEG file.
        
        Args:
            file_path: Path to input JPEG file
            metadata: Dictionary of AFCP metadata
            output_path: Path to output JPEG file
            
        Raises:
            MetadataWriteError: If writing fails
        """
        try:
            with open(file_path, 'rb') as f:
                jpeg_data = f.read()
            
            if not jpeg_data.startswith(b'\xff\xd8'):
                raise MetadataWriteError("Invalid JPEG file: missing JPEG signature")
            
            # Extract AFCP metadata
            afcp_metadata = {}
            for key, value in metadata.items():
                if key.startswith('AFCP:'):
                    afcp_metadata[key[5:]] = value
            
            if not afcp_metadata:
                # No AFCP metadata, just copy file
                with open(output_path, 'wb') as f:
                    f.write(jpeg_data)
                return
            
            # Build AFCP APP2 segment
            afcp_segment = self._build_afcp_segment(afcp_metadata)
            
            # Find existing AFCP APP2 segment or insert new one
            offset = 2
            afcp_pos = -1
            afcp_length = 0
            
            while offset < len(jpeg_data) - 4:
                if jpeg_data[offset:offset+2] == b'\xff\xe2':  # APP2
                    length = struct.unpack('>H', jpeg_data[offset+2:offset+4])[0]
                    if jpeg_data[offset+4:offset+12] == b'AFCP\x00\x00\x00\x00':
                        afcp_pos = offset
                        afcp_length = length
                        break
                    offset += 2 + length
                elif jpeg_data[offset] == 0xFF and jpeg_data[offset+1] >= 0xE0 and jpeg_data[offset+1] <= 0xEF:
                    length = struct.unpack('>H', jpeg_data[offset+2:offset+4])[0]
                    offset += 2 + length
                else:
                    offset += 1
            
            # Insert or replace AFCP segment
            if afcp_pos != -1:
                # Replace existing segment
                new_jpeg = (
                    jpeg_data[:afcp_pos] +
                    afcp_segment +
                    jpeg_data[afcp_pos + afcp_length:]
                )
            else:
                # Insert new segment
                insert_pos = 2
                if len(jpeg_data) > 4:
                    pos = 2
                    while pos < len(jpeg_data) - 4:
                        if jpeg_data[pos] == 0xFF and jpeg_data[pos+1] >= 0xE0 and jpeg_data[pos+1] <= 0xEF:
                            length = struct.unpack('>H', jpeg_data[pos+2:pos+4])[0]
                            insert_pos = pos + 2 + length
                            break
                        pos += 1
                
                new_jpeg = (
                    jpeg_data[:insert_pos] +
                    afcp_segment +
                    jpeg_data[insert_pos:]
                )
            
            with open(output_path, 'wb') as f:
                f.write(new_jpeg)
                
        except Exception as e:
            raise MetadataWriteError(f"Failed to write AFCP metadata: {str(e)}")
    
    def _build_afcp_segment(self, metadata: Dict[str, Any]) -> bytes:
        """
        Build AFCP APP2 segment.
        
        Args:
            metadata: AFCP metadata dictionary
            
        Returns:
            APP2 segment bytes
        """
        # AFCP identifier
        segment_data = b'AFCP\x00\x00\x00\x00'
        
        # Build AFCP data (simplified - full implementation would parse AFCP structure)
        # For now, store as key-value pairs
        for key, value in metadata.items():
            key_bytes = key.encode('utf-8')
            value_bytes = str(value).encode('utf-8')
            segment_data += struct.pack('>H', len(key_bytes)) + key_bytes
            segment_data += struct.pack('>I', len(value_bytes)) + value_bytes
        
        segment_length = len(segment_data) + 2
        
        segment = (
            b'\xff\xe2' +  # APP2 marker
            struct.pack('>H', segment_length) +
            segment_data
        )
        
        return segment

