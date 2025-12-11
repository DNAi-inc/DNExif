# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Audio format metadata writer

This module handles writing metadata to audio files (MP3, WAV, FLAC, etc.).
Audio formats use various metadata standards (ID3, RIFF INFO, Vorbis comments).

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List
from pathlib import Path

from dnexif.exceptions import MetadataWriteError


def _build_ogg_crc_table() -> List[int]:
    """
    Build the lookup table used for Ogg CRC32 calculations.
    """
    poly = 0x04C11DB7
    table: List[int] = []
    for i in range(256):
        crc = i << 24
        for _ in range(8):
            if crc & 0x80000000:
                crc = ((crc << 1) ^ poly) & 0xFFFFFFFF
            else:
                crc = (crc << 1) & 0xFFFFFFFF
        table.append(crc)
    return table


OGG_CRC_TABLE = _build_ogg_crc_table()


class AudioWriter:
    """
    Writes metadata to audio files.
    
    Supports MP3 (ID3v2), WAV (RIFF INFO), FLAC (Vorbis comments), and other formats.
    """
    
    def __init__(self):
        """Initialize audio writer."""
        pass
    
    def write_audio(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to an audio file.
        
        Args:
            file_path: Path to original audio file
            metadata: Metadata dictionary to write
            output_path: Output file path
            
        Raises:
            MetadataWriteError: If writing fails
        """
        # Detect format from extension
        ext = Path(file_path).suffix.lower()
        
        if ext == '.mp3':
            self._write_mp3(file_path, metadata, output_path)
        elif ext == '.wav':
            self._write_wav(file_path, metadata, output_path)
        elif ext == '.flac':
            self._write_flac(file_path, metadata, output_path)
        elif ext in ('.aac', '.m4a'):
            # AAC/M4A files use MP4 container format, route to video writer
            from dnexif.video_writer import VideoWriter
            video_writer = VideoWriter()
            video_writer.write_video(file_path, metadata, output_path)
        elif ext in ('.ogg', '.opus'):
            self._write_ogg(file_path, metadata, output_path)
        elif ext == '.wma':
            self._write_wma(file_path, metadata, output_path)
        else:
            raise MetadataWriteError(f"Audio format '{ext}' writing not yet implemented")
    
    def _write_mp3(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to MP3 files using ID3v2 tags.
        
        ID3v2 tags are stored at the beginning of MP3 files.
        This requires preserving the audio stream and updating/adding ID3v2 frames.
        
        Args:
            file_path: Original audio file path
            metadata: Metadata dictionary
            output_path: Output file path
        """
        title_value = (
            metadata.get('XMP:Title')
            or metadata.get('Audio:MP3:Title')
            or metadata.get('Title')
        )
        
        if not title_value:
            raise MetadataWriteError("No supported MP3 metadata fields provided (expected XMP:Title)")
        
        with open(file_path, 'rb') as f:
            original_data = f.read()
        
        if len(original_data) < 10:
            raise MetadataWriteError("Invalid MP3 file")
        
        audio_payload = self._strip_existing_id3v2(original_data)
        
        # Build ID3v2.3 tag with TIT2 frame
        frame_payload = self._build_text_frame_payload(title_value)
        frame_body = b'TIT2' + struct.pack('>I', len(frame_payload)) + b'\x00\x00' + frame_payload
        tag_size = len(frame_body)
        tag_header = b'ID3' + bytes([3, 0, 0]) + self._int_to_synchsafe(tag_size)
        tag_data = tag_header + frame_body
        
        with open(output_path, 'wb') as f:
            f.write(tag_data + audio_payload)
    
    def _write_wav(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to WAV files using RIFF INFO (LIST) chunks.
        Currently maps `XMP:Title` / `Audio:WAV:Title` onto the `INAM` field.
        """
        title_value = (
            metadata.get('XMP:Title')
            or metadata.get('Audio:WAV:Title')
            or metadata.get('Title')
        )
        
        if not title_value:
            raise MetadataWriteError("No supported WAV metadata fields provided (expected XMP:Title)")
        
        with open(file_path, 'rb') as f:
            original_data = f.read()
        
        if len(original_data) < 12 or original_data[:4] != b'RIFF' or original_data[8:12] != b'WAVE':
            raise MetadataWriteError("Invalid WAV file (missing RIFF/WAVE headers)")
        
        # Build INFO entries
        def _build_info_entry(tag: bytes, value: str) -> bytes:
            text_bytes = value.encode('utf-8')
            if not text_bytes or text_bytes[-1] != 0:
                text_bytes += b'\x00'
            entry = tag + struct.pack('<I', len(text_bytes)) + text_bytes
            if len(text_bytes) % 2:
                entry += b'\x00'  # Pad to even length
            return entry
        
        info_entries = []
        info_entries.append(_build_info_entry(b'INAM', title_value))
        info_payload = b'INFO' + b''.join(info_entries)
        info_chunk = b'LIST' + struct.pack('<I', len(info_payload)) + info_payload
        if len(info_payload) % 2:
            info_chunk += b'\x00'
        
        # Rebuild RIFF chunks, removing any existing INFO LIST
        chunks = []
        offset = 12  # Skip RIFF header
        data_len = len(original_data)
        while offset + 8 <= data_len:
            chunk_id = original_data[offset:offset+4]
            chunk_size = struct.unpack('<I', original_data[offset+4:offset+8])[0]
            chunk_total = 8 + chunk_size
            if chunk_size % 2:
                chunk_total += 1  # Account for padding byte
            
            chunk_bytes = original_data[offset:offset+chunk_total]
            
            if chunk_id == b'LIST' and chunk_total >= 12:
                list_type = chunk_bytes[8:12]
                if list_type == b'INFO':
                    offset += chunk_total
                    continue  # Skip existing INFO chunk
            
            chunks.append(chunk_bytes)
            offset += chunk_total
        
        chunks.append(info_chunk)
        riff_body = b''.join(chunks)
        final_data = bytearray(12 + len(riff_body))
        final_data[:12] = original_data[:12]
        final_data[12:] = riff_body
        final_size = len(final_data) - 8
        final_data[4:8] = struct.pack('<I', final_size)
        
        with open(output_path, 'wb') as f:
            f.write(final_data)
    
    def _write_flac(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to FLAC files using Vorbis comments.
        
        FLAC files use Vorbis comment blocks for metadata.
        
        Args:
            file_path: Original audio file path
            metadata: Metadata dictionary
            output_path: Output file path
        """
        title_value = (
            metadata.get('XMP:Title')
            or metadata.get('Audio:FLAC:Title')
            or metadata.get('Title')
        )
        
        if not title_value:
            raise MetadataWriteError("No supported FLAC metadata fields provided (expected XMP:Title)")
        
        original_data = Path(file_path).read_bytes()
        if not original_data.startswith(b'fLaC'):
            raise MetadataWriteError("Invalid FLAC file")
        
        vorbis_block = self._build_vorbis_comment_block({'TITLE': title_value})
        
        # Parse metadata blocks
        offset = 4
        blocks = []
        audio_start = len(original_data)
        found = False
        
        while offset < len(original_data):
            header = original_data[offset]
            block_type = header & 0x7F
            is_last = bool(header & 0x80)
            block_length = int.from_bytes(original_data[offset + 1:offset + 4], 'big')
            block_data = original_data[offset + 4:offset + 4 + block_length]
            blocks.append((block_type, block_data))
            offset += 4 + block_length
            if is_last:
                audio_start = offset
                break
        
        new_blocks = []
        replaced = False
        for block_type, block_data in blocks:
            if block_type == 4 and not replaced:
                new_blocks.append((4, vorbis_block))
                replaced = True
            else:
                new_blocks.append((block_type, block_data))
        if not replaced:
            new_blocks.append((4, vorbis_block))
        
        rebuilt = bytearray(b'fLaC')
        for idx, (block_type, block_data) in enumerate(new_blocks):
            header = block_type & 0x7F
            if idx == len(new_blocks) - 1:
                header |= 0x80
            rebuilt.append(header)
            rebuilt.extend(len(block_data).to_bytes(3, 'big'))
            rebuilt.extend(block_data)
        
        rebuilt.extend(original_data[audio_start:])
        
        with open(output_path, 'wb') as f:
            f.write(rebuilt)
    
    def _write_aac_m4a(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to AAC/M4A files.
        
        AAC/M4A files use MP4-like atom structure.
        
        Args:
            file_path: Original audio file path
            metadata: Metadata dictionary
            output_path: Output file path
        """
        raise MetadataWriteError(
            "AAC/M4A writing requires MP4-like atom manipulation. "
            "This will be implemented in a future update."
        )
    
    def _write_ogg(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to OGG files using Vorbis comments.
        
        OGG files use Vorbis comment pages for metadata.
        
        Args:
            file_path: Original audio file path
            metadata: Metadata dictionary
            output_path: Output file path
        """
        title_value = (
            metadata.get('XMP:Title')
            or metadata.get('Audio:OGG:Title')
            or metadata.get('Audio:OPUS:Title')
            or metadata.get('Title')
        )
        
        if not title_value:
            raise MetadataWriteError("No supported OGG/Opus metadata fields provided (expected XMP:Title)")
        
        original_data = Path(file_path).read_bytes()
        if not original_data.startswith(b'OggS'):
            raise MetadataWriteError("Invalid OGG/Opus file (missing OggS capture pattern)")
        
        header_window = original_data[:4096]
        is_opus = b'OpusHead' in header_window or file_path.lower().endswith('.opus')
        signature = b'OpusTags' if is_opus else b'\x03vorbis'
        
        vorbis_block = self._build_vorbis_comment_block(
            {'TITLE': title_value},
            include_framing=not is_opus
        )
        comment_packet = signature + vorbis_block
        
        updated_data = self._replace_ogg_comment_page(original_data, signature, comment_packet)
        
        with open(output_path, 'wb') as f:
            f.write(updated_data)

    def _strip_existing_id3v2(self, data: bytes) -> bytes:
        """
        Remove existing ID3v2 tag (if present) and return the remaining audio payload.
        """
        if len(data) >= 10 and data.startswith(b'ID3'):
            tag_size = self._synchsafe_to_int(data[6:10])
            cutoff = 10 + tag_size
            if cutoff < len(data):
                return data[cutoff:]
        return data

    def _build_text_frame_payload(self, text: str) -> bytes:
        """
        Build ID3v2 text frame payload (ISO-8859-1 encoded, null terminated).
        """
        encoded = text.encode('latin-1', errors='replace')
        if not encoded or encoded[-1] != 0:
            encoded += b'\x00'
        return b'\x00' + encoded  # encoding byte 0 = ISO-8859-1 (ID3v2.3)

    @staticmethod
    def _int_to_synchsafe(value: int) -> bytes:
        """Convert integer to 4-byte synchsafe representation."""
        out = bytearray(4)
        for i in range(4):
            out[3 - i] = value & 0x7F
            value >>= 7
        return bytes(out)

    @staticmethod
    def _synchsafe_to_int(data: bytes) -> int:
        """Convert 4-byte synchsafe integer to int."""
        value = 0
        for byte in data:
            value = (value << 7) | (byte & 0x7F)
        return value

    @staticmethod
    def _build_vorbis_comment_block(
        fields: Dict[str, str],
        include_framing: bool = False
    ) -> bytes:
        """
        Build a Vorbis comment block given a dict of key/value pairs.
        
        Args:
            fields: Mapping of KEY -> value pairs to encode
            include_framing: Append Vorbis framing bit (0x01). Required for
                Ogg Vorbis comment packets, but omitted for FLAC/Opus.
        """
        vendor = b'DNExif'
        comments = []
        for key, value in fields.items():
            comments.append(f"{key}={value}".encode('utf-8'))
        
        blob = bytearray()
        blob.extend(len(vendor).to_bytes(4, 'little'))
        blob.extend(vendor)
        blob.extend(len(comments).to_bytes(4, 'little'))
        for comment in comments:
            blob.extend(len(comment).to_bytes(4, 'little'))
            blob.extend(comment)
        
        if include_framing:
            blob.append(1)  # Vorbis framing bit
        return bytes(blob)

    @staticmethod
    def _build_ogg_lacing(packet_data: bytes) -> List[int]:
        """
        Build Ogg lacing values for the provided packet data.
        """
        if not packet_data:
            return [0]
        
        lacing: List[int] = []
        idx = 0
        remaining = len(packet_data)
        while remaining > 0:
            chunk = min(255, remaining)
            lacing.append(chunk)
            idx += chunk
            remaining -= chunk
        if lacing[-1] == 255:
            lacing.append(0)
        return lacing

    @staticmethod
    def _compute_ogg_crc(page_bytes: bytes) -> int:
        """
        Compute the Ogg CRC32 checksum for a full page.
        """
        crc = 0
        for byte in page_bytes:
            index = ((crc >> 24) & 0xFF) ^ byte
            crc = ((crc << 8) & 0xFFFFFFFF) ^ OGG_CRC_TABLE[index]
        return crc & 0xFFFFFFFF

    def _replace_ogg_comment_page(self, data: bytes, signature: bytes, comment_packet: bytes) -> bytes:
        """
        Replace the Vorbis/Opus comment packet page with updated metadata.
        """
        offset = 0
        data_len = len(data)
        
        while offset + 27 <= data_len:
            if data[offset:offset+4] != b'OggS':
                break
            
            header = bytearray(data[offset:offset+27])
            seg_count = header[26]
            seg_table_start = offset + 27
            seg_table_end = seg_table_start + seg_count
            if seg_table_end > data_len:
                break
            lacing_vals = list(data[seg_table_start:seg_table_end])
            payload_len = sum(lacing_vals)
            payload_start = seg_table_end
            payload_end = payload_start + payload_len
            if payload_end > data_len:
                break
            payload = data[payload_start:payload_end]
            
            if payload.startswith(signature):
                # Determine how many lacing entries belong to the comment packet
                comment_seg_count = 0
                comment_payload_len = 0
                found_end = False
                for val in lacing_vals:
                    comment_seg_count += 1
                    comment_payload_len += val
                    if val < 255:
                        found_end = True
                        break
                if not found_end:
                    raise MetadataWriteError("Vorbis comment packet spans multiple pages; cannot update safely")
                
                remainder_lacing = lacing_vals[comment_seg_count:]
                remainder_payload = payload[comment_payload_len:]
                
                new_lacing = self._build_ogg_lacing(comment_packet)
                if len(new_lacing) + len(remainder_lacing) > 255:
                    raise MetadataWriteError("Updated Vorbis comment page exceeds segment limit")
                new_lacing += remainder_lacing
                
                if len(remainder_payload) != sum(remainder_lacing):
                    # Safety check to avoid corrupting setup packet
                    raise MetadataWriteError("Unexpected OGG layout; aborting comment rewrite")
                
                new_payload = comment_packet + remainder_payload
                
                header[26] = len(new_lacing)
                header[22:26] = b'\x00\x00\x00\x00'
                
                segment_table = bytes(new_lacing)
                rebuilt_page = bytes(header) + segment_table + new_payload
                crc = self._compute_ogg_crc(rebuilt_page)
                header[22:26] = crc.to_bytes(4, 'little')
                rebuilt_page = bytes(header) + segment_table + new_payload
                
                return data[:offset] + rebuilt_page + data[payload_end:]
            
            offset = payload_end
        
        raise MetadataWriteError("Could not locate Vorbis/Opus comment packet in OGG stream")
    
    def _write_wma(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        output_path: str
    ) -> None:
        """
        Write metadata to WMA files using ASF Content Description Object.
        
        WMA files use ASF (Advanced Systems Format) container.
        Content Description Object GUID: 75B22630-668E-11CF-A6D9-00AA0062CE6C
        
        Args:
            file_path: Original WMA file path
            metadata: Metadata dictionary
            output_path: Output file path
        """
        title_value = (
            metadata.get('XMP:Title')
            or metadata.get('Audio:WMA:Title')
            or metadata.get('Title')
        )
        
        if not title_value:
            raise MetadataWriteError("No supported WMA metadata fields provided (expected XMP:Title)")
        
        try:
            with open(file_path, 'rb') as f:
                original_data = f.read()
            
            # Verify ASF Header Object
            asf_header_guid = bytes.fromhex('3026b2758e66cf11a6d900aa0062ce6c')
            if len(original_data) < 16 or original_data[:16] != asf_header_guid:
                raise MetadataWriteError("Invalid WMA/ASF file (missing ASF header)")
            
            # Extended Content Description Object GUID: 40A4D0D2-07E3-D211-97F0-00A0C95EA850
            # Stored as: 40 A4 D0 D2 07 E3 D2 11 97 F0 00 A0 C9 5E A8 50 (big-endian)
            ext_content_desc_guid = bytes.fromhex('40a4d0d207e3d21197f000a0c95ea850')
            
            # Build Extended Content Description Object payload
            # Structure: Descriptor Count (2 bytes) + Descriptors
            # Each Descriptor: Name Length (2) + Name (UTF-16LE) + Value Type (2) + Value Length (2) + Value (UTF-16LE)
            if isinstance(title_value, bytes):
                title_bytes = title_value
            else:
                title_bytes = str(title_value).encode('utf-16-le')
            # Use standard ASF tag name "WM/Title"
            name_bytes = 'WM/Title'.encode('utf-16-le')
            
            # Build descriptor: Name Length + Name + Value Type (0=Unicode) + Value Length + Value
            descriptor = struct.pack('<H', len(name_bytes)) + name_bytes
            descriptor += struct.pack('<H', 0)  # Value type: Unicode string
            descriptor += struct.pack('<H', len(title_bytes)) + title_bytes
            
            # Build payload: Descriptor Count (1) + Descriptor
            payload = struct.pack('<H', 1) + descriptor
            
            # Extended Content Description Object: GUID (16 bytes) + Size (8 bytes) + Payload
            obj_size = 24 + len(payload)
            ext_content_desc_obj = ext_content_desc_guid + struct.pack('<Q', obj_size) + payload
            
            # Find and replace existing Content Description Object, or insert it
            # ASF structure: Header Object + other objects
            # We'll search for the Content Description Object and replace it
            offset = 0
            data_len = len(original_data)
            found = False
            new_data = bytearray()
            
            while offset + 24 <= data_len:
                # Check for Extended Content Description Object GUID
                if original_data[offset:offset+16] == ext_content_desc_guid:
                    # Found existing Extended Content Description Object
                    obj_size_old = struct.unpack('<Q', original_data[offset+16:offset+24])[0]
                    # Replace it
                    new_data.extend(original_data[:offset])
                    new_data.extend(ext_content_desc_obj)
                    new_data.extend(original_data[offset+obj_size_old:])
                    found = True
                    break
                
                # Check if this is an ASF object (has GUID + size)
                # Try to read size
                try:
                    obj_size_check = struct.unpack('<Q', original_data[offset+16:offset+24])[0]
                    if obj_size_check < 24 or offset + obj_size_check > data_len:
                        # Not a valid object, move forward
                        offset += 1
                        continue
                    # Valid object, skip it
                    offset += obj_size_check
                except Exception:
                    offset += 1
            
            if not found:
                # Extended Content Description Object not found, insert it after Header Object
                # Header Object size is at offset 16 (8 bytes, little-endian)
                if len(original_data) >= 24:
                    header_size = struct.unpack('<Q', original_data[16:24])[0]
                    # Insert after Header Object
                    new_data = bytearray(original_data[:header_size])
                    new_data.extend(ext_content_desc_obj)
                    new_data.extend(original_data[header_size:])
                    # Update Header Object size to include new object
                    new_header_size = header_size + len(ext_content_desc_obj)
                    new_data[16:24] = struct.pack('<Q', new_header_size)
                else:
                    raise MetadataWriteError("Invalid ASF file structure")
            
            with open(output_path, 'wb') as f:
                f.write(new_data)
                
        except Exception as e:
            if isinstance(e, MetadataWriteError):
                raise
            raise MetadataWriteError(f"Failed to write WMA file: {str(e)}")

