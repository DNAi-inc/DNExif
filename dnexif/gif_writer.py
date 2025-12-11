# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
GIF format metadata writer

This module handles writing XMP metadata to GIF files.
GIF stores metadata in application extension blocks.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from dnexif.exceptions import MetadataWriteError
from dnexif.xmp_writer import XMPWriter


class GIFWriter:
    """
    Writes metadata to GIF files.
    
    GIF uses application extension blocks (0x21 0xFF) for metadata.
    XMP can be stored in an application extension with identifier "XMP DataXMP".
    """
    
    # GIF block types
    EXTENSION_INTRODUCER = 0x21
    APPLICATION_EXTENSION = 0xFF
    COMMENT_EXTENSION = 0xFE
    PLAIN_TEXT_EXTENSION = 0x01
    GRAPHIC_CONTROL_EXTENSION = 0xF9
    IMAGE_SEPARATOR = 0x2C
    TRAILER = 0x3B
    
    # XMP application extension identifier
    XMP_IDENTIFIER = b'XMP DataXMP'
    
    def __init__(self):
        """Initialize GIF writer."""
        self.xmp_writer = XMPWriter()
    
    def write_gif(
        self,
        original_data: bytes,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to a GIF file.
        
        Args:
            original_data: Original GIF file data
            metadata: Metadata dictionary to write
            output_path: Output file path
            
        Raises:
            MetadataWriteError: If writing fails
        """
        if not original_data.startswith(b'GIF87a') and not original_data.startswith(b'GIF89a'):
            raise MetadataWriteError("Invalid GIF file")
        
        try:
            # Parse GIF structure
            blocks = self._parse_gif_blocks(original_data)
            
            # Extract XMP metadata
            xmp_metadata = {
                k: v for k, v in metadata.items()
                if k.startswith('XMP:')
            }
            
            # Build new GIF file
            new_gif_data = self._build_gif_file(blocks, xmp_metadata)
            
            # Write to output file
            with open(output_path, 'wb') as f:
                f.write(new_gif_data)
                
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to write GIF file: {str(e)}")
    
    def _parse_gif_blocks(self, gif_data: bytes) -> List[Tuple[int, bytes]]:
        """
        Parse GIF blocks from file data.
        
        Args:
            gif_data: GIF file data
            
        Returns:
            List of (block_type, block_data) tuples
        """
        blocks = []
        offset = 0
        
        # Read GIF header (6 bytes: GIF87a or GIF89a)
        if offset + 6 > len(gif_data):
            return blocks
        
        header = gif_data[offset:offset+6]
        blocks.append((0, header))  # 0 = header
        offset += 6
        
        # Read Logical Screen Descriptor (7 bytes)
        if offset + 7 > len(gif_data):
            return blocks
        
        lsd = gif_data[offset:offset+7]
        blocks.append((1, lsd))  # 1 = logical screen descriptor
        offset += 7
        
        # Check for Global Color Table
        packed = lsd[4]
        has_gct = (packed & 0x80) != 0
        gct_size = 2 << (packed & 0x07)
        
        if has_gct:
            gct_size_bytes = gct_size * 3
            if offset + gct_size_bytes > len(gif_data):
                return blocks
            gct = gif_data[offset:offset+gct_size_bytes]
            blocks.append((2, gct))  # 2 = global color table
            offset += gct_size_bytes
        
        # Parse blocks
        while offset < len(gif_data) - 1:
            if gif_data[offset] == self.EXTENSION_INTRODUCER:
                offset += 1
                if offset >= len(gif_data):
                    break
                
                extension_type = gif_data[offset]
                offset += 1
                
                if extension_type == self.APPLICATION_EXTENSION:
                    # Application extension - read full block structure
                    full_block = self._read_full_application_extension(gif_data, offset)
                    if full_block is not None:
                        # Check if it's XMP (we'll replace it)
                        # Skip the first size byte to check identifier
                        if len(full_block) > 1 and not full_block[1:12].startswith(self.XMP_IDENTIFIER):
                            blocks.append((self.APPLICATION_EXTENSION, full_block))
                        # Calculate offset: skip all sub-blocks until terminator
                        offset = self._skip_all_sub_blocks(gif_data, offset)
                    else:
                        break
                elif extension_type == self.COMMENT_EXTENSION:
                    # Comment extension - read all sub-blocks
                    block_data = self._read_all_sub_blocks(gif_data, offset)
                    if block_data is not None:
                        blocks.append((self.COMMENT_EXTENSION, block_data))
                        offset = self._skip_all_sub_blocks(gif_data, offset)
                    else:
                        break
                elif extension_type == self.PLAIN_TEXT_EXTENSION:
                    # Plain text extension - read all sub-blocks
                    block_data = self._read_all_sub_blocks(gif_data, offset)
                    if block_data is not None:
                        blocks.append((self.PLAIN_TEXT_EXTENSION, block_data))
                        offset = self._skip_all_sub_blocks(gif_data, offset)
                    else:
                        break
                elif extension_type == self.GRAPHIC_CONTROL_EXTENSION:
                    # Graphic control extension
                    if offset + 1 > len(gif_data):
                        break
                    block_size = gif_data[offset]
                    if offset + block_size + 2 > len(gif_data):  # +2 for size byte and terminator
                        break
                    # Read block_size byte + data (block_size bytes)
                    block_data = gif_data[offset:offset+block_size+1]
                    blocks.append((self.GRAPHIC_CONTROL_EXTENSION, block_data))
                    offset += block_size + 2  # Skip size byte, data, and terminator
                else:
                    # Unknown extension, skip
                    break
            elif gif_data[offset] == self.IMAGE_SEPARATOR:
                # Image data block
                image_data = self._read_image_data(gif_data, offset)
                if image_data:
                    blocks.append((self.IMAGE_SEPARATOR, image_data))
                    offset += len(image_data)
                else:
                    break
            elif gif_data[offset] == self.TRAILER:
                # Trailer
                blocks.append((self.TRAILER, b'\x3B'))
                break
            else:
                # Unknown block, skip
                offset += 1
        
        return blocks
    
    def _read_data_sub_block(self, gif_data: bytes, offset: int) -> Optional[bytes]:
        """
        Read a single data sub-block from GIF.
        
        Args:
            gif_data: GIF file data
            offset: Starting offset (at size byte)
            
        Returns:
            Block data bytes (without size byte), or None if invalid
        """
        if offset >= len(gif_data):
            return None
        
        block_size = gif_data[offset]
        if block_size == 0:
            return None
        
        if offset + block_size + 1 > len(gif_data):
            return None
        
        block_data = gif_data[offset+1:offset+1+block_size]
        return block_data
    
    def _read_all_sub_blocks(self, gif_data: bytes, offset: int) -> Optional[bytes]:
        """
        Read all data sub-blocks from GIF until terminator.
        
        Args:
            gif_data: GIF file data
            offset: Starting offset (at first size byte)
            
        Returns:
            Concatenated block data bytes (all sub-blocks combined), or None if invalid
        """
        if offset >= len(gif_data):
            return None
        
        result = bytearray()
        while offset < len(gif_data):
            block_size = gif_data[offset]
            if block_size == 0:
                # Terminator found
                break
            if offset + block_size + 1 > len(gif_data):
                return None
            result.extend(gif_data[offset+1:offset+1+block_size])
            offset += block_size + 1
        
        return bytes(result) if result else None
    
    def _skip_all_sub_blocks(self, gif_data: bytes, offset: int) -> int:
        """
        Skip all data sub-blocks until terminator.
        
        Args:
            gif_data: GIF file data
            offset: Starting offset (at first size byte)
            
        Returns:
            New offset after skipping all sub-blocks and terminator
        """
        while offset < len(gif_data):
            block_size = gif_data[offset]
            if block_size == 0:
                # Terminator found, skip it and return
                return offset + 1
            if offset + block_size + 1 > len(gif_data):
                return len(gif_data)
            offset += block_size + 1
        
        return offset
    
    def _read_full_application_extension(self, gif_data: bytes, offset: int) -> Optional[bytes]:
        """
        Read full application extension block with all size bytes preserved.
        
        Args:
            gif_data: GIF file data
            offset: Starting offset (at first size byte)
            
        Returns:
            Full block bytes including all size bytes and terminator, or None if invalid
        """
        if offset >= len(gif_data):
            return None
        
        result = bytearray()
        while offset < len(gif_data):
            block_size = gif_data[offset]
            result.append(block_size)
            if block_size == 0:
                # Terminator found
                break
            if offset + block_size + 1 > len(gif_data):
                return None
            result.extend(gif_data[offset+1:offset+1+block_size])
            offset += block_size + 1
        
        return bytes(result) if result else None
    
    def _read_image_data(self, gif_data: bytes, offset: int) -> Optional[bytes]:
        """
        Read image data block from GIF.
        
        Args:
            gif_data: GIF file data
            offset: Starting offset (should be at IMAGE_SEPARATOR)
            
        Returns:
            Image data bytes, or None if invalid
        """
        if offset >= len(gif_data) or gif_data[offset] != self.IMAGE_SEPARATOR:
            return None
        
        start_offset = offset
        offset += 1
        
        # Read Image Descriptor (9 bytes)
        if offset + 9 > len(gif_data):
            return None
        
        offset += 9
        
        # Check for Local Color Table
        # (simplified - would need to check flags)
        
        # Read LZW minimum code size
        if offset >= len(gif_data):
            return None
        
        lzw_min = gif_data[offset]
        offset += 1
        
        # Read image data sub-blocks until terminator
        while offset < len(gif_data):
            if gif_data[offset] == 0:
                # Block terminator
                offset += 1
                break
            else:
                block_size = gif_data[offset]
                if offset + block_size + 1 > len(gif_data):
                    break
                offset += block_size + 1
        
        return gif_data[start_offset:offset]
    
    def _build_gif_file(
        self,
        blocks: List[Tuple[int, bytes]],
        xmp_metadata: Dict[str, Any]
    ) -> bytes:
        """
        Build a complete GIF file with metadata.
        
        Args:
            blocks: List of (block_type, block_data) tuples
            xmp_metadata: XMP metadata dictionary
            
        Returns:
            Complete GIF file as bytes
        """
        gif_data = bytearray()
        
        # Write header and logical screen descriptor first
        for block_type, block_data in blocks:
            if block_type in (0, 1, 2):  # Header, LSD, GCT
                gif_data.extend(block_data)
        
        # Insert XMP application extension after header/LSD/GCT if we have XMP data
        if xmp_metadata:
            xmp_block = self._build_xmp_application_extension(xmp_metadata)
            if xmp_block:
                gif_data.extend(xmp_block)
        
        # Write remaining blocks (skip header/LSD/GCT already written)
        header_written = False
        lsd_written = False
        gct_written = False
        
        for block_type, block_data in blocks:
            if block_type == 0 and not header_written:
                header_written = True
                continue
            elif block_type == 1 and not lsd_written:
                lsd_written = True
                continue
            elif block_type == 2 and not gct_written:
                gct_written = True
                continue
            elif block_type == self.APPLICATION_EXTENSION:
                # Skip old XMP blocks (we've already added new one)
                if block_data.startswith(self.XMP_IDENTIFIER):
                    continue
                # Write other application extensions
                # block_data contains: [size_byte, identifier, ...sub-blocks..., 0x00]
                gif_data.append(self.EXTENSION_INTRODUCER)
                gif_data.append(self.APPLICATION_EXTENSION)
                gif_data.extend(block_data)  # Already includes size bytes and terminator
            elif block_type == self.GRAPHIC_CONTROL_EXTENSION:
                # Graphic Control Extension has fixed structure
                # block_data already contains: [block_size, packed, delay_low, delay_high, transparent_index]
                gif_data.append(self.EXTENSION_INTRODUCER)
                gif_data.append(self.GRAPHIC_CONTROL_EXTENSION)
                gif_data.extend(block_data)  # Write block_size + data
                gif_data.append(0x00)  # Block terminator
            elif block_type == self.COMMENT_EXTENSION:
                # Comment extension uses data sub-blocks
                # block_data is concatenated data from all sub-blocks
                gif_data.append(self.EXTENSION_INTRODUCER)
                gif_data.append(self.COMMENT_EXTENSION)
                gif_data.extend(self._write_data_sub_block(block_data))
            elif block_type == self.PLAIN_TEXT_EXTENSION:
                # Plain text extension uses data sub-blocks
                # block_data is concatenated data from all sub-blocks
                gif_data.append(self.EXTENSION_INTRODUCER)
                gif_data.append(self.PLAIN_TEXT_EXTENSION)
                gif_data.extend(self._write_data_sub_block(block_data))
            elif block_type == self.IMAGE_SEPARATOR:
                # Image data block (includes separator, descriptor, and image data)
                gif_data.extend(block_data)
            elif block_type == self.TRAILER:
                # Trailer
                gif_data.extend(block_data)
            else:
                # Unknown block type - skip to avoid corruption
                continue
        
        return bytes(gif_data)
    
    def _build_xmp_application_extension(self, xmp_metadata: Dict[str, Any]) -> Optional[bytes]:
        """
        Build XMP application extension block.
        
        Args:
            xmp_metadata: XMP metadata dictionary
            
        Returns:
            Application extension block bytes, or None if no metadata
        """
        if not xmp_metadata:
            return None
        
        # Build XMP packet (already returns bytes)
        xmp_packet = self.xmp_writer.build_xmp_packet(xmp_metadata)
        xmp_bytes = xmp_packet if isinstance(xmp_packet, bytes) else xmp_packet.encode('utf-8')
        
        # XMP application extension format:
        # 0x21 0xFF (extension introducer + application extension)
        # 0x0B (block size = 11)
        # "XMP DataXMP" (11 bytes identifier)
        # XMP data in 255-byte chunks
        # 0x00 (terminator)
        
        block = bytearray()
        block.append(self.EXTENSION_INTRODUCER)
        block.append(self.APPLICATION_EXTENSION)
        block.append(0x0B)  # Block size
        block.extend(self.XMP_IDENTIFIER)
        
        # Write XMP data in 255-byte chunks
        chunk_size = 255
        for i in range(0, len(xmp_bytes), chunk_size):
            chunk = xmp_bytes[i:i+chunk_size]
            block.append(len(chunk))
            block.extend(chunk)
        
        # Terminator
        block.append(0x00)
        
        return bytes(block)
    
    def _write_data_sub_block(self, data: bytes) -> bytes:
        """
        Write data as a GIF sub-block.
        
        Args:
            data: Data to write
            
        Returns:
            Sub-block bytes
        """
        block = bytearray()
        
        # Write in 255-byte chunks
        chunk_size = 255
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i+chunk_size]
            block.append(len(chunk))
            block.extend(chunk)
        
        # Terminator
        block.append(0x00)
        
        return bytes(block)

