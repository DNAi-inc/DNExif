# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
XMP metadata writer

This module handles writing XMP metadata to image files.
XMP data is typically embedded in JPEG APP1 segments as XML packets.

Copyright 2025 DNAi inc.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional
from xml.dom import minidom
from dnexif.exceptions import MetadataWriteError


class XMPWriter:
    """
    Writes XMP metadata to image files.
    
    XMP data is embedded in JPEG APP1 segments as XML packets.
    """
    
    # XMP namespace URIs (matching parser - comprehensive list)
    NAMESPACES = {
        # Core namespaces
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'x': 'adobe:ns:meta/',
        
        # Adobe standard namespaces
        'xmp': 'http://ns.adobe.com/xap/1.0/',
        'xmpG': 'http://ns.adobe.com/xap/1.0/g/',
        'xmpGImg': 'http://ns.adobe.com/xap/1.0/g/img/',
        'xmpMM': 'http://ns.adobe.com/xap/1.0/mm/',
        'xmpRights': 'http://ns.adobe.com/xap/1.0/rights/',
        'xmpBJ': 'http://ns.adobe.com/xap/1.0/bj/',
        'xmpTPg': 'http://ns.adobe.com/xap/1.0/t/pg/',
        'xmpDM': 'http://ns.adobe.com/xmp/1.0/DynamicMedia/',
        'xmpNote': 'http://ns.adobe.com/xmp/note/',
        
        # Adobe application namespaces
        'photoshop': 'http://ns.adobe.com/photoshop/1.0/',
        'crs': 'http://ns.adobe.com/camera-raw-settings/1.0/',
        'lr': 'http://ns.adobe.com/lightroom/1.0/',
        'stEvt': 'http://ns.adobe.com/xap/1.0/sType/ResourceEvent#',
        'stRef': 'http://ns.adobe.com/xap/1.0/sType/ResourceRef#',
        'stJob': 'http://ns.adobe.com/xap/1.0/sType/Job#',
        'stVer': 'http://ns.adobe.com/xap/1.0/sType/Version#',
        'stFnt': 'http://ns.adobe.com/xap/1.0/sType/Font#',
        'stMfs': 'http://ns.adobe.com/xap/1.0/sType/ManifestItem#',
        
        # Dublin Core
        'dc': 'http://purl.org/dc/elements/1.1/',
        
        # EXIF and TIFF
        'exif': 'http://ns.adobe.com/exif/1.0/',
        'tiff': 'http://ns.adobe.com/tiff/1.0/',
        'aux': 'http://ns.adobe.com/exif/1.0/aux/',
        
        # external tool namespace (for tags like OriginalImageMD5)
        'et': 'http://ns.standard format.ca/1.0/',
        
        # IPTC
        'Iptc4xmpCore': 'http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/',
        'Iptc4xmpExt': 'http://iptc.org/std/Iptc4xmpExt/2008-02-29/',
        
        # Additional Adobe namespaces
        'apdi': 'http://ns.adobe.com/apdi/1.0/',
        'xmpidq': 'http://ns.adobe.com/xmp/identifier/qual/1.0/',
        
        # Manufacturer-specific namespaces
        'xmpDSA': 'http://ns.leica-camera.com/xmp/1.0/DSA/',
        'acdsee-rs': 'http://ns.acdsee.com/iptc/1.0/',
        'photomech': 'http://ns.camerabits.com/photomechanic/1.0/',
        'GCamera': 'http://ns.google.com/photos/1.0/camera/',
        
        # Additional standard namespaces
        'plus': 'http://ns.useplus.org/ldf/xmp/1.0/',
        'prism': 'http://prismstandard.org/namespaces/basic/2.0/',
        'prl': 'http://prismstandard.org/namespaces/prl/2.0/',
        'prm': 'http://prismstandard.org/namespaces/prm/2.0/',
        
        # HDR Gain Map namespace
        'HDRGM': 'http://ns.adobe.com/hdr-gain-map/1.0/',
    }
    
    def __init__(self):
        """Initialize XMP writer."""
        pass
    
    def build_xmp_packet(self, metadata: Dict[str, Any]) -> bytes:
        """
        Build XMP packet from metadata dictionary.
        
        Args:
            metadata: Dictionary of XMP tags (e.g., {'XMP:Title': 'My Photo'})
            
        Returns:
            XMP packet as bytes
        """
        # Filter XMP tags
        xmp_tags: Dict[str, Any] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if key.startswith('XMP:'):
                tag_name = key.split(':', 1)[1]
                xmp_tags[f'xmp:{tag_name}'] = value
            elif ':' in key or (key.startswith('{') and '}' in key):
                xmp_tags[key] = value
        
        if not xmp_tags:
            return b''
        
        # Create XMP packet
        xmp_packet = self._create_xmp_xml(xmp_tags)
        
        # Wrap in xpacket processing instruction
        xpacket_start = b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        xpacket_end = b'\n<?xpacket end="w"?>'
        
        full_packet = xpacket_start + xmp_packet.encode('utf-8') + xpacket_end
        
        return full_packet
    
    def _create_xmp_xml(self, tags: Dict[str, Any]) -> str:
        """
        Create XMP XML structure from tags.
        
        Args:
            tags: Dictionary of XMP tags
            
        Returns:
            XML string
        """
        # Register namespaces
        for prefix, uri in self.NAMESPACES.items():
            ET.register_namespace(prefix, uri)
        
        # Create root element
        xmpmeta = ET.Element('{adobe:ns:meta/}xmpmeta')
        xmpmeta.set('{http://www.w3.org/XML/1998/namespace}lang', 'x-default')
        
        rdf = ET.SubElement(xmpmeta, '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF')
        description = ET.SubElement(rdf, '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')
        
        ns_lookup = {uri: prefix for prefix, uri in self.NAMESPACES.items()}
        dynamic_ns_counter = 0
        
        for tag_name, value in tags.items():
            if tag_name.startswith('{') and '}' in tag_name:
                uri, local_name = tag_name[1:].split('}', 1)
                prefix = ns_lookup.get(uri)
                if prefix is None:
                    prefix = f'ns{dynamic_ns_counter}'
                    dynamic_ns_counter += 1
                    ns_lookup[uri] = prefix
                    ET.register_namespace(prefix, uri)
                full_name = f'{{{uri}}}{local_name}'
                self._add_xmp_property(description, full_name, value)
                continue
            
            namespace, local_name = self._parse_tag_name(tag_name)
            if not namespace:
                continue
            ns_uri = self.NAMESPACES.get(namespace, f'http://ns.adobe.com/{namespace}/1.0/')
            if ns_uri not in ns_lookup:
                ns_lookup[ns_uri] = namespace
                ET.register_namespace(namespace, ns_uri)
            full_name = f'{{{ns_uri}}}{local_name}'
            self._add_xmp_property(description, full_name, value)
        
        # Convert to string
        xml_str = ET.tostring(xmpmeta, encoding='unicode', method='xml')
        
        # Pretty print
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent='  ', encoding=None)
        
        # Remove XML declaration added by toprettyxml (XMP packets don't need it when wrapped in xpacket)
        # toprettyxml adds "<?xml version="1.0" ?>\n" at the beginning
        if pretty_xml.startswith('<?xml'):
            # Find the end of the XML declaration
            decl_end = pretty_xml.find('?>')
            if decl_end != -1:
                # Skip the XML declaration and any following whitespace
                pretty_xml = pretty_xml[decl_end + 2:].lstrip('\n\r\t ')
        
        return pretty_xml
    
    def _parse_tag_name(self, tag_name: str) -> tuple:
        """
        Parse XMP tag name into namespace and local name.
        
        Args:
            tag_name: Tag name (e.g., 'Title', 'dc:Title', 'xmp:Title')
            
        Returns:
            Tuple of (namespace_prefix, local_name)
        """
        if ':' in tag_name:
            parts = tag_name.split(':', 1)
            return parts[0], parts[1]
        
        # Default namespace based on common tags
        default_namespaces = {
            'Title': 'dc',
            'Creator': 'dc',
            'Subject': 'dc',
            'Description': 'dc',
            'CreateDate': 'xmp',
            'ModifyDate': 'xmp',
            'MetadataDate': 'xmp',
            'Rating': 'xmp',
            'Label': 'xmp',
        }
        
        if tag_name in default_namespaces:
            return default_namespaces[tag_name], tag_name
        
        return 'xmp', tag_name
    
    def _add_xmp_property(self, parent: ET.Element, name: str, value: Any) -> None:
        """
        Add a property to XMP description.
        
        Args:
            parent: Parent element
            name: Property name (with namespace)
            value: Property value
        """
        if isinstance(value, (list, tuple)):
            # Bag (unordered list)
            bag = ET.SubElement(parent, name)
            bag_elem = ET.SubElement(bag, '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Bag')
            for item in value:
                li = ET.SubElement(bag_elem, '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li')
                li.text = str(item)
        elif isinstance(value, dict):
            # Structure
            struct = ET.SubElement(parent, name)
            struct_elem = ET.SubElement(struct, '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')
            for key, val in value.items():
                self._add_xmp_property(struct_elem, key, val)
        else:
            # Simple value
            elem = ET.SubElement(parent, name)
            elem.text = str(value)
    
    def build_app1_xmp_segment(self, xmp_packet: bytes) -> bytes:
        """
        Build JPEG APP1 segment containing XMP data.
        
        Args:
            xmp_packet: XMP packet bytes
            
        Returns:
            Complete APP1 segment
        """
        if not xmp_packet:
            return b''
        
        # Build APP1 segment
        segment = bytearray()
        
        # APP1 marker
        segment.extend(b'\xFF\xE1')
        
        # XMP identifier: "http://ns.adobe.com/xap/1.0/\x00"
        xmp_identifier = b'http://ns.adobe.com/xap/1.0/\x00'
        
        # Calculate length (XMP identifier + XMP packet)
        # Note: JPEG segment length field represents length AFTER the 2-byte length field itself
        length = len(xmp_identifier) + len(xmp_packet)
        
        # Ensure length doesn't exceed 65535 (max for 2 bytes)
        if length > 65535:
            raise MetadataWriteError("XMP packet too large for single APP1 segment")
        
        # Write length (big-endian)
        segment.extend(length.to_bytes(2, byteorder='big'))
        
        # XMP identifier
        segment.extend(xmp_identifier)
        
        # XMP packet
        segment.extend(xmp_packet)
        
        return bytes(segment)

