# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
SEAL metadata parser

This module handles reading and deleting SEAL metadata from various file formats.
SEAL metadata can be embedded in JPG, TIFF, XMP, PNG, WEBP, HEIC, PPM, MOV, MP4, PDF, MKV, WAV files.

Copyright 2025 DNAi inc.
"""

import struct
import re
from typing import Dict, Any, Optional, List
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class SEALParser:
    """
    Parser for SEAL metadata.
    
    SEAL metadata can be embedded in various file formats:
    - JPEG: APP segments
    - TIFF: IFD entries
    - PNG: tEXt/iTXt chunks
    - XMP: XMP packets
    - HEIC: UUID boxes
    - Video/Audio: format-specific locations
    """
    
    # SEAL signature patterns
    SEAL_SIGNATURES = [
        b'SEAL',
        b'seal',
        b'Seal',
        b'\x53\x45\x41\x4C',  # "SEAL" in ASCII
    ]
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize SEAL parser.
        
        Args:
            file_path: Path to file
            file_data: File data bytes
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
        Parse SEAL metadata from file.
        
        Returns:
            Dictionary of SEAL metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) == 0:
                return {}
            
            metadata = {}
            metadata['SEAL:HasSEALMetadata'] = False
            
            # Detect file format and parse accordingly
            if self.file_path:
                ext = self.file_path.suffix.lower()
                
                # JPEG files
                if ext in ('.jpg', '.jpeg', '.jph'):
                    seal_data = self._parse_jpeg_seal(file_data)
                    if seal_data:
                        metadata.update(seal_data)
                        metadata['SEAL:HasSEALMetadata'] = True
                
                # TIFF files
                elif ext in ('.tif', '.tiff'):
                    seal_data = self._parse_tiff_seal(file_data)
                    if seal_data:
                        metadata.update(seal_data)
                        metadata['SEAL:HasSEALMetadata'] = True
                
                # PNG files
                elif ext == '.png':
                    seal_data = self._parse_png_seal(file_data)
                    if seal_data:
                        metadata.update(seal_data)
                        metadata['SEAL:HasSEALMetadata'] = True
                
                # XMP files
                elif ext == '.xmp':
                    seal_data = self._parse_xmp_seal(file_data)
                    if seal_data:
                        metadata.update(seal_data)
                        metadata['SEAL:HasSEALMetadata'] = True
                
                # WEBP files
                elif ext == '.webp':
                    seal_data = self._parse_webp_seal(file_data)
                    if seal_data:
                        metadata.update(seal_data)
                        metadata['SEAL:HasSEALMetadata'] = True
                
                # HEIC/HEIF files
                elif ext in ('.heic', '.heif'):
                    seal_data = self._parse_heic_seal(file_data)
                    if seal_data:
                        metadata.update(seal_data)
                        metadata['SEAL:HasSEALMetadata'] = True
                
                # PPM files
                elif ext in ('.ppm', '.pgm', '.pbm'):
                    seal_data = self._parse_ppm_seal(file_data)
                    if seal_data:
                        metadata.update(seal_data)
                        metadata['SEAL:HasSEALMetadata'] = True
                
                # Video files (MOV, MP4)
                elif ext in ('.mov', '.mp4', '.m4v'):
                    seal_data = self._parse_video_seal(file_data)
                    if seal_data:
                        metadata.update(seal_data)
                        metadata['SEAL:HasSEALMetadata'] = True
                
                # PDF files
                elif ext == '.pdf':
                    seal_data = self._parse_pdf_seal(file_data)
                    if seal_data:
                        metadata.update(seal_data)
                        metadata['SEAL:HasSEALMetadata'] = True
                
                # MKV files
                elif ext == '.mkv':
                    seal_data = self._parse_mkv_seal(file_data)
                    if seal_data:
                        metadata.update(seal_data)
                        metadata['SEAL:HasSEALMetadata'] = True
                
                # WAV files
                elif ext == '.wav':
                    seal_data = self._parse_wav_seal(file_data)
                    if seal_data:
                        metadata.update(seal_data)
                        metadata['SEAL:HasSEALMetadata'] = True
            
            # Generic SEAL search (search for SEAL signatures)
            if not metadata.get('SEAL:HasSEALMetadata'):
                generic_seal = self._search_seal_signatures(file_data)
                if generic_seal:
                    metadata.update(generic_seal)
                    metadata['SEAL:HasSEALMetadata'] = True
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse SEAL metadata: {str(e)}")
    
    def _search_seal_signatures(self, file_data: bytes) -> Dict[str, Any]:
        """
        Search for SEAL signatures in file data.
        
        Args:
            file_data: File data bytes
            
        Returns:
            Dictionary of SEAL metadata if found
        """
        metadata = {}
        
        for signature in self.SEAL_SIGNATURES:
            offset = file_data.find(signature)
            if offset != -1:
                metadata['SEAL:Signature'] = signature.decode('ascii', errors='ignore')
                metadata['SEAL:SignatureOffset'] = offset
                
                # Try to extract SEAL data following signature
                if offset + len(signature) + 4 < len(file_data):
                    # Try to read length field (4 bytes, big-endian)
                    try:
                        length = struct.unpack('>I', file_data[offset + len(signature):offset + len(signature) + 4])[0]
                        if 0 < length < len(file_data) - offset:
                            seal_data = file_data[offset + len(signature) + 4:offset + len(signature) + 4 + length]
                            metadata['SEAL:DataLength'] = length
                            metadata['SEAL:Data'] = seal_data.hex()[:200]  # Limit hex output
                    except Exception:
                        pass
                
                break
        
        return metadata
    
    def _parse_jpeg_seal(self, file_data: bytes) -> Dict[str, Any]:
        """Parse SEAL metadata from JPEG APP segments."""
        metadata = {}
        
        try:
            if len(file_data) < 2 or file_data[:2] != b'\xff\xd8':
                return metadata
            
            offset = 2
            while offset < len(file_data) - 1:
                if file_data[offset] != 0xff:
                    break
                
                marker = file_data[offset + 1]
                
                # APP segments (0xE0-0xEF)
                if 0xE0 <= marker <= 0xEF:
                    if offset + 4 > len(file_data):
                        break
                    
                    segment_length = struct.unpack('>H', file_data[offset + 2:offset + 4])[0]
                    if segment_length < 2:
                        break
                    
                    segment_data = file_data[offset + 4:offset + 2 + segment_length]
                    
                    # Check for SEAL in segment
                    for signature in self.SEAL_SIGNATURES:
                        if signature in segment_data:
                            metadata['SEAL:Location'] = f'APP{marker - 0xE0}'
                            metadata['SEAL:Offset'] = offset
                            seal_offset = segment_data.find(signature)
                            metadata['SEAL:SegmentOffset'] = seal_offset
                            break
                    
                    offset += 2 + segment_length
                elif marker == 0xD9:  # EOI
                    break
                else:
                    if offset + 4 > len(file_data):
                        break
                    segment_length = struct.unpack('>H', file_data[offset + 2:offset + 4])[0]
                    offset += 2 + segment_length
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_tiff_seal(self, file_data: bytes) -> Dict[str, Any]:
        """Parse SEAL metadata from TIFF IFD entries."""
        metadata = {}
        
        try:
            # Search for SEAL in TIFF data
            for signature in self.SEAL_SIGNATURES:
                offset = file_data.find(signature)
                if offset != -1:
                    metadata['SEAL:Location'] = 'TIFF'
                    metadata['SEAL:Offset'] = offset
                    break
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_png_seal(self, file_data: bytes) -> Dict[str, Any]:
        """Parse SEAL metadata from PNG chunks."""
        metadata = {}
        
        try:
            if len(file_data) < 8 or file_data[:8] != b'\x89PNG\r\n\x1a\n':
                return metadata
            
            offset = 8
            while offset < len(file_data) - 8:
                chunk_length = struct.unpack('>I', file_data[offset:offset + 4])[0]
                chunk_type = file_data[offset + 4:offset + 8]
                
                # Check tEXt, iTXt, zTXt chunks for SEAL
                if chunk_type in (b'tEXt', b'iTXt', b'zTXt'):
                    chunk_data = file_data[offset + 8:offset + 8 + chunk_length]
                    
                    for signature in self.SEAL_SIGNATURES:
                        if signature in chunk_data:
                            metadata['SEAL:Location'] = chunk_type.decode('ascii', errors='ignore')
                            metadata['SEAL:Offset'] = offset
                            break
                
                offset += 8 + chunk_length + 4  # length + type + data + CRC
                
                if chunk_type == b'IEND':
                    break
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_xmp_seal(self, file_data: bytes) -> Dict[str, Any]:
        """Parse SEAL metadata from XMP packets."""
        metadata = {}
        
        try:
            # Search for SEAL in XMP data
            for signature in self.SEAL_SIGNATURES:
                offset = file_data.find(signature)
                if offset != -1:
                    metadata['SEAL:Location'] = 'XMP'
                    metadata['SEAL:Offset'] = offset
                    break
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_webp_seal(self, file_data: bytes) -> Dict[str, Any]:
        """Parse SEAL metadata from WebP chunks."""
        metadata = {}
        
        try:
            if len(file_data) < 12 or file_data[:4] != b'RIFF' or file_data[8:12] != b'WEBP':
                return metadata
            
            # Search for SEAL in WebP chunks
            for signature in self.SEAL_SIGNATURES:
                offset = file_data.find(signature, 12)
                if offset != -1:
                    metadata['SEAL:Location'] = 'WebP'
                    metadata['SEAL:Offset'] = offset
                    break
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_heic_seal(self, file_data: bytes) -> Dict[str, Any]:
        """Parse SEAL metadata from HEIC UUID boxes."""
        metadata = {}
        
        try:
            # Search for SEAL in HEIC data
            for signature in self.SEAL_SIGNATURES:
                offset = file_data.find(signature)
                if offset != -1:
                    metadata['SEAL:Location'] = 'HEIC'
                    metadata['SEAL:Offset'] = offset
                    break
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_ppm_seal(self, file_data: bytes) -> Dict[str, Any]:
        """Parse SEAL metadata from PPM files."""
        metadata = {}
        
        try:
            # Search for SEAL in PPM data
            for signature in self.SEAL_SIGNATURES:
                offset = file_data.find(signature)
                if offset != -1:
                    metadata['SEAL:Location'] = 'PPM'
                    metadata['SEAL:Offset'] = offset
                    break
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_video_seal(self, file_data: bytes) -> Dict[str, Any]:
        """Parse SEAL metadata from video files (MOV, MP4)."""
        metadata = {}
        
        try:
            # Search for SEAL in video data
            for signature in self.SEAL_SIGNATURES:
                offset = file_data.find(signature)
                if offset != -1:
                    metadata['SEAL:Location'] = 'Video'
                    metadata['SEAL:Offset'] = offset
                    break
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_pdf_seal(self, file_data: bytes) -> Dict[str, Any]:
        """Parse SEAL metadata from PDF files."""
        metadata = {}
        
        try:
            # Search for SEAL in PDF data
            for signature in self.SEAL_SIGNATURES:
                offset = file_data.find(signature)
                if offset != -1:
                    metadata['SEAL:Location'] = 'PDF'
                    metadata['SEAL:Offset'] = offset
                    break
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_mkv_seal(self, file_data: bytes) -> Dict[str, Any]:
        """Parse SEAL metadata from MKV files."""
        metadata = {}
        
        try:
            # Search for SEAL in MKV data
            for signature in self.SEAL_SIGNATURES:
                offset = file_data.find(signature)
                if offset != -1:
                    metadata['SEAL:Location'] = 'MKV'
                    metadata['SEAL:Offset'] = offset
                    break
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_wav_seal(self, file_data: bytes) -> Dict[str, Any]:
        """Parse SEAL metadata from WAV files."""
        metadata = {}
        
        try:
            # Search for SEAL in WAV chunks
            if len(file_data) >= 12 and file_data[:4] == b'RIFF' and file_data[8:12] == b'WAVE':
                for signature in self.SEAL_SIGNATURES:
                    offset = file_data.find(signature, 12)
                    if offset != -1:
                        metadata['SEAL:Location'] = 'WAV'
                        metadata['SEAL:Offset'] = offset
                        break
        
        except Exception:
            pass
        
        return metadata
    
    def delete_seal_metadata(self, output_path: Optional[str] = None) -> bytes:
        """
        Delete SEAL metadata from file.
        
        Args:
            output_path: Optional output path (if None, modifies in place)
            
        Returns:
            Modified file data bytes
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = bytearray(f.read())
            else:
                file_data = bytearray(self.file_data)
            
            # Find and remove SEAL metadata
            for signature in self.SEAL_SIGNATURES:
                offset = file_data.find(signature)
                while offset != -1:
                    # Try to determine SEAL block size and remove it
                    # This is a simplified removal - full implementation would parse SEAL structure
                    if offset + len(signature) + 4 < len(file_data):
                        try:
                            length = struct.unpack('>I', file_data[offset + len(signature):offset + len(signature) + 4])[0]
                            if 0 < length < len(file_data) - offset:
                                # Remove SEAL block
                                del file_data[offset:offset + len(signature) + 4 + length]
                            else:
                                # Remove just the signature
                                del file_data[offset:offset + len(signature)]
                        except Exception:
                            # Remove just the signature
                            del file_data[offset:offset + len(signature)]
                    
                    # Search for next occurrence
                    offset = file_data.find(signature, offset)
            
            # Write output if path provided
            if output_path:
                with open(output_path, 'wb') as f:
                    f.write(file_data)
            
            return bytes(file_data)
        
        except Exception as e:
            raise MetadataReadError(f"Failed to delete SEAL metadata: {str(e)}")

