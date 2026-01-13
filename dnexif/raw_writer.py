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
import json
import time
import tempfile
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from dnexif.exceptions import MetadataWriteError
from dnexif.tiff_writer import TIFFWriter
from dnexif.raw_parser import RAWParser
from dnexif.exif_tags import EXIF_TAG_NAMES
from dnexif.iptc_writer import IPTCWriter
from dnexif.xmp_writer import XMPWriter


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
        'FFF', 'IIQ', 'MEF', 'MOS', 'MRW', 'NRW', 'RWL', 'SRF', 'SR2'
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

    def _parse_mrw_sections(self, file_data: bytes) -> List[Dict[str, Any]]:
        if not file_data.startswith(b'\x00MRM') or len(file_data) < 12:
            return []

        sections = []
        offset = 8  # Skip MRW header + version/flags
        while offset + 8 <= len(file_data):
            header = file_data[offset:offset + 4]
            if header == b'\x00\x00\x00\x00':
                break

            size = struct.unpack('>I', file_data[offset + 4:offset + 8])[0]
            data_offset = offset + 8
            if size == 0 or data_offset + size > len(file_data):
                break

            sections.append({
                'offset': offset,
                'header': header,
                'name': header[1:4].upper(),
                'size': size,
                'data_offset': data_offset,
            })
            offset = data_offset + size

        return sections

    def _write_mrw_with_sections(
        self,
        file_data: bytes,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        sections = self._parse_mrw_sections(file_data)
        if not sections:
            raise MetadataWriteError("Invalid MRW file: missing or malformed MRM header/sections")

        ttw_section = next((s for s in sections if s['name'] == b'TTW'), None)
        if not ttw_section:
            raise MetadataWriteError("Invalid MRW file: missing TTW section")

        ttw_data = file_data[ttw_section['data_offset']:ttw_section['data_offset'] + ttw_section['size']]
        tiff_pos = ttw_data.find(b'II*\x00')
        if tiff_pos == -1:
            tiff_pos = ttw_data.find(b'MM\x00*')
        if tiff_pos == -1:
            raise MetadataWriteError("Invalid MRW file: TTW section has no TIFF header")

        tiff_prefix = ttw_data[:tiff_pos]
        tiff_data = ttw_data[tiff_pos:]

        endian = '<'
        if tiff_data[:2] == b'MM':
            endian = '>'
        elif tiff_data[:2] != b'II':
            raise MetadataWriteError("Invalid MRW file: bad TIFF byte order in TTW section")

        self.tiff_writer.endian = endian
        self.tiff_writer.exif_writer.endian = endian

        tiff_metadata = {
            k: v for k, v in metadata.items()
            if (k.startswith('EXIF:') or k.startswith('IFD0:') or k.startswith('GPS:') or
                k.startswith('IPTC:') or k.startswith('XMP:'))
        }

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            self.tiff_writer.write_tiff(tiff_data, tiff_metadata, tmp_path)
            with open(tmp_path, 'rb') as f:
                modified_tiff = f.read()
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass

        new_ttw_data = tiff_prefix + modified_tiff

        output = bytearray()
        output += file_data[:8]
        for section in sections:
            header = section['header']
            if section is ttw_section:
                section_data = new_ttw_data
            else:
                start = section['data_offset']
                end = start + section['size']
                section_data = file_data[start:end]

            output += header
            output += struct.pack('>I', len(section_data))
            output += section_data

        with open(output_path, 'wb') as f:
            f.write(output)
    
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
        write_start = time.perf_counter()
        def _find_tiff_offset(data: bytes, start: int = 0, limit: int = 1024 * 1024) -> Optional[int]:
            search_end = min(len(data), start + limit)
            tiff_pos = data.find(b'II*\x00', start, search_end)
            if tiff_pos == -1:
                tiff_pos = data.find(b'MM\x00*', start, search_end)
            return tiff_pos if tiff_pos != -1 else None

        try:
            if raw_format == 'MRW':
                try:
                    self._write_mrw_with_sections(file_data, metadata, output_path)
                    return
                except MetadataWriteError:
                    # Fall back to standard TIFF handling only if the file starts with a TIFF header.
                    if file_data[:2] not in (b'II', b'MM'):
                        raise MetadataWriteError(
                            "Invalid MRW file: missing MRM header/sections and no TIFF header found"
                        )

            # Handle format-specific headers
            tiff_data = file_data
            header_prefix = b''
            tiff_offset = 0
            
            if raw_format == 'ORF':
                # ORF has IIRO or MMOR header (4 bytes)
                # The TIFF structure may start at an offset specified in bytes 4-8
                # or we need to search for it
                if file_data.startswith(b'IIRO') or file_data.startswith(b'IIRS'):
                    header_prefix = file_data[:4]
                    tiff_data = b'II*\x00' + file_data[4:]
                    tiff_offset = 0
                elif file_data.startswith(b'MMOR'):
                    header_prefix = file_data[:4]
                    tiff_data = b'MM\x00*' + file_data[4:]
                    tiff_offset = 0
                else:
                    # Try to find TIFF structure for older ORF variants
                    tiff_pos = _find_tiff_offset(file_data)
                    if tiff_pos is not None and tiff_pos > 0:
                        header_prefix = file_data[:tiff_pos]
                        tiff_data = file_data[tiff_pos:]
                        tiff_offset = tiff_pos
                    else:
                        raise MetadataWriteError(f"Invalid {raw_format} file: could not find TIFF structure")
            
            elif raw_format == 'RW2':
                # RW2 uses a custom IIU/MMU header; preserve full file and patch IFD0 in place.
                self._write_rw2_in_place(file_data, metadata, output_path)
                return
            
            elif raw_format == 'RAF':
                # RAF has FUJIFILM header, then TIFF at offset
                if file_data.startswith(b'FUJIFILM'):
                    # Find TIFF structure
                    tiff_pos = _find_tiff_offset(file_data)
                    if tiff_pos is not None and tiff_pos > 0:
                        header_prefix = file_data[:tiff_pos]
                        tiff_data = file_data[tiff_pos:]
                        tiff_offset = tiff_pos
                    else:
                        raise MetadataWriteError(f"Invalid {raw_format} file: could not find TIFF structure")
                else:
                    raise MetadataWriteError(f"Invalid {raw_format} file")

            elif raw_format == 'ERF':
                tiff_pos = _find_tiff_offset(file_data, limit=len(file_data))
                if tiff_pos is not None and tiff_pos > 0:
                    header_prefix = file_data[:tiff_pos]
                    tiff_data = file_data[tiff_pos:]
                    tiff_offset = tiff_pos
                elif file_data[:2] in (b'II', b'MM'):
                    tiff_data = file_data
                    tiff_offset = 0
                else:
                    raise MetadataWriteError(f"Invalid {raw_format} file: could not find TIFF structure")
            
            elif raw_format == 'CR2':
                # Some CR2 variants embed TIFF data at a non-zero offset.
                if file_data[:2] in (b'II', b'MM'):
                    tiff_data = file_data
                    tiff_offset = 0
                else:
                    tiff_pos = _find_tiff_offset(file_data)
                    if tiff_pos is not None and tiff_pos > 0:
                        header_prefix = file_data[:tiff_pos]
                        tiff_data = file_data[tiff_pos:]
                        tiff_offset = tiff_pos
                    else:
                        raise MetadataWriteError(f"Invalid {raw_format} file: could not find TIFF structure")

            else:
                # Standard TIFF-based format (CR2, NEF, ARW, DNG, PEF, etc.)
                tiff_data = file_data
                tiff_offset = 0
            
            # Determine endianness from TIFF data
            endian = '<'
            if tiff_data[:2] == b'MM':
                endian = '>'
            elif tiff_data[:2] != b'II':
                if raw_format in ('ORF', 'ERF', 'MRW'):
                    raise MetadataWriteError(
                        f"Invalid {raw_format} file: missing TIFF header (no II/MM magic found)"
                    )
                raise MetadataWriteError(f"Invalid {raw_format} file: bad TIFF structure")
            
            # Update TIFF writer endianness
            self.tiff_writer.endian = endian
            self.tiff_writer.exif_writer.endian = endian
            
            # Extract metadata (EXIF, IPTC, XMP)
            # The TIFF writer now handles IPTC and XMP in addition to EXIF
            tiff_metadata = {
                k: v for k, v in metadata.items()
                if (k.startswith('EXIF:') or k.startswith('IFD0:') or k.startswith('GPS:') or
                    k.startswith('IPTC:') or k.startswith('XMP:'))
            }

            if raw_format == 'MOS':
                self._write_mos_in_place(file_data, metadata, output_path)
                return

            # For RAW files, we need to preserve:
            # 1. RAW image data (usually in IFD0 or a separate IFD)
            # 2. Preview/thumbnail images (often in IFD1)
            # 3. Manufacturer-specific IFDs (MakerNote, etc.)
            # 4. SubIFDs (for multiple images)
            
            if os.getenv('DNEXIF_RAW_WRITE_TIMING'):
                print(f"[RAW WRITE] {raw_format} setup {time.perf_counter() - write_start:.3f}s")

            # Use TIFF writer which handles image data preservation
            # Write to temporary path first
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                skip_parse = (raw_format == 'MOS')
                if raw_format == 'ORF':
                    # Avoid deep parsing on ORF; preserve core IFD0 tags for structure.
                    for tag_name, value in self._extract_ifd0_tags(tiff_data, endian).items():
                        tiff_metadata.setdefault(f'IFD0:{tag_name}', value)
                    skip_parse = True
                elif raw_format == 'DCR':
                    # DCR files can be large; avoid deep parse and preserve core IFD0 tags.
                    for tag_name, value in self._extract_ifd0_tags(tiff_data, endian).items():
                        tiff_metadata.setdefault(f'IFD0:{tag_name}', value)
                    skip_parse = True
                elif raw_format == 'NEF':
                    # NEF files can be large; avoid deep parse and preserve core IFD0 tags.
                    for tag_name, value in self._extract_ifd0_tags(tiff_data, endian).items():
                        tiff_metadata.setdefault(f'IFD0:{tag_name}', value)
                    skip_parse = True
                elif raw_format == 'ARW':
                    # ARW files can be large; avoid deep parse and preserve core IFD0 tags.
                    for tag_name, value in self._extract_ifd0_tags(tiff_data, endian).items():
                        tiff_metadata.setdefault(f'IFD0:{tag_name}', value)
                    skip_parse = True
                elif raw_format == 'PEF':
                    # PEF files can be large; avoid deep parse and preserve core IFD0 tags.
                    for tag_name, value in self._extract_ifd0_tags(tiff_data, endian).items():
                        tiff_metadata.setdefault(f'IFD0:{tag_name}', value)
                    skip_parse = True
                elif raw_format == '3FR':
                    # 3FR files can be large; avoid deep parse and preserve core IFD0 tags.
                    for tag_name, value in self._extract_ifd0_tags(tiff_data, endian).items():
                        tiff_metadata.setdefault(f'IFD0:{tag_name}', value)
                    skip_parse = True
                if os.getenv('DNEXIF_RAW_WRITE_TIMING'):
                    tiff_start = time.perf_counter()
                self.tiff_writer.write_tiff(tiff_data, tiff_metadata, tmp_path, skip_parse=skip_parse)
                if os.getenv('DNEXIF_RAW_WRITE_TIMING'):
                    print(f"[RAW WRITE] {raw_format} write_tiff {time.perf_counter() - tiff_start:.3f}s")
                
                # Read the modified TIFF data
                if os.getenv('DNEXIF_RAW_WRITE_TIMING'):
                    read_start = time.perf_counter()
                with open(tmp_path, 'rb') as f:
                    modified_tiff = f.read()
                if os.getenv('DNEXIF_RAW_WRITE_TIMING'):
                    print(f"[RAW WRITE] {raw_format} read tmp {time.perf_counter() - read_start:.3f}s")
                
                # Combine header prefix with modified TIFF
                if raw_format == 'ORF' and header_prefix in (b'IIRO', b'MMOR'):
                    modified_tiff = header_prefix + modified_tiff[4:]
                if os.getenv('DNEXIF_RAW_WRITE_TIMING'):
                    write_out_start = time.perf_counter()
                with open(output_path, 'wb') as f:
                    if header_prefix and raw_format != 'ORF':
                        f.write(header_prefix)
                    f.write(modified_tiff)
                if os.getenv('DNEXIF_RAW_WRITE_TIMING'):
                    print(f"[RAW WRITE] {raw_format} write out {time.perf_counter() - write_out_start:.3f}s")
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

    def _extract_ifd0_tags(self, tiff_data: bytes, endian: str) -> Dict[str, Any]:
        tag_ids = {
            256, 257, 258, 259, 262, 273, 277, 278, 279, 282, 283, 284, 296,
            317, 322, 323, 324, 325, 339
        }
        if len(tiff_data) < 8:
            return {}

        ifd0_offset = struct.unpack(f'{endian}I', tiff_data[4:8])[0]
        if ifd0_offset == 0 or ifd0_offset + 2 > len(tiff_data):
            return {}

        num_entries = struct.unpack(f'{endian}H', tiff_data[ifd0_offset:ifd0_offset + 2])[0]
        entry_offset = ifd0_offset + 2
        tags: Dict[str, Any] = {}

        type_sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1}

        for _ in range(min(num_entries, 200)):
            if entry_offset + 12 > len(tiff_data):
                break

            tag_id, tag_type, count = struct.unpack(
                f'{endian}HHI', tiff_data[entry_offset:entry_offset + 8]
            )
            value_bytes = tiff_data[entry_offset + 8:entry_offset + 12]
            value_offset = struct.unpack(f'{endian}I', value_bytes)[0]
            entry_offset += 12

            if tag_id not in tag_ids:
                continue

            size = type_sizes.get(tag_type)
            if not size:
                continue

            value_size = count * size
            if value_size <= 4:
                raw_value = value_bytes[:value_size]
            else:
                if value_offset + value_size > len(tiff_data):
                    continue
                raw_value = tiff_data[value_offset:value_offset + value_size]

            try:
                if tag_type == 3:  # SHORT
                    values = list(struct.unpack(f'{endian}{count}H', raw_value))
                    value = values[0] if count == 1 else values
                elif tag_type == 4:  # LONG
                    values = list(struct.unpack(f'{endian}{count}I', raw_value))
                    value = values[0] if count == 1 else values
                elif tag_type == 5:  # RATIONAL
                    values = []
                    for i in range(count):
                        numerator, denominator = struct.unpack(
                            f'{endian}II', raw_value[i * 8:(i + 1) * 8]
                        )
                        if denominator:
                            values.append(numerator / denominator)
                        else:
                            values.append(0)
                    value = values[0] if count == 1 else values
                elif tag_type == 2:  # ASCII
                    value = raw_value.split(b'\x00', 1)[0].decode('ascii', errors='replace')
                else:
                    continue
            except Exception:
                continue

            tag_name = EXIF_TAG_NAMES.get(tag_id)
            if tag_name:
                tags[tag_name] = value

        return tags

    def _write_mos_in_place(
        self,
        file_data: bytes,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write MOS metadata by appending a new IFD0 and preserving original structure.

        This avoids rebuilding the TIFF structure, which can corrupt MOS RAW data
        that relies on vendor-specific IFDs and offsets.
        """
        if len(file_data) < 8:
            raise MetadataWriteError("Invalid MOS file: too short")

        if file_data[:2] == b'II':
            endian = '<'
        elif file_data[:2] == b'MM':
            endian = '>'
        else:
            raise MetadataWriteError("Invalid MOS file: missing TIFF header")

        ifd0_offset = struct.unpack(f'{endian}I', file_data[4:8])[0]
        if ifd0_offset == 0 or ifd0_offset + 2 > len(file_data):
            raise MetadataWriteError("Invalid MOS file: bad IFD0 offset")

        num_entries = struct.unpack(f'{endian}H', file_data[ifd0_offset:ifd0_offset + 2])[0]
        if ifd0_offset + 2 + (num_entries * 12) + 4 > len(file_data):
            raise MetadataWriteError("Invalid MOS file: IFD0 extends past file size")

        entries = []
        entry_offset = ifd0_offset + 2
        for _ in range(num_entries):
            tag_id, tag_type, tag_count = struct.unpack(
                f'{endian}HHI', file_data[entry_offset:entry_offset + 8]
            )
            raw_value = file_data[entry_offset + 8:entry_offset + 12]
            entries.append({
                'id': tag_id,
                'type': tag_type,
                'count': tag_count,
                'raw_value': raw_value
            })
            entry_offset += 12

        next_ifd_offset = struct.unpack(
            f'{endian}I', file_data[entry_offset:entry_offset + 4]
        )[0]

        updates: Dict[int, Tuple[int, int, bytes]] = {}

        artist_value = metadata.get('EXIF:Artist') or metadata.get('IFD0:Artist')
        if artist_value is not None:
            artist_bytes = str(artist_value).encode('ascii', errors='replace') + b'\x00'
            updates[0x013B] = (2, len(artist_bytes), artist_bytes)

        copyright_value = metadata.get('EXIF:Copyright') or metadata.get('IFD0:Copyright')
        if copyright_value is not None:
            copyright_bytes = str(copyright_value).encode('ascii', errors='replace') + b'\x00'
            updates[0x8298] = (2, len(copyright_bytes), copyright_bytes)

        iptc_tags = {k: v for k, v in metadata.items() if k.startswith('IPTC:')}
        if iptc_tags:
            iptc_data = IPTCWriter().build_iptc_data(iptc_tags)
            if iptc_data:
                updates[0x83BB] = (7, len(iptc_data), iptc_data)

        xmp_tags = {k: v for k, v in metadata.items() if k.startswith('XMP:')}
        xmp_packet = XMPWriter().build_xmp_packet(xmp_tags)
        if xmp_packet:
            xmp_data = xmp_packet if isinstance(xmp_packet, bytes) else xmp_packet.encode('utf-8')
            updates[0x02BC] = (7, len(xmp_data), xmp_data)

        if not updates:
            with open(output_path, 'wb') as f:
                f.write(file_data)
            return

        tag_index = {entry['id']: idx for idx, entry in enumerate(entries)}
        for tag_id, update in updates.items():
            if tag_id in tag_index:
                entries[tag_index[tag_id]]['update'] = update
            else:
                tag_type, tag_count, data_bytes = update
                entries.append({
                    'id': tag_id,
                    'type': tag_type,
                    'count': tag_count,
                    'raw_value': b'\x00\x00\x00\x00',
                    'update': (tag_type, tag_count, data_bytes)
                })

        type_sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}
        new_ifd0_offset = len(file_data)
        entry_count = len(entries)
        ifd0_size = 2 + (entry_count * 12) + 4
        data_start_offset = new_ifd0_offset + ifd0_size
        current_offset = data_start_offset
        data_blocks: List[Tuple[int, bytes]] = []

        built_entries: List[Tuple[int, int, int, bytes]] = []
        for entry in entries:
            tag_id = entry['id']
            if 'update' in entry:
                tag_type, tag_count, data_bytes = entry['update']
                value_size = tag_count * type_sizes.get(tag_type, 1)
                if value_size <= 4:
                    value_bytes = data_bytes[:4].ljust(4, b'\x00')
                else:
                    if current_offset % 2 != 0:
                        current_offset += 1
                    value_bytes = struct.pack(f'{endian}I', current_offset)
                    data_blocks.append((current_offset, data_bytes))
                    current_offset += len(data_bytes)
                    if current_offset % 2 != 0:
                        current_offset += 1
                built_entries.append((tag_id, tag_type, tag_count, value_bytes))
            else:
                built_entries.append((tag_id, entry['type'], entry['count'], entry['raw_value']))

        ifd_bytes = bytearray()
        ifd_bytes.extend(struct.pack(f'{endian}H', entry_count))
        for tag_id, tag_type, tag_count, value_bytes in built_entries:
            ifd_bytes.extend(struct.pack(f'{endian}H', tag_id))
            ifd_bytes.extend(struct.pack(f'{endian}H', tag_type))
            ifd_bytes.extend(struct.pack(f'{endian}I', tag_count))
            ifd_bytes.extend(value_bytes)
        ifd_bytes.extend(struct.pack(f'{endian}I', next_ifd_offset))

        data_blob = bytearray()
        for offset, data_bytes in data_blocks:
            expected_offset = data_start_offset + len(data_blob)
            if offset < expected_offset:
                raise MetadataWriteError("Failed to build MOS data blocks: offset overlap")
            data_blob.extend(b'\x00' * (offset - expected_offset))
            data_blob.extend(data_bytes)
            if len(data_bytes) % 2 != 0:
                data_blob.extend(b'\x00')

        output_data = bytearray(file_data)
        output_data[4:8] = struct.pack(f'{endian}I', new_ifd0_offset)
        output_data.extend(ifd_bytes)
        output_data.extend(data_blob)

        with open(output_path, 'wb') as f:
            f.write(output_data)

    def _write_rw2_in_place(
        self,
        file_data: bytes,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write RW2 metadata by appending a new IFD0 and preserving original structure.

        RW2 files use a custom IIU/MMU header with an IFD0 pointer at offset 4.
        Updating the primary IFD0 keeps ExifTool visibility without rewriting RAW data.
        """
        if len(file_data) < 8:
            raise MetadataWriteError("Invalid RW2 file: too short")

        if file_data[:2] == b'II':
            endian = '<'
        elif file_data[:2] == b'MM':
            endian = '>'
        else:
            raise MetadataWriteError("Invalid RW2 file: missing byte order")

        if file_data[2:3] != b'U':
            raise MetadataWriteError("Invalid RW2 file: missing RW2 header")

        ifd0_offset = struct.unpack(f'{endian}I', file_data[4:8])[0]
        if ifd0_offset == 0 or ifd0_offset + 2 > len(file_data):
            raise MetadataWriteError("Invalid RW2 file: bad IFD0 offset")

        num_entries = struct.unpack(f'{endian}H', file_data[ifd0_offset:ifd0_offset + 2])[0]
        if ifd0_offset + 2 + (num_entries * 12) + 4 > len(file_data):
            raise MetadataWriteError("Invalid RW2 file: IFD0 extends past file size")

        entries = []
        entry_offset = ifd0_offset + 2
        for _ in range(num_entries):
            tag_id, tag_type, tag_count = struct.unpack(
                f'{endian}HHI', file_data[entry_offset:entry_offset + 8]
            )
            raw_value = file_data[entry_offset + 8:entry_offset + 12]
            entries.append({
                'id': tag_id,
                'type': tag_type,
                'count': tag_count,
                'raw_value': raw_value
            })
            entry_offset += 12

        next_ifd_offset = struct.unpack(
            f'{endian}I', file_data[entry_offset:entry_offset + 4]
        )[0]

        updates: Dict[int, Tuple[int, int, bytes]] = {}

        artist_value = metadata.get('EXIF:Artist') or metadata.get('IFD0:Artist')
        if artist_value is not None:
            artist_bytes = str(artist_value).encode('ascii', errors='replace') + b'\x00'
            updates[0x013B] = (2, len(artist_bytes), artist_bytes)

        copyright_value = metadata.get('EXIF:Copyright') or metadata.get('IFD0:Copyright')
        if copyright_value is not None:
            copyright_bytes = str(copyright_value).encode('ascii', errors='replace') + b'\x00'
            updates[0x8298] = (2, len(copyright_bytes), copyright_bytes)

        if not updates:
            with open(output_path, 'wb') as f:
                f.write(file_data)
            return

        tag_index = {entry['id']: idx for idx, entry in enumerate(entries)}
        for tag_id, update in updates.items():
            if tag_id in tag_index:
                entries[tag_index[tag_id]]['update'] = update
            else:
                tag_type, tag_count, data_bytes = update
                entries.append({
                    'id': tag_id,
                    'type': tag_type,
                    'count': tag_count,
                    'raw_value': b'\x00\x00\x00\x00',
                    'update': (tag_type, tag_count, data_bytes)
                })

        type_sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}
        new_ifd0_offset = len(file_data)
        entry_count = len(entries)
        ifd0_size = 2 + (entry_count * 12) + 4
        data_start_offset = new_ifd0_offset + ifd0_size
        current_offset = data_start_offset
        data_blocks: List[Tuple[int, bytes]] = []

        built_entries: List[Tuple[int, int, int, bytes]] = []
        for entry in entries:
            tag_id = entry['id']
            if 'update' in entry:
                tag_type, tag_count, data_bytes = entry['update']
                value_size = tag_count * type_sizes.get(tag_type, 1)
                if value_size <= 4:
                    value_bytes = data_bytes[:4].ljust(4, b'\x00')
                else:
                    if current_offset % 2 != 0:
                        current_offset += 1
                    value_bytes = struct.pack(f'{endian}I', current_offset)
                    data_blocks.append((current_offset, data_bytes))
                    current_offset += len(data_bytes)
                    if current_offset % 2 != 0:
                        current_offset += 1
                built_entries.append((tag_id, tag_type, tag_count, value_bytes))
            else:
                built_entries.append((tag_id, entry['type'], entry['count'], entry['raw_value']))

        ifd_bytes = bytearray()
        ifd_bytes.extend(struct.pack(f'{endian}H', entry_count))
        for tag_id, tag_type, tag_count, value_bytes in built_entries:
            ifd_bytes.extend(struct.pack(f'{endian}H', tag_id))
            ifd_bytes.extend(struct.pack(f'{endian}H', tag_type))
            ifd_bytes.extend(struct.pack(f'{endian}I', tag_count))
            ifd_bytes.extend(value_bytes)
        ifd_bytes.extend(struct.pack(f'{endian}I', next_ifd_offset))

        data_blob = bytearray()
        for offset, data_bytes in data_blocks:
            expected_offset = data_start_offset + len(data_blob)
            if offset < expected_offset:
                raise MetadataWriteError("Failed to build RW2 data blocks: offset overlap")
            data_blob.extend(b'\x00' * (offset - expected_offset))
            data_blob.extend(data_bytes)
            if len(data_bytes) % 2 != 0:
                data_blob.extend(b'\x00')

        output_data = bytearray(file_data)
        output_data[4:8] = struct.pack(f'{endian}I', new_ifd0_offset)
        output_data.extend(ifd_bytes)
        output_data.extend(data_blob)

        with open(output_path, 'wb') as f:
            f.write(output_data)
    
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
            self._write_crw_appended_metadata(file_data, metadata, output_path)
        elif raw_format == 'X3F':
            self._write_x3f_appended_metadata(file_data, metadata, output_path)
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
        # ORF uses a custom header; patch to a standard TIFF header for writing.
        if header_prefix.startswith(b'IIRO'):
            tiff_data = b'II*\x00' + file_data[4:]
            endian = '<'
        elif header_prefix.startswith(b'MMOR'):
            tiff_data = b'MM\x00*' + file_data[4:]
            endian = '>'
        else:
            tiff_data = file_data[tiff_offset:]
            endian = '<'
            if tiff_data[:2] == b'MM':
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
            
            # Replace TIFF header with ORF header while preserving IFD offset.
            with open(output_path, 'wb') as f:
                f.write(header_prefix)
                f.write(modified_tiff[4:])
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass

    def _write_x3f_appended_metadata(
        self,
        file_data: bytes,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        tag_payload = {
            k: str(v) for k, v in metadata.items()
            if (k.startswith('EXIF:') or k.startswith('IFD0:') or k.startswith('IPTC:') or k.startswith('XMP:'))
        }
        payload = json.dumps(tag_payload, ensure_ascii=True).encode('utf-8')
        magic = b'DNEXIFX3F'
        length = struct.pack('<I', len(payload))

        data = file_data
        existing = data.rfind(magic)
        if existing != -1 and existing + len(magic) + 4 <= len(data):
            data = data[:existing]

        with open(output_path, 'wb') as f:
            f.write(data)
            f.write(magic)
            f.write(length)
            f.write(payload)

    def _write_crw_appended_metadata(
        self,
        file_data: bytes,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        tag_payload = {
            k: str(v) for k, v in metadata.items()
            if (k.startswith('EXIF:') or k.startswith('IFD0:') or k.startswith('IPTC:') or k.startswith('XMP:'))
        }
        payload = json.dumps(tag_payload, ensure_ascii=True).encode('utf-8')
        magic = b'DNEXIFCRW'
        length = struct.pack('<I', len(payload))

        data = file_data
        existing = data.rfind(magic)
        if existing != -1 and existing + len(magic) + 4 <= len(data):
            data = data[:existing]

        with open(output_path, 'wb') as f:
            f.write(data)
            f.write(magic)
            f.write(length)
            f.write(payload)
    
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
