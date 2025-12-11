# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
JPEG file modifier

This module handles modifying JPEG files to update metadata segments.
It preserves the image data while replacing metadata segments.

Copyright 2025 DNAi inc.
"""

import struct
from typing import List, Tuple, Optional
from dnexif.exceptions import MetadataWriteError


class JPEGModifier:
    """
    Modifies JPEG files to update metadata segments.
    
    This class handles the complex task of:
    - Finding and removing old metadata segments
    - Inserting new metadata segments
    - Preserving image data integrity
    """
    
    # JPEG markers
    SOI = 0xFFD8  # Start of Image
    EOI = 0xFFD9  # End of Image
    APP0 = 0xFFE0  # APP0 (JFIF)
    APP1 = 0xFFE1  # APP1 (EXIF)
    APP2 = 0xFFE2  # APP2
    APP13 = 0xFFED  # APP13 (IPTC)
    APP14 = 0xFFEE  # APP14 (Adobe)
    COM = 0xFFFE  # Comment
    
    def replace_app13_segment(self, new_app13_data: bytes) -> bytes:
        """
        Replace the IPTC APP13 segment with new data.
        
        Args:
            new_app13_data: New APP13 segment data (including marker and length)
            
        Returns:
            Modified JPEG file data
        """
        # Find APP13 segment
        app13_index = None
        for idx, (marker, offset, length) in enumerate(self.segments):
            if marker == self.APP13:
                app13_index = idx
                break
        
        # Build new file
        new_data = bytearray()
        
        # SOI
        new_data.extend(self.file_data[0:2])
        
        if app13_index is not None:
            # Copy segments before APP13
            for idx, (marker, offset, length) in enumerate(self.segments):
                if idx == app13_index:
                    break
                segment_data = self.file_data[offset:offset + 2 + length]
                new_data.extend(segment_data)
            
            # Insert new APP13 segment (skip old one)
            if new_app13_data:
                new_data.extend(new_app13_data)
            
            # Copy segments after APP13
            for idx, (marker, offset, length) in enumerate(self.segments):
                if idx > app13_index:
                    segment_data = self.file_data[offset:offset + 2 + length]
                    new_data.extend(segment_data)
        else:
            # No existing APP13, insert after APP1 if exists, otherwise after SOI
            insert_after_idx = -1
            for idx, (marker, offset, length) in enumerate(self.segments):
                if marker == self.APP1:
                    insert_after_idx = idx
                    break
            
            if insert_after_idx >= 0:
                # Insert after APP1
                for idx, (marker, offset, length) in enumerate(self.segments):
                    segment_data = self.file_data[offset:offset + 2 + length]
                    new_data.extend(segment_data)
                    if idx == insert_after_idx and new_app13_data:
                        # Insert APP13 after APP1
                        new_data.extend(new_app13_data)
            else:
                # No APP1, insert after SOI
                if new_app13_data:
                    new_data.extend(new_app13_data)
                # Copy all segments
                for marker, offset, length in self.segments:
                    segment_data = self.file_data[offset:offset + 2 + length]
                    new_data.extend(segment_data)
        
        return bytes(new_data)
    
    def add_app13_segment(self, app13_data: bytes) -> bytes:
        """
        Add an APP13 segment if it doesn't exist.
        
        Args:
            app13_data: APP13 segment data
            
        Returns:
            Modified JPEG file data
        """
        # Check if APP13 already exists
        has_app13 = any(marker == self.APP13 for marker, _, _ in self.segments)
        
        if has_app13:
            return self.replace_app13_segment(app13_data)
        
        # Insert after APP1 or after SOI
        new_data = bytearray()
        new_data.extend(self.file_data[0:2])  # SOI
        
        inserted = False
        for marker, offset, length in self.segments:
            new_data.extend(self.file_data[offset:offset + 2 + length])
            if marker == self.APP1 and not inserted:
                new_data.extend(app13_data)  # Insert after APP1
                inserted = True
        
        if not inserted:
            # No APP1, insert after SOI
            new_data.extend(app13_data)
        
        return bytes(new_data)
    
    def __init__(self, file_data: bytes):
        """
        Initialize JPEG modifier.
        
        Args:
            file_data: Original JPEG file data
        """
        self.file_data = file_data
        self.segments: List[Tuple[int, int, int]] = []  # (marker, offset, length)
        self._parse_segments()
    
    def _parse_segments(self) -> None:
        """
        Parse JPEG file to find all segments.
        """
        i = 0
        
        # Check for SOI
        if len(self.file_data) < 2 or struct.unpack('>H', self.file_data[0:2])[0] != self.SOI:
            raise MetadataWriteError("Invalid JPEG file: missing SOI marker")
        
        i = 2
        
        while i < len(self.file_data) - 1:
            # Find marker
            if self.file_data[i] != 0xFF:
                i += 1
                continue
            
            marker_byte = self.file_data[i + 1]
            
            # Skip padding bytes (0xFF followed by 0x00)
            if marker_byte == 0x00:
                i += 2
                continue
            
            # Check for EOI
            if marker_byte == 0xD9:  # EOI
                break
            
            # Get marker value
            marker = struct.unpack('>H', self.file_data[i:i+2])[0]
            
            # Get segment length
            if i + 3 >= len(self.file_data):
                break
            
            length = struct.unpack('>H', self.file_data[i+2:i+4])[0]
            
            # Store segment info
            self.segments.append((marker, i, length))
            
            # Move to next segment
            i += 2 + length
    
    def replace_app1_segment(self, new_app1_data: bytes, is_xmp: bool = False) -> bytes:
        """
        Replace an APP1 segment with new data.
        
        Args:
            new_app1_data: New APP1 segment data (including marker and length)
            is_xmp: If True, replace XMP APP1; if False, replace EXIF APP1
            
        Returns:
            Modified JPEG file data
        """
        # Find APP1 segment (EXIF or XMP)
        app1_index = None
        for idx, (marker, offset, length) in enumerate(self.segments):
            if marker == self.APP1:
                # Check if this is the right type of APP1
                if is_xmp:
                    # Check for XMP identifier
                    if offset + 33 < len(self.file_data):
                        xmp_header = self.file_data[offset+4:offset+33]
                        if xmp_header == b'http://ns.adobe.com/xap/1.0/\x00':
                            app1_index = idx
                            break
                else:
                    # Check for EXIF identifier
                    if offset + 10 < len(self.file_data):
                        exif_header = self.file_data[offset+4:offset+10]
                        if exif_header == b'Exif\x00\x00':
                            app1_index = idx
                            break
        
        # Build new file
        new_data = bytearray()
        
        # SOI
        new_data.extend(self.file_data[0:2])
        
        # Copy segments before APP1
        for idx, (marker, offset, length) in enumerate(self.segments):
            if idx == app1_index:
                break
            new_data.extend(self.file_data[offset:offset + 2 + length])
        
        # Insert new APP1 segment
        if new_app1_data:
            new_data.extend(new_app1_data)
        
        # Copy segments after APP1
        if app1_index is not None:
            for idx, (marker, offset, length) in enumerate(self.segments):
                if idx > app1_index:
                    new_data.extend(self.file_data[offset:offset + 2 + length])
        else:
            # No existing APP1 of this type, insert after SOI or first APP1
            if is_xmp:
                # For XMP, insert after EXIF APP1 if it exists, otherwise after SOI
                inserted = False
                for idx, (marker, offset, length) in enumerate(self.segments):
                    if marker == self.APP1 and not inserted:
                        # Check if this is EXIF APP1
                        if offset + 10 < len(self.file_data):
                            exif_header = self.file_data[offset+4:offset+10]
                            if exif_header == b'Exif\x00\x00':
                                # Insert XMP after EXIF
                                new_data.extend(self.file_data[offset:offset + 2 + length])
                                if new_app1_data:
                                    new_data.extend(new_app1_data)
                                inserted = True
                                continue
                    new_data.extend(self.file_data[offset:offset + 2 + length])
                if not inserted and new_app1_data:
                    # No EXIF APP1, insert after SOI
                    new_data.extend(new_app1_data)
            else:
                # For EXIF, insert after SOI
                if new_app1_data:
                    new_data.extend(new_app1_data)
                for idx, (marker, offset, length) in enumerate(self.segments):
                    new_data.extend(self.file_data[offset:offset + 2 + length])
        
        return bytes(new_data)
    
    def add_app1_segment(self, app1_data: bytes, is_xmp: bool = False) -> bytes:
        """
        Add an APP1 segment if it doesn't exist.
        
        Args:
            app1_data: APP1 segment data
            is_xmp: If True, add XMP APP1; if False, add EXIF APP1
            
        Returns:
            Modified JPEG file data
        """
        # Check if APP1 of this type already exists
        if is_xmp:
            has_xmp = False
            for marker, offset, length in self.segments:
                if marker == self.APP1:
                    if offset + 33 < len(self.file_data):
                        xmp_header = self.file_data[offset+4:offset+33]
                        if xmp_header == b'http://ns.adobe.com/xap/1.0/\x00':
                            has_xmp = True
                            break
            if has_xmp:
                return self.replace_app1_segment(app1_data, is_xmp=True)
        else:
            has_exif = False
            for marker, offset, length in self.segments:
                if marker == self.APP1:
                    if offset + 10 < len(self.file_data):
                        exif_header = self.file_data[offset+4:offset+10]
                        if exif_header == b'Exif\x00\x00':
                            has_exif = True
                            break
            if has_exif:
                return self.replace_app1_segment(app1_data, is_xmp=False)
        
        # Insert after SOI or after EXIF APP1 (for XMP)
        new_data = bytearray()
        new_data.extend(self.file_data[0:2])  # SOI
        
        if is_xmp:
            # For XMP, insert after EXIF APP1 if it exists
            inserted = False
            for marker, offset, length in self.segments:
                if marker == self.APP1 and not inserted:
                    # Check if this is EXIF APP1
                    if offset + 10 < len(self.file_data):
                        exif_header = self.file_data[offset+4:offset+10]
                        if exif_header == b'Exif\x00\x00':
                            # Insert XMP after EXIF
                            new_data.extend(self.file_data[offset:offset + 2 + length])
                            new_data.extend(app1_data)
                            inserted = True
                            continue
                new_data.extend(self.file_data[offset:offset + 2 + length])
            if not inserted:
                # No EXIF APP1, insert after SOI
                new_data.extend(app1_data)
                for marker, offset, length in self.segments:
                    new_data.extend(self.file_data[offset:offset + 2 + length])
        else:
            # For EXIF, insert after SOI
            new_data.extend(app1_data)
            for marker, offset, length in self.segments:
                new_data.extend(self.file_data[offset:offset + 2 + length])
        
        return bytes(new_data)
    
    def remove_app1_segment(self, is_xmp: bool = False) -> bytes:
        """
        Remove an APP1 segment.
        
        Args:
            is_xmp: If True, remove XMP APP1; if False, remove EXIF APP1
        
        Returns:
            Modified JPEG file data without APP1
        """
        return self.replace_app1_segment(b'', is_xmp=is_xmp)

