# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
XISF (Extended Image Serialization Format) image metadata parser

This module handles reading metadata from XISF files.
XISF files are XML-based image files used by PixInsight software for astronomical image processing.

Copyright 2025 DNAi inc.
"""

import struct
import re
from typing import Dict, Any, Optional
from pathlib import Path
import xml.etree.ElementTree as ET

from dnexif.exceptions import MetadataReadError


class XISFParser:
    """
    Parser for XISF (Extended Image Serialization Format) metadata.
    
    XISF files are XML-based image files used by PixInsight software.
    Structure:
    - XML header with XISF namespace
    - Image elements with metadata
    - Property elements with key-value pairs
    """
    
    # XISF namespace
    XISF_NAMESPACE = 'http://www.pixinsight.com/xisf'
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize XISF parser.
        
        Args:
            file_path: Path to XISF file
            file_data: XISF file data bytes
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
        Parse XISF metadata.
        
        Returns:
            Dictionary of XISF metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) == 0:
                raise MetadataReadError("Invalid XISF file: empty file")
            
            metadata = {}
            metadata['File:FileType'] = 'XISF'
            metadata['File:FileTypeExtension'] = 'xisf'
            metadata['File:MIMEType'] = 'image/x-xisf'
            
            # Try to decode as UTF-8
            try:
                xml_content = file_data.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    xml_content = file_data.decode('utf-16-le')
                except UnicodeDecodeError:
                    xml_content = file_data.decode('latin-1', errors='ignore')
            
            # Check for XISF signature
            if 'xisf' not in xml_content.lower() and 'pixinsight' not in xml_content.lower():
                # May be binary XISF - try to find XML header
                xml_start = file_data.find(b'<?xml')
                if xml_start != -1:
                    try:
                        xml_content = file_data[xml_start:].decode('utf-8', errors='ignore')
                    except Exception:
                        return metadata
                else:
                    return metadata
            
            # Parse XML
            try:
                root = ET.fromstring(xml_content)
            except ET.ParseError:
                # Try to find root element if XML is malformed
                root_match = re.search(r'<[^>]+xisf[^>]*>', xml_content, re.IGNORECASE)
                if root_match:
                    try:
                        # Extract XML portion
                        xml_start = xml_content.find(root_match.group(0))
                        xml_end = xml_content.rfind('</')
                        if xml_end > xml_start:
                            xml_portion = xml_content[xml_start:xml_end + 2]
                            root = ET.fromstring(xml_portion + '</xisf>')
                    except Exception:
                        return metadata
                else:
                    return metadata
            
            # Extract namespace
            ns = {'xisf': self.XISF_NAMESPACE}
            
            # Check for XISF root element
            if 'xisf' not in root.tag.lower():
                # Try without namespace
                ns = {}
            
            # Extract version
            version = root.get('version') or root.get('Version')
            if version:
                metadata['XISF:Version'] = version
            
            # Extract image elements
            images = root.findall('.//Image', ns) or root.findall('.//image', ns) or root.findall('.//{*}Image')
            if images:
                metadata['XISF:ImageCount'] = len(images)
                for i, image in enumerate(images[:10], 1):  # Limit to 10 images
                    image_metadata = self._parse_image_element(image, i)
                    if image_metadata:
                        metadata.update(image_metadata)
            
            # Extract property elements
            properties = root.findall('.//Property', ns) or root.findall('.//property', ns) or root.findall('.//{*}Property')
            if properties:
                metadata['XISF:PropertyCount'] = len(properties)
                for i, prop in enumerate(properties[:50], 1):  # Limit to 50 properties
                    prop_metadata = self._parse_property_element(prop, i)
                    if prop_metadata:
                        metadata.update(prop_metadata)
            
            # Extract metadata elements
            metadata_elements = root.findall('.//Metadata', ns) or root.findall('.//metadata', ns) or root.findall('.//{*}Metadata')
            if metadata_elements:
                for i, meta in enumerate(metadata_elements[:10], 1):
                    meta_data = self._parse_metadata_element(meta, i)
                    if meta_data:
                        metadata.update(meta_data)
            
            # Extract file size
            if self.file_path:
                import os
                file_size = os.path.getsize(self.file_path)
                metadata['File:FileSize'] = file_size
                metadata['File:FileSizeBytes'] = file_size
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse XISF metadata: {str(e)}")
    
    def _parse_image_element(self, image_elem: ET.Element, index: int) -> Dict[str, Any]:
        """
        Parse Image element.
        
        Args:
            image_elem: Image XML element
            index: Image index
            
        Returns:
            Dictionary of image metadata
        """
        metadata = {}
        
        try:
            prefix = f'XISF:Image{index}'
            
            # Extract attributes
            width = image_elem.get('width') or image_elem.get('Width')
            if width:
                metadata[f'{prefix}:Width'] = int(width)
                metadata['XISF:ImageWidth'] = int(width)
            
            height = image_elem.get('height') or image_elem.get('Height')
            if height:
                metadata[f'{prefix}:Height'] = int(height)
                metadata['XISF:ImageHeight'] = int(height)
            
            color_space = image_elem.get('colorSpace') or image_elem.get('ColorSpace')
            if color_space:
                metadata[f'{prefix}:ColorSpace'] = color_space
            
            sample_format = image_elem.get('sampleFormat') or image_elem.get('SampleFormat')
            if sample_format:
                metadata[f'{prefix}:SampleFormat'] = sample_format
            
            # Extract child elements
            for child in image_elem:
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                value = child.text or child.get('value') or child.get('Value')
                if value:
                    metadata[f'{prefix}:{tag_name}'] = value
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_property_element(self, prop_elem: ET.Element, index: int) -> Dict[str, Any]:
        """
        Parse Property element.
        
        Args:
            prop_elem: Property XML element
            index: Property index
            
        Returns:
            Dictionary of property metadata
        """
        metadata = {}
        
        try:
            prefix = f'XISF:Property{index}'
            
            # Extract name and value
            name = prop_elem.get('name') or prop_elem.get('Name') or prop_elem.get('id') or prop_elem.get('Id')
            value = prop_elem.get('value') or prop_elem.get('Value') or prop_elem.text
            
            if name:
                metadata[f'{prefix}:Name'] = name
                # Use name as key if value exists
                if value:
                    metadata[f'XISF:{name}'] = value
                    metadata[f'{prefix}:Value'] = value
            
            # Extract type
            prop_type = prop_elem.get('type') or prop_elem.get('Type')
            if prop_type:
                metadata[f'{prefix}:Type'] = prop_type
        
        except Exception:
            pass
        
        return metadata
    
    def _parse_metadata_element(self, meta_elem: ET.Element, index: int) -> Dict[str, Any]:
        """
        Parse Metadata element.
        
        Args:
            meta_elem: Metadata XML element
            index: Metadata index
            
        Returns:
            Dictionary of metadata
        """
        metadata = {}
        
        try:
            prefix = f'XISF:Metadata{index}'
            
            # Extract all child elements
            for child in meta_elem:
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                value = child.text or child.get('value') or child.get('Value')
                if value:
                    metadata[f'{prefix}:{tag_name}'] = value
                    # Also add without prefix for common metadata
                    if tag_name.lower() in ('title', 'author', 'copyright', 'description', 'keywords'):
                        metadata[f'XISF:{tag_name.capitalize()}'] = value
        
        except Exception:
            pass
        
        return metadata

