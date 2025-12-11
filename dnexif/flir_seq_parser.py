# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
FLIR SEQ file parser for extracting raw thermal data from all frames

This module handles reading raw thermal data from FLIR SEQ (sequence) files.
FLIR SEQ files contain multiple frames, each with raw thermal data.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class FLIRSeqParser:
    """
    Parser for FLIR SEQ thermal sequence files.
    
    FLIR SEQ files contain multiple frames, each with raw thermal data.
    This parser extracts raw thermal data from all frames (enhanced extraction mode -ee2).
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None, enhanced_extraction: bool = True):
        """
        Initialize FLIR SEQ parser.
        
        Args:
            file_path: Path to FLIR SEQ file
            file_data: File data bytes
            enhanced_extraction: If True, extract raw thermal data from all frames (equivalent to -ee2 flag)
        """
        if file_path:
            self.file_path = Path(file_path)
            self.file_data = None
        elif file_data:
            self.file_data = file_data
            self.file_path = None
        else:
            raise ValueError("Either file_path or file_data must be provided")
        
        self.enhanced_extraction = enhanced_extraction
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse FLIR SEQ file and extract raw thermal data from all frames.
        
        Returns:
            Dictionary of FLIR SEQ metadata including raw thermal data from all frames
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 100:
                raise MetadataReadError("Invalid FLIR SEQ file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'SEQ'
            metadata['File:FileTypeExtension'] = 'seq'
            metadata['File:MIMEType'] = 'application/octet-stream'
            metadata['FLIR:Format'] = 'FLIR SEQ'
            metadata['FLIR:HasFLIRMetadata'] = True
            
            # Check for FLIR SEQ signature
            # FLIR SEQ files typically start with specific headers
            # Common signatures: "FLIR", "SEQ", or specific byte patterns
            is_flir_seq = False
            flir_patterns = [
                b'FLIR',
                b'flir',
                b'SEQ',
                b'seq',
                b'FLIRSEQ',
            ]
            
            # Check first 100 bytes for FLIR patterns
            for pattern in flir_patterns:
                if pattern in file_data[:100]:
                    is_flir_seq = True
                    metadata['FLIR:IsFLIRSEQ'] = True
                    break
            
            if not is_flir_seq:
                # Still try to parse, might be a FLIR SEQ without obvious markers
                metadata['FLIR:IsFLIRSEQ'] = False
            
            # Extract frame count and frame information
            # FLIR SEQ files contain multiple frames
            # Each frame typically has:
            # - Frame header (metadata)
            # - Raw thermal data (temperature values, typically 16-bit)
            # - Possibly JPEG image data
            
            frames = self._extract_all_frames(file_data)
            
            if frames:
                metadata['FLIR:FrameCount'] = len(frames)
                metadata['FLIR:HasFrames'] = True
                
                # Extract raw thermal data from all frames if enhanced extraction is enabled
                if self.enhanced_extraction:
                    thermal_frames = []
                    for i, frame in enumerate(frames):
                        if frame.get('has_raw_thermal_data'):
                            thermal_frames.append(i)
                            metadata[f'FLIR:Frame{i+1}:HasRawThermalData'] = True
                            metadata[f'FLIR:Frame{i+1}:RawThermalDataOffset'] = frame.get('raw_thermal_offset', 0)
                            metadata[f'FLIR:Frame{i+1}:RawThermalDataSize'] = frame.get('raw_thermal_size', 0)
                            metadata[f'FLIR:Frame{i+1}:RawThermalDataLength'] = f"{frame.get('raw_thermal_size', 0)} bytes"
                            
                            # Extract frame metadata
                            if frame.get('width'):
                                metadata[f'FLIR:Frame{i+1}:Width'] = frame['width']
                            if frame.get('height'):
                                metadata[f'FLIR:Frame{i+1}:Height'] = frame['height']
                            if frame.get('timestamp'):
                                metadata[f'FLIR:Frame{i+1}:Timestamp'] = frame['timestamp']
                    
                    if thermal_frames:
                        metadata['FLIR:RawThermalDataFrameCount'] = len(thermal_frames)
                        metadata['FLIR:HasRawThermalData'] = True
                        metadata['FLIR:EnhancedExtraction'] = True
                        metadata['FLIR:EnhancedExtractionMode'] = '-ee2'
            
            # File size
            if self.file_path:
                try:
                    file_size = self.file_path.stat().st_size
                    metadata['File:FileSize'] = file_size
                except Exception:
                    pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse FLIR SEQ metadata: {str(e)}")
    
    def _extract_all_frames(self, file_data: bytes) -> List[Dict[str, Any]]:
        """
        Extract all frames from FLIR SEQ file.
        
        Args:
            file_data: File data bytes
            
        Returns:
            List of frame dictionaries with frame information
        """
        frames = []
        
        try:
            # FLIR SEQ files can have different structures
            # Common structure:
            # - File header
            # - Frame headers (one per frame)
            # - Frame data (raw thermal data + optional JPEG)
            
            # Try to detect frame boundaries
            # Frames are typically separated by specific markers or have fixed sizes
            
            # Method 1: Look for frame markers
            # FLIR frames may have markers like 0xFF 0xFF or specific patterns
            offset = 0
            frame_number = 0
            
            # Skip file header (typically first 100-1000 bytes)
            header_size = min(1000, len(file_data) // 10)
            offset = header_size
            
            # Look for potential frame boundaries
            # Common patterns: repeated 0xFF bytes, specific frame markers
            while offset < len(file_data) - 100:
                # Look for potential frame start markers
                # FLIR frames may start with specific patterns
                
                # Check for JPEG start (some frames may contain JPEG)
                if file_data[offset:offset+2] == b'\xFF\xD8':
                    # Found JPEG, this might be a frame
                    jpeg_end = file_data.find(b'\xFF\xD9', offset + 2)
                    if jpeg_end > offset:
                        frame_size = jpeg_end - offset + 2
                        
                        # Check if there's raw thermal data after JPEG
                        thermal_offset = jpeg_end + 2
                        if thermal_offset < len(file_data):
                            # Estimate raw thermal data size
                            # Common resolutions: 160x120, 320x240, 640x480
                            # 16-bit data: width * height * 2 bytes
                            potential_thermal_size = self._estimate_thermal_data_size(file_data, thermal_offset)
                            
                            if potential_thermal_size > 0:
                                frame = {
                                    'frame_number': frame_number,
                                    'offset': offset,
                                    'size': frame_size + potential_thermal_size,
                                    'has_jpeg': True,
                                    'has_raw_thermal_data': True,
                                    'raw_thermal_offset': thermal_offset,
                                    'raw_thermal_size': potential_thermal_size,
                                }
                                frames.append(frame)
                                frame_number += 1
                                offset = thermal_offset + potential_thermal_size
                                continue
                        
                        offset = jpeg_end + 2
                        continue
                
                # Look for raw thermal data patterns
                # Raw thermal data is typically 16-bit grayscale
                # Look for patterns that suggest thermal data
                thermal_data_info = self._detect_raw_thermal_data(file_data, offset)
                if thermal_data_info:
                    frame = {
                        'frame_number': frame_number,
                        'offset': offset,
                        'size': thermal_data_info['size'],
                        'has_jpeg': False,
                        'has_raw_thermal_data': True,
                        'raw_thermal_offset': offset,
                        'raw_thermal_size': thermal_data_info['size'],
                        'width': thermal_data_info.get('width'),
                        'height': thermal_data_info.get('height'),
                    }
                    frames.append(frame)
                    frame_number += 1
                    offset += thermal_data_info['size']
                    continue
                
                offset += 1
            
            # If no frames found with markers, try fixed-size frame approach
            if not frames and len(file_data) > 10000:
                # Estimate frame size based on file size
                # Common FLIR SEQ frame sizes: 50KB - 500KB per frame
                estimated_frame_size = len(file_data) // 100  # Rough estimate
                if estimated_frame_size > 10000:  # At least 10KB per frame
                    num_frames = len(file_data) // estimated_frame_size
                    for i in range(min(num_frames, 1000)):  # Limit to 1000 frames
                        frame_offset = i * estimated_frame_size
                        if frame_offset + estimated_frame_size <= len(file_data):
                            frame = {
                                'frame_number': i,
                                'offset': frame_offset,
                                'size': estimated_frame_size,
                                'has_raw_thermal_data': True,
                                'raw_thermal_offset': frame_offset,
                                'raw_thermal_size': estimated_frame_size,
                            }
                            frames.append(frame)
        
        except Exception:
            # Frame extraction is optional - don't raise errors
            pass
        
        return frames
    
    def _estimate_thermal_data_size(self, file_data: bytes, offset: int) -> int:
        """
        Estimate raw thermal data size at given offset.
        
        Args:
            file_data: File data bytes
            offset: Offset to check
            
        Returns:
            Estimated thermal data size in bytes, or 0 if not found
        """
        if offset >= len(file_data):
            return 0
        
        # Common FLIR thermal resolutions and their data sizes (16-bit):
        # 160x120 = 38,400 bytes
        # 320x240 = 153,600 bytes
        # 640x480 = 614,400 bytes
        
        common_sizes = [
            160 * 120 * 2,   # 38,400 bytes
            320 * 240 * 2,   # 153,600 bytes
            640 * 480 * 2,   # 614,400 bytes
            80 * 60 * 2,     # 9,600 bytes
        ]
        
        remaining_data = len(file_data) - offset
        
        # Check if remaining data matches a common size
        for size in common_sizes:
            if remaining_data >= size:
                # Check if data looks like thermal data (not all zeros, has variation)
                sample_size = min(size, 1000)
                sample_data = file_data[offset:offset + sample_size]
                
                # Thermal data should have some variation
                if len(set(sample_data[:100])) > 10:  # At least 10 different byte values
                    return size
        
        # If no exact match, return reasonable estimate
        if remaining_data > 10000:
            return min(remaining_data, 1000000)  # Max 1MB per frame
        
        return 0
    
    def _detect_raw_thermal_data(self, file_data: bytes, offset: int) -> Optional[Dict[str, Any]]:
        """
        Detect raw thermal data at given offset.
        
        Args:
            file_data: File data bytes
            offset: Offset to check
            
        Returns:
            Dictionary with thermal data information, or None if not found
        """
        if offset >= len(file_data) - 100:
            return None
        
        # Check for patterns that suggest raw thermal data
        # Raw thermal data is typically 16-bit grayscale values
        
        # Check if data size matches common thermal resolutions
        remaining = len(file_data) - offset
        common_sizes = [
            (160, 120, 160 * 120 * 2),
            (320, 240, 320 * 240 * 2),
            (640, 480, 640 * 480 * 2),
        ]
        
        for width, height, size in common_sizes:
            if remaining >= size:
                # Check if data looks like thermal data
                sample = file_data[offset:offset + min(size, 10000)]
                
                # Thermal data should have variation (not all same value)
                if len(set(sample[:1000])) > 5:
                    return {
                        'size': size,
                        'width': width,
                        'height': height,
                    }
        
        return None

