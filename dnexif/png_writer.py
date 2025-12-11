# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
PNG metadata writer

This module handles writing EXIF and XMP metadata to PNG files.
PNG 1.2.1+ supports EXIF in eXIf chunks, and XMP in iTXt chunks.

Copyright 2025 DNAi inc.
"""

import struct
import zlib
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from dnexif.exceptions import MetadataWriteError
from dnexif.exif_writer import EXIFWriter
from dnexif.xmp_writer import XMPWriter


class PNGWriter:
    """
    Writes metadata to PNG files.
    
    PNG 1.2.1+ supports EXIF in eXIf chunks (standardized in 2017).
    XMP can be stored in iTXt chunks.
    """
    
    # PNG chunk types
    CHUNK_IHDR = b'IHDR'
    CHUNK_EXIF = b'eXIf'  # EXIF data chunk (PNG 1.2.1+)
    CHUNK_ITXT = b'iTXt'  # International text chunk (for XMP)
    CHUNK_TEXT = b'tEXt'  # Text chunk (for Stable Diffusion and other text metadata)
    CHUNK_ZTXT = b'zTXt'  # Compressed text chunk
    CHUNK_IEND = b'IEND'
    
    def __init__(self):
        """Initialize PNG writer."""
        self.exif_writer = EXIFWriter(exif_version='0300')  # Use EXIF 3.0 for UTF-8
        self.xmp_writer = XMPWriter()
    
    def write_png(
        self,
        original_data: bytes,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to a PNG file.
        
        Args:
            original_data: Original PNG file data
            metadata: Metadata dictionary to write
            output_path: Output file path
            
        Raises:
            MetadataWriteError: If writing fails
        """
        if not original_data.startswith(b'\x89PNG\r\n\x1a\n'):
            raise MetadataWriteError("Invalid PNG file")
        
        try:
            # Parse original PNG structure
            chunks = self._parse_png_chunks(original_data)
            
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
            
            # Extract Stable Diffusion metadata (PNG:StableDiffusion:* tags)
            stable_diffusion_metadata = {
                k: v for k, v in metadata.items()
                if k.startswith('PNG:StableDiffusion:')
            }
            
            # Extract PNG text metadata (PNG:Text:* tags)
            png_text_metadata = {
                k: v for k, v in metadata.items()
                if k.startswith('PNG:Text:')
            }
            
            # Build new PNG file
            new_png_data = self._build_png_file(chunks, exif_metadata, xmp_metadata, stable_diffusion_metadata, png_text_metadata)
            
            # Write to output file
            with open(output_path, 'wb') as f:
                f.write(new_png_data)
                
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to write PNG file: {str(e)}")
    
    def _parse_png_chunks(self, png_data: bytes) -> List[Tuple[bytes, bytes]]:
        """
        Parse PNG chunks from file data.
        
        Args:
            png_data: PNG file data
            
        Returns:
            List of (chunk_type, chunk_data) tuples
        """
        chunks = []
        offset = 8  # Skip PNG signature
        
        while offset < len(png_data) - 8:
            # Read chunk length (4 bytes, big-endian)
            if offset + 4 > len(png_data):
                break
            chunk_length = struct.unpack('>I', png_data[offset:offset + 4])[0]
            offset += 4
            
            # Read chunk type (4 bytes)
            if offset + 4 > len(png_data):
                break
            chunk_type = png_data[offset:offset + 4]
            offset += 4
            
            # Read chunk data
            if offset + chunk_length > len(png_data):
                break
            chunk_data = png_data[offset:offset + chunk_length]
            offset += chunk_length
            
            # Read CRC (4 bytes) - we'll recalculate it
            if offset + 4 > len(png_data):
                break
            offset += 4
            
            # Store chunk (excluding eXIf, iTXt, and tEXt chunks that we'll replace)
            # Note: We preserve existing tEXt chunks unless they're being modified
            if chunk_type not in (self.CHUNK_EXIF, self.CHUNK_ITXT):
                chunks.append((chunk_type, chunk_data))
            
            # Stop at IEND chunk
            if chunk_type == self.CHUNK_IEND:
                break
        
        return chunks
    
    def _build_png_file(
        self,
        chunks: List[Tuple[bytes, bytes]],
        exif_metadata: Dict[str, Any],
        xmp_metadata: Dict[str, Any],
        stable_diffusion_metadata: Dict[str, Any] = None,
        png_text_metadata: Dict[str, Any] = None
    ) -> bytes:
        """
        Build a complete PNG file with metadata.
        
        Args:
            chunks: List of (chunk_type, chunk_data) tuples
            exif_metadata: EXIF metadata dictionary
            xmp_metadata: XMP metadata dictionary
            
        Returns:
            Complete PNG file as bytes
        """
        png_data = bytearray()
        
        # PNG signature
        png_data.extend(b'\x89PNG\r\n\x1a\n')
        
        # Insert chunks in correct order:
        # 1. IHDR (must be first)
        # 2. eXIf (EXIF data) - after IHDR, before IDAT
        # 3. iTXt (XMP data) - after IHDR, before IDAT
        # 4. Other chunks (IDAT, etc.)
        # 5. IEND (must be last)
        
        ihdr_added = False
        idat_started = False
        
        for chunk_type, chunk_data in chunks:
            # Add IHDR first
            if not ihdr_added:
                if chunk_type == self.CHUNK_IHDR:
                    png_data.extend(self._write_chunk(chunk_type, chunk_data))
                    ihdr_added = True
                    
                    # Add eXIf chunk after IHDR if we have EXIF data
                    if exif_metadata:
                        exif_chunk_data = self._build_exif_chunk(exif_metadata)
                        if exif_chunk_data:
                            png_data.extend(self._write_chunk(self.CHUNK_EXIF, exif_chunk_data))
                    
                    # Add iTXt chunk for XMP after IHDR if we have XMP data
                    if xmp_metadata:
                        xmp_chunk_data = self._build_xmp_chunk(xmp_metadata)
                        if xmp_chunk_data:
                            png_data.extend(self._write_chunk(self.CHUNK_ITXT, xmp_chunk_data))
                    
                    # Add tEXt chunks for Stable Diffusion metadata and other text metadata
                    if stable_diffusion_metadata is not None and stable_diffusion_metadata:
                        # Write Stable Diffusion parameters as tEXt chunk with keyword "parameters"
                        if 'PNG:StableDiffusion:Parameters' in stable_diffusion_metadata:
                            params_text = str(stable_diffusion_metadata['PNG:StableDiffusion:Parameters'])
                            text_chunk_data = self._build_text_chunk('parameters', params_text)
                            if text_chunk_data:
                                png_data.extend(self._write_chunk(self.CHUNK_TEXT, text_chunk_data))
                    
                    # Add other PNG text metadata as tEXt chunks
                    if png_text_metadata is not None and png_text_metadata:
                        for tag_name, text_value in png_text_metadata.items():
                            # Extract keyword from tag name (PNG:Text:Keyword -> Keyword)
                            keyword = tag_name.replace('PNG:Text:', '')
                            if keyword and text_value:
                                text_chunk_data = self._build_text_chunk(keyword, str(text_value))
                                if text_chunk_data:
                                    png_data.extend(self._write_chunk(self.CHUNK_TEXT, text_chunk_data))
                else:
                    # IHDR not found, add it first
                    raise MetadataWriteError("PNG file missing IHDR chunk")
            else:
                # Write chunk (including IDAT, IEND, etc.)
                png_data.extend(self._write_chunk(chunk_type, chunk_data))
        
        return bytes(png_data)
    
    def _build_exif_chunk(self, exif_metadata: Dict[str, Any]) -> Optional[bytes]:
        """
        Build eXIf chunk data from EXIF metadata.
        
        The eXIf chunk contains EXIF data directly (TIFF structure).
        
        Args:
            exif_metadata: EXIF metadata dictionary
            
        Returns:
            eXIf chunk data bytes, or None if no metadata
        """
        if not exif_metadata:
            return None
        
        # Build EXIF segment (without JPEG APP1 wrapper)
        # Get endianness from existing metadata or default to little-endian
        endian = '<'
        if 'EXIF:ExifVersion' in exif_metadata:
            exif_version = str(exif_metadata.get('EXIF:ExifVersion', '0300'))
        else:
            exif_version = '0300'  # Default to EXIF 3.0
        
        exif_writer = EXIFWriter(endian=endian, exif_version=exif_version)
        
        # Build TIFF structure (without APP1 header)
        tiff_header = exif_writer._build_tiff_header()
        
        # Build IFDs
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
        Build iTXt chunk data for XMP metadata.
        
        iTXt chunk format:
        - Keyword (null-terminated): "XML:com.adobe.xmp"
        - Compression flag (1 byte): 0 = uncompressed, 1 = compressed
        - Compression method (1 byte): 0 = zlib
        - Language tag (null-terminated): usually empty
        - Translated keyword (null-terminated): usually empty
        - Text (XMP packet)
        
        Args:
            xmp_metadata: XMP metadata dictionary
            
        Returns:
            iTXt chunk data bytes, or None if no metadata
        """
        if not xmp_metadata:
            return None
        
        # Build XMP packet
        xmp_packet = self.xmp_writer.build_xmp_packet(xmp_metadata)
        
        # Build iTXt chunk data
        chunk_data = bytearray()
        
        # Keyword: "XML:com.adobe.xmp"
        chunk_data.extend(b'XML:com.adobe.xmp\x00')
        
        # Compression flag: 1 (compressed)
        chunk_data.append(1)
        
        # Compression method: 0 (zlib)
        chunk_data.append(0)
        
        # Language tag: empty
        chunk_data.append(0)
        
        # Translated keyword: empty
        chunk_data.append(0)
        
        # Compress XMP packet
        # xmp_packet is already bytes
        xmp_bytes = xmp_packet if isinstance(xmp_packet, bytes) else xmp_packet.encode('utf-8')
        compressed_xmp = zlib.compress(xmp_bytes)
        chunk_data.extend(compressed_xmp)
        
        return bytes(chunk_data)
    
    def _build_text_chunk(self, keyword: str, text: str) -> Optional[bytes]:
        """
        Build tEXt chunk data for text metadata.
        
        tEXt chunk format:
        - Keyword (null-terminated): e.g., "parameters", "Comment"
        - Text: UTF-8 encoded text
        
        Args:
            keyword: Chunk keyword
            text: Text content
            
        Returns:
            tEXt chunk data bytes, or None if invalid
        """
        if not keyword or not text:
            return None
        
        chunk_data = bytearray()
        
        # Keyword (null-terminated)
        chunk_data.extend(keyword.encode('ascii', errors='ignore'))
        chunk_data.append(0)  # Null terminator
        
        # Text (UTF-8)
        chunk_data.extend(text.encode('utf-8', errors='ignore'))
        
        return bytes(chunk_data)
    
    def _write_chunk(self, chunk_type: bytes, chunk_data: bytes) -> bytes:
        """
        Write a PNG chunk with CRC.
        
        Args:
            chunk_type: Chunk type (4 bytes)
            chunk_data: Chunk data
            
        Returns:
            Complete chunk bytes (length + type + data + CRC)
        """
        import zlib
        
        chunk = bytearray()
        
        # Length (4 bytes, big-endian)
        chunk.extend(struct.pack('>I', len(chunk_data)))
        
        # Chunk type
        chunk.extend(chunk_type)
        
        # Chunk data
        chunk.extend(chunk_data)
        
        # Calculate CRC (CRC-32 of chunk type + data)
        crc_data = chunk_type + chunk_data
        crc = zlib.crc32(crc_data) & 0xffffffff
        chunk.extend(struct.pack('>I', crc))
        
        return bytes(chunk)

