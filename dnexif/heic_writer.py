# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
HEIC/HEIF metadata writer

This module provides metadata writing for HEIC/HEIF files.
HEIC files use ISOBMFF container format (similar to MP4).

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from dnexif.exceptions import MetadataWriteError
from dnexif.xmp_writer import XMPWriter
from dnexif.exif_writer import EXIFWriter


class HEICWriter:
    """
    Writer for HEIC/HEIF metadata.
    
    HEIC files use ISOBMFF container format. Metadata is stored in:
    - meta box (metadata container)
    - EXIF box (EXIF data)
    - XMP box (XMP data in UUID box)
    """
    
    def __init__(self, exif_version: str = '0300'):
        """
        Initialize HEIC writer.
        
        Args:
            exif_version: EXIF version to use (default: '0300' for EXIF 3.0)
        """
        if not exif_version:
            exif_version = '0300'
        if isinstance(exif_version, bytes):
            exif_version = exif_version.decode('ascii', errors='replace')
        if not isinstance(exif_version, str):
            exif_version = str(exif_version)
        self.exif_writer = EXIFWriter(exif_version=exif_version)
        self.xmp_writer = XMPWriter()
    
    def write_heic(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to HEIC file.
        
        Args:
            file_path: Path to input HEIC file
            metadata: Dictionary of metadata to write
            output_path: Path to output HEIC file
            
        Raises:
            MetadataWriteError: If writing fails
        """
        try:
            with open(file_path, 'rb') as f:
                heic_data = f.read()
            
            if len(heic_data) < 8:
                raise MetadataWriteError("Invalid HEIC file: too short")
            
            # Check for ftyp box
            if heic_data[4:8] != b'ftyp':
                ftyp_pos = heic_data.find(b'ftyp')
                if ftyp_pos == -1:
                    raise MetadataWriteError("Invalid HEIC file: missing ftyp box")
            
            # Separate metadata by type
            exif_metadata: Dict[str, Any] = {}
            xmp_metadata: Dict[str, Any] = {}

            for key, value in metadata.items():
                if key.startswith(('EXIF:', 'IFD0:', 'GPS:')):
                    exif_metadata[key] = value
                elif key.startswith('XMP:'):
                    xmp_metadata[key] = value
                elif ':' not in key:
                    # Default to EXIF namespace for unknown prefixes
                    exif_metadata[f"EXIF:{key}"] = value

            # Mirror EXIF artist into XMP for broader reader compatibility.
            if 'XMP:Artist' not in xmp_metadata:
                artist_value = metadata.get('EXIF:Artist') or metadata.get('IFD0:Artist') or metadata.get('Artist')
                if artist_value:
                    xmp_metadata['XMP:Artist'] = artist_value
            
            # Write EXIF metadata if present
            if exif_metadata:
                exif_bytes = self._build_exif_payload(exif_metadata)
                if exif_bytes:
                    heic_data = self._write_exif_box(heic_data, exif_metadata, exif_bytes)
                    heic_data = self._ensure_item_property_linkage(heic_data, exif_bytes)
            
            # Write XMP metadata if present
            if xmp_metadata:
                heic_data = self._write_xmp_box(heic_data, xmp_metadata)
            
            # Write output file
            with open(output_path, 'wb') as f:
                f.write(heic_data)
                
        except Exception as e:
            raise MetadataWriteError(f"Failed to write HEIC metadata: {str(e)}")
    
    def _write_exif_box(self, heic_data: bytes, metadata: Dict[str, Any], exif_bytes: Optional[bytes] = None) -> bytes:
        """
        Write EXIF data to HEIC file in exif box.
        
        Args:
            heic_data: Original HEIC data
            metadata: EXIF metadata dictionary
            
        Returns:
            Modified HEIC data with EXIF box
        """
        try:
            if exif_bytes is None:
                exif_bytes = self._build_exif_payload(metadata)
            if not exif_bytes:
                return heic_data
            
            # Find or create meta box
            meta_box_pos = self._find_box(heic_data, b'meta')
            if meta_box_pos == -1:
                # Create minimal meta box with version/flags and exif child box
                exif_box = self._create_box(b'exif', exif_bytes)
                meta_payload = struct.pack('>I', 0) + exif_box
                meta_box = self._create_box(b'meta', meta_payload)
                # Insert after ftyp box
                ftyp_end = self._find_box_end(heic_data, b'ftyp')
                if ftyp_end != -1:
                    return heic_data[:ftyp_end] + meta_box + heic_data[ftyp_end:]
            
            # Find exif box in meta box
            exif_box_pos = self._find_box(heic_data, b'exif', meta_box_pos)
            if exif_box_pos != -1:
                # Update existing exif box
                exif_box_end = self._find_box_end(heic_data, b'exif', exif_box_pos)
                if exif_box_end != -1:
                    new_exif_box = self._create_box(b'exif', exif_bytes)
                    return (
                        heic_data[:exif_box_pos] +
                        new_exif_box +
                        heic_data[exif_box_end:]
                    )
            
            # Add new exif box to meta box
            meta_box_end = self._find_box_end(heic_data, b'meta', meta_box_pos)
            if meta_box_end != -1:
                exif_box = self._create_box(b'exif', exif_bytes)
                # Update meta box size
                meta_size = struct.unpack('>I', heic_data[meta_box_pos:meta_box_pos+4])[0]
                new_meta_size = meta_size + len(exif_box)
                new_heic = (
                    heic_data[:meta_box_pos] +
                    struct.pack('>I', new_meta_size) +
                    heic_data[meta_box_pos+4:meta_box_end] +
                    exif_box +
                    heic_data[meta_box_end:]
                )
                return new_heic
            
            # Fallback: append exif box
            exif_box = self._create_box(b'exif', exif_bytes)
            return heic_data + exif_box
            
        except Exception as e:
            raise MetadataWriteError(f"Failed to write EXIF box: {str(e)}")

    def _build_exif_payload(self, metadata: Dict[str, Any]) -> bytes:
        """
        Build EXIF payload for HEIC exif box (4-byte offset + TIFF data).
        """
        app1_segment = self.exif_writer.build_exif_segment(metadata)
        if not app1_segment:
            return b''

        tiff_data = app1_segment
        if app1_segment.startswith(b'\xFF\xE1') and len(app1_segment) > 10:
            if app1_segment[4:10] == b'Exif\x00\x00':
                tiff_data = app1_segment[10:]

        return struct.pack('>I', 0) + tiff_data
    
    def _write_xmp_box(self, heic_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """
        Write XMP data to HEIC file in UUID box.
        
        Args:
            heic_data: Original HEIC data
            metadata: XMP metadata dictionary
            
        Returns:
            Modified HEIC data with XMP UUID box
        """
        try:
            # Generate XMP packet (already returns bytes)
            xmp_packet = self.xmp_writer.build_xmp_packet(metadata)
            # build_xmp_packet already returns bytes, no need to encode
            xmp_bytes = xmp_packet if isinstance(xmp_packet, bytes) else xmp_packet.encode('utf-8')
            
            # XMP UUID: B14BF8BD-083D-4B43-A5D8-0208A36F02B8
            xmp_uuid_hex = 'B14BF8BD083D4B43A5D80208A36F02B8'
            if len(xmp_uuid_hex) % 2 != 0:
                xmp_uuid_hex = f"0{xmp_uuid_hex}"
            xmp_uuid = bytes.fromhex(xmp_uuid_hex)
            
            # Find or create meta box
            meta_box_pos = self._find_box(heic_data, b'meta')
            if meta_box_pos == -1:
                # Create meta box and add XMP UUID box
                uuid_box = self._create_uuid_box(xmp_uuid, xmp_bytes)
                ftyp_end = self._find_box_end(heic_data, b'ftyp')
                if ftyp_end != -1:
                    return heic_data[:ftyp_end] + uuid_box + heic_data[ftyp_end:]
            
            # Find existing XMP UUID box
            uuid_box_pos = self._find_uuid_box(heic_data, xmp_uuid, meta_box_pos)
            if uuid_box_pos != -1:
                # Update existing UUID box
                uuid_box_end = self._find_box_end(heic_data, b'uuid', uuid_box_pos)
                if uuid_box_end != -1:
                    new_uuid_box = self._create_uuid_box(xmp_uuid, xmp_bytes)
                    return (
                        heic_data[:uuid_box_pos] +
                        new_uuid_box +
                        heic_data[uuid_box_end:]
                    )
            
            # Add new XMP UUID box to meta box
            meta_box_end = self._find_box_end(heic_data, b'meta', meta_box_pos)
            if meta_box_end != -1:
                uuid_box = self._create_uuid_box(xmp_uuid, xmp_bytes)
                # Update meta box size
                meta_size = struct.unpack('>I', heic_data[meta_box_pos:meta_box_pos+4])[0]
                new_meta_size = meta_size + len(uuid_box)
                new_heic = (
                    heic_data[:meta_box_pos] +
                    struct.pack('>I', new_meta_size) +
                    heic_data[meta_box_pos+4:meta_box_end] +
                    uuid_box +
                    heic_data[meta_box_end:]
                )
                return new_heic
            
            # Fallback: append UUID box
            uuid_box = self._create_uuid_box(xmp_uuid, xmp_bytes)
            return heic_data + uuid_box
            
        except Exception as e:
            raise MetadataWriteError(f"Failed to write XMP box: {str(e)}")
    
    def _find_box(self, data: bytes, box_type: bytes, start_pos: int = 0) -> int:
        """Find box of given type in ISOBMFF data."""
        pos = start_pos
        while pos < len(data) - 8:
            if pos + 8 > len(data):
                break
            size = struct.unpack('>I', data[pos:pos+4])[0]
            box = data[pos+4:pos+8]
            if box == box_type:
                return pos
            if size == 0 or size > len(data) - pos:
                break
            pos += size
        return -1

    def _find_box_in_range(self, data: bytes, box_type: bytes, start_pos: int, end_pos: int) -> int:
        """Find box of given type within a bounded range."""
        pos = start_pos
        while pos + 8 <= end_pos:
            size = struct.unpack('>I', data[pos:pos+4])[0]
            box = data[pos+4:pos+8]
            if box == box_type:
                return pos
            if size == 0 or pos + size > end_pos:
                break
            pos += size
        return -1

    def _ensure_item_property_linkage(self, heic_data: bytes, exif_bytes: bytes) -> bytes:
        """
        Ensure iinf/iloc/idat construction and iprp/ipco/ipma linkage for EXIF.
        """
        meta_pos = self._find_box(heic_data, b'meta')
        if meta_pos == -1:
            return heic_data
        meta_end = self._find_box_end(heic_data, b'meta', meta_pos)
        if meta_end == -1 or meta_end <= meta_pos + 12:
            return heic_data

        version_flags = heic_data[meta_pos+8:meta_pos+12]
        meta_payload_start = meta_pos + 12

        pitm_pos = self._find_box_in_range(heic_data, b'pitm', meta_payload_start, meta_end)
        if pitm_pos == -1:
            return heic_data
        pitm_size = struct.unpack('>I', heic_data[pitm_pos:pitm_pos+4])[0]
        if pitm_size < 14 or pitm_pos + pitm_size > meta_end:
            return heic_data
        pitm_version = heic_data[pitm_pos+8]
        if pitm_version == 0:
            primary_item_id = struct.unpack('>H', heic_data[pitm_pos+12:pitm_pos+14])[0]
        elif pitm_version == 1:
            if pitm_pos + 16 > meta_end:
                return heic_data
            primary_item_id = struct.unpack('>I', heic_data[pitm_pos+12:pitm_pos+16])[0]
        else:
            return heic_data

        exif_prop = self._create_box(b'Exif', exif_bytes)

        # Gather existing meta child boxes.
        child_boxes = []
        pos = meta_payload_start
        while pos + 8 <= meta_end:
            size = struct.unpack('>I', heic_data[pos:pos+4])[0]
            if size < 8 or pos + size > meta_end:
                break
            child_boxes.append((heic_data[pos+4:pos+8], heic_data[pos:pos+size]))
            pos += size

        # Parse existing iinf to find max item ID.
        max_item_id = 0
        iinf_box = None
        for box_type, box_data in child_boxes:
            if box_type == b'iinf':
                iinf_box = box_data
                break

        def _parse_iinf_max_item_id(iinf_data: bytes) -> Tuple[int, Optional[int]]:
            if len(iinf_data) < 12:
                return 0, None
            version = iinf_data[8]
            if version == 2:
                if len(iinf_data) < 16:
                    return 0, version
                entry_count = struct.unpack('>I', iinf_data[12:16])[0]
                offset = 16
            else:
                if len(iinf_data) < 14:
                    return 0, version
                entry_count = struct.unpack('>H', iinf_data[12:14])[0]
                offset = 14
            max_id = 0
            for _ in range(entry_count):
                if offset + 8 > len(iinf_data):
                    break
                size = struct.unpack('>I', iinf_data[offset:offset+4])[0]
                if size < 8 or offset + size > len(iinf_data):
                    break
                if iinf_data[offset+4:offset+8] == b'infe' and offset + 12 <= len(iinf_data):
                    infe_version = iinf_data[offset+8]
                    if infe_version == 2 and offset + 16 <= len(iinf_data):
                        item_id = struct.unpack('>H', iinf_data[offset+12:offset+14])[0]
                        if item_id > max_id:
                            max_id = item_id
                offset += size
            return max_id, version

        max_item_id, iinf_version = _parse_iinf_max_item_id(iinf_box) if iinf_box else (0, None)
        exif_item_id = max_item_id + 1 if max_item_id else (primary_item_id + 1 if primary_item_id else 1)

        # Build Exif item info entry (infe v2).
        infe_payload = (
            b'\x02\x00\x00\x00' +  # version 2, flags 0
            struct.pack('>H', exif_item_id) +
            struct.pack('>H', 0) +
            b'Exif' +
            b'Exif\x00'
        )
        infe_box = self._create_box(b'infe', infe_payload)

        # Update or create iinf box.
        if iinf_box and iinf_version == 2:
            entry_count = struct.unpack('>I', iinf_box[12:16])[0]
            new_entry_count = entry_count + 1
            new_payload = iinf_box[8:12] + struct.pack('>I', new_entry_count) + iinf_box[16:] + infe_box
            new_iinf = self._create_box(b'iinf', new_payload)
        else:
            new_payload = b'\x02\x00\x00\x00' + struct.pack('>I', 1) + infe_box
            new_iinf = self._create_box(b'iinf', new_payload)

        # Build or update idat box and get offset within idat.
        idat_box = None
        idat_offset = 0
        for box_type, box_data in child_boxes:
            if box_type == b'idat':
                idat_box = box_data
                break
        if idat_box:
            idat_payload = idat_box[8:]
            idat_offset = len(idat_payload)
            idat_box = self._create_box(b'idat', idat_payload + exif_bytes)
        else:
            idat_box = self._create_box(b'idat', exif_bytes)
            idat_offset = 0

        # Update or create iloc box (version 1 with construction_method).
        def _encode_int(value: int, size: int) -> bytes:
            return value.to_bytes(size, 'big') if size > 0 else b''

        iloc_box = None
        iloc_version = None
        for box_type, box_data in child_boxes:
            if box_type == b'iloc':
                iloc_box = box_data
                iloc_version = box_data[8]
                break

        if iloc_box and iloc_version in (1, 2):
            offset_size = iloc_box[12] >> 4
            length_size = iloc_box[12] & 0x0F
            base_offset_size = iloc_box[13] >> 4
            index_size = iloc_box[13] & 0x0F
            if iloc_version == 1:
                item_count = struct.unpack('>H', iloc_box[14:16])[0]
                header_len = 16
            else:
                item_count = struct.unpack('>I', iloc_box[14:18])[0]
                header_len = 18

            entry_bytes = bytearray()
            entry_bytes.extend(struct.pack('>H', exif_item_id))
            entry_bytes.extend(struct.pack('>H', 1))  # construction_method=1 (idat)
            entry_bytes.extend(struct.pack('>H', 0))  # data_reference_index
            entry_bytes.extend(_encode_int(0, base_offset_size))
            entry_bytes.extend(struct.pack('>H', 1))  # extent_count
            if index_size:
                entry_bytes.extend(_encode_int(0, index_size))
            entry_bytes.extend(_encode_int(idat_offset, offset_size))
            entry_bytes.extend(_encode_int(len(exif_bytes), length_size))

            if iloc_version == 1:
                new_header = iloc_box[8:12] + bytes([iloc_box[12], iloc_box[13]]) + struct.pack('>H', item_count + 1)
                new_payload = new_header + iloc_box[header_len:] + bytes(entry_bytes)
            else:
                new_header = iloc_box[8:12] + bytes([iloc_box[12], iloc_box[13]]) + struct.pack('>I', item_count + 1)
                new_payload = new_header + iloc_box[header_len:] + bytes(entry_bytes)
            iloc_box = self._create_box(b'iloc', new_payload)
        else:
            offset_size = 4
            length_size = 4
            base_offset_size = 0
            index_size = 0
            header = b'\x01\x00\x00\x00' + bytes([(offset_size << 4) | length_size, (base_offset_size << 4) | index_size]) + struct.pack('>H', 1)
            entry_bytes = bytearray()
            entry_bytes.extend(struct.pack('>H', exif_item_id))
            entry_bytes.extend(struct.pack('>H', 1))  # construction_method=1 (idat)
            entry_bytes.extend(struct.pack('>H', 0))
            entry_bytes.extend(struct.pack('>H', 1))  # extent_count
            entry_bytes.extend(struct.pack('>I', idat_offset))
            entry_bytes.extend(struct.pack('>I', len(exif_bytes)))
            iloc_box = self._create_box(b'iloc', header + bytes(entry_bytes))
        exif_prop_index = None
        iprp_box = None
        for box_type, box_data in child_boxes:
            if box_type == b'iprp':
                iprp_box = box_data
                break

        def _parse_ipco_props(ipco_data: bytes) -> List[bytes]:
            props = []
            offset = 8
            while offset + 8 <= len(ipco_data):
                size = struct.unpack('>I', ipco_data[offset:offset+4])[0]
                if size < 8 or offset + size > len(ipco_data):
                    break
                props.append(ipco_data[offset:offset+size])
                offset += size
            return props

        ipco_props: List[bytes] = []
        ipma_payload = None
        if iprp_box:
            ipco_pos = self._find_box_in_range(iprp_box, b'ipco', 8, len(iprp_box))
            if ipco_pos != -1:
                ipco_size = struct.unpack('>I', iprp_box[ipco_pos:ipco_pos+4])[0]
                ipco_box = iprp_box[ipco_pos:ipco_pos+ipco_size]
                ipco_props = _parse_ipco_props(ipco_box)
            ipma_pos = self._find_box_in_range(iprp_box, b'ipma', 8, len(iprp_box))
            if ipma_pos != -1:
                ipma_size = struct.unpack('>I', iprp_box[ipma_pos:ipma_pos+4])[0]
                ipma_payload = iprp_box[ipma_pos+8:ipma_pos+ipma_size]

        # Find existing Exif property.
        for idx, prop in enumerate(ipco_props, start=1):
            if prop[4:8] == b'Exif':
                exif_prop_index = idx
                break
        if exif_prop_index is None:
            ipco_props.append(exif_prop)
            exif_prop_index = len(ipco_props)

        ipco_box = self._create_box(b'ipco', b''.join(ipco_props))

        # Build ipma box (version 0).
        ipma_entries = []
        if ipma_payload and len(ipma_payload) >= 6 and ipma_payload[0] == 0:
            item_count = struct.unpack('>H', ipma_payload[4:6])[0]
            offset = 6
            for _ in range(item_count):
                if offset + 3 > len(ipma_payload):
                    break
                item_id = struct.unpack('>H', ipma_payload[offset:offset+2])[0]
                assoc_count = ipma_payload[offset+2]
                offset += 3
                assoc_bytes = ipma_payload[offset:offset+assoc_count]
                offset += assoc_count
                ipma_entries.append((item_id, bytearray(assoc_bytes)))
        # Update/append association for Exif item.
        found_item = False
        for entry in ipma_entries:
            if entry[0] == exif_item_id:
                found_item = True
                if all((b & 0x7F) != exif_prop_index for b in entry[1]):
                    entry[1].append(exif_prop_index & 0x7F)
                break
        if not found_item:
            ipma_entries.append((exif_item_id, bytearray([exif_prop_index & 0x7F])))

        ipma_payload_bytes = bytearray()
        ipma_payload_bytes.extend(b'\x00\x00\x00\x00')  # version/flags
        ipma_payload_bytes.extend(struct.pack('>H', len(ipma_entries)))
        for entry in ipma_entries:
            ipma_payload_bytes.extend(struct.pack('>H', entry[0]))
            ipma_payload_bytes.append(len(entry[1]))
            ipma_payload_bytes.extend(entry[1])

        ipma_box = self._create_box(b'ipma', bytes(ipma_payload_bytes))
        iprp_box = self._create_box(b'iprp', ipco_box + ipma_box)

        # Rebuild meta box with updated iprp.
        new_children = []
        replaced = False
        for box_type, box_data in child_boxes:
            if box_type == b'iprp' and not replaced:
                new_children.append(iprp_box)
                replaced = True
            elif box_type == b'iinf':
                continue
            elif box_type == b'iloc':
                continue
            elif box_type == b'idat':
                continue
            else:
                new_children.append(box_data)
        if not replaced:
            new_children.append(iprp_box)
        new_children.append(new_iinf)
        new_children.append(iloc_box)
        new_children.append(idat_box)

        new_meta_payload = version_flags + b''.join(new_children)
        new_meta_box = self._create_box(b'meta', new_meta_payload)

        return heic_data[:meta_pos] + new_meta_box + heic_data[meta_end:]
    
    def _find_box_end(self, data: bytes, box_type: bytes, start_pos: int = 0) -> int:
        """Find end position of box."""
        box_pos = self._find_box(data, box_type, start_pos)
        if box_pos == -1:
            return -1
        size = struct.unpack('>I', data[box_pos:box_pos+4])[0]
        if size == 0:
            return len(data)
        return box_pos + size
    
    def _find_uuid_box(self, data: bytes, uuid: bytes, start_pos: int = 0) -> int:
        """Find UUID box with specific UUID."""
        pos = start_pos
        while pos < len(data) - 24:
            if pos + 24 > len(data):
                break
            size = struct.unpack('>I', data[pos:pos+4])[0]
            box = data[pos+4:pos+8]
            if box == b'uuid':
                box_uuid = data[pos+8:pos+24]
                if box_uuid == uuid:
                    return pos
            if size == 0 or size > len(data) - pos:
                break
            pos += size
        return -1
    
    def _create_box(self, box_type: bytes, data: bytes) -> bytes:
        """Create ISOBMFF box."""
        box_size = 8 + len(data)
        return struct.pack('>I', box_size) + box_type + data
    
    def _create_uuid_box(self, uuid: bytes, data: bytes) -> bytes:
        """Create UUID box."""
        box_size = 24 + len(data)
        return struct.pack('>I', box_size) + b'uuid' + uuid + data
