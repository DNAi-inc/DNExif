# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
C2PA Writer - Write and delete C2PA JUMBF metadata from files.

This module provides functionality to write and delete C2PA (Coalition for Content
Provenance and Authenticity) JUMBF metadata from various file formats.
"""

from typing import Optional, Dict, Any
from pathlib import Path
import struct

from dnexif.exceptions import MetadataWriteError


class C2PAWriter:
    """
    Writer for C2PA JUMBF metadata.
    
    Provides functionality to delete C2PA metadata from files.
    Writing C2PA metadata is more complex and requires full JUMBF box construction,
    which can be added incrementally.
    """
    
    # C2PA signature patterns
    C2PA_SIGNATURE = b'c2pa'
    CAI_SIGNATURE = b'cai '
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize C2PA writer.
        
        Args:
            file_path: Path to file containing C2PA metadata
            file_data: File data as bytes (alternative to file_path)
        """
        self.file_path = Path(file_path) if file_path else None
        self.file_data = file_data
        
        if not file_path and not file_data:
            raise ValueError("Either file_path or file_data must be provided")
    
    def delete_cai_jumbf_from_png(self, output_path: Optional[str] = None) -> bytes:
        """
        Delete CAI JUMBF metadata from PNG image.
        
        This method removes C2PA/CAI iTXt chunks from PNG files.
        
        Args:
            output_path: Optional output path (if None, returns modified data)
            
        Returns:
            Modified PNG file data bytes with CAI JUMBF metadata removed
            
        Raises:
            MetadataWriteError: If file cannot be read or written
        """
        try:
            # Read file data
            if self.file_data is None:
                if not self.file_path or not self.file_path.exists():
                    raise MetadataWriteError(f"File not found: {self.file_path}")
                with open(self.file_path, 'rb') as f:
                    file_data = bytearray(f.read())
            else:
                file_data = bytearray(self.file_data)
            
            # Check PNG signature
            if not file_data.startswith(b'\x89PNG\r\n\x1a\n'):
                raise MetadataWriteError("Not a valid PNG file")
            
            # Parse PNG chunks and remove C2PA/CAI iTXt chunks
            offset = 8  # Skip PNG signature
            
            chunks_to_remove = []
            
            while offset < len(file_data) - 8:
                # Read chunk length (4 bytes, big-endian)
                if offset + 4 > len(file_data):
                    break
                chunk_length = struct.unpack('>I', file_data[offset:offset + 4])[0]
                offset += 4
                
                # Read chunk type (4 bytes)
                if offset + 4 > len(file_data):
                    break
                chunk_type = file_data[offset:offset + 4]
                offset += 4
                
                # Read chunk data
                if offset + chunk_length + 4 > len(file_data):
                    break
                chunk_data = file_data[offset:offset + chunk_length]
                offset += chunk_length
                
                # Read CRC (4 bytes)
                crc = file_data[offset:offset + 4]
                offset += 4
                
                # Check if this is an iTXt chunk with C2PA/CAI keyword
                if chunk_type == b'iTXt':
                    # iTXt format: keyword (null-terminated), compression flag, compression method, language tag, translated keyword, text
                    keyword_end = chunk_data.find(b'\x00')
                    if keyword_end > 0:
                        keyword = chunk_data[:keyword_end].decode('ascii', errors='ignore').lower()
                        
                        # Check if this is a C2PA/CAI chunk
                        if keyword in ('c2pa', 'cai', 'jumbf'):
                            # Mark this chunk for removal
                            chunk_start = offset - 8 - chunk_length - 4  # Start of chunk (length + type + data + CRC)
                            chunks_to_remove.append((chunk_start, offset - chunk_start))
                
                # Stop at IEND chunk
                if chunk_type == b'IEND':
                    break
            
            # Remove chunks in reverse order to maintain offsets
            for chunk_start, chunk_length in reversed(chunks_to_remove):
                del file_data[chunk_start:chunk_start + chunk_length]
            
            # Write output if path provided
            if output_path:
                with open(output_path, 'wb') as f:
                    f.write(file_data)
            
            return bytes(file_data)
            
        except Exception as e:
            raise MetadataWriteError(f"Failed to delete CAI JUMBF metadata: {str(e)}")
    
    def delete_c2pa_metadata(self, output_path: Optional[str] = None) -> bytes:
        """
        Delete C2PA metadata from file (format-agnostic wrapper).
        
        Currently supports PNG files. Other formats can be added incrementally.
        
        Args:
            output_path: Optional output path (if None, returns modified data)
            
        Returns:
            Modified file data bytes with C2PA metadata removed
        """
        if self.file_path:
            ext = self.file_path.suffix.lower()
            if ext == '.png':
                return self.delete_cai_jumbf_from_png(output_path)
            else:
                raise MetadataWriteError(f"C2PA deletion not yet implemented for {ext} format")
        else:
            # Try to detect format from file data
            if self.file_data and self.file_data.startswith(b'\x89PNG\r\n\x1a\n'):
                return self.delete_cai_jumbf_from_png(output_path)
            else:
                raise MetadataWriteError("C2PA deletion not yet implemented for this format")

