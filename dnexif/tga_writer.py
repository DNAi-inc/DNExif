# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
TGA (Targa) metadata writer

Provides limited metadata writing by populating the TGA 2.0 extension area
with Author/Comment fields so that `XMP:Title` style tags can round-trip.

Copyright 2025 DNAi inc.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import struct

from dnexif.exceptions import MetadataWriteError


class TGAWriter:
    """
    Writes metadata to TGA files by creating/updating the TGA 2.0 extension area.
    """

    FOOTER_SIGNATURE = b'TRUEVISION-XFILE.\x00'
    EXTENSION_SIZE = 495  # Bytes (including size field)

    def write_tga(self, file_data: bytes, metadata: Dict[str, Any], output_path: str) -> None:
        """
        Write metadata to a TGA file.

        Args:
            file_data: Original TGA file bytes
            metadata: Metadata dictionary
            output_path: Output file path
        """
        if len(file_data) < 18:
            raise MetadataWriteError("Invalid TGA file (too small)")

        author_value = (
            metadata.get('EXIF:Artist')
            or metadata.get('TGA:AuthorName')
            or metadata.get('Artist')
        )
        title_value = (
            metadata.get('XMP:Title')
            or metadata.get('Title')
        )

        if not author_value and not title_value:
            raise MetadataWriteError("No supported TGA metadata fields provided (expected EXIF:Artist or XMP:Title)")

        base_data = self._strip_existing_extension(file_data)
        extension_offset = len(base_data)
        extension_area = self._build_extension_area(author_value or title_value, title_value, metadata)

        footer = struct.pack('<I', extension_offset)
        footer += struct.pack('<I', 0)  # Developer area offset not used
        footer += self.FOOTER_SIGNATURE

        final_data = base_data + extension_area + footer
        Path(output_path).write_bytes(final_data)

    def _strip_existing_extension(self, file_data: bytes) -> bytearray:
        """
        Remove any existing extension/developer areas & footer so we can rebuild cleanly.
        """
        if len(file_data) >= 26 and file_data[-18:] == self.FOOTER_SIGNATURE:
            footer_start = len(file_data) - 26
            extension_offset = struct.unpack('<I', file_data[footer_start:footer_start+4])[0]
            developer_offset = struct.unpack('<I', file_data[footer_start+4:footer_start+8])[0]

            cut_points: List[int] = [footer_start]
            if extension_offset:
                cut_points.append(extension_offset)
            if developer_offset:
                cut_points.append(developer_offset)

            cut_pos = min(point for point in cut_points if point > 0)
            return bytearray(file_data[:cut_pos])

        return bytearray(file_data)

    def _build_extension_area(self, author_value: str, title_value: Optional[str], metadata: Dict[str, Any]) -> bytes:
        """
        Construct a TGA 2.0 extension area populated with author/comments.
        """
        area = bytearray(self.EXTENSION_SIZE)
        struct.pack_into('<H', area, 0, self.EXTENSION_SIZE)

        data_offset = 2  # Skip size field

        # Author name (41 bytes)
        self._write_fixed_field(area, data_offset, 41, author_value)

        # Comments (4 lines of 81 bytes each)
        comments_values = metadata.get('TGA:Comments')
        if isinstance(comments_values, str):
            comment_lines = [comments_values]
        elif isinstance(comments_values, list):
            comment_lines = [str(c) for c in comments_values]
        else:
            comment_lines = []

        if not comment_lines:
            if title_value:
                comment_lines = [title_value]
            else:
                comment_lines = [author_value]

        comments_offset = data_offset + 41
        for i in range(4):
            value = comment_lines[i] if i < len(comment_lines) else ''
            self._write_fixed_field(area, comments_offset + (i * 81), 81, value)

        # Remaining extension fields left as zero (Date/Time, Job name, etc.)
        return bytes(area)

    @staticmethod
    def _write_fixed_field(buffer: bytearray, offset: int, length: int, value: str) -> None:
        """
        Write a UTF-8 string into a fixed-length ASCII field (null padded).
        """
        encoded = value.encode('utf-8', errors='replace')
        truncated = encoded[:length]
        padded = truncated + b'\x00' * (length - len(truncated))
        buffer[offset:offset+length] = padded
