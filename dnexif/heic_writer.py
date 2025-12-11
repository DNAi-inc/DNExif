# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
HEIC/HEIF metadata writer

This module provides metadata writing for HEIC/HEIF files.
HEIC files use ISOBMFF container format (similar to MP4).

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from dnexif.exceptions import MetadataWriteError
from dnexif.xmp_writer import XMPWriter
from dnexif.exif_writer import EXIFWriter


class HEICWriter:
    """
    Writer for HEIC/HEIF metadata.
    
    HEIC files use ISOBMFF container format. Metadata is stored in:
    - meta box (metadata container)
    - EXIF box (EXIF data)
    - XMP box (XMP data in UUID box)
    """
    
    def __init__(self, exif_version: str = '0300'):
        """
        Initialize HEIC writer.
        
        Args:
            exif_version: EXIF version to use (default: '0300' for EXIF 3.0)
        """
        self.exif_writer = EXIFWriter(exif_version=exif_version)
        self.xmp_writer = XMPWriter()
    
    def write_heic(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to HEIC file.
        
        Args:
            file_path: Path to input HEIC file
            metadata: Dictionary of metadata to write
            output_path: Path to output HEIC file
            
        Raises:
            MetadataWriteError: If writing fails
        """
        try:
            with open(file_path, 'rb') as f:
                heic_data = f.read()
            
            if len(heic_data) < 8:
                raise MetadataWriteError("Invalid HEIC file: too short")
            
            # Check for ftyp box
            if heic_data[4:8] != b'ftyp':
                ftyp_pos = heic_data.find(b'ftyp')
                if ftyp_pos == -1:
                    raise MetadataWriteError("Invalid HEIC file: missing ftyp box")
            
            # Separate metadata by type
            exif_metadata = {}
            xmp_metadata = {}
            
            for key, value in metadata.items():
                if key.startswith('EXIF:'):
                    exif_metadata[key[5:]] = value
                elif key.startswith('XMP:'):
                    xmp_metadata[key[4:]] = value
                elif ':' not in key:
                    # Default to EXIF for unknown prefixes
                    exif_metadata[key] = value
            
            # Write EXIF metadata if present
            if exif_metadata:
                heic_data = self._write_exif_box(heic_data, exif_metadata)
            
            # Write XMP metadata if present
            if xmp_metadata:
                heic_data = self._write_xmp_box(heic_data, xmp_metadata)
            
            # Write output file
            with open(output_path, 'wb') as f:
                f.write(heic_data)
                
        except Exception as e:
            raise MetadataWriteError(f"Failed to write HEIC metadata: {str(e)}")
    
    def _write_exif_box(self, heic_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """
        Write EXIF data to HEIC file in exif box.
        
        Args:
            heic_data: Original HEIC data
            metadata: EXIF metadata dictionary
            
        Returns:
            Modified HEIC data with EXIF box
        """
        try:
            # Build EXIF data using EXIF writer
            # For HEIC, we need to create a TIFF-like structure
            exif_bytes = self.exif_writer.build_exif_segment(metadata)
            
            # Find or create meta box
            meta_box_pos = self._find_box(heic_data, b'meta')
            if meta_box_pos == -1:
                # Create meta box (simplified - would need proper box structure)
                # For now, append as new box
                exif_box = self._create_box(b'exif', exif_bytes)
                # Insert after ftyp box
                ftyp_end = self._find_box_end(heic_data, b'ftyp')
                if ftyp_end != -1:
                    return heic_data[:ftyp_end] + exif_box + heic_data[ftyp_end:]
            
            # Find exif box in meta box
            exif_box_pos = self._find_box(heic_data, b'exif', meta_box_pos)
            if exif_box_pos != -1:
                # Update existing exif box
                exif_box_end = self._find_box_end(heic_data, b'exif', exif_box_pos)
                if exif_box_end != -1:
                    new_exif_box = self._create_box(b'exif', exif_bytes)
                    return (
                        heic_data[:exif_box_pos] +
                        new_exif_box +
                        heic_data[exif_box_end:]
                    )
            
            # Add new exif box to meta box
            meta_box_end = self._find_box_end(heic_data, b'meta', meta_box_pos)
            if meta_box_end != -1:
                exif_box = self._create_box(b'exif', exif_bytes)
                # Update meta box size
                meta_size = struct.unpack('>I', heic_data[meta_box_pos:meta_box_pos+4])[0]
                new_meta_size = meta_size + len(exif_box)
                new_heic = (
                    heic_data[:meta_box_pos] +
                    struct.pack('>I', new_meta_size) +
                    heic_data[meta_box_pos+4:meta_box_end] +
                    exif_box +
                    heic_data[meta_box_end:]
                )
                return new_heic
            
            # Fallback: append exif box
            exif_box = self._create_box(b'exif', exif_bytes)
            return heic_data + exif_box
            
        except Exception as e:
            raise MetadataWriteError(f"Failed to write EXIF box: {str(e)}")
    
    def _write_xmp_box(self, heic_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """
        Write XMP data to HEIC file in UUID box.
        
        Args:
            heic_data: Original HEIC data
            metadata: XMP metadata dictionary
            
        Returns:
            Modified HEIC data with XMP UUID box
        """
        try:
            # Generate XMP packet (already returns bytes)
            xmp_packet = self.xmp_writer.build_xmp_packet(metadata)
            # build_xmp_packet already returns bytes, no need to encode
            xmp_bytes = xmp_packet if isinstance(xmp_packet, bytes) else xmp_packet.encode('utf-8')
            
            # XMP UUID: B14BF8BD083D4B43A5D8208A36F02B8
            xmp_uuid = bytes.fromhex('B14BF8BD083D4B43A5D8208A36F02B8')
            
            # Find or create meta box
            meta_box_pos = self._find_box(heic_data, b'meta')
            if meta_box_pos == -1:
                # Create meta box and add XMP UUID box
                uuid_box = self._create_uuid_box(xmp_uuid, xmp_bytes)
                ftyp_end = self._find_box_end(heic_data, b'ftyp')
                if ftyp_end != -1:
                    return heic_data[:ftyp_end] + uuid_box + heic_data[ftyp_end:]
            
            # Find existing XMP UUID box
            uuid_box_pos = self._find_uuid_box(heic_data, xmp_uuid, meta_box_pos)
            if uuid_box_pos != -1:
                # Update existing UUID box
                uuid_box_end = self._find_box_end(heic_data, b'uuid', uuid_box_pos)
                if uuid_box_end != -1:
                    new_uuid_box = self._create_uuid_box(xmp_uuid, xmp_bytes)
                    return (
                        heic_data[:uuid_box_pos] +
                        new_uuid_box +
                        heic_data[uuid_box_end:]
                    )
            
            # Add new XMP UUID box to meta box
            meta_box_end = self._find_box_end(heic_data, b'meta', meta_box_pos)
            if meta_box_end != -1:
                uuid_box = self._create_uuid_box(xmp_uuid, xmp_bytes)
                # Update meta box size
                meta_size = struct.unpack('>I', heic_data[meta_box_pos:meta_box_pos+4])[0]
                new_meta_size = meta_size + len(uuid_box)
                new_heic = (
                    heic_data[:meta_box_pos] +
                    struct.pack('>I', new_meta_size) +
                    heic_data[meta_box_pos+4:meta_box_end] +
                    uuid_box +
                    heic_data[meta_box_end:]
                )
                return new_heic
            
            # Fallback: append UUID box
            uuid_box = self._create_uuid_box(xmp_uuid, xmp_bytes)
            return heic_data + uuid_box
            
        except Exception as e:
            raise MetadataWriteError(f"Failed to write XMP box: {str(e)}")
    
    def _find_box(self, data: bytes, box_type: bytes, start_pos: int = 0) -> int:
        """Find box of given type in ISOBMFF data."""
        pos = start_pos
        while pos < len(data) - 8:
            if pos + 8 > len(data):
                break
            size = struct.unpack('>I', data[pos:pos+4])[0]
            box = data[pos+4:pos+8]
            if box == box_type:
                return pos
            if size == 0 or size > len(data) - pos:
                break
            pos += size
        return -1
    
    def _find_box_end(self, data: bytes, box_type: bytes, start_pos: int = 0) -> int:
        """Find end position of box."""
        box_pos = self._find_box(data, box_type, start_pos)
        if box_pos == -1:
            return -1
        size = struct.unpack('>I', data[box_pos:box_pos+4])[0]
        if size == 0:
            return len(data)
        return box_pos + size
    
    def _find_uuid_box(self, data: bytes, uuid: bytes, start_pos: int = 0) -> int:
        """Find UUID box with specific UUID."""
        pos = start_pos
        while pos < len(data) - 24:
            if pos + 24 > len(data):
                break
            size = struct.unpack('>I', data[pos:pos+4])[0]
            box = data[pos+4:pos+8]
            if box == b'uuid':
                box_uuid = data[pos+8:pos+24]
                if box_uuid == uuid:
                    return pos
            if size == 0 or size > len(data) - pos:
                break
            pos += size
        return -1
    
    def _create_box(self, box_type: bytes, data: bytes) -> bytes:
        """Create ISOBMFF box."""
        box_size = 8 + len(data)
        return struct.pack('>I', box_size) + box_type + data
    
    def _create_uuid_box(self, uuid: bytes, data: bytes) -> bytes:
        """Create UUID box."""
        box_size = 24 + len(data)
        return struct.pack('>I', box_size) + b'uuid' + uuid + data

