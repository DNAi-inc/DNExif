# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
TIFF metadata writer

This module provides a framework for writing metadata to TIFF files
with file structure preservation.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from dnexif.exceptions import MetadataWriteError
from dnexif.exif_writer import EXIFWriter
from dnexif.exif_parser import ExifParser, ExifTagType, TAG_SIZES
from dnexif.iptc_writer import IPTCWriter
from dnexif.xmp_writer import XMPWriter


class TIFFWriter:
    """
    TIFF writer with file structure preservation.
    
    This class provides a framework for writing metadata to TIFF files
    while preserving image data. Full implementation requires extensive
    TIFF format knowledge and testing.
    """
    
    def __init__(self, endian: str = '<', exif_version: str = '0300'):
        """
        Initialize TIFF writer.
        
        Args:
            endian: Byte order ('<' for little-endian, '>' for big-endian)
            exif_version: EXIF version to use ('0230' for 2.30, '0300' for 3.0)
        """
        self.endian = endian
        self.exif_writer = EXIFWriter(endian=endian, exif_version=exif_version)
        self.iptc_writer = IPTCWriter()
        self.xmp_writer = XMPWriter()
    
    def write_tiff(
        self,
        original_data: bytes,
        metadata: Dict[str, Any],
        output_path: str,
        skip_parse: bool = False
    ) -> None:
        """
        Write metadata to a TIFF file with structure preservation.
        
        This implementation preserves the original image data and
        rebuilds the TIFF structure with updated metadata.
        
        Args:
            original_data: Original TIFF file data
            metadata: Metadata dictionary to write
            output_path: Output file path
            
        Raises:
            MetadataWriteError: If writing fails
        """
        # Determine endianness from original file
        if original_data[:2] == b'II':
            self.endian = '<'
        elif original_data[:2] == b'MM':
            self.endian = '>'
        else:
            raise MetadataWriteError("Invalid TIFF file")
        self.exif_writer.endian = self.endian
        
        try:
            if skip_parse:
                updated_metadata = metadata.copy()
            else:
                # Parse original TIFF structure to extract image data
                exif_parser = ExifParser(file_data=original_data)
                original_metadata = exif_parser.read()
                
                # Merge new metadata with original
                updated_metadata = original_metadata.copy()
                updated_metadata.update(metadata)
            
            # Remove tags marked for deletion (None values)
            updated_metadata = {k: v for k, v in updated_metadata.items() if v is not None}
            
            # Extract image data from original TIFF (strips or tiles)
            image_data, strip_offsets, strip_byte_counts, tile_offsets, tile_byte_counts, is_tiled = self._extract_image_data(original_data)
            
            # Build new TIFF structure with updated metadata
            new_tiff_data = self._build_tiff_file(
                updated_metadata,
                image_data,
                strip_offsets,
                strip_byte_counts,
                tile_offsets,
                tile_byte_counts,
                is_tiled
            )
            
            # Write to output file
            with open(output_path, 'wb') as f:
                f.write(new_tiff_data)
                
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to write TIFF file: {str(e)}")
    
    def _extract_image_data(
        self,
        file_data: bytes
    ) -> Tuple[bytes, List[int], List[int], List[int], List[int], bool]:
        """
        Extract image data (strips or tiles) from TIFF file.
        
        Args:
            file_data: Original TIFF file data
            
        Returns:
            Tuple of (image_data, strip_offsets, strip_byte_counts, 
                     tile_offsets, tile_byte_counts, is_tiled)
        """
        # Parse IFD0 to find image data
        if len(file_data) < 8:
            return b'', [], [], [], [], False
        
        # Read IFD0 offset
        ifd0_offset = struct.unpack(f'{self.endian}I', file_data[4:8])[0]
        
        if ifd0_offset == 0 or ifd0_offset >= len(file_data):
            return b'', [], [], [], [], False
        
        # Parse IFD0 to find StripOffsets, StripByteCounts, TileOffsets, TileByteCounts
        num_entries = struct.unpack(f'{self.endian}H', 
                                   file_data[ifd0_offset:ifd0_offset + 2])[0]
        
        strip_offsets = []
        strip_byte_counts = []
        tile_offsets = []
        tile_byte_counts = []
        is_tiled = False
        
        entry_offset = ifd0_offset + 2
        for i in range(min(num_entries, 100)):
            if entry_offset + 12 > len(file_data):
                break
            
            tag_id = struct.unpack(f'{self.endian}H', 
                                  file_data[entry_offset:entry_offset + 2])[0]
            tag_type = struct.unpack(f'{self.endian}H', 
                                    file_data[entry_offset + 2:entry_offset + 4])[0]
            tag_count = struct.unpack(f'{self.endian}I', 
                                     file_data[entry_offset + 4:entry_offset + 8])[0]
            tag_value = struct.unpack(f'{self.endian}I', 
                                     file_data[entry_offset + 8:entry_offset + 12])[0]
            
            # StripOffsets tag (273)
            if tag_id == 273:
                if tag_count == 1:
                    strip_offsets = [tag_value]
                else:
                    # Multiple strips - read from offset
                    if tag_value < len(file_data):
                        strip_offsets = list(struct.unpack(
                            f'{self.endian}{tag_count}I',
                            file_data[tag_value:tag_value + (tag_count * 4)]
                        ))
            
            # StripByteCounts tag (279)
            elif tag_id == 279:
                if tag_count == 1:
                    strip_byte_counts = [tag_value]
                else:
                    # Multiple strips - read from offset
                    if tag_value < len(file_data):
                        strip_byte_counts = list(struct.unpack(
                            f'{self.endian}{tag_count}I',
                            file_data[tag_value:tag_value + (tag_count * 4)]
                        ))
            
            # TileOffsets tag (324)
            elif tag_id == 324:
                is_tiled = True
                if tag_count == 1:
                    tile_offsets = [tag_value]
                else:
                    # Multiple tiles - read from offset
                    if tag_value < len(file_data):
                        tile_offsets = list(struct.unpack(
                            f'{self.endian}{tag_count}I',
                            file_data[tag_value:tag_value + (tag_count * 4)]
                        ))
            
            # TileByteCounts tag (325)
            elif tag_id == 325:
                is_tiled = True
                if tag_count == 1:
                    tile_byte_counts = [tag_value]
                else:
                    # Multiple tiles - read from offset
                    if tag_value < len(file_data):
                        tile_byte_counts = list(struct.unpack(
                            f'{self.endian}{tag_count}I',
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
        
        return image_data, strip_offsets, strip_byte_counts, tile_offsets, tile_byte_counts, is_tiled
    
    def _build_tiff_file(
        self,
        metadata: Dict[str, Any],
        image_data: bytes,
        strip_offsets: List[int],
        strip_byte_counts: List[int],
        tile_offsets: List[int],
        tile_byte_counts: List[int],
        is_tiled: bool
    ) -> bytes:
        """
        Build a complete TIFF file with metadata and image data.
        
        Supports both strip-based and tile-based images.
        Complex TIFF files (multiple IFDs) are partially supported.
        
        Args:
            metadata: Metadata dictionary
            image_data: Image data bytes
            strip_offsets: List of strip offsets (for strip-based images)
            strip_byte_counts: List of strip byte counts
            tile_offsets: List of tile offsets (for tile-based images)
            tile_byte_counts: List of tile byte counts
            is_tiled: Whether image uses tiles instead of strips
            
        Returns:
            Complete TIFF file as bytes
        """
        # For now, implement a basic version that rebuilds the EXIF structure
        # and preserves image data if present
        
        # Use EXIF writer to build the TIFF structure (without JPEG APP1 wrapper)
        # The EXIF writer builds TIFF structures internally
        
        # Filter EXIF tags
        exif_tags = {}
        for key, value in metadata.items():
            if key.startswith('EXIF:') or key.startswith('IFD0:') or key.startswith('GPS:'):
                exif_tags[key] = value
        
        # Filter IPTC tags
        iptc_tags = {
            k: v for k, v in metadata.items()
            if k.startswith('IPTC:')
        }
        
        # Filter XMP tags
        xmp_tags = {
            k: v for k, v in metadata.items()
            if k.startswith('XMP:')
        }
        
        if not exif_tags and not iptc_tags and not xmp_tags and not image_data:
            raise MetadataWriteError("No metadata or image data to write")
        
        # Build TIFF header
        if self.endian == '<':
            header = b'II'
        else:
            header = b'MM'
        
        header += struct.pack(f'{self.endian}H', 42)  # Magic number
        header += struct.pack(f'{self.endian}I', 8)  # IFD0 offset (will be 8)
        
        # Ensure image data offsets exist so we can update them later
        if image_data:
            if is_tiled:
                if 'IFD0:TileOffsets' not in exif_tags:
                    exif_tags['IFD0:TileOffsets'] = [0]
                if 'IFD0:TileByteCounts' not in exif_tags:
                    exif_tags['IFD0:TileByteCounts'] = [len(image_data)]
            else:
                if 'IFD0:StripOffsets' not in exif_tags:
                    exif_tags['IFD0:StripOffsets'] = [0]
                if 'IFD0:StripByteCounts' not in exif_tags:
                    exif_tags['IFD0:StripByteCounts'] = [len(image_data)]

        # Build IFD0 with metadata using EXIF writer
        ifd0_tags, ifd0_data = self.exif_writer._build_ifd(exif_tags, ifd_type='IFD0')
        initial_ifd0_entries = len(ifd0_tags)
        
        # Calculate offsets
        base_offset = len(header)  # 8
        ifd0_offset = base_offset
        ifd0_data_offset = ifd0_offset + 2 + (len(ifd0_tags) * 12) + 4
        
        # Build EXIF IFD if needed
        exif_ifd_tags, exif_ifd_data = self.exif_writer._build_ifd(exif_tags, ifd_type='EXIF')
        exif_ifd_offset = 0
        exif_ifd_data_offset = 0
        
        if exif_ifd_tags:
            exif_ifd_offset = ifd0_data_offset + len(ifd0_data)
            exif_ifd_data_offset = exif_ifd_offset + 2 + (len(exif_ifd_tags) * 12) + 4
        
        # Build GPS IFD if needed
        gps_ifd_tags, gps_ifd_data = self.exif_writer._build_ifd(exif_tags, ifd_type='GPS')
        gps_ifd_offset = 0
        gps_ifd_data_offset = 0
        
        if gps_ifd_tags:
            if exif_ifd_tags:
                gps_ifd_offset = exif_ifd_data_offset + len(exif_ifd_data)
            else:
                gps_ifd_offset = ifd0_data_offset + len(ifd0_data)
            gps_ifd_data_offset = gps_ifd_offset + 2 + (len(gps_ifd_tags) * 12) + 4
        
        # Build IPTC data if present
        iptc_data = b''
        iptc_data_offset = 0
        if iptc_tags:
            iptc_data = self.iptc_writer.build_iptc_data(iptc_tags)
            if iptc_data:
                # IPTC is stored in tag 33723 (0x83BB) as UNDEFINED type (7)
                # Calculate offset after all IFDs
                if gps_ifd_tags:
                    iptc_data_offset = gps_ifd_data_offset + len(gps_ifd_data)
                elif exif_ifd_tags:
                    iptc_data_offset = exif_ifd_data_offset + len(exif_ifd_data)
                else:
                    iptc_data_offset = ifd0_data_offset + len(ifd0_data)
        
        # Build XMP data if present
        xmp_data = b''
        xmp_data_offset = 0
        if xmp_tags:
            xmp_packet = self.xmp_writer.build_xmp_packet(xmp_tags)
            if xmp_packet:
                xmp_data = xmp_packet if isinstance(xmp_packet, bytes) else xmp_packet.encode('utf-8')
                # XMP is stored in tag 700 (0x02BC) as UNDEFINED type (7)
                # Calculate offset after IPTC if present, otherwise after all IFDs
                if iptc_data:
                    xmp_data_offset = iptc_data_offset + len(iptc_data)
                elif gps_ifd_tags:
                    xmp_data_offset = gps_ifd_data_offset + len(gps_ifd_data)
                elif exif_ifd_tags:
                    xmp_data_offset = exif_ifd_data_offset + len(exif_ifd_data)
                else:
                    xmp_data_offset = ifd0_data_offset + len(ifd0_data)
        
        # Calculate image data offset
        image_data_offset = ifd0_data_offset + len(ifd0_data)
        if exif_ifd_tags:
            image_data_offset = exif_ifd_data_offset + len(exif_ifd_data)
        if gps_ifd_tags:
            image_data_offset = gps_ifd_data_offset + len(gps_ifd_data)
        if iptc_data:
            image_data_offset = iptc_data_offset + len(iptc_data)
        if xmp_data:
            image_data_offset = xmp_data_offset + len(xmp_data)

        def _update_ifd0_tag(tag_id: int, value: Any) -> None:
            for tag in ifd0_tags:
                if tag['id'] == tag_id:
                    tag_type, encoded_value, count = self.exif_writer._encode_tag_value(value)
                    if tag_type is None:
                        return
                    value_size = TAG_SIZES.get(ExifTagType(tag_type), 1) * count
                    if value_size <= 4:
                        tag['type'] = tag_type
                        tag['count'] = count
                        tag['value'] = encoded_value
                        tag['data'] = b''
                        tag['inline'] = True
                    else:
                        tag['type'] = tag_type
                        tag['count'] = count
                        tag['data'] = encoded_value
                        tag['inline'] = False
                    return

        if image_data:
            if is_tiled:
                counts = tile_byte_counts if tile_byte_counts else [len(image_data)]
                offsets = []
                current_offset = image_data_offset
                for count in counts:
                    offsets.append(current_offset)
                    current_offset += count
                _update_ifd0_tag(324, offsets)
                _update_ifd0_tag(325, counts)
            else:
                counts = strip_byte_counts if strip_byte_counts else [len(image_data)]
                offsets = []
                current_offset = image_data_offset
                for count in counts:
                    offsets.append(current_offset)
                    current_offset += count
                _update_ifd0_tag(273, offsets)
                _update_ifd0_tag(279, counts)
        
        # Update IFD0 to link to EXIF IFD if present
        if exif_ifd_tags:
            # Find or add EXIF IFD pointer tag (34665)
            exif_ifd_pointer_tag = None
            for tag in ifd0_tags:
                if tag['id'] == 34665:  # EXIF IFD pointer
                    exif_ifd_pointer_tag = tag
                    break
            
            if exif_ifd_pointer_tag is None:
                # Add EXIF IFD pointer tag
                exif_ifd_pointer_tag = {
                    'id': 34665,
                    'type': 4,  # LONG
                    'count': 1,
                    'value': struct.pack(f'{self.endian}I', exif_ifd_offset),
                    'data': b'',
                    'inline': True
                }
                ifd0_tags.append(exif_ifd_pointer_tag)
            else:
                exif_ifd_pointer_tag['value'] = struct.pack(f'{self.endian}I', exif_ifd_offset)
                exif_ifd_pointer_tag['inline'] = True
        
        # Update IFD0 to link to GPS IFD if present
        if gps_ifd_tags:
            # Find or add GPS IFD pointer tag (34853)
            gps_ifd_pointer_tag = None
            for tag in ifd0_tags:
                if tag['id'] == 34853:  # GPS IFD pointer
                    gps_ifd_pointer_tag = tag
                    break
            
            if gps_ifd_pointer_tag is None:
                # Add GPS IFD pointer tag
                gps_ifd_pointer_tag = {
                    'id': 34853,
                    'type': 4,  # LONG
                    'count': 1,
                    'value': struct.pack(f'{self.endian}I', gps_ifd_offset),
                    'data': b'',
                    'inline': True
                }
                ifd0_tags.append(gps_ifd_pointer_tag)
            else:
                gps_ifd_pointer_tag['value'] = struct.pack(f'{self.endian}I', gps_ifd_offset)
                gps_ifd_pointer_tag['inline'] = True
        
        # Add IPTC tag (33723 / 0x83BB) to IFD0 if present
        if iptc_data:
            # Find or add IPTC tag
            iptc_tag = None
            for tag in ifd0_tags:
                if tag['id'] == 33723:  # IPTC tag
                    iptc_tag = tag
                    break
            
            if iptc_tag is None:
                # Add IPTC tag as UNDEFINED type (7)
                iptc_tag = {
                    'id': 33723,
                    'type': 7,  # UNDEFINED
                    'count': len(iptc_data),
                    'value': iptc_data_offset,
                    'data': b'',
                    'inline': False
                }
                ifd0_tags.append(iptc_tag)
            else:
                iptc_tag['count'] = len(iptc_data)
                iptc_tag['value'] = iptc_data_offset
                iptc_tag['inline'] = False
        
        # Add XMP tag (700 / 0x02BC) to IFD0 if present
        if xmp_data:
            # Find or add XMP tag
            xmp_tag = None
            for tag in ifd0_tags:
                if tag['id'] == 700:  # XMP tag
                    xmp_tag = tag
                    break
            
            if xmp_tag is None:
                # Add XMP tag as UNDEFINED type (7)
                xmp_tag = {
                    'id': 700,
                    'type': 7,  # UNDEFINED
                    'count': len(xmp_data),
                    'value': xmp_data_offset,
                    'data': b'',
                    'inline': False
                }
                ifd0_tags.append(xmp_tag)
            else:
                xmp_tag['count'] = len(xmp_data)
                xmp_tag['value'] = xmp_data_offset
                xmp_tag['inline'] = False
        
        # Add image data references if present
        if image_data:
            if is_tiled and tile_offsets and tile_byte_counts:
                # Tile-based image
                if not tile_offsets or not tile_byte_counts:
                    # Single tile
                    tile_offsets = [image_data_offset]
                    tile_byte_counts = [len(image_data)]
                
                # Add TileOffsets tag (324) if not present
                has_tile_offsets = any(tag['id'] == 324 for tag in ifd0_tags)
                if not has_tile_offsets:
                    if len(tile_offsets) == 1:
                        tile_offsets_tag = {
                            'id': 324,
                            'type': 4,  # LONG
                            'count': 1,
                            'value': tile_offsets[0],
                            'data': struct.pack(f'{self.endian}I', tile_offsets[0])
                        }
                    else:
                        tile_offsets_tag = {
                            'id': 324,
                            'type': 4,  # LONG
                            'count': len(tile_offsets),
                            'value': image_data_offset - (len(tile_offsets) * 4),
                            'data': b''
                        }
                    ifd0_tags.append(tile_offsets_tag)
                
                # Add TileByteCounts tag (325) if not present
                has_tile_byte_counts = any(tag['id'] == 325 for tag in ifd0_tags)
                if not has_tile_byte_counts:
                    if len(tile_byte_counts) == 1:
                        tile_byte_counts_tag = {
                            'id': 325,
                            'type': 4,  # LONG
                            'count': 1,
                            'value': tile_byte_counts[0],
                            'data': struct.pack(f'{self.endian}I', tile_byte_counts[0])
                        }
                    else:
                        tile_byte_counts_tag = {
                            'id': 325,
                            'type': 4,  # LONG
                            'count': len(tile_byte_counts),
                            'value': image_data_offset - (len(tile_byte_counts) * 4),
                            'data': b''
                        }
                    ifd0_tags.append(tile_byte_counts_tag)
            else:
                # Strip-based image
                if not strip_offsets or not strip_byte_counts:
                    # Single strip
                    strip_offsets = [image_data_offset]
                    strip_byte_counts = [len(image_data)]
                
                # Add StripOffsets tag (273) if not present
                has_strip_offsets = any(tag['id'] == 273 for tag in ifd0_tags)
                if not has_strip_offsets:
                    if len(strip_offsets) == 1:
                        # Single strip - store inline
                        strip_offsets_tag = {
                            'id': 273,
                            'type': 4,  # LONG
                            'count': 1,
                            'value': strip_offsets[0],
                            'data': struct.pack(f'{self.endian}I', strip_offsets[0])
                        }
                    else:
                        # Multiple strips - store offset
                        strip_offsets_tag = {
                            'id': 273,
                            'type': 4,  # LONG
                            'count': len(strip_offsets),
                            'value': image_data_offset - (len(strip_offsets) * 4),
                            'data': b''
                        }
                    ifd0_tags.append(strip_offsets_tag)
                
                # Add StripByteCounts tag (279) if not present
                has_strip_byte_counts = any(tag['id'] == 279 for tag in ifd0_tags)
                if not has_strip_byte_counts:
                    if len(strip_byte_counts) == 1:
                        # Single strip - store inline
                        strip_byte_counts_tag = {
                            'id': 279,
                            'type': 4,  # LONG
                            'count': 1,
                            'value': strip_byte_counts[0],
                            'data': struct.pack(f'{self.endian}I', strip_byte_counts[0])
                        }
                    else:
                        # Multiple strips - store offset
                        strip_byte_counts_tag = {
                            'id': 279,
                            'type': 4,  # LONG
                            'count': len(strip_byte_counts),
                            'value': image_data_offset - (len(strip_byte_counts) * 4),
                            'data': b''
                        }
                    ifd0_tags.append(strip_byte_counts_tag)
        
        # Adjust offsets if we added new entries to IFD0 (e.g., pointer, strip, IPTC, or XMP tags)
        additional_entries = len(ifd0_tags) - initial_ifd0_entries
        if additional_entries > 0:
            offset_adjustment = additional_entries * 12
            ifd0_data_offset += offset_adjustment
            if exif_ifd_tags:
                exif_ifd_offset += offset_adjustment
                exif_ifd_data_offset += offset_adjustment
            if gps_ifd_tags:
                gps_ifd_offset += offset_adjustment
                gps_ifd_data_offset += offset_adjustment
            if iptc_data:
                iptc_data_offset += offset_adjustment
            if xmp_data:
                xmp_data_offset += offset_adjustment
            image_data_offset += offset_adjustment
            # Refresh pointer tag values with adjusted offsets
            if exif_ifd_tags and exif_ifd_pointer_tag is not None:
                exif_ifd_pointer_tag['value'] = struct.pack(f'{self.endian}I', exif_ifd_offset)
            if gps_ifd_tags and gps_ifd_pointer_tag is not None:
                gps_ifd_pointer_tag['value'] = struct.pack(f'{self.endian}I', gps_ifd_offset)
            # Refresh IPTC and XMP tag values with adjusted offsets
            if iptc_data:
                for tag in ifd0_tags:
                    if tag['id'] == 33723:  # IPTC tag
                        tag['value'] = iptc_data_offset
            if xmp_data:
                for tag in ifd0_tags:
                    if tag['id'] == 700:  # XMP tag
                        tag['value'] = xmp_data_offset

        # Build complete TIFF file
        tiff_data = bytearray()
        tiff_data.extend(header)
        
        # Write IFD0
        tiff_data.extend(self.exif_writer._write_ifd(ifd0_tags, ifd0_data, ifd0_data_offset))
        tiff_data.extend(ifd0_data)
        
        # Write EXIF IFD if present
        if exif_ifd_tags:
            tiff_data.extend(self.exif_writer._write_ifd(exif_ifd_tags, exif_ifd_data, exif_ifd_data_offset))
            tiff_data.extend(exif_ifd_data)
        
        # Write GPS IFD if present
        if gps_ifd_tags:
            tiff_data.extend(self.exif_writer._write_ifd(gps_ifd_tags, gps_ifd_data, gps_ifd_data_offset))
            tiff_data.extend(gps_ifd_data)
        
        # Write IPTC data if present
        if iptc_data:
            tiff_data.extend(iptc_data)
        
        # Write XMP data if present
        if xmp_data:
            tiff_data.extend(xmp_data)
        
        # Write image data if present
        if image_data:
            tiff_data.extend(image_data)
        
        return bytes(tiff_data)
