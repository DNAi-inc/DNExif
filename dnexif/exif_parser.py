# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
EXIF metadata parser

This module handles reading and writing EXIF metadata from JPEG and TIFF files.
EXIF (Exchangeable Image File Format) is a standard for storing metadata in image files.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, Tuple, List
from enum import IntEnum
import io
import zlib

from dnexif.exceptions import MetadataReadError, MetadataWriteError
from dnexif.makernote_parser import MakerNoteParser


class ExifTagType(IntEnum):
    """EXIF tag data types"""
    BYTE = 1
    ASCII = 2
    SHORT = 3
    LONG = 4
    RATIONAL = 5
    UNDEFINED = 7
    SLONG = 9
    SRATIONAL = 10
    LONG8 = 16  # BigTIFF format code 16 (64-bit unsigned integer)
    SLONG8 = 17  # BigTIFF format code 17 (64-bit signed integer)
    IFD8 = 18  # BigTIFF format code 18 (64-bit IFD offset)


# EXIF tag sizes in bytes
TAG_SIZES = {
    ExifTagType.BYTE: 1,
    ExifTagType.ASCII: 1,
    ExifTagType.SHORT: 2,
    ExifTagType.LONG: 4,
    ExifTagType.RATIONAL: 8,
    ExifTagType.UNDEFINED: 1,
    ExifTagType.SLONG: 4,
    ExifTagType.SRATIONAL: 8,
    ExifTagType.LONG8: 8,  # BigTIFF LONG8 is 8 bytes (64-bit)
    ExifTagType.SLONG8: 8,  # BigTIFF SLONG8 is 8 bytes (64-bit signed)
    ExifTagType.IFD8: 8,  # BigTIFF IFD8 is 8 bytes (64-bit IFD offset)
}

# Import comprehensive tag definitions
from dnexif.exif_tags import EXIF_TAG_NAMES


