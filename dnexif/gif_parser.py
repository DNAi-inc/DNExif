# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
GIF metadata parser

Extracts XMP metadata embedded in GIF application extension blocks.
GIF XMP is typically stored in a block with the identifier ``XMP DataXMP``.

This parser focuses on locating that block and handing the packet off
to the shared XMP parser so downstream consumers receive familiar
``XMP:*`` keys (e.g., ``XMP:Title``).
"""

from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from dnexif.exceptions import MetadataReadError
from dnexif.xmp_parser import XMPParser


class GIFParser:
    """Parser for GIF metadata (currently XMP packets)."""

    EXTENSION_INTRODUCER = 0x21
    APPLICATION_EXTENSION = 0xFF
    COMMENT_EXTENSION = 0xFE
    PLAIN_TEXT_EXTENSION = 0x01
    GRAPHIC_CONTROL_EXTENSION = 0xF9
    IMAGE_SEPARATOR = 0x2C
    TRAILER = 0x3B
    XMP_IDENTIFIER = b'XMP DataXMP'

    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        self.file_path = Path(file_path) if file_path else None
        self.file_data = file_data

    def parse(self) -> Dict[str, Any]:
        """Parse GIF metadata."""
        try:
            data = self.file_data
            if data is None:
                if not self.file_path or not self.file_path.exists():
                    return {}
                data = self.file_path.read_bytes()
            if not data or not (data.startswith(b'GIF87a') or data.startswith(b'GIF89a')):
                return {}

            metadata: Dict[str, Any] = {}
            
            # Parse GIF header and Logical Screen Descriptor
            self._parse_gif_header(data, metadata)
            
            # Parse animation and frame information
            self._parse_gif_animation(data, metadata)
            
            # Parse XMP metadata
            xmp_packet = self._extract_xmp_packet(data)
            if xmp_packet:
                try:
                    xmp_parser = XMPParser(file_data=xmp_packet)
                    metadata.update(xmp_parser.read(scan_entire_file=True))
                except Exception:
                    pass
            
            # Parse user-defined application extensions
            self._parse_gif_application_extensions(data, metadata)
            
            return metadata
        except Exception as exc:
            raise MetadataReadError(f"Failed to parse GIF metadata: {exc}") from exc
    
    def _parse_gif_header(self, data: bytes, metadata: Dict[str, Any]) -> None:
        """Parse GIF header and Logical Screen Descriptor."""
        try:
            if len(data) < 13:
                return
            
            # GIF version (bytes 0-5)
            version = data[0:6].decode('ascii', errors='ignore')
            # Standard format shows just "87a" or "89a", not "GIF87a" or "GIF89a"
            if version.startswith('GIF'):
                version = version[3:]
            metadata['GIF:GIFVersion'] = version
            
            # Logical Screen Descriptor (bytes 6-12)
            # Width (2 bytes, little-endian)
            width = int.from_bytes(data[6:8], 'little')
            metadata['GIF:ImageWidth'] = width
            # Height (2 bytes, little-endian)
            height = int.from_bytes(data[8:10], 'little')
            metadata['GIF:ImageHeight'] = height
            
            # Packed byte (byte 10)
            packed = data[10]
            has_color_map = (packed & 0x80) != 0
            color_resolution = ((packed >> 4) & 0x07) + 1
            sort_flag = (packed & 0x08) != 0
            gct_size = 2 << (packed & 0x07)
            
            metadata['GIF:HasColorMap'] = 'Yes' if has_color_map else 'No'
            metadata['GIF:ColorResolutionDepth'] = color_resolution
            metadata['GIF:BitsPerPixel'] = color_resolution
            
            # Background Color Index (byte 11)
            background_color = data[11]
            metadata['GIF:BackgroundColor'] = background_color
            
            # Don't set TransparentColor here - let it be set from Graphic Control Extension if present
            # standard format calculates TransparentColor from GCE, not from BackgroundColor
            # We'll only use BackgroundColor - 7 as a fallback if no GCE is found
            
            # Pixel Aspect Ratio (byte 12)
            # If 0, aspect ratio is not specified
            # If non-zero, aspect ratio = (value + 15) / 64
            pixel_aspect = data[12]
            if pixel_aspect != 0:
                # Calculate aspect ratio: (pixel_aspect + 15) / 64
                aspect_ratio = (pixel_aspect + 15) / 64.0
                metadata['GIF:PixelAspectRatio'] = aspect_ratio
                # Also store as AspectRatio (Standard format shows both)
                metadata['GIF:AspectRatio'] = aspect_ratio
                # Format as fraction if it's a common ratio
                if aspect_ratio == 1.0:
                    metadata['GIF:PixelAspectRatio'] = '1:1'
                    metadata['GIF:AspectRatio'] = '1:1'
                elif abs(aspect_ratio - 4.0/3.0) < 0.01:
                    metadata['GIF:PixelAspectRatio'] = '4:3'
                    metadata['GIF:AspectRatio'] = '4:3'
                elif abs(aspect_ratio - 16.0/9.0) < 0.01:
                    metadata['GIF:PixelAspectRatio'] = '16:9'
                    metadata['GIF:AspectRatio'] = '16:9'
                else:
                    # Store as decimal with precision
                    metadata['GIF:PixelAspectRatio'] = f"{aspect_ratio:.6f}"
                    metadata['GIF:AspectRatio'] = f"{aspect_ratio:.6f}"
            
        except Exception:
            pass  # GIF header parsing is optional
    
    def _parse_gif_animation(self, data: bytes, metadata: Dict[str, Any]) -> None:
        """Parse GIF animation information (NETSCAPE extension, frame count, duration)."""
        try:
            import struct
            offset = 6  # Skip header
            
            # Skip Logical Screen Descriptor
            if offset + 7 > len(data):
                return
            lsd = data[offset:offset+7]
            offset += 7
            
            # Check for Global Color Table
            packed = lsd[4]
            has_gct = (packed & 0x80) != 0
            gct_size = 2 << (packed & 0x07)
            if has_gct:
                gct_bytes = gct_size * 3
                offset += gct_bytes
            
            frame_count = 0
            total_duration = 0.0
            animation_iterations = 0
            
            # Parse blocks to find NETSCAPE extension and count frames
            while offset < len(data) - 1:
                block_id = data[offset]
                
                if block_id == self.EXTENSION_INTRODUCER:
                    offset += 1
                    if offset >= len(data):
                        break
                    label = data[offset]
                    offset += 1
                    
                    if label == self.APPLICATION_EXTENSION:
                        if offset >= len(data):
                            break
                        block_size = data[offset]
                        offset += 1
                        if offset + block_size > len(data):
                            break
                        app_identifier = data[offset:offset+block_size]
                        offset += block_size
                        
                        # Check for NETSCAPE extension (animation control)
                        if app_identifier == b'NETSCAPE2.0':
                            sub_blocks, offset = self._read_sub_blocks(data, offset)
                            if sub_blocks and len(sub_blocks) >= 3:
                                # First byte is 1, next 2 bytes are iteration count (0 = infinite)
                                if sub_blocks[0] == 1:
                                    iterations = struct.unpack('<H', sub_blocks[1:3])[0]
                                    animation_iterations = iterations
                        else:
                            _, offset = self._read_sub_blocks(data, offset)
                    elif label == self.GRAPHIC_CONTROL_EXTENSION:
                        # Parse Graphic Control Extension
                        # GCE structure: block_size(1) + packed(1) + delay(2) + transparent_color(1) + terminator(1)
                        if offset + 4 < len(data):
                            block_size = data[offset]
                            # block_size is typically 4 (packed + delay + transparent)
                            if block_size >= 4:
                                # Packed byte (disposal method, user input flag, transparent color flag)
                                packed = data[offset+1]
                                has_transparent = (packed & 0x01) != 0
                                delay_time = struct.unpack('<H', data[offset+2:offset+4])[0]
                                # Delay time is in hundredths of a second
                                total_duration += delay_time / 100.0
                                
                                # Transparent Color Index (byte 4, only if transparent flag is set)
                                # block_size=4 means we have 4 data bytes: packed(1) + delay(2) + transparent(1)
                                if has_transparent and offset + 4 < len(data):
                                    transparent_color = data[offset+4]
                                    if 'GIF:TransparentColor' not in metadata:
                                        # standard behavior: if GCE transparent color equals BackgroundColor,
                                        # use BackgroundColor - 7 instead (standard fallback calculation)
                                        background_color = metadata.get('GIF:BackgroundColor')
                                        if background_color is not None and transparent_color == background_color and background_color >= 7:
                                            metadata['GIF:TransparentColor'] = background_color - 7
                                        else:
                                            metadata['GIF:TransparentColor'] = transparent_color
                        offset = self._skip_fixed_block(data, offset)
                    elif label in (self.PLAIN_TEXT_EXTENSION, self.COMMENT_EXTENSION):
                        _, offset = self._read_sub_blocks(data, offset)
                    else:
                        _, offset = self._read_sub_blocks(data, offset)
                elif block_id == self.IMAGE_SEPARATOR:
                    frame_count += 1
                    offset = self._skip_image_block(data, offset)
                elif block_id == self.TRAILER:
                    break
                else:
                    offset += 1
            
            # Add animation metadata
            if frame_count > 0:
                metadata['GIF:FrameCount'] = frame_count
            if total_duration > 0:
                # Store as float, let formatter handle the formatting
                metadata['GIF:Duration'] = total_duration
            if animation_iterations == 0 and frame_count > 1:
                metadata['GIF:AnimationIterations'] = 'Infinite'
            elif animation_iterations > 0:
                metadata['GIF:AnimationIterations'] = str(animation_iterations)
            
            # If no TransparentColor was found in GCE, use standard fallback calculation
            # Standard format uses BackgroundColor - 7 as a fallback when no GCE transparent color is present
            if 'GIF:TransparentColor' not in metadata:
                background_color = metadata.get('GIF:BackgroundColor')
                if background_color is not None and background_color >= 7:
                    metadata['GIF:TransparentColor'] = background_color - 7
            
        except Exception:
            pass  # Animation parsing is optional

    def _extract_xmp_packet(self, data: bytes) -> Optional[bytes]:
        """Locate and return the raw XMP packet bytes."""
        offset = 6  # Skip header
        if offset + 7 > len(data):
            return None

        lsd = data[offset:offset + 7]
        offset += 7

        packed = lsd[4]
        has_gct = (packed & 0x80) != 0
        gct_size = 2 << (packed & 0x07)
        if has_gct:
            gct_bytes = gct_size * 3
            if offset + gct_bytes > len(data):
                return None
            offset += gct_bytes

        while offset < len(data):
            block_id = data[offset]
            if block_id == self.EXTENSION_INTRODUCER:
                offset += 1
                if offset >= len(data):
                    break
                label = data[offset]
                offset += 1

                if label == self.APPLICATION_EXTENSION:
                    if offset >= len(data):
                        break
                    block_size = data[offset]
                    offset += 1
                    if offset + block_size > len(data):
                        break
                    app_identifier = data[offset:offset + block_size]
                    offset += block_size
                    sub_blocks, offset = self._read_sub_blocks(data, offset)
                    if sub_blocks is None:
                        break
                    if app_identifier == self.XMP_IDENTIFIER:
                        return sub_blocks
                elif label == self.GRAPHIC_CONTROL_EXTENSION:
                    offset = self._skip_fixed_block(data, offset)
                elif label in (self.PLAIN_TEXT_EXTENSION, self.COMMENT_EXTENSION):
                    _, offset = self._read_sub_blocks(data, offset)
                else:
                    _, offset = self._read_sub_blocks(data, offset)
            elif block_id == self.IMAGE_SEPARATOR:
                offset = self._skip_image_block(data, offset)
            elif block_id == self.TRAILER:
                break
            else:
                break
        return None

    def _read_sub_blocks(self, data: bytes, offset: int) -> Tuple[Optional[bytes], int]:
        """Read GIF sub-blocks and return their concatenated payload."""
        payload = bytearray()
        while offset < len(data):
            size = data[offset]
            offset += 1
            if size == 0:
                return bytes(payload), offset
            if offset + size > len(data):
                return None, offset
            payload.extend(data[offset:offset + size])
            offset += size
        return None, offset

    def _skip_fixed_block(self, data: bytes, offset: int) -> int:
        """Skip fixed-size extension blocks (e.g., Graphic Control Extension)."""
        if offset >= len(data):
            return offset
        block_size = data[offset]
        offset += 1 + block_size
        if offset < len(data):
            offset += 1  # terminator
        return offset

    def _parse_gif_application_extensions(self, data: bytes, metadata: Dict[str, Any]) -> None:
        """Parse user-defined application extensions (excluding XMP and NETSCAPE)."""
        try:
            offset = 6  # Skip header
            if offset + 7 > len(data):
                return
            
            # Skip Logical Screen Descriptor
            lsd = data[offset:offset+7]
            offset += 7
            
            # Check for Global Color Table
            packed = lsd[4]
            has_gct = (packed & 0x80) != 0
            gct_size = 2 << (packed & 0x07)
            if has_gct:
                gct_bytes = gct_size * 3
                offset += gct_bytes
            
            app_extensions = []
            
            # Parse blocks to find application extensions
            while offset < len(data) - 1:
                block_id = data[offset]
                
                if block_id == self.EXTENSION_INTRODUCER:
                    offset += 1
                    if offset >= len(data):
                        break
                    label = data[offset]
                    offset += 1
                    
                    if label == self.APPLICATION_EXTENSION:
                        if offset >= len(data):
                            break
                        block_size = data[offset]
                        offset += 1
                        if offset + block_size > len(data):
                            break
                        app_identifier = data[offset:offset + block_size]
                        offset += block_size
                        
                        # Skip known application extensions (XMP and NETSCAPE are already handled)
                        if app_identifier == self.XMP_IDENTIFIER or app_identifier == b'NETSCAPE2.0':
                            _, offset = self._read_sub_blocks(data, offset)
                            continue
                        
                        # Read sub-blocks for user-defined application extension
                        sub_blocks, offset = self._read_sub_blocks(data, offset)
                        if sub_blocks is not None and len(sub_blocks) > 0:
                            # Decode application identifier (typically 8 bytes ASCII)
                            try:
                                app_id_str = app_identifier.decode('ascii', errors='ignore').strip('\x00')
                                if app_id_str:
                                    # Store application extension information
                                    app_ext_info = {
                                        'identifier': app_id_str,
                                        'size': len(sub_blocks),
                                        'data': sub_blocks.hex().upper() if len(sub_blocks) <= 64 else sub_blocks[:64].hex().upper() + '...'
                                    }
                                    app_extensions.append(app_ext_info)
                                    # Store as GIF:ApplicationExtension:identifier
                                    metadata[f'GIF:ApplicationExtension:{app_id_str}'] = f'Present ({len(sub_blocks)} bytes)'
                                    # Store data reference if small enough
                                    if len(sub_blocks) <= 256:
                                        metadata[f'GIF:ApplicationExtension:{app_id_str}:Data'] = sub_blocks
                            except Exception:
                                pass
                    elif label == self.GRAPHIC_CONTROL_EXTENSION:
                        offset = self._skip_fixed_block(data, offset)
                    elif label in (self.PLAIN_TEXT_EXTENSION, self.COMMENT_EXTENSION):
                        _, offset = self._read_sub_blocks(data, offset)
                    else:
                        _, offset = self._read_sub_blocks(data, offset)
                elif block_id == self.IMAGE_SEPARATOR:
                    offset = self._skip_image_block(data, offset)
                elif block_id == self.TRAILER:
                    break
                else:
                    offset += 1
            
            # Store count of user-defined application extensions
            if app_extensions:
                metadata['GIF:ApplicationExtension:Count'] = len(app_extensions)
                # Store list of identifiers
                identifiers = [ext['identifier'] for ext in app_extensions]
                metadata['GIF:ApplicationExtension:Identifiers'] = ', '.join(identifiers)
        
        except Exception:
            pass  # Application extension parsing is optional

    def _skip_image_block(self, data: bytes, offset: int) -> int:
        """Skip image descriptor, optional local color table, and image data."""
        offset += 1  # skip separator
        if offset + 9 > len(data):
            return len(data)
        descriptor = data[offset:offset + 9]
        offset += 9
        packed = descriptor[8]
        has_lct = (packed & 0x80) != 0
        lct_size = 2 << (packed & 0x07)
        if has_lct:
            lct_bytes = lct_size * 3
            offset += lct_bytes
        if offset >= len(data):
            return len(data)
        offset += 1  # LZW minimum code size
        while offset < len(data):
            block_size = data[offset]
            offset += 1
            if block_size == 0:
                break
            offset += block_size
        return offset

