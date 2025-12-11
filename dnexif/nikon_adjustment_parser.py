# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Nikon NKA and NXD adjustment file metadata parser

This module handles reading metadata from Nikon NKA and NXD adjustment files.
NKA files are Nikon Capture NX adjustment files.
NXD files are Nikon NX-D adjustment files.

Copyright 2025 DNAi inc.
"""

import struct
import json
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class NikonAdjustmentParser:
    """
    Parser for Nikon NKA and NXD adjustment file metadata.
    
    NKA files are Nikon Capture NX adjustment files (XML-based).
    NXD files are Nikon NX-D adjustment files (may be XML or binary).
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize Nikon adjustment parser.
        
        Args:
            file_path: Path to NKA/NXD file
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
        Parse Nikon adjustment metadata.
        
        Returns:
            Dictionary of adjustment metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) == 0:
                raise MetadataReadError("Invalid Nikon adjustment file: empty file")
            
            metadata = {}
            
            # Determine file type from extension
            if self.file_path:
                ext = self.file_path.suffix.lower()
                if ext == '.nka':
                    metadata['File:FileType'] = 'NKA'
                    metadata['File:FileTypeExtension'] = 'nka'
                    metadata['File:MIMEType'] = 'application/x-nikon-nka'
                    metadata['Nikon:AdjustmentType'] = 'Nikon Capture NX'
                elif ext == '.nxd':
                    metadata['File:FileType'] = 'NXD'
                    metadata['File:FileTypeExtension'] = 'nxd'
                    metadata['File:MIMEType'] = 'application/x-nikon-nxd'
                    metadata['Nikon:AdjustmentType'] = 'Nikon NX-D'
                else:
                    metadata['File:FileType'] = 'Nikon Adjustment'
            
            # Check if file is XML-based (common for NKA files)
            if file_data.startswith(b'<?xml') or file_data.startswith(b'<'):
                # XML-based adjustment file
                xml_metadata = self._parse_xml_adjustment(file_data)
                if xml_metadata:
                    metadata.update(xml_metadata)
            else:
                # Binary or other format
                binary_metadata = self._parse_binary_adjustment(file_data)
                if binary_metadata:
                    metadata.update(binary_metadata)
            
            # Extract file size
            if self.file_path:
                import os
                file_size = os.path.getsize(self.file_path)
                metadata['File:FileSize'] = file_size
                metadata['File:FileSizeBytes'] = file_size
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse Nikon adjustment metadata: {str(e)}")
    
    def _parse_xml_adjustment(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse XML-based adjustment file.
        
        Args:
            file_data: File data bytes
            
        Returns:
            Dictionary of parsed metadata
        """
        metadata = {}
        
        try:
            # Try to decode as UTF-8
            try:
                xml_content = file_data.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    xml_content = file_data.decode('utf-16-le')
                except UnicodeDecodeError:
                    xml_content = file_data.decode('latin-1', errors='ignore')
            
            # Basic XML parsing - look for common Nikon adjustment elements
            # This is a simplified parser - full XML parsing would use xml.etree.ElementTree
            
            # Look for version information
            if 'version' in xml_content.lower():
                # Try to extract version
                import re
                version_match = re.search(r'version["\']?\s*[:=]\s*["\']?([0-9.]+)', xml_content, re.IGNORECASE)
                if version_match:
                    metadata['Nikon:Version'] = version_match.group(1)
            
            # Look for adjustment settings
            adjustment_keywords = [
                'exposure', 'brightness', 'contrast', 'saturation', 'hue',
                'whitebalance', 'colortone', 'sharpness', 'noisereduction',
                'vignette', 'distortion', 'chromaticaberration', 'lenscorrection',
                'crop', 'rotation', 'perspective', 'keystone'
            ]
            
            for keyword in adjustment_keywords:
                if keyword.lower() in xml_content.lower():
                    metadata[f'Nikon:Has{keyword.capitalize()}'] = True
            
            # Look for file references (source image)
            file_ref_match = re.search(r'file["\']?\s*[:=]\s*["\']?([^"\']+)', xml_content, re.IGNORECASE)
            if file_ref_match:
                metadata['Nikon:SourceFile'] = file_ref_match.group(1)
            
            # Look for creation date
            date_match = re.search(r'(?:created|date|timestamp)["\']?\s*[:=]\s*["\']?([^"\']+)', xml_content, re.IGNORECASE)
            if date_match:
                metadata['Nikon:CreatedDate'] = date_match.group(1)
            
            # Count adjustment elements
            adjustment_count = xml_content.lower().count('<adjustment') + xml_content.lower().count('<setting')
            if adjustment_count > 0:
                metadata['Nikon:AdjustmentCount'] = adjustment_count
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_binary_adjustment(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse binary adjustment file.
        
        Args:
            file_data: File data bytes
            
        Returns:
            Dictionary of parsed metadata
        """
        metadata = {}
        
        try:
            # Check for common binary signatures
            if len(file_data) >= 4:
                # Check for TIFF-like structure (some Nikon formats use TIFF)
                if file_data[:2] in (b'II', b'MM'):
                    metadata['Nikon:HasTIFFStructure'] = True
                
                # Check for Nikon signature
                if b'Nikon' in file_data[:100]:
                    metadata['Nikon:HasNikonSignature'] = True
                
                # Check for version information in first 100 bytes
                version_match = None
                for i in range(min(100, len(file_data) - 4)):
                    # Look for version pattern (e.g., "1.0", "2.0")
                    if file_data[i:i+1].isdigit() and file_data[i+1:i+2] == b'.' and file_data[i+2:i+3].isdigit():
                        version_match = file_data[i:i+3].decode('ascii', errors='ignore')
                        break
                
                if version_match:
                    metadata['Nikon:Version'] = version_match
            
            # Extract file size
            metadata['Nikon:FileSize'] = len(file_data)
        
        except Exception:
            pass
        
        return metadata

