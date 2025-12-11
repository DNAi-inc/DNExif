# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Parser for XML files.

Extracts XML-specific metadata like structure information, element count, attribute count, and content analysis.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import xml.etree.ElementTree as ET
import re

from dnexif.exceptions import MetadataReadError


class XMLParser:
    """
    Parser for XML file metadata.
    
    Extracts:
    - XML structure information (element count, attribute count, depth)
    - Content analysis (text nodes, CDATA sections)
    - XML declaration information (version, encoding, standalone)
    - File metadata (already handled by _add_file_tags)
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize XML parser.
        
        Args:
            file_path: Path to XML file
            file_data: XML file data bytes
        """
        if file_path:
            self.file_path = Path(file_path)
            self.file_data = None
        elif file_data:
            self.file_data = file_data
            self.file_path = None
        else:
            raise ValueError("Either file_path or file_data must be provided")
    
    def _analyze_xml_structure(self, element: ET.Element, depth: int = 0) -> Dict[str, int]:
        """
        Recursively analyze XML structure.
        
        Args:
            element: XML element to analyze
            depth: Current depth level
            
        Returns:
            Dictionary with structure statistics
        """
        stats = {
            'max_depth': depth,
            'element_count': 1,  # Count this element
            'attribute_count': len(element.attrib),
            'text_node_count': 1 if (element.text and element.text.strip()) else 0,
            'child_element_count': len(list(element)),
        }
        
        # Analyze children
        for child in element:
            nested_stats = self._analyze_xml_structure(child, depth + 1)
            stats['max_depth'] = max(stats['max_depth'], nested_stats['max_depth'])
            stats['element_count'] += nested_stats['element_count']
            stats['attribute_count'] += nested_stats['attribute_count']
            stats['text_node_count'] += nested_stats['text_node_count']
            stats['child_element_count'] += nested_stats['child_element_count']
        
        # Count tail text (text after element)
        if element.tail and element.tail.strip():
            stats['text_node_count'] += 1
        
        return stats
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse XML file metadata.
        
        Returns:
            Dictionary of XML metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if not file_data:
                raise MetadataReadError("Invalid XML file: empty file")
            
            metadata = {}
            metadata['File:FileType'] = 'XML'
            metadata['File:FileTypeExtension'] = 'xml'
            metadata['File:MIMEType'] = 'application/xml'
            
            # Try to decode as UTF-8
            try:
                text = file_data.decode('utf-8')
                encoding = 'utf-8'
            except UnicodeDecodeError:
                # Try other encodings
                for enc in ['latin-1', 'cp1252', 'us-ascii']:
                    try:
                        text = file_data.decode(enc)
                        encoding = enc
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    text = file_data.decode('utf-8', errors='ignore')
                    encoding = 'utf-8'
            
            metadata['XML:Encoding'] = encoding
            
            # Extract XML declaration
            xml_decl_match = re.match(r'<\?xml\s+([^>]+)\?>', text)
            if xml_decl_match:
                decl_content = xml_decl_match.group(1)
                metadata['XML:HasDeclaration'] = True
                
                # Extract version
                version_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', decl_content, re.IGNORECASE)
                if version_match:
                    metadata['XML:Version'] = version_match.group(1)
                
                # Extract encoding from declaration
                encoding_match = re.search(r'encoding\s*=\s*["\']([^"\']+)["\']', decl_content, re.IGNORECASE)
                if encoding_match:
                    metadata['XML:DeclarationEncoding'] = encoding_match.group(1)
                
                # Extract standalone
                standalone_match = re.search(r'standalone\s*=\s*["\']([^"\']+)["\']', decl_content, re.IGNORECASE)
                if standalone_match:
                    metadata['XML:Standalone'] = standalone_match.group(1)
            else:
                metadata['XML:HasDeclaration'] = False
            
            # Parse XML
            try:
                root = ET.fromstring(text)
                metadata['XML:IsValid'] = True
                metadata['XML:RootElement'] = root.tag
                
                # Remove namespace prefix if present
                root_tag_local = root.tag.split('}')[-1] if '}' in root.tag else root.tag
                metadata['XML:RootElementLocalName'] = root_tag_local
                
                # Extract namespace if present
                if root.tag.startswith('{'):
                    namespace = root.tag[1:].split('}')[0]
                    metadata['XML:RootNamespace'] = namespace
                
                # Extract root attributes
                if root.attrib:
                    metadata['XML:RootAttributeCount'] = len(root.attrib)
                    for i, (attr_name, attr_value) in enumerate(root.attrib.items(), 1):
                        attr_local = attr_name.split('}')[-1] if '}' in attr_name else attr_name
                        metadata[f'XML:RootAttribute{i}'] = f'{attr_local}={attr_value}'
                
                # Analyze structure
                stats = self._analyze_xml_structure(root)
                metadata['XML:MaxDepth'] = stats['max_depth']
                metadata['XML:ElementCount'] = stats['element_count']
                metadata['XML:AttributeCount'] = stats['attribute_count']
                metadata['XML:TextNodeCount'] = stats['text_node_count']
                metadata['XML:ChildElementCount'] = stats['child_element_count']
                
                # Count CDATA sections
                cdata_count = text.count('<![CDATA[')
                metadata['XML:CDATASectionCount'] = cdata_count
                
                # Count comments
                comment_count = text.count('<!--')
                metadata['XML:CommentCount'] = comment_count
                
                # Count processing instructions
                pi_count = text.count('<?') - (1 if metadata.get('XML:HasDeclaration') else 0)
                metadata['XML:ProcessingInstructionCount'] = pi_count
                
            except ET.ParseError as e:
                metadata['XML:IsValid'] = False
                metadata['XML:ParseError'] = str(e)
                metadata['XML:ParseErrorLine'] = getattr(e, 'lineno', None)
                metadata['XML:ParseErrorColumn'] = getattr(e, 'colno', None)
            
            # Character and byte counts
            metadata['XML:CharacterCount'] = len(text)
            metadata['XML:ByteCount'] = len(file_data)
            
            # Line count
            line_count = text.count('\n')
            if text and not text.endswith('\n'):
                line_count += 1
            metadata['XML:LineCount'] = line_count
            
            return metadata
            
        except Exception as e:
            raise MetadataReadError(f"Failed to parse XML file metadata: {str(e)}")

