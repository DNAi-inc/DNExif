# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
File format detector

This module provides comprehensive file format detection for
various image, video, document, and audio formats.

Copyright 2025 DNAi inc.
"""

from typing import Optional, Dict, Any
from pathlib import Path


class FormatDetector:
    """
    Detects file formats from file signatures and extensions.
    
    Supports detection of image, video, document, and audio formats.
    """
    
    # Format signatures (magic numbers)
    FORMAT_SIGNATURES: Dict[bytes, str] = {
        # Image formats
        b'\xff\xd8\xff': 'JPEG',
        b'II*\x00': 'TIFF',
        b'MM\x00*': 'TIFF',
        b'\x89PNG\r\n\x1a\n': 'PNG',
        b'GIF87a': 'GIF',
        b'GIF89a': 'GIF',
        b'BM': 'BMP',
        b'RIFF': 'WEBP',  # May need more checking
        b'ftyp': 'HEIC',  # May need more checking
        # RAW formats
        b'IIRS': 'CR2',
        b'IIRO': 'CRW',
        b'FUJIFILM': 'RAF',
        # Video formats
        b'ftyp': 'MP4',  # May need more checking
        b'ftypqt': 'MOV',
        # Document formats
        b'%PDF': 'PDF',
        # Audio formats
        b'ID3': 'MP3',
        b'\xff\xfb': 'MP3',
        b'\xff\xf3': 'MP3',
        b'\xff\xf2': 'MP3',
        b'RIFF': 'WAV',  # May need more checking
    }
    
    # Extension to format mapping
    EXTENSION_FORMATS: Dict[str, str] = {
        # Image formats
        '.jpg': 'JPEG', '.jpeg': 'JPEG',
        '.tif': 'TIFF', '.tiff': 'TIFF',
        '.png': 'PNG',
        '.gif': 'GIF',
        '.bmp': 'BMP',
        '.webp': 'WEBP',
        '.heic': 'HEIC', '.heif': 'HEIF',
        # RAW formats
        '.cr2': 'CR2', '.cr3': 'CR3', '.crw': 'CRW',
        '.nef': 'NEF', '.arw': 'ARW', '.dng': 'DNG',
        '.orf': 'ORF', '.raf': 'RAF', '.rw2': 'RW2',
        '.srw': 'SRW', '.pef': 'PEF', '.x3f': 'X3F',
        # Video formats
        '.mp4': 'MP4', '.mov': 'MOV', '.avi': 'AVI',
        '.mkv': 'MKV', '.webm': 'WEBM',
        # Document formats
        '.pdf': 'PDF',
        # Medical imaging formats
        '.dcm': 'DICOM', '.dicom': 'DICOM',
        # Audio formats
        '.mp3': 'MP3', '.wav': 'WAV', '.flac': 'FLAC',
        '.aac': 'AAC', '.ogg': 'OGG',
    }
    
    @classmethod
    def detect_format(cls, file_path: Optional[str] = None, file_data: Optional[bytes] = None) -> Optional[str]:
        """
        Detect file format from file path and/or data.
        
        Args:
            file_path: Path to file
            file_data: File data (first few bytes)
            
        Returns:
            Format name or None if not detected
        """
        # Check extension first
        if file_path:
            ext = Path(file_path).suffix.lower()
            if ext in cls.EXTENSION_FORMATS:
                return cls.EXTENSION_FORMATS[ext]
        
        # Check file signature
        if file_data:
            for signature, format_name in cls.FORMAT_SIGNATURES.items():
                if file_data.startswith(signature):
                    return format_name
        
        return None
    
    @classmethod
    def is_supported_format(cls, format_name: str) -> bool:
        """
        Check if format is supported for metadata operations.
        
        Args:
            format_name: Format name
            
        Returns:
            True if format is supported
        """
        supported = [
            'JPEG', 'TIFF',
            'CR2', 'NEF', 'ARW', 'DNG', 'ORF', 'RAF', 'RW2', 'PEF',
        ]
        return format_name.upper() in supported

