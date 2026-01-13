# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
HEIC/HEIF (High Efficiency Image Format) metadata parser

This module handles reading metadata from HEIC/HEIF files.
HEIC is a container format that can contain EXIF, XMP, and other metadata.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class HEICParser:
    """
    Parser for HEIC/HEIF (High Efficiency Image Format) metadata.
    
    HEIC files use the ISO Base Media File Format (ISOBMFF) container,
    which is similar to MP4. Metadata is stored in various boxes (atoms).
    """
    
    # HEIC file signatures
    HEIC_SIGNATURES = [
        b'ftyp',  # File type box
        b'heic',  # HEIC brand
        b'heif',  # HEIF brand
        b'mif1',  # HEIF image brand
        b'msf1',  # HEIF sequence brand
    ]
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize HEIC parser.
        
        Args:
            file_path: Path to HEIC file
            file_data: HEIC file data bytes
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
        Parse HEIC metadata.
        
        Returns:
            Dictionary of HEIC metadata
        """
        try:
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            if len(file_data) < 8:
                raise MetadataReadError("Invalid HEIC file: too short")
            
            metadata = {}
            
            # Check for HEIC signature (ftyp box)
            if file_data[4:8] != b'ftyp':
                # Try to find ftyp box
                ftyp_pos = file_data.find(b'ftyp')
                if ftyp_pos == -1:
                    raise MetadataReadError("Invalid HEIC file: missing ftyp box")
            
            # Parse ISOBMFF boxes (atoms)
            offset = 0
            max_offset = len(file_data) - 8
            box_count = 0
            max_boxes = 1000  # Limit to prevent infinite loops
            
            while offset < max_offset and box_count < max_boxes:
                if offset + 8 > len(file_data):
                    break
                
                # Read box size (4 bytes, big-endian)
                box_size = struct.unpack('>I', file_data[offset:offset+4])[0]
                
                # Read box type (4 bytes)
                box_type = file_data[offset+4:offset+8]
                
                # Check for special size values
                box_data_start = offset + 8
                if box_size == 0:
                    # Box extends to end of file
                    box_size = len(file_data) - offset
                elif box_size == 1:
                    # Extended size (8 bytes)
                    if offset + 16 > len(file_data):
                        break
                    box_size = struct.unpack('>Q', file_data[offset+8:offset+16])[0]
                    box_data_start = offset + 16
                
                # Check box bounds
                if box_size < 8 or offset + box_size > len(file_data):
                    break
                
                box_data = file_data[box_data_start:offset+box_size]
                
                # Parse specific box types
                if box_type == b'ftyp':
                    # File type box
                    parsed = self._parse_ftyp_box(box_data)
                    metadata.update(parsed)
                elif box_type == b'meta':
                    # Metadata box
                    parsed = self._parse_meta_box(box_data)
                    metadata.update(parsed)
                elif box_type == b'uuid':
                    # UUID box (may contain XMP)
                    parsed = self._parse_uuid_box(box_data)
                    metadata.update(parsed)
                elif box_type == b'moov':
                    # Movie box - may contain metadata
                    metadata['HEIC:HasMovieBox'] = True
                    # Try to parse QuickTime-style metadata from moov box
                    try:
                        from dnexif.video_parser import VideoParser
                        video_parser = VideoParser(file_data=box_data)
                        qt_data = video_parser._parse_quicktime()
                        if qt_data:
                            metadata.update(qt_data)
                    except Exception:
                        pass
                elif box_type == b'mdat':
                    # Media data box
                    metadata['HEIC:HasMediaData'] = True
                
                offset += box_size
                box_count += 1
            
            metadata['HEIC:BoxCount'] = box_count
            
            # Scan entire file for EXIF data (HEIC files may store EXIF in various locations)
            # This is a fallback to ensure we extract all EXIF data
            try:
                exif_positions = []
                for i in range(len(file_data) - 8):
                    if (file_data[i:i+2] == b'II' and file_data[i+2] == 0x2A and file_data[i+3] == 0x00) or \
                       (file_data[i:i+2] == b'MM' and file_data[i+2] == 0x00 and file_data[i+3] == 0x2A):
                        exif_positions.append(i)
                
                # Try to extract EXIF from each found position
                for exif_offset in exif_positions[:3]:  # Limit to first 3 to avoid duplicates
                    try:
                        exif_data_bytes = file_data[exif_offset:]
                        from dnexif.exif_parser import ExifParser
                        exif_parser = ExifParser(file_data=exif_data_bytes)
                        exif_data = exif_parser.read()
                        if exif_data:
                            # Add EXIF tags with proper prefix (avoid duplicates)
                            for k, v in exif_data.items():
                                if not k.startswith('EXIF:'):
                                    tag_key = f'EXIF:{k}'
                                else:
                                    tag_key = k
                                # Only add if not already present (avoid duplicates from multiple EXIF blocks)
                                if tag_key not in metadata:
                                    metadata[tag_key] = v
                            break  # Found valid EXIF, stop searching
                    except Exception:
                        continue
            except Exception:
                pass
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse HEIC metadata: {str(e)}")
    
    def _parse_ftyp_box(self, data: bytes) -> Dict[str, Any]:
        """Parse ftyp (file type) box."""
        metadata = {}
        
        try:
            if len(data) >= 4:
                # Major brand (4 bytes)
                major_brand = data[0:4].decode('ascii', errors='ignore')
                metadata['HEIC:MajorBrand'] = major_brand
                
                # Minor version (4 bytes)
                if len(data) >= 8:
                    minor_version = struct.unpack('>I', data[4:8])[0]
                    metadata['HEIC:MinorVersion'] = minor_version
                
                # Compatible brands
                if len(data) > 8:
                    compatible_brands = []
                    for i in range(8, len(data), 4):
                        if i + 4 <= len(data):
                            brand = data[i:i+4].decode('ascii', errors='ignore')
                            compatible_brands.append(brand)
                    if compatible_brands:
                        metadata['HEIC:CompatibleBrands'] = compatible_brands
        except Exception:
            pass
        
        return metadata
    
    def _parse_meta_box(self, data: bytes) -> Dict[str, Any]:
        """Parse meta (metadata) box."""
        metadata = {}
        
        try:
            # Meta box contains other boxes
            # Look for EXIF, XMP, and other metadata
            offset = 0
            if len(data) >= 4:
                # Version and flags (4 bytes)
                version_flags = struct.unpack('>I', data[0:4])[0]
                offset = 4
            
            # Parse nested boxes
            while offset < len(data) - 8:
                if offset + 8 > len(data):
                    break
                
                box_size = struct.unpack('>I', data[offset:offset+4])[0]
                box_type = data[offset+4:offset+8]
                
                # Handle extended size
                if box_size == 1:
                    if offset + 16 > len(data):
                        break
                    box_size = struct.unpack('>Q', data[offset+8:offset+16])[0]
                    box_data_start = offset + 16
                else:
                    box_data_start = offset + 8
                
                if box_size < 8 or offset + box_size > len(data):
                    break
                
                box_data = data[box_data_start:offset+box_size]
                
                if box_type == b'iref':
                    # Item reference box
                    metadata['HEIC:HasItemRef'] = True
                elif box_type == b'exif':
                    # EXIF box (4-byte offset + TIFF data)
                    try:
                        if len(box_data) >= 4:
                            exif_offset = struct.unpack('>I', box_data[0:4])[0]
                            tiff_start = 4 + exif_offset
                            if 0 <= tiff_start < len(box_data):
                                exif_data_bytes = box_data[tiff_start:]
                                from dnexif.exif_parser import ExifParser
                                exif_parser = ExifParser(file_data=exif_data_bytes)
                                exif_data = exif_parser.read()
                                for k, v in exif_data.items():
                                    if not k.startswith('EXIF:'):
                                        metadata[f'EXIF:{k}'] = v
                                    else:
                                        metadata[k] = v
                    except Exception:
                        pass
                elif box_type == b'iprp':
                    # Item properties box - may contain PLIST data
                    metadata['HEIC:HasItemProperties'] = True
                    # Try to extract PLIST from item properties
                    plist_metadata = self._extract_plist_data(box_data)
                    if plist_metadata:
                        metadata.update(plist_metadata)
                elif box_type == b'idat':
                    # Item data box - may contain EXIF data
                    metadata['HEIC:HasItemData'] = True
                    # Try to extract EXIF from item data
                    try:
                        # Look for EXIF signature (II*\x00 or MM\x00*)
                        # HEIC stores EXIF data in idat boxes, but it may be offset
                        exif_start = -1
                        if b'II*\x00' in box_data:
                            exif_start = box_data.find(b'II*\x00')
                        elif b'MM\x00*' in box_data:
                            exif_start = box_data.find(b'MM\x00*')
                        
                        if exif_start >= 0:
                            # Found EXIF signature, extract EXIF data
                            exif_data_bytes = box_data[exif_start:]
                            from dnexif.exif_parser import ExifParser
                            exif_parser = ExifParser(file_data=exif_data_bytes)
                            exif_data = exif_parser.read()
                            # Add EXIF tags with proper prefix
                            for k, v in exif_data.items():
                                if not k.startswith('EXIF:'):
                                    metadata[f'EXIF:{k}'] = v
                                else:
                                    metadata[k] = v
                        else:
                            # Try scanning the entire box_data for EXIF patterns
                            # Sometimes EXIF data is embedded without clear signature
                            for i in range(len(box_data) - 8):
                                if (box_data[i:i+2] == b'II' and box_data[i+2] == 0x2A and box_data[i+3] == 0x00) or \
                                   (box_data[i:i+2] == b'MM' and box_data[i+2] == 0x00 and box_data[i+3] == 0x2A):
                                    try:
                                        exif_data_bytes = box_data[i:]
                                        from dnexif.exif_parser import ExifParser
                                        exif_parser = ExifParser(file_data=exif_data_bytes)
                                        exif_data = exif_parser.read()
                                        if exif_data:
                                            # Add EXIF tags with proper prefix
                                            for k, v in exif_data.items():
                                                if not k.startswith('EXIF:'):
                                                    metadata[f'EXIF:{k}'] = v
                                                else:
                                                    metadata[k] = v
                                            break  # Found EXIF, stop searching
                                    except Exception:
                                        continue
                    except Exception:
                        pass
                elif box_type == b'iloc':
                    # Item location box
                    metadata['HEIC:HasItemLocation'] = True
                elif box_type == b'iinf':
                    # Item info box
                    metadata['HEIC:HasItemInfo'] = True
                elif box_type == b'pitm':
                    # Primary item box
                    metadata['HEIC:HasPrimaryItem'] = True
                
                offset += box_size
        except Exception:
            pass
        
        metadata['HEIC:HasMeta'] = True
        return metadata
    
    def _parse_uuid_box(self, data: bytes) -> Dict[str, Any]:
        """Parse UUID box (may contain XMP, PLIST, or other metadata)."""
        metadata = {}
        
        try:
            if len(data) < 16:
                return metadata
            
            uuid_bytes = data[0:16]
            payload = data[16:]
            
            # XMP UUID: be7acfcf-2a4d-854d-0d06-9c7adf000000
            xmp_uuid = bytes.fromhex('be7acfcf2a4d854d0d069c7adf000000')
            
            if uuid_bytes == xmp_uuid:
                # XMP data
                if payload.startswith(b'<?xml') or payload.startswith(b'<x:xmpmeta'):
                    metadata['HEIC:HasXMP'] = True
                    metadata['HEIC:XMPSize'] = len(payload)
            
            # Extract PLIST data (can be in various UUID boxes or as standalone data)
            # PLIST data can be XML format (starts with <?xml or <plist) or binary format
            plist_metadata = self._extract_plist_data(payload)
            if plist_metadata:
                metadata.update(plist_metadata)
        except Exception:
            pass
        
        return metadata
    
    def _extract_plist_data(self, data: bytes) -> Dict[str, Any]:
        """
        Extract PLIST (Property List) data from HEIC files.
        
        PLIST data can be in XML format (<?xml or <plist) or binary format (bplist00).
        
        Args:
            data: Data bytes that may contain PLIST information
            
        Returns:
            Dictionary of PLIST metadata
        """
        metadata = {}
        
        try:
            if not data or len(data) < 8:
                return metadata
            
            # Check for XML PLIST format
            # PLIST XML can start with <?xml or <plist
            plist_xml_start = -1
            if data.startswith(b'<?xml'):
                plist_xml_start = 0
            elif b'<?xml' in data[:100]:
                plist_xml_start = data.find(b'<?xml')
            elif data.startswith(b'<plist'):
                plist_xml_start = 0
            elif b'<plist' in data[:100]:
                plist_xml_start = data.find(b'<plist')
            
            if plist_xml_start >= 0:
                # Found XML PLIST
                try:
                    # Find the end of the PLIST (</plist>)
                    plist_end = data.find(b'</plist>', plist_xml_start)
                    if plist_end > plist_xml_start:
                        plist_xml_data = data[plist_xml_start:plist_end + 8]
                        
                        # Try to decode as UTF-8
                        try:
                            plist_xml_str = plist_xml_data.decode('utf-8', errors='ignore')
                            
                            # Parse PLIST XML
                            import xml.etree.ElementTree as ET
                            try:
                                root = ET.fromstring(plist_xml_str)
                                
                                # Extract PLIST metadata
                                metadata['HEIC:PLIST:Present'] = 'Yes'
                                metadata['HEIC:PLIST:Format'] = 'XML'
                                metadata['HEIC:PLIST:Size'] = len(plist_xml_data)
                                
                                # Extract root element type (dict, array, string, etc.)
                                if root.tag:
                                    root_tag = root.tag.replace('{', '').replace('}', '').split('}')[-1]
                                    metadata['HEIC:PLIST:RootType'] = root_tag
                                
                                # Extract key-value pairs from dict elements
                                if root.tag.endswith('dict'):
                                    self._extract_plist_dict(root, metadata, 'HEIC:PLIST')
                                
                                # Extract array elements
                                elif root.tag.endswith('array'):
                                    array_items = []
                                    for child in root:
                                        item_text = child.text if child.text else ''
                                        if item_text.strip():
                                            array_items.append(item_text.strip())
                                    if array_items:
                                        metadata['HEIC:PLIST:ArrayItems'] = array_items
                                        metadata['HEIC:PLIST:ArrayCount'] = len(array_items)
                                
                                # Extract string values
                                elif root.tag.endswith('string'):
                                    if root.text:
                                        metadata['HEIC:PLIST:StringValue'] = root.text.strip()
                                
                                # Store raw PLIST XML (truncate if too long)
                                if len(plist_xml_str) <= 10000:  # Store up to 10KB
                                    metadata['HEIC:PLIST:Data'] = plist_xml_str
                                else:
                                    metadata['HEIC:PLIST:Data'] = plist_xml_str[:10000] + '...'
                                    metadata['HEIC:PLIST:Truncated'] = 'Yes'
                            except ET.ParseError:
                                # Not valid XML, try to extract as text
                                if len(plist_xml_str) <= 1000:
                                    metadata['HEIC:PLIST:Present'] = 'Yes'
                                    metadata['HEIC:PLIST:Format'] = 'XML (malformed)'
                                    metadata['HEIC:PLIST:Data'] = plist_xml_str[:1000]
                        except UnicodeDecodeError:
                            pass
                except Exception:
                    pass
            
            # Check for binary PLIST format (bplist00)
            elif data.startswith(b'bplist00'):
                # Binary PLIST format
                metadata['HEIC:PLIST:Present'] = 'Yes'
                metadata['HEIC:PLIST:Format'] = 'Binary'
                metadata['HEIC:PLIST:Size'] = len(data)
                
                # Binary PLIST parsing is complex, just mark as present
                # Full binary PLIST parsing would require implementing bplist parser
                metadata['HEIC:PLIST:BinaryFormat'] = 'Yes'
        except Exception:
            pass
        
        return metadata
    
    def _extract_plist_dict(self, dict_elem, metadata: Dict[str, Any], prefix: str) -> None:
        """
        Extract key-value pairs from PLIST dict element.
        
        Args:
            dict_elem: XML element representing a PLIST dict
            metadata: Metadata dictionary to update
            prefix: Prefix for metadata keys
        """
        try:
            import xml.etree.ElementTree as ET
            
            # PLIST dict structure: <key>keyname</key><value>value</value> pairs
            children = list(dict_elem)
            i = 0
            while i < len(children) - 1:
                key_elem = children[i]
                value_elem = children[i + 1]
                
                if key_elem.tag.endswith('key') and key_elem.text:
                    key_name = key_elem.text.strip()
                    # Sanitize key name for metadata tag
                    tag_key = key_name.replace(' ', '').replace('-', '').replace(':', '')
                    
                    # Extract value based on value element type
                    if value_elem.tag.endswith('string'):
                        value = value_elem.text if value_elem.text else ''
                        if value.strip():
                            metadata[f'{prefix}:{tag_key}'] = value.strip()
                    elif value_elem.tag.endswith('integer'):
                        try:
                            value = int(value_elem.text) if value_elem.text else 0
                            metadata[f'{prefix}:{tag_key}'] = value
                        except ValueError:
                            pass
                    elif value_elem.tag.endswith('real'):
                        try:
                            value = float(value_elem.text) if value_elem.text else 0.0
                            metadata[f'{prefix}:{tag_key}'] = value
                        except ValueError:
                            pass
                    elif value_elem.tag.endswith('true'):
                        metadata[f'{prefix}:{tag_key}'] = True
                    elif value_elem.tag.endswith('false'):
                        metadata[f'{prefix}:{tag_key}'] = False
                    elif value_elem.tag.endswith('dict'):
                        # Nested dict - extract recursively
                        nested_prefix = f'{prefix}:{tag_key}'
                        self._extract_plist_dict(value_elem, metadata, nested_prefix)
                    elif value_elem.tag.endswith('array'):
                        # Array - extract items
                        array_items = []
                        for item in value_elem:
                            if item.text:
                                array_items.append(item.text.strip())
                        if array_items:
                            metadata[f'{prefix}:{tag_key}'] = array_items
                
                i += 2  # Move to next key-value pair
        except Exception:
            pass
