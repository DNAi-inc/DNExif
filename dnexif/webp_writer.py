# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
WebP format metadata writer

This module handles writing EXIF and XMP metadata to WebP files.
WebP stores metadata in chunks similar to PNG.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from dnexif.exceptions import MetadataWriteError
from dnexif.exif_writer import EXIFWriter
from dnexif.xmp_writer import XMPWriter


class WebPWriter:
    """
    Writes metadata to WebP files.
    
    WebP uses RIFF container format with chunks for metadata.
    EXIF and XMP can be stored in EXIF and XMP chunks.
    """
    
    # WebP chunk types
    CHUNK_VP8 = b'VP8 '  # VP8 image data
    CHUNK_VP8L = b'VP8L'  # VP8L image data
    CHUNK_VP8X = b'VP8X'  # Extended format
    CHUNK_EXIF = b'EXIF'  # EXIF data
    CHUNK_XMP = b'XMP '  # XMP data
    CHUNK_ICCP = b'ICCP'  # ICC profile
    CHUNK_ALPHA = b'ALPH'
    CHUNK_ANIM = b'ANIM'
    CHUNK_ANMF = b'ANMF'
    
    # VP8X feature flag bits
    FLAG_ANIMATION = 0x02
    FLAG_XMP = 0x04
    FLAG_EXIF = 0x08
    FLAG_ALPHA = 0x10
    FLAG_ICC = 0x20
    
    def __init__(self):
        """Initialize WebP writer."""
        self.exif_writer = EXIFWriter(exif_version='0300')
        self.xmp_writer = XMPWriter()
    
    def write_webp(
        self,
        original_data: bytes,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to a WebP file.
        
        Args:
            original_data: Original WebP file data
            metadata: Metadata dictionary to write
            output_path: Output file path
            
        Raises:
            MetadataWriteError: If writing fails
        """
        if not original_data.startswith(b'RIFF') or b'WEBP' not in original_data[:12]:
            raise MetadataWriteError("Invalid WebP file")
        
        try:
            # Parse WebP structure
            chunk_info = self._parse_webp_chunks(original_data)
            
            # Extract EXIF metadata
            exif_metadata = {
                k: v for k, v in metadata.items()
                if k.startswith('EXIF:') or k.startswith('IFD0:') or k.startswith('GPS:')
            }
            
            # Extract XMP metadata
            xmp_metadata = {
                k: v for k, v in metadata.items()
                if k.startswith('XMP:')
            }
            
            # Build new WebP file
            new_webp_data = self._build_webp_file(chunk_info, exif_metadata, xmp_metadata)
            
            # Write to output file
            with open(output_path, 'wb') as f:
                f.write(new_webp_data)
                
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to write WebP file: {str(e)}")
    
    def _parse_webp_chunks(self, webp_data: bytes) -> Dict[str, Any]:
        """
        Parse WebP chunks from file data.
        
        Args:
            webp_data: WebP file data
            
        Returns:
            Dictionary containing parsed chunk data and WebP characteristics
        """
        chunks: List[Tuple[bytes, bytes]] = []
        offset = 0
        
        info: Dict[str, Any] = {
            'chunks': chunks,
            'has_vp8x': False,
            'vp8x_data': None,
            'canvas_width': None,
            'canvas_height': None,
            'vp8x_flags': 0,
            'has_alpha_chunk': False,
            'has_anim_chunk': False,
            'has_icc_chunk': False,
        }
        
        # Check RIFF header
        if webp_data[offset:offset+4] != b'RIFF':
            return info
        
        offset += 4
        file_size = struct.unpack('<I', webp_data[offset:offset+4])[0]
        offset += 4
        
        # Check WEBP identifier
        if webp_data[offset:offset+4] != b'WEBP':
            return info
        
        offset += 4
        
        # Parse chunks
        while offset < len(webp_data) - 8:
            # Read chunk type (4 bytes)
            if offset + 4 > len(webp_data):
                break
            chunk_type = webp_data[offset:offset+4]
            offset += 4
            
            # Read chunk size (4 bytes, little-endian)
            if offset + 4 > len(webp_data):
                break
            chunk_size = struct.unpack('<I', webp_data[offset:offset+4])[0]
            offset += 4
            
            # Read chunk data
            if offset + chunk_size > len(webp_data):
                break
            chunk_data = webp_data[offset:offset+chunk_size]
            offset += chunk_size
            
            # Track specific chunk types and skip EXIF/XMP (to be rebuilt)
            if chunk_type == self.CHUNK_VP8X:
                info['has_vp8x'] = True
                info['vp8x_data'] = chunk_data
                if len(chunk_data) >= 10:
                    info['vp8x_flags'] = chunk_data[0]
                    width_minus_one = int.from_bytes(chunk_data[4:7], 'little')
                    height_minus_one = int.from_bytes(chunk_data[7:10], 'little')
                    info['canvas_width'] = width_minus_one + 1
                    info['canvas_height'] = height_minus_one + 1
            elif chunk_type == self.CHUNK_VP8:
                dims = self._extract_vp8_dimensions(chunk_data)
                if dims:
                    info['canvas_width'], info['canvas_height'] = dims
                chunks.append((chunk_type, chunk_data))
            elif chunk_type == self.CHUNK_VP8L:
                dims = self._extract_vp8l_dimensions(chunk_data)
                if dims:
                    info['canvas_width'], info['canvas_height'] = dims
                chunks.append((chunk_type, chunk_data))
            elif chunk_type == self.CHUNK_EXIF or chunk_type == self.CHUNK_XMP:
                # Skip existing metadata chunks; they'll be replaced
                pass
            else:
                if chunk_type == self.CHUNK_ALPHA:
                    info['has_alpha_chunk'] = True
                elif chunk_type in (self.CHUNK_ANIM, self.CHUNK_ANMF):
                    info['has_anim_chunk'] = True
                elif chunk_type == self.CHUNK_ICCP:
                    info['has_icc_chunk'] = True
                chunks.append((chunk_type, chunk_data))
            
            # Align to even boundary
            if chunk_size % 2 == 1:
                offset += 1
        
        return info
    
    def _build_webp_file(
        self,
        chunk_info: Dict[str, Any],
        exif_metadata: Dict[str, Any],
        xmp_metadata: Dict[str, Any]
    ) -> bytes:
        """
        Build a complete WebP file with metadata.
        
        Args:
            chunks: List of (chunk_type, chunk_data) tuples
            exif_metadata: EXIF metadata dictionary
            xmp_metadata: XMP metadata dictionary
            
        Returns:
            Complete WebP file as bytes
        """
        chunks = chunk_info['chunks']
        has_vp8x = chunk_info['has_vp8x']
        vp8x_data = chunk_info.get('vp8x_data')
        vp8x_flags = chunk_info.get('vp8x_flags', 0)
        canvas_width = chunk_info.get('canvas_width')
        canvas_height = chunk_info.get('canvas_height')
        
        exif_chunk_data = self._build_exif_chunk(exif_metadata) if exif_metadata else None
        xmp_chunk_data = self._build_xmp_chunk(xmp_metadata) if xmp_metadata else None
        has_metadata = bool(exif_chunk_data or xmp_chunk_data)
        
        final_chunks: List[Tuple[bytes, bytes]] = []
        
        # Ensure VP8X chunk exists if metadata is present (required by spec)
        if has_vp8x:
            vp8x_payload = bytearray(vp8x_data or b'')
            if len(vp8x_payload) < 10:
                raise MetadataWriteError("Malformed VP8X chunk")
            flags = vp8x_payload[0]
        elif has_metadata:
            if not canvas_width or not canvas_height:
                raise MetadataWriteError("Unable to determine canvas size for VP8X chunk")
            flags = 0
            if chunk_info.get('has_alpha_chunk'):
                flags |= self.FLAG_ALPHA
            if chunk_info.get('has_anim_chunk'):
                flags |= self.FLAG_ANIMATION
            if chunk_info.get('has_icc_chunk'):
                flags |= self.FLAG_ICC
            vp8x_payload = bytearray(self._build_vp8x_payload(flags, canvas_width, canvas_height))
            has_vp8x = True
        else:
            vp8x_payload = None
            flags = 0
        
        if has_vp8x and vp8x_payload is not None:
            if exif_chunk_data:
                flags |= self.FLAG_EXIF
            if xmp_chunk_data:
                flags |= self.FLAG_XMP
            vp8x_payload[0] = flags
            final_chunks.append((self.CHUNK_VP8X, bytes(vp8x_payload)))
            
            if exif_chunk_data:
                final_chunks.append((self.CHUNK_EXIF, exif_chunk_data))
            if xmp_chunk_data:
                final_chunks.append((self.CHUNK_XMP, xmp_chunk_data))
        else:
            # No VP8X and no metadata; nothing to add before existing chunks
            pass
        
        # Append original chunks (excluding VP8X/metadata which were removed earlier)
        final_chunks.extend(chunks)
        
        webp_data = bytearray()
        webp_data.extend(b'RIFF')
        webp_data.extend(b'\x00\x00\x00\x00')
        webp_data.extend(b'WEBP')
        
        for chunk_type, chunk_data in final_chunks:
            webp_data.extend(self._write_chunk(chunk_type, chunk_data))
        
        file_size = len(webp_data) - 8
        webp_data[4:8] = struct.pack('<I', file_size)
        return bytes(webp_data)
    
    def _build_exif_chunk(self, exif_metadata: Dict[str, Any]) -> Optional[bytes]:
        """
        Build EXIF chunk data from EXIF metadata.
        
        Args:
            exif_metadata: EXIF metadata dictionary
            
        Returns:
            EXIF chunk data bytes, or None if no metadata
        """
        if not exif_metadata:
            return None
        
        # Build EXIF segment (TIFF structure)
        endian = '<'
        exif_version = '0300'
        if 'EXIF:ExifVersion' in exif_metadata:
            exif_version = str(exif_metadata.get('EXIF:ExifVersion', '0300'))
        
        exif_writer = EXIFWriter(endian=endian, exif_version=exif_version)
        
        # Build TIFF structure
        tiff_header = exif_writer._build_tiff_header()
        ifd0_tags, ifd0_data = exif_writer._build_ifd(exif_metadata, ifd_type='IFD0')
        exif_ifd_tags, exif_ifd_data = exif_writer._build_ifd(exif_metadata, ifd_type='EXIF')
        gps_ifd_tags, gps_ifd_data = exif_writer._build_ifd(exif_metadata, ifd_type='GPS')
        
        # Ensure ExifVersion is present
        has_exif_version = any(tag.get('id') == 0x9000 for tag in exif_ifd_tags)
        if not has_exif_version:
            version_bytes = exif_version.encode('ascii') + b'\x00'
            exif_version_tag = {
                'id': 0x9000,
                'type': 2,  # ASCII
                'count': len(version_bytes),
                'value': len(exif_ifd_data),
                'data': b''
            }
            exif_ifd_tags.append(exif_version_tag)
            exif_ifd_data = exif_ifd_data + version_bytes
        
        # Calculate offsets
        base_offset = len(tiff_header)
        ifd0_offset = base_offset
        ifd0_data_offset = ifd0_offset + 2 + (len(ifd0_tags) * 12) + 4
        exif_ifd_offset = ifd0_data_offset + len(ifd0_data)
        exif_ifd_data_offset = exif_ifd_offset + 2 + (len(exif_ifd_tags) * 12) + 4
        gps_ifd_offset = exif_ifd_data_offset + len(exif_ifd_data)
        gps_ifd_data_offset = gps_ifd_offset + 2 + (len(gps_ifd_tags) * 12) + 4
        
        # Build complete EXIF data
        exif_data = bytearray()
        exif_data.extend(tiff_header)
        exif_data.extend(exif_writer._write_ifd(ifd0_tags, ifd0_data, ifd0_data_offset))
        exif_data.extend(ifd0_data)
        
        if exif_ifd_tags:
            exif_data.extend(exif_writer._write_ifd(exif_ifd_tags, exif_ifd_data, exif_ifd_data_offset))
            exif_data.extend(exif_ifd_data)
        
        if gps_ifd_tags:
            exif_data.extend(exif_writer._write_ifd(gps_ifd_tags, gps_ifd_data, gps_ifd_data_offset))
            exif_data.extend(gps_ifd_data)
        
        return bytes(exif_data)
    
    def _build_xmp_chunk(self, xmp_metadata: Dict[str, Any]) -> Optional[bytes]:
        """
        Build XMP chunk data from XMP metadata.
        
        Args:
            xmp_metadata: XMP metadata dictionary
            
        Returns:
            XMP chunk data bytes, or None if no metadata
        """
        if not xmp_metadata:
            return None
        
        # Build XMP packet
        xmp_packet = self.xmp_writer.build_xmp_packet(xmp_metadata)
        
        # XMP chunk is just the XMP packet
        return xmp_packet.encode('utf-8')
    
    def _write_chunk(self, chunk_type: bytes, chunk_data: bytes) -> bytes:
        """
        Write a WebP chunk.
        
        Args:
            chunk_type: Chunk type (4 bytes)
            chunk_data: Chunk data
            
        Returns:
            Complete chunk bytes (type + size + data)
        """
        chunk = bytearray()
        
        # Chunk type
        chunk.extend(chunk_type)
        
        # Chunk size (4 bytes, little-endian)
        chunk.extend(struct.pack('<I', len(chunk_data)))
        
        # Chunk data
        chunk.extend(chunk_data)
        
        # Align to even boundary
        if len(chunk_data) % 2 == 1:
            chunk.append(0)
        
        return bytes(chunk)

    @staticmethod
    def _extract_vp8_dimensions(chunk_data: bytes) -> Optional[Tuple[int, int]]:
        """Extract canvas width/height from a VP8 chunk."""
        if len(chunk_data) < 10:
            return None
        # Start code 0x9d 0x01 0x2a per VP8 spec
        if chunk_data[3:6] != b'\x9d\x01\x2a':
            return None
        raw_width = struct.unpack('<H', chunk_data[6:8])[0]
        raw_height = struct.unpack('<H', chunk_data[8:10])[0]
        width = raw_width & 0x3FFF
        height = raw_height & 0x3FFF
        if width == 0 or height == 0:
            return None
        return width, height

    @staticmethod
    def _extract_vp8l_dimensions(chunk_data: bytes) -> Optional[Tuple[int, int]]:
        """Extract canvas width/height from a VP8L chunk."""
        if len(chunk_data) < 5:
            return None
        if chunk_data[0] != 0x2f:
            return None
        bits = struct.unpack('<I', chunk_data[1:5])[0]
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        if width == 0 or height == 0:
            return None
        return width, height

    def _build_vp8x_payload(self, flags: int, width: int, height: int) -> bytes:
        """Build a VP8X chunk payload with the provided flags and canvas size."""
        if width <= 0 or height <= 0:
            raise MetadataWriteError("Invalid canvas dimensions for VP8X chunk")
        payload = bytearray(10)
        payload[0] = flags & 0xFF
        payload[1:4] = b'\x00\x00\x00'
        payload[4:7] = (width - 1).to_bytes(3, 'little')
        payload[7:10] = (height - 1).to_bytes(3, 'little')
        return bytes(payload)

