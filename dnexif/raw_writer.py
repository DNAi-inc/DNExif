# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
RAW format writer

This module handles writing metadata to RAW image files.
Most RAW formats are TIFF-based, but require special handling to preserve
RAW image data, preview images, and manufacturer-specific structures.

Copyright 2025 DNAi inc.
"""

import struct
import os
import tempfile
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from dnexif.exceptions import MetadataWriteError
from dnexif.tiff_writer import TIFFWriter
from dnexif.raw_parser import RAWParser


class RAWWriter:
    """
    Writes metadata to RAW image files.
    
    Supports TIFF-based RAW formats (CR2, NEF, ARW, DNG, ORF, RAF, RW2, PEF, etc.)
    and preserves RAW image data, preview images, and manufacturer-specific structures.
    """
    
    # TIFF-based RAW formats (can use TIFF writer)
    TIFF_BASED_FORMATS = {
        'CR2', 'NEF', 'ARW', 'DNG', 'ORF', 'RAF', 'RW2', 'PEF', 'SRW',
        '3FR', 'ARI', 'BAY', 'CAP', 'DCS', 'DCR', 'DRF', 'EIP', 'ERF',
        'FFF', 'IIQ', 'MEF', 'MOS', 'MRW', 'NRW', 'RWL', 'SRF'
    }
    
    # Special format handlers
    SPECIAL_FORMATS = {
        'CR3',  # ISO Base Media File Format (similar to MP4)
        'CRW',  # Canon CRW (special header)
        'X3F',  # Sigma X3F (special format)
    }
    
    def __init__(self):
        """Initialize RAW writer."""
        self.tiff_writer = TIFFWriter(exif_version='0300')  # Use EXIF 3.0 for UTF-8
    
    def write_raw(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to a RAW file.
        
        Args:
            file_path: Path to original RAW file
            metadata: Metadata dictionary to write
            output_path: Output file path
            
        Raises:
            MetadataWriteError: If writing fails
        """
        # Detect RAW format
        raw_parser = RAWParser(file_path=file_path)
        raw_format = raw_parser.detect_format()
        
        if not raw_format:
            raise MetadataWriteError("Could not detect RAW format")
        
        # Read original file
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        # Route to appropriate writer
        if raw_format in self.TIFF_BASED_FORMATS:
            self._write_tiff_based_raw(file_data, metadata, output_path, raw_format)
        elif raw_format in self.SPECIAL_FORMATS:
            self._write_special_format_raw(file_data, metadata, output_path, raw_format)
        else:
            raise MetadataWriteError(f"RAW format '{raw_format}' writing not yet implemented")
    
    def _write_tiff_based_raw(
        self,
        file_data: bytes,
        metadata: Dict[str, Any],
        output_path: str,
        raw_format: str
    ) -> None:
        """
        Write metadata to TIFF-based RAW files.
        
        Most RAW formats (CR2, NEF, ARW, DNG, ORF, RAF, RW2, PEF, etc.) are
        TIFF-based and can use the TIFF writer with special handling for
        preserving RAW image data and multiple IFDs.
        
        Args:
            file_data: Original RAW file data
            metadata: Metadata dictionary
            output_path: Output file path
            raw_format: RAW format name
        """
        try:
            # Handle format-specific headers
            tiff_data = file_data
            header_prefix = b''
            tiff_offset = 0
            
            if raw_format == 'ORF':
                # ORF has IIRO or MMOR header (4 bytes)
                # The TIFF structure may start at an offset specified in bytes 4-8
                # or we need to search for it
                if file_data.startswith(b'IIRO'):
                    header_prefix = file_data[:4]
                    tiff_pos = None
                    
                    # Check if bytes 4-8 contain an offset to TIFF
                    if len(file_data) >= 8:
                        possible_offset = struct.unpack('<I', file_data[4:8])[0]
                        # Check if this offset points to a valid TIFF structure
                        if 4 < possible_offset < len(file_data) - 10:
                            check_bytes = file_data[possible_offset:possible_offset+4]
                            if check_bytes[:2] == b'II':
                                magic = struct.unpack('<H', check_bytes[2:4])[0]
                                if magic == 42:
                                    tiff_pos = possible_offset
                    
                    # If offset didn't work, search for TIFF pattern
                    if tiff_pos is None:
                        # Search for TIFF magic number pattern
                        for search_offset in range(4, min(1000, len(file_data) - 4), 2):
                            if file_data[search_offset:search_offset+2] == b'II':
                                magic = struct.unpack('<H', file_data[search_offset+2:search_offset+4])[0]
                                if magic == 42:
                                    tiff_pos = search_offset
                                    break
                    
                    if tiff_pos and tiff_pos > 4:
                        header_prefix = file_data[:tiff_pos]
                        tiff_data = file_data[tiff_pos:]
                        tiff_offset = tiff_pos
                    else:
                        # Fallback: assume TIFF starts at offset 4
                        tiff_data = file_data[4:]
                        tiff_offset = 4
                        
                elif file_data.startswith(b'MMOR'):
                    header_prefix = file_data[:4]
                    tiff_pos = None
                    
                    # Check if bytes 4-8 contain an offset to TIFF (big-endian)
                    if len(file_data) >= 8:
                        possible_offset = struct.unpack('>I', file_data[4:8])[0]
                        # Check if this offset points to a valid TIFF structure
                        if 4 < possible_offset < len(file_data) - 10:
                            check_bytes = file_data[possible_offset:possible_offset+4]
                            if check_bytes[:2] == b'MM':
                                magic = struct.unpack('>H', check_bytes[2:4])[0]
                                if magic == 42:
                                    tiff_pos = possible_offset
                    
                    # If offset didn't work, search for TIFF pattern
                    if tiff_pos is None:
                        # Search for TIFF magic number pattern
                        for search_offset in range(4, min(1000, len(file_data) - 4), 2):
                            if file_data[search_offset:search_offset+2] == b'MM':
                                magic = struct.unpack('>H', file_data[search_offset+2:search_offset+4])[0]
                                if magic == 42:
                                    tiff_pos = search_offset
                                    break
                    
                    if tiff_pos and tiff_pos > 4:
                        header_prefix = file_data[:tiff_pos]
                        tiff_data = file_data[tiff_pos:]
                        tiff_offset = tiff_pos
                    else:
                        # Fallback: assume TIFF starts at offset 4
                        tiff_data = file_data[4:]
                        tiff_offset = 4
                else:
                    # Try to find TIFF structure
                    tiff_pos = file_data.find(b'II*\x00')
                    if tiff_pos == -1:
                        tiff_pos = file_data.find(b'MM\x00*')
                    if tiff_pos > 0:
                        header_prefix = file_data[:tiff_pos]
                        tiff_data = file_data[tiff_pos:]
                        tiff_offset = tiff_pos
                    else:
                        raise MetadataWriteError(f"Invalid {raw_format} file: could not find TIFF structure")
            
            elif raw_format == 'RW2':
                # RW2 may have IIU header, find actual TIFF structure
                # Look for TIFF magic number
                tiff_pos = file_data.find(b'II*\x00')
                if tiff_pos == -1:
                    tiff_pos = file_data.find(b'MM\x00*')
                if tiff_pos > 0:
                    header_prefix = file_data[:tiff_pos]
                    tiff_data = file_data[tiff_pos:]
                    tiff_offset = tiff_pos
                elif file_data[:2] in (b'II', b'MM'):
                    # Standard TIFF, no special header
                    tiff_data = file_data
                    tiff_offset = 0
                else:
                    raise MetadataWriteError(f"Invalid {raw_format} file: could not find TIFF structure")
            
            elif raw_format == 'RAF':
                # RAF has FUJIFILM header, then TIFF at offset
                if file_data.startswith(b'FUJIFILM'):
                    # Find TIFF structure
                    tiff_pos = file_data.find(b'II*\x00')
                    if tiff_pos == -1:
                        tiff_pos = file_data.find(b'MM\x00*')
                    if tiff_pos > 0:
                        header_prefix = file_data[:tiff_pos]
                        tiff_data = file_data[tiff_pos:]
                        tiff_offset = tiff_pos
                    else:
                        raise MetadataWriteError(f"Invalid {raw_format} file: could not find TIFF structure")
                else:
                    raise MetadataWriteError(f"Invalid {raw_format} file")
            
            else:
                # Standard TIFF-based format (CR2, NEF, ARW, DNG, PEF, etc.)
                tiff_data = file_data
                tiff_offset = 0
            
            # Determine endianness from TIFF data
            endian = '<'
            if tiff_data[:2] == b'MM':
                endian = '>'
            elif tiff_data[:2] != b'II':
                raise MetadataWriteError(f"Invalid {raw_format} file: bad TIFF structure")
            
            # Update TIFF writer endianness
            self.tiff_writer.endian = endian
            
            # Extract metadata (EXIF, IPTC, XMP)
            # The TIFF writer now handles IPTC and XMP in addition to EXIF
            tiff_metadata = {
                k: v for k, v in metadata.items()
                if (k.startswith('EXIF:') or k.startswith('IFD0:') or k.startswith('GPS:') or
                    k.startswith('IPTC:') or k.startswith('XMP:'))
            }
            
            # For RAW files, we need to preserve:
            # 1. RAW image data (usually in IFD0 or a separate IFD)
            # 2. Preview/thumbnail images (often in IFD1)
            # 3. Manufacturer-specific IFDs (MakerNote, etc.)
            # 4. SubIFDs (for multiple images)
            
            # Use TIFF writer which handles image data preservation
            # Write to temporary path first
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                self.tiff_writer.write_tiff(tiff_data, tiff_metadata, tmp_path)
                
                # Read the modified TIFF data
                with open(tmp_path, 'rb') as f:
                    modified_tiff = f.read()
                
                # Combine header prefix with modified TIFF
                with open(output_path, 'wb') as f:
                    if header_prefix:
                        f.write(header_prefix)
                    f.write(modified_tiff)
            except Exception as tiff_error:
                # If TIFF writing fails (e.g., ORF with non-standard structure),
                # try to preserve original file structure
                if raw_format == 'ORF':
                    # ORF has a special header (IIRO or MMOR) followed by TIFF structure
                    # Try improved ORF-specific handling
                    try:
                        self._write_orf_with_header(
                            file_data, metadata, output_path, header_prefix, tiff_offset
                        )
                    except Exception as orf_error:
                        # If improved ORF writing also fails, preserve original file
                        with open(output_path, 'wb') as f:
                            f.write(file_data)
                        raise MetadataWriteError(
                            f"ORF writing requires special format handling. "
                            f"The file structure is not standard TIFF. "
                            f"Original file preserved. TIFF error: {str(tiff_error)}, "
                            f"ORF-specific error: {str(orf_error)}"
                        )
                else:
                    raise
            finally:
                # Clean up temp file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
            
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to write {raw_format} file: {str(e)}")
    
    def _write_special_format_raw(
        self,
        file_data: bytes,
        metadata: Dict[str, Any],
        output_path: str,
        raw_format: str
    ) -> None:
        """
        Write metadata to special format RAW files.
        
        Handles formats that are not TIFF-based:
        - CR3: ISO Base Media File Format (similar to MP4)
        - CRW: Canon CRW (special header)
        - X3F: Sigma X3F (special format)
        
        Args:
            file_data: Original RAW file data
            metadata: Metadata dictionary
            output_path: Output file path
            raw_format: RAW format name
        """
        if raw_format == 'CR3':
            # CR3 uses ISO Base Media File Format (similar to MP4)
            # This requires QuickTime atom manipulation
            # For now, raise an error indicating it's not fully implemented
            raise MetadataWriteError(
                "CR3 writing requires ISO Base Media File Format support. "
                "This will be implemented in a future update."
            )
        elif raw_format == 'CRW':
            # CRW has a special header structure
            # For now, try to preserve the header and update EXIF if present
            raise MetadataWriteError(
                "CRW writing requires special header handling. "
                "This will be implemented in a future update."
            )
        elif raw_format == 'X3F':
            # X3F (Sigma) has a special format structure with:
            # - X3F header ("FOVb" signature)
            # - Version, directory offset, directory count
            # - Image data offset/size, thumbnail offset/size
            # - Directory structure with metadata blocks
            # X3F uses big-endian byte order
            try:
                self._write_x3f_with_structure(file_data, metadata, output_path)
            except Exception as e:
                if isinstance(e, MetadataWriteError):
                    raise
                # If X3F writing fails, preserve original file
                try:
                    with open(output_path, 'wb') as f:
                        f.write(file_data)
                    raise MetadataWriteError(
                        "X3F writing requires special format handling. "
                        "Sigma X3F files use a proprietary format structure. "
                        "Original file preserved. Error: " + str(e)
                    )
                except Exception as preserve_error:
                    raise MetadataWriteError(f"Failed to preserve X3F file: {str(preserve_error)}")
        else:
            raise MetadataWriteError(f"Special format '{raw_format}' writing not implemented")
    
    def _write_orf_with_header(
        self,
        file_data: bytes,
        metadata: Dict[str, Any],
        output_path: str,
        header_prefix: bytes,
        tiff_offset: int
    ) -> None:
        """
        Write ORF file with proper header preservation.
        
        ORF files have a special header (IIRO or MMOR) followed by a TIFF structure.
        This method preserves the header and updates the TIFF metadata.
        
        Args:
            file_data: Original ORF file data
            metadata: Metadata dictionary to write
            output_path: Output file path
            header_prefix: ORF header prefix (IIRO or MMOR)
            tiff_offset: Offset where TIFF structure starts
        """
        # Extract TIFF data from original file
        tiff_data = file_data[tiff_offset:]
        
        # Determine endianness from header
        endian = '<'
        if header_prefix.startswith(b'MMOR'):
            endian = '>'
        
        # Update TIFF writer endianness
        self.tiff_writer.endian = endian
        
        # Extract metadata (EXIF, IPTC, XMP)
        tiff_metadata = {
            k: v for k, v in metadata.items()
            if (k.startswith('EXIF:') or k.startswith('IFD0:') or k.startswith('GPS:') or
                k.startswith('IPTC:') or k.startswith('XMP:'))
        }
        
        # Write TIFF data to temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            self.tiff_writer.write_tiff(tiff_data, tiff_metadata, tmp_path)
            
            # Read the modified TIFF data
            with open(tmp_path, 'rb') as f:
                modified_tiff = f.read()
            
            # Combine header prefix with modified TIFF
            # For ORF, the header is typically 4 bytes (IIRO or MMOR)
            # followed by 4 bytes for IFD offset
            with open(output_path, 'wb') as f:
                f.write(header_prefix)
                # Write IFD offset (typically 8 for ORF files)
                if endian == '<':
                    f.write(struct.pack('<I', 8))
                else:
                    f.write(struct.pack('>I', 8))
                f.write(modified_tiff)
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def _write_x3f_with_structure(
        self,
        file_data: bytes,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write X3F file with structure preservation.
        
        X3F files use a proprietary format with:
        - "FOVb" signature (4 bytes)
        - Version, directory offset, directory count (4 bytes each, big-endian)
        - Image data offset/size, thumbnail offset/size (4 bytes each, big-endian)
        - Directory structure with metadata blocks
        
        This implementation preserves the file structure and attempts to update
        metadata where possible. Full X3F writing requires deep format knowledge.
        
        Args:
            file_data: Original X3F file data
            metadata: Metadata dictionary to write
            output_path: Output file path
        """
        # X3F files start with "FOVb" signature
        if not file_data.startswith(b'FOVb'):
            raise MetadataWriteError("Invalid X3F file: missing FOVb signature")
        
        # X3F uses big-endian byte order
        if len(file_data) < 28:
            raise MetadataWriteError("Invalid X3F file: too short")
        
        # Read X3F header structure
        version = struct.unpack('>I', file_data[4:8])[0]
        dir_offset = struct.unpack('>I', file_data[8:12])[0]
        dir_count = struct.unpack('>I', file_data[12:16])[0]
        image_offset = struct.unpack('>I', file_data[16:20])[0]
        image_size = struct.unpack('>I', file_data[20:24])[0]
        thumb_offset = struct.unpack('>I', file_data[24:28])[0]
        
        # For now, preserve the entire file structure
        # X3F metadata is embedded in directory entries and specific blocks
        # Full implementation would require:
        # 1. Parsing directory entries
        # 2. Locating metadata blocks
        # 3. Updating metadata in place
        # 4. Recalculating offsets if needed
        
        # Copy original file to preserve structure
        with open(output_path, 'wb') as f:
            f.write(file_data)
        
        # Note: This is a structure-preserving implementation
        # Full X3F metadata writing would require extensive format research
        # For now, we preserve the file and indicate that metadata updates
        # are limited due to the proprietary format structure
        raise MetadataWriteError(
            "X3F writing preserves file structure but metadata updates are limited. "
            "Sigma X3F files use a proprietary format with embedded metadata blocks. "
            "Full metadata writing support requires additional format research. "
            "Original file preserved."
        )
    
    def _preserve_raw_structure(
        self,
        original_data: bytes,
        new_metadata: Dict[str, Any],
        raw_format: str
    ) -> bytes:
        """
        Preserve RAW file structure while updating metadata.
        
        This method ensures that:
        - RAW image data is preserved
        - Preview/thumbnail images are preserved
        - Manufacturer-specific structures are preserved
        - Multiple IFDs are handled correctly
        
        Args:
            original_data: Original RAW file data
            new_metadata: New metadata to write
            raw_format: RAW format name
            
        Returns:
            Modified RAW file data
        """
        # For TIFF-based formats, the TIFF writer handles this
        # For special formats, format-specific logic is needed
        
        # This is a placeholder for future enhancements
        # The actual implementation would depend on the specific format
        
        return original_data

