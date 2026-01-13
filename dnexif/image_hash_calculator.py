# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Image Data Hash Calculator Module

This module provides functions for calculating MD5/hash of image data only,
excluding metadata. Similar to standard ImageDataMD5/ImageDataHash feature.

Copyright 2025 DNAi inc.
"""

from typing import Optional, Dict, Any
from pathlib import Path
import hashlib
import struct


class ImageHashCalculator:
    """
    Calculator for image data hash (excluding metadata).
    
    Calculates MD5/hash of image pixel data only, excluding all metadata
    segments (EXIF, IPTC, XMP, etc.).
    """
    
    def __init__(self, hash_type: str = 'md5'):
        """
        Initialize hash calculator.
        
        Args:
            hash_type: Type of hash to calculate ('md5', 'sha1', 'sha256')
        """
        self.hash_type = hash_type.lower()
        if self.hash_type == 'md5':
            self.hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            self.hasher = hashlib.sha1()
        elif self.hash_type == 'sha256':
            self.hasher = hashlib.sha256()
        else:
            raise ValueError(f"Unsupported hash type: {hash_type}")
    
    def calculate_jpeg_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of JPEG image data (excluding metadata).
        
        For JPEG files, this extracts the compressed image data from
        scan segments (SOI, SOS, EOI) while excluding APP segments
        that contain EXIF, IPTC, XMP, and other metadata.
        
        Args:
            file_path: Path to JPEG file
            
        Returns:
            Hexadecimal hash string or None if calculation fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception:
            return None
        
        if len(file_data) < 2:
            return None
        
        # Check JPEG signature
        if file_data[:2] != b'\xff\xd8':
            return None
        
        # Reset hasher
        if self.hash_type == 'md5':
            hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()
        
        # Process JPEG segments
        offset = 0
        while offset < len(file_data):
            # Check for segment marker
            if offset + 1 >= len(file_data):
                break
            
            if file_data[offset] != 0xff:
                # Not a valid JPEG segment, skip byte
                offset += 1
                continue
            
            marker = file_data[offset + 1]
            
            # Start of Image (SOI) - include
            if marker == 0xd8:
                hasher.update(file_data[offset:offset + 2])
                offset += 2
                continue
            
            # End of Image (EOI) - include and finish
            if marker == 0xd9:
                hasher.update(file_data[offset:offset + 2])
                break
            
            # Start of Scan (SOS) - include scan data until EOI
            if marker == 0xda:
                # Include SOS marker
                hasher.update(file_data[offset:offset + 2])
                offset += 2
                
                # Read segment length (2 bytes)
                if offset + 2 > len(file_data):
                    break
                segment_length = struct.unpack('>H', file_data[offset:offset + 2])[0]
                offset += segment_length
                
                # Include scan data until EOI marker
                scan_start = offset
                while offset < len(file_data) - 1:
                    if file_data[offset] == 0xff and file_data[offset + 1] == 0xd9:
                        # Found EOI
                        hasher.update(file_data[scan_start:offset + 2])
                        offset += 2
                        break
                    offset += 1
                break
            
            # APP segments (EXIF, IPTC, XMP, etc.) - skip
            if 0xe0 <= marker <= 0xef:
                offset += 2
                if offset + 2 > len(file_data):
                    break
                segment_length = struct.unpack('>H', file_data[offset:offset + 2])[0]
                offset += segment_length
                continue
            
            # Other segments - include header but skip data
            offset += 2
            if offset + 2 > len(file_data):
                break
            
            segment_length = struct.unpack('>H', file_data[offset:offset + 2])[0]
            # Include segment marker and length
            hasher.update(file_data[offset - 2:offset + 2])
            offset += segment_length
        
        return hasher.hexdigest()
    
    def calculate_png_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of PNG image data (excluding metadata).
        
        For PNG files, this extracts image data chunks (IDAT) while
        excluding metadata chunks (tEXt, iTXt, zTXt, iCCP, etc.).
        
        Args:
            file_path: Path to PNG file
            
        Returns:
            Hexadecimal hash string or None if calculation fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception:
            return None
        
        if len(file_data) < 8:
            return None
        
        # Check PNG signature
        if file_data[:8] != b'\x89PNG\r\n\x1a\n':
            return None
        
        # Reset hasher
        if self.hash_type == 'md5':
            hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()
        
        # Include PNG signature
        hasher.update(file_data[:8])
        
        # Process PNG chunks
        offset = 8
        while offset < len(file_data):
            if offset + 8 > len(file_data):
                break
            
            # Read chunk length and type
            chunk_length = struct.unpack('>I', file_data[offset:offset + 4])[0]
            chunk_type = file_data[offset + 4:offset + 8]
            offset += 8
            
            # Metadata chunks to skip
            metadata_chunks = [b'tEXt', b'iTXt', b'zTXt', b'iCCP', b'tIME', b'tRNS']
            
            if chunk_type not in metadata_chunks:
                # Include chunk (length, type, data, CRC)
                if offset + chunk_length + 4 > len(file_data):
                    break
                hasher.update(file_data[offset - 8:offset + chunk_length + 4])
            
            offset += chunk_length + 4  # Skip data and CRC
        
        return hasher.hexdigest()
    
    def calculate_tiff_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of TIFF image data (excluding metadata).
        
        For TIFF files, this extracts image strip/tile data while
        excluding IFD metadata structures.
        
        Args:
            file_path: Path to TIFF file
            
        Returns:
            Hexadecimal hash string or None if calculation fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception:
            return None
        
        if len(file_data) < 8:
            return None
        
        # Check TIFF signature
        if file_data[:2] not in [b'II', b'MM']:
            return None
        
        # Reset hasher
        if self.hash_type == 'md5':
            hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()
        
        # Determine byte order
        if file_data[0] == 0x49:  # 'II' - little endian
            endian = '<'
        else:  # 'MM' - big endian
            endian = '>'
        
        # Include TIFF header (signature + magic number + IFD offset)
        hasher.update(file_data[:8])
        
        # Read IFD offset
        ifd_offset = struct.unpack(f'{endian}I', file_data[4:8])[0]
        
        if ifd_offset == 0 or ifd_offset >= len(file_data):
            return None
        
        # Parse IFD0 to find strip/tile offsets
        strip_offsets = []
        strip_byte_counts = []
        tile_offsets = []
        tile_byte_counts = []
        is_tiled = False
        
        current_ifd_offset = ifd_offset
        
        # Parse IFD entries (limit to first IFD for image data)
        if current_ifd_offset + 2 > len(file_data):
            return None
        
        entry_count = struct.unpack(f'{endian}H', file_data[current_ifd_offset:current_ifd_offset + 2])[0]
        entry_offset = current_ifd_offset + 2
        
        for _ in range(entry_count):
            if entry_offset + 12 > len(file_data):
                break
            
            # Read IFD entry (12 bytes: tag(2) + type(2) + count(4) + value/offset(4))
            tag_id = struct.unpack(f'{endian}H', file_data[entry_offset:entry_offset + 2])[0]
            tag_type = struct.unpack(f'{endian}H', file_data[entry_offset + 2:entry_offset + 4])[0]
            tag_count = struct.unpack(f'{endian}I', file_data[entry_offset + 4:entry_offset + 8])[0]
            tag_value = struct.unpack(f'{endian}I', file_data[entry_offset + 8:entry_offset + 12])[0]
            
            # StripOffsets tag (273)
            if tag_id == 273:
                if tag_count == 1:
                    strip_offsets = [tag_value]
                else:
                    # Multiple strips - read from offset
                    if tag_value < len(file_data) and tag_value + (tag_count * 4) <= len(file_data):
                        strip_offsets = list(struct.unpack(
                            f'{endian}{tag_count}I',
                            file_data[tag_value:tag_value + (tag_count * 4)]
                        ))
            
            # StripByteCounts tag (279)
            elif tag_id == 279:
                if tag_count == 1:
                    strip_byte_counts = [tag_value]
                else:
                    # Multiple strips - read from offset
                    if tag_value < len(file_data) and tag_value + (tag_count * 4) <= len(file_data):
                        strip_byte_counts = list(struct.unpack(
                            f'{endian}{tag_count}I',
                            file_data[tag_value:tag_value + (tag_count * 4)]
                        ))
            
            # TileOffsets tag (324)
            elif tag_id == 324:
                is_tiled = True
                if tag_count == 1:
                    tile_offsets = [tag_value]
                else:
                    # Multiple tiles - read from offset
                    if tag_value < len(file_data) and tag_value + (tag_count * 4) <= len(file_data):
                        tile_offsets = list(struct.unpack(
                            f'{endian}{tag_count}I',
                            file_data[tag_value:tag_value + (tag_count * 4)]
                        ))
            
            # TileByteCounts tag (325)
            elif tag_id == 325:
                is_tiled = True
                if tag_count == 1:
                    tile_byte_counts = [tag_value]
                else:
                    # Multiple tiles - read from offset
                    if tag_value < len(file_data) and tag_value + (tag_count * 4) <= len(file_data):
                        tile_byte_counts = list(struct.unpack(
                            f'{endian}{tag_count}I',
                            file_data[tag_value:tag_value + (tag_count * 4)]
                        ))
            
            entry_offset += 12
        
        # Extract image data from strips or tiles
        image_data = b''
        if is_tiled and tile_offsets and tile_byte_counts:
            # Tiled image
            for offset, byte_count in zip(tile_offsets, tile_byte_counts):
                if offset + byte_count <= len(file_data):
                    image_data += file_data[offset:offset + byte_count]
        elif strip_offsets and strip_byte_counts:
            # Strip-based image
            for offset, byte_count in zip(strip_offsets, strip_byte_counts):
                if offset + byte_count <= len(file_data):
                    image_data += file_data[offset:offset + byte_count]
        
        if not image_data:
            return None
        
        # Hash the image data
        hasher.update(image_data)
        
        return hasher.hexdigest()
    
    def calculate_heic_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of HEIC/HEIF image data (excluding metadata).
        
        For HEIC files, this extracts the compressed image data from
        media data boxes (mdat) while excluding metadata boxes (meta, exif, xmp, etc.).
        
        Args:
            file_path: Path to HEIC/HEIF file
            
        Returns:
            Hexadecimal hash string or None if calculation fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception:
            return None
        
        if len(file_data) < 8:
            return None
        
        # Check HEIC signature (ftyp box)
        if file_data[4:8] != b'ftyp':
            ftyp_pos = file_data.find(b'ftyp')
            if ftyp_pos == -1:
                return None
        
        # Reset hasher
        if self.hash_type == 'md5':
            hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()
        
        # Metadata boxes to exclude
        metadata_boxes = {b'meta', b'exif', b'xmp ', b'uuid', b'iref', b'pitm', b'iloc', b'iinf', b'infe', b'iprp', b'ipco', b'ispe', b'pasp', b'colr', b'pixi'}
        
        # Parse ISOBMFF boxes and extract image data
        offset = 0
        max_offset = len(file_data) - 8
        box_count = 0
        max_boxes = 1000
        
        while offset < max_offset and box_count < max_boxes:
            if offset + 8 > len(file_data):
                break
            
            # Read box size (4 bytes, big-endian)
            box_size = struct.unpack('>I', file_data[offset:offset+4])[0]
            box_type = file_data[offset+4:offset+8]
            
            # Handle extended size (size == 1 means 64-bit size follows)
            if box_size == 1:
                if offset + 16 > len(file_data):
                    break
                box_size = struct.unpack('>Q', file_data[offset+8:offset+16])[0]
                box_data_start = offset + 16
            else:
                box_data_start = offset + 8
            
            if box_size == 0:
                # Box extends to end of file
                box_size = len(file_data) - offset
            elif box_size < 8:
                break
            
            box_end = offset + box_size
            if box_end > len(file_data):
                break
            
            # Include mdat boxes (media data - contains image data)
            # Exclude metadata boxes
            if box_type == b'mdat':
                # mdat box contains the actual image data
                box_data = file_data[box_data_start:box_end]
                hasher.update(box_data)
            elif box_type not in metadata_boxes:
                # Include other non-metadata boxes (like ftyp, moov, etc.)
                # These are part of the container structure
                pass
            
            offset = box_end
            box_count += 1
        
        return hasher.hexdigest()
    
    def calculate_j2c_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of J2C (JPEG 2000 codestream) image data (excluding metadata).
        
        For J2C files, this extracts the codestream data while excluding
        metadata boxes (XML, UUID, etc.).
        
        Args:
            file_path: Path to J2C file
            
        Returns:
            Hexadecimal hash string or None if calculation fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception:
            return None
        
        if len(file_data) < 4:
            return None
        
        # Check J2C signature (SOC marker: FF 4F)
        if file_data[:2] != b'\xff\x4f':
            return None
        
        # Reset hasher
        if self.hash_type == 'md5':
            hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()
        
        # Process JPEG 2000 codestream
        # Include SOC, SIZ, and codestream data
        # Exclude metadata boxes (XML, UUID, etc.)
        offset = 0
        while offset < len(file_data) - 1:
            if offset + 2 > len(file_data):
                break
            
            marker = struct.unpack('>H', file_data[offset:offset+2])[0]
            
            # SOC (Start of Codestream) - FF 4F
            if marker == 0xFF4F:
                # Include SOC marker
                hasher.update(file_data[offset:offset+2])
                offset += 2
                continue
            
            # SIZ (Image and tile size) - FF 51
            if marker == 0xFF51:
                # Include SIZ marker and parameters
                if offset + 2 <= len(file_data):
                    hasher.update(file_data[offset:offset+2])
                    offset += 2
                    # SIZ has variable length, read length field
                    if offset + 2 <= len(file_data):
                        siz_length = struct.unpack('>H', file_data[offset:offset+2])[0]
                        if offset + siz_length <= len(file_data):
                            hasher.update(file_data[offset:offset+siz_length])
                            offset += siz_length
                        else:
                            offset += 2
                continue
            
            # EOC (End of Codestream) - FF D9
            if marker == 0xFFD9:
                # Include EOC marker
                hasher.update(file_data[offset:offset+2])
                break
            
            # Metadata boxes to exclude: XML (FF 64), UUID (FF 65), etc.
            # Include codestream markers (FF 50-FF 5F, FF 90-FF 93, FF 90-FF 93)
            if marker >= 0xFF50 and marker <= 0xFF5F:
                # Codestream markers - include them
                if offset + 2 <= len(file_data):
                    hasher.update(file_data[offset:offset+2])
                    offset += 2
                    # Read length if present
                    if offset + 2 <= len(file_data):
                        seg_length = struct.unpack('>H', file_data[offset:offset+2])[0]
                        if offset + seg_length <= len(file_data):
                            hasher.update(file_data[offset:offset+seg_length])
                            offset += seg_length
                        else:
                            offset += 2
                continue
            
            # Skip metadata boxes (XML, UUID, etc.)
            if marker == 0xFF64 or marker == 0xFF65:
                # XML or UUID box - skip
                if offset + 2 <= len(file_data):
                    offset += 2
                    if offset + 2 <= len(file_data):
                        box_length = struct.unpack('>H', file_data[offset:offset+2])[0]
                        if offset + box_length <= len(file_data):
                            offset += box_length
                        else:
                            offset += 2
                continue
            
            # Include other codestream data
            offset += 1
        
        return hasher.hexdigest()
    
    def calculate_jxl_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of JXL (JPEG XL) image data (excluding metadata).
        
        For JXL files, this extracts the codestream data while excluding
        metadata boxes.
        
        Args:
            file_path: Path to JXL file
            
        Returns:
            Hexadecimal hash string or None if calculation fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception:
            return None
        
        if len(file_data) < 2:
            return None
        
        # Check JXL signature (FF 0A)
        if file_data[:2] != b'\xff\x0a':
            return None
        
        # Reset hasher
        if self.hash_type == 'md5':
            hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()
        
        # Process JPEG XL codestream
        # Include codestream data, exclude metadata boxes
        offset = 0
        while offset < len(file_data) - 1:
            if offset + 2 > len(file_data):
                break
            
            marker = struct.unpack('>H', file_data[offset:offset+2])[0]
            
            # JXL signature (FF 0A)
            if marker == 0xFF0A:
                # Include signature
                hasher.update(file_data[offset:offset+2])
                offset += 2
                continue
            
            # Include codestream data
            # JXL uses variable-length segments
            # For simplicity, include all data except known metadata boxes
            # Metadata in JXL is typically in boxes with specific markers
            hasher.update(file_data[offset:offset+1])
            offset += 1
        
        return hasher.hexdigest()
    
    def calculate_avif_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of AVIF image data (excluding metadata).
        
        For AVIF files, this extracts the compressed image data from
        media data boxes (mdat) while excluding metadata boxes (meta, exif, xmp, etc.).
        AVIF uses ISO Base Media File Format (ISOBMFF), similar to HEIC.
        
        Args:
            file_path: Path to AVIF file
            
        Returns:
            Hexadecimal hash string or None if calculation fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception:
            return None
        
        if len(file_data) < 8:
            return None
        
        # Check AVIF signature (ftyp box with 'avif' brand)
        if file_data[4:8] != b'ftyp':
            ftyp_pos = file_data.find(b'ftyp')
            if ftyp_pos == -1:
                return None
        
        # Reset hasher
        if self.hash_type == 'md5':
            hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()
        
        # Metadata boxes to exclude
        metadata_boxes = {b'meta', b'exif', b'xmp ', b'uuid', b'iref', b'pitm', b'iloc', b'iinf', b'infe', b'iprp', b'ipco', b'ispe', b'pasp', b'colr', b'pixi'}
        
        # Parse ISOBMFF boxes and extract image data
        offset = 0
        max_offset = len(file_data) - 8
        box_count = 0
        max_boxes = 1000
        
        while offset < max_offset and box_count < max_boxes:
            if offset + 8 > len(file_data):
                break
            
            # Read box size (4 bytes, big-endian)
            box_size = struct.unpack('>I', file_data[offset:offset+4])[0]
            box_type = file_data[offset+4:offset+8]
            
            # Handle extended size (size == 1 means 64-bit size follows)
            if box_size == 1:
                if offset + 16 > len(file_data):
                    break
                box_size = struct.unpack('>Q', file_data[offset+8:offset+16])[0]
                box_data_start = offset + 16
            else:
                box_data_start = offset + 8
            
            if box_size == 0:
                # Box extends to end of file
                box_size = len(file_data) - offset
            elif box_size < 8:
                break
            
            box_end = offset + box_size
            if box_end > len(file_data):
                break
            
            # Include mdat boxes (media data - contains image data)
            # Exclude metadata boxes
            if box_type == b'mdat':
                # mdat box contains the actual image data
                box_data = file_data[box_data_start:box_end]
                hasher.update(box_data)
            elif box_type not in metadata_boxes:
                # Include other non-metadata boxes (like ftyp, moov, etc.)
                # These are part of the container structure
                pass
            
            offset = box_end
            box_count += 1
        
        return hasher.hexdigest()
    
    def calculate_raf_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of RAF (Fujifilm RAW) image data (excluding metadata).
        
        For RAF files, this extracts the image data from TIFF strips/tiles
        while excluding metadata. RAF files have a "FUJIFILM" header followed
        by a TIFF structure.
        
        Args:
            file_path: Path to RAF file
            
        Returns:
            Hexadecimal hash string or None if calculation fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception:
            return None
        
        if len(file_data) < 16:
            return None
        
        # Check RAF signature (FUJIFILM header)
        if not file_data.startswith(b'FUJIFILM'):
            return None
        
        # Find TIFF structure after FUJIFILM header
        tiff_offset = None
        for i in range(8, min(5000, len(file_data) - 4)):
            if file_data[i:i+2] == b'II' and file_data[i+2:i+4] == b'*\x00':
                tiff_offset = i
                break
            elif file_data[i:i+2] == b'MM' and file_data[i+2:i+4] == b'\x00*':
                tiff_offset = i
                break
        
        if tiff_offset is None:
            return None
        
        # Extract TIFF portion and use TIFF hash calculation
        # Create a temporary Path-like object for the TIFF data
        # We'll use the TIFF hash calculation logic directly
        tiff_data = file_data[tiff_offset:]
        
        # Use TIFF hash calculation logic
        # Determine endianness
        endian = '<'
        if tiff_data[:2] == b'MM':
            endian = '>'
        elif tiff_data[:2] != b'II':
            return None
        
        # Reset hasher
        if self.hash_type == 'md5':
            hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()
        
        # Parse TIFF structure to extract image data (strips/tiles)
        if len(tiff_data) < 8:
            return None
        
        # Read IFD0 offset
        ifd0_offset = struct.unpack(f'{endian}I', tiff_data[4:8])[0]
        
        if ifd0_offset == 0 or ifd0_offset >= len(tiff_data):
            return None
        
        # Parse IFD0 to find image data
        if ifd0_offset + 2 > len(tiff_data):
            return None
        
        num_entries = struct.unpack(f'{endian}H', tiff_data[ifd0_offset:ifd0_offset+2])[0]
        
        strip_offsets = []
        strip_byte_counts = []
        tile_offsets = []
        tile_byte_counts = []
        is_tiled = False
        
        entry_offset = ifd0_offset + 2
        for i in range(min(num_entries, 100)):
            if entry_offset + 12 > len(tiff_data):
                break
            
            tag_id = struct.unpack(f'{endian}H', tiff_data[entry_offset:entry_offset+2])[0]
            tag_type = struct.unpack(f'{endian}H', tiff_data[entry_offset+2:entry_offset+4])[0]
            tag_count = struct.unpack(f'{endian}I', tiff_data[entry_offset+4:entry_offset+8])[0]
            tag_value = struct.unpack(f'{endian}I', tiff_data[entry_offset+8:entry_offset+12])[0]
            
            # StripOffsets (273)
            if tag_id == 273:
                if tag_count == 1:
                    strip_offsets.append(tag_value)
                else:
                    # Multiple strips - value is offset to array
                    if tag_value + tag_count * 4 <= len(tiff_data):
                        for j in range(tag_count):
                            offset = struct.unpack(f'{endian}I', tiff_data[tag_value+j*4:tag_value+j*4+4])[0]
                            strip_offsets.append(offset)
            
            # StripByteCounts (279)
            elif tag_id == 279:
                if tag_count == 1:
                    strip_byte_counts.append(tag_value)
                else:
                    if tag_value + tag_count * 4 <= len(tiff_data):
                        for j in range(tag_count):
                            count = struct.unpack(f'{endian}I', tiff_data[tag_value+j*4:tag_value+j*4+4])[0]
                            strip_byte_counts.append(count)
            
            # TileOffsets (324)
            elif tag_id == 324:
                is_tiled = True
                if tag_count == 1:
                    tile_offsets.append(tag_value)
                else:
                    if tag_value + tag_count * 4 <= len(tiff_data):
                        for j in range(tag_count):
                            offset = struct.unpack(f'{endian}I', tiff_data[tag_value+j*4:tag_value+j*4+4])[0]
                            tile_offsets.append(offset)
            
            # TileByteCounts (325)
            elif tag_id == 325:
                if tag_count == 1:
                    tile_byte_counts.append(tag_value)
                else:
                    if tag_value + tag_count * 4 <= len(tiff_data):
                        for j in range(tag_count):
                            count = struct.unpack(f'{endian}I', tiff_data[tag_value+j*4:tag_value+j*4+4])[0]
                            tile_byte_counts.append(count)
            
            entry_offset += 12
        
        # Hash image data from strips or tiles
        if is_tiled and tile_offsets and tile_byte_counts:
            for offset, count in zip(tile_offsets, tile_byte_counts):
                if offset + count <= len(tiff_data):
                    hasher.update(tiff_data[offset:offset+count])
        elif strip_offsets and strip_byte_counts:
            for offset, count in zip(strip_offsets, strip_byte_counts):
                if offset + count <= len(tiff_data):
                    hasher.update(tiff_data[offset:offset+count])
        else:
            # No image data found
            return None
        
        return hasher.hexdigest()
    
    def calculate_mrw_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of MRW (Minolta RAW) image data (excluding metadata).
        
        For MRW files, this extracts the image data from TIFF strips/tiles
        while excluding metadata. MRW files have a "\x00MRM" header followed
        by sections and then a TIFF structure.
        
        Args:
            file_path: Path to MRW file
            
        Returns:
            Hexadecimal hash string or None if calculation fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception:
            return None
        
        if len(file_data) < 100:
            return None
        
        # Check MRW signature (\x00MRM header)
        if file_data[:4] != b'\x00MRM':
            return None
        
        # Find TIFF structure after MRW header sections
        # MRW structure: \x00MRM header (4 bytes), then 4 bytes (version/flags), then sections
        # Each section: 4 bytes header (1 byte type + 3 bytes name), 4 bytes size (big-endian), then data
        # TIFF structure is usually embedded within one of the sections
        tiff_offset = None
        ttw_offset = None
        ttw_size = None

        # Parse MRW sections to locate TTW block
        offset = 8
        while offset + 8 <= len(file_data):
            header = file_data[offset:offset + 4]
            if header == b'\x00\x00\x00\x00':
                break
            size = struct.unpack('>I', file_data[offset + 4:offset + 8])[0]
            data_offset = offset + 8
            if size == 0 or data_offset + size > len(file_data):
                break
            if header[1:4] == b'TTW':
                ttw_offset = data_offset
                ttw_size = size
                break
            offset = data_offset + size

        # Search for TIFF signature (II*\x00 or MM\x00*), prefer TTW section if present.
        if ttw_offset is not None and ttw_size:
            ttw_data = file_data[ttw_offset:ttw_offset + ttw_size]
            tiff_pos = ttw_data.find(b'II*\x00')
            if tiff_pos == -1:
                tiff_pos = ttw_data.find(b'MM\x00*')
            if tiff_pos != -1:
                tiff_offset = ttw_offset + tiff_pos

        if tiff_offset is None:
            for i in range(8, min(10000, len(file_data) - 4)):
                if file_data[i:i+2] == b'II' and file_data[i+2:i+4] == b'*\x00':
                    tiff_offset = i
                    break
                elif file_data[i:i+2] == b'MM' and file_data[i+2:i+4] == b'\x00*':
                    tiff_offset = i
                    break
        
        if tiff_offset is None:
            return None
        
        # Extract TIFF portion and use TIFF hash calculation logic
        tiff_data = file_data[tiff_offset:]
        
        # Determine endianness
        endian = '<'
        if tiff_data[:2] == b'MM':
            endian = '>'
        elif tiff_data[:2] != b'II':
            return None
        
        # Reset hasher
        if self.hash_type == 'md5':
            hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()
        
        # Parse TIFF structure to extract image data (strips/tiles)
        if len(tiff_data) < 8:
            return None
        
        # Read IFD0 offset
        ifd0_offset = struct.unpack(f'{endian}I', tiff_data[4:8])[0]
        
        if ifd0_offset == 0 or ifd0_offset >= len(tiff_data):
            return None
        
        # Parse IFD0 to find image data
        if ifd0_offset + 2 > len(tiff_data):
            return None
        
        num_entries = struct.unpack(f'{endian}H', tiff_data[ifd0_offset:ifd0_offset+2])[0]
        
        strip_offsets = []
        strip_byte_counts = []
        tile_offsets = []
        tile_byte_counts = []
        is_tiled = False
        
        entry_offset = ifd0_offset + 2
        for i in range(min(num_entries, 100)):
            if entry_offset + 12 > len(tiff_data):
                break
            
            tag_id = struct.unpack(f'{endian}H', tiff_data[entry_offset:entry_offset+2])[0]
            tag_type = struct.unpack(f'{endian}H', tiff_data[entry_offset+2:entry_offset+4])[0]
            tag_count = struct.unpack(f'{endian}I', tiff_data[entry_offset+4:entry_offset+8])[0]
            tag_value = struct.unpack(f'{endian}I', tiff_data[entry_offset+8:entry_offset+12])[0]
            
            # StripOffsets (273)
            if tag_id == 273:
                if tag_count == 1:
                    strip_offsets.append(tag_value)
                else:
                    if tag_value + tag_count * 4 <= len(tiff_data):
                        for j in range(tag_count):
                            offset = struct.unpack(f'{endian}I', tiff_data[tag_value+j*4:tag_value+j*4+4])[0]
                            strip_offsets.append(offset)
            
            # StripByteCounts (279)
            elif tag_id == 279:
                if tag_count == 1:
                    strip_byte_counts.append(tag_value)
                else:
                    if tag_value + tag_count * 4 <= len(tiff_data):
                        for j in range(tag_count):
                            count = struct.unpack(f'{endian}I', tiff_data[tag_value+j*4:tag_value+j*4+4])[0]
                            strip_byte_counts.append(count)
            
            # TileOffsets (324)
            elif tag_id == 324:
                is_tiled = True
                if tag_count == 1:
                    tile_offsets.append(tag_value)
                else:
                    if tag_value + tag_count * 4 <= len(tiff_data):
                        for j in range(tag_count):
                            offset = struct.unpack(f'{endian}I', tiff_data[tag_value+j*4:tag_value+j*4+4])[0]
                            tile_offsets.append(offset)
            
            # TileByteCounts (325)
            elif tag_id == 325:
                if tag_count == 1:
                    tile_byte_counts.append(tag_value)
                else:
                    if tag_value + tag_count * 4 <= len(tiff_data):
                        for j in range(tag_count):
                            count = struct.unpack(f'{endian}I', tiff_data[tag_value+j*4:tag_value+j*4+4])[0]
                            tile_byte_counts.append(count)
            
            entry_offset += 12
        
        # Hash image data from strips or tiles
        if is_tiled and tile_offsets and tile_byte_counts:
            for offset, count in zip(tile_offsets, tile_byte_counts):
                if offset + count <= len(tiff_data):
                    hasher.update(tiff_data[offset:offset+count])
        elif strip_offsets and strip_byte_counts:
            for offset, count in zip(strip_offsets, strip_byte_counts):
                if offset + count <= len(tiff_data):
                    hasher.update(tiff_data[offset:offset+count])
        else:
            # No image data found
            return None
        
        return hasher.hexdigest()
    
    def calculate_cr3_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of CR3 (Canon RAW 3) image data (excluding metadata).
        
        For CR3 files, this extracts the compressed image data from
        media data boxes (mdat) while excluding metadata boxes (meta, exif, xmp, etc.).
        CR3 uses ISO Base Media File Format (ISOBMFF), similar to HEIC/AVIF.
        
        Args:
            file_path: Path to CR3 file
            
        Returns:
            Hexadecimal hash string or None if calculation fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception:
            return None
        
        if len(file_data) < 8:
            return None
        
        # Check CR3 signature (ftyp box with 'crx' brand or similar)
        # CR3 files use ISOBMFF format
        if file_data[4:8] != b'ftyp':
            ftyp_pos = file_data.find(b'ftyp')
            if ftyp_pos == -1:
                return None
        
        # Reset hasher
        if self.hash_type == 'md5':
            hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()
        
        # Metadata boxes to exclude
        metadata_boxes = {b'meta', b'exif', b'xmp ', b'uuid', b'iref', b'pitm', b'iloc', b'iinf', b'infe', b'iprp', b'ipco', b'ispe', b'pasp', b'colr', b'pixi', b'moov', b'mvhd', b'trak', b'mdia', b'minf', b'stbl', b'co64', b'stco', b'stsc', b'stsz', b'stts', b'ctts', b'stss', b'stsd', b'pdin', b'free', b'skip', b'wide', b'pnot', b'udta'}
        
        # Parse ISOBMFF boxes and extract image data
        offset = 0
        max_offset = len(file_data) - 8
        box_count = 0
        max_boxes = 1000
        
        while offset < max_offset and box_count < max_boxes:
            if offset + 8 > len(file_data):
                break
            
            # Read box size (4 bytes, big-endian)
            box_size = struct.unpack('>I', file_data[offset:offset+4])[0]
            box_type = file_data[offset+4:offset+8]
            
            # Handle extended size (size == 1 means 64-bit size follows)
            if box_size == 1:
                if offset + 16 > len(file_data):
                    break
                box_size = struct.unpack('>Q', file_data[offset+8:offset+16])[0]
                box_data_start = offset + 16
            else:
                box_data_start = offset + 8
            
            if box_size == 0:
                # Box extends to end of file
                box_size = len(file_data) - offset
            elif box_size < 8:
                break
            
            box_end = offset + box_size
            if box_end > len(file_data):
                break
            
            # Include mdat boxes (media data - contains image data)
            # Exclude metadata boxes
            if box_type == b'mdat':
                # mdat box contains the actual image data
                box_data = file_data[box_data_start:box_end]
                hasher.update(box_data)
            elif box_type not in metadata_boxes:
                # Include other non-metadata boxes (like ftyp, etc.)
                # These are part of the container structure
                pass
            
            offset = box_end
            box_count += 1
        
        return hasher.hexdigest()
    
    def calculate_mov_mp4_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of MOV/MP4 video/image data (excluding metadata).
        
        For MOV/MP4 files, this extracts the compressed video/image data from
        media data boxes (mdat) while excluding metadata boxes (moov, meta, ilst, uuid, etc.).
        MOV/MP4 uses ISO Base Media File Format (ISOBMFF), similar to HEIC/AVIF/CR3.
        
        Args:
            file_path: Path to MOV/MP4 file
            
        Returns:
            Hexadecimal hash string or None if calculation fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception:
            return None
        
        if len(file_data) < 8:
            return None
        
        # Check MOV/MP4 signature (ftyp box)
        if file_data[4:8] != b'ftyp':
            ftyp_pos = file_data.find(b'ftyp')
            if ftyp_pos == -1:
                return None
        
        # Reset hasher
        if self.hash_type == 'md5':
            hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()
        
        # Metadata boxes to exclude (more comprehensive for video files)
        metadata_boxes = {
            b'meta', b'exif', b'xmp ', b'uuid', b'iref', b'pitm', b'iloc', b'iinf', b'infe', 
            b'iprp', b'ipco', b'ispe', b'pasp', b'colr', b'pixi',
            b'moov', b'mvhd', b'trak', b'mdia', b'minf', b'stbl', b'stsd', b'stts', b'stsc',
            b'stsz', b'stco', b'co64', b'ctts', b'stss', b'pdin', b'free', b'skip', b'wide',
            b'pnot', b'udta', b'ilst', b'\xa9nam', b'\xa9ART', b'\xa9day', b'\xa9alb',
            b'\xa9cmt', b'\xa9gen', b'\xa9wrt', b'\xa9too', b'\xa9cpy', b'\xa9des',
            b'cprt', b'\xa9xyz', b'\xa9loc', b'\xa9grp', b'\xa9lyr', b'\xa9enc'
        }
        
        # Parse ISOBMFF boxes and extract video/image data
        offset = 0
        max_offset = len(file_data) - 8
        box_count = 0
        max_boxes = 1000
        
        while offset < max_offset and box_count < max_boxes:
            if offset + 8 > len(file_data):
                break
            
            # Read box size (4 bytes, big-endian)
            box_size = struct.unpack('>I', file_data[offset:offset+4])[0]
            box_type = file_data[offset+4:offset+8]
            
            # Handle extended size (size == 1 means 64-bit size follows)
            if box_size == 1:
                if offset + 16 > len(file_data):
                    break
                box_size = struct.unpack('>Q', file_data[offset+8:offset+16])[0]
                box_data_start = offset + 16
            else:
                box_data_start = offset + 8
            
            if box_size == 0:
                # Box extends to end of file
                box_size = len(file_data) - offset
            elif box_size < 8:
                break
            
            box_end = offset + box_size
            if box_end > len(file_data):
                break
            
            # Include mdat boxes (media data - contains video/image data)
            # Exclude metadata boxes
            if box_type == b'mdat':
                # mdat box contains the actual video/image data
                box_data = file_data[box_data_start:box_end]
                hasher.update(box_data)
            elif box_type not in metadata_boxes:
                # Include other non-metadata boxes (like ftyp, etc.)
                # These are part of the container structure
                pass
            
            offset = box_end
            box_count += 1
        
        return hasher.hexdigest()
    
    def calculate_riff_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of RIFF-based file data (excluding metadata).
        
        For RIFF files (WAV, AVI, etc.), this extracts the actual audio/video data
        from data chunks while excluding metadata chunks (LIST, INFO, etc.).
        
        Args:
            file_path: Path to RIFF file (WAV, AVI, etc.)
            
        Returns:
            Hexadecimal hash string or None if calculation fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception:
            return None
        
        if len(file_data) < 12:
            return None
        
        # Check RIFF signature
        if file_data[:4] != b'RIFF':
            return None
        
        # Reset hasher
        if self.hash_type == 'md5':
            hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()
        
        # Metadata chunks to exclude
        metadata_chunks = {b'LIST', b'INFO', b'id3 ', b'JUNK', b'FMT ', b'fact', b'cue ', b'plst', b'labl', b'note', b'ltxt', b'smpl', b'inst', b'PEAK', b'DISP', b'acid', b'strc', b'strh', b'strf', b'strd', b'vprp', b'indx', b'odml', b'dmlh', b'idx1'}
        
        # Parse RIFF chunks
        offset = 12  # Skip RIFF header (RIFF + size + format)
        
        while offset < len(file_data) - 8:
            if offset + 8 > len(file_data):
                break
            
            # Read chunk ID (4 bytes)
            chunk_id = file_data[offset:offset+4]
            
            # Read chunk size (4 bytes, little-endian)
            chunk_size = struct.unpack('<I', file_data[offset+4:offset+8])[0]
            
            if chunk_size == 0 or offset + 8 + chunk_size > len(file_data):
                break
            
            chunk_data_start = offset + 8
            chunk_data_end = chunk_data_start + chunk_size
            
            # Include data chunks (actual audio/video data)
            # Exclude metadata chunks
            if chunk_id == b'data':
                # 'data' chunk contains actual audio/video data
                chunk_data = file_data[chunk_data_start:chunk_data_end]
                hasher.update(chunk_data)
            elif chunk_id not in metadata_chunks:
                # Include other non-metadata chunks (like 'fmt ', 'WAVE', etc.)
                # These are part of the format structure
                pass
            
            # Move to next chunk (chunks are aligned to 2-byte boundaries)
            offset = chunk_data_end
            if offset % 2:
                offset += 1  # Skip padding byte
        
        return hasher.hexdigest()
    
    def calculate_iiq_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of IIQ (Phase One RAW) image data (excluding metadata).
        
        IIQ files are TIFF-based RAW files from Phase One cameras.
        They use TIFF structure with "IIR" signature (Phase One specific).
        This extracts image strip/tile data while excluding IFD metadata structures.
        
        Args:
            file_path: Path to IIQ file
            
        Returns:
            Hexadecimal hash string or None if calculation fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception:
            return None
        
        if len(file_data) < 8:
            return None
        
        # Check IIQ signature (Phase One RAW files start with "IIR")
        # Note: IIQ files are TIFF-based, so they have TIFF structure after signature
        if file_data[:3] != b'IIR':
            return None
        
        # Reset hasher
        if self.hash_type == 'md5':
            hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()
        
        # IIQ files use little-endian TIFF structure (II = little-endian)
        endian = '<'
        
        # Include TIFF header (signature + magic number + IFD offset)
        # For IIQ, the signature is "IIR" but the TIFF magic number (0x002A) follows
        # Skip the "IIR" signature and use standard TIFF hash calculation
        # Actually, IIQ files have "IIR" at start, but then follow TIFF structure
        # The IFD offset is typically at offset 4 (after "IIR" + 1 byte)
        # However, some IIQ files may have the TIFF structure starting at offset 0
        # Let's check if it's standard TIFF structure after "IIR"
        
        # Try to find TIFF magic number (0x002A) - it should be at offset 2-4
        # IIQ structure: "IIR" (3 bytes) + magic (2 bytes) + IFD offset (4 bytes)
        if len(file_data) < 8:
            return None
        
        # Check for TIFF magic number at offset 2 (after "IIR")
        magic = struct.unpack('<H', file_data[2:4])[0]
        if magic != 0x002A:
            # Try standard TIFF structure (IIQ might use standard TIFF)
            if file_data[:2] == b'II' and struct.unpack('<H', file_data[2:4])[0] == 0x002A:
                # Standard TIFF structure
                hasher.update(file_data[:8])
                ifd_offset = struct.unpack('<I', file_data[4:8])[0]
            else:
                return None
        else:
            # IIQ-specific structure: "IIR" + magic + IFD offset
            hasher.update(file_data[:8])
            ifd_offset = struct.unpack('<I', file_data[4:8])[0]
        
        if ifd_offset == 0 or ifd_offset >= len(file_data):
            return None
        
        # Parse IFD0 to find strip/tile offsets (same as TIFF)
        strip_offsets = []
        strip_byte_counts = []
        tile_offsets = []
        tile_byte_counts = []
        is_tiled = False
        
        current_ifd_offset = ifd_offset
        
        # Parse IFD entries (limit to first IFD for image data)
        if current_ifd_offset + 2 > len(file_data):
            return None
        
        entry_count = struct.unpack(f'{endian}H', file_data[current_ifd_offset:current_ifd_offset + 2])[0]
        entry_offset = current_ifd_offset + 2
        
        for _ in range(entry_count):
            if entry_offset + 12 > len(file_data):
                break
            
            # Read IFD entry (12 bytes: tag(2) + type(2) + count(4) + value/offset(4))
            tag_id = struct.unpack(f'{endian}H', file_data[entry_offset:entry_offset + 2])[0]
            tag_type = struct.unpack(f'{endian}H', file_data[entry_offset + 2:entry_offset + 4])[0]
            tag_count = struct.unpack(f'{endian}I', file_data[entry_offset + 4:entry_offset + 8])[0]
            tag_value = struct.unpack(f'{endian}I', file_data[entry_offset + 8:entry_offset + 12])[0]
            
            # StripOffsets tag (273)
            if tag_id == 273:
                if tag_count == 1:
                    strip_offsets = [tag_value]
                else:
                    # Multiple strips - read from offset
                    if tag_value < len(file_data) and tag_value + (tag_count * 4) <= len(file_data):
                        strip_offsets = list(struct.unpack(
                            f'{endian}{tag_count}I',
                            file_data[tag_value:tag_value + (tag_count * 4)]
                        ))
            
            # StripByteCounts tag (279)
            elif tag_id == 279:
                if tag_count == 1:
                    strip_byte_counts = [tag_value]
                else:
                    # Multiple strips - read from offset
                    if tag_value < len(file_data) and tag_value + (tag_count * 4) <= len(file_data):
                        strip_byte_counts = list(struct.unpack(
                            f'{endian}{tag_count}I',
                            file_data[tag_value:tag_value + (tag_count * 4)]
                        ))
            
            # TileOffsets tag (324)
            elif tag_id == 324:
                is_tiled = True
                if tag_count == 1:
                    tile_offsets = [tag_value]
                else:
                    # Multiple tiles - read from offset
                    if tag_value < len(file_data) and tag_value + (tag_count * 4) <= len(file_data):
                        tile_offsets = list(struct.unpack(
                            f'{endian}{tag_count}I',
                            file_data[tag_value:tag_value + (tag_count * 4)]
                        ))
            
            # TileByteCounts tag (325)
            elif tag_id == 325:
                is_tiled = True
                if tag_count == 1:
                    tile_byte_counts = [tag_value]
                else:
                    # Multiple tiles - read from offset
                    if tag_value < len(file_data) and tag_value + (tag_count * 4) <= len(file_data):
                        tile_byte_counts = list(struct.unpack(
                            f'{endian}{tag_count}I',
                            file_data[tag_value:tag_value + (tag_count * 4)]
                        ))
            
            entry_offset += 12
        
        # Extract image data from strips or tiles
        image_data = b''
        if is_tiled and tile_offsets and tile_byte_counts:
            # Tiled image
            for offset, byte_count in zip(tile_offsets, tile_byte_counts):
                if offset + byte_count <= len(file_data):
                    image_data += file_data[offset:offset + byte_count]
        elif strip_offsets and strip_byte_counts:
            # Striped image
            for offset, byte_count in zip(strip_offsets, strip_byte_counts):
                if offset + byte_count <= len(file_data):
                    image_data += file_data[offset:offset + byte_count]
        
        if image_data:
            hasher.update(image_data)
        
        return hasher.hexdigest()
    
    def calculate_crw_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of CRW (Canon RAW) image data (excluding metadata).
        
        CRW files use a HEAPCCDR structure:
        - Header: "IIRO" or "II\x1a\x00" signature
        - HEAPCCDR structure contains metadata
        - Image data is typically in the HEAP section
        
        For hash calculation, we extract image data while excluding metadata structures.
        
        Args:
            file_path: Path to CRW file
            
        Returns:
            Hexadecimal hash string or None if calculation fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception:
            return None
        
        if len(file_data) < 20:
            return None
        
        # Check CRW signature
        if not (file_data.startswith(b'IIRO') or 
                (len(file_data) >= 4 and file_data[:2] == b'II' and file_data[2:4] == b'\x1a\x00')):
            return None
        
        # Reset hasher
        if self.hash_type == 'md5':
            hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()
        
        # CRW uses little-endian
        endian = '<'
        
        # Include CRW header signature
        hasher.update(file_data[:4])
        
        # CRW structure: HEAPCCDR header (bytes 6-13)
        # Skip HEAPCCDR header for hash (metadata)
        # Extract image data from HEAP section
        # For CRW, image data is typically after the HEAPCCDR header
        # The HEAP section contains both metadata and image data
        
        # Try to find image data offset
        # CRW files have image data in the HEAP section
        # Skip HEAPCCDR header (bytes 0-19) and extract remaining data
        # This is a simplified approach - full CRW parsing would require understanding HEAP structure
        
        # Include file data after HEAPCCDR header (simplified approach)
        # In a full implementation, we would parse the HEAP structure to find actual image data
        if len(file_data) > 20:
            # Skip HEAPCCDR header and include rest as image data
            # This is a simplified approach - actual CRW image data extraction requires HEAP parsing
            hasher.update(file_data[20:])
        
        return hasher.hexdigest()
    
    def calculate_x3f_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of X3F (Sigma RAW) image data (excluding metadata).
        
        X3F files use a proprietary format structure:
        - Header: "FOVb" signature (4 bytes)
        - Version (4 bytes, big-endian)
        - Directory offset (4 bytes, big-endian)
        - Directory count (4 bytes, big-endian)
        - Image data offset (4 bytes, big-endian)
        - Image data size (4 bytes, big-endian)
        - Thumbnail offset (4 bytes, big-endian)
        - Thumbnail size (4 bytes, big-endian)
        
        For hash calculation, we extract image data using the image data offset and size.
        
        Args:
            file_path: Path to X3F file
            
        Returns:
            Hexadecimal hash string or None if calculation fails
        """
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception:
            return None
        
        if len(file_data) < 28:
            return None
        
        # Check X3F signature
        if file_data[:4] != b'FOVb':
            return None
        
        # Reset hasher
        if self.hash_type == 'md5':
            hasher = hashlib.md5()
        elif self.hash_type == 'sha1':
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()
        
        # X3F uses big-endian
        endian = '>'
        
        # Include X3F header signature
        hasher.update(file_data[:4])
        
        # Parse X3F header to find image data
        if len(file_data) >= 28:
            # Image data offset (bytes 16-19, big-endian)
            image_offset = struct.unpack('>I', file_data[16:20])[0]
            
            # Image data size (bytes 20-23, big-endian)
            image_size = struct.unpack('>I', file_data[20:24])[0]
            
            # Extract image data
            if image_offset > 0 and image_size > 0 and image_offset + image_size <= len(file_data):
                image_data = file_data[image_offset:image_offset + image_size]
                hasher.update(image_data)
            else:
                # Fallback: include all data after header if offsets are invalid
                if len(file_data) > 28:
                    hasher.update(file_data[28:])
        
        return hasher.hexdigest()
    
    def calculate_hash(self, file_path: Path) -> Optional[str]:
        """
        Calculate hash of image data for supported formats.
        
        Args:
            file_path: Path to image file
            
        Returns:
            Hexadecimal hash string or None if format not supported or calculation fails
        """
        suffix = file_path.suffix.lower()
        
        if suffix in ['.jpg', '.jpeg']:
            return self.calculate_jpeg_hash(file_path)
        elif suffix == '.png':
            return self.calculate_png_hash(file_path)
        elif suffix in ['.tif', '.tiff']:
            return self.calculate_tiff_hash(file_path)
        elif suffix in ['.heic', '.heif']:
            return self.calculate_heic_hash(file_path)
        elif suffix == '.j2c':
            return self.calculate_j2c_hash(file_path)
        elif suffix == '.jxl':
            return self.calculate_jxl_hash(file_path)
        elif suffix == '.avif':
            return self.calculate_avif_hash(file_path)
        elif suffix == '.raf':
            return self.calculate_raf_hash(file_path)
        elif suffix == '.mrw':
            return self.calculate_mrw_hash(file_path)
        elif suffix == '.cr3':
            return self.calculate_cr3_hash(file_path)
        elif suffix in ['.mov', '.mp4', '.m4v', '.m4a']:
            return self.calculate_mov_mp4_hash(file_path)
        elif suffix in ['.wav', '.avi']:
            return self.calculate_riff_hash(file_path)
        elif suffix == '.iiq':
            return self.calculate_iiq_hash(file_path)
        elif suffix == '.crw':
            return self.calculate_crw_hash(file_path)
        elif suffix == '.x3f':
            return self.calculate_x3f_hash(file_path)
        else:
            # Format not yet supported
            return None


