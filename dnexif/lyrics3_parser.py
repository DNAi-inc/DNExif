# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Lyrics3 metadata parser

This module handles reading Lyrics3 metadata from MP3 files.
Lyrics3 metadata is stored at the end of MP3 files, before the ID3v1 tag.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class Lyrics3Parser:
    """
    Parser for Lyrics3 metadata.
    
    Lyrics3 metadata is stored at the end of MP3 files, before the ID3v1 tag.
    Formats:
    - Lyrics3 v1.00: Fixed-length format (5100 bytes)
    - Lyrics3 v2.00: Variable-length format
    """
    
    # Lyrics3 signatures
    LYRICS3_V1_SIGNATURE = b'LYRICSBEGIN'
    LYRICS3_V2_SIGNATURE = b'LYRICS200'
    LYRICS3_V1_END = b'LYRICSEND'
    LYRICS3_V2_END = b'LYRICS200'
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize Lyrics3 parser.
        
        Args:
            file_path: Path to MP3 file
            file_data: MP3 file data bytes
        """
        if file_path:
            self.file_path = Path(file_path)
            self.file_data = None
        elif file_data:
            self.file_data = file_data
            self.file_path = None
        else:
            raise ValueError("Either file_path or file_data must be provided")
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse Lyrics3 metadata.
        
        Returns:
            Dictionary of Lyrics3 metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 20:
                return {}  # No Lyrics3 metadata if file is too short
            
            metadata = {}
            
            # Lyrics3 is stored at the end of MP3 files, before ID3v1 tag
            # ID3v1 tag is 128 bytes, so Lyrics3 should be before that
            # Search backwards from the end
            
            # Check for Lyrics3 v2.00 (variable-length)
            # Lyrics3 v2.00 format: LYRICS200 (9) + size (9) + fields (N) + size (9) + LYRICS200 (9)
            # Size field value = fields_length + 9 (size field itself)
            # Total block = 9 + 9 + fields_length + 9 + 9 = fields_length + 36 = (size - 9) + 36 = size + 27
            lyrics3_v2_end_pos = file_data.rfind(self.LYRICS3_V2_END)
            if lyrics3_v2_end_pos != -1 and lyrics3_v2_end_pos >= 9:
                # Found Lyrics3 v2.00 end marker
                # Read size field (9 digits before end marker)
                size_str = file_data[lyrics3_v2_end_pos - 9:lyrics3_v2_end_pos].decode('ascii', errors='ignore')
                try:
                    lyrics3_size = int(size_str)
                    # Total Lyrics3 block size = size + 27 (9 start + 9 size + fields + 9 size + 9 end)
                    lyrics3_total_size = lyrics3_size + 27
                    lyrics3_start = lyrics3_v2_end_pos - lyrics3_total_size + 9
                    
                    if lyrics3_start >= 0 and lyrics3_start < len(file_data):
                        # Check for Lyrics3 v2.00 start marker
                        if file_data[lyrics3_start:lyrics3_start + 9] == self.LYRICS3_V2_SIGNATURE:
                            metadata['Lyrics3:Version'] = '2.00'
                            metadata['Lyrics3:HasLyrics3'] = True
                            
                            # Parse Lyrics3 v2.00 fields (between start marker + 9 and end marker - 9)
                            lyrics3_data = file_data[lyrics3_start + 9:lyrics3_v2_end_pos - 9]
                            self._parse_lyrics3_v2(lyrics3_data, metadata)
                except (ValueError, IndexError, UnicodeDecodeError):
                    pass
            
            # Check for Lyrics3 v1.00 (fixed-length, 5100 bytes)
            lyrics3_v1_end_pos = file_data.rfind(self.LYRICS3_V1_END)
            if lyrics3_v1_end_pos != -1 and 'Lyrics3:Version' not in metadata:
                # Lyrics3 v1.00 is 5100 bytes + 9 bytes for end marker = 5109 bytes total
                lyrics3_v1_start = lyrics3_v1_end_pos - 5100
                
                if lyrics3_v1_start >= 0 and lyrics3_v1_start < len(file_data):
                    # Check for Lyrics3 v1.00 start marker
                    if file_data[lyrics3_v1_start:lyrics3_v1_start + 11] == self.LYRICS3_V1_SIGNATURE:
                        metadata['Lyrics3:Version'] = '1.00'
                        metadata['Lyrics3:HasLyrics3'] = True
                        
                        # Parse Lyrics3 v1.00 fields
                        lyrics3_data = file_data[lyrics3_v1_start + 11:lyrics3_v1_end_pos]
                        self._parse_lyrics3_v1(lyrics3_data, metadata)
            
            return metadata
        
        except Exception as e:
            # Lyrics3 is optional metadata, don't raise error
            return {}
    
    def _parse_lyrics3_v1(self, data: bytes, metadata: Dict[str, Any]) -> None:
        """
        Parse Lyrics3 v1.00 format.
        
        Args:
            data: Lyrics3 v1.00 data (5100 bytes)
            metadata: Metadata dictionary to update
        """
        try:
            # Lyrics3 v1.00 is fixed-length (5100 bytes)
            # Contains lyrics text (null-terminated or space-padded)
            lyrics_text = data[:5100].decode('latin-1', errors='ignore').rstrip('\x00 ').rstrip()
            if lyrics_text:
                metadata['Lyrics3:Lyrics'] = lyrics_text
                metadata['Lyrics3:LyricsLength'] = len(lyrics_text)
        except Exception:
            pass
    
    def _parse_lyrics3_v2(self, data: bytes, metadata: Dict[str, Any]) -> None:
        """
        Parse Lyrics3 v2.00 format.
        
        Args:
            data: Lyrics3 v2.00 data
            metadata: Metadata dictionary to update
        """
        try:
            offset = 0
            
            # Lyrics3 v2.00 uses field format: "XXX=value"
            # Fields are separated by newlines or null bytes
            # Common fields: IND (indicator), INF (info), AUT (author), EAL (album), EAR (artist), ETT (title), LYR (lyrics)
            
            while offset < len(data):
                # Find field separator (=)
                eq_pos = data.find(b'=', offset)
                if eq_pos == -1:
                    break
                
                # Get field name (3 characters before =)
                if eq_pos < 3:
                    offset += 1
                    continue
                
                field_name = data[eq_pos - 3:eq_pos].decode('ascii', errors='ignore')
                field_start = eq_pos + 1
                
                # Find field end (newline, null byte, or next field)
                field_end = len(data)
                for end_marker in [b'\n', b'\r', b'\x00']:
                    end_pos = data.find(end_marker, field_start)
                    if end_pos != -1 and end_pos < field_end:
                        field_end = end_pos
                
                # Extract field value
                field_value = data[field_start:field_end].decode('latin-1', errors='ignore')
                
                # Map field names to metadata tags
                field_map = {
                    'IND': 'Indicator',
                    'INF': 'Info',
                    'AUT': 'Author',
                    'EAL': 'Album',
                    'EAR': 'Artist',
                    'ETT': 'Title',
                    'LYR': 'Lyrics',
                    'IMG': 'Image',
                }
                
                tag_name = field_map.get(field_name, field_name)
                metadata[f'Lyrics3:{tag_name}'] = field_value
                
                offset = field_end + 1
                
                # Limit number of fields to prevent excessive parsing
                if len(metadata) > 50:
                    break
        
        except Exception:
            pass

