# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
VNT file metadata parser

This module handles reading metadata from VNT files.
VNT files can be either Scene7 Vignette files or V-Note document files.

Copyright 2025 DNAi inc.
"""

import struct
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class VNTParser:
    """
    Parser for VNT file metadata.
    
    VNT files can be:
    - Scene7 Vignette files (binary or XML-based)
    - V-Note document files (XML-based)
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize VNT parser.
        
        Args:
            file_path: Path to VNT file
            file_data: VNT file data bytes
        """
        if file_path:
            self.file_path = Path(file_path)
            self.file_data = None
        elif file_data:
            self.file_data = file_data
            self.file_path = None
        else:
            raise ValueError("Either file_path or file_data must be provided")
    
    def _extract_embedded_image_rectangle(self, root: ET.Element, metadata: Dict[str, Any]) -> None:
        """
        Extract EmbeddedImageRectangle from XML structure.
        
        Args:
            root: XML root element
            metadata: Metadata dictionary to update
        """
        # Look for EmbeddedImageRectangle (common in VNT files)
        # EmbeddedImageRectangle can be an element or attribute
        embedded_rect = None
        
        # Search all elements recursively
        for elem in root.iter():
            tag_lower = elem.tag.lower()
            if 'embeddedimagerectangle' in tag_lower or 'imagerectangle' in tag_lower:
                if elem.text:
                    embedded_rect = elem.text.strip()
                elif 'rect' in elem.attrib or 'rectangle' in elem.attrib:
                    embedded_rect = elem.attrib.get('rect') or elem.attrib.get('rectangle')
                break
        
        # Also check root attributes
        if not embedded_rect:
            for attr_name, attr_value in root.attrib.items():
                if 'embeddedimagerectangle' in attr_name.lower() or 'imagerectangle' in attr_name.lower():
                    embedded_rect = attr_value
                    break
        
        if embedded_rect:
            metadata['VNT:EmbeddedImageRectangle'] = embedded_rect
            # Try to parse rectangle coordinates if in format like "x1,y1,x2,y2" or "x,y,width,height"
            try:
                # Handle various formats: "x1,y1,x2,y2", "x y width height", "x,y,width,height", etc.
                coords_str = embedded_rect.replace(',', ' ').replace(';', ' ').replace(':', ' ')
                coords = [int(x.strip()) for x in coords_str.split() if x.strip().lstrip('-').isdigit()]
                if len(coords) >= 4:
                    metadata['VNT:EmbeddedImageRectangleX1'] = coords[0]
                    metadata['VNT:EmbeddedImageRectangleY1'] = coords[1]
                    metadata['VNT:EmbeddedImageRectangleX2'] = coords[2]
                    metadata['VNT:EmbeddedImageRectangleY2'] = coords[3]
                    # Calculate width and height
                    width = abs(coords[2] - coords[0])
                    height = abs(coords[3] - coords[1])
                    if width > 0:
                        metadata['VNT:EmbeddedImageRectangleWidth'] = width
                    if height > 0:
                        metadata['VNT:EmbeddedImageRectangleHeight'] = height
            except (ValueError, IndexError):
                pass
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse VNT metadata.
        
        Returns:
            Dictionary of VNT metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 4:
                raise MetadataReadError("Invalid VNT file: too short")
            
            metadata = {}
            metadata['File:FileType'] = 'VNT'
            metadata['File:FileTypeExtension'] = 'vnt'
            metadata['File:MIMEType'] = 'application/x-vnt'
            
            # Try to detect format type
            # Check if it's XML-based (V-Note or Scene7 Vignette XML)
            try:
                # Try to decode as UTF-8
                file_text = file_data.decode('utf-8', errors='ignore')
                
                # Check for XML declaration or XML root elements
                if file_text.strip().startswith('<?xml') or file_text.strip().startswith('<'):
                    metadata['VNT:Format'] = 'XML'
                    
                    # Try to parse as XML
                    try:
                        root = ET.fromstring(file_text)
                        
                        # Check for V-Note document structure
                        if root.tag.lower() in ('vnote', 'v-note', 'note', 'document'):
                            metadata['VNT:Type'] = 'V-Note'
                            metadata['VNT:DocumentType'] = 'V-Note'
                            
                            # Extract common V-Note elements
                            if root.text:
                                metadata['VNT:Content'] = root.text.strip()
                            
                            # Extract attributes
                            for attr_name, attr_value in root.attrib.items():
                                metadata[f'VNT:{attr_name}'] = attr_value
                            
                            # Extract child elements
                            for child in root:
                                tag_name = child.tag.replace('{', '').replace('}', '').split('}')[-1]
                                if child.text:
                                    metadata[f'VNT:{tag_name}'] = child.text.strip()
                                if child.attrib:
                                    for attr_name, attr_value in child.attrib.items():
                                        metadata[f'VNT:{tag_name}:{attr_name}'] = attr_value
                            
                            # Extract EmbeddedImageRectangle if present
                            self._extract_embedded_image_rectangle(root, metadata)
                        
                        # Check for Scene7 Vignette structure
                        elif 'vignette' in root.tag.lower() or 'scene7' in root.tag.lower() or 's7' in root.tag.lower():
                            metadata['VNT:Type'] = 'Scene7 Vignette'
                            metadata['VNT:DocumentType'] = 'Scene7 Vignette'
                            
                            # Extract Scene7 Vignette metadata
                            if root.text:
                                metadata['VNT:Content'] = root.text.strip()
                            
                            # Extract attributes
                            for attr_name, attr_value in root.attrib.items():
                                metadata[f'VNT:{attr_name}'] = attr_value
                            
                            # Extract child elements
                            for child in root:
                                tag_name = child.tag.replace('{', '').replace('}', '').split('}')[-1]
                                if child.text:
                                    metadata[f'VNT:{tag_name}'] = child.text.strip()
                                if child.attrib:
                                    for attr_name, attr_value in child.attrib.items():
                                        metadata[f'VNT:{tag_name}:{attr_name}'] = attr_value
                            
                            # Extract EmbeddedImageRectangle if present
                            self._extract_embedded_image_rectangle(root, metadata)
                        
                        else:
                            # Generic XML structure
                            metadata['VNT:Type'] = 'XML Document'
                            metadata['VNT:RootElement'] = root.tag
                            
                            # Extract root attributes
                            for attr_name, attr_value in root.attrib.items():
                                metadata[f'VNT:{attr_name}'] = attr_value
                            
                            # Count child elements
                            child_count = len(list(root))
                            if child_count > 0:
                                metadata['VNT:ChildElementCount'] = child_count
                            
                            # Extract EmbeddedImageRectangle if present
                            self._extract_embedded_image_rectangle(root, metadata)
                    
                    except ET.ParseError:
                        # XML parsing failed, but it's still XML format
                        metadata['VNT:Type'] = 'XML (Unparseable)'
                
                else:
                    # Not XML, might be binary Scene7 Vignette
                    metadata['VNT:Format'] = 'Binary'
                    metadata['VNT:Type'] = 'Scene7 Vignette (Binary)'
                    
                    # Try to extract basic information from binary structure
                    # Scene7 Vignette files may have headers or signatures
                    if len(file_data) >= 4:
                        # Check for common binary patterns
                        signature = file_data[:4]
                        metadata['VNT:Signature'] = signature.hex()
                        
                        # Try to extract dimensions if present (common in image formats)
                        if len(file_data) >= 16:
                            try:
                                # Try little-endian 32-bit integers for dimensions
                                width = struct.unpack('<I', file_data[4:8])[0]
                                height = struct.unpack('<I', file_data[8:12])[0]
                                
                                # Validate dimensions
                                if 0 < width < 65535 and 0 < height < 65535:
                                    metadata['VNT:Width'] = width
                                    metadata['VNT:Height'] = height
                                    metadata['Image:ImageWidth'] = width
                                    metadata['Image:ImageHeight'] = height
                            except Exception:
                                pass
                            
                            try:
                                # Try big-endian 32-bit integers for dimensions
                                width = struct.unpack('>I', file_data[4:8])[0]
                                height = struct.unpack('>I', file_data[8:12])[0]
                                
                                # Validate dimensions
                                if 0 < width < 65535 and 0 < height < 65535:
                                    if 'VNT:Width' not in metadata:
                                        metadata['VNT:Width'] = width
                                        metadata['VNT:Height'] = height
                                        metadata['Image:ImageWidth'] = width
                                        metadata['Image:ImageHeight'] = height
                            except Exception:
                                pass
            
            except UnicodeDecodeError:
                # Binary file, treat as Scene7 Vignette binary
                metadata['VNT:Format'] = 'Binary'
                metadata['VNT:Type'] = 'Scene7 Vignette (Binary)'
                
                # Extract basic binary information
                if len(file_data) >= 4:
                    signature = file_data[:4]
                    metadata['VNT:Signature'] = signature.hex()
            
            # File size
            if self.file_path:
                try:
                    file_size = self.file_path.stat().st_size
                    metadata['File:FileSize'] = file_size
                except Exception:
                    pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse VNT metadata: {str(e)}")