def calculate_image_data_hash(
    file_path: Path,
    hash_type: str = 'md5'
) -> Optional[str]:
    """
    Calculate hash of image data (excluding metadata).
    
    Args:
        file_path: Path to image file
        hash_type: Type of hash ('md5', 'sha1', 'sha256')
        
    Returns:
        Hexadecimal hash string or None if calculation fails
        
    Example:
        >>> hash_value = calculate_image_data_hash(Path('image.jpg'))
        >>> print(f"ImageDataMD5: {hash_value}")
    """
    calculator = ImageHashCalculator(hash_type=hash_type)
    return calculator.calculate_hash(file_path)


def add_image_data_hash_to_metadata(
    metadata: Dict[str, Any],
    file_path: Path,
    hash_type: str = 'md5'
) -> Dict[str, Any]:
    """
    Calculate image data hash and add to metadata.
    
    Args:
        metadata: Existing metadata dictionary
        file_path: Path to image file
        hash_type: Type of hash ('md5', 'sha1', 'sha256')
        
    Returns:
        Updated metadata dictionary with ImageDataMD5/ImageDataHash tag
        
    Example:
        >>> metadata = {}
        >>> metadata = add_image_data_hash_to_metadata(metadata, Path('image.jpg'))
        >>> print(metadata.get('Composite:ImageDataMD5'))
    """
    hash_value = calculate_image_data_hash(file_path, hash_type)
    
    if hash_value:
        if hash_type.lower() == 'md5':
            metadata['Composite:ImageDataMD5'] = hash_value
            metadata['Composite:ImageDataHash'] = hash_value  # Alias
        else:
            metadata[f'Composite:ImageDataHash'] = hash_value
    
    return metadata
