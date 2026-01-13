# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Audio format metadata parser

This module provides metadata parsing for audio formats like MP3, WAV, FLAC
which can contain ID3 tags, RIFF chunks, and other metadata.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path
from dnexif.exceptions import MetadataReadError


class AudioParser:
    """
    Audio format metadata parser.
    
    Supports MP3 (ID3 tags), WAV (RIFF chunks), FLAC (Vorbis comments).
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize audio parser.
        
        Args:
            file_path: Path to audio file
            file_data: Raw file data
        """
        self.file_path = file_path
        self.file_data = file_data
        self.metadata: Dict[str, Any] = {}
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse audio file metadata.
        
        Returns:
            Dictionary containing all extracted metadata
        """
        if not self.file_data and self.file_path:
            with open(self.file_path, 'rb') as f:
                # For FLAC files, we need to read enough to get STREAMINFO and Vorbis comment blocks
                # STREAMINFO is 34 bytes, Vorbis comments can be larger, so read more
                self.file_data = f.read(65536)  # Read first 64KB for metadata (FLAC blocks are usually in first few KB)
        
        if not self.file_data:
            return {}
        
        metadata = {}
        
        # Detect format
        format_type = self._detect_format()
        if not format_type:
            return metadata
        
        # Parse based on format
        if format_type == 'MP3':
            metadata.update(self._parse_mp3())
        elif format_type == 'WAV':
            metadata.update(self._parse_wav())
        elif format_type == 'FLAC':
            metadata.update(self._parse_flac())
        elif format_type == 'OGG':
            metadata.update(self._parse_ogg_vorbis())
        elif format_type == 'OPUS':
            metadata.update(self._parse_opus())
        elif format_type == 'WMA':
            metadata.update(self._parse_wma())
        elif format_type == 'DSF':
            metadata.update(self._parse_dsf())
        elif format_type == 'AAC':
            metadata.update(self._parse_aac())
        
        return metadata
    
    def _detect_format(self) -> Optional[str]:
        """Detect audio format."""
        if not self.file_data:
            return None
        
        # MP3 with ID3 tag
        if self.file_data.startswith(b'ID3'):
            return 'MP3'
        
        # MP3 with frame sync
        if len(self.file_data) >= 2:
            if self.file_data[0:2] in (b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'):
                return 'MP3'
        
        # WAV (RIFF)
        if self.file_data.startswith(b'RIFF') and b'WAVE' in self.file_data[:12]:
            return 'WAV'
        
        # FLAC
        if self.file_data.startswith(b'fLaC'):
            return 'FLAC'
        
        # OGG/Opus
        if self.file_data.startswith(b'OggS'):
            window = self.file_data[:4096]
            if b'OpusHead' in window or (self.file_path and Path(self.file_path).suffix.lower() == '.opus'):
                return 'OPUS'
            return 'OGG'
        
        # WMA (ASF) - Header Object GUID: 75B22630-668E-11CF-A6D9-00AA0062CE6C
        # Stored as: 3026B275-8E66-CF11-A6D9-00AA0062CE6C (little-endian)
        if len(self.file_data) >= 16:
            asf_header_guid = bytes.fromhex('3026b2758e66cf11a6d900aa0062ce6c')
            if self.file_data[:16] == asf_header_guid:
                return 'WMA'
        
        # Check extension
        if self.file_path:
            ext = Path(self.file_path).suffix.lower()
            if ext == '.mp3':
                return 'MP3'
            elif ext == '.wav':
                return 'WAV'
            elif ext == '.flac':
                return 'FLAC'
            elif ext == '.aac':
                return 'AAC'
            elif ext == '.ogg':
                return 'OGG'
            elif ext == '.opus':
                return 'OPUS'
            elif ext == '.m4a':
                return 'M4A'
            elif ext == '.wma':
                return 'WMA'
            elif ext == '.dsf':
                return 'DSF'
        
        # DSF (DSD Stream File) - starts with "DSD "
        if len(self.file_data) >= 4 and self.file_data[:4] == b'DSD ':
            return 'DSF'
        
        # Check file signatures
        if len(self.file_data) >= 4:
            # OGG files start with 'OggS'
            if self.file_data.startswith(b'OggS'):
                window = self.file_data[:4096]
                if b'OpusHead' in window:
                    return 'OPUS'
                return 'OGG'
            # AAC files may have ADIF or ADTS headers
            elif self.file_data.startswith(b'ADIF'):
                return 'AAC'
            # ADTS (Audio Data Transport Stream) - starts with sync word 0xFFF
            elif len(self.file_data) >= 2:
                if self.file_data[0] == 0xFF and (self.file_data[1] & 0xF0) == 0xF0:
                    # Check if it's ADTS (MPEG-4 AAC) - sync word 0xFFF, then 4 bits for ID, layer, protection
                    # ADTS frame header: sync word (12 bits) = 0xFFF
                    if (self.file_data[1] & 0xF6) == 0xF0:  # Check sync word pattern
                        return 'AAC'
            # M4A files start with 'ftyp' atom
            elif len(self.file_data) >= 8 and self.file_data[4:8] == b'ftyp':
                if b'M4A ' in self.file_data[8:20]:
                    return 'M4A'
        
        return None
    
    def _parse_mp3(self) -> Dict[str, Any]:
        """Parse MP3 ID3 tags with value extraction."""
        metadata = {}
        
        try:
            if not self.file_data:
                return metadata
            
            # ID3v2 tags at the beginning
            if self.file_data.startswith(b'ID3'):
                metadata['Audio:MP3:HasID3v2'] = True
                # ID3v2 header: 'ID3' + version (2 bytes) + flags (1 byte) + size (4 bytes)
                if len(self.file_data) >= 10:
                    version_major = self.file_data[3]
                    version_minor = self.file_data[4]
                    metadata['Audio:MP3:ID3v2Version'] = f"{version_major}.{version_minor}"
                    
                    # Parse synchsafe integer for tag size
                    size_bytes = self.file_data[6:10]
                    tag_size = (size_bytes[0] << 21) | (size_bytes[1] << 14) | (size_bytes[2] << 7) | size_bytes[3]
                    metadata['Audio:MP3:ID3v2Size'] = tag_size
                    # Standard format shows File:ID3Size (total ID3 tag size including header)
                    metadata['File:ID3Size'] = tag_size + 10  # Include 10-byte header
                    
                    # Parse ID3v2 frames (tags)
                    frame_offset = 10
                    while frame_offset < min(10 + tag_size, len(self.file_data) - 10):
                        if frame_offset + 10 > len(self.file_data):
                            break
                        
                        # Frame header: 4-byte ID, 4-byte size, 2-byte flags
                        frame_id = self.file_data[frame_offset:frame_offset+4]
                        frame_size = struct.unpack('>I', self.file_data[frame_offset+4:frame_offset+8])[0]
                        
                        # Common ID3v2 frame IDs
                        if frame_id == b'TIT2':  # Title
                            try:
                                # Skip encoding byte, read text
                                text = self.file_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-8', errors='ignore').strip('\x00')
                                if text:
                                    metadata['Audio:MP3:Title'] = text
                                    metadata.setdefault('XMP:Title', text)
                            except Exception:
                                pass
                        elif frame_id == b'TPE1':  # Artist
                            try:
                                text = self.file_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-8', errors='ignore').strip('\x00')
                                if text:
                                    metadata['Audio:MP3:Artist'] = text
                            except Exception:
                                pass
                        elif frame_id == b'TALB':  # Album
                            try:
                                text = self.file_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-8', errors='ignore').strip('\x00')
                                if text:
                                    metadata['Audio:MP3:Album'] = text
                            except Exception:
                                pass
                        elif frame_id == b'TYER' or frame_id == b'TDRC':  # Year/Date
                            try:
                                text = self.file_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-8', errors='ignore').strip('\x00')
                                if text:
                                    metadata['Audio:MP3:Year'] = text
                            except Exception:
                                pass
                        elif frame_id == b'TENC':  # Encoder
                            try:
                                # Skip encoding byte, read text
                                if frame_offset + 11 <= len(self.file_data):
                                    encoding_byte = self.file_data[frame_offset+10]
                                    # Encoding: 0 = ISO-8859-1, 1 = UTF-16 with BOM, 2 = UTF-16BE, 3 = UTF-8
                                    if encoding_byte == 0:  # ISO-8859-1
                                        text = self.file_data[frame_offset+11:frame_offset+10+frame_size].decode('latin-1', errors='ignore').strip('\x00')
                                    elif encoding_byte == 1:  # UTF-16 with BOM
                                        text = self.file_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-16', errors='ignore').strip('\x00')
                                    elif encoding_byte == 2:  # UTF-16BE
                                        text = self.file_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-16-be', errors='ignore').strip('\x00')
                                    elif encoding_byte == 3:  # UTF-8
                                        text = self.file_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-8', errors='ignore').strip('\x00')
                                    else:
                                        # Default to UTF-8
                                        text = self.file_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-8', errors='ignore').strip('\x00')
                                    if text:
                                        metadata['Audio:MP3:Encoder'] = text
                                        metadata['ID3:Encoder'] = text
                            except Exception:
                                pass
                        elif frame_id == b'TSSE':  # Software/Hardware and settings used for encoding
                            try:
                                # Skip encoding byte, read text
                                if frame_offset + 11 <= len(self.file_data):
                                    encoding_byte = self.file_data[frame_offset+10]
                                    # Encoding: 0 = ISO-8859-1, 1 = UTF-16 with BOM, 2 = UTF-16BE, 3 = UTF-8
                                    if encoding_byte == 0:  # ISO-8859-1
                                        text = self.file_data[frame_offset+11:frame_offset+10+frame_size].decode('latin-1', errors='ignore').strip('\x00')
                                    elif encoding_byte == 1:  # UTF-16 with BOM
                                        text = self.file_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-16', errors='ignore').strip('\x00')
                                    elif encoding_byte == 2:  # UTF-16BE
                                        text = self.file_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-16-be', errors='ignore').strip('\x00')
                                    elif encoding_byte == 3:  # UTF-8
                                        text = self.file_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-8', errors='ignore').strip('\x00')
                                    else:
                                        # Default to UTF-8
                                        text = self.file_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-8', errors='ignore').strip('\x00')
                                    if text:
                                        metadata['Audio:MP3:EncoderSettings'] = text
                                        metadata['ID3:EncoderSettings'] = text
                            except Exception:
                                pass
                        
                        frame_offset += 10 + frame_size
                        
                        # Stop if we hit padding or invalid frame
                        if frame_id == b'\x00\x00\x00\x00':
                            break
            
            metadata['Audio:MP3:Format'] = 'MP3'
            
            # Parse MPEG audio frame header
            # MPEG frame sync starts with 0xFF, followed by sync bits and header
            # Look for MPEG frame sync pattern (0xFF followed by 0xE0-0xFF)
            mpeg_offset = 0
            id3_tag_size = 0
            if self.file_data.startswith(b'ID3'):
                # Skip ID3v2 tag
                if len(self.file_data) >= 10:
                    size_bytes = self.file_data[6:10]
                    id3_tag_size = (size_bytes[0] << 21) | (size_bytes[1] << 14) | (size_bytes[2] << 7) | size_bytes[3]
                    mpeg_offset = 10 + id3_tag_size
            
            # Search for MPEG frame sync (0xFF followed by 0xE0-0xFF)
            bitrate_kbps = None
            while mpeg_offset < len(self.file_data) - 4:
                if self.file_data[mpeg_offset] == 0xFF and (self.file_data[mpeg_offset + 1] & 0xE0) == 0xE0:
                    # Found potential MPEG frame sync
                    header_bytes = self.file_data[mpeg_offset:mpeg_offset + 4]
                    if len(header_bytes) >= 4:
                        # Parse MPEG header
                        mpeg_metadata = self._parse_mpeg_header(header_bytes)
                        if mpeg_metadata:
                            metadata.update(mpeg_metadata)
                            # Extract bitrate for duration calculation
                            bitrate_str = mpeg_metadata.get('Audio:MP3:AudioBitrate', '')
                            if bitrate_str and ' kbps' in bitrate_str:
                                try:
                                    bitrate_kbps = int(bitrate_str.replace(' kbps', ''))
                                except ValueError:
                                    pass
                            break
                mpeg_offset += 1
            
            # Calculate duration from file size and bitrate
            if bitrate_kbps and self.file_path:
                try:
                    import os
                    file_size = os.path.getsize(self.file_path)
                    # Subtract ID3 tag size from file size to get audio data size
                    audio_data_size = file_size - id3_tag_size
                    if audio_data_size > 0 and bitrate_kbps > 0:
                        # Duration = (audio_data_size * 8) / (bitrate_kbps * 1000)
                        duration_seconds = (audio_data_size * 8) / (bitrate_kbps * 1000)
                        if duration_seconds > 0:
                            # Format duration similar to standard format (add "(approx)" suffix for MP3)
                            if duration_seconds >= 60:
                                hours = int(duration_seconds // 3600)
                                minutes = int((duration_seconds % 3600) // 60)
                                secs = int(duration_seconds % 60)
                                duration_str = f"{hours}:{minutes:02d}:{secs:02d} (approx)"
                            elif duration_seconds == 0:
                                duration_str = "0 s"
                            else:
                                duration_str = f"{duration_seconds:.2f} s (approx)"
                            
                            metadata['Audio:MP3:Duration'] = duration_str
                            metadata['MP3:Duration'] = duration_str  # For Composite:Duration lookup
                            metadata['Composite:Duration'] = duration_str  # Set Composite:Duration directly
                except (OSError, ValueError, TypeError):
                    pass
            
        except Exception:
            pass
        
        # Parse Lyrics3 metadata (stored at end of file, before ID3v1 tag)
        try:
            from dnexif.lyrics3_parser import Lyrics3Parser
            lyrics3_parser = Lyrics3Parser(file_path=str(self.file_path) if self.file_path else None, file_data=self.file_data)
            lyrics3_metadata = lyrics3_parser.parse()
            if lyrics3_metadata:
                metadata.update(lyrics3_metadata)
        except Exception:
            pass  # Lyrics3 is optional metadata
        
        return metadata
    
    def _parse_mpeg_header(self, header: bytes) -> Dict[str, Any]:
        """
        Parse MPEG audio frame header.
        
        Args:
            header: 4-byte MPEG frame header
            
        Returns:
            Dictionary of MPEG metadata
        """
        metadata = {}
        
        try:
            if len(header) < 4:
                return metadata
            
            # Byte 0: 0xFF (sync)
            # Byte 1: Sync bits (0xE0-0xFF) + MPEG version + Layer
            sync_byte1 = header[1]
            
            # MPEG Version (bits 3-4)
            mpeg_version_bits = (sync_byte1 >> 3) & 0x03
            mpeg_version_map = {
                0: '2.5',
                2: '2',
                3: '1'
            }
            mpeg_version = mpeg_version_map.get(mpeg_version_bits, 'Unknown')
            metadata['Audio:MP3:MPEGAudioVersion'] = mpeg_version
            # Standard format shows MPEG version as integer (1, 2, or 2.5)
            if mpeg_version == '1':
                metadata['MPEG:MPEGAudioVersion'] = 1
            elif mpeg_version == '2':
                metadata['MPEG:MPEGAudioVersion'] = 2
            elif mpeg_version == '2.5':
                metadata['MPEG:MPEGAudioVersion'] = 2.5
            
            # Layer (bits 1-2)
            layer_bits = (sync_byte1 >> 1) & 0x03
            layer_map = {
                1: 'III',
                2: 'II',
                3: 'I'
            }
            layer = layer_map.get(layer_bits, 'Unknown')
            metadata['Audio:MP3:AudioLayer'] = layer
            # Standard format shows AudioLayer as integer (1, 2, or 3)
            if layer == 'I':
                metadata['MPEG:AudioLayer'] = 1
            elif layer == 'II':
                metadata['MPEG:AudioLayer'] = 2
            elif layer == 'III':
                metadata['MPEG:AudioLayer'] = 3
            
            # Byte 2: Bitrate index + Sample rate index + Padding + Private
            byte2 = header[2]
            
            # Bitrate index (bits 4-7)
            bitrate_index = (byte2 >> 4) & 0x0F
            
            # Sample rate index (bits 2-3)
            sample_rate_index = (byte2 >> 2) & 0x03
            
            # Padding bit (bit 1)
            padding = (byte2 >> 1) & 0x01
            metadata['Audio:MP3:HasPadding'] = bool(padding)
            
            # Byte 3: Channel mode + Mode extension + Copyright + Original + Emphasis
            byte3 = header[3]
            
            # Channel mode (bits 6-7)
            channel_mode_bits = (byte3 >> 6) & 0x03
            channel_mode_map = {
                0: 'Stereo',
                1: 'Joint Stereo',
                2: 'Dual Channel',
                3: 'Mono'
            }
            channel_mode = channel_mode_map.get(channel_mode_bits, 'Unknown')
            metadata['Audio:MP3:ChannelMode'] = channel_mode
            metadata['MPEG:ChannelMode'] = channel_mode
            
            # Mode extension (bits 4-5) - only for Joint Stereo
            if channel_mode_bits == 1:
                mode_ext_bits = (byte3 >> 4) & 0x03
                # MSStereo and IntensityStereo flags
                mss = (mode_ext_bits >> 1) & 0x01
                intensity = mode_ext_bits & 0x01
                metadata['Audio:MP3:MSStereo'] = bool(mss)
                metadata['Audio:MP3:IntensityStereo'] = bool(intensity)
                # Standard format shows "Off" for false, "On" for true
                metadata['MPEG:MSStereo'] = 'On' if mss else 'Off'
                metadata['MPEG:IntensityStereo'] = 'On' if intensity else 'Off'
            else:
                # MSStereo is only for Joint Stereo mode
                metadata['MPEG:MSStereo'] = 'Off'
                metadata['MPEG:IntensityStereo'] = 'Off'
            
            # Copyright bit (bit 3)
            copyright = (byte3 >> 3) & 0x01
            metadata['Audio:MP3:Copyright'] = bool(copyright)
            metadata['MPEG:CopyrightFlag'] = bool(copyright)
            
            # Original bit (bit 2)
            original = (byte3 >> 2) & 0x01
            metadata['Audio:MP3:OriginalMedia'] = bool(original)
            metadata['MPEG:OriginalMedia'] = bool(original)
            
            # Emphasis (bits 0-1)
            emphasis_bits = byte3 & 0x03
            emphasis_map = {
                0: 'None',
                1: '50/15 ms',
                2: 'Reserved',
                3: 'CCIT J.17'
            }
            emphasis = emphasis_map.get(emphasis_bits, 'Unknown')
            metadata['Audio:MP3:Emphasis'] = emphasis
            metadata['MPEG:Emphasis'] = emphasis
            
            # IntensityStereo (only for Joint Stereo)
            if channel_mode_bits == 1:
                mode_ext_bits = (byte3 >> 4) & 0x03
                intensity = mode_ext_bits & 0x01
                metadata['Audio:MP3:IntensityStereo'] = bool(intensity)
                metadata['MPEG:IntensityStereo'] = bool(intensity)
            
            # Calculate bitrate (kbps) - depends on version, layer, and bitrate index
            bitrate = self._get_mpeg_bitrate(mpeg_version_bits, layer_bits, bitrate_index)
            if bitrate:
                metadata['Audio:MP3:AudioBitrate'] = f"{bitrate} kbps"
                metadata['MPEG:AudioBitrate'] = f"{bitrate} kbps"
            
            # Calculate sample rate (Hz) - depends on version and sample rate index
            sample_rate = self._get_mpeg_sample_rate(mpeg_version_bits, sample_rate_index)
            if sample_rate:
                metadata['Audio:MP3:SampleRate'] = f"{sample_rate} Hz"
                metadata['MPEG:SampleRate'] = sample_rate  # Standard format shows as integer
            
        except Exception:
            pass
        
        return metadata
    
    def _get_mpeg_bitrate(self, version: int, layer: int, index: int) -> Optional[int]:
        """Get MPEG bitrate from index."""
        # MPEG 1 Layer III (most common)
        if version == 3 and layer == 1:
            bitrates = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
        # MPEG 1 Layer II
        elif version == 3 and layer == 2:
            bitrates = [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0]
        # MPEG 2/2.5 Layer III
        elif version in (2, 0) and layer == 1:
            bitrates = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]
        else:
            return None
        
        if 0 <= index < len(bitrates):
            return bitrates[index]
        return None
    
    def _get_mpeg_sample_rate(self, version: int, index: int) -> Optional[int]:
        """Get MPEG sample rate from index."""
        # MPEG 1
        if version == 3:
            sample_rates = [44100, 48000, 32000, 0]
        # MPEG 2
        elif version == 2:
            sample_rates = [22050, 24000, 16000, 0]
        # MPEG 2.5
        elif version == 0:
            sample_rates = [11025, 12000, 8000, 0]
        else:
            return None
        
        if 0 <= index < len(sample_rates):
            return sample_rates[index]
        return None
    
    def _parse_wav(self) -> Dict[str, Any]:
        """Parse WAV RIFF chunks with metadata extraction."""
        metadata = {}
        
        try:
            wav_data = self.file_data
            if self.file_path:
                with open(self.file_path, 'rb') as f:
                    wav_data = f.read()
                    self.file_data = wav_data
            
            if not wav_data:
                return metadata
            
            # WAV files have RIFF structure
            if wav_data.startswith(b'RIFF'):
                metadata['Audio:WAV:Format'] = 'WAV'
                metadata['Audio:WAV:IsRIFF'] = True
                
                # Parse RIFF chunks
                offset = 12  # Skip 'RIFF' header (RIFF + size + 'WAVE')
                while offset < len(wav_data) - 8:
                    if offset + 8 > len(wav_data):
                        break
                    
                    chunk_id = wav_data[offset:offset+4]
                    chunk_size = struct.unpack('<I', wav_data[offset+4:offset+8])[0]
                    
                    if chunk_id == b'fmt ':
                        # Format chunk - contains audio format information
                        if offset + 8 + chunk_size <= len(wav_data) and chunk_size >= 16:
                            fmt_data = wav_data[offset+8:offset+8+chunk_size]
                            
                            # Audio format (2 bytes) - 1 = PCM, 3 = IEEE float, etc.
                            audio_format = struct.unpack('<H', fmt_data[0:2])[0]
                            format_map = {
                                1: 'PCM',
                                3: 'IEEE Float',
                                6: 'A-law',
                                7: 'μ-law',
                                17: 'ADPCM',
                                85: 'MP3'
                            }
                            encoding = format_map.get(audio_format, f'Format {audio_format}')
                            # Standard format shows "Microsoft PCM" for format 1, "PCM" for others
                            if audio_format == 1:
                                encoding_standard_format = 'Microsoft PCM'
                            else:
                                encoding_standard_format = encoding
                            metadata['Audio:WAV:Encoding'] = encoding
                            metadata['RIFF:Encoding'] = encoding_standard_format
                            
                            # Number of channels (2 bytes)
                            num_channels = struct.unpack('<H', fmt_data[2:4])[0]
                            metadata['Audio:WAV:NumChannels'] = num_channels
                            metadata['RIFF:NumChannels'] = num_channels
                            
                            # Sample rate (4 bytes)
                            sample_rate = struct.unpack('<I', fmt_data[4:8])[0]
                            metadata['Audio:WAV:SampleRate'] = f"{sample_rate} Hz"
                            metadata['RIFF:SampleRate'] = sample_rate  # Standard format shows as integer, not "Hz"
                            
                            # Average bytes per second (4 bytes)
                            avg_bytes_per_sec = struct.unpack('<I', fmt_data[8:12])[0]
                            metadata['Audio:WAV:AvgBytesPerSec'] = avg_bytes_per_sec
                            metadata['RIFF:AvgBytesPerSec'] = avg_bytes_per_sec
                            
                            # Block align (2 bytes)
                            block_align = struct.unpack('<H', fmt_data[12:14])[0]
                            metadata['Audio:WAV:BlockAlign'] = block_align
                            
                            # Bits per sample (2 bytes) - at offset 14-16, so need at least 16 bytes
                            if chunk_size >= 16 and len(fmt_data) >= 16:
                                bits_per_sample = struct.unpack('<H', fmt_data[14:16])[0]
                                metadata['Audio:WAV:BitsPerSample'] = bits_per_sample
                                metadata['RIFF:BitsPerSample'] = bits_per_sample
                    
                    elif chunk_id == b'LIST':
                        # LIST chunk - check for INFO or guano
                        if offset + 12 < len(wav_data):
                            list_type = wav_data[offset+8:offset+12]
                            if list_type == b'INFO':
                                metadata['Audio:WAV:HasINFOChunk'] = True
                                # Parse INFO subchunks
                                info_offset = offset + 12
                                while info_offset < offset + 8 + chunk_size:
                                    if info_offset + 8 > len(wav_data):
                                        break
                                    info_id = wav_data[info_offset:info_offset+4]
                                    info_size = struct.unpack('<I', wav_data[info_offset+4:info_offset+8])[0]
                                    
                                    # Common INFO chunk IDs
                                    if info_id == b'INAM':  # Name/Title
                                        try:
                                            text = wav_data[info_offset+8:info_offset+8+info_size].decode('utf-8', errors='ignore').strip('\x00')
                                            if text:
                                                metadata['Audio:WAV:Title'] = text
                                                metadata['XMP:Title'] = text
                                        except Exception:
                                            pass
                                    elif info_id == b'IART':  # Artist
                                        try:
                                            text = wav_data[info_offset+8:info_offset+8+info_size].decode('utf-8', errors='ignore').strip('\x00')
                                            if text:
                                                metadata['Audio:WAV:Artist'] = text
                                        except Exception:
                                            pass
                                    elif info_id == b'ICMT':  # Comment
                                        try:
                                            text = wav_data[info_offset+8:info_offset+8+info_size].decode('utf-8', errors='ignore').strip('\x00')
                                            if text:
                                                metadata['Audio:WAV:Comment'] = text
                                        except Exception:
                                            pass
                                    
                                    info_offset += 8 + info_size
                                    if info_size % 2:  # Pad to even
                                        info_offset += 1
                            elif list_type == b'guano' or list_type == b'GUAN':
                                # Guano metadata chunk - used in bat acoustic analysis software
                                # Guano format: key-value pairs separated by newlines or semicolons
                                metadata['RIFF:Guano:Present'] = 'Yes'
                                guano_offset = offset + 12
                                guano_data = wav_data[guano_offset:offset+8+chunk_size]
                                try:
                                    # Guano metadata is typically UTF-8 text with key-value pairs
                                    guano_text = guano_data.decode('utf-8', errors='ignore').strip('\x00')
                                    if guano_text:
                                        # Parse Guano key-value pairs (format: "Key: Value\n" or "Key=Value\n")
                                        guano_lines = guano_text.split('\n')
                                        for line in guano_lines:
                                            line = line.strip()
                                            if not line or line.startswith('#'):
                                                continue
                                            
                                            # Try "Key: Value" format first
                                            if ':' in line:
                                                parts = line.split(':', 1)
                                                if len(parts) == 2:
                                                    key = parts[0].strip()
                                                    value = parts[1].strip()
                                                    if key and value:
                                                        # Sanitize key name for metadata tag
                                                        tag_key = key.replace(' ', '').replace('-', '')
                                                        metadata[f'RIFF:Guano:{tag_key}'] = value
                                            # Try "Key=Value" format
                                            elif '=' in line:
                                                parts = line.split('=', 1)
                                                if len(parts) == 2:
                                                    key = parts[0].strip()
                                                    value = parts[1].strip()
                                                    if key and value:
                                                        tag_key = key.replace(' ', '').replace('-', '')
                                                        metadata[f'RIFF:Guano:{tag_key}'] = value
                                        
                                        # Store raw Guano data (truncate if too long)
                                        if len(guano_text) <= 10000:  # Store up to 10KB
                                            metadata['RIFF:Guano:Data'] = guano_text
                                        else:
                                            metadata['RIFF:Guano:Data'] = guano_text[:10000] + '...'
                                            metadata['RIFF:Guano:Truncated'] = 'Yes'
                                        
                                        metadata['RIFF:Guano:DataSize'] = chunk_size
                                except Exception:
                                    # If parsing fails, still mark as present
                                    metadata['RIFF:Guano:Present'] = 'Yes'
                                    metadata['RIFF:Guano:DataSize'] = chunk_size
                    
                    elif chunk_id == b'acid':
                        # Acid chunk - written by Acidizer (music production software)
                        # Acid chunk structure: flags(4) + tempo(4) + time signature(2) + beats(2) + meter(2) + root note(2) + unknown(2)
                        if offset + 8 + chunk_size <= len(wav_data) and chunk_size >= 16:
                            acid_data = wav_data[offset+8:offset+8+chunk_size]
                            try:
                                # Parse Acid chunk data
                                # Flags (4 bytes)
                                flags = struct.unpack('<I', acid_data[0:4])[0]
                                metadata['RIFF:Acid:Flags'] = f'0x{flags:08X}'
                                
                                # Tempo (4 bytes, float)
                                if len(acid_data) >= 8:
                                    tempo = struct.unpack('<f', acid_data[4:8])[0]
                                    metadata['RIFF:Acid:Tempo'] = f"{tempo:.2f} bpm"
                                
                                # Time signature (2 bytes)
                                if len(acid_data) >= 10:
                                    time_sig = struct.unpack('<H', acid_data[8:10])[0]
                                    metadata['RIFF:Acid:TimeSignature'] = time_sig
                                
                                # Beats (2 bytes)
                                if len(acid_data) >= 12:
                                    beats = struct.unpack('<H', acid_data[10:12])[0]
                                    metadata['RIFF:Acid:Beats'] = beats
                                
                                # Meter (2 bytes)
                                if len(acid_data) >= 14:
                                    meter = struct.unpack('<H', acid_data[12:14])[0]
                                    metadata['RIFF:Acid:Meter'] = meter
                                
                                # Root note (2 bytes)
                                if len(acid_data) >= 16:
                                    root_note = struct.unpack('<H', acid_data[14:16])[0]
                                    metadata['RIFF:Acid:RootNote'] = root_note
                                
                                # Mark Acid chunk as present
                                metadata['RIFF:Acid:Present'] = 'Yes'
                                metadata['RIFF:Acid:DataSize'] = chunk_size
                            except Exception:
                                # If parsing fails, still mark as present
                                metadata['RIFF:Acid:Present'] = 'Yes'
                                metadata['RIFF:Acid:DataSize'] = chunk_size
                    
                    elif chunk_id == b'id3 ':
                        # ID3 chunk - contains ID3v2 tag data in WAV files
                        if offset + 8 + chunk_size <= len(wav_data):
                            id3_data = wav_data[offset+8:offset+8+chunk_size]
                            try:
                                # Check for ID3v2 header signature
                                if len(id3_data) >= 10 and id3_data[:3] == b'ID3':
                                    # Parse ID3v2 header
                                    id3_version_major = id3_data[3]
                                    id3_version_minor = id3_data[4]
                                    id3_flags = id3_data[5]
                                    
                                    # ID3v2 tag size (4 bytes, synchsafe integer)
                                    id3_size_bytes = id3_data[6:10]
                                    id3_tag_size = (id3_size_bytes[0] << 21) | (id3_size_bytes[1] << 14) | (id3_size_bytes[2] << 7) | id3_size_bytes[3]
                                    
                                    metadata['RIFF:ID3:Present'] = 'Yes'
                                    metadata['RIFF:ID3:Version'] = f"2.{id3_version_major}.{id3_version_minor}"
                                    metadata['RIFF:ID3:Size'] = id3_tag_size
                                    metadata['RIFF:ID3:Flags'] = f'0x{id3_flags:02X}'
                                    
                                    # Parse ID3v2 frames if available
                                    if len(id3_data) >= 10 + id3_tag_size:
                                        id3_frame_data = id3_data[10:10+id3_tag_size]
                                        # Parse ID3v2 frames (similar to MP3 ID3 parsing)
                                        frame_offset = 0
                                        while frame_offset < len(id3_frame_data) - 10:
                                            # ID3v2 frame header: frame ID (4 bytes) + size (4 bytes) + flags (2 bytes)
                                            frame_id = id3_frame_data[frame_offset:frame_offset+4]
                                            
                                            # Check for padding (all zeros)
                                            if frame_id == b'\x00\x00\x00\x00':
                                                break
                                            
                                            frame_size_bytes = id3_frame_data[frame_offset+4:frame_offset+8]
                                            frame_size = (frame_size_bytes[0] << 24) | (frame_size_bytes[1] << 16) | (frame_size_bytes[2] << 8) | frame_size_bytes[3]
                                            
                                            if frame_size == 0 or frame_offset + 10 + frame_size > len(id3_frame_data):
                                                break
                                            
                                            # Parse common ID3v2 frames
                                            try:
                                                frame_id_str = frame_id.decode('ascii', errors='ignore')
                                                if frame_id_str == 'TIT2':  # Title
                                                    text = id3_frame_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-8', errors='ignore').strip('\x00')
                                                    if text:
                                                        metadata['RIFF:ID3:Title'] = text
                                                        metadata.setdefault('XMP:Title', text)
                                                elif frame_id_str == 'TPE1':  # Artist
                                                    text = id3_frame_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-8', errors='ignore').strip('\x00')
                                                    if text:
                                                        metadata['RIFF:ID3:Artist'] = text
                                                elif frame_id_str == 'TALB':  # Album
                                                    text = id3_frame_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-8', errors='ignore').strip('\x00')
                                                    if text:
                                                        metadata['RIFF:ID3:Album'] = text
                                                elif frame_id_str in ('TYER', 'TDRC'):  # Year/Date
                                                    text = id3_frame_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-8', errors='ignore').strip('\x00')
                                                    if text:
                                                        metadata['RIFF:ID3:Year'] = text
                                                elif frame_id_str == 'TENC':  # Encoder
                                                    text = id3_frame_data[frame_offset+11:frame_offset+10+frame_size].decode('utf-8', errors='ignore').strip('\x00')
                                                    if text:
                                                        metadata['RIFF:ID3:Encoder'] = text
                                            except Exception:
                                                pass
                                            
                                            frame_offset += 10 + frame_size
                                else:
                                    # ID3 chunk present but doesn't start with ID3 signature
                                    metadata['RIFF:ID3:Present'] = 'Yes'
                                    metadata['RIFF:ID3:DataSize'] = chunk_size
                            except Exception:
                                # If parsing fails, still mark as present
                                metadata['RIFF:ID3:Present'] = 'Yes'
                                metadata['RIFF:ID3:DataSize'] = chunk_size
                    
                    elif chunk_id == b'iXML':
                        # BWF iXML chunk - Broadcast Wave Format XML metadata
                        if offset + 8 + chunk_size <= len(wav_data):
                            ixml_data = wav_data[offset+8:offset+8+chunk_size]
                            try:
                                # iXML is XML data, try to decode as UTF-8
                                ixml_text = ixml_data.decode('utf-8', errors='ignore').strip('\x00')
                                if ixml_text:
                                    metadata['RIFF:iXML:Present'] = 'Yes'
                                    metadata['RIFF:iXML:DataSize'] = chunk_size
                                    # Store XML content (truncate if too long)
                                    if len(ixml_text) <= 10000:  # Store up to 10KB
                                        metadata['RIFF:iXML:Data'] = ixml_text
                                    else:
                                        metadata['RIFF:iXML:Data'] = ixml_text[:10000] + '...'
                                        metadata['RIFF:iXML:Truncated'] = 'Yes'
                            except Exception:
                                # If decoding fails, still mark as present
                                metadata['RIFF:iXML:Present'] = 'Yes'
                                metadata['RIFF:iXML:DataSize'] = chunk_size
                    
                    elif chunk_id == b'aXML':
                        # BWF aXML chunk - Broadcast Wave Format XML metadata (alternative)
                        if offset + 8 + chunk_size <= len(wav_data):
                            axml_data = wav_data[offset+8:offset+8+chunk_size]
                            try:
                                # aXML is XML data, try to decode as UTF-8
                                axml_text = axml_data.decode('utf-8', errors='ignore').strip('\x00')
                                if axml_text:
                                    metadata['RIFF:aXML:Present'] = 'Yes'
                                    metadata['RIFF:aXML:DataSize'] = chunk_size
                                    # Store XML content (truncate if too long)
                                    if len(axml_text) <= 10000:  # Store up to 10KB
                                        metadata['RIFF:aXML:Data'] = axml_text
                                    else:
                                        metadata['RIFF:aXML:Data'] = axml_text[:10000] + '...'
                                        metadata['RIFF:aXML:Truncated'] = 'Yes'
                            except Exception:
                                # If decoding fails, still mark as present
                                metadata['RIFF:aXML:Present'] = 'Yes'
                                metadata['RIFF:aXML:DataSize'] = chunk_size
                    
                    elif chunk_id == b'UMID':
                        # BWF UMID chunk - Unique Material Identifier (SMPTE 330M)
                        if offset + 8 + chunk_size <= len(wav_data):
                            umid_data = wav_data[offset+8:offset+8+chunk_size]
                            try:
                                # UMID is typically 32 or 64 bytes
                                # Format: Material Number (32 bytes) + optional Instance Number (32 bytes)
                                if len(umid_data) >= 32:
                                    # Extract Material Number (first 32 bytes)
                                    material_num = umid_data[:32]
                                    material_hex = ''.join(f'{b:02x}' for b in material_num)
                                    metadata['RIFF:UMID:Present'] = 'Yes'
                                    metadata['RIFF:UMID:MaterialNumber'] = material_hex.upper()
                                    
                                    if len(umid_data) >= 64:
                                        # Extract Instance Number (next 32 bytes)
                                        instance_num = umid_data[32:64]
                                        instance_hex = ''.join(f'{b:02x}' for b in instance_num)
                                        metadata['RIFF:UMID:InstanceNumber'] = instance_hex.upper()
                                    
                                    metadata['RIFF:UMID:DataSize'] = chunk_size
                            except Exception:
                                # If parsing fails, still mark as present
                                metadata['RIFF:UMID:Present'] = 'Yes'
                                metadata['RIFF:UMID:DataSize'] = chunk_size
                    
                    elif chunk_id == b'data':
                        # Data chunk - contains audio sample data
                        # Calculate duration from data chunk size and audio format
                        if offset + 8 + chunk_size <= len(wav_data):
                            data_size = chunk_size
                            # Get audio format info from previously parsed fmt chunk
                            sample_rate = None
                            num_channels = None
                            bits_per_sample = None
                            
                            # Extract sample rate, channels, bits from metadata if available
                            # Try RIFF:SampleRate first (integer), then Audio:WAV:SampleRate (with " Hz")
                            sample_rate = metadata.get('RIFF:SampleRate')
                            if not sample_rate:
                                sample_rate_str = metadata.get('Audio:WAV:SampleRate', '')
                                if sample_rate_str and ' Hz' in sample_rate_str:
                                    try:
                                        sample_rate = int(sample_rate_str.replace(' Hz', ''))
                                    except ValueError:
                                        pass
                            
                            num_channels = metadata.get('Audio:WAV:NumChannels') or metadata.get('RIFF:NumChannels')
                            bits_per_sample = metadata.get('Audio:WAV:BitsPerSample') or metadata.get('RIFF:BitsPerSample')
                            
                            # Calculate duration: data_size / (sample_rate * channels * bytes_per_sample)
                            if sample_rate and num_channels and bits_per_sample and sample_rate > 0:
                                bytes_per_sample = bits_per_sample // 8
                                duration_seconds = data_size / (sample_rate * num_channels * bytes_per_sample)
                                if duration_seconds > 0:
                                    # Format duration similar to standard format
                                    if duration_seconds >= 60:
                                        hours = int(duration_seconds // 3600)
                                        minutes = int((duration_seconds % 3600) // 60)
                                        secs = int(duration_seconds % 60)
                                        duration_str = f"{hours}:{minutes:02d}:{secs:02d}"
                                    elif duration_seconds == 0:
                                        duration_str = "0 s"
                                    else:
                                        duration_str = f"{duration_seconds:.2f} s"
                                    
                                    metadata['Audio:WAV:Duration'] = duration_str
                                    metadata['WAV:Duration'] = duration_str  # For Composite:Duration lookup
                                    metadata['Composite:Duration'] = duration_str  # Set Composite:Duration directly
                    
                    offset += 8 + chunk_size
                    if chunk_size % 2:  # Pad to even
                        offset += 1
                
        except Exception:
            pass
        
        return metadata
    
    def _parse_flac(self) -> Dict[str, Any]:
        """Parse FLAC Vorbis comments with value extraction."""
        metadata = {}
        
        try:
            if not self.file_data:
                return metadata
            
            # FLAC files start with 'fLaC'
            if self.file_data.startswith(b'fLaC'):
                metadata['Audio:FLAC:Format'] = 'FLAC'
                metadata['Audio:FLAC:IsFLAC'] = True
                
                # Look for Vorbis comment block (type 4)
                # FLAC metadata blocks after 'fLaC' marker
                if len(self.file_data) >= 8:
                    offset = 4
                    while offset < len(self.file_data) - 4:
                        if offset + 4 > len(self.file_data):
                            break
                        
                        block_header = self.file_data[offset:offset+4]
                        if len(block_header) >= 4:
                            block_type = block_header[0] & 0x7F  # Last bit is "last block" flag
                            is_last = (block_header[0] & 0x80) != 0
                            
                            # Block length (3 bytes, big-endian)
                            block_length = struct.unpack('>I', b'\x00' + self.file_data[offset+1:offset+4])[0]
                            
                            if block_type == 0:  # STREAMINFO block
                                # STREAMINFO contains audio stream information
                                if offset + 4 + block_length <= len(self.file_data):
                                    streaminfo_data = self.file_data[offset+4:offset+4+block_length]
                                    if len(streaminfo_data) >= 34:
                                        # Minimum block size (2 bytes, big-endian)
                                        block_size_min = struct.unpack('>H', streaminfo_data[0:2])[0]
                                        metadata['FLAC:BlockSizeMin'] = block_size_min
                                        metadata['Audio:FLAC:BlockSizeMin'] = block_size_min  # Keep for backward compatibility
                                        
                                        # Maximum block size (2 bytes, big-endian)
                                        block_size_max = struct.unpack('>H', streaminfo_data[2:4])[0]
                                        metadata['FLAC:BlockSizeMax'] = block_size_max
                                        metadata['Audio:FLAC:BlockSizeMax'] = block_size_max  # Keep for backward compatibility
                                        
                                        # Minimum frame size (3 bytes, big-endian)
                                        frame_size_min_bytes = streaminfo_data[4:7]
                                        frame_size_min = struct.unpack('>I', b'\x00' + frame_size_min_bytes)[0]
                                        metadata['FLAC:FrameSizeMin'] = frame_size_min
                                        metadata['Audio:FLAC:FrameSizeMin'] = frame_size_min  # Keep for backward compatibility
                                        
                                        # Maximum frame size (3 bytes, big-endian)
                                        frame_size_max_bytes = streaminfo_data[7:10]
                                        frame_size_max = struct.unpack('>I', b'\x00' + frame_size_max_bytes)[0]
                                        metadata['FLAC:FrameSizeMax'] = frame_size_max
                                        metadata['Audio:FLAC:FrameSizeMax'] = frame_size_max  # Keep for backward compatibility
                                        
                                        # Sample rate (20 bits, big-endian, stored in bytes 10-12)
                                        sample_rate_bytes = streaminfo_data[10:13]
                                        # Extract 20 bits: bits 0-11 from byte 10, bits 12-19 from byte 11, bits 20-27 from byte 12
                                        sample_rate = ((sample_rate_bytes[0] << 12) | 
                                                      (sample_rate_bytes[1] << 4) | 
                                                      ((sample_rate_bytes[2] >> 4) & 0x0F))
                                        # Standard format shows SampleRate as integer without "Hz" suffix
                                        metadata['FLAC:SampleRate'] = sample_rate
                                        metadata['Audio:FLAC:SampleRate'] = f"{sample_rate} Hz"  # Keep formatted version for backward compatibility
                                        
                                        # Number of channels (3 bits, from byte 12, bits 4-6)
                                        channels = ((sample_rate_bytes[2] >> 1) & 0x07) + 1
                                        metadata['FLAC:Channels'] = channels
                                        metadata['Audio:FLAC:Channels'] = channels  # Keep for backward compatibility
                                        
                                        # Bits per sample (5 bits, from bytes 12-13)
                                        # sample_rate_bytes is only 3 bytes (bytes 10-12), so use streaminfo_data[13] directly
                                        bits_per_sample = (((sample_rate_bytes[2] & 0x01) << 4) | 
                                                          ((streaminfo_data[13] >> 4) & 0x0F)) + 1
                                        metadata['FLAC:BitsPerSample'] = bits_per_sample
                                        metadata['Audio:FLAC:BitsPerSample'] = bits_per_sample  # Keep for backward compatibility
                                        
                                        # Total samples in stream (36 bits, from bytes 13-17)
                                        # According to FLAC spec: 36-bit value stored across bytes 13-17
                                        # However, in practice, the value is often stored as a 32-bit value in bytes 14-17
                                        # Byte 13's upper 4 bits may be used for other purposes or reserved
                                        # Extract 32-bit value from bytes 14-17 (this standard format's output)
                                        if len(streaminfo_data) >= 18:
                                            total_samples_bytes = streaminfo_data[13:18]
                                            if len(total_samples_bytes) >= 5:
                                                # Use bytes 14-17 as 32-bit big-endian value (standard format behavior)
                                                total_samples = struct.unpack('>I', total_samples_bytes[1:5])[0]
                                                if total_samples > 0:
                                                    metadata['FLAC:TotalSamples'] = total_samples
                                                    metadata['Audio:FLAC:TotalSamples'] = total_samples  # Keep for backward compatibility
                                                    # Calculate duration from total samples and sample rate
                                                    if sample_rate > 0:
                                                        duration_seconds = total_samples / sample_rate
                                                        if duration_seconds > 0:
                                                            # Format duration similar to standard format (HH:MM:SS format)
                                                            # Standard rounding to nearest second for FLAC duration
                                                            duration_rounded = round(duration_seconds)
                                                            hours = int(duration_rounded // 3600)
                                                            minutes = int((duration_rounded % 3600) // 60)
                                                            secs = int(duration_rounded % 60)
                                                            duration_str = f"{hours}:{minutes:02d}:{secs:02d}"
                                                            metadata['Composite:Duration'] = duration_str
                                        
                                        # MD5 signature (16 bytes, from bytes 18-34)
                                        md5_signature = streaminfo_data[18:34]
                                        md5_hex = ''.join(f'{b:02x}' for b in md5_signature)
                                        metadata['FLAC:MD5Signature'] = md5_hex
                                        metadata['Audio:FLAC:MD5Signature'] = md5_hex  # Keep for backward compatibility
                            
                            elif block_type == 4:  # Vorbis comment block
                                metadata['Audio:FLAC:HasVorbisComments'] = True
                                
                                # Parse Vorbis comment structure
                                comment_offset = offset + 4
                                if comment_offset + 4 < len(self.file_data):
                                    # Vendor string length (4 bytes, little-endian)
                                    vendor_len = struct.unpack('<I', self.file_data[comment_offset:comment_offset+4])[0]
                                    comment_offset += 4
                                    
                                    # Extract vendor string
                                    if comment_offset + vendor_len <= len(self.file_data):
                                        vendor_str = self.file_data[comment_offset:comment_offset+vendor_len].decode('utf-8', errors='ignore')
                                        metadata['Vorbis:Vendor'] = vendor_str
                                        comment_offset += vendor_len
                                    
                                    # User comment list length
                                    if comment_offset + 4 < len(self.file_data):
                                        comment_count = struct.unpack('<I', self.file_data[comment_offset:comment_offset+4])[0]
                                        comment_offset += 4
                                        
                                        # Parse comments
                                        for i in range(min(comment_count, 100)):
                                            if comment_offset + 4 > len(self.file_data):
                                                break
                                            comment_len = struct.unpack('<I', self.file_data[comment_offset:comment_offset+4])[0]
                                            comment_offset += 4
                                            
                                            if comment_offset + comment_len > len(self.file_data):
                                                break
                                            
                                            comment = self.file_data[comment_offset:comment_offset+comment_len].decode('utf-8', errors='ignore')
                                            comment_offset += comment_len
                                            
                                            # Parse comment (format: KEY=value)
                                            if '=' in comment:
                                                key, value = comment.split('=', 1)
                                                key = key.upper()
                                                if key == 'TITLE':
                                                    metadata['Audio:FLAC:Title'] = value
                                                    metadata.setdefault('XMP:Title', value)
                                                elif key == 'ARTIST':
                                                    metadata['Audio:FLAC:Artist'] = value
                                                elif key == 'ALBUM':
                                                    metadata['Audio:FLAC:Album'] = value
                                                elif key == 'DATE' or key == 'YEAR':
                                                    metadata['Audio:FLAC:Date'] = value
                                                elif key == 'COMMENT':
                                                    metadata['Audio:FLAC:Comment'] = value
                                                elif key == 'ENCODER':
                                                    metadata['Vorbis:Encoder'] = value
                                
                                # Continue to next block after processing Vorbis comments
                                offset += 4 + block_length
                                if is_last:
                                    break
                                continue
                            
                            elif block_type == 2:  # APPLICATION block
                                # APPLICATION blocks can contain RIFF metadata
                                if offset + 4 + block_length <= len(self.file_data):
                                    app_data = self.file_data[offset+4:offset+4+block_length]
                                    
                                    # Check if this APPLICATION block contains RIFF data
                                    # APPLICATION block structure: application ID (4 bytes) + data
                                    if len(app_data) >= 4:
                                        app_id = app_data[:4]
                                        
                                        # Check if the data after app_id contains RIFF structure
                                        if len(app_data) > 4:
                                            riff_data = app_data[4:]
                                            # Look for RIFF signature in the data
                                            if b'RIFF' in riff_data[:100]:  # Check first 100 bytes
                                                # Parse RIFF chunks from APPLICATION block
                                                riff_offset = riff_data.find(b'RIFF')
                                                if riff_offset != -1 and riff_offset + 12 <= len(riff_data):
                                                    # Parse RIFF structure
                                                    try:
                                                        # RIFF header: RIFF (4) + size (4) + format (4)
                                                        riff_format = riff_data[riff_offset+8:riff_offset+12]
                                                        
                                                        # Parse RIFF chunks after header
                                                        riff_chunk_offset = riff_offset + 12
                                                        while riff_chunk_offset < len(riff_data) - 8:
                                                            chunk_id = riff_data[riff_chunk_offset:riff_chunk_offset+4]
                                                            if len(chunk_id) < 4:
                                                                break
                                                            chunk_size = struct.unpack('<I', riff_data[riff_chunk_offset+4:riff_chunk_offset+8])[0]
                                                            
                                                            if chunk_size == 0 or riff_chunk_offset + 8 + chunk_size > len(riff_data):
                                                                break
                                                            
                                                            # Extract chunk data
                                                            chunk_data = riff_data[riff_chunk_offset+8:riff_chunk_offset+8+chunk_size]
                                                            
                                                            # Store RIFF chunk information
                                                            metadata[f'FLAC:RIFF:{chunk_id.decode("ascii", errors="ignore")}:Present'] = 'Yes'
                                                            metadata[f'FLAC:RIFF:{chunk_id.decode("ascii", errors="ignore")}:Size'] = chunk_size
                                                            
                                                            # Mark that RIFF metadata was found
                                                            metadata['FLAC:RIFF:Present'] = 'Yes'
                                                            metadata['FLAC:RIFF:ApplicationID'] = app_id.decode('ascii', errors='ignore')
                                                            
                                                            riff_chunk_offset += 8 + chunk_size
                                                            if chunk_size % 2:  # Pad to even
                                                                riff_chunk_offset += 1
                                                    except Exception:
                                                        # If RIFF parsing fails, still mark as present
                                                        metadata['FLAC:RIFF:Present'] = 'Yes'
                                                        metadata['FLAC:RIFF:ApplicationID'] = app_id.decode('ascii', errors='ignore')
                            
                            # Move to next block
                            offset += 4 + block_length
                            
                            if is_last:
                                break
                        else:
                            break
                
        except Exception:
            pass
        
        return metadata

    def _parse_ogg_vorbis(self) -> Dict[str, Any]:
        """Parse Vorbis comments stored inside an OGG container."""
        metadata: Dict[str, Any] = {}
        data = self._read_entire_file()
        if not data or not data.startswith(b'OggS'):
            return metadata
        
        # Look for Vorbis identification header (packet type 1)
        vorbis_id_sig = b'\x01vorbis'
        vorbis_id_idx = data.find(vorbis_id_sig)
        if vorbis_id_idx != -1:
            # Parse Vorbis identification header
            id_header = data[vorbis_id_idx + len(vorbis_id_sig):]
            if len(id_header) >= 24:
                # Vorbis version (4 bytes, should be 0)
                vorbis_version = struct.unpack('<I', id_header[0:4])[0]
                metadata['Audio:OGG:VorbisVersion'] = vorbis_version
                metadata['Vorbis:VorbisVersion'] = vorbis_version
                
                # Audio channels (1 byte)
                channels = id_header[4]
                metadata['Audio:OGG:AudioChannels'] = channels
                metadata['Vorbis:AudioChannels'] = channels
                
                # Sample rate (4 bytes, little-endian)
                sample_rate = struct.unpack('<I', id_header[5:9])[0]
                metadata['Audio:OGG:SampleRate'] = f"{sample_rate} Hz"
                metadata['Vorbis:SampleRate'] = sample_rate  # Standard format shows as integer
                
                # Bitrate maximum (4 bytes, little-endian)
                bitrate_max = struct.unpack('<I', id_header[9:13])[0]
                # Bitrate nominal (4 bytes, little-endian)
                bitrate_nominal = struct.unpack('<I', id_header[13:17])[0]
                if bitrate_nominal > 0:
                    metadata['Audio:OGG:NominalBitrate'] = f"{bitrate_nominal} bps"
                    # Standard format shows nominal bitrate in kbps
                    bitrate_kbps = bitrate_nominal / 1000
                    metadata['Vorbis:NominalBitrate'] = f"{int(bitrate_kbps)} kbps"
                    # Calculate duration from file size and bitrate
                    if self.file_path:
                        try:
                            import os
                            file_size = os.path.getsize(self.file_path)
                            if file_size > 0 and bitrate_nominal > 0:
                                # Duration = (file_size * 8) / bitrate_nominal
                                duration_seconds = (file_size * 8) / bitrate_nominal
                                if duration_seconds > 0:
                                    # Format duration similar to standard format (add "(approx)" suffix for OGG)
                                    if duration_seconds >= 60:
                                        hours = int(duration_seconds // 3600)
                                        minutes = int((duration_seconds % 3600) // 60)
                                        secs = int(duration_seconds % 60)
                                        duration_str = f"{hours}:{minutes:02d}:{secs:02d} (approx)"
                                    elif duration_seconds == 0:
                                        duration_str = "0 s"
                                    else:
                                        duration_str = f"{duration_seconds:.2f} s (approx)"
                                    
                                    metadata['Audio:OGG:Duration'] = duration_str
                                    metadata['OGG:Duration'] = duration_str  # For Composite:Duration lookup
                                    metadata['Composite:Duration'] = duration_str  # Set Composite:Duration directly
                        except (OSError, ValueError, TypeError):
                            pass
                # Bitrate minimum (4 bytes, little-endian)
                bitrate_min = struct.unpack('<I', id_header[17:21])[0]
        
        # Look for Vorbis comment header (packet type 3)
        signature = b'\x03vorbis'
        idx = data.find(signature)
        if idx == -1:
            return metadata
        
        comment_block = data[idx + len(signature):]
        metadata['Audio:OGG:Format'] = 'Ogg Vorbis'
        vorbis_metadata = self._extract_vorbis_comments(comment_block, prefix='Audio:OGG')
        metadata.update(vorbis_metadata)
        
        # Extract Vorbis:Vendor and Vorbis:Encoder from comment block
        try:
            if len(comment_block) >= 4:
                vendor_len = struct.unpack('<I', comment_block[0:4])[0]
                if vendor_len > 0 and vendor_len < len(comment_block) - 4:
                    vendor_str = comment_block[4:4+vendor_len].decode('utf-8', errors='ignore')
                    if vendor_str:
                        metadata['Vorbis:Vendor'] = vendor_str
        except Exception:
            pass
        
        # Encoder is extracted in _extract_vorbis_comments, add Vorbis: prefix
        if 'Audio:OGG:Encoder' in metadata:
            metadata['Vorbis:Encoder'] = metadata['Audio:OGG:Encoder']
        
        return metadata

    def _parse_opus(self) -> Dict[str, Any]:
        """Parse OpusTags (Vorbis comment structure) inside an Ogg Opus stream."""
        metadata: Dict[str, Any] = {}
        data = self._read_entire_file()
        if not data or not data.startswith(b'OggS'):
            return metadata
        
        # Look for Opus identification header (OpusHead)
        opus_head_sig = b'OpusHead'
        opus_head_idx = data.find(opus_head_sig)
        if opus_head_idx != -1:
            # Parse Opus identification header
            head_data = data[opus_head_idx + len(opus_head_sig):]
            if len(head_data) >= 19:
                # Version (1 byte)
                opus_version = head_data[0]
                metadata['Audio:OPUS:OpusVersion'] = opus_version
                
                # Output channel count (1 byte)
                channels = head_data[1]
                metadata['Audio:OPUS:AudioChannels'] = channels
                metadata['Opus:AudioChannels'] = channels
                
                # Pre-skip (2 bytes, little-endian)
                pre_skip = struct.unpack('<H', head_data[2:4])[0]
                metadata['Audio:OPUS:PreSkip'] = pre_skip
                
                # Input sample rate (4 bytes, little-endian)
                sample_rate = struct.unpack('<I', head_data[4:8])[0]
                metadata['Audio:OPUS:SampleRate'] = f"{sample_rate} Hz"
                metadata['Opus:SampleRate'] = sample_rate  # Standard format shows as integer
                
                # Output gain (2 bytes, little-endian, signed)
                # Opus OutputGain is Q7.8 fixed-point, but Standard format shows it as integer
                # If value is 0, Standard format shows 1 (possibly a default or different interpretation)
                output_gain_raw = struct.unpack('<h', head_data[8:10])[0]
                # Standard format shows 1 when the raw value is 0
                if output_gain_raw == 0:
                    output_gain_standard_format = 1
                else:
                    output_gain_standard_format = output_gain_raw
                metadata['Audio:OPUS:OutputGain'] = f"{output_gain_raw} dB"
                metadata['Opus:OutputGain'] = output_gain_standard_format  # standard format's interpretation
                
                # Channel mapping family (1 byte)
                channel_mapping_family = head_data[10]
                metadata['Audio:OPUS:ChannelMappingFamily'] = channel_mapping_family
                
                # Calculate duration from file size and sample rate
                # For Opus, we can estimate duration from file size and average bitrate
                # Opus files typically have variable bitrate, so we use a rough estimate
                if self.file_path and sample_rate > 0:
                    try:
                        import os
                        file_size = os.path.getsize(self.file_path)
                        # Opus files typically have bitrate around 64-128 kbps
                        # Use a conservative estimate: assume 96 kbps average
                        estimated_bitrate_bps = 96 * 1000
                        if file_size > 0:
                            duration_seconds = (file_size * 8) / estimated_bitrate_bps
                            if duration_seconds > 0:
                                # Format duration similar to standard format
                                if duration_seconds >= 60:
                                    hours = int(duration_seconds // 3600)
                                    minutes = int((duration_seconds % 3600) // 60)
                                    secs = int(duration_seconds % 60)
                                    metadata['Audio:OPUS:Duration'] = f"{hours}:{minutes:02d}:{secs:02d}"
                                elif duration_seconds == 0:
                                    metadata['Audio:OPUS:Duration'] = "0 s"
                                else:
                                    metadata['Audio:OPUS:Duration'] = f"{duration_seconds:.2f} s"
                    except (OSError, ValueError, TypeError):
                        pass
        
        # Look for OpusTags (Vorbis comment structure)
        signature = b'OpusTags'
        idx = data.find(signature)
        if idx == -1:
            return metadata
        
        comment_block = data[idx + len(signature):]
        metadata['Audio:OPUS:Format'] = 'Opus'
        vorbis_metadata = self._extract_vorbis_comments(comment_block, prefix='Audio:OPUS')
        metadata.update(vorbis_metadata)
        
        # Extract Vorbis:Vendor and Vorbis:Encoder from comment block
        try:
            if len(comment_block) >= 4:
                vendor_len = struct.unpack('<I', comment_block[0:4])[0]
                if vendor_len > 0 and vendor_len < len(comment_block) - 4:
                    vendor_str = comment_block[4:4+vendor_len].decode('utf-8', errors='ignore')
                    if vendor_str:
                        metadata['Vorbis:Vendor'] = vendor_str
        except Exception:
            pass
        
        # Encoder is extracted in _extract_vorbis_comments, add Vorbis: prefix
        if 'Audio:OPUS:Encoder' in metadata:
            metadata['Vorbis:Encoder'] = metadata['Audio:OPUS:Encoder']
        
        # Add Opus:OpusVersion
        if 'Audio:OPUS:OpusVersion' in metadata:
            metadata['Opus:OpusVersion'] = metadata['Audio:OPUS:OpusVersion']
        
        return metadata

    def _extract_vorbis_comments(self, block: bytes, prefix: str) -> Dict[str, Any]:
        """Extract key/value data from a Vorbis comment block."""
        metadata: Dict[str, Any] = {}
        offset = 0
        try:
            if offset + 4 > len(block):
                return metadata
            # Vendor string length (4 bytes, little-endian)
            vendor_len = struct.unpack('<I', block[offset:offset+4])[0]
            offset += 4
            if offset + vendor_len <= len(block):
                vendor = block[offset:offset+vendor_len].decode('utf-8', errors='ignore')
                metadata[f'{prefix}:Vendor'] = vendor
            offset += vendor_len
            if offset + 4 > len(block):
                return metadata
            comment_count = struct.unpack('<I', block[offset:offset+4])[0]
            offset += 4
            for _ in range(min(comment_count, 200)):
                if offset + 4 > len(block):
                    break
                length = struct.unpack('<I', block[offset:offset+4])[0]
                offset += 4
                if offset + length > len(block):
                    break
                comment = block[offset:offset+length].decode('utf-8', errors='ignore')
                offset += length
                if '=' not in comment:
                    continue
                key, value = comment.split('=', 1)
                key_upper = key.upper()
                namespaced_key = f'{prefix}:{key_upper.title()}'
                metadata[namespaced_key] = value
                if key_upper == 'TITLE':
                    metadata[f'{prefix}:Title'] = value
                    metadata.setdefault('XMP:Title', value)
                elif key_upper == 'ARTIST':
                    metadata[f'{prefix}:Artist'] = value
                elif key_upper == 'ALBUM':
                    metadata[f'{prefix}:Album'] = value
                elif key_upper in ('DATE', 'YEAR'):
                    metadata[f'{prefix}:Date'] = value
                elif key_upper == 'ENCODER':
                    metadata[f'{prefix}:Encoder'] = value
        except Exception:
            pass
        return metadata

    def _parse_wma(self) -> Dict[str, Any]:
        """
        Parse WMA file metadata from ASF objects.
        
        WMA files use ASF (Advanced Systems Format) container.
        ASF Header Object GUID: 75B22630-668E-11CF-A6D9-00AA0062CE6C
        Extended Content Description Object GUID: 40A4D0D2-07E3-D211-97F0-00A0C95EA850
        File Properties Object GUID: 8CABDCA1-A947-11CF-8EE4-00C00C205365
        Stream Properties Object GUID: B7DC0791-A9B7-11CF-8EE6-00C00C205365
        Codec List Object GUID: 86D15240-311D-11D0-A3A4-00A0C90348F6
        
        Returns:
            Dictionary of parsed metadata
        """
        metadata = {}
        
        try:
            # Read entire file for ASF parsing
            file_data = self._read_entire_file()
            if not file_data or len(file_data) < 16:
                return metadata
            
            # Verify ASF Header Object
            asf_header_guid = bytes.fromhex('3026b2758e66cf11a6d900aa0062ce6c')
            if file_data[:16] != asf_header_guid:
                return metadata
            
            metadata['Audio:WMA:HasASF'] = True
            
            # Get file size for FileLength tag
            if self.file_path:
                import os
                file_size = os.path.getsize(self.file_path)
                metadata['Audio:WMA:FileLength'] = file_size
            
            # File Properties Object GUID: 8CABDCA1-A947-11CF-8EE4-00C00C205365
            # Contains: FileID, FileSize, CreationDate, DataPacketsCount, PlayDuration, SendDuration, Preroll, Flags, MinDataPacketSize, MaxDataPacketSize, MaxBitrate
            file_props_guid = bytes.fromhex('a1dccab847a9cf11e48e00c00c205365')
            
            # Stream Properties Object GUID: B7DC0791-A9B7-11CF-8EE6-00C00C205365
            # Contains: StreamType, ErrorCorrectionType, TimeOffset, TypeSpecificData (codec info), UserData
            stream_props_guid = bytes.fromhex('9107dcb7b7a9cf11e68e00c00c205365')
            
            # Codec List Object GUID: 86D15240-311D-11D0-A3A4-00A0C90348F6
            # Contains: Codec entries with CodecID, CodecName, CodecDescription, CodecInformation
            codec_list_guid = bytes.fromhex('4052d1861d31d011a3a400a0c90348f6')
            
            # Parse File Properties Object
            data_len = len(file_data)
            offset = 0
            while offset + 24 <= data_len:
                if file_data[offset:offset+16] == file_props_guid:
                    # Read object size (8 bytes, little-endian)
                    obj_size = struct.unpack('<Q', file_data[offset+16:offset+24])[0]
                    if obj_size < 104 or offset + obj_size > data_len:  # File Properties Object is at least 104 bytes
                        offset += 1
                        continue
                    
                    data_start = offset + 24
                    # File Properties Object structure (after GUID and Size):
                    # FileID (16 bytes) + FileSize (8 bytes) + CreationDate (8 bytes) + DataPacketsCount (8 bytes)
                    # + PlayDuration (8 bytes) + SendDuration (8 bytes) + Preroll (8 bytes) + Flags (4 bytes)
                    # + MinDataPacketSize (4 bytes) + MaxDataPacketSize (4 bytes) + MaxBitrate (4 bytes)
                    
                    if data_start + 84 <= offset + obj_size:
                        # FileSize (offset 16 from data_start, i.e., data_start + 16)
                        file_size_val = struct.unpack('<Q', file_data[data_start+16:data_start+24])[0]
                        if file_size_val > 0:
                            metadata['Audio:WMA:FileLength'] = file_size_val
                        
                        # CreationDate (offset 24 from data_start, i.e., data_start + 24)
                        # ASF uses 100-nanosecond intervals since January 1, 1601
                        creation_date_val = struct.unpack('<Q', file_data[data_start+24:data_start+32])[0]
                        if creation_date_val > 0:
                            # Convert to Unix timestamp: (ASF time - 116444736000000000) / 10000000
                            # 116444736000000000 is the number of 100-nanosecond intervals from 1601-01-01 to 1970-01-01
                            unix_timestamp = (creation_date_val - 116444736000000000) / 10000000.0
                            if unix_timestamp > 0:
                                import datetime
                                dt = datetime.datetime.fromtimestamp(unix_timestamp, tz=datetime.timezone.utc)
                                metadata['Audio:WMA:CreationDate'] = dt.strftime('%Y:%m:%d %H:%M:%S')
                        
                        # Preroll (offset 48 from data_start, i.e., data_start + 48)
                        preroll_val = struct.unpack('<Q', file_data[data_start+48:data_start+56])[0]
                        if preroll_val > 0:
                            # Preroll is in milliseconds
                            metadata['Audio:WMA:Preroll'] = f"{preroll_val} ms"
                        
                        # MaxDataPacketSize (offset 72 from data_start, i.e., data_start + 72)
                        max_packet_size = struct.unpack('<I', file_data[data_start+72:data_start+76])[0]
                        if max_packet_size > 0:
                            metadata['Audio:WMA:MaxPacketSize'] = max_packet_size
                        
                        # MaxBitrate (offset 76 from data_start, i.e., data_start + 76)
                        max_bitrate = struct.unpack('<I', file_data[data_start+76:data_start+80])[0]
                        if max_bitrate > 0:
                            metadata['Audio:WMA:MaxBitrate'] = f"{max_bitrate} bps"
                        
                        # PlayDuration (offset 32 from data_start, i.e., data_start + 32)
                        # Duration is in 100-nanosecond intervals
                        play_duration_val = struct.unpack('<Q', file_data[data_start+32:data_start+40])[0]
                        if play_duration_val > 0:
                            # Convert to seconds: play_duration_val / 10000000.0
                            duration_seconds = play_duration_val / 10000000.0
                            metadata['Audio:WMA:Duration'] = self._format_duration(duration_seconds)
                    
                    offset += obj_size
                    continue
                
                offset += 1
                if offset + 24 > data_len:
                    break
            
            # Parse Stream Properties Object (for audio codec info)
            offset = 0
            while offset + 24 <= data_len:
                if file_data[offset:offset+16] == stream_props_guid:
                    # Read object size (8 bytes, little-endian)
                    obj_size = struct.unpack('<Q', file_data[offset+16:offset+24])[0]
                    if obj_size < 78 or offset + obj_size > data_len:  # Stream Properties Object is at least 78 bytes
                        offset += 1
                        continue
                    
                    data_start = offset + 24
                    # Stream Properties Object structure (after GUID and Size):
                    # StreamType (16 bytes GUID) + ErrorCorrectionType (16 bytes GUID) + TimeOffset (8 bytes)
                    # + TypeSpecificDataLength (4 bytes) + TypeSpecificData (variable) + UserDataLength (4 bytes) + UserData (variable)
                    
                    if data_start + 44 <= offset + obj_size:
                        # StreamType GUID (offset 0 from data_start)
                        stream_type_guid = file_data[data_start:data_start+16]
                        # Audio stream GUID: F8699E40-5B4D-11CF-A8FD-00AA006B2EA4
                        audio_stream_guid = bytes.fromhex('409e69f84d5bcf11a8fd00aa006b2ea4')
                        
                        if stream_type_guid == audio_stream_guid:
                            # This is an audio stream, parse TypeSpecificData for audio codec info
                            # TypeSpecificDataLength (offset 40 from data_start, i.e., data_start + 40)
                            type_specific_len = struct.unpack('<I', file_data[data_start+40:data_start+44])[0]
                            
                            if type_specific_len > 0 and data_start + 44 + type_specific_len <= offset + obj_size:
                                type_specific_data = file_data[data_start+44:data_start+44+type_specific_len]
                                
                                # WMA audio format structure (in TypeSpecificData):
                                # CodecID (2 bytes) + NumberOfChannels (2 bytes) + SamplesPerSecond (4 bytes)
                                # + AvgBytesPerSecond (4 bytes) + BlockAlign (2 bytes) + BitsPerSample (2 bytes)
                                # + CodecSpecificDataSize (2 bytes) + CodecSpecificData (variable)
                                
                                if len(type_specific_data) >= 18:
                                    # NumberOfChannels (offset 2)
                                    num_channels = struct.unpack('<H', type_specific_data[2:4])[0]
                                    if num_channels > 0:
                                        metadata['Audio:WMA:AudioChannels'] = num_channels
                                    
                                    # SamplesPerSecond (offset 4)
                                    sample_rate = struct.unpack('<I', type_specific_data[4:8])[0]
                                    if sample_rate > 0:
                                        metadata['Audio:WMA:AudioSampleRate'] = f"{sample_rate} Hz"
                                    
                                    # CodecID (offset 0) - WMA codec IDs: 0x0161 (WMA), 0x0162 (WMA Pro), 0x0163 (WMA Lossless)
                                    codec_id = struct.unpack('<H', type_specific_data[0:2])[0]
                                    codec_id_map = {
                                        0x0161: 'Windows Media Audio',
                                        0x0162: 'Windows Media Audio Professional',
                                        0x0163: 'Windows Media Audio Lossless',
                                        0x0164: 'Windows Media Audio Voice',
                                        0x0165: 'Windows Media Audio 9.2 Lossless'
                                    }
                                    codec_name = codec_id_map.get(codec_id, f'Unknown ({hex(codec_id)})')
                                    metadata['Audio:WMA:AudioCodecID'] = hex(codec_id)
                                    metadata['Audio:WMA:AudioCodecName'] = codec_name
                    
                    offset += obj_size
                    continue
                
                offset += 1
                if offset + 24 > data_len:
                    break
            
            # Parse Codec List Object (for additional codec information)
            offset = 0
            while offset + 24 <= data_len:
                if file_data[offset:offset+16] == codec_list_guid:
                    # Read object size (8 bytes, little-endian)
                    obj_size = struct.unpack('<Q', file_data[offset+16:offset+24])[0]
                    if obj_size < 26 or offset + obj_size > data_len:
                        offset += 1
                        continue
                    
                    data_start = offset + 24
                    # Codec List Object structure (after GUID and Size):
                    # Reserved (6 bytes) + CodecEntriesCount (4 bytes) + Codec Entries
                    # Each Codec Entry: Type (2 bytes) + CodecNameLength (2 bytes) + CodecName (UTF-16LE)
                    # + CodecDescriptionLength (2 bytes) + CodecDescription (UTF-16LE)
                    # + CodecInformationLength (2 bytes) + CodecInformation (binary)
                    
                    if data_start + 10 <= offset + obj_size:
                        codec_count = struct.unpack('<I', file_data[data_start+6:data_start+10])[0]
                        codec_pos = data_start + 10
                        
                        for _ in range(codec_count):
                            if codec_pos + 2 > offset + obj_size:
                                break
                            
                            # Type (2 bytes) - 1 = Video, 2 = Audio
                            codec_type = struct.unpack('<H', file_data[codec_pos:codec_pos+2])[0]
                            codec_pos += 2
                            
                            # CodecNameLength (2 bytes)
                            if codec_pos + 2 > offset + obj_size:
                                break
                            codec_name_len = struct.unpack('<H', file_data[codec_pos:codec_pos+2])[0]
                            codec_pos += 2
                            
                            # CodecName (UTF-16LE)
                            if codec_name_len > 0 and codec_pos + codec_name_len <= offset + obj_size:
                                try:
                                    codec_name = file_data[codec_pos:codec_pos+codec_name_len].decode('utf-16-le', errors='ignore').strip('\x00')
                                    if codec_name and codec_type == 2:  # Audio codec
                                        # Only set if not already set from Stream Properties
                                        if 'Audio:WMA:AudioCodecName' not in metadata:
                                            metadata['Audio:WMA:AudioCodecName'] = codec_name
                                except Exception:
                                    pass
                                codec_pos += codec_name_len
                            
                            # CodecDescriptionLength (2 bytes)
                            if codec_pos + 2 > offset + obj_size:
                                break
                            codec_desc_len = struct.unpack('<H', file_data[codec_pos:codec_pos+2])[0]
                            codec_pos += 2
                            
                            # CodecDescription (UTF-16LE) - extract
                            if codec_desc_len > 0 and codec_pos + codec_desc_len <= offset + obj_size:
                                try:
                                    codec_desc = file_data[codec_pos:codec_pos+codec_desc_len].decode('utf-16-le', errors='ignore').strip('\x00')
                                    if codec_desc:
                                        metadata['Audio:WMA:AudioCodecDescription'] = codec_desc
                                        metadata['ASF:AudioCodecDescription'] = codec_desc
                                except Exception:
                                    pass
                                codec_pos += codec_desc_len
                            
                            # CodecInformationLength (2 bytes)
                            if codec_pos + 2 > offset + obj_size:
                                break
                            codec_info_len = struct.unpack('<H', file_data[codec_pos:codec_pos+2])[0]
                            codec_pos += 2
                            
                            # CodecInformation (binary) - skip
                            if codec_info_len > 0:
                                codec_pos += codec_info_len
                            
                            if codec_pos > offset + obj_size:
                                break
                    
                    offset += obj_size
                    continue
                
                offset += 1
                if offset + 24 > data_len:
                    break
            
            # ASF GUIDs are stored with the first three fields in little-endian order.
            # Extended Content Description Object GUID: 40A4D0D2-07E3-D211-97F0-00A0C95EA850
            ext_content_desc_guid = bytes.fromhex('d2d0a440e30711d297f000a0c95ea850')
            ext_content_desc_guid_legacy = bytes.fromhex('40a4d0d207e3d21197f000a0c95ea850')
            
            # Content Description Object GUID: 75B22633-668E-11CF-A6D9-00AA0062CE6C
            content_desc_guid = bytes.fromhex('3326b2758e66cf11a6d900aa0062ce6c')
            content_desc_guid_legacy = bytes.fromhex('75b22633668e11cfa6d900aa0062ce6c')
            
            # Search for Extended Content Description Object (more common) or Content Description Object
            # ASF objects have: GUID (16 bytes) + Size (8 bytes) + Data
            # Search for all Extended Content Description Objects (there may be multiple)
            offset = 0
            data_len = len(file_data)
            found_title = False
            
            # First, collect all Extended Content Description Object positions
            ext_content_positions = []
            while offset < data_len:
                pos = file_data.find(ext_content_desc_guid, offset)
                if pos == -1:
                    break
                ext_content_positions.append(pos)
                offset = pos + 1
            offset = 0
            while offset < data_len:
                pos = file_data.find(ext_content_desc_guid_legacy, offset)
                if pos == -1:
                    break
                ext_content_positions.append(pos)
                offset = pos + 1
            ext_content_positions = sorted(set(ext_content_positions))
            
            # Parse all Extended Content Description Objects (check last one first as it's likely the newest)
            for pos in reversed(ext_content_positions):
                if found_title:
                    break
                
                offset = pos
                if offset + 24 <= data_len:
                    # Check for Extended Content Description Object GUID
                    if file_data[offset:offset+16] in (ext_content_desc_guid, ext_content_desc_guid_legacy):
                        # Read object size (8 bytes, little-endian)
                        obj_size = struct.unpack('<Q', file_data[offset+16:offset+24])[0]
                        if obj_size < 26 or offset + obj_size > data_len:
                            continue
                        
                        # Extended Content Description Object structure:
                        # Content Descriptors Count (2 bytes) + Descriptors
                        # Each Descriptor: Name Length (2) + Name (UTF-16LE) + Value Type (2) + Value Length (2) + Value
                        data_start = offset + 24
                        if data_start + 2 > offset + obj_size:
                            continue
                        
                        desc_count = struct.unpack('<H', file_data[data_start:data_start+2])[0]
                        data_pos = data_start + 2
                        
                        for _ in range(desc_count):
                            if data_pos + 2 > offset + obj_size:
                                break
                            # Read name length
                            name_len = struct.unpack('<H', file_data[data_pos:data_pos+2])[0]
                            data_pos += 2
                            if name_len == 0 or data_pos + name_len > offset + obj_size:
                                break
                            # Read name
                            try:
                                name = file_data[data_pos:data_pos+name_len].decode('utf-16-le', errors='ignore').strip('\x00')
                            except Exception:
                                name = None
                            data_pos += name_len
                            
                            if data_pos + 4 > offset + obj_size:
                                break
                            # Read value type and length
                            value_type = struct.unpack('<H', file_data[data_pos:data_pos+2])[0]
                            value_len = struct.unpack('<H', file_data[data_pos+2:data_pos+4])[0]
                            data_pos += 4
                            
                            if value_len == 0 or data_pos + value_len > offset + obj_size:
                                break
                            
                            # Read value based on type
                            if value_type == 0:  # Unicode string
                                try:
                                    value = file_data[data_pos:data_pos+value_len].decode('utf-16-le', errors='ignore').strip('\x00')
                                    if name and value:
                                        name_upper = name.upper().strip('\x00')
                                        # Map common ASF tag names to metadata keys
                                        if name_upper in ('TITLE', 'WM/TITLE', 'WM\\TITLE'):
                                            metadata['Audio:WMA:Title'] = value
                                            metadata['XMP:Title'] = value
                                        elif name_upper in ('AUTHOR', 'ARTIST', 'WM/AUTHOR', 'WM/ARTIST'):
                                            metadata['Audio:WMA:Artist'] = value
                                            metadata['XMP:Artist'] = value
                                        elif name_upper in ('COPYRIGHT', 'WM/COPYRIGHT'):
                                            metadata['Audio:WMA:Copyright'] = value
                                        elif name_upper in ('DESCRIPTION', 'WM/DESCRIPTION'):
                                            metadata['Audio:WMA:Description'] = value
                                        elif name_upper in ('ALBUM', 'WM/ALBUM'):
                                            metadata['Audio:WMA:Album'] = value
                                            metadata['XMP:Album'] = value
                                        elif name_upper in ('GENRE', 'WM/GENRE'):
                                            metadata['Audio:WMA:Genre'] = value
                                        elif name_upper in ('YEAR', 'WM/YEAR'):
                                            metadata['Audio:WMA:Year'] = value
                                        elif name_upper in ('TRACK', 'WM/TRACK'):
                                            metadata['Audio:WMA:Track'] = value
                                        elif name_upper in ('ALBUMARTIST', 'WM/ALBUMARTIST'):
                                            metadata['Audio:WMA:AlbumArtist'] = value
                                        elif name_upper in ('COMPOSER', 'WM/COMPOSER'):
                                            metadata['Audio:WMA:Composer'] = value
                                        elif name_upper in ('LYRICS', 'WM/LYRICS'):
                                            metadata['Audio:WMA:Lyrics'] = value
                                        elif name_upper in ('ENCODINGSETTINGS', 'WM/ENCODINGSETTINGS', 'WM\\ENCODINGSETTINGS'):
                                            metadata['Audio:WMA:EncodingSettings'] = value
                                            metadata['ASF:EncodingSettings'] = value
                                        else:
                                            # Store any other Extended Content Description tags
                                            # Use the name as-is but sanitize it
                                            safe_name = name.replace('/', '_').replace('\\', '_').replace(' ', '_')
                                            metadata[f'Audio:WMA:{safe_name}'] = value
                                except Exception:
                                    pass
                            elif value_type == 1:  # BYTE array
                                # Store as hex string
                                try:
                                    value_bytes = file_data[data_pos:data_pos+value_len]
                                    value_hex = value_bytes.hex().upper()
                                    name_upper = name.upper().strip('\x00')
                                    metadata[f'Audio:WMA:{name}'] = value_hex
                                except Exception:
                                    pass
                            elif value_type == 2:  # BOOL
                                try:
                                    bool_value = struct.unpack('<?', file_data[data_pos:data_pos+1])[0] if value_len >= 1 else False
                                    name_upper = name.upper().strip('\x00')
                                    metadata[f'Audio:WMA:{name}'] = 'Yes' if bool_value else 'No'
                                except Exception:
                                    pass
                            elif value_type == 3:  # DWORD (32-bit unsigned int)
                                try:
                                    if value_len >= 4:
                                        dword_value = struct.unpack('<I', file_data[data_pos:data_pos+4])[0]
                                        name_upper = name.upper().strip('\x00')
                                        metadata[f'Audio:WMA:{name}'] = dword_value
                                except Exception:
                                    pass
                            elif value_type == 4:  # QWORD (64-bit unsigned int)
                                try:
                                    if value_len >= 8:
                                        qword_value = struct.unpack('<Q', file_data[data_pos:data_pos+8])[0]
                                        name_upper = name.upper().strip('\x00')
                                        metadata[f'Audio:WMA:{name}'] = qword_value
                                except Exception:
                                    pass
                            elif value_type == 5:  # WORD (16-bit unsigned int)
                                try:
                                    if value_len >= 2:
                                        word_value = struct.unpack('<H', file_data[data_pos:data_pos+2])[0]
                                        name_upper = name.upper().strip('\x00')
                                        metadata[f'Audio:WMA:{name}'] = word_value
                                except Exception:
                                    pass
                            
                            data_pos += value_len
                        
                        if metadata.get('XMP:Title'):
                            found_title = True
                            break  # Found title in Extended Content Description Object
            
            # If still no title, check for Content Description Object (fallback)
            if not found_title:
                offset = 0
                while offset + 24 <= data_len:
                    if file_data[offset:offset+16] in (content_desc_guid, content_desc_guid_legacy):
                        # Read object size (8 bytes, little-endian)
                        obj_size = struct.unpack('<Q', file_data[offset+16:offset+24])[0]
                        if obj_size < 24 or offset + obj_size > data_len:
                            offset += 1
                            continue
                        
                        # Content Description Object structure:
                        # Title Length (2 bytes) + Title (UTF-16LE)
                        # Author Length (2 bytes) + Author (UTF-16LE)
                        # Copyright Length (2 bytes) + Copyright (UTF-16LE)
                        # Description Length (2 bytes) + Description (UTF-16LE)
                        # Rating Length (2 bytes) + Rating (UTF-16LE)
                        
                        data_start = offset + 24
                        data_pos = data_start
                        
                        # Parse Title
                        if data_pos + 2 <= offset + obj_size:
                            title_len = struct.unpack('<H', file_data[data_pos:data_pos+2])[0]
                            data_pos += 2
                            if title_len > 0 and data_pos + title_len <= offset + obj_size:
                                try:
                                    title = file_data[data_pos:data_pos+title_len].decode('utf-16-le', errors='ignore').strip('\x00')
                                    if title:
                                        metadata['Audio:WMA:Title'] = title
                                        metadata['XMP:Title'] = title
                                        found_title = True
                                except Exception:
                                    pass
                                data_pos += title_len
                        
                                if metadata.get('XMP:Title'):
                                    found_title = True
                                    break
                    
                    offset += 1
                    if offset + 24 > data_len:
                        break
            
            # Parse File Properties Object (0x8CABDCA1-A947-11CF-8EE4-00C00C205365)
            # Contains: FileSize, CreationDate, DataPacketsCount, PlayDuration, Preroll, Flags, MinDataPacketSize, MaxDataPacketSize, MaxBitrate
            # GUID is stored with first 8 bytes in little-endian: a1dcab8c47a9cf118ee400c00c205365
            file_props_guid = bytes.fromhex('a1dcab8c47a9cf118ee400c00c205365')
            offset = 0
            while offset + 24 <= data_len:
                pos = file_data.find(file_props_guid, offset)
                if pos == -1:
                    break
                
                if pos + 24 <= data_len:
                    obj_size = struct.unpack('<Q', file_data[pos+16:pos+24])[0]
                    if obj_size >= 104 and pos + obj_size <= data_len:  # File Properties Object is at least 104 bytes
                        # File ID (16 bytes GUID, offset 24)
                        if pos + 40 <= data_len:
                            file_id_guid = file_data[pos+24:pos+40]
                            # Convert GUID to string format
                            file_id_str = '-'.join([
                                file_id_guid[0:4][::-1].hex(),
                                file_id_guid[4:6][::-1].hex(),
                                file_id_guid[6:8][::-1].hex(),
                                file_id_guid[8:10].hex(),
                                file_id_guid[10:16].hex()
                            ])
                            metadata['ASF:FileID'] = file_id_str.upper()
                        
                        # File Size (8 bytes, offset 24 + 16 = offset 40)
                        if pos + 48 <= data_len:
                            file_size = struct.unpack('<Q', file_data[pos+40:pos+48])[0]
                            if file_size > 0:
                                metadata['Audio:WMA:FileLength'] = file_size
                                metadata['ASF:FileLength'] = str(file_size)
                        
                        # Creation Date (8 bytes, offset 48) - 100-nanosecond intervals since Jan 1, 1601
                        if pos + 56 <= data_len:
                            creation_date = struct.unpack('<Q', file_data[pos+48:pos+56])[0]
                            if creation_date > 0:
                                # Convert Windows FILETIME to datetime
                                # FILETIME is 100-nanosecond intervals since Jan 1, 1601
                                # Unix epoch is Jan 1, 1970
                                # Difference: 116444736000000000 (100-nanosecond intervals)
                                filetime_epoch = 116444736000000000
                                if creation_date >= filetime_epoch:
                                    unix_timestamp = (creation_date - filetime_epoch) / 10000000.0
                                    try:
                                        import datetime
                                        dt = datetime.datetime.fromtimestamp(unix_timestamp, tz=datetime.timezone.utc)
                                        creation_date_str = dt.strftime('%Y:%m:%d %H:%M:%S')
                                        metadata['Audio:WMA:CreationDate'] = creation_date_str
                                        metadata['ASF:CreationDate'] = creation_date_str
                                    except Exception:
                                        pass
                        
                        # Data Packets Count (8 bytes, offset 56)
                        if pos + 64 <= data_len:
                            data_packets = struct.unpack('<Q', file_data[pos+56:pos+64])[0]
                            if data_packets > 0:
                                metadata['Audio:WMA:DataPacketsCount'] = data_packets
                                metadata['ASF:DataPackets'] = str(data_packets)
                        
                        # Play Duration (8 bytes, offset 64) - in 100-nanosecond units
                        if pos + 72 <= data_len:
                            play_duration = struct.unpack('<Q', file_data[pos+64:pos+72])[0]
                            if play_duration > 0:
                                duration_seconds = play_duration / 10000000.0
                                duration_str = self._format_duration(duration_seconds)
                                metadata['Audio:WMA:Duration'] = duration_str
                                metadata['ASF:Duration'] = duration_str
                                metadata['Composite:Duration'] = duration_str
                        
                        # Send Duration (8 bytes, offset 72) - in 100-nanosecond units
                        if pos + 80 <= data_len:
                            send_duration = struct.unpack('<Q', file_data[pos+72:pos+80])[0]
                            if send_duration > 0:
                                send_duration_seconds = send_duration / 10000000.0
                                send_duration_str = self._format_duration(send_duration_seconds)
                                metadata['Audio:WMA:SendDuration'] = send_duration_str
                                metadata['ASF:SendDuration'] = send_duration_str
                        
                        # Preroll (8 bytes, offset 80) - in milliseconds
                        if pos + 88 <= data_len:
                            preroll = struct.unpack('<Q', file_data[pos+80:pos+88])[0]
                            if preroll > 0:
                                metadata['Audio:WMA:Preroll'] = f"{preroll} ms"
                                metadata['ASF:Preroll'] = str(preroll)
                        
                        # Flags (4 bytes, offset 88)
                        if pos + 92 <= data_len:
                            flags = struct.unpack('<I', file_data[pos+88:pos+92])[0]
                            metadata['ASF:Flags'] = str(flags)
                        
                        # Min Data Packet Size (4 bytes, offset 92)
                        if pos + 96 <= data_len:
                            min_packet_size = struct.unpack('<I', file_data[pos+92:pos+96])[0]
                            if min_packet_size > 0:
                                metadata['Audio:WMA:MinPacketSize'] = min_packet_size
                                metadata['ASF:MinPacketSize'] = str(min_packet_size)
                        
                        # Max Data Packet Size (4 bytes, offset 96)
                        if pos + 100 <= data_len:
                            max_packet_size = struct.unpack('<I', file_data[pos+96:pos+100])[0]
                            if max_packet_size > 0:
                                metadata['Audio:WMA:MaxPacketSize'] = max_packet_size
                                metadata['ASF:MaxPacketSize'] = str(max_packet_size)
                        
                        # Max Bitrate (4 bytes, offset 100) - in bits per second
                        if pos + 104 <= data_len:
                            max_bitrate = struct.unpack('<I', file_data[pos+100:pos+104])[0]
                            if max_bitrate > 0:
                                max_bitrate_kbps = max_bitrate / 1000.0
                                metadata['Audio:WMA:MaxBitrate'] = f"{max_bitrate} bps"
                                metadata['ASF:MaxBitrate'] = f"{max_bitrate_kbps:.0f} kbps"
                
                offset = pos + 1
                if offset + 24 > data_len:
                    break
            
            # Parse Stream Properties Object (0xB7DC0791-A9B7-11CF-8EE6-00C00C205365)
            # Contains: StreamType, ErrorCorrectionType, TimeOffset, TypeSpecificDataLength, ErrorCorrectionDataLength, Flags
            # TypeSpecificData contains codec information
            # GUID is stored with first 8 bytes in little-endian: 9107dcb7b7a9cf118ee600c00c205365
            stream_props_guid = bytes.fromhex('9107dcb7b7a9cf118ee600c00c205365')
            offset = 0
            while offset + 24 <= data_len:
                pos = file_data.find(stream_props_guid, offset)
                if pos == -1:
                    break
                
                if pos + 24 <= data_len:
                    obj_size = struct.unpack('<Q', file_data[pos+16:pos+24])[0]
                    if obj_size >= 78 and pos + obj_size <= data_len:  # Stream Properties Object is at least 78 bytes
                        # Stream Number (1 byte, offset 24) - actually at offset 24, but Stream Type GUID is at 24
                        # Actually, Stream Properties Object structure:
                        # Stream Type GUID (16 bytes, offset 24)
                        # Error Correction Type GUID (16 bytes, offset 40)
                        # Time Offset (8 bytes, offset 56)
                        # Type-Specific Data Length (4 bytes, offset 64)
                        # Error Correction Data Length (4 bytes, offset 68)
                        # Flags (2 bytes, offset 72)
                        # Reserved (4 bytes, offset 74)
                        # Type-Specific Data (variable, offset 78)
                        
                        # Stream Type GUID (16 bytes, offset 24)
                        stream_type_guid = file_data[pos+24:pos+40]
                        # Audio Media GUID: F8699E40-5B4D-11CF-A8FD-00805F5C442B
                        # Stored with first 8 bytes in little-endian: 409e69f84d5bcf11a8fd00805f5c442b
                        audio_media_guid = bytes.fromhex('409e69f84d5bcf11a8fd00805f5c442b')
                        # Video Media GUID: C055BD11-CE11-11CF-8EE4-00C00C205365
                        # Stored with first 8 bytes in little-endian: 11bd55c011cecf118ee400c00c205365
                        video_media_guid = bytes.fromhex('11bd55c011cecf118ee400c00c205365')
                        if stream_type_guid == audio_media_guid:
                            metadata['Audio:WMA:StreamType'] = 'Audio'
                            metadata['ASF:StreamType'] = 'Audio'
                        elif stream_type_guid == video_media_guid:
                            metadata['Audio:WMA:StreamType'] = 'Video'
                            metadata['ASF:StreamType'] = 'Video'
                        
                        # Error Correction Type GUID (16 bytes, offset 40)
                        error_correction_guid = file_data[pos+40:pos+56]
                        # Audio Spread GUID: BFB3B8A2-5B4D-11CF-A8FD-00805F5C442B
                        # Stored with first 8 bytes in little-endian: a2b8b3bf4d5bcf11a8fd00805f5c442b
                        audio_spread_guid = bytes.fromhex('a2b8b3bf4d5bcf11a8fd00805f5c442b')
                        if error_correction_guid == audio_spread_guid:
                            metadata['Audio:WMA:ErrorCorrectionType'] = 'Audio Spread'
                            metadata['ASF:ErrorCorrectionType'] = 'Audio Spread'
                        
                        # Time Offset (8 bytes, offset 56) - in 100-nanosecond units
                        time_offset = struct.unpack('<Q', file_data[pos+56:pos+64])[0]
                        # Always store TimeOffset, even if 0 (standard format does this)
                        time_offset_seconds = time_offset / 10000000.0
                        metadata['ASF:TimeOffset'] = f"{time_offset_seconds:.2f} s"
                        
                        # Flags (2 bytes, offset 72) - contains Stream Number in lower 7 bits
                        flags = struct.unpack('<H', file_data[pos+72:pos+74])[0]
                        stream_number = flags & 0x7F
                        if stream_number > 0:
                            metadata['Audio:WMA:StreamNumber'] = str(stream_number)
                            metadata['ASF:StreamNumber'] = str(stream_number)
                        
                        if stream_type_guid == audio_media_guid:
                            
                            # Error Correction Type GUID (16 bytes, offset 40)
                            # Time Offset (8 bytes, offset 56)
                            # Type-Specific Data Length (4 bytes, offset 64)
                            type_specific_len = struct.unpack('<I', file_data[pos+64:pos+68])[0]
                            
                            # Type-Specific Data starts at offset 78
                            if type_specific_len > 0 and pos + 78 + type_specific_len <= data_len:
                                type_specific_data = file_data[pos+78:pos+78+type_specific_len]
                                
                                # Audio stream format structure (WAVEFORMATEX):
                                # FormatTag (2 bytes) - audio format code
                                # Channels (2 bytes) - number of audio channels
                                # SamplesPerSec (4 bytes) - sample rate
                                # AvgBytesPerSec (4 bytes) - average bytes per second
                                # BlockAlign (2 bytes) - block alignment
                                # BitsPerSample (2 bytes) - bits per sample
                                # (Optional: CodecData)
                                
                                if len(type_specific_data) >= 18:
                                    # FormatTag (2 bytes)
                                    format_tag = struct.unpack('<H', type_specific_data[0:2])[0]
                                    format_names = {
                                        0x0001: 'PCM',
                                        0x0002: 'Microsoft ADPCM',
                                        0x0055: 'MPEG Layer 3',
                                        0x0161: 'Windows Media Audio',
                                        0x0162: 'Windows Media Audio Professional',
                                        0x0163: 'Windows Media Audio Lossless',
                                        0x000F: 'DVI/Intel IMA ADPCM',
                                        0x0011: 'Intel IMA ADPCM',
                                        0x0031: 'GSM 6.10',
                                        0x0040: 'Microsoft G.723.1',
                                        0x0042: 'Microsoft G.726',
                                        0x0050: 'MPEG',
                                        0x0055: 'MP3',
                                        0x0059: 'AAC',
                                        0x0061: 'Windows Media Audio',
                                        0x0062: 'Windows Media Audio Professional',
                                        0x0063: 'Windows Media Audio Lossless',
                                        0x0071: 'Windows Media Audio Voice',
                                        0x0161: 'WMA',
                                        0x0162: 'WMA Pro',
                                        0x0163: 'WMA Lossless',
                                        0x0164: 'WMA Voice',
                                    }
                                    codec_name = format_names.get(format_tag, f'Unknown (0x{format_tag:04X})')
                                    metadata['Audio:WMA:AudioCodecID'] = format_tag
                                    metadata['Audio:WMA:AudioCodecName'] = codec_name
                                    metadata['ASF:AudioCodecID'] = f"{format_tag:04X}"
                                    metadata['ASF:AudioCodecName'] = codec_name
                                    
                                    # Channels (2 bytes)
                                    channels = struct.unpack('<H', type_specific_data[2:4])[0]
                                    if channels > 0:
                                        metadata['Audio:WMA:AudioChannels'] = channels
                                        metadata['ASF:AudioChannels'] = str(channels)
                                    
                                    # Sample Rate (4 bytes)
                                    sample_rate = struct.unpack('<I', type_specific_data[4:8])[0]
                                    if sample_rate > 0:
                                        metadata['Audio:WMA:AudioSampleRate'] = f"{sample_rate} Hz"
                                        metadata['ASF:AudioSampleRate'] = str(sample_rate)
                                    
                                    # Average Bytes Per Second (4 bytes)
                                    avg_bytes_per_sec = struct.unpack('<I', type_specific_data[8:12])[0]
                                    if avg_bytes_per_sec > 0:
                                        metadata['Audio:WMA:AvgBytesPerSec'] = avg_bytes_per_sec
                                    
                                    # Block Align (2 bytes)
                                    block_align = struct.unpack('<H', type_specific_data[12:14])[0]
                                    if block_align > 0:
                                        metadata['Audio:WMA:BlockAlign'] = block_align
                                    
                                    # Bits Per Sample (2 bytes)
                                    bits_per_sample = struct.unpack('<H', type_specific_data[14:16])[0]
                                    if bits_per_sample > 0:
                                        metadata['Audio:WMA:BitsPerSample'] = bits_per_sample
                
                offset = pos + 1
                if offset + 24 > data_len:
                    break
            
        except Exception:
            pass
        
        return metadata
    
    def _parse_asf_file_properties(self, file_data: bytes, offset: int, obj_size: int) -> Dict[str, Any]:
        """
        Parse ASF File Properties Object.
        
        Args:
            file_data: Full file data
            offset: Offset to object GUID
            obj_size: Object size
            
        Returns:
            Dictionary of parsed metadata
        """
        metadata = {}
        
        try:
            if offset + obj_size > len(file_data) or obj_size < 104:
                return metadata
            
            # File Properties Object structure (starting at offset + 24):
            # File ID (16 bytes) - GUID
            # File Size (8 bytes) - QWORD
            # Creation Date (8 bytes) - QWORD (100-nanosecond intervals since Jan 1, 1601)
            # Data Packets Count (8 bytes) - QWORD
            # Play Duration (8 bytes) - QWORD (100-nanosecond intervals)
            # Send Duration (8 bytes) - QWORD
            # Preroll (8 bytes) - QWORD
            # Flags (4 bytes) - DWORD - offset 72 from data_start
            # Min Data Packet Size (4 bytes) - DWORD - offset 76 from data_start
            # Max Data Packet Size (4 bytes) - DWORD - offset 80 from data_start
            # Max Bitrate (4 bytes) - DWORD - offset 84 from data_start
            
            data_start = offset + 24
            
            # File Size (8 bytes at offset + 24 + 16 = offset + 40)
            if data_start + 24 <= offset + obj_size:
                file_size = struct.unpack('<Q', file_data[data_start+16:data_start+24])[0]
                if file_size > 0:
                    metadata['Audio:WMA:FileLength'] = file_size
            
            # Creation Date (8 bytes at offset + 24 + 16 = offset + 40)
            if data_start + 24 <= offset + obj_size:
                creation_date = struct.unpack('<Q', file_data[data_start+16:data_start+24])[0]
                if creation_date > 0:
                    # Convert Windows FILETIME to datetime
                    filetime_epoch = 116444736000000000
                    if creation_date >= filetime_epoch:
                        unix_timestamp = (creation_date - filetime_epoch) / 10000000.0
                        try:
                            import datetime
                            dt = datetime.datetime.fromtimestamp(unix_timestamp, tz=datetime.timezone.utc)
                            metadata['Audio:WMA:CreationDate'] = dt.strftime('%Y:%m:%d %H:%M:%S')
                        except Exception:
                            pass
            
            # Play Duration (8 bytes at offset + 24 + 32 = offset + 56)
            if data_start + 32 <= offset + obj_size:
                play_duration = struct.unpack('<Q', file_data[data_start+32:data_start+40])[0]
                if play_duration > 0:
                    duration_seconds = play_duration / 10000000.0
                    duration_str = self._format_duration(duration_seconds)
                    metadata['Audio:WMA:Duration'] = duration_str
                    metadata['Composite:Duration'] = duration_str
            
            # Preroll (8 bytes at offset + 24 + 40 = offset + 64)
            if data_start + 40 <= offset + obj_size:
                preroll = struct.unpack('<Q', file_data[data_start+40:data_start+48])[0]
                if preroll > 0:
                    metadata['Audio:WMA:Preroll'] = f"{preroll} ms"
                    metadata['ASF:Preroll'] = str(preroll)
            
            # Flags (4 bytes at offset + 24 + 64 = offset + 88)
            if data_start + 64 <= offset + obj_size:
                flags = struct.unpack('<I', file_data[data_start+64:data_start+68])[0]
                metadata['ASF:Flags'] = str(flags)
            
            # Min Data Packet Size (4 bytes at offset + 24 + 68 = offset + 92)
            if data_start + 68 <= offset + obj_size:
                min_packet_size = struct.unpack('<I', file_data[data_start+68:data_start+72])[0]
                if min_packet_size > 0:
                    metadata['Audio:WMA:MinPacketSize'] = min_packet_size
                    metadata['ASF:MinPacketSize'] = str(min_packet_size)
            
            # Max Data Packet Size (4 bytes at offset + 24 + 72 = offset + 96)
            if data_start + 72 <= offset + obj_size:
                max_packet_size = struct.unpack('<I', file_data[data_start+72:data_start+76])[0]
                if max_packet_size > 0:
                    metadata['Audio:WMA:MaxPacketSize'] = max_packet_size
                    metadata['ASF:MaxPacketSize'] = str(max_packet_size)
            
            # Max Bitrate (4 bytes at offset + 24 + 76 = offset + 100)
            if data_start + 76 <= offset + obj_size:
                max_bitrate = struct.unpack('<I', file_data[data_start+76:data_start+80])[0]
                if max_bitrate > 0:
                    max_bitrate_kbps = max_bitrate / 1000.0
                    metadata['Audio:WMA:MaxBitrate'] = f"{max_bitrate} bps"
                    metadata['ASF:MaxBitrate'] = f"{max_bitrate_kbps:.0f} kbps"
                    
        except Exception:
            pass
        
        return metadata
    
    def _parse_asf_stream_properties(self, file_data: bytes, offset: int, obj_size: int) -> Dict[str, Any]:
        """
        Parse ASF Stream Properties Object.
        
        Args:
            file_data: Full file data
            offset: Offset to object GUID
            obj_size: Object size
            
        Returns:
            Dictionary of parsed metadata
        """
        metadata = {}
        
        try:
            if offset + obj_size > len(file_data) or obj_size < 78:
                return metadata
            
            # Stream Properties Object structure (starting at offset + 24):
            # Stream Type (16 bytes) - GUID
            # Error Correction Type (16 bytes) - GUID
            # Time Offset (8 bytes) - QWORD
            # Type-Specific Data Length (4 bytes) - DWORD
            # Error Correction Data Length (4 bytes) - DWORD
            # Flags (2 bytes) - WORD
            # Reserved (4 bytes)
            # Type-Specific Data (variable)
            
            data_start = offset + 24
            
            # Stream Type GUID (first 16 bytes) - check if it's an audio stream
            # Audio stream GUID: F8699E40-5B4D-11CF-A8FD-00805F5C442B
            audio_stream_guid = bytes.fromhex('f8699e405b4d11cfa8fd00805f5c442b')
            
            if data_start + 16 <= offset + obj_size:
                stream_type = file_data[data_start:data_start+16]
                if stream_type == audio_stream_guid:
                    # This is an audio stream, parse audio-specific data
                    # Type-Specific Data Length (4 bytes at offset + 24 + 40 = offset + 64)
                    if data_start + 50 <= offset + obj_size:
                        type_specific_len = struct.unpack('<I', file_data[data_start+40:data_start+44])[0]
                        
                        # Audio-specific data starts at offset + 24 + 50 = offset + 74
                        type_specific_start = data_start + 50
                        if type_specific_start + type_specific_len <= offset + obj_size:
                            # Find null-terminated codec ID string
                            codec_id_end = type_specific_start
                            while codec_id_end < type_specific_start + type_specific_len:
                                if file_data[codec_id_end] == 0:
                                    break
                                codec_id_end += 1
                            
                            if codec_id_end > type_specific_start:
                                try:
                                    codec_id = file_data[type_specific_start:codec_id_end].decode('utf-8', errors='ignore')
                                    if codec_id:
                                        metadata['Audio:WMA:AudioCodecID'] = codec_id
                                        
                                        # Parse codec-specific data for audio parameters
                                        # WMA codec-specific data structure (after codec ID):
                                        # Format Tag (2 bytes) - WORD
                                        # Channels (2 bytes) - WORD
                                        # Samples Per Second (4 bytes) - DWORD
                                        # Avg Bytes Per Sec (4 bytes) - DWORD
                                        # Block Align (2 bytes) - WORD
                                        # Bits Per Sample (2 bytes) - WORD
                                        
                                        codec_data_start = codec_id_end + 1
                                        if codec_data_start + 16 <= type_specific_start + type_specific_len:
                                            # Channels (2 bytes)
                                            channels = struct.unpack('<H', file_data[codec_data_start+2:codec_data_start+4])[0]
                                            if channels > 0:
                                                metadata['Audio:WMA:AudioChannels'] = channels
                                            
                                            # Samples Per Second (4 bytes) - Sample Rate
                                            sample_rate = struct.unpack('<I', file_data[codec_data_start+4:codec_data_start+8])[0]
                                            if sample_rate > 0:
                                                metadata['Audio:WMA:AudioSampleRate'] = f"{sample_rate} Hz"
                                except Exception:
                                    pass
                                    
        except Exception:
            pass
        
        return metadata
    
    def _parse_asf_codec_list(self, file_data: bytes, offset: int, obj_size: int) -> Dict[str, Any]:
        """
        Parse ASF Codec List Object.
        
        Args:
            file_data: Full file data
            offset: Offset to object GUID
            obj_size: Object size
            
        Returns:
            Dictionary of parsed metadata
        """
        metadata = {}
        
        try:
            if offset + obj_size > len(file_data) or obj_size < 26:
                return metadata
            
            # Codec List Object structure (starting at offset + 24):
            # Reserved (6 bytes) + CodecEntriesCount (4 bytes) + Codec Entries
            # Each Codec Entry: Type (2 bytes) + CodecNameLength (2 bytes) + CodecName (UTF-16LE)
            # + CodecDescriptionLength (2 bytes) + CodecDescription (UTF-16LE)
            # + CodecInformationLength (2 bytes) + CodecInformation (binary)
            
            data_start = offset + 24
            
            if data_start + 10 <= offset + obj_size:
                codec_count = struct.unpack('<I', file_data[data_start+6:data_start+10])[0]
                codec_pos = data_start + 10
                
                for _ in range(min(codec_count, 100)):  # Limit to 100 codecs
                    if codec_pos + 2 > offset + obj_size:
                        break
                    
                    # Type (2 bytes) - 1 = Video, 2 = Audio
                    codec_type = struct.unpack('<H', file_data[codec_pos:codec_pos+2])[0]
                    codec_pos += 2
                    
                    # CodecNameLength (2 bytes)
                    if codec_pos + 2 > offset + obj_size:
                        break
                    codec_name_len = struct.unpack('<H', file_data[codec_pos:codec_pos+2])[0]
                    codec_pos += 2
                    
                    # CodecName (UTF-16LE)
                    if codec_name_len > 0 and codec_pos + codec_name_len <= offset + obj_size:
                        try:
                            codec_name = file_data[codec_pos:codec_pos+codec_name_len].decode('utf-16-le', errors='ignore').strip('\x00')
                            if codec_name and codec_type == 2:  # Audio codec
                                # Only set if not already set from Stream Properties
                                if 'Audio:WMA:AudioCodecName' not in metadata:
                                    metadata['Audio:WMA:AudioCodecName'] = codec_name
                        except Exception:
                            pass
                        codec_pos += codec_name_len
                    
                    # CodecDescriptionLength (2 bytes)
                    if codec_pos + 2 > offset + obj_size:
                        break
                    codec_desc_len = struct.unpack('<H', file_data[codec_pos:codec_pos+2])[0]
                    codec_pos += 2
                    
                    # CodecDescription (UTF-16LE) - skip
                    if codec_desc_len > 0:
                        codec_pos += codec_desc_len
                    
                    # CodecInformationLength (2 bytes)
                    if codec_pos + 2 > offset + obj_size:
                        break
                    codec_info_len = struct.unpack('<H', file_data[codec_pos:codec_pos+2])[0]
                    codec_pos += 2
                    
                    # CodecInformation (binary) - skip
                    if codec_info_len > 0:
                        codec_pos += codec_info_len
                    
                    if codec_pos > offset + obj_size:
                        break
                        
        except Exception:
            pass
        
        return metadata
    
    def _calculate_mp3_duration(self, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Calculate MP3 duration from file size and bitrate.
        
        Args:
            metadata: Existing metadata dictionary
            
        Returns:
            Formatted duration string or None
        """
        try:
            if not self.file_path:
                return None
            
            import os
            file_size = os.path.getsize(self.file_path)
            
            # Get bitrate from metadata
            bitrate_str = metadata.get('Audio:MP3:AudioBitrate', '')
            if not bitrate_str:
                return None
            
            # Extract bitrate value (e.g., "128 kbps" -> 128)
            import re
            match = re.search(r'(\d+)', bitrate_str)
            if not match:
                return None
            
            bitrate_kbps = int(match.group(1))
            if bitrate_kbps <= 0:
                return None
            
            # Calculate duration: file_size (bytes) * 8 (bits) / bitrate (kbps) / 1000
            # For MP3, we need to account for ID3 tags at the beginning
            # Estimate audio data size (subtract ID3 tag size if present)
            audio_size = file_size
            if self.file_data and self.file_data.startswith(b'ID3'):
                if len(self.file_data) >= 10:
                    size_bytes = self.file_data[6:10]
                    id3_size = (size_bytes[0] << 21) | (size_bytes[1] << 14) | (size_bytes[2] << 7) | size_bytes[3]
                    audio_size = max(0, file_size - 10 - id3_size)
            
            if audio_size <= 0:
                return None
            
            # Duration in seconds
            duration_sec = (audio_size * 8) / (bitrate_kbps * 1000)
            
            # Format duration
            return self._format_duration(duration_sec)
        except Exception:
            return None
    
    def _calculate_wav_duration(self, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Calculate WAV duration from file size, sample rate, channels, and bits per sample.
        
        Args:
            metadata: Existing metadata dictionary
            
        Returns:
            Formatted duration string or None
        """
        try:
            if not self.file_path:
                return None
            
            import os
            file_size = os.path.getsize(self.file_path)
            
            # Get audio parameters from metadata
            sample_rate_str = metadata.get('Audio:WAV:SampleRate', '')
            num_channels = metadata.get('Audio:WAV:NumChannels')
            bits_per_sample = metadata.get('Audio:WAV:BitsPerSample')
            
            if not sample_rate_str or num_channels is None or bits_per_sample is None:
                return None
            
            # Extract sample rate (e.g., "44100 Hz" -> 44100)
            import re
            match = re.search(r'(\d+)', sample_rate_str)
            if not match:
                return None
            
            sample_rate = int(match.group(1))
            if sample_rate <= 0:
                return None
            
            # Find 'data' chunk to get actual audio data size
            # For now, estimate: file_size - header_size (typically ~44 bytes for basic WAV)
            # More accurate: find 'data' chunk and use its size
            wav_data = None
            if self.file_path:
                with open(self.file_path, 'rb') as f:
                    wav_data = f.read()
            
            audio_data_size = 0
            if wav_data and wav_data.startswith(b'RIFF'):
                offset = 12
                while offset < len(wav_data) - 8:
                    chunk_id = wav_data[offset:offset+4]
                    chunk_size = struct.unpack('<I', wav_data[offset+4:offset+8])[0]
                    
                    if chunk_id == b'data':
                        audio_data_size = chunk_size
                        break
                    
                    offset += 8 + chunk_size
                    if chunk_size % 2:
                        offset += 1
            
            if audio_data_size <= 0:
                # Fallback: estimate from file size (subtract typical header size)
                audio_data_size = max(0, file_size - 44)
            
            if audio_data_size <= 0:
                return None
            
            # Calculate duration: audio_data_size (bytes) / (sample_rate * channels * (bits_per_sample / 8))
            bytes_per_sample = bits_per_sample // 8
            bytes_per_second = sample_rate * num_channels * bytes_per_sample
            
            if bytes_per_second <= 0:
                return None
            
            duration_sec = audio_data_size / bytes_per_second
            
            # Format duration
            return self._format_duration(duration_sec)
        except Exception:
            return None
    
    def _calculate_flac_duration(self, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Calculate FLAC duration from total samples and sample rate.
        
        Args:
            metadata: Existing metadata dictionary
            
        Returns:
            Formatted duration string or None
        """
        try:
            # Get total samples and sample rate from STREAMINFO
            total_samples = metadata.get('Audio:FLAC:TotalSamples')
            sample_rate_str = metadata.get('Audio:FLAC:SampleRate', '')
            
            if total_samples is None or not sample_rate_str:
                return None
            
            # Extract sample rate (e.g., "44100 Hz" -> 44100)
            import re
            match = re.search(r'(\d+)', sample_rate_str)
            if not match:
                return None
            
            sample_rate = int(match.group(1))
            if sample_rate <= 0:
                return None
            
            # Calculate duration: total_samples / sample_rate
            duration_sec = total_samples / sample_rate
            
            # Format duration
            return self._format_duration(duration_sec)
        except Exception:
            return None
    
    def _calculate_ogg_duration(self, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Calculate OGG Vorbis duration from file size and bitrate.
        
        Args:
            metadata: Existing metadata dictionary
            
        Returns:
            Formatted duration string or None
        """
        try:
            if not self.file_path:
                return None
            
            import os
            file_size = os.path.getsize(self.file_path)
            
            # Get bitrate from metadata
            bitrate_str = metadata.get('Audio:OGG:NominalBitrate', '')
            if not bitrate_str:
                return None
            
            # Extract bitrate value (e.g., "128000 bps" -> 128000)
            import re
            match = re.search(r'(\d+)', bitrate_str)
            if not match:
                return None
            
            bitrate_bps = int(match.group(1))
            if bitrate_bps <= 0:
                return None
            
            # Calculate duration: file_size (bytes) * 8 (bits) / bitrate (bps)
            duration_sec = (file_size * 8) / bitrate_bps
            
            # Format duration
            return self._format_duration(duration_sec)
        except Exception:
            return None
    
    def _calculate_opus_duration(self, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Calculate Opus duration from file size and estimated bitrate.
        
        Args:
            metadata: Existing metadata dictionary
            
        Returns:
            Formatted duration string or None
        """
        try:
            if not self.file_path:
                return None
            
            import os
            file_size = os.path.getsize(self.file_path)
            
            # Opus files typically have variable bitrate, so we estimate
            # Common Opus bitrates: 64-128 kbps for music
            # For more accuracy, we could parse Opus packets, but that's complex
            # Use a reasonable estimate: 96 kbps average
            estimated_bitrate_kbps = 96
            
            # Calculate duration: file_size (bytes) * 8 (bits) / bitrate (kbps) / 1000
            duration_sec = (file_size * 8) / (estimated_bitrate_kbps * 1000)
            
            # Format duration
            return self._format_duration(duration_sec)
        except Exception:
            return None
    
    def _format_duration(self, seconds: float) -> str:
        """
        Format duration in seconds to standard format format.
        
        Standard format uses:
        - "0 s" for zero durations
        - "HH:MM:SS" format for durations >= 60 seconds
        - "X.XX s" format for durations < 60 seconds
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Formatted duration string
        """
        if seconds == 0:
            return "0 s"
        
        # For durations >= 60 seconds, use HH:MM:SS format
        if seconds >= 60:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours}:{minutes:02d}:{secs:02d}"
        
        # For durations < 60 seconds, use decimal format with 2 decimal places
        return f"{seconds:.2f} s"
    
    def _parse_dsf(self) -> Dict[str, Any]:
        """
        Parse DSF (DSD Stream File) metadata.
        
        DSF files contain DSD (Direct Stream Digital) audio data.
        Structure:
        - Header: "DSD " (4 bytes)
        - File size (8 bytes, big-endian)
        - fmt chunk (format chunk)
        - data chunk (audio data)
        - Optional: ID3v2 tag at end of file
        
        Returns:
            Dictionary containing DSF metadata
        """
        metadata = {}
        metadata['File:FileType'] = 'DSF'
        metadata['File:FileTypeExtension'] = 'dsf'
        metadata['File:MIMEType'] = 'audio/dsd'
        
        try:
            if not self.file_data or len(self.file_data) < 12:
                return metadata
            
            # Check DSF signature
            if self.file_data[:4] != b'DSD ':
                return metadata
            
            metadata['DSF:Format'] = 'DSD Stream File'
            metadata['DSF:HasDSFHeader'] = True
            
            # Read file size (bytes 4-11, big-endian, 8 bytes)
            if len(self.file_data) >= 12:
                file_size = struct.unpack('>Q', self.file_data[4:12])[0]
                metadata['DSF:FileSize'] = file_size
                metadata['File:FileSize'] = file_size
                metadata['File:FileSizeBytes'] = file_size
            
            # Parse chunks starting at offset 12
            offset = 12
            
            while offset < len(self.file_data) - 8:
                # Read chunk header (12 bytes):
                # - Chunk ID (4 bytes, ASCII)
                # - Chunk size (8 bytes, big-endian)
                
                if offset + 12 > len(self.file_data):
                    break
                
                chunk_id = self.file_data[offset:offset+4]
                chunk_size = struct.unpack('>Q', self.file_data[offset+4:offset+12])[0]
                
                offset += 12
                
                # Validate chunk size
                if chunk_size < 0 or offset + chunk_size > len(self.file_data):
                    break
                
                chunk_data = self.file_data[offset:offset+chunk_size]
                
                # Parse chunk based on ID
                if chunk_id == b'fmt ':
                    # Format chunk - contains DSD format information
                    fmt_metadata = self._parse_dsf_fmt_chunk(chunk_data)
                    if fmt_metadata:
                        metadata.update(fmt_metadata)
                
                elif chunk_id == b'data':
                    # Data chunk - contains DSD audio data
                    metadata['DSF:DataChunkSize'] = chunk_size
                    metadata['DSF:DataChunkOffset'] = offset
                    # Data chunk size indicates audio data size
                    metadata['DSF:AudioDataSize'] = chunk_size
                
                elif chunk_id == b'ID3 ':
                    # ID3v2 tag chunk (optional)
                    # Try to parse ID3 tag
                    try:
                        id3_metadata = self._parse_id3v2_tag(chunk_data)
                        if id3_metadata:
                            metadata.update(id3_metadata)
                    except Exception:
                        pass
                
                offset += chunk_size
            
            # Calculate duration if we have sample rate and file size
            if 'DSF:SampleRate' in metadata and 'DSF:AudioDataSize' in metadata:
                sample_rate = metadata['DSF:SampleRate']
                audio_size = metadata['DSF:AudioDataSize']
                # DSD is 1 bit per sample, so samples = audio_size * 8
                # Duration = samples / sample_rate
                if sample_rate > 0:
                    samples = audio_size * 8
                    duration = samples / sample_rate
                    metadata['DSF:Duration'] = duration
                    metadata['Audio:Duration'] = duration
                    metadata['Audio:DurationSeconds'] = duration
        
        except Exception as e:
            if not self.ignore_minor_errors:
                raise MetadataReadError(f"Failed to parse DSF metadata: {str(e)}") from e
        
        return metadata
    
    def _parse_aac(self) -> Dict[str, Any]:
        """
        Parse AAC (Advanced Audio Coding) metadata.
        
        AAC files can be in two formats:
        - ADIF (Audio Data Interchange Format) - starts with 'ADIF'
        - ADTS (Audio Data Transport Stream) - starts with sync word 0xFFF
        
        Returns:
            Dictionary containing AAC metadata
        """
        metadata = {}
        metadata['File:FileType'] = 'AAC'
        metadata['File:FileTypeExtension'] = 'aac'
        metadata['File:MIMEType'] = 'audio/aac'
        metadata['Audio:Format'] = 'AAC'
        
        try:
            if not self.file_data:
                return metadata
            
            # Check if it's ADIF format
            if self.file_data.startswith(b'ADIF'):
                metadata['AAC:Format'] = 'ADIF'
                metadata['AAC:HasADIF'] = True
                
                # Parse ADIF header
                # ADIF header structure (minimum 32 bytes):
                # - ADIF signature: 4 bytes ('ADIF')
                # - Copyright ID present: 1 bit
                # - Original copy: 1 bit
                # - Home: 1 bit
                # - Bitstream type: 1 bit (0=Main, 1=LC)
                # - Bitrate: 23 bits (variable bitrate = 0)
                # - Number of AAC frames: 4 bits
                # - Buffer fullness: 20 bits
                # - Copyright ID: 72 bits (if present)
                # - ADIF CRC: 16 bits (if CRC present)
                
                if len(self.file_data) >= 32:
                    # Read copyright ID present flag (bit 0 of byte 4)
                    copyright_id_present = (self.file_data[4] & 0x80) != 0
                    metadata['AAC:CopyrightIDPresent'] = copyright_id_present
                    
                    # Read original copy flag (bit 1 of byte 4)
                    original_copy = (self.file_data[4] & 0x40) != 0
                    metadata['AAC:OriginalCopy'] = original_copy
                    
                    # Read home flag (bit 2 of byte 4)
                    home = (self.file_data[4] & 0x20) != 0
                    metadata['AAC:Home'] = home
                    
                    # Read bitstream type (bit 3 of byte 4)
                    bitstream_type = (self.file_data[4] & 0x10) != 0
                    metadata['AAC:BitstreamType'] = 'LC' if bitstream_type else 'Main'
                    
                    # Read bitrate (bits 4-26 of bytes 4-6)
                    # Bitrate is stored in 23 bits, variable bitrate = 0
                    bitrate_bits = ((self.file_data[4] & 0x0F) << 19) | (self.file_data[5] << 11) | (self.file_data[6] << 3) | ((self.file_data[7] & 0xE0) >> 5)
                    if bitrate_bits > 0:
                        metadata['AAC:Bitrate'] = bitrate_bits
                        metadata['Audio:Bitrate'] = bitrate_bits
                    else:
                        metadata['AAC:VariableBitrate'] = True
                    
                    # Read number of AAC frames (bits 27-30 of bytes 7-8)
                    num_frames = ((self.file_data[7] & 0x1F) << 1) | ((self.file_data[8] & 0x80) >> 7)
                    if num_frames > 0:
                        metadata['AAC:NumberOfFrames'] = num_frames
                    
                    # Read buffer fullness (bits 31-50 of bytes 8-10)
                    buffer_fullness = ((self.file_data[8] & 0x7F) << 13) | (self.file_data[9] << 5) | ((self.file_data[10] & 0xF8) >> 3)
                    if buffer_fullness > 0:
                        metadata['AAC:BufferFullness'] = buffer_fullness
            
            # Check if it's ADTS format
            elif len(self.file_data) >= 7 and self.file_data[0] == 0xFF and (self.file_data[1] & 0xF0) == 0xF0:
                metadata['AAC:Format'] = 'ADTS'
                metadata['AAC:HasADTS'] = True
                
                # Parse ADTS frame header (7 bytes)
                # ADTS frame header structure:
                # - Sync word: 12 bits (0xFFF)
                # - MPEG version: 1 bit (0=MPEG-4, 1=MPEG-2)
                # - Layer: 2 bits (always 00 for AAC)
                # - Protection absent: 1 bit (0=CRC present, 1=no CRC)
                # - Profile: 2 bits (0=Main, 1=LC, 2=SSR, 3=LTP)
                # - Sampling frequency index: 4 bits
                # - Private bit: 1 bit
                # - Channel configuration: 3 bits
                # - Original/copy: 1 bit
                # - Home: 1 bit
                # - Copyright ID bit: 1 bit
                # - Copyright ID start: 1 bit
                # - Frame length: 13 bits
                # - Buffer fullness: 11 bits
                # - Number of AAC frames: 2 bits
                # - CRC: 16 bits (if protection absent = 0)
                
                # Sync word check (already verified)
                sync_word = ((self.file_data[0] << 4) | (self.file_data[1] >> 4)) & 0xFFF
                if sync_word == 0xFFF:
                    # MPEG version (bit 3 of byte 1)
                    mpeg_version = (self.file_data[1] >> 3) & 0x01
                    metadata['AAC:MPEGVersion'] = 'MPEG-2' if mpeg_version else 'MPEG-4'
                    
                    # Layer (bits 1-2 of byte 1)
                    layer = (self.file_data[1] >> 1) & 0x03
                    metadata['AAC:Layer'] = layer
                    
                    # Protection absent (bit 0 of byte 1)
                    protection_absent = (self.file_data[1] & 0x01) != 0
                    metadata['AAC:ProtectionAbsent'] = protection_absent
                    
                    # Profile (bits 6-7 of byte 2)
                    profile = (self.file_data[2] >> 6) & 0x03
                    profile_names = {0: 'Main', 1: 'LC', 2: 'SSR', 3: 'LTP'}
                    if profile in profile_names:
                        metadata['AAC:Profile'] = profile_names[profile]
                    
                    # Sampling frequency index (bits 2-5 of byte 2)
                    sample_freq_index = (self.file_data[2] >> 2) & 0x0F
                    sample_rates = {
                        0: 96000, 1: 88200, 2: 64000, 3: 48000, 4: 44100, 5: 32000,
                        6: 24000, 7: 22050, 8: 16000, 9: 12000, 10: 11025, 11: 8000
                    }
                    if sample_freq_index in sample_rates:
                        metadata['AAC:SampleRate'] = sample_rates[sample_freq_index]
                        metadata['Audio:SampleRate'] = sample_rates[sample_freq_index]
                    
                    # Channel configuration (bits 7-9 of byte 3, but byte 3 bits 0-1 are part of it)
                    channel_config = ((self.file_data[2] & 0x01) << 2) | ((self.file_data[3] >> 6) & 0x03)
                    metadata['AAC:ChannelConfiguration'] = channel_config
                    channel_names = {
                        0: 'Defined in AOT', 1: 'Mono', 2: 'Stereo', 3: '3 channels',
                        4: '4 channels', 5: '5 channels', 6: '5.1', 7: '7.1'
                    }
                    if channel_config in channel_names:
                        metadata['AAC:ChannelConfigurationName'] = channel_names[channel_config]
                    if channel_config > 0:
                        metadata['Audio:Channels'] = channel_config
                    
                    # Frame length (bits 3-15 of bytes 3-4)
                    frame_length = ((self.file_data[3] & 0x03) << 11) | (self.file_data[4] << 3) | ((self.file_data[5] >> 5) & 0x07)
                    if frame_length > 0:
                        metadata['AAC:FrameLength'] = frame_length
                    
                    # Buffer fullness (bits 5-15 of bytes 5-6)
                    buffer_fullness = ((self.file_data[5] & 0x1F) << 6) | ((self.file_data[6] >> 2) & 0x3F)
                    if buffer_fullness > 0:
                        metadata['AAC:BufferFullness'] = buffer_fullness
                    
                    # Number of AAC frames (bits 0-1 of byte 6)
                    num_frames = self.file_data[6] & 0x03
                    if num_frames > 0:
                        metadata['AAC:NumberOfFrames'] = num_frames + 1  # ADTS stores frames-1
            
            # Calculate file size
            if self.file_path:
                try:
                    file_size = self.file_path.stat().st_size
                    metadata['File:FileSize'] = file_size
                except Exception:
                    pass
        
        except Exception as e:
            if not self.ignore_minor_errors:
                raise MetadataReadError(f"Failed to parse AAC metadata: {str(e)}") from e
        
        return metadata
    
    def _parse_dsf_fmt_chunk(self, chunk_data: bytes) -> Dict[str, Any]:
        """
        Parse DSF format chunk.
        
        Format chunk structure:
        - Format version (4 bytes, big-endian)
        - Format ID (4 bytes, big-endian) - usually 1 for DSD
        - Channel type (4 bytes, big-endian) - 1=mono, 2=stereo, 5=5.1, 7=7.1
        - Channel number (4 bytes, big-endian)
        - Sample rate (4 bytes, big-endian) - e.g., 2822400, 5644800, 11289600
        - Bits per sample (4 bytes, big-endian) - usually 1 for DSD
        - Sample count (8 bytes, big-endian)
        - Block size per channel (4 bytes, big-endian) - usually 4096
        - Reserved (4 bytes)
        
        Args:
            chunk_data: Format chunk data bytes
            
        Returns:
            Dictionary containing format metadata
        """
        metadata = {}
        
        try:
            if len(chunk_data) < 52:
                return metadata
            
            # Format version (bytes 0-3, big-endian)
            format_version = struct.unpack('>I', chunk_data[0:4])[0]
            metadata['DSF:FormatVersion'] = format_version
            
            # Format ID (bytes 4-7, big-endian) - 1 = DSD
            format_id = struct.unpack('>I', chunk_data[4:8])[0]
            metadata['DSF:FormatID'] = format_id
            if format_id == 1:
                metadata['DSF:Format'] = 'DSD'
            
            # Channel type (bytes 8-11, big-endian)
            channel_type = struct.unpack('>I', chunk_data[8:12])[0]
            metadata['DSF:ChannelType'] = channel_type
            channel_names = {
                1: 'Mono',
                2: 'Stereo',
                5: '5.1',
                7: '7.1',
            }
            if channel_type in channel_names:
                metadata['DSF:ChannelTypeName'] = channel_names[channel_type]
            
            # Channel number (bytes 12-15, big-endian)
            channel_number = struct.unpack('>I', chunk_data[12:16])[0]
            metadata['DSF:ChannelNumber'] = channel_number
            metadata['Audio:Channels'] = channel_number
            
            # Sample rate (bytes 16-19, big-endian)
            sample_rate = struct.unpack('>I', chunk_data[16:20])[0]
            metadata['DSF:SampleRate'] = sample_rate
            metadata['Audio:SampleRate'] = sample_rate
            
            # Bits per sample (bytes 20-23, big-endian)
            bits_per_sample = struct.unpack('>I', chunk_data[20:24])[0]
            metadata['DSF:BitsPerSample'] = bits_per_sample
            metadata['Audio:BitsPerSample'] = bits_per_sample
            
            # Sample count (bytes 24-31, big-endian, 8 bytes)
            sample_count = struct.unpack('>Q', chunk_data[24:32])[0]
            metadata['DSF:SampleCount'] = sample_count
            
            # Block size per channel (bytes 32-35, big-endian)
            block_size = struct.unpack('>I', chunk_data[32:36])[0]
            metadata['DSF:BlockSizePerChannel'] = block_size
            
            # Reserved (bytes 36-39, big-endian)
            reserved = struct.unpack('>I', chunk_data[36:40])[0]
            metadata['DSF:Reserved'] = reserved
            
            # Calculate bitrate
            if sample_rate > 0 and channel_number > 0:
                # DSD bitrate = sample_rate * channels * bits_per_sample
                bitrate = sample_rate * channel_number * bits_per_sample
                metadata['DSF:Bitrate'] = bitrate
                metadata['Audio:Bitrate'] = bitrate
        
        except Exception:
            pass
        
        return metadata
    
    def _read_entire_file(self) -> bytes:
        """Read the entire file into memory when precise parsing is needed."""
        if self.file_path:
            with open(self.file_path, 'rb') as f:
                data = f.read()
                self.file_data = data
                return data
        return self.file_data or b''