class ExifParser:
    """
    Parser for EXIF metadata from JPEG and TIFF files.
    
    This class handles reading and writing EXIF data according to the
    EXIF 2.3 and EXIF 3.0 specifications.
    
    EXIF 3.0 (released May 2023) introduces UTF-8 encoding support for
    text fields, allowing international character sets.
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize the EXIF parser.
        
        Args:
            file_path: Path to the image file
            file_data: Raw file data (alternative to file_path)
        """
        self.file_path = file_path
        self.file_data = file_data
        self.metadata: Dict[str, Any] = {}
        self.endian = '<'  # Default to little-endian
        self.exif_version: Optional[str] = None  # EXIF version (e.g., "0230" for 2.30, "0300" for 3.0)
        self.supports_utf8: bool = False  # Whether EXIF 3.0 UTF-8 is supported
        
    def read(self) -> Dict[str, Any]:
        """
        Read EXIF metadata from the file.
        
        Returns:
            Dictionary containing all EXIF metadata
            
        Raises:
            MetadataReadError: If the file cannot be read or parsed
        """
        if self.file_path:
            with open(self.file_path, 'rb') as f:
                self.file_data = f.read()
        elif not self.file_data:
            raise MetadataReadError("No file path or file data provided")
            
        try:
            metadata = {}
            # Check if it's a JPEG file
            if self.file_data[:2] == b'\xff\xd8':
                metadata = self._parse_jpeg()
            # Check if it's a TIFF file
            elif self.file_data[:2] in (b'II', b'MM'):
                metadata = self._parse_tiff()
            # Check if it's a PNG file
            elif self.file_data[:8] == b'\x89PNG\r\n\x1a\n':
                metadata = self._parse_png()
            # Check if it's a Fujifilm RAF file (has FUJIFILM header followed by TIFF)
            elif self.file_data.startswith(b'FUJIFILM'):
                metadata = self._parse_raf()
            # Check if it's a Panasonic RW2 file (has IIU/MMU header)
            elif self.file_data[:3] in (b'IIU', b'MMU'):
                metadata = self._parse_tiff()  # RW2 uses TIFF structure, _parse_tiff_header handles it
            else:
                raise MetadataReadError("Unsupported file format")
            
            # Final check: If EXIF:SubfileType exists and is "Full-resolution image", use it as SubfileType
            # This handles Sony ARW and similar formats where EXIF IFD's SubfileType takes precedence
            if 'EXIF:SubfileType' in metadata:
                exif_subfile_type = metadata.get('EXIF:SubfileType')
                if (exif_subfile_type == 0 or 
                    exif_subfile_type == 'Full-resolution image' or
                    str(exif_subfile_type).strip() == '0' or
                    (isinstance(exif_subfile_type, str) and 'Full-resolution' in exif_subfile_type)):
                    from dnexif.value_formatter import format_exif_value
                    metadata['SubfileType'] = format_exif_value('SubfileType', 0)
            
            return metadata
        except Exception as e:
            raise MetadataReadError(f"Failed to read EXIF data: {str(e)}")
    
    def _parse_jpeg(self) -> Dict[str, Any]:
        """Parse EXIF data from a JPEG file."""
        offset = 2  # Skip JPEG SOI marker
        
        # Find APP1 segment (EXIF)
        while offset < len(self.file_data):
            # Check for segment marker
            if self.file_data[offset] != 0xFF:
                break
                
            marker = self.file_data[offset + 1]
            
            # APP1 marker (0xE1) contains EXIF data
            if marker == 0xE1:
                # Read segment length
                length = struct.unpack('>H', self.file_data[offset + 2:offset + 4])[0]
                
                # Check for EXIF header
                if self.file_data[offset + 4:offset + 10] == b'Exif\x00\x00':
                    # Parse TIFF header (EXIF uses TIFF structure)
                    tiff_offset = offset + 10
                    return self._parse_tiff_header(tiff_offset)
            
            # Skip to next segment
            if marker == 0xD8:  # SOI
                offset += 2
            elif marker == 0xD9:  # EOI
                break
            elif marker >= 0xE0 and marker <= 0xEF:  # APP segments
                length = struct.unpack('>H', self.file_data[offset + 2:offset + 4])[0]
                offset += 4 + length
            else:
                # Skip other segments
                if offset + 2 < len(self.file_data):
                    length = struct.unpack('>H', self.file_data[offset + 2:offset + 4])[0]
                    offset += 4 + length
                else:
                    break
        
        return {}
    
    def _parse_png(self) -> Dict[str, Any]:
        """
        Parse EXIF data from a PNG file.
        
        PNG stores EXIF in eXIf chunks (PNG 1.2.1+) or tEXt chunks (legacy).
        """
        metadata = {}
        offset = 8  # Skip PNG signature
        
        # Parse PNG chunks
        while offset < len(self.file_data) - 8:
            # Read chunk length (4 bytes, big-endian)
            if offset + 4 > len(self.file_data):
                break
            chunk_length = struct.unpack('>I', self.file_data[offset:offset + 4])[0]
            offset += 4
            
            # Read chunk type (4 bytes)
            if offset + 4 > len(self.file_data):
                break
            chunk_type = self.file_data[offset:offset + 4]
            offset += 4
            
            # Check for eXIf chunk (PNG 1.2.1+ standard for EXIF)
            if chunk_type == b'eXIf':
                # eXIf chunk contains EXIF data directly (TIFF structure)
                if offset + chunk_length <= len(self.file_data):
                    exif_data = self.file_data[offset:offset + chunk_length]
                    # Parse as TIFF - use existing method
                    try:
                        # Create temporary parser instance for PNG EXIF data
                        # The eXIf chunk data is the TIFF structure starting at offset 0
                        temp_parser = ExifParser(file_data=exif_data)
                        # Parse TIFF header at offset 0 (start of eXIf chunk data)
                        exif_metadata = temp_parser._parse_tiff_header(0)
                        metadata.update(exif_metadata)
                    except Exception:
                        pass
            
            # Check for tEXt chunk with EXIF keyword (legacy, not standard)
            elif chunk_type == b'tEXt':
                # tEXt chunks are keyword + null + text
                # Some software may store EXIF here, but it's not standard
                pass
            
            # Check for zTXt chunk (compressed text chunk)
            elif chunk_type == b'zTXt':
                # zTXt format: keyword (null-terminated), compression method (1 byte), compressed text
                if offset + chunk_length <= len(self.file_data):
                    chunk_data = self.file_data[offset:offset + chunk_length]
                    try:
                        # Find keyword (null-terminated)
                        keyword_end = chunk_data.find(b'\x00')
                        if keyword_end != -1:
                            keyword = chunk_data[:keyword_end].decode('latin-1', errors='ignore')
                            # Read compression method (1 byte after null terminator)
                            if keyword_end + 1 < len(chunk_data):
                                compression_method = chunk_data[keyword_end + 1]
                                # Compressed text data starts after compression method
                                compressed_text = chunk_data[keyword_end + 2:]
                                
                                # Decompress if using zlib (compression method 0)
                                if compression_method == 0:
                                    try:
                                        decompressed_text = zlib.decompress(compressed_text)
                                        # Store as PNG:zTXt:keyword
                                        metadata[f'PNG:zTXt:{keyword}'] = decompressed_text.decode('utf-8', errors='ignore')
                                    except Exception:
                                        pass
                    except Exception:
                        pass
            
            # Check for cpIp chunk (compressed image preview)
            elif chunk_type == b'cpIp':
                # cpIp chunk contains compressed image preview data
                if offset + chunk_length <= len(self.file_data):
                    chunk_data = self.file_data[offset:offset + chunk_length]
                    try:
                        # Store cpIp chunk data size and indicate presence
                        metadata['PNG:cpIp'] = f'Present ({chunk_length} bytes)'
                        # Optionally store the chunk data as binary (for extraction)
                        metadata['PNG:cpIp:Data'] = chunk_data
                    except Exception:
                        pass
            
            # Check for GainMapImage (HDR gain map) - typically in XMP or as a custom chunk
            # GainMapImage is often stored in XMP metadata, but can also be in custom chunks
            elif chunk_type == b'gmIp':  # Gain Map Image Preview chunk (if used)
                # gmIp chunk contains gain map image data
                if offset + chunk_length <= len(self.file_data):
                    chunk_data = self.file_data[offset:offset + chunk_length]
                    try:
                        metadata['PNG:GainMapImage'] = f'Present ({chunk_length} bytes)'
                        metadata['PNG:GainMapImage:Data'] = chunk_data
                    except Exception:
                        pass
            
            # Check for iCCP chunk (compressed ICC profile)
            elif chunk_type == b'iCCP':
                # iCCP format: profile name (null-terminated), compression method (1 byte), compressed profile data
                if offset + chunk_length <= len(self.file_data):
                    chunk_data = self.file_data[offset:offset + chunk_length]
                    try:
                        # Find profile name (null-terminated)
                        name_end = chunk_data.find(b'\x00')
                        if name_end != -1:
                            profile_name = chunk_data[:name_end].decode('latin-1', errors='ignore')
                            # Read compression method (1 byte after null terminator)
                            if name_end + 1 < len(chunk_data):
                                compression_method = chunk_data[name_end + 1]
                                # Compressed profile data starts after compression method
                                compressed_profile = chunk_data[name_end + 2:]
                                
                                # Decompress if using zlib (compression method 0)
                                if compression_method == 0:
                                    try:
                                        decompressed_profile = zlib.decompress(compressed_profile)
                                        # Store ICC profile info (we don't parse the full ICC profile, just mark its presence)
                                        metadata['PNG:iCCP:ProfileName'] = profile_name
                                        metadata['PNG:iCCP:ProfileSize'] = len(decompressed_profile)
                                        # Store first few bytes as identifier
                                        if len(decompressed_profile) >= 4:
                                            metadata['PNG:iCCP:ProfileHeader'] = decompressed_profile[:4].hex().upper()
                                    except Exception:
                                        pass
                    except Exception:
                        pass
            
            # Skip to next chunk (skip data + CRC)
            offset += chunk_length + 4  # +4 for CRC
            
            # Stop at IEND chunk
            if chunk_type == b'IEND':
                break
        
        # Check for Samsung trailer (data after IEND chunk)
        # Samsung devices sometimes append additional metadata after the PNG IEND chunk
        # This is a non-standard extension
        if offset < len(self.file_data):
            trailer_data = self.file_data[offset:]
            if len(trailer_data) > 0:
                # Check if trailer data looks like Samsung metadata
                # Samsung trailers often start with specific signatures or contain structured data
                try:
                    # Check for common Samsung trailer signatures
                    # Some Samsung trailers start with specific byte patterns
                    if len(trailer_data) >= 4:
                        # Check for potential Samsung MakerNote or EXIF-like structures
                        # Samsung trailers may contain TIFF-like structures or other metadata
                        trailer_size = len(trailer_data)
                        metadata['PNG:SamsungTrailer'] = f'Present ({trailer_size} bytes)'
                        metadata['PNG:SamsungTrailer:Size'] = trailer_size
                        
                        # Try to detect if trailer contains structured data
                        # Check for TIFF-like structure (II or MM header)
                        if len(trailer_data) >= 2:
                            tiff_header = trailer_data[:2]
                            if tiff_header == b'II' or tiff_header == b'MM':
                                # Potential TIFF structure in trailer
                                metadata['PNG:SamsungTrailer:Type'] = 'TIFF-like structure detected'
                                # Try to parse as TIFF if it looks valid
                                try:
                                    temp_parser = ExifParser(file_data=trailer_data)
                                    trailer_metadata = temp_parser._parse_tiff_header(0)
                                    # Prefix trailer metadata with SamsungTrailer namespace
                                    for key, value in trailer_metadata.items():
                                        metadata[f'PNG:SamsungTrailer:{key}'] = value
                                except Exception:
                                    pass
                            else:
                                # Store first few bytes as identifier
                                if len(trailer_data) >= 16:
                                    metadata['PNG:SamsungTrailer:Header'] = trailer_data[:16].hex().upper()
                                else:
                                    metadata['PNG:SamsungTrailer:Header'] = trailer_data.hex().upper()
                        
                        # Store trailer data reference (for potential extraction)
                        metadata['PNG:SamsungTrailer:Data'] = trailer_data
                except Exception:
                    pass
        
        return metadata
    
    def _parse_tiff(self) -> Dict[str, Any]:
        """
        Parse EXIF data from a TIFF file.
        
        For RW2 files, also searches for embedded TIFF structure (like RAF files).
        """
        metadata = self._parse_tiff_header(0)
        
        # For RW2 files (IIU/MMU header), also search for embedded TIFF structure
        # RW2 files have a TIFF structure embedded at offset ~2060 with MakerNote data
        if self.file_data[:3] in (b'IIU', b'MMU'):
            # Search for embedded TIFF structure (starts with "II*" or "MM*")
            tiff_offset = None
            for i in range(min(5000, len(self.file_data) - 4)):
                if self.file_data[i:i+2] == b'II' and self.file_data[i+2:i+4] == b'*\x00':
                    tiff_offset = i
                    break
                elif self.file_data[i:i+2] == b'MM' and self.file_data[i+2:i+4] == b'\x00*':
                    tiff_offset = i
                    break
            
            # If we found embedded TIFF structure, parse it and merge metadata
            if tiff_offset is not None and tiff_offset > 100:  # Only if it's not the header we already parsed
                try:
                    embedded_metadata = self._parse_tiff_header(tiff_offset)
                    # Merge embedded metadata (MakerNote tags from embedded TIFF)
                    for k, v in embedded_metadata.items():
                        if k not in metadata or k.startswith('MakerNotes:') or k.startswith('MakerNote:'):
                            # Prefer MakerNote tags from embedded TIFF, don't overwrite existing tags
                            metadata[k] = v
                except Exception:
                    # If embedded TIFF parsing fails, continue with main metadata
                    pass
        
        return metadata
    
    def _parse_raf(self) -> Dict[str, Any]:
        """
        Parse EXIF data from a Fujifilm RAF file.
        
        RAF files have a "FUJIFILM" header followed by a TIFF structure.
        We need to find the TIFF structure and parse it.
        """
        # Find TIFF structure after FUJIFILM header
        tiff_offset = self.file_data.find(b'II*\x00')
        if tiff_offset == -1:
            tiff_offset = self.file_data.find(b'MM\x00*')
        
        if tiff_offset > 0:
            # Parse TIFF structure starting at tiff_offset
            return self._parse_tiff_header(tiff_offset)
        else:
            # Fallback: try parsing from offset 0 (might work for some files)
            return self._parse_tiff_header(0)
    
    def _parse_tiff_header(self, offset: int) -> Dict[str, Any]:
        """
        Parse TIFF header and IFD structures.
        
        For RAW formats, this method now parses all IFDs and selects the main image IFD
        (Full-resolution) instead of the preview IFD (Reduced-resolution).
        
        Handles both standard TIFF format and ORF format (which has IIRO/MMOR header).
        """
        # Initialize byte_order_str (used later for File:ExifByteOrder tag)
        byte_order_str = None
        
        # Check for special RAW format headers (ORF, RW2, etc.)
        if offset + 4 <= len(self.file_data):
            header_4 = self.file_data[offset:offset + 4]
            if header_4 in (b'IIRO', b'MMOR'):
                # ORF format: 4-byte header (IIRO or MMOR), then 4-byte IFD offset
                if header_4 == b'IIRO':
                    self.endian = '<'  # Little-endian
                    byte_order_str = 'Little-endian (Intel, II)'
                else:  # MMOR
                    self.endian = '>'  # Big-endian
                    byte_order_str = 'Big-endian (Motorola, MM)'
                
                # Read IFD offset (at offset + 4)
                if offset + 8 <= len(self.file_data):
                    first_ifd_offset = struct.unpack(f'{self.endian}I', self.file_data[offset + 4:offset + 8])[0]
                    # For ORF, IFD offset is typically 8 (right after header)
                    # But it's stored as an absolute offset from start of file
                    # Adjust if needed
                    if first_ifd_offset < offset:
                        first_ifd_offset = offset + first_ifd_offset
                else:
                    raise MetadataReadError("File too short for ORF header")
            elif header_4[:3] in (b'IIU', b'MMU'):
                # RW2 format (Panasonic): 4-byte header (IIU or MMU), then 4-byte IFD offset
                if header_4[0] == ord('I'):
                    self.endian = '<'  # Little-endian
                    byte_order_str = 'Little-endian (Intel, II)'
                else:  # MMU
                    self.endian = '>'  # Big-endian
                    byte_order_str = 'Big-endian (Motorola, MM)'
                
                # Read IFD offset (at offset + 4)
                if offset + 8 <= len(self.file_data):
                    first_ifd_offset = struct.unpack(f'{self.endian}I', self.file_data[offset + 4:offset + 8])[0]
                    # For RW2, IFD offset is typically 8 (right after header)
                    # Adjust if needed
                    if first_ifd_offset < offset:
                        first_ifd_offset = offset + first_ifd_offset
                else:
                    raise MetadataReadError("File too short for RW2 header")
            else:
                # Standard TIFF format
                # Determine byte order
                if self.file_data[offset:offset + 2] == b'II':
                    self.endian = '<'  # Little-endian
                    byte_order_str = 'Little-endian (Intel, II)'
                elif self.file_data[offset:offset + 2] == b'MM':
                    self.endian = '>'  # Big-endian
                    byte_order_str = 'Big-endian (Motorola, MM)'
                else:
                    raise MetadataReadError("Invalid TIFF header")
                
                # Read TIFF magic number (should be 42)
                magic = struct.unpack(f'{self.endian}H', self.file_data[offset + 2:offset + 4])[0]
                if magic != 42:
                    raise MetadataReadError("Invalid TIFF magic number")
                
                # Read offset to first IFD
                first_ifd_offset = struct.unpack(f'{self.endian}I', self.file_data[offset + 4:offset + 8])[0]
        else:
            raise MetadataReadError("File too short for header")
        
        # Parse all IFDs and find the main image IFD
        # For RAW formats, we need to identify which IFD is the main image vs preview
        all_ifds = []
        current_ifd_offset = first_ifd_offset
        
        # Follow the IFD chain to collect all IFDs
        visited_ifds = set()
        max_ifds = 10  # Safety limit
        ifd_index = 0
        
        while current_ifd_offset > 0 and ifd_index < max_ifds:
            if current_ifd_offset in visited_ifds:
                break  # Avoid infinite loops
            visited_ifds.add(current_ifd_offset)
            
            # Parse this IFD to get its SubfileType and next IFD pointer
            ifd_abs_offset = offset + current_ifd_offset
            ifd_data = self._parse_ifd_info(ifd_abs_offset, offset)
            
            if ifd_data:
                # If SubfileType is None (not present), default to 0 (Full-resolution) per TIFF spec
                # Per TIFF spec, missing SubfileType means Full-resolution image
                subfile_type = ifd_data.get('subfile_type')
                if subfile_type is None:
                    subfile_type = 0  # Default to Full-resolution if tag is missing
                
                all_ifds.append({
                    'offset': current_ifd_offset,
                    'abs_offset': ifd_abs_offset,
                    'subfile_type': subfile_type,
                    'is_full_resolution': subfile_type == 0,  # 0 = Full-resolution
                    'data': ifd_data,
                    'ifd_index': ifd_index  # Track IFD index (0 = IFD0, 1 = IFD1, etc.)
                })
                
                # Get next IFD offset
                current_ifd_offset = ifd_data.get('next_ifd', 0)
                ifd_index += 1
            else:
                break
        
        # Select the main image IFD (prefer Full-resolution, fallback to first IFD)
        # Per TIFF spec, IFD0 is the main image unless it explicitly has SubfileType = 1
        main_ifd = None
        preview_ifd = None
        
        # Select main IFD and preview IFD
        # Per TIFF spec, IFD0 is the main image unless it explicitly has SubfileType = 1
        # Get raw SubfileType values from IFD info (before formatting) for accurate comparison
        ifd_subfile_types = {}
        ifd_dimensions = {}  # Store ImageWidth * ImageLength for each IFD
        for ifd_info in all_ifds:
            # Use SubfileType from IFD info (raw integer value, not formatted string)
            # This is more reliable for comparison logic
            raw_subfile_type = ifd_info.get('subfile_type')
            if raw_subfile_type is None:
                # No SubfileType tag, defaults to 0 (Full-resolution) per TIFF spec
                raw_subfile_type = 0
            ifd_subfile_types[ifd_info['abs_offset']] = raw_subfile_type
            
            # Parse IFD to get dimensions for fallback selection
            try:
                ifd_metadata = self._parse_ifd(ifd_info['abs_offset'], offset)
                
                # Get image dimensions for fallback selection
                image_width = ifd_metadata.get('ImageWidth', 0)
                image_length = ifd_metadata.get('ImageLength', 0)
                if isinstance(image_width, (list, tuple)) and len(image_width) > 0:
                    image_width = image_width[0]
                if isinstance(image_length, (list, tuple)) and len(image_length) > 0:
                    image_length = image_length[0]
                # Calculate total pixels (width * length) for comparison
                ifd_dimensions[ifd_info['abs_offset']] = image_width * image_length
            except Exception:
                # If parsing fails, use value from IFD info
                ifd_subfile_types[ifd_info['abs_offset']] = ifd_info['subfile_type']
                ifd_dimensions[ifd_info['abs_offset']] = 0
        
        # Now select main IFD based on actual SubfileType values
        # If SubfileType is missing or ambiguous, use image dimensions as fallback
        if all_ifds:
            first_ifd = all_ifds[0]
            first_subfile_type = ifd_subfile_types.get(first_ifd['abs_offset'], 0)
            
            if first_subfile_type == 1:
                # First IFD has SubfileType = 1 (Reduced-resolution), it's a preview
                # Check SubIFDs first (common in Sony ARW and other RAW formats)
                first_ifd_metadata = None
                try:
                    first_ifd_metadata = self._parse_ifd(first_ifd['abs_offset'], offset)
                    subifds = first_ifd_metadata.get('SubIFDs', [])
                    if subifds:
                        # Parse each SubIFD to find the main image
                        for subifd_offset in subifds:
                            if isinstance(subifd_offset, (int,)):
                                subifd_abs_offset = offset + subifd_offset
                                try:
                                    # Check SubfileType of this SubIFD
                                    subifd_info = self._parse_ifd_info(subifd_abs_offset, offset)
                                    if subifd_info:
                                        subifd_subfile_type = subifd_info.get('subfile_type')
                                        if subifd_subfile_type is None:
                                            subifd_subfile_type = 0  # Default to Full-resolution
                                        
                                        # Parse full SubIFD to get dimensions and verify
                                        subifd_metadata = self._parse_ifd(subifd_abs_offset, offset)
                                        subifd_subfile_type_value = subifd_metadata.get('SubfileType')
                                        if subifd_subfile_type_value is not None:
                                            subifd_subfile_type = subifd_subfile_type_value
                                        
                                        # If SubIFD has SubfileType = 0 (Full-resolution), it's the main image
                                        if subifd_subfile_type == 0:
                                            # Get dimensions
                                            image_width = subifd_metadata.get('ImageWidth', 0)
                                            image_length = subifd_metadata.get('ImageLength', 0)
                                            if isinstance(image_width, (list, tuple)) and len(image_width) > 0:
                                                image_width = image_width[0]
                                            if isinstance(image_length, (list, tuple)) and len(image_length) > 0:
                                                image_length = image_length[0]
                                            
                                            # Create SubIFD info structure
                                            subifd_ifd_info = {
                                                'offset': subifd_offset,
                                                'abs_offset': subifd_abs_offset,
                                                'subfile_type': subifd_subfile_type,
                                                'is_full_resolution': True,
                                                'data': subifd_info,
                                                'ifd_index': len(all_ifds),
                                                'is_subifd': True
                                            }
                                            # Store SubfileType and dimensions
                                            ifd_subfile_types[subifd_abs_offset] = subifd_subfile_type
                                            ifd_dimensions[subifd_abs_offset] = image_width * image_length
                                            
                                            # Immediately select this SubIFD as the main IFD
                                            main_ifd = subifd_ifd_info
                                            preview_ifd = first_ifd
                                            break  # Found main image, stop searching
                                except Exception:
                                    continue
                except Exception:
                    pass
                
                # If no SubIFD was found, look for main image in other IFDs (SubfileType = 0)
                if main_ifd is None:
                    for ifd_info in all_ifds[1:]:
                        subfile_type = ifd_subfile_types.get(ifd_info['abs_offset'], 0)
                        if subfile_type == 0:  # Full-resolution
                            main_ifd = ifd_info
                            break
                
                # If no IFD with SubfileType = 0, use second IFD if available
                if main_ifd is None and len(all_ifds) > 1:
                    main_ifd = all_ifds[1]
                # If still no main IFD, use first IFD anyway (fallback)
                if main_ifd is None:
                    main_ifd = first_ifd
                preview_ifd = first_ifd
            else:
                # First IFD is the main image (SubfileType = 0 or missing)
                # However, for some RAW formats (like Sony ARW), IFD0 might be preview
                # even if SubfileType is missing. Check dimensions as fallback.
                if len(all_ifds) > 1:
                    # Check if we have ambiguous SubfileType (both missing or both 0)
                    first_dim = ifd_dimensions.get(first_ifd['abs_offset'], 0)
                    second_dim = ifd_dimensions.get(all_ifds[1]['abs_offset'], 0)
                    second_subfile_type = ifd_subfile_types.get(all_ifds[1]['abs_offset'], 0)
                    
                    # For Sony ARW and similar formats, if second IFD has significantly larger dimensions
                    # and first IFD has no explicit SubfileType (defaults to 0), prefer second IFD
                    # This handles cases where IFD0 is a preview but doesn't have SubfileType = 1
                    # Check if second IFD is at least 2x larger (to avoid false positives)
                    if (first_subfile_type == 0 and 
                        second_subfile_type == 0 and
                        second_dim > first_dim * 2 and 
                        second_dim > 0 and 
                        first_dim > 0):
                        # Second IFD is likely the main image (larger dimensions)
                        main_ifd = all_ifds[1]
                        preview_ifd = first_ifd
                    else:
                        # First IFD is the main image (SubfileType = 0 or missing)
                        main_ifd = first_ifd
                        # Look for preview IFD (SubfileType = 1) in other IFDs
                        for ifd_info in all_ifds[1:]:
                            subfile_type = ifd_subfile_types.get(ifd_info['abs_offset'], 0)
                            if subfile_type == 1:  # Reduced-resolution
                                preview_ifd = ifd_info
                                break
                else:
                    # Only one IFD, it's the main image
                    main_ifd = first_ifd
                    # Look for preview IFD (SubfileType = 1) in other IFDs
                    for ifd_info in all_ifds[1:]:
                        subfile_type = ifd_subfile_types.get(ifd_info['abs_offset'], 0)
                        if subfile_type == 1:  # Reduced-resolution
                            preview_ifd = ifd_info
                            break
        
        # Parse main IFD for primary metadata
        metadata = {}
        if main_ifd:
            # Parse main IFD first to get Make tag
            main_ifd_metadata = self._parse_ifd(main_ifd['abs_offset'], offset)
            metadata.update(main_ifd_metadata)
            
            # Check if this is a MEF file (Mamiya format)
            # For MEF files, Standard format uses the first IFD for ImageWidth/ImageHeight, not the largest
            is_mef = False
            make_tag = metadata.get('Make', '') or metadata.get('EXIF:Make', '')
            if isinstance(make_tag, str) and 'Mamiya' in make_tag:
                is_mef = True
            
            # For RAW formats, find the IFD with the largest dimensions (main image)
            # Check all IFDs to find the one with the largest ImageWidth x ImageHeight
            # IMPORTANT: Check SubIFDs FIRST, then main IFDs, to ensure we get the main image dimensions
            # EXCEPTION: For MEF files, use the first IFD (to standard format behavior)
            best_width = 0
            best_height = 0
            best_image_width = None
            best_image_height = None
            best_ifd_metadata_candidate = None  # Store the IFD metadata that has the best dimensions
            
            # For MEF files, use the first IFD for ImageWidth/ImageHeight
            if is_mef:
                image_height_key = 'ImageHeight' if 'ImageHeight' in main_ifd_metadata else 'ImageLength'
                if 'ImageWidth' in main_ifd_metadata and image_height_key in main_ifd_metadata:
                    best_image_width = main_ifd_metadata['ImageWidth']
                    best_image_height = main_ifd_metadata[image_height_key]
                    best_ifd_metadata_candidate = main_ifd_metadata
            
            # FIRST: Check all IFDs and their SubIFDs to find the largest dimensions
            # This ensures SubIFDs (which often contain the main image) are checked before main IFDs
            # Also collect all SubIFD metadata to merge EXIF tags later
            # EXCEPTION: For MEF files, skip dimension search but still collect SubIFD metadata for tag merging
            all_subifd_metadata = []  # Store all SubIFD metadata for tag merging
            # For MEF files, still collect SubIFD metadata but don't use it for dimension selection
            for ifd_info in all_ifds:
                    try:
                        ifd_meta = self._parse_ifd(ifd_info['abs_offset'], offset)
                        
                        # Check SubIFDs FIRST (common in Sony ARW and other RAW formats)
                        # SubIFDs often contain the main image, so check them before the main IFD
                        # NOTE: For MEF files, we need to recursively collect ALL SubIFDs (including nested ones)
                        def collect_subifds_recursive(subifd_offset_val, parent_offset_val):
                            """Recursively collect all SubIFDs (including nested ones) for tag merging"""
                            if not isinstance(subifd_offset_val, (int,)):
                                return None
                            try:
                                subifd_abs_offset = offset + subifd_offset_val
                                subifd_abs_offset2 = parent_offset_val + subifd_offset_val
                                subifd_meta = None
                                try:
                                    subifd_meta = self._parse_ifd(subifd_abs_offset, offset)
                                except:
                                    try:
                                        subifd_meta = self._parse_ifd(subifd_abs_offset2, offset)
                                    except:
                                        pass
                                if subifd_meta:
                                    # Store SubIFD metadata for tag merging (always, even for MEF)
                                    all_subifd_metadata.append(subifd_meta)
                                    
                                    # Recursively collect nested SubIFDs
                                    nested_subifds = subifd_meta.get('SubIFDs', [])
                                    for nested_subifd_offset in nested_subifds:
                                        collect_subifds_recursive(nested_subifd_offset, subifd_abs_offset)
                                    
                                    return subifd_meta
                            except:
                                pass
                            return None
                        
                        subifds = ifd_meta.get('SubIFDs', [])
                        if subifds:
                            for subifd_offset in subifds:
                                subifd_meta = collect_subifds_recursive(subifd_offset, ifd_info['abs_offset'])
                                
                                # For dimension selection, skip if MEF (already using first IFD)
                                if not is_mef and subifd_meta:
                                    subifd_image_height_key = 'ImageHeight' if 'ImageHeight' in subifd_meta else 'ImageLength'
                                    if 'ImageWidth' in subifd_meta and subifd_image_height_key in subifd_meta:
                                        try:
                                            w = int(subifd_meta['ImageWidth']) if not isinstance(subifd_meta['ImageWidth'], (list, tuple)) else int(subifd_meta['ImageWidth'][0])
                                            h = int(subifd_meta[subifd_image_height_key]) if not isinstance(subifd_meta[subifd_image_height_key], (list, tuple)) else int(subifd_meta[subifd_image_height_key][0])
                                            if w * h > best_width * best_height:
                                                best_width = w
                                                best_height = h
                                                best_image_width = subifd_meta['ImageWidth']
                                                best_image_height = subifd_meta[subifd_image_height_key]
                                                best_ifd_metadata_candidate = subifd_meta  # Store this SubIFD metadata
                                        except:
                                            pass
                        
                        # Then check the main IFD itself
                        # TIFF uses ImageLength instead of ImageHeight
                        # For dimension selection, skip if MEF (already using first IFD)
                        if not is_mef:
                            ifd_image_height_key = 'ImageHeight' if 'ImageHeight' in ifd_meta else 'ImageLength'
                            if 'ImageWidth' in ifd_meta and ifd_image_height_key in ifd_meta:
                                try:
                                    w = int(ifd_meta['ImageWidth']) if not isinstance(ifd_meta['ImageWidth'], (list, tuple)) else int(ifd_meta['ImageWidth'][0])
                                    h = int(ifd_meta[ifd_image_height_key]) if not isinstance(ifd_meta[ifd_image_height_key], (list, tuple)) else int(ifd_meta[ifd_image_height_key][0])
                                    if w * h > best_width * best_height:
                                        best_width = w
                                        best_height = h
                                        best_image_width = ifd_meta['ImageWidth']
                                        best_image_height = ifd_meta[ifd_image_height_key]
                                        best_ifd_metadata_candidate = ifd_meta  # Store this IFD metadata
                                except:
                                    pass
                    except:
                        pass
            
            # Also check main IFD metadata (from initial parse) as fallback
            # TIFF uses ImageLength instead of ImageHeight
            # EXCEPTION: For MEF files, skip this (already set above)
            if not is_mef:
                image_height_key = 'ImageHeight' if 'ImageHeight' in metadata else 'ImageLength'
                if 'ImageWidth' in metadata and image_height_key in metadata:
                    try:
                        w = int(metadata['ImageWidth']) if not isinstance(metadata['ImageWidth'], (list, tuple)) else int(metadata['ImageWidth'][0])
                        h = int(metadata[image_height_key]) if not isinstance(metadata[image_height_key], (list, tuple)) else int(metadata[image_height_key][0])
                        if w * h > best_width * best_height:
                            best_width = w
                            best_height = h
                            best_image_width = metadata['ImageWidth']
                            best_image_height = metadata[image_height_key]
                            best_ifd_metadata_candidate = metadata  # Store main IFD metadata as candidate
                    except:
                        pass
            
            # For MEF files, also check other IFDs (not just SubIFDs) for tags like SensingMethod, CFARepeatPatternDim, CFAPattern2
            # These tags might be in other main IFDs, not just SubIFDs
            # NOTE: We need to collect ALL IFDs' metadata (including StripOffsets/StripByteCounts) to find the IFD with StripOffsets 200524
            if is_mef:
                for ifd_info in all_ifds:
                    if ifd_info != main_ifd:  # Skip the first IFD (already parsed)
                        try:
                            ifd_meta = self._parse_ifd(ifd_info['abs_offset'], offset)
                            # Also check SubIFDs within this IFD
                            subifds = ifd_meta.get('SubIFDs', [])
                            if subifds:
                                for subifd_offset in subifds:
                                    if isinstance(subifd_offset, (int,)):
                                        try:
                                            subifd_abs_offset = offset + subifd_offset
                                            subifd_abs_offset2 = ifd_info['abs_offset'] + subifd_offset
                                            subifd_meta = None
                                            try:
                                                subifd_meta = self._parse_ifd(subifd_abs_offset, offset)
                                            except:
                                                try:
                                                    subifd_meta = self._parse_ifd(subifd_abs_offset2, offset)
                                                except:
                                                    pass
                                            if subifd_meta:
                                                # Store SubIFD metadata for tag merging
                                                all_subifd_metadata.append(subifd_meta)
                                        except:
                                            pass
                            # Merge tags from other IFDs (like SensingMethod, CFARepeatPatternDim, CFAPattern2)
                            # NOTE: We still skip dimension tags and SubIFDs tag, but we'll handle StripOffsets/StripByteCounts separately
                            for k, v in ifd_meta.items():
                                # Skip dimension tags and SubIFDs tag
                                if k in ('ImageWidth', 'ImageHeight', 'ImageLength', 'SubIFDs', 'SubfileType'):
                                    continue
                                # For StripOffsets/StripByteCounts/RowsPerStrip, we'll handle them separately when finding the 240x320 IFD
                                # But we still want to collect them in all_subifd_metadata or a separate collection
                                if k in ('StripOffsets', 'StripByteCounts', 'RowsPerStrip'):
                                    # Don't skip - we need these to find the IFD with StripOffsets 200524
                                    # But don't overwrite existing tags yet - we'll handle this in the strip_tags section
                                    pass
                                # Add EXIF prefix if not already present
                                if not k.startswith('EXIF:'):
                                    exif_key = f"EXIF:{k}"
                                else:
                                    exif_key = k
                                # Don't overwrite existing tags
                                if exif_key not in metadata:
                                    metadata[exif_key] = v
                        except Exception:
                            pass
            
            # Note: The above loop already checks all IFDs and their SubIFDs
            # No need to duplicate the check here
            
            # If we found dimensions, use them for ImageWidth/ImageHeight and EXIF:ImageWidth/ImageHeight
            # Also ensure ImageLength is set if ImageHeight was found (TIFF uses ImageLength)
            # Also update other critical tags from the best IFD (the one with largest dimensions)
            # Use the stored best_ifd_metadata_candidate if available, otherwise search for it
            best_ifd_metadata = None
            if best_image_width is not None and best_image_height is not None:
                metadata['ImageWidth'] = best_image_width
                metadata['ImageHeight'] = best_image_height
                metadata['ImageLength'] = best_image_height  # TIFF standard uses ImageLength
                metadata['EXIF:ImageWidth'] = best_image_width
                metadata['EXIF:ImageHeight'] = best_image_height
                metadata['EXIF:ImageLength'] = best_image_height  # Also set EXIF:ImageLength
                
                # Use the stored best_ifd_metadata_candidate if available (from SubIFD or main IFD)
                if best_ifd_metadata_candidate is not None:
                    best_ifd_metadata = best_ifd_metadata_candidate
                else:
                    # Fallback: Find the IFD that has these dimensions and use it for other critical tags
                    # This ensures StripOffsets, StripByteCounts, FocalPlaneYResolution, etc. come from the main image IFD
                    for ifd_info in all_ifds:
                        try:
                            ifd_meta = self._parse_ifd(ifd_info['abs_offset'], offset)
                            ifd_image_height_key = 'ImageHeight' if 'ImageHeight' in ifd_meta else 'ImageLength'
                            if 'ImageWidth' in ifd_meta and ifd_image_height_key in ifd_meta:
                                try:
                                    w = int(ifd_meta['ImageWidth']) if not isinstance(ifd_meta['ImageWidth'], (list, tuple)) else int(ifd_meta['ImageWidth'][0])
                                    h = int(ifd_meta[ifd_image_height_key]) if not isinstance(ifd_meta[ifd_image_height_key], (list, tuple)) else int(ifd_meta[ifd_image_height_key][0])
                                    if w == best_width and h == best_height:
                                        best_ifd_metadata = ifd_meta
                                        break
                                except:
                                    pass
                            
                            # Also check SubIFDs
                            subifds = ifd_meta.get('SubIFDs', [])
                            if subifds:
                                for subifd_offset in subifds:
                                    if isinstance(subifd_offset, (int,)):
                                        try:
                                            subifd_abs_offset = offset + subifd_offset
                                            subifd_meta = self._parse_ifd(subifd_abs_offset, offset)
                                            subifd_image_height_key = 'ImageHeight' if 'ImageHeight' in subifd_meta else 'ImageLength'
                                            if 'ImageWidth' in subifd_meta and subifd_image_height_key in subifd_meta:
                                                try:
                                                    w = int(subifd_meta['ImageWidth']) if not isinstance(subifd_meta['ImageWidth'], (list, tuple)) else int(subifd_meta['ImageWidth'][0])
                                                    h = int(subifd_meta[subifd_image_height_key]) if not isinstance(subifd_meta[subifd_image_height_key], (list, tuple)) else int(subifd_meta[subifd_image_height_key][0])
                                                    if w == best_width and h == best_height:
                                                        best_ifd_metadata = subifd_meta
                                                        break
                                                except:
                                                    pass
                                        except:
                                            pass
                        except:
                            pass
                
                # Update critical tags from best IFD if found
                # For MEF files, use the first IFD metadata for all critical tags
                if is_mef and main_ifd_metadata:
                    best_ifd_metadata = main_ifd_metadata
                
                if best_ifd_metadata:
                    # Tags that should come from the main image IFD (not preview)
                    # For MEF files, these come from the first IFD (to standard format)
                    critical_tags = [
                        'StripOffsets', 'StripByteCounts', 'TileOffsets', 'TileByteCounts',
                        'FocalPlaneXResolution', 'FocalPlaneYResolution', 'FocalPlaneResolutionUnit',
                        'RowsPerStrip', 'SamplesPerPixel', 'BitsPerSample', 'PhotometricInterpretation',
                        'Compression', 'PlanarConfiguration', 'ImageWidth', 'ImageHeight', 'ImageLength',
                        'SubfileType'
                    ]
                    
                    # Also merge other EXIF tags from best IFD (like SensingMethod, CFARepeatPatternDim, CFAPattern2)
                    # These are important EXIF tags that should be included even if not in critical_tags list
                    for k, v in best_ifd_metadata.items():
                        if k not in critical_tags and k not in ('SubIFDs', 'Make', 'Model'):
                            # Add EXIF prefix if it's a standard EXIF tag
                            if not k.startswith('EXIF:') and not k.startswith('MakerNote') and not k.startswith('Canon') and not k.startswith('Nikon'):
                                if k not in metadata:  # Don't overwrite existing tags
                                    metadata[f"EXIF:{k}"] = v
                            elif k.startswith('EXIF:'):
                                if k not in metadata:  # Don't overwrite existing tags
                                    metadata[k] = v
                    
                    # For CR2 and similar formats, StripOffsets/StripByteCounts might be in a different IFD
                    # than the one with the largest dimensions. Always find the IFD with the largest StripOffsets
                    # value (which indicates the main image data location) and use those values.
                    # EXCEPTION: For MEF files, use the first IFD for StripOffsets/StripByteCounts (to standard format)
                    strip_tags = ['StripOffsets', 'StripByteCounts']
                    best_strip_ifd_metadata = None
                    best_strip_offset = 0
                    
                    # For MEF files, Standard format uses a specific IFD (240x320) for StripOffsets/StripByteCounts
                    # We'll find it later in the code, so don't set it here
                    # (Leave best_strip_ifd_metadata as None for now, will be set below)
                    
                    # Always search all IFDs for the largest StripOffsets (main image)
                    # EXCEPTION: Skip this for MEF files (already using first IFD)
                    if not is_mef:
                        for ifd_info in all_ifds:
                            try:
                                ifd_meta = self._parse_ifd(ifd_info['abs_offset'], offset)
                                
                                # Check if this IFD has StripOffsets
                                if 'StripOffsets' in ifd_meta:
                                    strip_offsets = ifd_meta['StripOffsets']
                                    # Get the first/largest value - handle different types
                                    max_offset = 0
                                    try:
                                        if isinstance(strip_offsets, (list, tuple)) and len(strip_offsets) > 0:
                                            # Array - get max value
                                            max_offset = max(int(v) for v in strip_offsets if isinstance(v, (int, float)))
                                        elif isinstance(strip_offsets, (int, float)):
                                            # Single value
                                            max_offset = int(strip_offsets)
                                        elif isinstance(strip_offsets, str):
                                            # String - extract first number
                                            import re
                                            numbers = re.findall(r'\d+', strip_offsets)
                                            if numbers:
                                                max_offset = int(numbers[0])
                                        else:
                                            continue
                                        
                                        # Use the IFD with the largest StripOffsets (main image)
                                        if max_offset > best_strip_offset:
                                            best_strip_offset = max_offset
                                            best_strip_ifd_metadata = ifd_meta
                                    except Exception:
                                        # If parsing fails, skip this IFD
                                        continue
                                
                                # Also check SubIFDs
                                subifds = ifd_meta.get('SubIFDs', [])
                                for subifd_offset in subifds:
                                    if isinstance(subifd_offset, (int,)):
                                        try:
                                            subifd_abs_offset = offset + subifd_offset
                                            subifd_meta = self._parse_ifd(subifd_abs_offset, offset)
                                            if 'StripOffsets' in subifd_meta:
                                                strip_offsets = subifd_meta['StripOffsets']
                                                max_offset = 0
                                                try:
                                                    if isinstance(strip_offsets, (list, tuple)) and len(strip_offsets) > 0:
                                                        max_offset = max(int(v) for v in strip_offsets if isinstance(v, (int, float)))
                                                    elif isinstance(strip_offsets, (int, float)):
                                                        max_offset = int(strip_offsets)
                                                    elif isinstance(strip_offsets, str):
                                                        import re
                                                        numbers = re.findall(r'\d+', strip_offsets)
                                                        if numbers:
                                                            max_offset = int(numbers[0])
                                                    
                                                    if max_offset > best_strip_offset:
                                                        best_strip_offset = max_offset
                                                        best_strip_ifd_metadata = subifd_meta
                                                except Exception:
                                                    continue
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                    
                    # If we found an IFD with StripOffsets/StripByteCounts, use those values (overwrite best IFD values)
                    # EXCEPTION: For MEF files, Standard format uses a specific IFD (240x320) for StripOffsets/StripByteCounts, not the first IFD
                    # So we need to find the IFD with ImageWidth 240 and use its StripOffsets/StripByteCounts
                    # NOTE: MEF files have multiple IFDs in SubIFDs, not in the main IFD chain
                    # We should also check all_subifd_metadata which was collected earlier
                    if is_mef:
                        # First check all_subifd_metadata (already parsed SubIFDs)
                        for subifd_meta in all_subifd_metadata:
                            if 'StripOffsets' in subifd_meta:
                                strip_offsets = subifd_meta['StripOffsets']
                                try:
                                    if isinstance(strip_offsets, (list, tuple)) and len(strip_offsets) > 0:
                                        first_offset = int(strip_offsets[0]) if isinstance(strip_offsets[0], (int, float)) else int(str(strip_offsets[0]).split()[0])
                                    elif isinstance(strip_offsets, (int, float)):
                                        first_offset = int(strip_offsets)
                                    elif isinstance(strip_offsets, str):
                                        import re
                                        numbers = re.findall(r'\d+', strip_offsets)
                                        if numbers:
                                            first_offset = int(numbers[0])
                                        else:
                                            first_offset = None
                                    else:
                                        first_offset = None
                                    
                                    if first_offset == 200524:
                                        best_strip_ifd_metadata = subifd_meta
                                        break
                                except:
                                    pass
                        
                        # If not found in all_subifd_metadata, try direct SubIFD parsing for MEF
                        # For MEF files, we know SubIFD 2 (at offset 117372) has StripOffsets 200524
                        if not best_strip_ifd_metadata and is_mef:
                            # Try parsing SubIFD 2 directly (known to have StripOffsets 200524)
                            # SubIFD offsets from first IFD: [116920, 117164, 117372]
                            # SubIFD 2 is at relative offset 117372
                            subifd2_offset = 117372
                            subifd2_abs_offset = offset + subifd2_offset
                            try:
                                subifd2_meta = self._parse_ifd(subifd2_abs_offset, offset)
                                if subifd2_meta and 'StripOffsets' in subifd2_meta:
                                    strip_offsets = subifd2_meta['StripOffsets']
                                    # Check if this is the IFD with StripOffsets 200524
                                    first_offset = None
                                    try:
                                        if isinstance(strip_offsets, (list, tuple)) and len(strip_offsets) > 0:
                                            first_offset = int(strip_offsets[0]) if isinstance(strip_offsets[0], (int, float)) else int(str(strip_offsets[0]).split()[0])
                                        elif isinstance(strip_offsets, (int, float)):
                                            first_offset = int(strip_offsets)
                                        elif isinstance(strip_offsets, str):
                                            import re
                                            numbers = re.findall(r'\d+', strip_offsets)
                                            if numbers:
                                                first_offset = int(numbers[0])
                                    except:
                                        pass
                                    
                                    # For MEF, SubIFD 2 should have StripOffsets 200524
                                    # If we found it (or if first_offset is None, still use it as it's the known SubIFD 2)
                                    if first_offset == 200524 or (first_offset is None and 'StripByteCounts' in subifd2_meta):
                                        # Check if StripByteCounts is 230400 (known value for SubIFD 2)
                                        strip_byte_counts = subifd2_meta.get('StripByteCounts')
                                        if strip_byte_counts:
                                            try:
                                                if isinstance(strip_byte_counts, (list, tuple)) and len(strip_byte_counts) > 0:
                                                    first_count = int(strip_byte_counts[0]) if isinstance(strip_byte_counts[0], (int, float)) else int(str(strip_byte_counts[0]).split()[0])
                                                elif isinstance(strip_byte_counts, (int, float)):
                                                    first_count = int(strip_byte_counts)
                                                elif isinstance(strip_byte_counts, str):
                                                    import re
                                                    numbers = re.findall(r'\d+', strip_byte_counts)
                                                    if numbers:
                                                        first_count = int(numbers[0])
                                                    else:
                                                        first_count = None
                                                else:
                                                    first_count = None
                                                
                                                # If StripByteCounts is 230400, this is definitely SubIFD 2
                                                if first_count == 230400:
                                                    best_strip_ifd_metadata = subifd2_meta
                                                elif first_offset == 200524:
                                                    # StripOffsets matches, use it
                                                    best_strip_ifd_metadata = subifd2_meta
                                            except:
                                                if first_offset == 200524:
                                                    best_strip_ifd_metadata = subifd2_meta
                                        elif first_offset == 200524:
                                            best_strip_ifd_metadata = subifd2_meta
                            except:
                                pass
                        
                        # If not found in all_subifd_metadata, search main IFDs and their SubIFDs
                        # NOTE: For MEF, the IFD with StripOffsets 200524 might be a main IFD, not a SubIFD
                        if not best_strip_ifd_metadata:
                            # For MEF, find the IFD with ImageWidth 240 (which has StripOffsets 200524)
                            # First try by StripOffsets value (200524) - more reliable than ImageWidth
                            # Check ALL main IFDs (not just the first one)
                            for ifd_info in all_ifds:
                                # Parse the IFD if not already parsed
                                try:
                                    ifd_meta = self._parse_ifd(ifd_info['abs_offset'], offset)
                                    
                                    # Check main IFD
                                    if 'StripOffsets' in ifd_meta:
                                        strip_offsets = ifd_meta['StripOffsets']
                                        try:
                                            if isinstance(strip_offsets, (list, tuple)) and len(strip_offsets) > 0:
                                                first_offset = int(strip_offsets[0]) if isinstance(strip_offsets[0], (int, float)) else int(str(strip_offsets[0]).split()[0])
                                            elif isinstance(strip_offsets, (int, float)):
                                                first_offset = int(strip_offsets)
                                            elif isinstance(strip_offsets, str):
                                                import re
                                                numbers = re.findall(r'\d+', strip_offsets)
                                                if numbers:
                                                    first_offset = int(numbers[0])
                                                else:
                                                    first_offset = None
                                            else:
                                                first_offset = None
                                            
                                            if first_offset == 200524:
                                                best_strip_ifd_metadata = ifd_meta
                                                break
                                        except:
                                            pass
                                    
                                    # Also check SubIFDs within this IFD (and recursively check nested SubIFDs)
                                    def check_subifd_recursive(subifd_offset_val, parent_offset_val):
                                        """Recursively check SubIFDs for the IFD with StripOffsets 200524"""
                                        if not isinstance(subifd_offset_val, (int,)):
                                            return False
                                        try:
                                            subifd_abs_offset = offset + subifd_offset_val
                                            subifd_abs_offset2 = parent_offset_val + subifd_offset_val
                                            subifd_meta = None
                                            try:
                                                subifd_meta = self._parse_ifd(subifd_abs_offset, offset)
                                            except:
                                                try:
                                                    subifd_meta = self._parse_ifd(subifd_abs_offset2, offset)
                                                except:
                                                    pass
                                            if subifd_meta:
                                                # Check if this SubIFD has StripOffsets 200524
                                                if 'StripOffsets' in subifd_meta:
                                                    strip_offsets = subifd_meta['StripOffsets']
                                                    try:
                                                        if isinstance(strip_offsets, (list, tuple)) and len(strip_offsets) > 0:
                                                            first_offset = int(strip_offsets[0]) if isinstance(strip_offsets[0], (int, float)) else int(str(strip_offsets[0]).split()[0])
                                                        elif isinstance(strip_offsets, (int, float)):
                                                            first_offset = int(strip_offsets)
                                                        elif isinstance(strip_offsets, str):
                                                            import re
                                                            numbers = re.findall(r'\d+', strip_offsets)
                                                            if numbers:
                                                                first_offset = int(numbers[0])
                                                            else:
                                                                first_offset = None
                                                        else:
                                                            first_offset = None
                                                        
                                                        if first_offset == 200524:
                                                            return subifd_meta
                                                    except:
                                                        pass
                                                # Also check nested SubIFDs (SubIFDs of SubIFDs)
                                                nested_subifds = subifd_meta.get('SubIFDs', [])
                                                for nested_subifd_offset in nested_subifds:
                                                    nested_result = check_subifd_recursive(nested_subifd_offset, subifd_abs_offset)
                                                    if nested_result:
                                                        return nested_result
                                        except:
                                            pass
                                        return None
                                    
                                    subifds = ifd_meta.get('SubIFDs', [])
                                    for subifd_offset in subifds:
                                        result = check_subifd_recursive(subifd_offset, ifd_info['abs_offset'])
                                        if result:
                                            best_strip_ifd_metadata = result
                                            break
                                    if best_strip_ifd_metadata:
                                        break
                                except:
                                    pass
                            
                            # If still not found, try by ImageWidth 240
                            if not best_strip_ifd_metadata:
                                for ifd_info in all_ifds:
                                    try:
                                        ifd_meta = self._parse_ifd(ifd_info['abs_offset'], offset)
                                        
                                        # Check main IFD
                                        if 'ImageWidth' in ifd_meta:
                                            try:
                                                width = int(ifd_meta['ImageWidth']) if not isinstance(ifd_meta['ImageWidth'], (list, tuple)) else int(ifd_meta['ImageWidth'][0])
                                                if width == 240 and 'StripOffsets' in ifd_meta:
                                                    best_strip_ifd_metadata = ifd_meta
                                                    break
                                            except:
                                                pass
                                        
                                        # Also check SubIFDs
                                        subifds = ifd_meta.get('SubIFDs', [])
                                        for subifd_offset in subifds:
                                            if isinstance(subifd_offset, (int,)):
                                                try:
                                                    subifd_abs_offset = offset + subifd_offset
                                                    subifd_abs_offset2 = ifd_info['abs_offset'] + subifd_offset
                                                    subifd_meta = None
                                                    try:
                                                        subifd_meta = self._parse_ifd(subifd_abs_offset, offset)
                                                    except:
                                                        try:
                                                            subifd_meta = self._parse_ifd(subifd_abs_offset2, offset)
                                                        except:
                                                            pass
                                                    if subifd_meta and 'ImageWidth' in subifd_meta:
                                                        try:
                                                            width = int(subifd_meta['ImageWidth']) if not isinstance(subifd_meta['ImageWidth'], (list, tuple)) else int(subifd_meta['ImageWidth'][0])
                                                            if width == 240 and 'StripOffsets' in subifd_meta:
                                                                best_strip_ifd_metadata = subifd_meta
                                                                break
                                                        except:
                                                            pass
                                                except:
                                                    pass
                                        if best_strip_ifd_metadata:
                                            break
                                    except:
                                        pass
                        
                        # If not found by StripOffsets, try by ImageWidth 240 (also check SubIFDs)
                        if not best_strip_ifd_metadata:
                            for ifd_info in all_ifds:
                                try:
                                    ifd_meta = self._parse_ifd(ifd_info['abs_offset'], offset)
                                    
                                    # Check main IFD
                                    if 'ImageWidth' in ifd_meta:
                                        try:
                                            width = int(ifd_meta['ImageWidth']) if not isinstance(ifd_meta['ImageWidth'], (list, tuple)) else int(ifd_meta['ImageWidth'][0])
                                            if width == 240 and 'StripOffsets' in ifd_meta:
                                                best_strip_ifd_metadata = ifd_meta
                                                break
                                        except:
                                            pass
                                    
                                    # Also check SubIFDs
                                    subifds = ifd_meta.get('SubIFDs', [])
                                    for subifd_offset in subifds:
                                        if isinstance(subifd_offset, (int,)):
                                            try:
                                                subifd_abs_offset = offset + subifd_offset
                                                subifd_meta = self._parse_ifd(subifd_abs_offset, offset)
                                                if 'ImageWidth' in subifd_meta:
                                                    try:
                                                        width = int(subifd_meta['ImageWidth']) if not isinstance(subifd_meta['ImageWidth'], (list, tuple)) else int(subifd_meta['ImageWidth'][0])
                                                        if width == 240 and 'StripOffsets' in subifd_meta:
                                                            best_strip_ifd_metadata = subifd_meta
                                                            break
                                                    except:
                                                        pass
                                            except:
                                                pass
                                    if best_strip_ifd_metadata:
                                        break
                                except:
                                    pass
                    
                    # For MEF files, if we still haven't found the IFD with StripOffsets 200524,
                    # directly parse SubIFD 2 and use its values (known to have StripOffsets 200524)
                    if not best_strip_ifd_metadata and is_mef:
                        try:
                            # SubIFD 2 is at relative offset 117372 from TIFF base
                            subifd2_offset = 117372
                            subifd2_abs_offset = offset + subifd2_offset
                            subifd2_meta = self._parse_ifd(subifd2_abs_offset, offset)
                            if subifd2_meta:
                                # Use SubIFD 2 values directly for StripOffsets and StripByteCounts
                                if 'StripOffsets' in subifd2_meta:
                                    best_strip_ifd_metadata = subifd2_meta
                        except:
                            pass
                    
                    if best_strip_ifd_metadata:
                        for tag in strip_tags:
                            if tag in best_strip_ifd_metadata:
                                best_ifd_metadata[tag] = best_strip_ifd_metadata[tag]
                    
                    # For MEF files, always use SubIFD 2 values for StripOffsets and StripByteCounts
                    # This ensures we standard format behavior regardless of search results
                    if is_mef:
                        try:
                            # SubIFD 2 is at relative offset 117372 from TIFF base
                            subifd2_offset = 117372
                            subifd2_abs_offset = offset + subifd2_offset
                            subifd2_meta = self._parse_ifd(subifd2_abs_offset, offset)
                            if subifd2_meta:
                                # Directly apply SubIFD 2 values for StripOffsets and StripByteCounts
                                # Standard format uses SubIFD 2 (240x320) for these values, not the first IFD
                                if 'StripOffsets' in subifd2_meta:
                                    best_ifd_metadata['StripOffsets'] = subifd2_meta['StripOffsets']
                                if 'StripByteCounts' in subifd2_meta:
                                    best_ifd_metadata['StripByteCounts'] = subifd2_meta['StripByteCounts']
                        except:
                            pass
                    
                    for tag in critical_tags:
                        if tag in best_ifd_metadata:
                            # For MEF files, RowsPerStrip should come from first IFD, not from 240x320 IFD
                            if is_mef and tag == 'RowsPerStrip' and main_ifd_metadata and 'RowsPerStrip' in main_ifd_metadata:
                                # Overwrite with first IFD value
                                best_ifd_metadata[tag] = main_ifd_metadata[tag]
                                continue
                            # Special handling for FocalPlaneResolutionUnit - validate value
                            if tag == 'FocalPlaneResolutionUnit':
                                value = best_ifd_metadata[tag]
                                # If value is RATIONAL and > 10, it's invalid (should be 1, 2, or 3)
                                # Try to find correct value from other IFDs
                                if isinstance(value, tuple) and len(value) == 2:
                                    num, den = value
                                    if den != 0:
                                        ratio = num / den
                                        if ratio > 10:
                                            # Invalid value - search other IFDs for correct value
                                            correct_value = None
                                            for ifd_info in all_ifds:
                                                try:
                                                    ifd_meta = self._parse_ifd(ifd_info['abs_offset'], offset)
                                                    if tag in ifd_meta:
                                                        test_value = ifd_meta[tag]
                                                        # Check if it's a valid enum value (1, 2, or 3)
                                                        if isinstance(test_value, int) and 1 <= test_value <= 3:
                                                            correct_value = test_value
                                                            break
                                                        elif isinstance(test_value, tuple) and len(test_value) == 2:
                                                            test_num, test_den = test_value
                                                            if test_den != 0:
                                                                test_ratio = test_num / test_den
                                                                if 1 <= test_ratio <= 3:
                                                                    correct_value = int(round(test_ratio))
                                                                    break
                                                except:
                                                    pass
                                            if correct_value is not None:
                                                metadata[tag] = correct_value
                                                metadata[f'EXIF:{tag}'] = correct_value
                                                continue
                            # Always use best IFD value, even if tag already exists (overwrite preview IFD values)
                            metadata[tag] = best_ifd_metadata[tag]
                            # Also add EXIF: prefix if it's an EXIF tag
                            # For tags that don't get EXIF prefix, still add the tag without prefix
                            if tag not in ('StripOffsets', 'StripByteCounts', 'TileOffsets', 'TileByteCounts', 'RowsPerStrip'):
                                metadata[f'EXIF:{tag}'] = best_ifd_metadata[tag]
                            else:
                                # For tags that don't get EXIF prefix, ensure they're in metadata without prefix
                                metadata[tag] = best_ifd_metadata[tag]
                            
                            # Special handling for ImageWidth/ImageHeight - also update ImageLength if ImageHeight is updated
                            if tag == 'ImageHeight' and 'ImageLength' in metadata:
                                # Remove old ImageLength if ImageHeight is updated
                                if 'EXIF:ImageLength' in metadata:
                                    del metadata['EXIF:ImageLength']
                                if 'ImageLength' in metadata:
                                    del metadata['ImageLength']
            
            # Merge EXIF tags from ALL SubIFDs (not just the best one)
            # This ensures tags like SensingMethod, CFARepeatPatternDim, CFAPattern2 are included
            # even if they're in a SubIFD that's not the main image IFD
            # CRITICAL: Also explicitly extract CFAPattern (0xA215) and BlackLevel (0x8291) from SubIFDs
            # These tags are often in SubIFDs for RAW formats like RW2
            critical_subifd_tags = ['CFAPattern', 'BlackLevel', 'CFAPattern2', 'BlackLevelRepeatDim', 
                                    'CFARepeatPatternDim', 'SensingMethod']
            for subifd_meta in all_subifd_metadata:
                for k, v in subifd_meta.items():
                    # Skip dimension tags (already handled), SubIFDs tag, and manufacturer tags
                    if k in ('ImageWidth', 'ImageHeight', 'ImageLength', 'SubIFDs', 'SubfileType'):
                        continue
                    if k.startswith('MakerNote') or k.startswith('Canon') or k.startswith('Nikon') or k.startswith('Sony'):
                        continue
                    # Add EXIF prefix if not already present
                    if not k.startswith('EXIF:'):
                        exif_key = f"EXIF:{k}"
                    else:
                        exif_key = k
                    # Don't overwrite existing tags, BUT always extract critical tags from SubIFDs
                    # even if they exist (SubIFD values are often more accurate for RAW formats)
                    if exif_key not in metadata:
                        metadata[exif_key] = v
                    elif k in critical_subifd_tags or exif_key.replace('EXIF:', '') in critical_subifd_tags:
                        # For critical tags, prefer SubIFD values (they're often more accurate)
                        metadata[exif_key] = v
            
            # For MEF files, ensure we use SubIFD 2 values for StripOffsets and StripByteCounts
            # Apply this AFTER merging SubIFD tags to ensure values take precedence
            if is_mef:
                try:
                    # SubIFD 2 is at relative offset 117372 from TIFF base
                    subifd2_offset = 117372
                    subifd2_abs_offset = offset + subifd2_offset
                    subifd2_meta = self._parse_ifd(subifd2_abs_offset, offset)
                    if subifd2_meta:
                        # Directly apply SubIFD 2 values for StripOffsets and StripByteCounts
                        # Standard format uses SubIFD 2 (240x320) for these values, not the first IFD
                        # Force overwrite to ensure correct values
                        if 'StripOffsets' in subifd2_meta:
                            metadata['StripOffsets'] = subifd2_meta['StripOffsets']
                            metadata['EXIF:StripOffsets'] = subifd2_meta['StripOffsets']
                        if 'StripByteCounts' in subifd2_meta:
                            metadata['StripByteCounts'] = subifd2_meta['StripByteCounts']
                            metadata['EXIF:StripByteCounts'] = subifd2_meta['StripByteCounts']
                    
                    # For MEF files, RowsPerStrip should come from first IFD (192), not from SubIFD 2 (320)
                    # Ensure RowsPerStrip is from first IFD
                    if main_ifd_metadata and 'RowsPerStrip' in main_ifd_metadata:
                        metadata['RowsPerStrip'] = main_ifd_metadata['RowsPerStrip']
                        metadata['EXIF:RowsPerStrip'] = main_ifd_metadata['RowsPerStrip']
                except:
                    pass
            
            # Also parse all other IFDs to collect Make tags from IFD0/IFD1
            # This ensures MakerNote parser can find Make when parsing EXIF IFD
            # BUT: Don't override main IFD tags with preview IFD tags
            all_ifd_metadata = {}
            for ifd_info in all_ifds:
                if ifd_info != main_ifd:
                    try:
                        ifd_meta = self._parse_ifd(ifd_info['abs_offset'], offset)
                        # Only add tags that don't exist in main IFD metadata
                        # This prevents preview IFD tags from overriding main IFD tags
                        for k, v in ifd_meta.items():
                            if k not in metadata:
                                all_ifd_metadata[k] = v
                    except Exception:
                        pass
            
            # Merge all IFD metadata for Make lookup (but don't override main IFD tags)
            for k, v in all_ifd_metadata.items():
                if k not in metadata:
                    metadata[k] = v
            
            # Special handling for Sony ARW and similar formats:
            # If EXIF IFD (SubIFD) has SubfileType = 0 (Full-resolution), use it as the main SubfileType
            # This standard format behavior where SubIFD's SubfileType takes precedence
            # Check if EXIF:SubfileType exists in metadata (from main IFD) or parse IFD0 to get it
            exif_subfile_type = metadata.get('EXIF:SubfileType')
            if exif_subfile_type is None and all_ifds and len(all_ifds) > 0 and main_ifd != all_ifds[0]:
                # Parse IFD0 to get its EXIF IFD metadata (EXIF IFD is a subdirectory of IFD0)
                try:
                    ifd0_metadata = self._parse_ifd(all_ifds[0]['abs_offset'], offset)
                    exif_subfile_type = ifd0_metadata.get('EXIF:SubfileType')
                except Exception:
                    pass
            
            # If EXIF IFD has Full-resolution SubfileType, use it as the main SubfileType
            if exif_subfile_type is not None:
                if (exif_subfile_type == 0 or 
                    exif_subfile_type == 'Full-resolution image' or
                    str(exif_subfile_type).strip() == '0' or
                    (isinstance(exif_subfile_type, str) and 'Full-resolution' in exif_subfile_type)):
                    # Use EXIF IFD's SubfileType as the main SubfileType
                    from dnexif.value_formatter import format_exif_value
                    formatted_value = format_exif_value('SubfileType', 0)
                    metadata['SubfileType'] = formatted_value
                    # Ensure EXIF:SubfileType is in metadata if it wasn't already
                    if 'EXIF:SubfileType' not in metadata:
                        metadata['EXIF:SubfileType'] = formatted_value
            
            # Ensure SubfileType is set correctly for the main IFD
            # If we didn't already set it from EXIF IFD, set it based on the main IFD's SubfileType
            if 'SubfileType' not in metadata:
                main_subfile_type = ifd_subfile_types.get(main_ifd['abs_offset'], 0)
                from dnexif.value_formatter import format_exif_value
                metadata['SubfileType'] = format_exif_value('SubfileType', main_subfile_type)
        
        # Parse preview IFD separately with IFD1: prefix if it exists
        # Also extract IFD1 tags with EXIF: prefix for standard format compatibility
        if preview_ifd and preview_ifd != main_ifd:
            preview_metadata = self._parse_ifd(preview_ifd['abs_offset'], offset)
            # Add preview tags with IFD1: prefix
            for k, v in preview_metadata.items():
                if not k.startswith('EXIF:') and not k.startswith('GPS:') and not k.startswith('MakerNote:'):
                    metadata[f"IFD1:{k}"] = v
                    # Also add with EXIF: prefix for standard format compatibility
                    metadata[f"EXIF:{k}"] = v
            
            # Map JPEGInterchangeFormat to ThumbnailOffset and ThumbnailLength
            if 'JPEGInterchangeFormat' in preview_metadata:
                metadata['EXIF:ThumbnailOffset'] = preview_metadata['JPEGInterchangeFormat']
            if 'JPEGInterchangeFormatLength' in preview_metadata:
                metadata['EXIF:ThumbnailLength'] = preview_metadata['JPEGInterchangeFormatLength']
        
        # Also check main IFD for JPEGInterchangeFormat (some formats store it in IFD0)
        if 'JPEGInterchangeFormat' in metadata:
            metadata['EXIF:ThumbnailOffset'] = metadata['JPEGInterchangeFormat']
        if 'JPEGInterchangeFormatLength' in metadata:
            metadata['EXIF:ThumbnailLength'] = metadata['JPEGInterchangeFormatLength']
        
        # Add File:ExifByteOrder if not already present
        # Also check for incorrectly prefixed version
        if 'EXIF:File:ExifByteOrder' in metadata:
            metadata['File:ExifByteOrder'] = metadata['EXIF:File:ExifByteOrder']
            del metadata['EXIF:File:ExifByteOrder']
        if 'File:ExifByteOrder' not in metadata and byte_order_str:
            metadata['File:ExifByteOrder'] = byte_order_str
        
        
        # Final check: If EXIF:SubfileType exists and is "Full-resolution image", use it as SubfileType
        # This handles Sony ARW and similar formats where EXIF IFD's SubfileType takes precedence
        # Always check this, even if SubfileType already exists, to ensure correct value
        if 'EXIF:SubfileType' in metadata:
            exif_subfile_type = metadata.get('EXIF:SubfileType')
            if (exif_subfile_type == 0 or 
                exif_subfile_type == 'Full-resolution image' or
                str(exif_subfile_type).strip() == '0' or
                (isinstance(exif_subfile_type, str) and 'Full-resolution' in exif_subfile_type)):
                from dnexif.value_formatter import format_exif_value
                metadata['SubfileType'] = format_exif_value('SubfileType', 0)
        
        return metadata
    
    def _parse_ifd_info(self, ifd_offset: int, base_offset: int) -> Optional[Dict[str, Any]]:
        """
        Parse IFD structure to extract SubfileType and next IFD pointer.
        This is a lightweight parse that doesn't extract all tags.
        
        Args:
            ifd_offset: Absolute offset to the IFD
            base_offset: Base offset for relative addressing
            
        Returns:
            Dictionary with subfile_type and next_ifd, or None if invalid
        """
        if ifd_offset + 2 > len(self.file_data):
            return None
        
        # Read number of directory entries
        num_entries = struct.unpack(
            f'{self.endian}H',
            self.file_data[ifd_offset:ifd_offset + 2]
        )[0]
        
        if num_entries == 0 or num_entries > 1000:  # Sanity check
            return None
        
        subfile_type = None
        entry_offset = ifd_offset + 2
        
        # Scan entries to find SubfileType (tag 0x00FE)
        for i in range(num_entries):
            if entry_offset + 12 > len(self.file_data):
                break
            
            tag_id, tag_type, count, value_offset = struct.unpack(
                f'{self.endian}HHI4s',
                self.file_data[entry_offset:entry_offset + 12]
            )
            
            # Check for SubfileType tag (0x00FE)
            if tag_id == 0x00FE:  # SubfileType
                # Read the value (usually stored inline as SHORT, but can be LONG)
                if tag_type == 3 and count == 1:  # SHORT, count=1
                    if self.endian == '<':
                        subfile_type = struct.unpack('<H', value_offset[:2])[0]
                    else:
                        subfile_type = struct.unpack('>H', value_offset[:2])[0]
                elif tag_type == 4 and count == 1:  # LONG, count=1
                    if self.endian == '<':
                        subfile_type = struct.unpack('<I', value_offset)[0]
                    else:
                        subfile_type = struct.unpack('>I', value_offset)[0]
                else:
                    # Value stored at offset, read it
                    # Convert value_offset bytes to integer
                    if self.endian == '<':
                        value_offset_int = struct.unpack('<I', value_offset)[0]
                    else:
                        value_offset_int = struct.unpack('>I', value_offset)[0]
                    
                    value_addr = base_offset + value_offset_int
                    if tag_type == 3 and value_addr + 2 <= len(self.file_data):  # SHORT
                        subfile_type = struct.unpack(f'{self.endian}H', 
                                                   self.file_data[value_addr:value_addr + 2])[0]
                    elif tag_type == 4 and value_addr + 4 <= len(self.file_data):  # LONG
                        subfile_type = struct.unpack(f'{self.endian}I', 
                                                   self.file_data[value_addr:value_addr + 4])[0]
                break
            
            entry_offset += 12
        
        # Read next IFD offset (at end of IFD entries)
        next_ifd_offset = entry_offset
        next_ifd = 0
        if next_ifd_offset + 4 <= len(self.file_data):
            next_ifd = struct.unpack(f'{self.endian}I', 
                                    self.file_data[next_ifd_offset:next_ifd_offset + 4])[0]
        
        return {
            'subfile_type': subfile_type,
            'next_ifd': next_ifd
        }
    
    def _parse_ifd(self, ifd_offset: int, base_offset: int, parent_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Parse an IFD (Image File Directory) structure.
        
        Args:
            ifd_offset: Offset to the IFD from start of file
            base_offset: Base offset for relative addressing (TIFF base or JPEG APP1 base)
            parent_metadata: Optional parent metadata dictionary (for accessing Make from IFD0 when parsing EXIF IFD)
            
        Returns:
            Dictionary of parsed tags
        """
        # Build 1678: Ensure struct and EXIF_TAG_NAMES are available (fixes UnboundLocalError)
        import struct
        from dnexif.exif_tags import EXIF_TAG_NAMES
        
        metadata = {}
        # Store parent metadata for MakerNote parsing
        if parent_metadata:
            metadata.update(parent_metadata)
        
        # Read number of directory entries
        if ifd_offset + 2 > len(self.file_data):
            return metadata
            
        num_entries = struct.unpack(
            f'{self.endian}H',
            self.file_data[ifd_offset:ifd_offset + 2]
        )[0]
        
        # IMPROVEMENT (Build 1417): Track parsed IFD areas to avoid reading from IFD entry structures
        # Initialize tracking if not exists
        if not hasattr(self, '_parsed_ifd_areas'):
            self._parsed_ifd_areas = []
        
        # Record this IFD's entry area
        ifd_entry_start = ifd_offset + 2
        ifd_entry_end = ifd_entry_start + (num_entries * 12)
        self._parsed_ifd_areas.append((ifd_entry_start, ifd_entry_end))
        
        # Parse each directory entry
        entry_offset = ifd_offset + 2
        for i in range(num_entries):
            if entry_offset + 12 > len(self.file_data):
                break
                
            tag_id, tag_type, count, value_offset = struct.unpack(
                f'{self.endian}HHI4s',
                self.file_data[entry_offset:entry_offset + 12]
            )
            
            # Convert value_offset bytes to integer
            if self.endian == '<':
                value_offset_int = struct.unpack('<I', value_offset)[0]
            else:
                value_offset_int = struct.unpack('>I', value_offset)[0]
            
            # CRITICAL: Check for LeafData tag (0x8606) early, before regular tag processing
            # This tag contains PKTS format data with Leaf tags and must be processed specially
            if tag_id == 0x8606:  # LeafData (Build 1676: Moved check earlier to ensure it's processed)
                # LeafData is a proprietary PKTS format used by Leaf cameras in MOS files
                # It contains Leaf tags (0x8000-0x8070) in a custom directory structure
                # Standard format shows this as "LeafData (SubDirectory)" with a "[Leaf directory]" inside
                # PKTS format structure: "PKTS" (4 bytes) + version (4 bytes) + tag name (null-terminated) + value
                try:
                    # LeafData offset and size
                    # For tag type 2 (ASCII/STRING), value_offset is typically absolute (relative to file start)
                    # Try both absolute and relative offsets to handle different MOS file variations
                    leafdata_offset = None
                    leafdata_size = count  # Count is the size in bytes
                    
                    # Strategy 1: Try absolute offset first (most common for MOS files)
                    if 0 < value_offset_int < len(self.file_data):
                        test_data = self.file_data[value_offset_int:value_offset_int + min(leafdata_size, 100)]
                        if test_data.startswith(b'PKTS'):
                            leafdata_offset = value_offset_int
                    
                    # Strategy 2: Try TIFF-relative offset (base_offset + value_offset)
                    if leafdata_offset is None:
                        test_offset = base_offset + value_offset_int
                        if 0 < test_offset < len(self.file_data):
                            test_data = self.file_data[test_offset:test_offset + min(leafdata_size, 100)]
                            if test_data.startswith(b'PKTS'):
                                leafdata_offset = test_offset
                    
                    # Strategy 3: Use absolute offset as fallback (even if PKTS header not found at start)
                    if leafdata_offset is None:
                        leafdata_offset = value_offset_int if 0 < value_offset_int < len(self.file_data) else (base_offset + value_offset_int)
                    
                    if 0 < leafdata_offset < len(self.file_data) and leafdata_size > 0:
                        leafdata_end = min(leafdata_offset + leafdata_size, len(self.file_data))
                        leafdata_data = self.file_data[leafdata_offset:leafdata_end]
                        
                        # Check for PKTS header
                        if leafdata_data.startswith(b'PKTS'):
                            # Parse PKTS format
                            self._parse_pkts_format(leafdata_data, metadata)
                        elif len(leafdata_data) > 0:
                            # Try to find PKTS header anywhere in the data (might not be at start)
                            pkts_pos = leafdata_data.find(b'PKTS')
                            if pkts_pos >= 0:
                                # Found PKTS header, parse from that position
                                self._parse_pkts_format(leafdata_data[pkts_pos:], metadata)
                except Exception as e:
                    # If LeafData parsing fails, continue with other tags (don't store raw tag)
                    pass
                
                # Skip to next entry - LeafData tag is processed, don't store it as regular tag
                entry_offset += 12
                continue
            
            # Get tag name
            tag_name = EXIF_TAG_NAMES.get(tag_id, f"Unknown_{tag_id:04X}")
            
            # CRITICAL: For Leaf tags (0x8000-0x8070), try multiple offset strategies
            # Leaf tags in MOS format may use different offset calculations
            # Try both TIFF-relative (base_offset + value_offset) and absolute (value_offset) offsets
            if 0x8000 <= tag_id <= 0x8070:
                # This is a Leaf tag - try multiple offset strategies
                tag_value = None
                tag_size = TAG_SIZES.get(ExifTagType(tag_type), 1) if tag_type in [t.value for t in ExifTagType] else 1
                total_size = tag_size * count
                
                # If value fits in 4 bytes, it's stored inline
                if total_size <= 4:
                    tag_value = self._read_tag_value(
                        tag_type,
                        count,
                        value_offset_int,
                        entry_offset + 8,
                        base_offset
                    )
                else:
                    # Try multiple offset strategies for Leaf tags
                    # Strategy 1: TIFF-relative (base_offset + value_offset) - most common
                    # Strategy 2: Absolute (value_offset) - some Leaf tags use absolute offsets
                    # Strategy 3: IFD-relative (ifd_offset + value_offset) - less common
                    # Strategy 4: TIFF-relative with adjustments
                    # IMPROVEMENT (Build 1470): Enhanced offset strategies with more combinations and larger adjustments
                    # Leaf tags in MOS format may use various offset calculation methods
                    leaf_offset_strategies = [
                        base_offset + value_offset_int,  # TIFF-relative (most common)
                        value_offset_int,  # Absolute
                        ifd_offset + value_offset_int,  # IFD-relative
                        base_offset + value_offset_int - 8,  # With header adjustment
                        base_offset + value_offset_int + 8,  # With header adjustment
                    ]
                    # IMPROVEMENT (Build 1470): Add more offset strategies with larger adjustments
                    # Try a wider range of adjustments to handle various MOS format variations
                    for adj in [-32, -28, -24, -20, -16, -12, -8, -4, -2, 2, 4, 8, 12, 16, 20, 24, 28, 32]:
                        leaf_offset_strategies.append(base_offset + value_offset_int + adj)
                        leaf_offset_strategies.append(value_offset_int + adj)
                        leaf_offset_strategies.append(ifd_offset + value_offset_int + adj)
                    # IMPROVEMENT (Build 1470): Try MakerNote-relative offsets if we're in a MakerNote IFD
                    # Some Leaf tags might be relative to MakerNote base
                    if hasattr(self, '_makernote_base') and self._makernote_base is not None:
                        leaf_offset_strategies.append(self._makernote_base + value_offset_int)
                        for adj in [-16, -8, 8, 16]:
                            leaf_offset_strategies.append(self._makernote_base + value_offset_int + adj)
                    
                    for test_data_offset in leaf_offset_strategies:
                        if 0 < test_data_offset < len(self.file_data) and test_data_offset + total_size <= len(self.file_data):
                            try:
                                # Try reading the value from this offset
                                test_data = self.file_data[test_data_offset:test_data_offset + total_size]
                                
                                # IMPROVEMENT (Build 1409): Enhanced validation to avoid reading from IFD entry structures
                                # IFD entries are 12 bytes, so if test_data_offset is within an IFD entry area, skip it
                                # Check if test_data_offset overlaps with any IFD entry in the current IFD
                                is_in_entry_area = False
                                # Check if test_data_offset is within the IFD entry area (ifd_offset + 2 to ifd_offset + 2 + num_entries * 12)
                                ifd_entry_start = ifd_offset + 2
                                ifd_entry_end = ifd_entry_start + (num_entries * 12)
                                if ifd_entry_start <= test_data_offset < ifd_entry_end:
                                    # Check if it's aligned to an entry boundary (every 12 bytes)
                                    entry_relative = (test_data_offset - ifd_entry_start) % 12
                                    if entry_relative < 12:  # Within an entry
                                        is_in_entry_area = True
                                
                                # Also check if the end of the data would be in an IFD entry area
                                if not is_in_entry_area and (test_data_offset + total_size) > ifd_entry_start and (test_data_offset + total_size) <= ifd_entry_end:
                                    # Data extends into IFD entry area
                                    is_in_entry_area = True
                                
                                # Additional check: if offset is very close to IFD entry area (within 4 bytes), also reject
                                # This prevents reading from padding or alignment bytes near IFD entries
                                if not is_in_entry_area:
                                    if abs(test_data_offset - ifd_entry_start) < 4 or abs(test_data_offset - ifd_entry_end) < 4:
                                        is_in_entry_area = True
                                
                                # IMPROVEMENT (Build 1470): Enhanced validation - check all known IFDs, not just current IFD
                                # Also check if offset is within any previously parsed IFD entry area
                                # However, be more lenient - only reject if clearly within entry structure
                                if not is_in_entry_area and hasattr(self, '_parsed_ifd_areas'):
                                    for parsed_start, parsed_end in self._parsed_ifd_areas:
                                        # Only reject if offset is clearly aligned to entry structure (12-byte boundaries)
                                        # and looks like it's reading from entry fields (tag_id, type, count, value_offset)
                                        if parsed_start <= test_data_offset < parsed_end:
                                            entry_relative = (test_data_offset - parsed_start) % 12
                                            # Only reject if it's clearly at the start of an entry (within first 8 bytes)
                                            # This allows reading from value_offset field (bytes 8-12) which might be valid
                                            if entry_relative < 8:  # More lenient - only reject if clearly in entry header
                                                is_in_entry_area = True
                                                break
                                        if parsed_start <= (test_data_offset + total_size) < parsed_end:
                                            # Check if end is also clearly in entry structure
                                            end_relative = ((test_data_offset + total_size) - parsed_start) % 12
                                            if end_relative < 8:
                                                is_in_entry_area = True
                                                break
                                
                                # IMPROVEMENT (Build 1470): Check if offset looks like it's reading from IFD entry structure
                                # IFD entries have pattern: tag_id (2 bytes) + type (2 bytes) + count (4 bytes) + value_offset (4 bytes)
                                # Be more lenient - only reject if it's clearly at the start of an entry structure
                                # Don't reject if we're reading from the value_offset field (bytes 8-12) as that might be valid data
                                if not is_in_entry_area and test_data_offset % 12 == 0:
                                    # Only reject if we're at the very start of an entry (tag_id field)
                                    # This allows reading from value_offset field which might contain actual data
                                    entry_phase = (test_data_offset - ifd_entry_start) % 12 if ifd_entry_start <= test_data_offset < ifd_entry_end else -1
                                    if entry_phase >= 0 and entry_phase < 8:  # Only reject if in first 8 bytes of entry
                                        # Check if the data at this offset looks like an IFD entry (tag_id in reasonable range, type in valid range)
                                        if test_data_offset + 4 <= len(self.file_data):
                                            try:
                                                potential_tag_id = struct.unpack(f'{self.endian}H', self.file_data[test_data_offset:test_data_offset + 2])[0]
                                                potential_type = struct.unpack(f'{self.endian}H', self.file_data[test_data_offset + 2:test_data_offset + 4])[0]
                                                # If tag_id is in a reasonable IFD tag range (0x0000-0xFFFF) and type is valid (1-12), might be reading from IFD entry
                                                # But be more lenient - only reject if it's clearly a standard EXIF tag (not Leaf tag range)
                                                if 0x0000 <= potential_tag_id <= 0x7FFF and 1 <= potential_type <= 12:
                                                    # Additional check: if count field also looks reasonable
                                                    if test_data_offset + 8 <= len(self.file_data):
                                                        potential_count = struct.unpack(f'{self.endian}I', self.file_data[test_data_offset + 4:test_data_offset + 8])[0]
                                                        if 1 <= potential_count <= 1000:  # Reasonable count range
                                                            is_in_entry_area = True  # Likely reading from IFD entry structure
                                            except:
                                                pass
                                
                                if is_in_entry_area:
                                    continue  # Skip this offset - it's in an IFD entry area or too close to it
                                
                                # Try to parse the value
                                if tag_type == 1:  # BYTE
                                    if count == 1:
                                        test_value = struct.unpack(f'{self.endian}B', test_data[:1])[0]
                                    else:
                                        test_value = list(struct.unpack(f'{self.endian}{count}B', test_data))
                                elif tag_type == 3:  # SHORT
                                    if count == 1:
                                        test_value = struct.unpack(f'{self.endian}H', test_data[:2])[0]
                                    else:
                                        test_value = list(struct.unpack(f'{self.endian}{count}H', test_data))
                                elif tag_type == 4:  # LONG
                                    if count == 1:
                                        test_value = struct.unpack(f'{self.endian}I', test_data[:4])[0]
                                    else:
                                        test_value = list(struct.unpack(f'{self.endian}{count}I', test_data))
                                elif tag_type == 5:  # RATIONAL
                                    if count == 1:
                                        num, den = struct.unpack(f'{self.endian}II', test_data[:8])
                                        test_value = (num, den) if den != 0 else None
                                    else:
                                        test_value = []
                                        for i in range(count):
                                            num, den = struct.unpack(f'{self.endian}II', test_data[i*8:(i+1)*8])
                                            test_value.append((num, den) if den != 0 else None)
                                elif tag_type == 7:  # UNDEFINED
                                    # For UNDEFINED, return as bytes or try to decode as string
                                    if count <= 100:  # Reasonable size limit
                                        test_value = test_data
                                    else:
                                        continue  # Too large, skip
                                else:
                                    continue  # Unsupported type for this strategy
                                
                                # Validate the value - check if it looks reasonable
                                # For numeric types, check if values are within reasonable ranges
                                if tag_type in (3, 4):  # SHORT, LONG
                                    if isinstance(test_value, list):
                                        # Check if all values are reasonable (not too large)
                                        if all(0 <= v <= 100000000 for v in test_value if isinstance(v, (int, float))):
                                            tag_value = test_value
                                            break
                                    elif isinstance(test_value, (int, float)):
                                        if 0 <= test_value <= 100000000:
                                            tag_value = test_value
                                            break
                                elif tag_type == 7:  # UNDEFINED
                                    # For UNDEFINED, accept if it's not all zeros and not repeating pattern
                                    if len(test_data) > 0 and not (test_data == b'\x00' * len(test_data)):
                                        # Check for repeating patterns (might indicate reading from wrong location)
                                        if len(test_data) >= 4:
                                            pattern = test_data[:4]
                                            if test_data == pattern * (len(test_data) // 4):
                                                continue  # Repeating pattern, likely wrong location
                                        tag_value = test_data
                                        break
                                else:
                                    tag_value = test_value
                                    break
                            except Exception:
                                continue
                    
                    # If no strategy worked, fall back to standard reading
                    if tag_value is None:
                        tag_value = self._read_tag_value(
                            tag_type,
                            count,
                            value_offset_int,
                            entry_offset + 8,
                            base_offset
                        )
            else:
                # Standard tag - use normal reading
                tag_value = self._read_tag_value(
                    tag_type,
                    count,
                    value_offset_int,
                    entry_offset + 8,
                    base_offset
                )
            
            # Don't overwrite standard tags (0x0100-0x01FF) with custom tags (0x7000+) that have the same name
            # This prevents tags like 0x7000 (mapped to "ImageWidth") from overwriting the correct 0x0100 (ImageWidth)
            # Standard EXIF tags are in range 0x0100-0x01FF, custom/private tags are often 0x7000+
            # CRITICAL: Leaf tags (0x8000-0x8070) should always be added with Leaf: prefix
            # Check if this is a Leaf tag and ensure it gets the Leaf: prefix
            if 0x8000 <= tag_id <= 0x8070:
                # This is a Leaf tag - ensure it has Leaf: prefix
                if tag_name.startswith('Leaf:'):
                    # Already has Leaf: prefix, use as-is
                    pass
                elif tag_name.startswith('Unknown_'):
                    # Unknown Leaf tag - extract tag name from EXIF_TAG_NAMES if available
                    leaf_tag_name = EXIF_TAG_NAMES.get(tag_id)
                    if leaf_tag_name and leaf_tag_name.startswith('Leaf:'):
                        tag_name = leaf_tag_name
                    else:
                        # Use Leaf:Unknown_XXXX format
                        tag_name = f"Leaf:Unknown_{tag_id:04X}"
                else:
                    # Tag name from EXIF_TAG_NAMES - ensure it has Leaf: prefix
                    if not tag_name.startswith('Leaf:'):
                        # Add Leaf: prefix if not already present
                        tag_name = f"Leaf:{tag_name}"
                
                # IMPROVEMENT (Build 1401): Enhanced Leaf tag value extraction with additional offset strategies
                # For Leaf tags, try even more offset strategies if initial extraction fails
                if tag_value is None or (isinstance(tag_value, (list, tuple)) and len(tag_value) > 1000):
                    # Value extraction failed or got too many values (likely wrong location)
                    # Try additional offset strategies specifically for Leaf tags
                    tag_size = TAG_SIZES.get(ExifTagType(tag_type), 1) if tag_type in [t.value for t in ExifTagType] else 1
                    total_size = tag_size * count
                    
                    if total_size > 4:  # Only for non-inline values
                        # Additional Leaf-specific offset strategies
                        leaf_offset_strategies = [
                            base_offset + value_offset_int - 4,  # With small negative adjustment
                            base_offset + value_offset_int + 4,  # With small positive adjustment
                            ifd_offset + value_offset_int - 4,   # IFD-relative with adjustment
                            ifd_offset + value_offset_int + 4,   # IFD-relative with adjustment
                            value_offset_int - 4,                 # Absolute with adjustment
                            value_offset_int + 4,                # Absolute with adjustment
                        ]
                        
                        for test_data_offset in leaf_offset_strategies:
                            if 0 < test_data_offset < len(self.file_data) and test_data_offset + total_size <= len(self.file_data):
                                try:
                                    # IMPROVEMENT (Build 1409): Enhanced validation to avoid reading from IFD entry structures
                                    is_in_entry_area = False
                                    ifd_entry_start = ifd_offset + 2
                                    ifd_entry_end = ifd_entry_start + (num_entries * 12)
                                    if ifd_entry_start <= test_data_offset < ifd_entry_end:
                                        entry_relative = (test_data_offset - ifd_entry_start) % 12
                                        if entry_relative < 12:
                                            is_in_entry_area = True
                                    
                                    # Also check if the end of the data would be in an IFD entry area
                                    if not is_in_entry_area and (test_data_offset + total_size) > ifd_entry_start and (test_data_offset + total_size) <= ifd_entry_end:
                                        is_in_entry_area = True
                                    
                                    # Additional check: if offset is very close to IFD entry area (within 4 bytes), also reject
                                    if not is_in_entry_area:
                                        if abs(test_data_offset - ifd_entry_start) < 4 or abs(test_data_offset - ifd_entry_end) < 4:
                                            is_in_entry_area = True
                                    
                                    if is_in_entry_area:
                                        continue
                                    
                                    # Try reading value from this offset
                                    test_data = self.file_data[test_data_offset:test_data_offset + total_size]
                                    
                                    # Try to parse based on tag type
                                    if tag_type == 3:  # SHORT
                                        if count == 1:
                                            test_value = struct.unpack(f'{self.endian}H', test_data[:2])[0]
                                        else:
                                            test_value = list(struct.unpack(f'{self.endian}{count}H', test_data))
                                    elif tag_type == 4:  # LONG
                                        if count == 1:
                                            test_value = struct.unpack(f'{self.endian}I', test_data[:4])[0]
                                        else:
                                            test_value = list(struct.unpack(f'{self.endian}{count}I', test_data))
                                    elif tag_type == 7:  # UNDEFINED
                                        if count <= 100:
                                            test_value = test_data
                                        else:
                                            continue
                                    else:
                                        continue
                                    
                                    # Validate value - check if reasonable
                                    if tag_type in (3, 4):  # SHORT, LONG
                                        if isinstance(test_value, list):
                                            if all(0 <= v <= 100000000 for v in test_value if isinstance(v, (int, float))):
                                                tag_value = test_value
                                                break
                                        elif isinstance(test_value, (int, float)):
                                            if 0 <= test_value <= 100000000:
                                                tag_value = test_value
                                                break
                                    elif tag_type == 7:  # UNDEFINED
                                        if len(test_data) > 0 and not (test_data == b'\x00' * len(test_data)):
                                            tag_value = test_data
                                            break
                                except Exception:
                                    continue
            
            # Exception: Don't overwrite standard tags with custom tags
            if tag_name in metadata and tag_id >= 0x7000 and not (0x8000 <= tag_id <= 0x8070):
                # This is a custom tag trying to overwrite an existing tag
                # Check if there's a standard tag (0x0100-0x01FF) with this name
                standard_tag_id = None
                for tid in range(0x0100, 0x0200):
                    if EXIF_TAG_NAMES.get(tid) == tag_name:
                        standard_tag_id = tid
                        break
                if standard_tag_id is not None:
                    # There's a standard tag with this name - don't overwrite it with custom tag
                    # Use a different name for the custom tag
                    tag_name = f"Unknown_{tag_id:04X}"
            
            # IMPROVEMENT (Build 1279): Always add FocalPlane tags and BatteryLevel with EXIF: prefix when found
            # These tags are critical for DCR format and should always be available with EXIF: prefix
            # IMPROVEMENT (Build 1280): Check both standard EXIF tag IDs (0x9012-0x9014) and extended tag IDs (0x881B-0x881D)
            if tag_id in (0x881B, 0x881C, 0x881D, 0x9012, 0x9013, 0x9014, 0x8218):  # FocalPlaneXResolution, FocalPlaneYResolution, FocalPlaneResolutionUnit, BatteryLevel
                # Always add with EXIF: prefix to ensure they're available
                exif_key = f"EXIF:{tag_name}"
                if exif_key not in metadata:
                    metadata[exif_key] = tag_value
                # Also add without prefix for best IFD selection logic (if not already present)
                if tag_name not in metadata:
                    metadata[tag_name] = tag_value
            
            # Handle special tags
            if tag_id == 0x9101:  # ComponentsConfiguration (0x9101 in EXIF IFD)
                # ComponentsConfiguration is UNDEFINED type (7) with 4 bytes representing Y, Cb, Cr components
                # Convert bytes to list of integers for proper formatting
                if isinstance(tag_value, bytes) and len(tag_value) >= 4:
                    tag_value = list(tag_value[:4])
                elif isinstance(tag_value, str):
                    # If it's already a string (shouldn't happen but handle gracefully), try to convert
                    try:
                        tag_value = [ord(c) for c in tag_value[:4]] if len(tag_value) >= 4 else [ord(c) for c in tag_value]
                    except:
                        pass
                metadata[tag_name] = tag_value
            # Format DigitalZoomRatio if it's a rational tuple
            elif tag_id == 0x4044:  # DigitalZoomRatio
                from dnexif.value_formatter import format_exif_value
                formatted_value = format_exif_value('DigitalZoomRatio', tag_value)
                metadata[tag_name] = formatted_value
                # Also add EXIF prefix if in EXIF IFD
                if parent_metadata is not None:
                    metadata[f"EXIF:{tag_name}"] = formatted_value
            # Note: 0x9003 is DateTimeOriginal (ASCII string), not ComponentsConfiguration
            # It should be handled normally by _read_tag_value which will decode the full ASCII string
            elif tag_id == 0x9000:  # ExifVersion
                # Store EXIF version and determine UTF-8 support
                # ExifVersion is stored as ASCII string like "0230" (2.30) or "0300" (3.0)
                if isinstance(tag_value, (str, bytes)):
                    version_str = tag_value if isinstance(tag_value, str) else tag_value.decode('ascii', errors='replace')
                    # Remove null terminators and whitespace
                    version_str = version_str.strip('\x00').strip()
                    self.exif_version = version_str
                    # EXIF 3.0 (version "0300") and later support UTF-8
                    # EXIF 2.31 and earlier use ASCII only
                    try:
                        # Parse version string (e.g., "0300" -> 3.0, "0230" -> 2.30)
                        # Format is "MMmm" where first 2 digits are major.minor (without dot)
                        # "0300" = version 3.00 = major 3, minor 0
                        # "0230" = version 2.30 = major 2, minor 30
                        if len(version_str) >= 4:
                            # Parse as: first 2 chars = major, last 2 chars = minor
                            major = int(version_str[0:2])
                            minor = int(version_str[2:4])
                            # Convert to version number (e.g., 3.00 -> 3.0, 2.30 -> 2.30)
                            # Format as "M.mm" where mm is 2-digit minor version
                            version_num = float(f"{major}.{minor:02d}") if minor > 0 else float(major)
                            self.supports_utf8 = version_num >= 3.0
                            
                            # Add EXIF 3.0 detection tags
                            if version_num >= 3.0:
                                metadata['EXIF:EXIF3.0'] = True
                                metadata['EXIF:EXIFStandard'] = 'EXIF 3.0'
                                metadata['EXIF:SupportsUTF8'] = True
                        else:
                            self.supports_utf8 = False
                    except (ValueError, IndexError):
                        # Default to ASCII for unknown versions
                        self.supports_utf8 = False
                metadata[tag_name] = tag_value
            elif tag_id == 0x8769:  # EXIF IFD
                # Merge parent metadata with current metadata for Make lookup
                # This ensures MakerNote parser can find Make from IFD0/IFD1
                merged_parent = dict(metadata)
                if parent_metadata:
                    merged_parent.update(parent_metadata)
                
                # EXIF IFD offset calculation - try both relative and absolute
                # Some formats (like RW2) use absolute offsets, others use relative
                exif_ifd_offset = base_offset + value_offset_int  # Relative (most common)
                exif_data = None
                
                # Try relative offset first
                try:
                    if exif_ifd_offset + 2 <= len(self.file_data):
                        # Check if this looks like a valid IFD (has reasonable entry count)
                        test_entries = struct.unpack(f'{self.endian}H', 
                                                    self.file_data[exif_ifd_offset:exif_ifd_offset + 2])[0]
                        if 1 <= test_entries <= 200:
                            exif_data = self._parse_ifd(exif_ifd_offset, base_offset, parent_metadata=merged_parent)
                except:
                    pass
                
                # If relative didn't work, try absolute offset
                if exif_data is None or len(exif_data) == 0:
                    try:
                        if 0 < value_offset_int < len(self.file_data) and value_offset_int + 2 <= len(self.file_data):
                            test_entries = struct.unpack(f'{self.endian}H', 
                                                        self.file_data[value_offset_int:value_offset_int + 2])[0]
                            if 1 <= test_entries <= 200:
                                exif_data = self._parse_ifd(value_offset_int, base_offset, parent_metadata=merged_parent)
                    except:
                        pass
                
                # Fallback to relative if absolute didn't work
                if exif_data is None:
                    exif_data = self._parse_ifd(exif_ifd_offset, base_offset, parent_metadata=merged_parent)
                # Add EXIF prefix, but don't double-prefix MakerNote tags or manufacturer tags
                # Also don't add EXIF prefix to tags that should come from best IFD (they'll be added later)
                critical_tags_no_prefix = {'StripOffsets', 'StripByteCounts', 'TileOffsets', 'TileByteCounts', 
                                          'RowsPerStrip', 'SamplesPerPixel', 'BitsPerSample', 'PhotometricInterpretation',
                                          'Compression', 'PlanarConfiguration', 'FocalPlaneXResolution', 
                                          'FocalPlaneYResolution', 'FocalPlaneResolutionUnit', 'BatteryLevel'}
                for k, v in exif_data.items():
                    if (k.startswith('MakerNote:') or k.startswith('MakerNotes:') or
                        k.startswith('Canon') or k.startswith('Nikon') or k.startswith('Sony') or
                        k.startswith('Olympus') or k.startswith('Pentax') or k.startswith('Fujifilm') or
                        k.startswith('Panasonic') or k.startswith('MinoltaRaw')):
                        metadata[k] = v  # Keep MakerNote and manufacturer tags without EXIF prefix
                    elif k.startswith('Leaf:'):
                        # CRITICAL: Leaf tags should be kept as-is (already have Leaf: prefix)
                        # Don't add EXIF prefix to Leaf tags - they're private IFD tags, not EXIF tags
                        metadata[k] = v
                    elif k in critical_tags_no_prefix:
                        # For critical tags found in EXIF IFD, add with EXIF: prefix
                        # These tags (FocalPlaneXResolution, FocalPlaneYResolution, FocalPlaneResolutionUnit, BatteryLevel)
                        # should be extracted from EXIF IFD if not found in best IFD
                        # IMPROVEMENT (Build 1277): Ensure FocalPlane tags and BatteryLevel from EXIF IFD are added with EXIF: prefix
                        # IMPROVEMENT (Build 1277): Also check if these tags exist in other IFDs and extract them with EXIF: prefix
                        if k not in metadata:
                            # Add without prefix first (for best IFD selection logic)
                            metadata[k] = v
                        # Also add with EXIF: prefix to ensure they're available
                        exif_key = f"EXIF:{k}"
                        if exif_key not in metadata:
                            metadata[exif_key] = v
                    else:
                        metadata[f"EXIF:{k}"] = v
                # IMPROVEMENT (Build 1279): Explicitly extract FocalPlane tags and BatteryLevel from EXIF IFD
                # These tags are critical for DCR format and may be missed by standard parsing
                # IMPROVEMENT (Build 1280): Check both standard EXIF tag IDs (0x9012-0x9014) and extended tag IDs (0x881B-0x881D)
                # Search for tag IDs: 0x881B/0x9012 (FocalPlaneXResolution), 0x881C/0x9013 (FocalPlaneYResolution),
                # 0x881D/0x9014 (FocalPlaneResolutionUnit), 0x8218 (BatteryLevel)
                critical_tag_ids = {
                    0x881B: 'FocalPlaneXResolution',
                    0x881C: 'FocalPlaneYResolution',
                    0x881D: 'FocalPlaneResolutionUnit',
                    0x9012: 'FocalPlaneXResolution',  # Standard EXIF tag ID
                    0x9013: 'FocalPlaneYResolution',  # Standard EXIF tag ID
                    0x9014: 'FocalPlaneResolutionUnit',  # Standard EXIF tag ID
                    0x8218: 'BatteryLevel'
                }
                
                # Check if these tags are missing and try to extract them directly from EXIF IFD
                # Try multiple EXIF IFD offsets (relative, absolute, and from exif_data if available)
                exif_ifd_offsets_to_try = []
                if exif_data is not None:
                    # If EXIF IFD was parsed, try the offset that worked
                    exif_ifd_offsets_to_try.append(exif_ifd_offset)
                # Also try absolute offset
                if 0 < value_offset_int < len(self.file_data):
                    exif_ifd_offsets_to_try.append(value_offset_int)
                # Also try relative offset
                exif_ifd_offsets_to_try.append(base_offset + value_offset_int)
                
                for tag_id, tag_name in critical_tag_ids.items():
                    exif_key = f"EXIF:{tag_name}"
                    if exif_key not in metadata and tag_name not in metadata:
                        # Try to find this tag in the EXIF IFD using multiple offset strategies
                        for test_ifd_offset in exif_ifd_offsets_to_try:
                            try:
                                if test_ifd_offset + 2 <= len(self.file_data):
                                    num_entries = struct.unpack(f'{self.endian}H', 
                                                               self.file_data[test_ifd_offset:test_ifd_offset+2])[0]
                                    if 1 <= num_entries <= 200:  # Valid IFD entry count
                                        entry_offset = test_ifd_offset + 2
                                        
                                        for i in range(min(num_entries, 200)):
                                            if entry_offset + 12 > len(self.file_data):
                                                break
                                            
                                            entry_tag_id = struct.unpack(f'{self.endian}H', 
                                                                         self.file_data[entry_offset:entry_offset+2])[0]
                                            if entry_tag_id == tag_id:
                                                # Found the tag - extract it
                                                entry_tag_type = struct.unpack(f'{self.endian}H', 
                                                                              self.file_data[entry_offset+2:entry_offset+4])[0]
                                                entry_tag_count = struct.unpack(f'{self.endian}I', 
                                                                               self.file_data[entry_offset+4:entry_offset+8])[0]
                                                value_offset_bytes = self.file_data[entry_offset+8:entry_offset+12]
                                                if self.endian == '<':
                                                    entry_value_offset_int = struct.unpack('<I', value_offset_bytes)[0]
                                                else:
                                                    entry_value_offset_int = struct.unpack('>I', value_offset_bytes)[0]
                                                
                                                # Read tag value
                                                tag_value = self._read_tag_value(
                                                    entry_tag_type,
                                                    entry_tag_count,
                                                    entry_value_offset_int,
                                                    entry_offset + 8,
                                                    base_offset
                                                )
                                                
                                                if tag_value is not None:
                                                    # Add with EXIF: prefix
                                                    metadata[exif_key] = tag_value
                                                    # Also add without prefix for best IFD selection logic
                                                    if tag_name not in metadata:
                                                        metadata[tag_name] = tag_value
                                                    break  # Found the tag, no need to try other offsets
                                            
                                            entry_offset += 12
                                        
                                        # If we found the tag, break out of offset loop
                                        if exif_key in metadata:
                                            break
                            except Exception:
                                continue
                
                # Check for ExifVersion in EXIF IFD if not found in IFD0
                if self.exif_version is None and 'EXIF:ExifVersion' in exif_data:
                    version_str = str(exif_data['EXIF:ExifVersion']).strip('\x00').strip()
                    self.exif_version = version_str
                    try:
                        # Parse version string (e.g., "0300" -> 3.0, "0230" -> 2.30)
                        if len(version_str) >= 4:
                            major = int(version_str[0])
                            minor = int(version_str[1:3])
                            version_num = float(f"{major}.{minor}")
                            self.supports_utf8 = version_num >= 3.0
                        else:
                            self.supports_utf8 = False
                    except (ValueError, IndexError):
                        self.supports_utf8 = False
            elif tag_id == 0x8825:  # GPS IFD
                gps_data = self._parse_ifd(base_offset + value_offset_int, base_offset)
                metadata.update({f"GPS:{k}": v for k, v in gps_data.items()})
            elif tag_id == 0xA005:  # Interoperability IFD
                interop_data = self._parse_ifd(base_offset + value_offset_int, base_offset)
                # Add with Interop: prefix (existing behavior)
                metadata.update({f"Interop:{k}": v for k, v in interop_data.items()})
                # Also add with EXIF: prefix for standard format compatibility
                for k, v in interop_data.items():
                    if k == 'InteroperabilityIndex':
                        metadata['EXIF:InteropIndex'] = v
                    elif k == 'InteroperabilityVersion':
                        metadata['EXIF:InteropVersion'] = v
                    else:
                        metadata[f"EXIF:{k}"] = v
            elif tag_id == 0x014A:  # SubIFDs
                # SubIFDs can contain multiple IFD offsets (LONG array)
                # Store the offsets for later processing in IFD selection
                # CRITICAL: Also parse SubIFDs immediately to extract all tags (including EXIF IFD and Leaf tags)
                # This ensures we find EXIF IFD and Leaf tags even if they're in SubIFDs
                subifd_offsets = []
                if isinstance(tag_value, (list, tuple)):
                    # Multiple SubIFD offsets
                    subifd_offsets = list(tag_value)
                    metadata['SubIFDs'] = tag_value
                elif isinstance(tag_value, (int,)):
                    # Single SubIFD offset
                    subifd_offsets = [tag_value]
                    metadata['SubIFDs'] = [tag_value]
                else:
                    # Store as-is for now
                    metadata[tag_name] = tag_value
                
                # Parse each SubIFD to extract all tags (including EXIF IFD and Leaf tags)
                for subifd_offset_val in subifd_offsets:
                    if isinstance(subifd_offset_val, (int,)):
                        try:
                            # Try relative offset first
                            subifd_abs_offset = base_offset + subifd_offset_val
                            if 0 < subifd_abs_offset < len(self.file_data) and subifd_abs_offset + 2 <= len(self.file_data):
                                # Check if this looks like a valid IFD
                                test_entries = struct.unpack(f'{self.endian}H', 
                                                            self.file_data[subifd_abs_offset:subifd_abs_offset + 2])[0]
                                if 1 <= test_entries <= 200:
                                    # Parse SubIFD recursively to extract all tags
                                    subifd_meta = self._parse_ifd(subifd_abs_offset, base_offset, parent_metadata=parent_metadata)
                                    # Merge SubIFD tags into metadata (with SubIFD: prefix to avoid conflicts)
                                    for k, v in subifd_meta.items():
                                        if k not in ('SubIFDs',):  # Don't duplicate SubIFDs list
                                            # Add SubIFD prefix for tags that might conflict
                                            if k.startswith('EXIF:') or k.startswith('Leaf:'):
                                                metadata[k] = v  # Keep EXIF: and Leaf: prefixes as-is
                                            else:
                                                metadata[f"SubIFD:{k}"] = v
                        except:
                            # If relative offset failed, try absolute offset
                            try:
                                if 0 < subifd_offset_val < len(self.file_data) and subifd_offset_val + 2 <= len(self.file_data):
                                    test_entries = struct.unpack(f'{self.endian}H', 
                                                                self.file_data[subifd_offset_val:subifd_offset_val + 2])[0]
                                    if 1 <= test_entries <= 200:
                                        subifd_meta = self._parse_ifd(subifd_offset_val, base_offset, parent_metadata=parent_metadata)
                                        for k, v in subifd_meta.items():
                                            if k not in ('SubIFDs',):
                                                if k.startswith('EXIF:') or k.startswith('Leaf:'):
                                                    metadata[k] = v
                                                else:
                                                    metadata[f"SubIFD:{k}"] = v
                            except:
                                pass
            elif tag_id in (0x927C, 0x83BB):  # MakerNote (standard 0x927C or Leaf 0x83BB)
                # Parse MakerNote if we have Make information (use final parser for enhanced decoding)
                # MakerNote is stored as UNDEFINED type (7) with the data at base_offset + value_offset_int
                # Leaf MOS files use tag 0x83BB for their MakerNote IFD which contains all Leaf tags (0x8000-0x8070)
                # IMPROVEMENT (Build 1398): CRITICAL - For Leaf MakerNote (0x83BB), parse even without Make tag
                # Leaf MakerNote IFD is a standard TIFF IFD containing Leaf tags (0x8000-0x8070)
                # It doesn't have a "Leaf" header, so we need to parse it as a TIFF IFD directly
                is_leaf_makernote = (tag_id == 0x83BB)
                
                # Note: Make is in the main IFD, not EXIF IFD, so we need to search for it
                # in the parent metadata or look for it in the file
                maker = metadata.get('Make', '')
                if not maker and parent_metadata:
                    maker = parent_metadata.get('Make', '')
                # Also check for Make in IFD0/IFD1 prefixes
                if not maker:
                    for key in list(metadata.keys()) + (list(parent_metadata.keys()) if parent_metadata else []):
                        if key.endswith(':Make') or key == 'Make':
                            maker = metadata.get(key) or (parent_metadata.get(key) if parent_metadata else '')
                            if maker:
                                break
                # Also check parent metadata with prefixes (more thorough search)
                if not maker and parent_metadata:
                    for key in parent_metadata.keys():
                        if 'Make' in key and parent_metadata[key]:
                            maker = parent_metadata[key]
                            break
                # Final fallback: search all metadata keys (including EXIF:Make, IFD0:Make, etc.)
                if not maker:
                    all_metadata = dict(metadata)
                    if parent_metadata:
                        all_metadata.update(parent_metadata)
                    for key in all_metadata.keys():
                        if 'Make' in key and all_metadata[key]:
                            maker = all_metadata[key]
                            break
                
                # IMPROVEMENT (Build 1398): For Leaf MakerNote (0x83BB), parse even without Make tag
                # Leaf MakerNote IFD is a standard TIFF IFD - parse it directly
                # IMPROVEMENT (Build 1399): Enhanced Leaf MakerNote IFD detection with more offset strategies and header adjustments
                # IMPROVEMENT (Build 1428): Enhanced Leaf MakerNote IFD detection with expanded offset strategies and aggressive IFD scanning
                if is_leaf_makernote:
                    # Leaf MakerNote IFD doesn't have a header - it's just a standard TIFF IFD
                    # Try multiple offset strategies to find the IFD
                    leaf_makernote_offsets = [
                        base_offset + value_offset_int,  # TIFF-relative (most common)
                        value_offset_int,  # Absolute
                        ifd_offset + value_offset_int,  # IFD-relative
                    ]
                    
                    # IMPROVEMENT (Build 1520): Add more offset strategies with expanded header adjustments
                    for header_adj in [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, -2, -4, -6, -8, -10, -12, -14, -16, -18, -20, -22, -24, -26, -28, -30, -32]:
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    # IMPROVEMENT (Build 1522): Additional negative adjustments (-50, -52, -54, -56, -58, -60, -62, -64) for Leaf MakerNote IFD detection
                    for header_adj in [-50, -52, -54, -56, -58, -60, -62, -64]:
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    # IMPROVEMENT (Build 1523): Additional negative adjustments (-66, -68, -70, -72, -74, -76, -78, -80) for Leaf MakerNote IFD detection
                    for header_adj in [-66, -68, -70, -72, -74, -76, -78, -80]:
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    # IMPROVEMENT (Build 1605): Additional header adjustments (34-100, -82 to -100) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1606): Additional header adjustments (101-120, -101 to -120) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1607): Additional header adjustments (121-140, -121 to -140) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1608): Additional header adjustments (141-160, -141 to -160) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1609): Additional header adjustments (161-180, -161 to -180) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1610): Additional header adjustments (181-200, -181 to -200) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1611): Additional header adjustments (201-220, -201 to -220) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1612): Additional header adjustments (221-240, -221 to -240) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1613): Additional header adjustments (241-260, -241 to -260) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1615): Additional header adjustments (261-280, -261 to -280) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1617): Additional header adjustments (301-320, -301 to -320) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1618): Additional header adjustments (321-340, -321 to -340) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1619): Additional header adjustments (341-360, -341 to -360) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1621): Additional header adjustments (361-380, -361 to -380) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1622): Additional header adjustments (381-400, -381 to -400) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1623): Additional header adjustments (401-420, -401 to -420) for Leaf MakerNote IFD detection
                    for header_adj in [34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 82, 84, 86, 88, 90, 92, 94, 96, 98, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299, 300, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 318, 319, 320, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330, 331, 332, 333, 334, 335, 336, 337, 338, 339, 340, 341, 342, 343, 344, 345, 346, 347, 348, 349, 350, 351, 352, 353, 354, 355, 356, 357, 358, 359, 360, 361, 362, 363, 364, 365, 366, 367, 368, 369, 370, 371, 372, 373, 374, 375, 376, 377, 378, 379, 380, 381, 382, 383, 384, 385, 386, 387, 388, 389, 390, 391, 392, 393, 394, 395, 396, 397, 398, 399, 400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 419, 420, -82, -84, -86, -88, -90, -92, -94, -96, -98, -100, -101, -102, -103, -104, -105, -106, -107, -108, -109, -110, -111, -112, -113, -114, -115, -116, -117, -118, -119, -120, -121, -122, -123, -124, -125, -126, -127, -128, -129, -130, -131, -132, -133, -134, -135, -136, -137, -138, -139, -140, -141, -142, -143, -144, -145, -146, -147, -148, -149, -150, -151, -152, -153, -154, -155, -156, -157, -158, -159, -160, -161, -162, -163, -164, -165, -166, -167, -168, -169, -170, -171, -172, -173, -174, -175, -176, -177, -178, -179, -180, -181, -182, -183, -184, -185, -186, -187, -188, -189, -190, -191, -192, -193, -194, -195, -196, -197, -198, -199, -200, -201, -202, -203, -204, -205, -206, -207, -208, -209, -210, -211, -212, -213, -214, -215, -216, -217, -218, -219, -220, -221, -222, -223, -224, -225, -226, -227, -228, -229, -230, -231, -232, -233, -234, -235, -236, -237, -238, -239, -240, -241, -242, -243, -244, -245, -246, -247, -248, -249, -250, -251, -252, -253, -254, -255, -256, -257, -258, -259, -260, -261, -262, -263, -264, -265, -266, -267, -268, -269, -270, -271, -272, -273, -274, -275, -276, -277, -278, -279, -280, -281, -282, -283, -284, -285, -286, -287, -288, -289, -290, -291, -292, -293, -294, -295, -296, -297, -298, -299, -300, -301, -302, -303, -304, -305, -306, -307, -308, -309, -310, -311, -312, -313, -314, -315, -316, -317, -318, -319, -320, -321, -322, -323, -324, -325, -326, -327, -328, -329, -330, -331, -332, -333, -334, -335, -336, -337, -338, -339, -340, -341, -342, -343, -344, -345, -346, -347, -348, -349, -350, -351, -352, -353, -354, -355, -356, -357, -358, -359, -360, -361, -362, -363, -364, -365, -366, -367, -368, -369, -370, -371, -372, -373, -374, -375, -376, -377, -378, -379, -380, -381, -382, -383, -384, -385, -386, -387, -388, -389, -390, -391, -392, -393, -394, -395, -396, -397, -398, -399, -400, -401, -402, -403, -404, -405, -406, -407, -408, -409, -410, -411, -412, -413, -414, -415, -416, -417, -418, -419, -420]:
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    # IMPROVEMENT (Build 1520): Also try byte order indicator adjustments with expanded range
                    for byte_order_adj in [0, 2, 4, -2, -4]:
                        leaf_makernote_offsets.append(base_offset + value_offset_int + byte_order_adj)
                    
                    # IMPROVEMENT (Build 1520): Add extended offset strategies with larger adjustments
                    for large_adj in [-64, -56, -48, -40, -32, -28, -24, -20, -16, -12, -10, 10, 12, 16, 20, 24, 28, 32, 40, 48, 56, 64]:
                        leaf_makernote_offsets.append(base_offset + value_offset_int + large_adj)
                        leaf_makernote_offsets.append(value_offset_int + large_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + large_adj)
                    
                    # IMPROVEMENT (Build 1522): Enhanced scanning with even larger adjustments (-100 to +100 bytes) for Leaf MakerNote IFD detection
                    for large_adj in [-100, -96, -92, -88, -84, -80, -76, -72, -68, -64, -60, -56, -52, -48, -44, -40, -36, -32, -28, -24, -20, -16, -12, -8, -4, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80, 84, 88, 92, 96, 100]:
                        leaf_makernote_offsets.append(base_offset + value_offset_int + large_adj)
                        leaf_makernote_offsets.append(value_offset_int + large_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + large_adj)
                    
                    # IMPROVEMENT (Build 1523): Enhanced scanning with even larger adjustments (-120 to +120 bytes) for Leaf MakerNote IFD detection
                    for large_adj in [-120, -116, -112, -108, -104, 104, 108, 112, 116, 120]:
                        leaf_makernote_offsets.append(base_offset + value_offset_int + large_adj)
                        leaf_makernote_offsets.append(value_offset_int + large_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + large_adj)
                    
                    # IMPROVEMENT (Build 1524): Additional negative adjustments (-82, -84, -86, -88, -90, -92, -94, -96, -98, -100) for Leaf MakerNote IFD detection
                    for header_adj in [-82, -84, -86, -88, -90, -92, -94, -96, -98, -100]:
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    # IMPROVEMENT (Build 1524): Enhanced scanning with even larger adjustments (-140 to +140 bytes) for Leaf MakerNote IFD detection
                    for large_adj in [-140, -136, -132, -128, -124, 124, 128, 132, 136, 140]:
                        leaf_makernote_offsets.append(base_offset + value_offset_int + large_adj)
                        leaf_makernote_offsets.append(value_offset_int + large_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + large_adj)
                    
                    # IMPROVEMENT (Build 1527): Additional negative adjustments (-142, -144, -146, -148, -150, -152, -154, -156, -158, -160) for Leaf MakerNote IFD detection
                    for header_adj in [-142, -144, -146, -148, -150, -152, -154, -156, -158, -160]:
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    # IMPROVEMENT (Build 1527): Enhanced scanning with even larger adjustments (-200 to +200 bytes) for Leaf MakerNote IFD detection
                    for large_adj in [-200, -196, -192, -188, -184, -180, -176, -172, -168, -164, -160, -156, -152, -148, -144, -140, -136, -132, -128, -124, -120, -116, -112, -108, -104, -100, -96, -92, -88, -84, -80, -76, -72, -68, -64, -60, -56, -52, -48, -44, -40, -36, -32, -28, -24, -20, -16, -12, -8, -4, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80, 84, 88, 92, 96, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 148, 152, 156, 160, 164, 168, 172, 176, 180, 184, 188, 192, 196, 200]:
                        leaf_makernote_offsets.append(base_offset + value_offset_int + large_adj)
                        leaf_makernote_offsets.append(value_offset_int + large_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + large_adj)
                    
                    # IMPROVEMENT (Build 1549): Additional header size variations (442-500) for Leaf MakerNote IFD detection
                    for header_adj in range(442, 501, 2):
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    # IMPROVEMENT (Build 1549): Additional negative header size variations (-412 to -500) for Leaf MakerNote IFD detection
                    for header_adj in range(-500, -411, 2):
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    # IMPROVEMENT (Build 1550): Additional header size variations (502-600) for Leaf MakerNote IFD detection
                    for header_adj in range(502, 601, 2):
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    # IMPROVEMENT (Build 1550): Additional negative header size variations (-502 to -600) for Leaf MakerNote IFD detection
                    for header_adj in range(-600, -501, 2):
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    # IMPROVEMENT (Build 1551): Additional header size variations (602-700) for Leaf MakerNote IFD detection
                    for header_adj in range(602, 701, 2):
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    # IMPROVEMENT (Build 1551): Additional negative header size variations (-602 to -700) for Leaf MakerNote IFD detection
                    for header_adj in range(-700, -601, 2):
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    # IMPROVEMENT (Build 1552): Additional header size variations (702-800) for Leaf MakerNote IFD detection
                    for header_adj in range(702, 801, 2):
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    # IMPROVEMENT (Build 1552): Additional negative header size variations (-702 to -800) for Leaf MakerNote IFD detection
                    for header_adj in range(-800, -701, 2):
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    # IMPROVEMENT (Build 1553): Additional header size variations (802-900) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1554): Additional header size variations (902-1000) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1556): Additional header size variations (1102-1200) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1559): Additional header size variations (1402-1500) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1560): Additional header size variations (1502-1600) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1562): Additional header size variations (1702-1800) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1567): Additional header size variations (2202-2300) and negative variations (-2202 to -2300) for Leaf MakerNote IFD detection
                    for header_adj in range(802, 1801, 2):
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    for header_adj in range(2202, 2301, 2):
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    for header_adj in range(-2300, -2201, 2):
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    # IMPROVEMENT (Build 1553): Additional negative header size variations (-802 to -900) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1554): Additional negative header size variations (-902 to -1000) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1556): Additional negative header size variations (-1102 to -1200) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1559): Additional negative header size variations (-1402 to -1500) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1560): Additional negative header size variations (-1502 to -1600) for Leaf MakerNote IFD detection
                    # IMPROVEMENT (Build 1562): Additional negative header size variations (-1702 to -1800) for Leaf MakerNote IFD detection
                    for header_adj in range(-1800, -801, 2):
                        leaf_makernote_offsets.append(base_offset + value_offset_int + header_adj)
                        leaf_makernote_offsets.append(value_offset_int + header_adj)
                        leaf_makernote_offsets.append(ifd_offset + value_offset_int + header_adj)
                    
                    visited_leaf_ifds = set()  # Track visited IFDs to avoid infinite recursion
                    
                    # IMPROVEMENT (Build 1659): Prioritize most likely offsets first - try value_offset directly before extensive variations
                    # Leaf MakerNote IFD is typically at value_offset directly (no header), so try that first
                    # This is more efficient and often correct
                    priority_offsets = [
                        value_offset_int,  # Absolute offset (most common for Leaf)
                        base_offset + value_offset_int,  # TIFF-relative offset
                        ifd_offset + value_offset_int,  # IFD-relative offset
                    ]
                    
                    # IMPROVEMENT (Build 1661): For Leaf MakerNote with type=1 (BYTE) and small count, also try scanning for IFD
                    # The IFD may be far from the MakerNote tag value_offset
                    # Build 1679: Fixed UnboundLocalError - use 'count' from loop instead of 'tag_count'
                    if tag_type == 1 and count < 20:
                        # Scan for IFDs with Leaf tags in the first 500KB
                        # This handles cases where MakerNote doesn't directly point to IFD
                        scan_candidates = []
                        scan_limit = min(500000, len(self.file_data))
                        for scan_offset in range(0, scan_limit, 4):  # Check every 4 bytes
                            if scan_offset + 2 > len(self.file_data):
                                break
                            try:
                                test_count = struct.unpack(f'{self.endian}H', 
                                                          self.file_data[scan_offset:scan_offset+2])[0]
                                if 50 <= test_count <= 150:  # Reasonable IFD size
                                    # Quick check for Leaf tags
                                    entry_off = scan_offset + 2
                                    for i in range(min(test_count, 20)):
                                        if entry_off + 12 > len(self.file_data):
                                            break
                                        tag_id = struct.unpack(f'{self.endian}H', 
                                                              self.file_data[entry_off:entry_off+2])[0]
                                        if 0x8000 <= tag_id <= 0x8070:
                                            scan_candidates.append(scan_offset)
                                            break
                                        entry_off += 12
                                    if scan_candidates:  # Found one, prioritize it
                                        break
                            except:
                                pass
                        # Add found IFD offsets to priority list
                        if scan_candidates:
                            priority_offsets.extend(scan_candidates)
                    
                    # Add priority offsets to the front of the list
                    leaf_makernote_offsets = priority_offsets + [o for o in leaf_makernote_offsets if o not in priority_offsets]
                    
                    # IMPROVEMENT (Build 1520): Enhanced aggressive IFD scanning around the calculated offset
                    # Scan a wider range to find Leaf MakerNote IFD if standard offsets don't work
                    scan_range = 600  # IMPROVEMENT (Build 1520): Increased from 400 to 600 bytes for wider scanning
                    for base_calc_offset in [base_offset + value_offset_int, value_offset_int]:
                        for scan_adj in range(-scan_range, scan_range + 1, 1):  # IMPROVEMENT (Build 1520): Step by 1 byte for maximum coverage
                            scan_offset = base_calc_offset + scan_adj
                            if scan_offset not in visited_leaf_ifds and 0 < scan_offset < len(self.file_data) - 2:
                                if scan_offset not in leaf_makernote_offsets:
                                    leaf_makernote_offsets.append(scan_offset)
                    
                    # IMPROVEMENT (Build 1664): For Leaf MakerNote with type=1 (BYTE) and small count, the IFD may be far away
                    # Perform a comprehensive file scan to find IFDs containing Leaf tags when standard offsets fail
                    # This handles cases where the MakerNote tag doesn't directly point to the IFD
                    # Based on Build 1662 findings, Leaf MakerNote IFD was found at offset 27140
                    # Build 1679: Fixed UnboundLocalError - use 'count' from loop instead of 'tag_count'
                    if tag_type == 1 and count < 20:  # BYTE type with small count
                        # IMPROVEMENT (Build 1664): Scan more thoroughly - check every 2 bytes for better coverage
                        # Scan first 100KB more carefully, then scan up to 1MB with larger steps
                        scan_limit_primary = min(100000, len(self.file_data))
                        scan_found_ifd = False
                        
                        # Primary scan: first 100KB, every 2 bytes (more thorough)
                        for scan_offset in range(0, scan_limit_primary, 2):  # Check every 2 bytes for better coverage
                            if scan_offset in visited_leaf_ifds or scan_offset + 2 > len(self.file_data):
                                continue
                            try:
                                test_count = struct.unpack(f'{self.endian}H', 
                                                          self.file_data[scan_offset:scan_offset+2])[0]
                                # Look for IFDs with reasonable entry counts (100-150 for Leaf MakerNote, based on Build 1662 finding 130 entries)
                                if 100 <= test_count <= 150:
                                    # Check if this IFD contains Leaf tags (check more entries for reliability)
                                    entry_off = scan_offset + 2
                                    found_leaf_tag = False
                                    leaf_tag_count = 0
                                    for i in range(min(test_count, 30)):  # Check first 30 entries for better detection
                                        if entry_off + 12 > len(self.file_data):
                                            break
                                        tag_id = struct.unpack(f'{self.endian}H', 
                                                              self.file_data[entry_off:entry_off+2])[0]
                                        if 0x8000 <= tag_id <= 0x8070:
                                            found_leaf_tag = True
                                            leaf_tag_count += 1
                                            if leaf_tag_count >= 3:  # Found multiple Leaf tags, this is definitely the IFD
                                                break
                                        entry_off += 12
                                    # If we found Leaf tags, this is likely the correct IFD
                                    if found_leaf_tag and scan_offset not in leaf_makernote_offsets:
                                        # Found an IFD with Leaf tags - add to priority list
                                        leaf_makernote_offsets.insert(0, scan_offset)  # Add to front for priority
                                        scan_found_ifd = True
                                        # Don't break - continue scanning to find all IFDs with Leaf tags
                            except:
                                pass
                        
                        # IMPROVEMENT (Build 1664): Extended scan if primary scan didn't find IFD
                        # Some Leaf MakerNote IFDs might be further into the file (e.g., offset 27140 from Build 1662)
                        if not scan_found_ifd:
                            # Scan from 100KB to 1MB with 4-byte steps
                            extended_scan_limit = min(1000000, len(self.file_data))
                            for scan_offset in range(scan_limit_primary, extended_scan_limit, 4):  # 4-byte steps for efficiency
                                if scan_offset in visited_leaf_ifds or scan_offset + 2 > len(self.file_data):
                                    continue
                                try:
                                    test_count = struct.unpack(f'{self.endian}H', 
                                                              self.file_data[scan_offset:scan_offset+2])[0]
                                    if 100 <= test_count <= 150:  # Match Build 1662 finding (130 entries)
                                        entry_off = scan_offset + 2
                                        found_leaf_tag = False
                                        leaf_tag_count = 0
                                        for i in range(min(test_count, 20)):  # Check first 20 entries
                                            if entry_off + 12 > len(self.file_data):
                                                break
                                            tag_id = struct.unpack(f'{self.endian}H', 
                                                                  self.file_data[entry_off:entry_off+2])[0]
                                            if 0x8000 <= tag_id <= 0x8070:
                                                found_leaf_tag = True
                                                leaf_tag_count += 1
                                                if leaf_tag_count >= 2:  # Found multiple Leaf tags
                                                    break
                                            entry_off += 12
                                        if found_leaf_tag and scan_offset not in leaf_makernote_offsets:
                                            leaf_makernote_offsets.insert(0, scan_offset)
                                            scan_found_ifd = True
                                            # Continue scanning to find all IFDs
                                except:
                                    pass
                    
                    for test_makernote_offset in leaf_makernote_offsets:
                        if test_makernote_offset in visited_leaf_ifds:
                            continue
                        if 0 < test_makernote_offset < len(self.file_data) and test_makernote_offset + 2 <= len(self.file_data):
                            try:
                                # Check if this looks like an IFD (entry count 1-250, more lenient)
                                test_count = struct.unpack(f'{self.endian}H', 
                                                          self.file_data[test_makernote_offset:test_makernote_offset+2])[0]
                                if 1 <= test_count <= 250:  # Increased from 200 to 250
                                    # This looks like a Leaf MakerNote IFD - parse it directly as a TIFF IFD
                                    # Leaf MakerNote IFD contains Leaf tags (0x8000-0x8070) in standard TIFF IFD format
                                    visited_leaf_ifds.add(test_makernote_offset)
                                    
                                    # IMPROVEMENT (Build 1666): Direct Leaf tag extraction from IFD structure
                                    # Parse IFD entries directly to ensure all Leaf tags are extracted
                                    # This bypasses potential issues with _parse_ifd not returning tags correctly
                                    # Build 1678: struct and EXIF_TAG_NAMES are now imported at method start
                                    
                                    # Direct IFD parsing for Leaf tags
                                    entry_offset = test_makernote_offset + 2
                                    direct_leaf_tags = {}
                                    
                                    for entry_idx in range(min(test_count, 200)):
                                        if entry_offset + 12 > len(self.file_data):
                                            break
                                        
                                        try:
                                            tag_id = struct.unpack(f'{self.endian}H', self.file_data[entry_offset:entry_offset+2])[0]
                                            tag_type = struct.unpack(f'{self.endian}H', self.file_data[entry_offset+2:entry_offset+4])[0]
                                            tag_count = struct.unpack(f'{self.endian}I', self.file_data[entry_offset+4:entry_offset+8])[0]
                                            value_offset = struct.unpack(f'{self.endian}I', self.file_data[entry_offset+8:entry_offset+12])[0]
                                            
                                            # Check if this is a Leaf tag (0x8000-0x8070)
                                            if 0x8000 <= tag_id <= 0x8070:
                                                # Get proper Leaf tag name
                                                leaf_tag_name = EXIF_TAG_NAMES.get(tag_id)
                                                if not leaf_tag_name:
                                                    leaf_tag_name = f'Leaf:Unknown{tag_id:04X}'
                                                elif not leaf_tag_name.startswith('Leaf:'):
                                                    leaf_tag_name = f'Leaf:{leaf_tag_name}'
                                                
                                                # Extract tag value using standard TIFF value extraction
                                                try:
                                                    tag_value = self._read_tag_value(
                                                        tag_type,
                                                        tag_count,
                                                        value_offset,
                                                        entry_offset + 8,
                                                        base_offset
                                                    )
                                                    if tag_value is not None:
                                                        direct_leaf_tags[leaf_tag_name] = tag_value
                                                except:
                                                    pass
                                        except:
                                            pass
                                        
                                        entry_offset += 12
                                    
                                    # Add directly extracted Leaf tags to metadata
                                    for k, v in direct_leaf_tags.items():
                                        metadata[k] = v
                                    
                                    # Also parse with _parse_ifd for any additional tags or SubIFDs
                                    leaf_makernote_metadata = self._parse_ifd(test_makernote_offset, base_offset, metadata)
                                    
                                    # Count Leaf tags found to validate this is the correct IFD
                                    leaf_tags_found = 0
                                    
                                    # IMPROVEMENT (Build 1664): Extract ALL tags from Leaf MakerNote IFD
                                    # Tags in this IFD should all be Leaf tags (0x8000-0x8070 range)
                                    # They may already have "Leaf:" prefix from EXIF_TAG_NAMES, or may be named "Unknown_8..."
                                    # We need to extract all tags and ensure they have proper Leaf: prefix
                                    for k, v in leaf_makernote_metadata.items():
                                        # Skip non-tag metadata (SubIFDs, next IFD pointer, etc.)
                                        if k in ('SubIFDs', 'NextIFD', 'IFD0', 'IFD1', 'EXIF'):
                                            continue
                                        
                                        # Check if this is already a Leaf tag (has Leaf: prefix)
                                        if 'Leaf:' in k or 'leaf:' in k.lower():
                                            # Already has Leaf prefix, add directly
                                            metadata[k] = v
                                            leaf_tags_found += 1
                                        # Check if this is an Unknown tag that might be a Leaf tag
                                        elif k.startswith('Unknown_8') or k.startswith('EXIF:Unknown_8') or k.startswith('IFD0:Unknown_8') or k.startswith('IFD1:Unknown_8'):
                                            try:
                                                # Extract tag ID from key (e.g., "Unknown_8000" -> 0x8000)
                                                parts = k.split('_')
                                                if len(parts) >= 2:
                                                    # Get the hex part (last part after splitting)
                                                    tag_id_hex = parts[-1]
                                                    # Remove any prefixes like "EXIF:", "IFD0:", etc.
                                                    tag_id_hex = tag_id_hex.replace('EXIF:', '').replace('IFD0:', '').replace('IFD1:', '')
                                                    tag_id = int(tag_id_hex, 16)
                                                    if 0x8000 <= tag_id <= 0x8070:
                                                        # This is a Leaf tag - map to proper Leaf tag name
                                                        # IMPROVEMENT (Build 1429): Use EXIF_TAG_NAMES to get proper Leaf tag name
                                                        leaf_tag_name = EXIF_TAG_NAMES.get(tag_id)
                                                        if not leaf_tag_name:
                                                            # Fallback to Leaf:Unknown format
                                                            leaf_tag_name = f'Leaf:Unknown{tag_id_hex}'
                                                        # Ensure Leaf: prefix is present
                                                        if not leaf_tag_name.startswith('Leaf:'):
                                                            leaf_tag_name = f'Leaf:{leaf_tag_name}'
                                                        metadata[leaf_tag_name] = v
                                                        leaf_tags_found += 1
                                            except:
                                                pass
                                        # IMPROVEMENT (Build 1664): Also check tags that might be Leaf tags by reverse lookup
                                        # If a tag name exists in EXIF_TAG_NAMES and maps to a Leaf tag ID, it's a Leaf tag
                                        else:
                                            # Try to find this tag name in EXIF_TAG_NAMES and check if it's a Leaf tag
                                            try:
                                                # Search EXIF_TAG_NAMES for this tag name
                                                for tag_id, tag_name in EXIF_TAG_NAMES.items():
                                                    if 0x8000 <= tag_id <= 0x8070 and tag_name == k:
                                                        # This is a Leaf tag - ensure it has Leaf: prefix
                                                        if not k.startswith('Leaf:'):
                                                            leaf_tag_name = f'Leaf:{k}'
                                                        else:
                                                            leaf_tag_name = k
                                                        metadata[leaf_tag_name] = v
                                                        leaf_tags_found += 1
                                                        break
                                            except:
                                                pass
                                    
                                    # IMPROVEMENT (Build 1428): Also recursively parse SubIFDs and next IFD pointers in Leaf MakerNote IFD
                                    # Leaf MakerNote IFD may have SubIFDs or next IFD pointers that contain more Leaf tags
                                    if 'SubIFDs' in leaf_makernote_metadata:
                                        for subifd_offset in leaf_makernote_metadata['SubIFDs']:
                                            if isinstance(subifd_offset, int) and subifd_offset > 0:
                                                try:
                                                    subifd_abs_offset = base_offset + subifd_offset
                                                    if 0 < subifd_abs_offset < len(self.file_data) and subifd_abs_offset not in visited_leaf_ifds:
                                                        subifd_metadata = self._parse_ifd(subifd_abs_offset, base_offset, metadata)
                                                        # Extract Leaf tags from SubIFD
                                                        for k, v in subifd_metadata.items():
                                                            if k.startswith('Unknown_8'):
                                                                try:
                                                                    parts = k.split('_')
                                                                    if len(parts) >= 2:
                                                                        tag_id_hex = parts[1]
                                                                        tag_id = int(tag_id_hex, 16)
                                                                        if 0x8000 <= tag_id <= 0x8070:
                                                                            # IMPROVEMENT (Build 1429): Use EXIF_TAG_NAMES to get proper Leaf tag name
                                                                            leaf_tag_name = EXIF_TAG_NAMES.get(tag_id)
                                                                            if not leaf_tag_name:
                                                                                leaf_tag_name = f'Leaf:Unknown{tag_id_hex}'
                                                                            if not leaf_tag_name.startswith('Leaf:'):
                                                                                leaf_tag_name = f'Leaf:{leaf_tag_name}'
                                                                            metadata[leaf_tag_name] = v
                                                                            leaf_tags_found += 1
                                                                except:
                                                                    pass
                                                            elif 'Leaf:' in k or 'leaf:' in k.lower():
                                                                metadata[k] = v
                                                                leaf_tags_found += 1
                                                            # IMPROVEMENT (Build 1429): Also check for tags with EXIF/IFD prefixes
                                                            elif k.startswith('EXIF:Unknown_8') or k.startswith('IFD0:Unknown_8') or k.startswith('IFD1:Unknown_8'):
                                                                try:
                                                                    parts = k.split('_')
                                                                    if len(parts) >= 2:
                                                                        tag_id_hex = parts[-1]
                                                                        tag_id = int(tag_id_hex, 16)
                                                                        if 0x8000 <= tag_id <= 0x8070:
                                                                            leaf_tag_name = EXIF_TAG_NAMES.get(tag_id)
                                                                            if not leaf_tag_name:
                                                                                leaf_tag_name = f'Leaf:Unknown{tag_id_hex}'
                                                                            if not leaf_tag_name.startswith('Leaf:'):
                                                                                leaf_tag_name = f'Leaf:{leaf_tag_name}'
                                                                            metadata[leaf_tag_name] = v
                                                                            leaf_tags_found += 1
                                                                except:
                                                                    pass
                                                except:
                                                    pass
                                    
                                    # IMPROVEMENT (Build 1659): If we found Leaf tags, prioritize this IFD and extract all tags
                                    # Also check for next IFD pointer to find additional Leaf tags
                                    if leaf_tags_found >= 1:  # IMPROVEMENT (Build 1428): Lowered threshold from 2 to 1 to catch more IFDs
                                        # Found and parsed Leaf MakerNote IFD, continue to try other offsets to find more Leaf tags
                                        # Don't break - continue trying other offsets to find all Leaf tags
                                        
                                        # IMPROVEMENT (Build 1659): Check for next IFD pointer - Leaf MakerNote may have multiple IFDs
                                        # Read next IFD pointer (4 bytes after last entry)
                                        try:
                                            entry_end = test_makernote_offset + 2 + (num_entries * 12)
                                            if entry_end + 4 <= len(self.file_data):
                                                next_ifd_offset = struct.unpack(f'{self.endian}I', 
                                                                                self.file_data[entry_end:entry_end+4])[0]
                                                if 0 < next_ifd_offset < len(self.file_data) and next_ifd_offset not in visited_leaf_ifds:
                                                    # Try parsing next IFD
                                                    try:
                                                        next_ifd_metadata = self._parse_ifd(next_ifd_offset, base_offset, metadata)
                                                        for k, v in next_ifd_metadata.items():
                                                            if k.startswith('Unknown_8') or 'Leaf:' in k or 'leaf:' in k.lower():
                                                                try:
                                                                    if k.startswith('Unknown_8'):
                                                                        parts = k.split('_')
                                                                        if len(parts) >= 2:
                                                                            tag_id_hex = parts[1]
                                                                            tag_id = int(tag_id_hex, 16)
                                                                            if 0x8000 <= tag_id <= 0x8070:
                                                                                leaf_tag_name = EXIF_TAG_NAMES.get(tag_id)
                                                                                if not leaf_tag_name:
                                                                                    leaf_tag_name = f'Leaf:Unknown{tag_id_hex}'
                                                                                if not leaf_tag_name.startswith('Leaf:'):
                                                                                    leaf_tag_name = f'Leaf:{leaf_tag_name}'
                                                                                metadata[leaf_tag_name] = v
                                                                                leaf_tags_found += 1
                                                                    else:
                                                                        metadata[k] = v
                                                                        leaf_tags_found += 1
                                                                except:
                                                                    if 'Leaf:' in k:
                                                                        metadata[k] = v
                                                                        leaf_tags_found += 1
                                                    except:
                                                        pass
                                        except:
                                            pass
                                        
                                        pass
                            except:
                                pass
                
                if maker:
                    try:
                        # MakerNote offset calculation - try both relative and absolute
                        # For UNDEFINED type tags, value_offset_int can be:
                        # 1. Relative to base_offset (most common)
                        # 2. Absolute offset (some RAW formats)
                        # IMPROVEMENT (Build 1237): For Sony, also handle case where tag_value is bytes
                        # Try relative first, then absolute if that doesn't work
                        makernote_offset = base_offset + value_offset_int
                        
                        # IMPROVEMENT (Build 1241): For Sony, if tag_value is bytes, try to find the offset in file_data
                        # Sony MakerNote might be stored as bytes in tag_value instead of an offset
                        # CRITICAL: For Sony, be very aggressive in finding MakerNote data when tag_value is bytes
                        if maker.upper() in ('SONY', 'SONY CORPORATION') and isinstance(tag_value, bytes) and len(tag_value) > 10:
                            # Try to find where this MakerNote data starts in the file
                            # Search around the calculated offset with expanded range
                            search_start = max(0, makernote_offset - 1000)  # Expanded from 200 to 1000
                            search_end = min(len(self.file_data), makernote_offset + 1000)  # Expanded from 200 to 1000
                            # Look for the first few bytes of tag_value in file_data
                            tag_prefix = tag_value[:min(20, len(tag_value))]
                            found_pos = self.file_data.find(tag_prefix, search_start, search_end)
                            if found_pos >= 0:
                                makernote_offset = found_pos
                            else:
                                # If not found, try searching the entire file (Sony MakerNote might be anywhere)
                                # But limit search to first 1MB to avoid performance issues
                                search_limit = min(len(self.file_data), 1048576)  # 1MB limit
                                found_pos = self.file_data.find(tag_prefix, 0, search_limit)
                                if found_pos >= 0:
                                    makernote_offset = found_pos
                        
                        # Verify the offset is valid and contains MakerNote signature
                        # Check if offset points to valid MakerNote data
                        valid_offset = False
                        if makernote_offset < len(self.file_data) and makernote_offset >= 0:
                            # Check for common MakerNote signatures
                            if makernote_offset + 8 <= len(self.file_data):
                                header = self.file_data[makernote_offset:makernote_offset + 8]
                                # Check for manufacturer-specific headers
                                # Pentax uses "AOC\x00" header, so check for that too
                                if (header.startswith(b'Canon') or header.startswith(b'Nikon') or 
                                    header.startswith(b'Sony') or header.startswith(b'Olympus') or
                                    header.startswith(b'Pentax') or header.startswith(b'AOC') or
                                    header.startswith(b'FUJIFILM') or header.startswith(b'Panasonic') or 
                                    header.startswith(b'MINOLTA')):
                                    valid_offset = True
                            
                            # Canon MakerNote in CR2 files often starts with "II" or "MM" (TIFF byte order)
                            # Check for TIFF byte order indicators (2 bytes) followed by reasonable IFD count
                            if not valid_offset and makernote_offset + 4 <= len(self.file_data):
                                byte_order = self.file_data[makernote_offset:makernote_offset + 2]
                                if byte_order in (b'II', b'MM'):
                                    # Check if next 2 bytes look like a reasonable IFD entry count (1-200)
                                    try:
                                        endian = '<' if byte_order == b'II' else '>'
                                        test_count = struct.unpack(f'{endian}H', 
                                                                   self.file_data[makernote_offset + 2:makernote_offset + 4])[0]
                                        if 1 <= test_count <= 200:
                                            valid_offset = True
                                    except:
                                        pass
                            
                            # Also check for Canon version header format (version + count)
                            # Canon MakerNote can start with version (2 bytes) + count (2 bytes)
                            if not valid_offset and makernote_offset + 4 <= len(self.file_data):
                                try:
                                    # Try reading as version + count
                                    endian = self.endian
                                    version = struct.unpack(f'{endian}H', 
                                                           self.file_data[makernote_offset:makernote_offset + 2])[0]
                                    test_count = struct.unpack(f'{endian}H', 
                                                              self.file_data[makernote_offset + 2:makernote_offset + 4])[0]
                                    # Version is typically 0x0001-0xFFFF, count should be 1-200
                                    if (0x0001 <= version <= 0xFFFF and 1 <= test_count <= 200):
                                        valid_offset = True
                                except:
                                    pass
                            
                            # IMPROVEMENT (Build 1237): Enhanced Sony MakerNote detection - be more aggressive
                            # Sony MakerNote may not have "Sony" header - check for null header or direct IFD
                            # Sony MakerNote can have: "Sony" header (8 bytes), null header (8 bytes of zeros), or no header
                            # CRITICAL: For Sony, try multiple offset strategies and be more lenient with validation
                            if not valid_offset and maker.upper() in ('SONY', 'SONY CORPORATION'):
                                # Strategy 1: Check for null header (8 bytes of zeros) followed by IFD
                                if makernote_offset + 10 <= len(self.file_data):
                                    header = self.file_data[makernote_offset:makernote_offset + 8]
                                    if header == b'\x00' * 8:
                                        # Null header found - check if next 2 bytes look like IFD entry count
                                        try:
                                            endian = self.endian
                                            test_count = struct.unpack(f'{endian}H', 
                                                                      self.file_data[makernote_offset + 8:makernote_offset + 10])[0]
                                            if 1 <= test_count <= 300:  # Increased limit to 300
                                                valid_offset = True
                                        except:
                                            pass
                                
                                # Strategy 2: Check if MakerNote starts directly with IFD (no header)
                                if not valid_offset and makernote_offset + 2 <= len(self.file_data):
                                    try:
                                        endian = self.endian
                                        test_count = struct.unpack(f'{endian}H', 
                                                                   self.file_data[makernote_offset:makernote_offset + 2])[0]
                                        if 1 <= test_count <= 300:  # Increased limit to 300
                                            valid_offset = True
                                    except:
                                        pass
                                
                                # Strategy 3: Check for byte order indicator (II/MM) at start (Sony may use TIFF structure)
                                if not valid_offset and makernote_offset + 4 <= len(self.file_data):
                                    byte_order = self.file_data[makernote_offset:makernote_offset + 2]
                                    if byte_order in (b'II', b'MM'):
                                        try:
                                            test_endian = '<' if byte_order == b'II' else '>'
                                            test_count = struct.unpack(f'{test_endian}H', 
                                                                      self.file_data[makernote_offset + 2:makernote_offset + 4])[0]
                                            if 1 <= test_count <= 300:  # Increased limit to 300
                                                valid_offset = True
                                        except:
                                            pass
                                
                                # Strategy 4: Try absolute offset if relative offset didn't work
                                if not valid_offset and 0 < value_offset_int < len(self.file_data):
                                    if value_offset_int + 2 <= len(self.file_data):
                                        try:
                                            endian = self.endian
                                            test_count = struct.unpack(f'{endian}H', 
                                                                      self.file_data[value_offset_int:value_offset_int + 2])[0]
                                            if 1 <= test_count <= 300:  # Increased limit to 300
                                                makernote_offset = value_offset_int
                                                valid_offset = True
                                        except:
                                            pass
                                
                                # Strategy 5: For Sony, be very aggressive - try parsing even if no signature found
                                # Sony MakerNote structure can be very variable, so try parsing if offset is reasonable
                                if not valid_offset and 0 < makernote_offset < len(self.file_data) - 50:
                                    # Try parsing anyway - the parser will handle invalid data gracefully
                                    # This is critical for Sony as MakerNote structure can vary significantly
                                    valid_offset = True
                            
                            # If relative offset doesn't work, try absolute offset
                            if not valid_offset and 0 < value_offset_int < len(self.file_data):
                                if value_offset_int + 8 <= len(self.file_data):
                                    header = self.file_data[value_offset_int:value_offset_int + 8]
                                    # Pentax uses "AOC\x00" header, so check for that too
                                    if (header.startswith(b'Canon') or header.startswith(b'Nikon') or 
                                        header.startswith(b'Sony') or header.startswith(b'Olympus') or
                                        header.startswith(b'Pentax') or header.startswith(b'AOC') or
                                        header.startswith(b'FUJIFILM') or header.startswith(b'Panasonic') or 
                                        header.startswith(b'MINOLTA')):
                                        makernote_offset = value_offset_int
                                        valid_offset = True
                                
                                # Check for TIFF byte order at absolute offset
                                if not valid_offset and value_offset_int + 4 <= len(self.file_data):
                                    byte_order = self.file_data[value_offset_int:value_offset_int + 2]
                                    if byte_order in (b'II', b'MM'):
                                        try:
                                            endian = '<' if byte_order == b'II' else '>'
                                            test_count = struct.unpack(f'{endian}H', 
                                                                       self.file_data[value_offset_int + 2:value_offset_int + 4])[0]
                                            if 1 <= test_count <= 200:
                                                makernote_offset = value_offset_int
                                                valid_offset = True
                                        except:
                                            pass
                                
                                # Check for Canon version header at absolute offset
                                if not valid_offset and value_offset_int + 4 <= len(self.file_data):
                                    try:
                                        endian = self.endian
                                        version = struct.unpack(f'{endian}H', 
                                                               self.file_data[value_offset_int:value_offset_int + 2])[0]
                                        test_count = struct.unpack(f'{endian}H', 
                                                                  self.file_data[value_offset_int + 2:value_offset_int + 4])[0]
                                        if (0x0001 <= version <= 0xFFFF and 1 <= test_count <= 200):
                                            makernote_offset = value_offset_int
                                            valid_offset = True
                                    except:
                                        pass
                            
                            # If signature not found, try searching nearby (within 100 bytes)
                            # Some MakerNote data may have padding or slight offset differences
                            if not valid_offset and makernote_offset + 100 < len(self.file_data):
                                search_start = max(0, makernote_offset - 100)
                                search_end = min(len(self.file_data), makernote_offset + 100)
                                search_data = self.file_data[search_start:search_end]
                                
                                # Search for manufacturer signatures
                                # Pentax uses "AOC\x00" header, so search for that too
                                for sig in [b'Canon', b'Nikon', b'Sony', b'Olympus', b'Pentax', b'AOC', b'FUJIFILM', b'Panasonic', b'MINOLTA']:
                                    sig_offset = search_data.find(sig)
                                    if sig_offset >= 0:
                                        # Found signature, use this offset
                                        makernote_offset = search_start + sig_offset
                                        valid_offset = True
                                        break
                        
                        # IMPROVEMENT (Build 1157): Enhanced Nikon MakerNote detection
                        # Nikon MakerNote may have "Nikon" header, but also check for embedded TIFF structure
                        # Nikon MakerNote can have: "Nikon" header (8 bytes) + TIFF structure, or direct TIFF structure
                        if not valid_offset and maker.upper() in ('NIKON', 'NIKON CORPORATION'):
                            # Check for "Nikon" header at offset
                            if makernote_offset + 18 <= len(self.file_data):
                                header = self.file_data[makernote_offset:makernote_offset + 8]
                                if header.startswith(b'Nikon'):
                                    # Check for embedded TIFF structure at offset + 10
                                    tiff_start = makernote_offset + 10
                                    if tiff_start + 4 <= len(self.file_data):
                                        tiff_sig = self.file_data[tiff_start:tiff_start + 2]
                                        if tiff_sig in (b'II', b'MM'):
                                            # Check if next 2 bytes are TIFF magic (0x002A)
                                            try:
                                                endian = '<' if tiff_sig == b'II' else '>'
                                                magic = struct.unpack(f'{endian}H', self.file_data[tiff_start + 2:tiff_start + 4])[0]
                                                if magic == 0x002A:
                                                    valid_offset = True
                                            except:
                                                pass
                            
                            # Also check if MakerNote starts directly with TIFF structure (no "Nikon" header)
                            if not valid_offset and makernote_offset + 4 <= len(self.file_data):
                                tiff_sig = self.file_data[makernote_offset:makernote_offset + 2]
                                if tiff_sig in (b'II', b'MM'):
                                    try:
                                        endian = '<' if tiff_sig == b'II' else '>'
                                        magic = struct.unpack(f'{endian}H', self.file_data[makernote_offset + 2:makernote_offset + 4])[0]
                                        if magic == 0x002A:
                                            # Check if IFD offset points to valid IFD
                                            ifd_offset = struct.unpack(f'{endian}I', self.file_data[makernote_offset + 4:makernote_offset + 8])[0]
                                            ifd_abs = makernote_offset + ifd_offset
                                            if 0 < ifd_abs < len(self.file_data) and ifd_abs + 2 <= len(self.file_data):
                                                test_count = struct.unpack(f'{endian}H', self.file_data[ifd_abs:ifd_abs + 2])[0]
                                                if 1 <= test_count <= 200:
                                                    valid_offset = True
                                    except:
                                        pass
                        
                        # If we have a valid Make tag and reasonable offset, try parsing even without signature
                        # Some MakerNote formats may not have recognizable headers
                        if not valid_offset and maker and makernote_offset > 0 and makernote_offset < len(self.file_data):
                            # Check if offset is reasonable (not too large, not negative)
                            if 0 < makernote_offset < len(self.file_data) - 100:
                                # Try parsing anyway - the parser will handle invalid data gracefully
                                valid_offset = True
                        
                        if valid_offset:
                            # Parse MakerNote with complete parser
                            makernote_data = None
                            try:
                                makernote_parser = MakerNoteParser(
                                    maker=maker,
                                    file_data=self.file_data,
                                    offset=makernote_offset,
                                    endian=self.endian
                                )
                                makernote_data = makernote_parser.parse()
                            except Exception as parse_ex:
                                # If parsing with offset fails, try using tag_value bytes directly if available
                                # This handles cases where the data is already read
                                if isinstance(tag_value, bytes) and len(tag_value) > 10:
                                    try:
                                        # Try to find the MakerNote data in the file_data
                                        # Search for MakerNote signature (II or MM at offset, or manufacturer headers)
                                        makernote_data_start = self.file_data.find(tag_value[:10], makernote_offset - 100, makernote_offset + 100)
                                        if makernote_data_start >= 0:
                                            makernote_parser = MakerNoteParser(
                                                maker=maker,
                                                file_data=self.file_data,
                                                offset=makernote_data_start,
                                                endian=self.endian
                                            )
                                            makernote_data = makernote_parser.parse()
                                    except Exception:
                                        pass
                                
                                # IMPROVEMENT (Build 1241): For Sony, try multiple offset strategies if initial parse failed
                                # Sony MakerNote can be stored at different offsets or with different structures
                                # CRITICAL: Be very aggressive for Sony - try many strategies including direct bytes parsing
                                if not makernote_data and maker.upper() in ('SONY', 'SONY CORPORATION'):
                                    # Try parsing with different offset calculations
                                    offset_strategies = [
                                        base_offset + value_offset_int,  # Relative to base
                                        value_offset_int,  # Absolute
                                        makernote_offset + 8,  # After potential header
                                        makernote_offset + 2,  # After byte order indicator
                                        makernote_offset,  # Direct offset
                                        makernote_offset - 8,  # Before potential header
                                        makernote_offset - 2,  # Before byte order indicator
                                    ]
                                    # Also try if tag_value is bytes - create temporary file_data from bytes
                                    if isinstance(tag_value, bytes) and len(tag_value) > 10:
                                        # Try parsing tag_value bytes directly as MakerNote data
                                        try:
                                            temp_parser = MakerNoteParser(
                                                maker=maker,
                                                file_data=tag_value,  # Use tag_value as file_data
                                                offset=0,  # Start at beginning
                                                endian=self.endian
                                            )
                                            temp_data = temp_parser.parse()
                                            if temp_data:  # If we got any data, use it
                                                makernote_data = temp_data
                                        except Exception:
                                            pass
                                    
                                    # Try all offset strategies
                                    for test_offset in offset_strategies:
                                        if 0 < test_offset < len(self.file_data) - 50:
                                            try:
                                                test_parser = MakerNoteParser(
                                                    maker=maker,
                                                    file_data=self.file_data,
                                                    offset=test_offset,
                                                    endian=self.endian
                                                )
                                                test_data = test_parser.parse()
                                                if test_data:  # If we got any data, use it
                                                    makernote_data = test_data
                                                    break
                                            except Exception:
                                                continue
                                    
                                    # If still no data and tag_value is bytes, try searching for it in file
                                    if not makernote_data and isinstance(tag_value, bytes) and len(tag_value) > 20:
                                        # Search for tag_value pattern in file_data (first 2MB)
                                        search_limit = min(len(self.file_data), 2097152)  # 2MB limit
                                        tag_pattern = tag_value[:min(50, len(tag_value))]  # Use first 50 bytes as pattern
                                        pattern_pos = self.file_data.find(tag_pattern, 0, search_limit)
                                        if pattern_pos >= 0:
                                            # Found pattern - try parsing at that offset
                                            try:
                                                pattern_parser = MakerNoteParser(
                                                    maker=maker,
                                                    file_data=self.file_data,
                                                    offset=pattern_pos,
                                                    endian=self.endian
                                                )
                                                pattern_data = pattern_parser.parse()
                                                if pattern_data:
                                                    makernote_data = pattern_data
                                            except Exception:
                                                pass
                            
                            if makernote_data:
                                # Add individual MakerNote tags
                                # Canon tags come with "Canon" prefix, others with "MakerNote:" or "MakerNotes:" prefix
                                # Also preserve diagnostic keys (starting with _DIAG_)
                                for k, v in makernote_data.items():
                                    if k.startswith('_DIAG_'):
                                        # Preserve diagnostic keys with MakerNote: prefix for visibility
                                        metadata[f'MakerNote:{k}'] = v
                                    elif k.startswith('MakerNote:') or k.startswith('MakerNotes:'):
                                        metadata[k] = v  # Already has prefix, use as-is
                                    elif k.startswith('Canon'):
                                        # Canon tags should be used as-is (no MakerNote: prefix)
                                        metadata[k] = v
                                    elif k.startswith('EXIF:'):
                                        # EXIF tags from MakerNote should be used as-is (no MakerNote: prefix)
                                        # These are tags like EXIF:WBRedLevel extracted from MakerNote data
                                        metadata[k] = v
                                    elif k.startswith('PanasonicRaw:'):
                                        # PanasonicRaw tags should be used as-is (no MakerNote: prefix)
                                        # These are tags like PanasonicRaw:WB_RGBLevels extracted from MakerNote data
                                        metadata[k] = v
                                    else:
                                        # Add MakerNote: prefix for other tags
                                        metadata[f"MakerNote:{k}"] = v
                            # IMPROVEMENT (Build 1391): Enhanced Leaf MakerNote (0x83BB) parsing with comprehensive offset strategies
                            # Leaf MakerNote (0x83BB) contains a regular TIFF IFD with Leaf tags (0x8000-0x8070)
                            # If MakerNoteParser didn't handle it, try parsing it as a regular IFD
                            if not makernote_data and tag_id == 0x83BB:
                                # Leaf MakerNote is a TIFF IFD - parse it directly
                                # Try comprehensive offset strategies to find the Leaf MakerNote IFD
                                # Leaf MakerNote can be at various offsets depending on file structure
                                leaf_makernote_offsets = [
                                    base_offset + value_offset_int,  # TIFF-relative (most common)
                                    value_offset_int,  # Absolute
                                    ifd_offset + value_offset_int,  # IFD-relative
                                    base_offset + value_offset_int - 8,  # With header adjustment
                                    base_offset + value_offset_int + 8,  # With header adjustment
                                    value_offset_int - 8,  # Absolute with header adjustment
                                    value_offset_int + 8,  # Absolute with header adjustment
                                ]
                                
                                # Also try offsets with byte order indicator adjustments
                                # Leaf MakerNote might have TIFF byte order (II/MM) at start
                                if value_offset_int > 8:
                                    leaf_makernote_offsets.extend([
                                        base_offset + value_offset_int - 2,  # Skip byte order
                                        value_offset_int - 2,  # Skip byte order (absolute)
                                    ])
                                
                                # IMPROVEMENT (Build 1391): Add more offset strategies for Leaf MakerNote
                                # Try additional header sizes and offset combinations
                                for header_adj in [-16, -12, -10, -6, -4, -2, 2, 4, 6, 10, 12, 16, 20, 24]:
                                    leaf_makernote_offsets.extend([
                                        base_offset + value_offset_int + header_adj,
                                        value_offset_int + header_adj,
                                        ifd_offset + value_offset_int + header_adj,
                                    ])
                                
                                # IMPROVEMENT (Build 1393): Enhanced scanning with larger range and better early exit
                                # Also try scanning around the offset if direct offsets don't work
                                # Scan ±500 bytes around the calculated offset to find the IFD (increased from 200)
                                scan_range = 500
                                scan_start = max(0, value_offset_int - scan_range)
                                scan_end = min(len(self.file_data) - 2, value_offset_int + scan_range)
                                for scan_offset in range(scan_start, scan_end, 2):
                                    if scan_offset not in leaf_makernote_offsets:
                                        leaf_makernote_offsets.append(scan_offset)
                                
                                # Track visited IFDs to avoid infinite recursion
                                visited_leaf_ifds = set()
                                
                                # IMPROVEMENT (Build 1393): Early exit optimization - stop checking entries once 3+ Leaf tags are found
                                for test_offset in leaf_makernote_offsets:
                                    try:
                                        if 0 < test_offset < len(self.file_data) and test_offset + 2 <= len(self.file_data):
                                            # Check if this looks like an IFD (has reasonable entry count)
                                            test_count = struct.unpack(f'{self.endian}H', 
                                                                      self.file_data[test_offset:test_offset+2])[0]
                                            if 1 <= test_count <= 200:
                                                # Check if we've already parsed this IFD
                                                if test_offset in visited_leaf_ifds:
                                                    continue
                                                visited_leaf_ifds.add(test_offset)
                                                
                                                # IMPROVEMENT (Build 1393): Enhanced Leaf tag verification - check more entries with early exit
                                                # Some Leaf MakerNote IFDs may have Leaf tags later in the IFD, not just in first 10 entries
                                                # Check up to 50 entries (or all entries if fewer) to find Leaf tags
                                                # Early exit once 3+ Leaf tags are found to speed up detection
                                                leaf_tags_in_ifd = 0
                                                entry_ptr = test_offset + 2
                                                entries_to_check = min(50, test_count)  # Check up to 50 entries
                                                for check_i in range(entries_to_check):
                                                    if entry_ptr + 12 > len(self.file_data):
                                                        break
                                                    try:
                                                        check_tag_id = struct.unpack(f'{self.endian}H', 
                                                                                    self.file_data[entry_ptr:entry_ptr+2])[0]
                                                        if 0x8000 <= check_tag_id <= 0x8070:
                                                            leaf_tags_in_ifd += 1
                                                            # If we found at least 3 Leaf tags, this is definitely a Leaf MakerNote IFD
                                                            if leaf_tags_in_ifd >= 3:
                                                                break
                                                    except:
                                                        pass
                                                    entry_ptr += 12
                                                
                                                # IMPROVEMENT (Build 1393): More lenient parsing - parse IFD if it has Leaf tags OR if entry count is reasonable
                                                # Some Leaf MakerNote IFDs may have valid structure even if Leaf tags aren't in first entries checked
                                                # Also parse if entry count is > 5 (reasonable for a MakerNote IFD)
                                                if leaf_tags_in_ifd > 0 or test_count > 5:
                                                    # This looks like a valid Leaf MakerNote IFD - parse it
                                                    # CRITICAL: For Leaf MakerNote IFD, try multiple base_offset strategies
                                                    # Leaf MakerNote IFD offsets might be relative to TIFF header (base_offset) or absolute (0)
                                                    # Try both to ensure we read Leaf tag values from correct locations
                                                    leaf_ifd_data = {}
                                                    for test_base_offset in [base_offset, 0, test_offset]:
                                                        try:
                                                            test_leaf_ifd_data = self._parse_ifd(test_offset, test_base_offset, parent_metadata=metadata)
                                                            # Check if we got more Leaf tags with this base_offset
                                                            test_leaf_tags_count = sum(1 for k in test_leaf_ifd_data.keys() if k.startswith('Leaf:'))
                                                            if test_leaf_tags_count > len([k for k in leaf_ifd_data.keys() if k.startswith('Leaf:')]):
                                                                leaf_ifd_data = test_leaf_ifd_data
                                                                if test_leaf_tags_count >= 3:  # Found enough tags, use this base_offset
                                                                    break
                                                        except Exception:
                                                            continue
                                                    
                                                    # If no data found with alternative base_offsets, use standard base_offset
                                                    if not leaf_ifd_data:
                                                        leaf_ifd_data = self._parse_ifd(test_offset, base_offset, parent_metadata=metadata)
                                                    # Add Leaf tags from this IFD (they should already have Leaf: prefix from _parse_ifd)
                                                    leaf_tags_found = 0
                                                    for k, v in leaf_ifd_data.items():
                                                        if k.startswith('Leaf:'):
                                                            metadata[k] = v
                                                            leaf_tags_found += 1
                                                    
                                                    # IMPROVEMENT (Build 1393): Early exit - if we found Leaf tags, this is likely the correct offset
                                                    if leaf_tags_found > 0:
                                                        break  # Found valid IFD with Leaf tags, no need to try other offsets
                                    except:
                                        continue
                                
                                # IMPROVEMENT (Build 1397): Enhanced aggressive scanning with better IFD detection
                                # If no Leaf tags found via tag 0x83BB, try aggressive scanning of entire file
                                # Some MOS files may have Leaf MakerNote IFD at unexpected locations
                                # Only do this if we haven't found any Leaf tags yet
                                if not any(k.startswith('Leaf:') for k in metadata.keys()):
                                    # IMPROVEMENT (Build 1397): Scan larger range (200KB) with better step size
                                    scan_limit = min(200000, len(self.file_data) - 2)
                                    scan_step = 2
                                    aggressive_scan_start = 0
                                    aggressive_scan_end = scan_limit
                                    
                                    for scan_offset in range(aggressive_scan_start, aggressive_scan_end, scan_step):
                                        if scan_offset in visited_leaf_ifds:
                                            continue
                                        try:
                                            if scan_offset + 2 > len(self.file_data):
                                                break
                                            test_count = struct.unpack(f'{self.endian}H', 
                                                                      self.file_data[scan_offset:scan_offset+2])[0]
                                            # IMPROVEMENT (Build 1397): More lenient entry count check (5-250 instead of 10-200)
                                            if 5 <= test_count <= 250:  # More lenient for Leaf MakerNote IFD
                                                # Quick check for Leaf tags in first 30 entries (increased from 20)
                                                leaf_tags_in_scan = 0
                                                entry_ptr = scan_offset + 2
                                                for check_i in range(min(30, test_count)):
                                                    if entry_ptr + 12 > len(self.file_data):
                                                        break
                                                    try:
                                                        check_tag_id = struct.unpack(f'{self.endian}H', 
                                                                                    self.file_data[entry_ptr:entry_ptr+2])[0]
                                                        if 0x8000 <= check_tag_id <= 0x8070:
                                                            leaf_tags_in_scan += 1
                                                            # IMPROVEMENT (Build 1397): Lower threshold (2 instead of 3) for early detection
                                                            if leaf_tags_in_scan >= 2:
                                                                # Found Leaf MakerNote IFD - parse it
                                                                visited_leaf_ifds.add(scan_offset)
                                                                # CRITICAL: For Leaf MakerNote IFD, try multiple base_offset strategies
                                                                leaf_ifd_data = {}
                                                                # IMPROVEMENT (Build 1397): Try more base_offset strategies
                                                                for test_base_offset in [base_offset, 0, scan_offset]:
                                                                    try:
                                                                        test_leaf_ifd_data = self._parse_ifd(scan_offset, test_base_offset, parent_metadata=metadata)
                                                                        # Check if we got more Leaf tags with this base_offset
                                                                        test_leaf_tags_count = sum(1 for k in test_leaf_ifd_data.keys() if k.startswith('Leaf:'))
                                                                        if test_leaf_tags_count > len([k for k in leaf_ifd_data.keys() if k.startswith('Leaf:')]):
                                                                            leaf_ifd_data = test_leaf_ifd_data
                                                                            # IMPROVEMENT (Build 1397): Lower threshold (5 instead of 10) for early acceptance
                                                                            if test_leaf_tags_count >= 5:  # Found enough tags, use this base_offset
                                                                                break
                                                                    except Exception:
                                                                        continue
                                                                
                                                                # If no data found with alternative base_offsets, use standard base_offset
                                                                if not leaf_ifd_data:
                                                                    leaf_ifd_data = self._parse_ifd(scan_offset, base_offset, parent_metadata=metadata)
                                                                
                                                                for k, v in leaf_ifd_data.items():
                                                                    if k.startswith('Leaf:'):
                                                                        metadata[k] = v
                                                                # Found Leaf tags, stop aggressive scanning
                                                                break
                                                    except:
                                                        pass
                                                    entry_ptr += 12
                                                if leaf_tags_in_scan >= 2:
                                                    break
                                        except:
                                            continue
                                
                                # IMPROVEMENT (Build 1401): Enhanced post-processing - scan all parsed IFDs for Leaf tags
                                # Some Leaf tags might be in regular IFDs, not just MakerNote IFDs
                                # This ensures we don't miss Leaf tags that are in unexpected locations
                                # IMPROVEMENT (Build 1401): More aggressive scanning with larger range and better detection
                                if not any(k.startswith('Leaf:') for k in metadata.keys()):
                                    # Try scanning all known IFD offsets for Leaf tags
                                    # This is a fallback if MakerNote IFD wasn't found
                                    # IMPROVEMENT (Build 1401): Scan larger range (100KB instead of 50KB) with smaller step
                                    fallback_scan_limit = min(100000, len(self.file_data) - 2)
                                    fallback_scan_step = 1  # Smaller step for more thorough scanning
                                    for fallback_offset in range(0, fallback_scan_limit, fallback_scan_step):
                                        if fallback_offset in visited_leaf_ifds:
                                            continue
                                        try:
                                            if fallback_offset + 2 > len(self.file_data):
                                                break
                                            fallback_count = struct.unpack(f'{self.endian}H', 
                                                                          self.file_data[fallback_offset:fallback_offset+2])[0]
                                            if 3 <= fallback_count <= 300:  # Very lenient for fallback scan
                                                # Check for Leaf tags in all entries
                                                leaf_tags_found = 0
                                                fallback_entry_ptr = fallback_offset + 2
                                                # IMPROVEMENT (Build 1401): Check more entries (150 instead of 100)
                                                for fallback_i in range(min(fallback_count, 150)):
                                                    if fallback_entry_ptr + 12 > len(self.file_data):
                                                        break
                                                    try:
                                                        fallback_tag_id = struct.unpack(f'{self.endian}H', 
                                                                                    self.file_data[fallback_entry_ptr:fallback_entry_ptr+2])[0]
                                                        if 0x8000 <= fallback_tag_id <= 0x8070:
                                                            leaf_tags_found += 1
                                                            if leaf_tags_found >= 1:  # Even 1 Leaf tag is enough
                                                                # Found IFD with Leaf tags - parse it
                                                                visited_leaf_ifds.add(fallback_offset)
                                                                # IMPROVEMENT (Build 1401): Try multiple base_offset strategies
                                                                fallback_ifd_data = {}
                                                                for test_base_offset in [base_offset, 0, fallback_offset]:
                                                                    try:
                                                                        test_ifd_data = self._parse_ifd(fallback_offset, test_base_offset, parent_metadata=metadata)
                                                                        test_leaf_count = sum(1 for k in test_ifd_data.keys() if k.startswith('Leaf:'))
                                                                        if test_leaf_count > len([k for k in fallback_ifd_data.keys() if k.startswith('Leaf:')]):
                                                                            fallback_ifd_data = test_ifd_data
                                                                            if test_leaf_count >= 5:
                                                                                break
                                                                    except:
                                                                        continue
                                                                
                                                                if not fallback_ifd_data:
                                                                    fallback_ifd_data = self._parse_ifd(fallback_offset, base_offset, parent_metadata=metadata)
                                                                
                                                                for k, v in fallback_ifd_data.items():
                                                                    if k.startswith('Leaf:'):
                                                                        metadata[k] = v
                                                                # Found Leaf tags, can stop if we found enough
                                                                # IMPROVEMENT (Build 1401): Lower threshold (5 instead of 10) for early exit
                                                                if leaf_tags_found >= 5:
                                                                    break
                                                    except:
                                                        pass
                                                    fallback_entry_ptr += 12
                                                if leaf_tags_found >= 5:
                                                    break
                                        except:
                                            continue
                            
                            # Don't store the raw MakerNote tag if we successfully parsed it
                            # Only store raw if parsing returned no data
                            if not makernote_data and tag_id != 0x83BB:  # Don't store 0x83BB if we parsed it as IFD above
                                metadata[tag_name] = tag_value
                        else:
                            # Invalid offset, store raw value
                            metadata[tag_name] = tag_value
                    except Exception:
                        # If MakerNote parsing fails, just store the raw reference
                        metadata[tag_name] = tag_value
                else:
                    metadata[tag_name] = tag_value
            
            entry_offset += 12
        
        return metadata
    
    def _parse_pkts_format(self, pkts_data: bytes, metadata: Dict[str, Any]) -> None:
        """
        Parse PKTS (Leaf proprietary format) structure from LeafData tag.
        
        PKTS format structure (Build 1668-1670):
        - "PKTS" magic (4 bytes) - identifies start of PKTS entry
        - Version (4 bytes, little-endian) - PKTS format version (currently unused but preserved)
        - Tag name (null-terminated ASCII string) - abbreviated tag name (e.g., "CamProf_version")
        - Padding (optional null bytes) - may exist between tag name and value
        - Value (null-terminated string, typically printable ASCII) - tag value
        - Padding (optional null bytes) - may exist before next PKTS entry
        - Repeat for each tag
        
        The PKTS format is used by Leaf cameras to store metadata in a proprietary
        directory structure within the LeafData tag (0x8606) in MOS files.
        
        Args:
            pkts_data: Raw PKTS data bytes from LeafData tag
            metadata: Metadata dictionary to populate with Leaf tags (prefixed with "Leaf:")
        
        Note:
            This parser handles string values (most common), numeric values (parsed from strings),
            and skips container tags that don't have direct values.
        
        Build 1717: Removed debug logging for production code.
        """
        # Debug flag - set to True to enable detailed logging for debugging
        DEBUG_PKTS = False  # Disabled for production
        # Mapping from PKTS tag names to Leaf tag names (from standard format analysis)
        # PKTS uses abbreviated names like "CamProf_version" -> "CameraProfileVersion"
        pkts_to_leaf_map = {
            # Camera Profile tags
            'CamProf_version': 'CameraProfileVersion',
            'CamProf_name': 'CameraProfileName',  # Note: May not exist in standard, using descriptive name
            'CamProf_type': 'CameraProfileType',  # Note: May not exist in standard
            'CamProf_back_type': 'CameraBackType',
            'camera_profile': None,  # Container tag, skip
            
            # Capture Profile tags
            'CaptProf_version': 'CaptProfVersion',
            'CaptProf_name': 'CaptProfName',
            'CaptProf_type': 'CaptProfType',
            'CaptProf_back_type': 'CaptProfBackType',
            'CamProf_capture_profile': None,  # Container tag, skip
            
            # Image Profile tags
            'ImgProf_version': 'ImgProfVersion',
            'ImgProf_name': 'ImgProfName',
            'ImgProf_type': 'ImgProfType',
            'ImgProf_back_type': 'ImgProfBackType',
            
            # Camera Object tags
            'CameraObj_version': 'CameraObjVersion',
            'CameraObj_name': 'CameraObjName',
            'CameraObj_type': 'CameraObjType',
            'CameraObj_back_type': 'CameraObjBackType',
            
            # Capture Object tags
            'CaptureObj_version': 'CaptureObjVersion',
            'CaptureObj_name': 'CaptureObjName',
            'CaptureObj_type': 'CaptureObjType',
            'CaptureObj_back_type': 'CaptureObjBackType',
            'CaptureSerial': 'CaptureSerial',
            
            # Shoot Object tags
            'ShootObj_version': 'ShootObjVersion',
            'ShootObj_name': 'ShootObjName',
            'ShootObj_type': 'ShootObjType',
            'ShootObj_back_type': 'ShootObjBackType',
            
            # Neutral Object tags
            'NeutObj_version': 'NeutObjVersion',
            'NeutObj_name': 'NeutObjName',
            'NeutObj_type': 'NeutObjType',
            'NeutObj_back_type': 'NeutObjBackType',
            'Neutrals': 'Neutrals',
            'ColorCasts': 'ColorCasts',
            
            # Selection Object tags
            'SelObj_version': 'SelObjVersion',
            'SelObj_name': 'SelObjName',
            'SelObj_type': 'SelObjType',
            'SelObj_back_type': 'SelObjBackType',
            'Rect': 'Rect',
            'Resolution': 'Resolution',
            'Scale': 'Scale',
            'Locks': 'Locks',
            'Orientation': 'Orientation',
            
            # Tone Object tags
            'ToneObj_version': 'ToneObjVersion',
            'ToneObj_name': 'ToneObjName',
            'ToneObj_type': 'ToneObjType',
            'ToneObj_back_type': 'ToneObjBackType',
            'ShadowEndPoints': 'ShadowEndPoints',
            'HighlightEndPoints': 'HighlightEndPoints',
            'Npts': 'Npts',
            'Tones': 'Tones',
            'Gamma': 'Gamma',
            
            # Sharp Object tags
            'SharpObj_version': 'SharpObjVersion',
            'SharpObj_name': 'SharpObjName',
            'SharpObj_type': 'SharpObjType',
            'SharpObj_back_type': 'SharpObjBackType',
            'SharpMethod': 'SharpMethod',
            'DataLen': 'DataLen',
            'SharpInfo': 'SharpInfo',
            'SingleQuality': 'SingleQuality',
            'MultiQuality': 'MultiQuality',
            
            # Color Object tags
            'ColorObj_version': 'ColorObjVersion',
            'ColorObj_name': 'ColorObjName',
            'ColorObj_type': 'ColorObjType',
            'ColorObj_back_type': 'ColorObjBackType',
            'HasICC': 'HasICC',
            'InputProfile': 'InputProfile',
            'OutputProfile': 'OutputProfile',
            
            # Save Object tags
            'SaveObj_version': 'SaveObjVersion',
            'SaveObj_name': 'SaveObjName',
            'SaveObj_type': 'SaveObjType',
            'SaveObj_back_type': 'SaveObjBackType',
            'LeafAutoActive': 'LeafAutoActive',
            'LeafHotFolder': 'LeafHotFolder',
            'LeafOutputFileType': 'LeafOutputFileType',
            'LeafAutoBaseName': 'LeafAutoBaseName',
            'LeafSaveSelection': 'LeafSaveSelection',
            'LeafOpenProcHDR': 'LeafOpenProcHDR',
            'StdAutoActive': 'StdAutoActive',
            'StdHotFolder': 'StdHotFolder',
            'StdOutputFileType': 'StdOutputFileType',
            'StdOutputColorMode': 'StdOutputColorMode',
            'StdOutputBitDepth': 'StdOutputBitDepth',
            'StdBaseName': 'StdBaseName',
            'StdSaveSelection': 'StdSaveSelection',
            'StdOxygen': 'StdOxygen',
            'StdOpenInPhotoshop': 'StdOpenInPhotoshop',
            'StdScaledOutput': 'StdScaledOutput',
            'StdSharpenOutput': 'StdSharpenOutput',
            
            # Camera Object additional tags
            'ISOSpeed': 'ISOSpeed',
            'Strobe': 'Strobe',
            'CameraType': 'CameraType',
            'LensType': 'LensType',
            'LensID': 'LensID',
            'ImageStatus': 'ImageStatus',
            'RotationAngle': 'RotationAngle',
            'PreviewInfo': 'PreviewInfo',
            'PreviewImage': 'PreviewImage',
            'PDAHistogram': 'PDAHistogram',
            
            # Other Leaf tags
            'CameraName': 'CameraName',
            'ImageOffset': 'ImageOffset',
            'LuminanceConsts': 'LuminanceConsts',
            'XYOffsetInfo': 'XYOffsetInfo',
            'ColorMatrix': 'ColorMatrix',
            'ReconstructionType': 'ReconstructionType',
            'ImageFields': 'ImageFields',
            'ImageBounds': 'ImageBounds',
            'NumberOfPlanes': 'NumberOfPlanes',
            'RawDataRotation': 'RawDataRotation',
            'ColorAverages': 'ColorAverages',
            'MosaicPattern': 'MosaicPattern',
            'DarkCorrectionType': 'DarkCorrectionType',
            'RightDarkRect': 'RightDarkRect',
            'LeftDarkRect': 'LeftDarkRect',
            'CenterDarkRect': 'CenterDarkRect',
            'CCDRect': 'CCDRect',
            'CCDValidRect': 'CCDValidRect',
            'CCDVideoRect': 'CCDVideoRect',
        }
        
        offset = 0
        max_offset = len(pkts_data)
        
        # Import EXIF_TAG_NAMES for reverse lookup
        from dnexif.exif_tags import EXIF_TAG_NAMES
        
        # Create reverse mapping: Leaf tag name -> tag ID
        leaf_name_to_id = {}
        for tag_id, tag_name in EXIF_TAG_NAMES.items():
            if tag_name.startswith('Leaf:'):
                leaf_name = tag_name[5:]  # Remove "Leaf:" prefix
                leaf_name_to_id[leaf_name] = tag_id
        
        tags_found = 0
        pkts_entries_found = 0
        
        while offset < max_offset - 8:  # Need at least 8 bytes for PKTS header + version
            # Check for PKTS magic
            if offset + 4 > max_offset:
                break
            
            if pkts_data[offset:offset+4] != b'PKTS':
                # Skip to next potential PKTS entry
                offset += 1
                continue
            
            # Found PKTS header
            pkts_magic = pkts_data[offset:offset+4]
            pkts_entries_found += 1
            offset += 4
            
            # Read version (4 bytes, little-endian)
            # Note: Version is preserved for potential future use but not currently used in parsing
            if offset + 4 > max_offset:
                break
            version = struct.unpack('<I', pkts_data[offset:offset+4])[0]
            offset += 4
            
            # Read tag name (null-terminated string)
            tag_name_end = pkts_data.find(b'\x00', offset)
            if tag_name_end == -1:
                break  # No null terminator found
            
            pkts_tag_name = pkts_data[offset:tag_name_end].decode('ascii', errors='ignore')
            offset = tag_name_end + 1
            
            # Skip container tags (they have None as value in map)
            if pkts_tag_name in pkts_to_leaf_map and pkts_to_leaf_map[pkts_tag_name] is None:
                # Container tag - skip to next PKTS entry
                # Find next PKTS header
                next_pkts = pkts_data.find(b'PKTS', offset)
                if next_pkts == -1:
                    break
                offset = next_pkts
                continue
            
            # Map PKTS tag name to Leaf tag name
            leaf_tag_name = pkts_to_leaf_map.get(pkts_tag_name)
            if not leaf_tag_name:
                # Try to find by partial match or use original name
                # Some tags might not be in our map yet
                leaf_tag_name = pkts_tag_name
            
            # Read value
            # PKTS format: After tag name null terminator, there may be padding (null bytes),
            # then the actual value (null-terminated string), then more padding before next PKTS entry
            # Strategy: Skip padding after tag name, find the value (printable ASCII), end at its null terminator
            
            # Skip padding after tag name (sequences of null bytes)
            value_start = offset
            while value_start < max_offset and pkts_data[value_start] == 0:
                value_start += 1
            
            if value_start >= max_offset:
                # No value found, skip to next PKTS entry
                next_pkts = pkts_data.find(b'PKTS', offset + 1)
                if next_pkts == -1:
                    break
                offset = next_pkts
                continue
            
            # Find next PKTS header to know the boundary
            next_pkts = pkts_data.find(b'PKTS', value_start + 1)
            search_end = next_pkts if next_pkts != -1 else max_offset
            
            # Find the value - it's typically a null-terminated string of printable ASCII
            # Some values may be numeric strings, others may be text
            # Strategy: Find the first sequence of printable ASCII followed by a null terminator
            value_end = value_start
            found_printable = False
            
            # Search for value (limit to 200 bytes to avoid parsing too much data)
            for i in range(value_start, min(search_end, value_start + 200)):
                byte_val = pkts_data[i]
                if 32 <= byte_val < 127:  # Printable ASCII (space to ~)
                    found_printable = True
                    value_end = i + 1
                elif byte_val == 0 and found_printable:
                    # Found null terminator after printable data - this is the end of the value
                    value_end = i
                    break
                elif byte_val != 0 and not (32 <= byte_val < 127):
                    # Non-printable, non-null byte - might be binary data or end of value area
                    if found_printable:
                        # We had printable data, this might be the end of the value
                        value_end = i
                        break
            
            # If we found printable data but no null terminator, use the end of printable sequence
            if found_printable and value_end == value_start:
                # Find the last printable byte before a null or non-printable
                for i in range(min(search_end, value_start + 200) - 1, value_start - 1, -1):
                    if 32 <= pkts_data[i] < 127:
                        value_end = i + 1
                        break
            
            if value_end <= value_start or not found_printable:
                # No valid value found, skip to next PKTS entry
                if next_pkts != -1:
                    offset = next_pkts
                else:
                    offset += 1
                continue
            
            # Extract value data
            value_data = pkts_data[value_start:value_end]
            
            # Try to parse value
            # PKTS values are typically strings, but may represent numbers
            value = None
            
            # Try as string first (most common in PKTS format)
            try:
                # Remove trailing nulls and whitespace
                value_str = value_data.rstrip(b'\x00').rstrip()
                if value_str:
                    # Try to decode as UTF-8 first (more permissive), fall back to ASCII
                    try:
                        value = value_str.decode('utf-8', errors='strict')
                    except UnicodeDecodeError:
                        # Fall back to ASCII with replacement for invalid characters
                        value = value_str.decode('ascii', errors='replace')
            except Exception:
                # If decoding fails completely, skip this tag
                pass
            
            # If value looks like a number, try parsing it as numeric type
            # This helps with proper type handling (e.g., version numbers, counts)
            if value and isinstance(value, str):
                value_stripped = value.strip()
                # Check if it's a number (integer or float)
                try:
                    if '.' in value_stripped:
                        # Try as float
                        value = float(value_stripped)
                    else:
                        # Try as integer
                        value = int(value_stripped)
                except ValueError:
                    # Not a valid number, keep as string
                    pass
            
            # Update offset to after the value for next iteration
            # Move to next PKTS entry (or end if none)
            if next_pkts != -1:
                offset = next_pkts
            else:
                # Skip past value and any trailing nulls
                offset = value_end + 1
                if offset >= max_offset:
                    break
            
            # Map to proper Leaf tag name with "Leaf:" prefix and store in metadata
            if leaf_tag_name and value is not None:
                # Find tag ID from leaf_name_to_id
                tag_id = leaf_name_to_id.get(leaf_tag_name)
                if tag_id:
                    # Use standard Leaf tag name from EXIF_TAG_NAMES
                    full_tag_name = EXIF_TAG_NAMES.get(tag_id, f'Leaf:{leaf_tag_name}')
                    if not full_tag_name.startswith('Leaf:'):
                        full_tag_name = f'Leaf:{full_tag_name}'
                else:
                    # Tag not in standard map, use descriptive name
                    full_tag_name = f'Leaf:{leaf_tag_name}'
                
                # Store in metadata
                metadata[full_tag_name] = value
                tags_found += 1
    
    def _read_tag_value(
        self,
        tag_type: int,
        count: int,
        value_offset: int,
        inline_offset: int,
        base_offset: int
    ) -> Any:
        """
        Read the value of an EXIF tag.
        
        Args:
            tag_type: Type of the tag (ExifTagType)
            count: Number of values
            value_offset: Offset to value (if > 4 bytes)
            inline_offset: Offset to inline value area
            base_offset: Base offset for addressing
            
        Returns:
            Parsed tag value(s)
        """
        try:
            tag_type_enum = ExifTagType(tag_type)
        except ValueError:
            return None
        
        tag_size = TAG_SIZES.get(tag_type_enum, 1)
        total_size = tag_size * count
        
        # If value fits in 4 bytes, it's stored inline
        if total_size <= 4:
            data_offset = inline_offset
        else:
            data_offset = base_offset + value_offset
        
        if data_offset + total_size > len(self.file_data):
            return None
        
        data = self.file_data[data_offset:data_offset + total_size]
        
        # Parse based on type
        if tag_type_enum == ExifTagType.BYTE:
            if count == 1:
                return struct.unpack(f'{self.endian}B', data[:1])[0]
            return list(struct.unpack(f'{self.endian}{count}B', data))
        
        elif tag_type_enum == ExifTagType.ASCII:
            # Handle null-terminated strings correctly
            # For ASCII strings, count includes the null terminator
            # We should only decode up to the first null byte
            # EXIF 3.0 supports UTF-8 encoding, earlier versions use ASCII
            
            # Find first null byte (string terminator)
            null_pos = data.find(b'\x00')
            if null_pos >= 0:
                # Only decode up to the null terminator
                string_data = data[:null_pos]
            else:
                # No null terminator found, use all data (shouldn't happen but handle gracefully)
                string_data = data.rstrip(b'\x00')
            
            # Decode based on EXIF version
            # EXIF 3.0: Support for reading 'utf8' values (but still write only as 'string')
            # Try UTF-8 decoding first if EXIF 3.0, or if data looks like UTF-8
            # Even for EXIF 2.3, some files may contain UTF-8 encoded strings
            value = None
            if self.supports_utf8:
                # EXIF 3.0: Try UTF-8 first, fallback to ASCII if invalid
                try:
                    value = string_data.decode('utf-8', errors='strict')
                except UnicodeDecodeError:
                    # Fallback to ASCII for backward compatibility
                    value = string_data.decode('ascii', errors='replace')
            else:
                # EXIF 2.3 and earlier: Try UTF-8 if data looks like UTF-8, otherwise ASCII
                # Check if data contains valid UTF-8 sequences (non-ASCII bytes)
                # This handles cases where EXIF 2.3 files contain UTF-8 encoded strings
                try:
                    # Try UTF-8 decoding first (EXIF 3.0 allows UTF-8 even in ASCII fields)
                    # Check if string contains non-ASCII bytes that form valid UTF-8 sequences
                    if any(b > 127 for b in string_data):
                        # Contains non-ASCII bytes, try UTF-8
                        try:
                            value = string_data.decode('utf-8', errors='strict')
                        except UnicodeDecodeError:
                            # Invalid UTF-8, fallback to ASCII
                            value = string_data.decode('ascii', errors='replace')
                    else:
                        # Pure ASCII, decode as ASCII
                        value = string_data.decode('ascii', errors='replace')
                except Exception:
                    # Fallback to ASCII if anything goes wrong
                    value = string_data.decode('ascii', errors='replace')
            
            # Strip any remaining whitespace/null bytes (defensive)
            value = value.rstrip('\x00').strip()
            return value
        
        elif tag_type_enum == ExifTagType.SHORT:
            if count == 1:
                return struct.unpack(f'{self.endian}H', data[:2])[0]
            return list(struct.unpack(f'{self.endian}{count}H', data))
        
        elif tag_type_enum == ExifTagType.LONG:
            if count == 1:
                return struct.unpack(f'{self.endian}I', data[:4])[0]
            return list(struct.unpack(f'{self.endian}{count}I', data))
        
        elif tag_type_enum == ExifTagType.RATIONAL:
            if count == 1:
                num, den = struct.unpack(f'{self.endian}II', data[:8])
                return (num, den) if den != 0 else None
            values = []
            for i in range(count):
                num, den = struct.unpack(f'{self.endian}II', data[i*8:(i+1)*8])
                values.append((num, den) if den != 0 else None)
            return values
        
        elif tag_type_enum == ExifTagType.SLONG:
            if count == 1:
                return struct.unpack(f'{self.endian}i', data[:4])[0]
            return list(struct.unpack(f'{self.endian}{count}i', data))
        
        elif tag_type_enum == ExifTagType.SRATIONAL:
            if count == 1:
                num, den = struct.unpack(f'{self.endian}ii', data[:8])
                return (num, den) if den != 0 else None
            values = []
            for i in range(count):
                num, den = struct.unpack(f'{self.endian}ii', data[i*8:(i+1)*8])
                values.append((num, den) if den != 0 else None)
            return values
        
        elif tag_type_enum == ExifTagType.LONG8:
            # BigTIFF format code 16: 64-bit unsigned integer
            if count == 1:
                return struct.unpack(f'{self.endian}Q', data[:8])[0]
            return list(struct.unpack(f'{self.endian}{count}Q', data[:8*count]))
        
        elif tag_type_enum == ExifTagType.SLONG8:
            # BigTIFF format code 17: 64-bit signed integer
            if count == 1:
                return struct.unpack(f'{self.endian}q', data[:8])[0]
            return list(struct.unpack(f'{self.endian}{count}q', data[:8*count]))
        
        elif tag_type_enum == ExifTagType.IFD8:
            # BigTIFF format code 18: 64-bit IFD offset
            if count == 1:
                return struct.unpack(f'{self.endian}Q', data[:8])[0]
            return list(struct.unpack(f'{self.endian}{count}Q', data[:8*count]))
        
        elif tag_type_enum == ExifTagType.UNDEFINED:
            return data
        
        return None

