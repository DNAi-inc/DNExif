# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
XMP (Extensible Metadata Platform) parser

This module handles parsing XMP metadata from JPEG APP1 segments,
TIFF files, and other formats that support XMP.

Copyright 2025 DNAi inc.
"""

import struct
import re
import zlib
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class XMPParser:
    """
    Parser for XMP (Extensible Metadata Platform) metadata.
    
    XMP is an XML-based metadata format that can be embedded in
    various file formats including JPEG, TIFF, PNG, and PDF.
    """
    
    # XMP packet markers
    XMP_PACKET_START = b'<?xpacket begin='
    XMP_PACKET_END = b'<?xpacket end='
    XMP_HEADER = b'http://ns.adobe.com/xap/1.0/\x00'

    # Common alias mapping to normalize frequently queried tags
    XMP_ALIAS_MAP = {
        # Dublin Core title -> XMP:Title
        'DC:TITLE': 'XMP:Title',
        'XMP:TITLE': 'XMP:Title',
        # Some parsers (including this one) expose dc:title as XMP-dc:Title
        # Normalize that alias as well so PNG/JPEG XMP dc:title becomes XMP:Title.
        'XMP-DC:TITLE': 'XMP:Title',
        # Dublin Core creator/description/subject
        'DC:CREATOR': 'XMP:Creator',
        'DC:DESCRIPTION': 'XMP:Description',
        'DC:SUBJECT': 'XMP:Subject',
        # XMP core date aliases
        'XMP-XMP:MODIFYDATE': 'XMP:ModifyDate',
        'XMP-XMP:CREATEDATE': 'XMP:CreateDate',
        'XMP-XMP:METADATADATE': 'XMP:MetadataDate',
    }
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize XMP parser.
        
        Args:
            file_path: Path to file (if reading from file)
            file_data: File data bytes (if reading from memory)
        """
        if file_path:
            self.file_path = Path(file_path)
            self.file_data = None
        elif file_data:
            self.file_data = file_data
            self.file_path = None
        else:
            raise ValueError("Either file_path or file_data must be provided")
    
    def read(self, scan_entire_file: bool = False) -> Dict[str, Any]:
        """
        Read XMP metadata from file.
        
        Args:
            scan_entire_file: If True, scan entire file for XMP (slower but more thorough)
            
        Returns:
            Dictionary of XMP metadata
        """
        try:
            if scan_entire_file:
                # Scan entire file for XMP packets
                return self._scan_entire_file()
            
            # Normal XMP reading (from standard locations)
            # Read file data if needed
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            
            # Try to parse XMP from different locations
            metadata = {}
            
            # Check if it's a JPEG file
            if file_data.startswith(b'\xff\xd8'):
                metadata.update(self._parse_jpeg_xmp(file_data))
            # Check if it's a TIFF file
            elif file_data[:2] in (b'II', b'MM'):
                metadata.update(self._parse_tiff_xmp(file_data))
            # Check if it's a PNG file
            elif file_data.startswith(b'\x89PNG\r\n\x1a\n'):
                metadata.update(self._parse_png_xmp(file_data))
            # Check if it's a PDF file
            elif file_data.startswith(b'%PDF'):
                metadata.update(self._parse_pdf_xmp(file_data))
            else:
                # Try to find XMP in any location
                metadata.update(self._find_xmp_in_data(file_data))
            
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to read XMP metadata: {str(e)}")
    
    def _scan_entire_file(self) -> Dict[str, Any]:
        """
        Scan entire file for XMP packets (slower but more thorough).
        
        Returns:
            Dictionary of XMP metadata
        """
        # Read file data
        if self.file_data is None:
            with open(self.file_path, 'rb') as f:
                file_data = f.read()
        else:
            file_data = self.file_data
        
        metadata = {}
        
        # For format-specific files, use the format-specific parser first
        # (PNG XMP is compressed in iTXt chunks, so direct search won't work)
        if file_data.startswith(b'\x89PNG\r\n\x1a\n'):
            # PNG files - use PNG-specific parser
            metadata.update(self._parse_png_xmp(file_data))
        elif file_data.startswith(b'\xff\xd8'):
            # JPEG files - use JPEG-specific parser
            metadata.update(self._parse_jpeg_xmp(file_data))
        elif file_data[:2] in (b'II', b'MM'):
            # TIFF files - use TIFF-specific parser
            metadata.update(self._parse_tiff_xmp(file_data))
        elif file_data.startswith(b'%PDF'):
            # PDF files - use PDF-specific parser
            metadata.update(self._parse_pdf_xmp(file_data))
        
        # Also search for XMP packet markers throughout the file (for embedded XMP)
        offset = 0
        while offset < len(file_data):
            # Look for XMP packet start
            xmp_start = file_data.find(self.XMP_PACKET_START, offset)
            if xmp_start == -1:
                break
            
            # Find corresponding end marker
            xmp_end = file_data.find(self.XMP_PACKET_END, xmp_start)
            if xmp_end == -1:
                # Try to find end of XMP data by looking for closing tags
                xmp_end = file_data.find(b'</x:xmpmeta>', xmp_start)
                if xmp_end != -1:
                    xmp_end = file_data.find(b'>', xmp_end) + 1
            
            if xmp_end != -1:
                # Extract XMP packet
                xmp_data = file_data[xmp_start:xmp_end]
                try:
                    parsed_xmp = self._parse_xmp_packet(xmp_data)
                    metadata.update(parsed_xmp)
                except Exception:
                    pass  # Skip invalid XMP packets
            
            offset = xmp_start + 1
        
        return metadata
    
    def _parse_jpeg_xmp(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse XMP from JPEG APP1 segment.
        
        Scans all APP segments (APP0-APP15) for XMP data, not just APP1.
        This ensures XMP written by DNExif or other tools is found even if
        it's in a non-standard APP segment location.
        """
        metadata = {}
        offset = 2  # Skip JPEG signature
        
        # Scan all APP segments (APP0-APP15, markers 0xFFE0-0xFFEF)
        while offset < len(file_data) - 4:
            # Check for segment marker
            if file_data[offset] != 0xFF:
                offset += 1
                continue
            
            marker = file_data[offset + 1]
            
            # Check if this is an APP segment (0xE0-0xEF)
            if 0xE0 <= marker <= 0xEF:
                # Read segment length
                if offset + 4 > len(file_data):
                    break
                length = struct.unpack('>H', file_data[offset+2:offset+4])[0]
                
                # Check for XMP identifier (standard XMP header)
                if offset + 33 <= len(file_data) and file_data[offset+4:offset+33] == self.XMP_HEADER:
                    # Extract XMP data
                    xmp_end = offset + 2 + length
                    if xmp_end <= len(file_data):
                        xmp_data = file_data[offset+33:xmp_end]
                        try:
                            parsed_xmp = self._parse_xmp_packet(xmp_data)
                            metadata.update(parsed_xmp)
                        except Exception:
                            pass
                
                # Also search for XMP packet markers within APP segments (for non-standard XMP)
                # This helps find XMP that might be embedded differently
                segment_end = min(offset + 2 + length, len(file_data))
                segment_data = file_data[offset+4:segment_end]
                
                # Look for XMP packet start marker within this segment
                xmp_start = segment_data.find(self.XMP_PACKET_START)
                if xmp_start != -1:
                    # Find XMP packet end
                    xmp_end = segment_data.find(self.XMP_PACKET_END, xmp_start)
                    if xmp_end == -1:
                        xmp_end = segment_data.find(b'</x:xmpmeta>', xmp_start)
                        if xmp_end != -1:
                            xmp_end = segment_data.find(b'>', xmp_end) + 1
                    
                    if xmp_end != -1:
                        xmp_data = segment_data[xmp_start:xmp_end]
                        try:
                            parsed_xmp = self._parse_xmp_packet(xmp_data)
                            metadata.update(parsed_xmp)
                        except Exception:
                            pass
                
                offset += 2 + length
            elif marker == 0xD8:  # SOI
                offset += 2
            elif marker == 0xD9:  # EOI
                break
            else:
                # Skip other segments
                if offset + 4 <= len(file_data):
                    length = struct.unpack('>H', file_data[offset+2:offset+4])[0]
                    offset += 2 + length
                else:
                    offset += 1
        
        return metadata
    
    def _parse_tiff_xmp(self, file_data: bytes) -> Dict[str, Any]:
        """Parse XMP from TIFF file."""
        # XMP in TIFF is typically in ImageDescription tag or as a separate IFD
        # This is a simplified implementation
        metadata = {}
        
        # Look for XMP in the file
        xmp_data = self._find_xmp_in_data(file_data)
        if xmp_data:
            metadata.update(xmp_data)
        
        return metadata
    
    def _parse_png_xmp(self, file_data: bytes) -> Dict[str, Any]:
        """Parse XMP from PNG iTXt chunk."""
        metadata = {}
        offset = 8  # Skip PNG signature
        
        while offset < len(file_data) - 12:
            # Read chunk length
            chunk_length = struct.unpack('>I', file_data[offset:offset+4])[0]
            offset += 4
            
            # Read chunk type
            chunk_type = file_data[offset:offset+4]
            offset += 4
            
            if chunk_type == b'iTXt':
                # iTXt chunk - check for XMP
                chunk_data = file_data[offset:offset+chunk_length]
                # iTXt format: keyword (null-terminated), compression flag, compression method, language tag, translated keyword, text
                # XMP is typically in the text field
                try:
                    # Find keyword (null-terminated)
                    keyword_end = chunk_data.find(b'\x00')
                    if keyword_end == -1:
                        offset += chunk_length + 4
                        continue
                    
                    keyword = chunk_data[:keyword_end]
                    # Check if this is an XMP chunk (keyword should be "XML:com.adobe.xmp")
                    if keyword != b'XML:com.adobe.xmp':
                        offset += chunk_length + 4
                        continue
                    
                    # Read compression flag (1 byte after keyword null terminator)
                    if keyword_end + 1 >= len(chunk_data):
                        offset += chunk_length + 4
                        continue
                    
                    compression_flag = chunk_data[keyword_end + 1]
                    compression_method = chunk_data[keyword_end + 2] if keyword_end + 2 < len(chunk_data) else 0
                    
                    # Find language tag (null-terminated)
                    lang_start = keyword_end + 3
                    lang_end = chunk_data.find(b'\x00', lang_start)
                    if lang_end == -1:
                        offset += chunk_length + 4
                        continue
                    
                    # Find translated keyword (null-terminated)
                    trans_keyword_start = lang_end + 1
                    trans_keyword_end = chunk_data.find(b'\x00', trans_keyword_start)
                    if trans_keyword_end == -1:
                        offset += chunk_length + 4
                        continue
                    
                    # Text data starts after translated keyword
                    text_start = trans_keyword_end + 1
                    text_data = chunk_data[text_start:]
                    
                    # Decompress if compressed
                    if compression_flag == 1 and compression_method == 0:
                        # zlib compression
                        try:
                            text_data = zlib.decompress(text_data)
                        except Exception:
                            pass
                    
                    # Find XMP packet in text data
                    xmp_start = text_data.find(self.XMP_PACKET_START)
                    if xmp_start != -1:
                        # Find the end of the XMP packet
                        xmp_end = text_data.find(self.XMP_PACKET_END, xmp_start)
                        if xmp_end == -1:
                            # Try finding </x:xmpmeta> tag
                            xmp_end = text_data.find(b'</x:xmpmeta>', xmp_start)
                            if xmp_end != -1:
                                xmp_end = text_data.find(b'>', xmp_end) + 1
                        
                        if xmp_end != -1:
                            # Extract XMP packet (include the end marker)
                            xmp_data = text_data[xmp_start:xmp_end]
                        else:
                            # If no end marker found, use all remaining data
                            xmp_data = text_data[xmp_start:]
                        
                        # Parse XMP packet
                        try:
                            parsed_xmp = self._parse_xmp_packet(xmp_data)
                            metadata.update(parsed_xmp)
                        except Exception:
                            pass
                except Exception:
                    pass
            
            elif chunk_type == b'zTXt':
                # zTXt chunk (compressed text) - check for XMP
                # zTXt format: keyword (null-terminated), compression method (1 byte), compressed text
                chunk_data = file_data[offset:offset+chunk_length]
                try:
                    # Find keyword (null-terminated)
                    keyword_end = chunk_data.find(b'\x00')
                    if keyword_end == -1:
                        offset += chunk_length + 4
                        continue
                    
                    keyword = chunk_data[:keyword_end]
                    # Check if this is an XMP chunk (keyword should be "XML:com.adobe.xmp")
                    if keyword != b'XML:com.adobe.xmp':
                        offset += chunk_length + 4
                        continue
                    
                    # Read compression method (1 byte after null terminator)
                    if keyword_end + 1 >= len(chunk_data):
                        offset += chunk_length + 4
                        continue
                    
                    compression_method = chunk_data[keyword_end + 1]
                    # Compressed text data starts after compression method
                    compressed_text = chunk_data[keyword_end + 2:]
                    
                    # Decompress if using zlib (compression method 0)
                    if compression_method == 0:
                        try:
                            text_data = zlib.decompress(compressed_text)
                            
                            # Find XMP packet in decompressed text data
                            xmp_start = text_data.find(self.XMP_PACKET_START)
                            if xmp_start != -1:
                                # Find the end of the XMP packet
                                xmp_end = text_data.find(self.XMP_PACKET_END, xmp_start)
                                if xmp_end == -1:
                                    # Try finding </x:xmpmeta> tag
                                    xmp_end = text_data.find(b'</x:xmpmeta>', xmp_start)
                                    if xmp_end != -1:
                                        xmp_end = text_data.find(b'>', xmp_end) + 1
                                
                                if xmp_end != -1:
                                    # Extract XMP packet (include the end marker)
                                    xmp_data = text_data[xmp_start:xmp_end]
                                else:
                                    # If no end marker found, use all remaining data
                                    xmp_data = text_data[xmp_start:]
                                
                                # Parse XMP packet
                                try:
                                    parsed_xmp = self._parse_xmp_packet(xmp_data)
                                    metadata.update(parsed_xmp)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass
            
            offset += chunk_length
            offset += 4  # Skip CRC
            
            if chunk_type == b'IEND':
                break
        
        return metadata
    
    def _parse_pdf_xmp(self, file_data: bytes) -> Dict[str, Any]:
        """Parse XMP from PDF file."""
        metadata = {}
        
        # Look for explicit /Metadata streams so compressed packets are parsed
        metadata_stream = self._extract_pdf_metadata_stream(file_data)
        if metadata_stream:
            metadata.update(metadata_stream)
        else:
            # Fallback to raw search (covers uncompressed or malformed packets)
            xmp_data = self._find_xmp_in_data(file_data)
            if xmp_data:
                metadata.update(xmp_data)
        
        return metadata
    def _extract_pdf_metadata_stream(self, file_data: bytes) -> Dict[str, Any]:
        """Extract and parse PDF /Metadata stream (handles FlateDecode)."""
        metadata = {}
        if not file_data:
            return metadata

        metadata_obj_pattern = re.compile(rb'(\d+)\s+\d+\s+obj\s+<<[^>]*?/Type\s*/Metadata', re.DOTALL)
        for match in metadata_obj_pattern.finditer(file_data):
            obj_start = match.start()
            obj_end = file_data.find(b'endobj', obj_start)
            if obj_end == -1:
                obj_end = len(file_data)

            dict_start = file_data.find(b'<<', obj_start, obj_end)
            dict_end = file_data.find(b'>>', dict_start, obj_end)
            if dict_start == -1 or dict_end == -1:
                continue
            dict_end += 2
            dict_bytes = file_data[dict_start:dict_end]

            stream_start = file_data.find(b'stream', dict_end, obj_end)
            if stream_start == -1:
                continue
            stream_start += len(b'stream')
            # Skip newline(s) after stream keyword
            if file_data[stream_start:stream_start+2] == b'\r\n':
                stream_start += 2
            elif file_data[stream_start:stream_start+1] in (b'\r', b'\n'):
                stream_start += 1

            stream_end = file_data.find(b'endstream', stream_start, obj_end)
            if stream_end == -1:
                continue

            stream_bytes = file_data[stream_start:stream_end]
            if b'/FlateDecode' in dict_bytes:
                try:
                    stream_bytes = zlib.decompress(stream_bytes)
                except Exception:
                    continue

            try:
                parsed = self._parse_xmp_packet(stream_bytes)
                metadata.update(parsed)
                # Stop after first valid metadata stream
                if parsed:
                    break
            except Exception:
                continue

        return metadata
    
    def _find_xmp_in_data(self, file_data: bytes) -> Dict[str, Any]:
        """Find and parse XMP data in file bytes."""
        metadata = {}
        
        # Look for XMP packet start
        xmp_start = file_data.find(self.XMP_PACKET_START)
        if xmp_start != -1:
            # Find XMP packet end
            xmp_end = file_data.find(self.XMP_PACKET_END, xmp_start)
            if xmp_end == -1:
                # Try alternative end marker
                xmp_end = file_data.find(b'</x:xmpmeta>', xmp_start)
                if xmp_end != -1:
                    xmp_end = file_data.find(b'>', xmp_end) + 1
            
            if xmp_end != -1:
                xmp_data = file_data[xmp_start:xmp_end]
                try:
                    parsed_xmp = self._parse_xmp_packet(xmp_data)
                    metadata.update(parsed_xmp)
                except Exception:
                    pass
        
        return metadata
    
    def _parse_xmp_packet(self, xmp_data: bytes) -> Dict[str, Any]:
        """
        Parse XMP packet XML data.
        
        Args:
            xmp_data: XMP packet bytes (XML)
            
        Returns:
            Dictionary of XMP metadata
        """
        metadata = {}
        
        try:
            # Decode to string
            if isinstance(xmp_data, bytes):
                # Try UTF-8 first
                try:
                    xmp_str = xmp_data.decode('utf-8')
                except UnicodeDecodeError:
                    # Fallback to latin-1
                    xmp_str = xmp_data.decode('latin-1', errors='ignore')
            else:
                xmp_str = str(xmp_data)
            
            # Remove xpacket wrappers to keep XML well-formed
            xmp_str = re.sub(r'<\?xpacket[^>]*\?>', '', xmp_str, flags=re.IGNORECASE).strip()
            
            # Parse XML
            root = ET.fromstring(xmp_str)
            
            # Extract XMPToolkit from x:xmpmeta tag's x:xmptk attribute
            # Standard format shows this as XMP:XMPToolkit
            if root.tag.startswith('{') or root.tag.startswith('x:'):
                # Check for x:xmptk attribute (namespace-aware or not)
                xmptk_attr = None
                # Try various attribute name formats
                for attr_name in ['{http://ns.adobe.com/xap/1.0/}xmptk', 'xmptk', '{adobe:ns:meta/}xmptk']:
                    if attr_name in root.attrib:
                        xmptk_attr = root.attrib[attr_name]
                        break
                # Also check for x: prefix in attribute names
                if not xmptk_attr:
                    for attr_key, attr_value in root.attrib.items():
                        if 'xmptk' in attr_key.lower() or attr_key.endswith(':xmptk'):
                            xmptk_attr = attr_value
                            break
                if xmptk_attr:
                    metadata['XMP:XMPToolkit'] = xmptk_attr.strip()
            
            # Define XMP namespaces (expanded for video/audio formats and manufacturer-specific)
            namespaces = {
                'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                'xmp': 'http://ns.adobe.com/xap/1.0/',
                'dc': 'http://purl.org/dc/elements/1.1/',
                'photoshop': 'http://ns.adobe.com/photoshop/1.0/',
                'xmpRights': 'http://ns.adobe.com/xap/1.0/rights/',
                'tiff': 'http://ns.adobe.com/tiff/1.0/',
                'exif': 'http://ns.adobe.com/exif/1.0/',
                'crs': 'http://ns.adobe.com/camera-raw-settings/1.0/',
                'xmpMM': 'http://ns.adobe.com/xap/1.0/mm/',  # Media Management (InstanceID, DocumentID, etc.)
                'xmpDM': 'http://ns.adobe.com/xmp/1.0/DynamicMedia/',  # Dynamic Media (video/audio - DurationScale, AudioSampleType, etc.)
                'xmpG': 'http://ns.adobe.com/xap/1.0/g/',  # General
                'xmpGImg': 'http://ns.adobe.com/xap/1.0/g/img/',  # General Image
                'xmpBJ': 'http://ns.adobe.com/xap/1.0/bj/',  # Basic Job
                'xmpTPg': 'http://ns.adobe.com/xap/1.0/t/pg/',  # Paged Text
                'xmpNote': 'http://ns.adobe.com/xmp/note/',  # Note
                'stEvt': 'http://ns.adobe.com/xap/1.0/sType/ResourceEvent#',  # Resource Event (History tags: action, when, softwareAgent, instanceID, changed)
                'stRef': 'http://ns.adobe.com/xap/1.0/sType/ResourceRef#',  # Resource Reference
                'stDim': 'http://ns.adobe.com/xap/1.0/sType/Dimensions#',  # Dimensions (for videoFrameSize: w, h, unit)
                'hdrgm': 'http://ns.adobe.com/hdr-gain-map/1.0/',  # HDR Gain Map (GainMapImage, GainMapMin, GainMapMax, etc.)
                'apdi': 'http://ns.adobe.com/apdi/1.0/',  # Adobe Photoshop Document Info namespace
                'Iptc4xmpExt': 'http://iptc.org/std/Iptc4xmpExt/2008-02-29/',  # IPTC Extension (includes GenerativeAI tags)
                'iptcExt': 'http://iptc.org/std/Iptc4xmpExt/2008-02-29/',  # IPTC Extension alias
                'acdsee-rs': 'http://ns.acdsee.com/iptc/1.0/',  # ACDSee IPTC namespace
                'acdsee': 'http://ns.acdsee.com/iptc/1.0/',  # ACDSee alias
                'photomech': 'http://ns.camerabits.com/photomechanic/1.0/',  # Photo Mechanic namespace
                'GCamera': 'http://ns.google.com/photos/1.0/camera/',  # Google Camera namespace
                'gCamera': 'http://ns.google.com/photos/1.0/camera/',  # Google Camera alias
                'xmpDSA': 'http://ns.leica-camera.com/xmp/1.0/DSA/',  # Leica Digital Signature Algorithm namespace
                'leaf': 'http://www.creo.com/global/products/digital_photography_leaf/default.htm/',  # Leaf camera metadata
                'x': 'adobe:ns:meta/',
                # Additional common XMP namespaces
                'aux': 'http://ns.adobe.com/exif/1.0/aux/',  # Auxiliary EXIF namespace
                'lr': 'http://ns.adobe.com/lightroom/1.0/',  # Adobe Lightroom namespace
                'plus': 'http://ns.useplus.org/ldf/xmp/1.0/',  # PLUS (Picture Licensing Universal System) namespace
                'stJob': 'http://ns.adobe.com/xap/1.0/sType/Job#',  # Job namespace
                'xmpidq': 'http://ns.adobe.com/xmp/identifier/qual/1.0/',  # XMP Identifier Qualifier namespace
                'stVer': 'http://ns.adobe.com/xap/1.0/sType/Version#',  # Version namespace
                'stFnt': 'http://ns.adobe.com/xap/1.0/sType/Font#',  # Font namespace
                'stMfs': 'http://ns.adobe.com/xap/1.0/sType/ManifestItem#',  # Manifest Item namespace
                'crs': 'http://ns.adobe.com/camera-raw-settings/1.0/',  # Camera Raw Settings (already defined but ensuring it's here)
                'Iptc4xmpCore': 'http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/',  # IPTC Core namespace
                'prism': 'http://prismstandard.org/namespaces/basic/2.0/',  # PRISM namespace
                'prl': 'http://prismstandard.org/namespaces/prl/2.0/',  # PRISM Rights Language namespace
                'prm': 'http://prismstandard.org/namespaces/prm/2.0/',  # PRISM Magazine namespace
                'xmpGImg': 'http://ns.adobe.com/xap/1.0/g/img/',  # General Image namespace
                'xmpTPg': 'http://ns.adobe.com/xap/1.0/t/pg/',  # Paged Text namespace
                'xmpBJ': 'http://ns.adobe.com/xap/1.0/bj/',  # Basic Job namespace
            }
            
            # Find ALL RDF Description elements (XMP can have multiple Description elements with different namespaces)
            rdf_descs = root.findall('.//rdf:Description', namespaces)
            if not rdf_descs:
                # Try without namespace
                rdf_descs = root.findall('.//Description')
            
            # Process each Description element
            for rdf_desc in rdf_descs:
                # Extract namespaces declared in this Description element (e.g., xmlns:leaf=...)
                # These namespaces might not be in the root element
                local_namespaces = dict(namespaces)  # Start with global namespaces
                for attr_name, attr_value in rdf_desc.attrib.items():
                    if attr_name.startswith('xmlns:'):
                        # Extract namespace prefix (e.g., "xmlns:leaf" -> "leaf")
                        ns_prefix = attr_name.split(':', 1)[1] if ':' in attr_name else attr_name[6:]
                        local_namespaces[ns_prefix] = attr_value
                    elif attr_name == 'xmlns':
                        # Default namespace
                        local_namespaces[''] = attr_value
                
                # Extract all attributes and child elements
                for attr_name, attr_value in rdf_desc.attrib.items():
                    # Handle namespace prefixes
                    if '}' in attr_name:
                        # Handle namespace in curly braces format {uri}localname
                        ns_end = attr_name.find('}')
                        if ns_end != -1:
                            ns_uri = attr_name[1:ns_end]
                            tag = attr_name[ns_end+1:]
                            # Find namespace prefix
                            namespace = 'XMP'
                            for ns_prefix, uri in namespaces.items():
                                if uri == ns_uri:
                                    # Map xmpMM to XMPMM for Media Management tags (DocumentID, InstanceID, etc.)
                                    if ns_prefix == 'xmpMM':
                                        namespace = 'XMPMM'
                                    # Map xmpDM to XMP for Dynamic Media tags (DurationScale, AudioSampleType, etc.)
                                    # Standard format shows these as XMP:DurationScale, not XMPDM:DurationScale
                                    elif ns_prefix == 'xmpDM':
                                        namespace = 'XMP'
                                    # Map hdrgm to HDRGM for HDR Gain Map tags (standard format)
                                    elif ns_prefix == 'hdrgm':
                                        namespace = 'HDRGM'
                                    # Map apdi to APDI for Adobe Photoshop Document Info tags
                                    elif ns_prefix == 'apdi':
                                        namespace = 'APDI'
                                    # Map Iptc4xmpExt/iptcExt to IPTC for IPTC Extension tags (standard format)
                                    elif ns_prefix in ('Iptc4xmpExt', 'iptcExt'):
                                        namespace = 'IPTC'
                                    # Map acdsee-rs/acdsee to ACDSEE for ACDSee tags (standard format)
                                    elif ns_prefix in ('acdsee-rs', 'acdsee'):
                                        namespace = 'ACDSEE'
                                    # Map photomech to PHOTOMECH for Photo Mechanic tags (standard format)
                                    elif ns_prefix == 'photomech':
                                        namespace = 'PHOTOMECH'
                                    # Map GCamera/gCamera to GCAMERA for Google Camera tags (standard format)
                                    elif ns_prefix in ('GCamera', 'gCamera'):
                                        namespace = 'GCAMERA'
                                    # Map xmpDSA to XMPDSA for Leica tags (standard format)
                                    elif ns_prefix == 'xmpDSA':
                                        namespace = 'XMPDSA'
                                    # Map xmp namespace to XMP (not XMP-xmp) - standard format
                                    elif ns_prefix == 'xmp':
                                        namespace = 'XMP'
                                    # Map common XMP namespaces to XMP- prefix format (standard format)
                                    elif ns_prefix in ('dc', 'tiff', 'exif', 'leaf'):
                                        namespace = f'XMP-{ns_prefix}'
                                    else:
                                        namespace = ns_prefix.upper()
                                    break
                            full_tag = f"{namespace}:{tag}"
                        else:
                            full_tag = f"XMP:{attr_name}"
                    elif ':' in attr_name:
                        namespace, tag = attr_name.split(':', 1)
                        # Map xmpMM to XMPMM for Media Management tags
                        if namespace.lower() == 'xmpmm':
                            namespace = 'XMPMM'
                        # Map xmpDM to XMP for Dynamic Media tags (standard format output)
                        elif namespace.lower() == 'xmpdm':
                            namespace = 'XMP'
                        # Map hdrgm to HDRGM for HDR Gain Map tags (standard format)
                        elif namespace.lower() == 'hdrgm':
                            namespace = 'HDRGM'
                        # Map apdi to APDI for Adobe Photoshop Document Info tags
                        elif namespace.lower() == 'apdi':
                            namespace = 'APDI'
                        # Map Iptc4xmpExt/iptcExt to IPTC for IPTC Extension tags (standard format)
                        elif namespace.lower() in ('iptc4xmpext', 'iptcext'):
                            namespace = 'IPTC'
                        # Map acdsee-rs/acdsee to ACDSEE for ACDSee tags (standard format)
                        elif namespace.lower() in ('acdsee-rs', 'acdsee'):
                            namespace = 'ACDSEE'
                        # Map photomech to PHOTOMECH for Photo Mechanic tags (standard format)
                        elif namespace.lower() == 'photomech':
                            namespace = 'PHOTOMECH'
                        # Map GCamera/gCamera to GCAMERA for Google Camera tags (standard format)
                        elif namespace.lower() in ('gcamera', 'gcamera'):
                            namespace = 'GCAMERA'
                        # Map xmpDSA to XMPDSA for Leica tags (standard format)
                        elif namespace.lower() == 'xmpdsa':
                            namespace = 'XMPDSA'
                        # Map xmp namespace to XMP (not XMP-xmp) - standard format
                        elif namespace.lower() == 'xmp':
                            namespace = 'XMP'
                        # Map common XMP namespaces to XMP- prefix format (standard format)
                        elif namespace.lower() in ('dc', 'tiff', 'exif', 'leaf'):
                            namespace = f'XMP-{namespace.lower()}'
                        full_tag = f"{namespace}:{tag}"
                    else:
                        full_tag = f"XMP:{attr_name}"
                    
                    self._store_xmp_value(metadata, full_tag, attr_value)
                
                # Extract child elements (including nested structures)
                # Use local_namespaces which includes namespaces declared in this Description element
                self._extract_xmp_elements(rdf_desc, local_namespaces, metadata)
        
        except ET.ParseError:
            # Try to extract basic information even if XML is malformed
            pass
        except Exception:
            pass
        
        # CRITICAL: Normalize ALL XMP-xmp: tags to XMP: tags at the end of parsing
        # This ensures all tags in the xmp namespace are shown as XMP: (not XMP-xmp:)
        # Standard format shows xmp namespace tags as XMP: prefix
        normalized_metadata = {}
        keys_to_remove = []
        for key, value in metadata.items():
            if key.startswith('XMP-xmp:'):
                # Normalize XMP-xmp:TagName to XMP:TagName
                normalized_key = key.replace('XMP-xmp:', 'XMP:', 1)
                # Only add normalized key if it doesn't already exist
                if normalized_key not in metadata and normalized_key not in normalized_metadata:
                    normalized_metadata[normalized_key] = value
                # Mark original key for removal (we'll keep it if normalized key already exists)
                keys_to_remove.append(key)
            else:
                normalized_metadata[key] = value
        
        # Remove original XMP-xmp: keys (they've been normalized)
        for key in keys_to_remove:
            if key in normalized_metadata:
                del normalized_metadata[key]
        
        return normalized_metadata

    def _extract_xmp_elements(self, parent: ET.Element, namespaces: Dict[str, str], metadata: Dict[str, Any]) -> None:
        """
        Recursively extract XMP elements from XML tree.
        
        Args:
            parent: Parent XML element to extract from
            namespaces: Dictionary of namespace prefixes to URIs
            metadata: Metadata dictionary to update
        """
        for child in parent:
            tag_name = child.tag
            # Remove namespace prefix from tag
            if '}' in tag_name:
                ns_end = tag_name.find('}')
                if ns_end != -1:
                    ns_uri = tag_name[1:ns_end]
                    tag_name = tag_name[ns_end+1:]
                    # Find namespace prefix
                    namespace = 'XMP'
                    for ns_prefix, uri in namespaces.items():
                        if uri == ns_uri:
                            # Map hdrgm to HDRGM for HDR Gain Map tags (standard format)
                            if ns_prefix == 'hdrgm':
                                namespace = 'HDRGM'
                            # Map apdi to APDI for Adobe Photoshop Document Info tags
                            elif ns_prefix == 'apdi':
                                namespace = 'APDI'
                            # Map Iptc4xmpExt/iptcExt to IPTC for IPTC Extension tags (standard format)
                            elif ns_prefix in ('Iptc4xmpExt', 'iptcExt'):
                                namespace = 'IPTC'
                            # Map acdsee-rs/acdsee to ACDSEE for ACDSee tags (standard format)
                            elif ns_prefix in ('acdsee-rs', 'acdsee'):
                                namespace = 'ACDSEE'
                            # Map photomech to PHOTOMECH for Photo Mechanic tags (standard format)
                            elif ns_prefix == 'photomech':
                                namespace = 'PHOTOMECH'
                            # Map GCamera/gCamera to GCAMERA for Google Camera tags (standard format)
                            elif ns_prefix in ('GCamera', 'gCamera'):
                                namespace = 'GCAMERA'
                            # Map xmpDSA to XMPDSA for Leica tags (standard format)
                            elif ns_prefix == 'xmpDSA':
                                namespace = 'XMPDSA'
                            # Map xmp namespace to XMP (not XMP-xmp) - standard format
                            elif ns_prefix == 'xmp':
                                namespace = 'XMP'
                            # Map common XMP namespaces to XMP- prefix format (standard format)
                            elif ns_prefix in ('dc', 'tiff', 'exif', 'leaf'):
                                namespace = f'XMP-{ns_prefix}'
                            # Map lr to LR for Lightroom tags (standard format)
                            elif ns_prefix == 'lr':
                                namespace = 'LR'
                            # Map aux to AUX for Auxiliary EXIF tags (standard format)
                            elif ns_prefix == 'aux':
                                namespace = 'AUX'
                            # Map plus to PLUS for PLUS namespace tags
                            elif ns_prefix == 'plus':
                                namespace = 'PLUS'
                            # Map stJob to XMP for Job tags (standard format)
                            elif ns_prefix == 'stJob':
                                namespace = 'XMP'
                            # Map xmpidq to XMPIDQ for Identifier Qualifier tags
                            elif ns_prefix == 'xmpidq':
                                namespace = 'XMPIDQ'
                            # Map stVer to XMP for Version tags (standard format)
                            elif ns_prefix == 'stVer':
                                namespace = 'XMP'
                            # Map stFnt to XMP for Font tags
                            elif ns_prefix == 'stFnt':
                                namespace = 'XMP'
                            # Map stMfs to XMP for Manifest Item tags
                            elif ns_prefix == 'stMfs':
                                namespace = 'XMP'
                            # Map Iptc4xmpCore to IPTC for IPTC Core tags (standard format)
                            elif ns_prefix == 'Iptc4xmpCore':
                                namespace = 'IPTC'
                            # Map prism to PRISM for PRISM namespace tags
                            elif ns_prefix == 'prism':
                                namespace = 'PRISM'
                            # Map prl to PRL for PRISM Rights Language tags
                            elif ns_prefix == 'prl':
                                namespace = 'PRL'
                            # Map prm to PRM for PRISM Magazine tags
                            elif ns_prefix == 'prm':
                                namespace = 'PRM'
                            # Map xmpGImg to XMP for General Image tags (standard format)
                            elif ns_prefix == 'xmpGImg':
                                namespace = 'XMP'
                            # Map xmpTPg to XMP for Paged Text tags (standard format)
                            elif ns_prefix == 'xmpTPg':
                                namespace = 'XMP'
                            # Map xmpBJ to XMP for Basic Job tags (standard format)
                            elif ns_prefix == 'xmpBJ':
                                namespace = 'XMP'
                            # Map crs to CRS for Camera Raw Settings tags (standard format)
                            elif ns_prefix == 'crs':
                                namespace = 'CRS'
                            else:
                                # For unknown namespaces, use the prefix uppercase or try to extract from URI
                                namespace = ns_prefix.upper() if ns_prefix else 'XMP'
                            break
                else:
                    tag_name = tag_name.split('}')[1] if '}' in tag_name else tag_name
                    namespace = 'XMP'
            else:
                namespace = 'XMP'
            
            # Get namespace from tag if not already determined
            if namespace == 'XMP':
                for ns_prefix, ns_uri in namespaces.items():
                    if ns_uri in child.tag:
                        # Map xmpMM to XMPMM for Media Management tags
                        if ns_prefix == 'xmpMM':
                            namespace = 'XMPMM'
                        # Map xmpDM to XMP for Dynamic Media tags (standard format output)
                        elif ns_prefix == 'xmpDM':
                            namespace = 'XMP'
                        # Map hdrgm to HDRGM for HDR Gain Map tags (standard format)
                        elif ns_prefix == 'hdrgm':
                            namespace = 'HDRGM'
                        # Map apdi to APDI for Adobe Photoshop Document Info tags
                        elif ns_prefix == 'apdi':
                            namespace = 'APDI'
                        # Map Iptc4xmpExt/iptcExt to IPTC for IPTC Extension tags (standard format)
                        elif ns_prefix in ('Iptc4xmpExt', 'iptcExt'):
                            namespace = 'IPTC'
                        # Map acdsee-rs/acdsee to ACDSEE for ACDSee tags (standard format)
                        elif ns_prefix in ('acdsee-rs', 'acdsee'):
                            namespace = 'ACDSEE'
                        # Map photomech to PHOTOMECH for Photo Mechanic tags (standard format)
                        elif ns_prefix == 'photomech':
                            namespace = 'PHOTOMECH'
                        # Map GCamera/gCamera to GCAMERA for Google Camera tags (standard format)
                        elif ns_prefix in ('GCamera', 'gCamera'):
                            namespace = 'GCAMERA'
                        # Map xmpDSA to XMPDSA for Leica tags (standard format)
                        elif ns_prefix == 'xmpDSA':
                            namespace = 'XMPDSA'
                        # Map leaf to XMP-leaf for Leaf camera metadata in XMP (standard format output)
                        elif ns_prefix == 'leaf':
                            namespace = 'XMP-leaf'
                        # Map common XMP namespaces to XMP- prefix format (standard format)
                        elif ns_prefix in ('dc', 'xmp', 'tiff', 'exif'):
                            namespace = f'XMP-{ns_prefix}'
                        else:
                            namespace = ns_prefix.upper()
                        break
            
            # Get value
            value = child.text if child.text else ''
            
            # Check if this is the xmpMM:History element (contains a Seq of Description elements)
            # History tags are reconstructed from the Seq structure by standard format
            if tag_name.lower() == 'history' and namespace == 'XMPMM':
                # This is the History element - it contains a Seq of Description elements
                # Each Description has stEvt attributes that map to HistoryAction, HistoryWhen, etc.
                seq = child.find('.//rdf:Seq', namespaces)
                if seq is not None:
                    # Extract History tags from all Description elements in the Seq
                    history_actions = []
                    history_whens = []
                    history_software_agents = []
                    history_instance_ids = []
                    history_changeds = []
                    
                    for li in seq.findall('.//rdf:li', namespaces):
                        # stEvt attributes are directly on the rdf:li elements, not on nested Description
                        # Extract stEvt attributes from the li element itself
                        for attr_name, attr_value in li.attrib.items():
                            # Check if attribute name contains stEvt namespace (can be stEvt:action or {uri}action format)
                            if '}' in attr_name:
                                ns_end = attr_name.find('}')
                                if ns_end != -1:
                                    ns_uri = attr_name[1:ns_end]
                                    attr_tag = attr_name[ns_end+1:]
                                    
                                    # Check if this is an stEvt namespace attribute
                                    if ns_uri == 'http://ns.adobe.com/xap/1.0/sType/ResourceEvent#':
                                        if attr_tag == 'action':
                                            history_actions.append(attr_value)
                                        elif attr_tag == 'when':
                                            # Convert ISO format to standard format (2024-06-13T12:18:28+03:00 -> 2024:06:13 12:18:28+03:00)
                                            when_formatted = attr_value.replace('T', ' ').replace('-', ':')
                                            history_whens.append(when_formatted)
                                        elif attr_tag == 'softwareAgent':
                                            history_software_agents.append(attr_value)
                                        elif attr_tag == 'instanceID':
                                            history_instance_ids.append(attr_value)
                                        elif attr_tag == 'changed':
                                            history_changeds.append(attr_value)
                            elif ':' in attr_name and attr_name.startswith('stEvt:'):
                                # Handle stEvt:action format (if namespace is declared with prefix)
                                attr_tag = attr_name.split(':', 1)[1]
                                if attr_tag == 'action':
                                    history_actions.append(attr_value)
                                elif attr_tag == 'when':
                                    when_formatted = attr_value.replace('T', ' ').replace('-', ':')
                                    history_whens.append(when_formatted)
                                elif attr_tag == 'softwareAgent':
                                    history_software_agents.append(attr_value)
                                elif attr_tag == 'instanceID':
                                    history_instance_ids.append(attr_value)
                                elif attr_tag == 'changed':
                                    history_changeds.append(attr_value)
                    
                    # Store History tags as comma-separated strings (matching standard format)
                    # Standard format shows: "saved, saved, saved" not "['saved', 'saved', 'saved']"
                    if history_actions:
                        formatted = ', '.join(history_actions)
                        self._store_xmp_value(metadata, 'XMP:HistoryAction', formatted)
                    if history_whens:
                        formatted = ', '.join(history_whens)
                        self._store_xmp_value(metadata, 'XMP:HistoryWhen', formatted)
                    if history_software_agents:
                        formatted = ', '.join(history_software_agents)
                        self._store_xmp_value(metadata, 'XMP:HistorySoftwareAgent', formatted)
                    if history_instance_ids:
                        formatted = ', '.join(history_instance_ids)
                        self._store_xmp_value(metadata, 'XMP:HistoryInstanceID', formatted)
                    if history_changeds:
                        formatted = ', '.join(history_changeds)
                        self._store_xmp_value(metadata, 'XMP:HistoryChanged', formatted)
                    
                    continue  # Skip normal processing for History element
            
            # Handle structured xmpDM elements (duration, videoFrameSize, startTimecode, altTimecode)
            # These elements have attributes directly on the element, not as nested children
            # Check if this is an xmpDM element by checking the namespace URI in the tag
            is_xmpdm_element = False
            if '}' in child.tag:
                ns_end = child.tag.find('}')
                if ns_end != -1:
                    ns_uri = child.tag[1:ns_end]
                    if ns_uri == 'http://ns.adobe.com/xmp/1.0/DynamicMedia/':
                        is_xmpdm_element = True
            
            if is_xmpdm_element and tag_name.lower() in ('duration', 'videoframesize', 'starttimecode', 'alttimecode'):
                # Extract attributes from the element itself
                for attr_name, attr_value in child.attrib.items():
                    if '}' in attr_name:
                        ns_end = attr_name.find('}')
                        if ns_end != -1:
                            ns_uri = attr_name[1:ns_end]
                            attr_tag = attr_name[ns_end+1:]
                            
                            # Find namespace prefix
                            found_ns_prefix = None
                            for ns_prefix, uri in namespaces.items():
                                if uri == ns_uri:
                                    found_ns_prefix = ns_prefix
                                    break
                            
                            # Map attributes to standard format tag names
                            if tag_name.lower() == 'duration':
                                if attr_tag == 'value':
                                    self._store_xmp_value(metadata, 'XMP:DurationValue', attr_value)
                                elif attr_tag == 'scale':
                                    # Convert "1/90000" to decimal format like standard format
                                    if '/' in attr_value:
                                        try:
                                            num, den = map(int, attr_value.split('/'))
                                            if den != 0:
                                                decimal = num / den
                                                self._store_xmp_value(metadata, 'XMP:DurationScale', f"{decimal:.15e}")
                                            else:
                                                self._store_xmp_value(metadata, 'XMP:DurationScale', attr_value)
                                        except (ValueError, ZeroDivisionError):
                                            self._store_xmp_value(metadata, 'XMP:DurationScale', attr_value)
                                    else:
                                        self._store_xmp_value(metadata, 'XMP:DurationScale', attr_value)
                            
                            elif tag_name.lower() == 'videoframesize':
                                if found_ns_prefix == 'stDim':
                                    if attr_tag == 'w':
                                        self._store_xmp_value(metadata, 'XMP:VideoFrameSizeW', attr_value)
                                    elif attr_tag == 'h':
                                        self._store_xmp_value(metadata, 'XMP:VideoFrameSizeH', attr_value)
                                    elif attr_tag == 'unit':
                                        self._store_xmp_value(metadata, 'XMP:VideoFrameSizeUnit', attr_value)
                            
                            elif tag_name.lower() == 'starttimecode':
                                if found_ns_prefix == 'xmpDM':
                                    if attr_tag == 'timeValue':
                                        self._store_xmp_value(metadata, 'XMP:StartTimecodeTimeValue', attr_value)
                                    elif attr_tag == 'timeFormat':
                                        # Format timecode format string to standard format
                                        # "2997NonDropTimecode" -> "29.97 fps (non-drop)"
                                        formatted = self._format_timecode_format(attr_value)
                                        self._store_xmp_value(metadata, 'XMP:StartTimecodeTimeFormat', formatted)
                            
                            elif tag_name.lower() == 'alttimecode':
                                if found_ns_prefix == 'xmpDM':
                                    if attr_tag == 'timeValue':
                                        self._store_xmp_value(metadata, 'XMP:AltTimecodeTimeValue', attr_value)
                                    elif attr_tag == 'timeFormat':
                                        # Format timecode format string to standard format
                                        formatted = self._format_timecode_format(attr_value)
                                        self._store_xmp_value(metadata, 'XMP:AltTimecodeTimeFormat', formatted)
            
            # Handle photoshop:CameraProfiles structured value
            # CameraProfiles is a Bag/Seq containing Description elements with camera profile information
            is_camera_profiles = False
            if '}' in child.tag:
                ns_end = child.tag.find('}')
                if ns_end != -1:
                    ns_uri = child.tag[1:ns_end]
                    if ns_uri == 'http://ns.adobe.com/photoshop/1.0/' and tag_name.lower() == 'cameraprofiles':
                        is_camera_profiles = True
            
            if is_camera_profiles:
                # Extract CameraProfiles structured value
                # CameraProfiles contains a Bag/Seq of Description elements
                profile_list = child.find('.//rdf:Bag', namespaces) or child.find('.//rdf:Seq', namespaces)
                if profile_list is not None:
                    profiles = []
                    for li in profile_list.findall('.//rdf:li', namespaces):
                        # Each li contains a Description element with profile attributes
                        desc = li.find('.//rdf:Description', namespaces)
                        if desc is not None:
                            profile_info = {}
                            for attr_name, attr_value in desc.attrib.items():
                                if '}' in attr_name:
                                    attr_tag = attr_name.split('}')[1] if '}' in attr_name else attr_name
                                    profile_info[attr_tag] = attr_value
                                elif ':' in attr_name:
                                    attr_tag = attr_name.split(':')[1] if ':' in attr_name else attr_name
                                    profile_info[attr_tag] = attr_value
                                else:
                                    profile_info[attr_name] = attr_value
                            
                            if profile_info:
                                profiles.append(profile_info)
                    
                    if profiles:
                        # Store as structured value
                        self._store_xmp_value(metadata, 'XMP-photoshop:CameraProfiles', profiles)
                        # Also store count
                        self._store_xmp_value(metadata, 'XMP-photoshop:CameraProfilesCount', len(profiles))
                        # Store individual profile information
                        for i, profile in enumerate(profiles[:10], 1):  # Limit to 10 profiles
                            for key, value in profile.items():
                                self._store_xmp_value(metadata, f'XMP-photoshop:CameraProfile{i}:{key}', value)
                    continue  # Skip normal processing for CameraProfiles
            
            # Handle array elements (Bag, Seq, Alt)
            if child.tag.endswith('}Bag') or child.tag.endswith('}Seq') or child.tag.endswith('}Alt'):
                # Array type
                items = []
                for item in child.findall('.//rdf:li', namespaces):
                    if item.text:
                        items.append(item.text)
                value = items if items else value
                
                # Check if parent element (the one containing this Bag) is a History tag
                # The parent's tag name would be like "xmpMM:HistoryAction" which contains the Bag
                # We need to check the parent element's tag, not the Bag element itself
                parent_tag_name = None
                if hasattr(child, 'getparent') or hasattr(parent, 'tag'):
                    # Get the actual element name that contains this Bag
                    # The child element IS the HistoryAction element (which contains the Bag)
                    # So tag_name should already be "HistoryAction" (after namespace removal)
                    # But we need to check the full tag before namespace removal
                    full_parent_tag = child.tag
                    if '}' in full_parent_tag:
                        ns_end = full_parent_tag.find('}')
                        if ns_end != -1:
                            parent_tag_name = full_parent_tag[ns_end+1:]
                
                # Check if this is a History tag (HistoryAction, HistoryWhen, etc.)
                # History tags are stored as XMPMM:History* but Standard format shows them as XMP:History*
                if (tag_name.lower().startswith('history') or 
                    (parent_tag_name and parent_tag_name.lower().startswith('history'))):
                    # Store as XMP:History* (not XMPMM:History*) to standard format
                    # Format as string representation like standard format: "['saved', 'saved', 'saved']"
                    if isinstance(value, list) and len(value) > 0:
                        formatted_value = str(value).replace("'", "'")  # Keep single quotes
                        # Use parent tag name if available, otherwise use tag_name
                        history_tag = parent_tag_name if parent_tag_name and parent_tag_name.lower().startswith('history') else tag_name
                        full_tag = f"XMP:{history_tag[0].upper() + history_tag[1:]}"  # Capitalize first letter
                        self._store_xmp_value(metadata, full_tag, formatted_value)
                        # Also store with XMPMM prefix for compatibility
                        xmpmm_tag = f"XMPMM:{history_tag[0].upper() + history_tag[1:]}"
                        self._store_xmp_value(metadata, xmpmm_tag, formatted_value)
                    continue  # Skip normal processing for History tags
            # Handle nested Description elements (for complex structures like xmpMM:History)
            elif child.tag.endswith('}Description') or 'Description' in child.tag:
                # Extract attributes from nested Description
                nested_attrs = {}
                for attr_name, attr_value in child.attrib.items():
                    if '}' in attr_name:
                        ns_end = attr_name.find('}')
                        if ns_end != -1:
                            ns_uri = attr_name[1:ns_end]
                            nested_tag = attr_name[ns_end+1:]
                            # Find namespace prefix
                            nested_ns = 'XMP'
                            found_ns_prefix = None
                            for ns_prefix, uri in namespaces.items():
                                if uri == ns_uri:
                                    found_ns_prefix = ns_prefix
                                    # Map xmpMM to XMPMM for Media Management tags
                                    if ns_prefix == 'xmpMM':
                                        nested_ns = 'XMPMM'
                                    # Map xmpDM to XMP for Dynamic Media tags (standard format output)
                                    elif ns_prefix == 'xmpDM':
                                        nested_ns = 'XMP'
                                    else:
                                        nested_ns = ns_prefix.upper()
                                    break
                            # For stEvt namespace (History tags), map to XMPMM:History* format
                            if found_ns_prefix == 'stEvt':
                                # Map stEvt:action -> XMPMM:HistoryAction, stEvt:when -> XMPMM:HistoryWhen, etc.
                                history_tag_name = 'History' + nested_tag[0].upper() + nested_tag[1:] if len(nested_tag) > 1 else 'History' + nested_tag.upper()
                                nested_attrs[f"XMPMM:{history_tag_name}"] = attr_value
                            # For stRef namespace (DerivedFrom tags), map to XMPMM:DerivedFrom* format
                            elif found_ns_prefix == 'stRef':
                                # Map stRef:documentID -> XMPMM:DerivedFromDocumentID, stRef:instanceID -> XMPMM:DerivedFromInstanceID, etc.
                                derived_from_tag_name = 'DerivedFrom' + nested_tag[0].upper() + nested_tag[1:] if len(nested_tag) > 1 else 'DerivedFrom' + nested_tag.upper()
                                nested_attrs[f"XMPMM:{derived_from_tag_name}"] = attr_value
                        else:
                                nested_attrs[f"{nested_ns}:{nested_tag}"] = attr_value
                    elif ':' in attr_name:
                        # Check if it's a stEvt namespace tag (History)
                        if attr_name.startswith('stEvt:') or attr_name.startswith('{http://ns.adobe.com/xap/1.0/sType/ResourceEvent#}'):
                            # Map stEvt:action -> XMPMM:HistoryAction, etc.
                            tag_part = attr_name.split(':', 1)[1] if ':' in attr_name else attr_name.split('}')[1] if '}' in attr_name else attr_name
                            history_tag_name = 'History' + tag_part[0].upper() + tag_part[1:] if len(tag_part) > 1 else 'History' + tag_part.upper()
                            nested_attrs[f"XMPMM:{history_tag_name}"] = attr_value
                        # Check if it's a stRef namespace tag (DerivedFrom)
                        elif attr_name.startswith('stRef:') or attr_name.startswith('{http://ns.adobe.com/xap/1.0/sType/ResourceRef#}'):
                            # Map stRef:documentID -> XMPMM:DerivedFromDocumentID, etc.
                            tag_part = attr_name.split(':', 1)[1] if ':' in attr_name else attr_name.split('}')[1] if '}' in attr_name else attr_name
                            derived_from_tag_name = 'DerivedFrom' + tag_part[0].upper() + tag_part[1:] if len(tag_part) > 1 else 'DerivedFrom' + tag_part.upper()
                            nested_attrs[f"XMPMM:{derived_from_tag_name}"] = attr_value
                        else:
                            nested_attrs[attr_name] = attr_value
                    else:
                        nested_attrs[f"XMP:{attr_name}"] = attr_value
                
                # Store nested attributes
                for nested_key, nested_value in nested_attrs.items():
                    self._store_xmp_value(metadata, nested_key, nested_value)
                
                # Recursively extract nested elements
                self._extract_xmp_elements(child, namespaces, metadata)
                continue
            
            # Handle rdf:li elements (list items)
            if 'li' in tag_name.lower() or child.tag.endswith('}li'):
                # This is a list item, value is already extracted
                pass
            else:
                # Determine full tag name with proper namespace
                # For xmpMM namespace tags, use XMPMM prefix
                if namespace == 'XMPMM':
                    full_tag = f"XMPMM:{tag_name}"
                elif namespace == 'XMP' or namespace == 'XMPDM':
                    # Use XMP prefix for standard XMP tags and xmpDM tags
                    full_tag = f"XMP:{tag_name}"
                    # Standard format shows xmpDM tags (DurationScale, AudioSampleType, etc.) as XMP:DurationScale
                    # Common XMP tags: CreateDate, ModifyDate, MetadataDate, CreatorTool, Format
                    # xmpDM tags: DurationScale, AudioSampleType, VideoFrameSizeH, VideoPixelAspectRatio, etc.
                    full_tag = f"XMP:{tag_name}"
                else:
                    full_tag = f"{namespace}:{tag_name}"
                
                self._store_xmp_value(metadata, full_tag, value)
                
                # Recursively extract nested elements if any
                if len(child) > 0:
                    self._extract_xmp_elements(child, namespaces, metadata)
    
    def _store_xmp_value(self, metadata: Dict[str, Any], key: str, value: Any) -> None:
        """Store raw XMP value and provide normalized aliases for common tags."""
        # Format value for specific tags to standard format's output
        formatted_value = value
        
        # VideoPixelAspectRatio: Standard format shows "1" instead of "1/1" for ratio values
        if key == 'XMP:VideoPixelAspectRatio' or key.endswith(':VideoPixelAspectRatio'):
            if isinstance(value, str) and '/' in value:
                try:
                    # Parse "1/1" format
                    parts = value.split('/')
                    if len(parts) == 2:
                        num, den = int(parts[0]), int(parts[1])
                        if den != 0:
                            ratio = num / den
                            # If ratio is 1.0, show as "1", otherwise show as decimal
                            if ratio == 1.0:
                                formatted_value = "1"
                            else:
                                formatted_value = f"{ratio:.3f}"
                except (ValueError, ZeroDivisionError):
                    pass
        
        # AudioSampleType: Standard format shows "16-bit integer" instead of "16Int"
        if key == 'XMP:AudioSampleType' or key.endswith(':AudioSampleType'):
            if isinstance(value, str):
                # Map common formats: "16Int" -> "16-bit integer", "24Int" -> "24-bit integer", etc.
                import re
                match = re.match(r'(\d+)Int', value)
                if match:
                    bits = match.group(1)
                    formatted_value = f"{bits}-bit integer"
                elif value.lower() in ['float', 'flt']:
                    formatted_value = "32-bit float"
                elif value.lower() in ['double', 'dbl']:
                    formatted_value = "64-bit float"
        
        # Orientation: Standard format shows "Horizontal (normal)" instead of "1"
        if key == 'XMP:Orientation' or key.endswith(':Orientation'):
            orientation_map = {
                1: 'Horizontal (normal)',
                2: 'Mirror horizontal',
                3: 'Rotate 180',
                4: 'Mirror vertical',
                5: 'Mirror horizontal and rotate 270 CW',
                6: 'Rotate 90 CW',
                7: 'Mirror horizontal and rotate 90 CW',
                8: 'Rotate 270 CW',
            }
            if isinstance(value, (int, str)):
                try:
                    int_value = int(value) if isinstance(value, str) else value
                    if int_value in orientation_map:
                        formatted_value = orientation_map[int_value]
                except (ValueError, TypeError):
                    pass
        
        # ColorMode: Standard format shows descriptions for color mode values
        if key == 'XMP:ColorMode' or key.endswith(':ColorMode'):
            color_mode_map = {
                0: 'Bitmap',
                1: 'Grayscale',
                2: 'Indexed Color',
                3: 'RGB Color',
                4: 'CMYK Color',
                7: 'Multichannel',
                8: 'Duotone',
                9: 'Lab Color',
            }
            if isinstance(value, (int, str)):
                try:
                    int_value = int(value) if isinstance(value, str) else value
                    if int_value in color_mode_map:
                        formatted_value = color_mode_map[int_value]
                except (ValueError, TypeError):
                    pass
        
        # VideoFieldOrder: Standard format shows descriptions for field order values
        if key == 'XMP:VideoFieldOrder' or key.endswith(':VideoFieldOrder'):
            field_order_map = {
                0: 'Progressive',
                1: 'Upper',
                2: 'Lower',
            }
            if isinstance(value, (int, str)):
                try:
                    int_value = int(value) if isinstance(value, str) else value
                    if int_value in field_order_map:
                        formatted_value = field_order_map[int_value]
                except (ValueError, TypeError):
                    pass
        
        # For Producer tag, always update (use last value found, matching standard behavior)
        # For other tags, update normally (later values override earlier ones)
        metadata[key] = formatted_value
        alias = self.XMP_ALIAS_MAP.get(key.upper())
        if alias:
            # Convert date values from ISO format to EXIF format
            date_formatted_value = self._format_xmp_date(formatted_value, alias)
            metadata[alias] = date_formatted_value if date_formatted_value is not None else self._simplify_xmp_value(formatted_value)
        
        # Create aliases for XMPMM tags to XMP: prefix (Standard format shows some XMPMM tags as XMP:)
        # XMPMM:InstanceID -> XMP:InstanceID
        if key == 'XMPMM:InstanceID' and 'XMP:InstanceID' not in metadata:
            metadata['XMP:InstanceID'] = formatted_value
        # XMPMM:OriginalDocumentID -> XMP:OriginalDocumentID
        elif key == 'XMPMM:OriginalDocumentID' and 'XMP:OriginalDocumentID' not in metadata:
            metadata['XMP:OriginalDocumentID'] = formatted_value
        # XMPMM:DocumentID -> XMP:DocumentID (if not already set)
        elif key == 'XMPMM:DocumentID' and 'XMP:DocumentID' not in metadata:
            metadata['XMP:DocumentID'] = formatted_value
        # XMPMM:History* -> XMP:History* (Standard format shows History tags with XMP: prefix)
        elif key.startswith('XMPMM:History') and not key.startswith('XMP:History'):
            xmp_key = key.replace('XMPMM:', 'XMP:', 1)
            if xmp_key not in metadata:
                metadata[xmp_key] = formatted_value
        
        # Create aliases for XMP-dc and XMP-tiff tags to XMP: prefix (Standard format shows these as XMP:)
        # XMP-dc:format -> XMP:Format
        if key == 'XMP-dc:format' and 'XMP:Format' not in metadata:
            metadata['XMP:Format'] = formatted_value
        # XMP-tiff:Orientation -> XMP:Orientation
        elif key == 'XMP-tiff:Orientation' and 'XMP:Orientation' not in metadata:
            metadata['XMP:Orientation'] = formatted_value
        
        # CRITICAL: Normalize ALL XMP-xmp: tags to XMP: tags (Standard format shows xmp namespace tags as XMP:)
        # This handles all tags in the xmp namespace, not just specific ones
        if key.startswith('XMP-xmp:'):
            normalized_key = key.replace('XMP-xmp:', 'XMP:', 1)
            if normalized_key not in metadata:
                metadata[normalized_key] = formatted_value
    
    def _format_timecode_format(self, timecode_format: str) -> str:
        """
        Format timecode format string to standard format's output.
        
        Args:
            timecode_format: Timecode format string (e.g., "2997NonDropTimecode")
            
        Returns:
            Formatted string (e.g., "29.97 fps (non-drop)")
        """
        if not timecode_format:
            return timecode_format
        
        # Common timecode format mappings
        # "2997NonDropTimecode" -> "29.97 fps (non-drop)"
        # "2997DropTimecode" -> "29.97 fps (drop)"
        # "30NonDropTimecode" -> "30 fps (non-drop)"
        # "25NonDropTimecode" -> "25 fps (non-drop)"
        # "24NonDropTimecode" -> "24 fps (non-drop)"
        
        timecode_format_lower = timecode_format.lower()
        
        # Extract frame rate
        frame_rate = None
        if '2997' in timecode_format_lower or '29970' in timecode_format_lower:
            frame_rate = "29.97"
        elif '30' in timecode_format_lower and '30000' not in timecode_format_lower:
            frame_rate = "30"
        elif '25' in timecode_format_lower:
            frame_rate = "25"
        elif '24' in timecode_format_lower:
            frame_rate = "24"
        
        # Determine drop/non-drop
        is_drop = 'drop' in timecode_format_lower and 'nondrop' not in timecode_format_lower
        
        if frame_rate:
            drop_str = "drop" if is_drop else "non-drop"
            return f"{frame_rate} fps ({drop_str})"
        
        # Fallback: return as-is if we can't parse it
        return timecode_format
        
        # Create aliases for XMPMM tags to XMP: prefix (Standard format shows some XMPMM tags as XMP:)
        # XMPMM:InstanceID -> XMP:InstanceID
        if key == 'XMPMM:InstanceID' and 'XMP:InstanceID' not in metadata:
            metadata['XMP:InstanceID'] = formatted_value
        # XMPMM:OriginalDocumentID -> XMP:OriginalDocumentID
        elif key == 'XMPMM:OriginalDocumentID' and 'XMP:OriginalDocumentID' not in metadata:
            metadata['XMP:OriginalDocumentID'] = formatted_value
        # XMPMM:DocumentID -> XMP:DocumentID (if not already set)
        elif key == 'XMPMM:DocumentID' and 'XMP:DocumentID' not in metadata:
            metadata['XMP:DocumentID'] = formatted_value
        
        # Create aliases for XMP-dc and XMP-tiff tags to XMP: prefix (Standard format shows these as XMP:)
        # XMP-dc:format -> XMP:Format
        if key == 'XMP-dc:format' and 'XMP:Format' not in metadata:
            metadata['XMP:Format'] = formatted_value
        # XMP-tiff:Orientation -> XMP:Orientation
        elif key == 'XMP-tiff:Orientation' and 'XMP:Orientation' not in metadata:
            metadata['XMP:Orientation'] = formatted_value
        # XMP-xmp:MetadataDate -> XMP:MetadataDate (Standard format shows xmp namespace tags as XMP:)
        elif key == 'XMP-xmp:MetadataDate' and 'XMP:MetadataDate' not in metadata:
            metadata['XMP:MetadataDate'] = formatted_value
        # XMP-xmp:CreateDate -> XMP:CreateDate
        elif key == 'XMP-xmp:CreateDate' and 'XMP:CreateDate' not in metadata:
            metadata['XMP:CreateDate'] = formatted_value
        # XMP-xmp:ModifyDate -> XMP:ModifyDate
        elif key == 'XMP-xmp:ModifyDate' and 'XMP:ModifyDate' not in metadata:
            metadata['XMP:ModifyDate'] = formatted_value
        
        # Normalize xmpDM tag names to standard format's capitalization
        # Standard format capitalizes xmpDM tags: audioSampleType -> AudioSampleType, startTimeScale -> StartTimeScale, etc.
        if key.startswith('XMP:') and len(key) > 4:
            tag_name = key[4:]  # Get tag name after "XMP:"
            # Check if it's a lowercase xmpDM tag that should be capitalized
            xmpdm_tags_lowercase = [
                'audiosampletype', 'audiosamplerate', 'audiochannels', 'audiochannellayout', 'audiochanneltype',
                'videoframesizeh', 'videoframesizew', 'videoframesizeunit', 'videopixelaspectratio', 'videofieldorder', 'videoframerate',
                'starttimescale', 'starttimesamplesize', 'starttimecodetimeformat', 'starttimecodetimevalue',
                'alttimecodetimevalue', 'alttimecodetimeformat', 'durationvalue', 'durationscale',
                'historyaction', 'historywhen', 'historysoftwareagent', 'historyinstanceid', 'historychanged',
                'format', 'orientation', 'duration'
            ]
            # Also check for xmpMM History tags (stEvt namespace)
            xmpmm_history_tags = [
                'action', 'when', 'softwareagent', 'instanceid', 'changed'
            ]
            # Check if this is a History-related tag (stEvt namespace)
            is_history_tag = tag_name.lower() in xmpmm_history_tags or 'history' in key.lower()
            
            if tag_name.lower() in xmpdm_tags_lowercase or is_history_tag:
                # Capitalize first letter to standard format's camelCase format
                # Standard format uses camelCase: videoFieldOrder -> VideoFieldOrder, startTimecodeTimeValue -> StartTimecodeTimeValue
                # XML tags are typically already in camelCase (e.g., "startTimecodeTimeValue"), so we just capitalize first letter
                # For History tags, add "History" prefix if not already present
                if is_history_tag and not tag_name.lower().startswith('history'):
                    capitalized = 'History' + tag_name[0].upper() + tag_name[1:] if len(tag_name) > 1 else 'History' + tag_name.upper()
                else:
                    # Just capitalize first letter (tag is already in camelCase from XML)
                    capitalized = tag_name[0].upper() + tag_name[1:] if len(tag_name) > 1 else tag_name.upper()
                
                # For History tags, use XMPMM namespace
                if is_history_tag:
                    normalized_key = f"XMPMM:{capitalized}"
                else:
                    normalized_key = f"XMP:{capitalized}"
                
                # Always create normalized key (capitalized version) to standard format
                # This ensures tags like "audioChannelType" are also available as "AudioChannelType"
                if normalized_key != key:
                    # Apply same formatting to normalized key
                    if normalized_key == 'XMP:VideoPixelAspectRatio' and isinstance(formatted_value, str) and '/' in formatted_value:
                        # Already formatted above - but need to re-format for normalized key
                        try:
                            parts = formatted_value.split('/')
                            if len(parts) == 2:
                                num, den = int(parts[0]), int(parts[1])
                                if den != 0:
                                    ratio = num / den
                                    if ratio == 1.0:
                                        metadata[normalized_key] = "1"
                                    else:
                                        metadata[normalized_key] = f"{ratio:.3f}"
                                else:
                                    metadata[normalized_key] = formatted_value
                            else:
                                metadata[normalized_key] = formatted_value
                        except (ValueError, ZeroDivisionError):
                            metadata[normalized_key] = formatted_value
                    elif normalized_key == 'XMP:AudioSampleType' and isinstance(formatted_value, str) and 'Int' in formatted_value:
                        # Already formatted above - but need to re-format for normalized key
                        import re
                        match = re.match(r'(\d+)Int', formatted_value)
                        if match:
                            bits = match.group(1)
                            metadata[normalized_key] = f"{bits}-bit integer"
                        else:
                            metadata[normalized_key] = formatted_value
                    else:
                        metadata[normalized_key] = formatted_value
                # Also ensure the normalized key is set even if it matches the original (for consistency)
                elif normalized_key == key and normalized_key not in metadata:
                    metadata[normalized_key] = formatted_value

    @staticmethod
    def _simplify_xmp_value(value: Any) -> Any:
        """Reduce complex XMP values (arrays/dicts) to a comparable scalar where possible."""
        if isinstance(value, (list, tuple)):
            return value[0] if value else ''
        return value
    
    @staticmethod
    def _format_xmp_date(value: Any, tag_name: str) -> Optional[str]:
        """
        Convert XMP date from ISO format to EXIF format.
        
        Converts ISO 8601 dates (e.g., "2005-10-25T20:57:06+01:00") 
        to EXIF format (e.g., "2005:10:25 20:57:06+01:00").
        
        Args:
            value: Date value (string or other)
            tag_name: Tag name (e.g., "XMP:ModifyDate")
            
        Returns:
            Formatted date string or None if not a date tag or conversion fails
        """
        # Only process date-related tags
        if not isinstance(value, str) or 'Date' not in tag_name:
            return None
        
        # Check if it's ISO format (has T separator or dashes in date part)
        if 'T' in value or (value.count('-') >= 2 and len(value) > 10):
            try:
                from datetime import datetime
                # Parse ISO format (handles various ISO 8601 formats)
                # Replace Z with +00:00 for UTC
                iso_value = value.replace('Z', '+00:00')
                # Try parsing with timezone
                try:
                    dt = datetime.fromisoformat(iso_value)
                except ValueError:
                    # Try without timezone (remove timezone part)
                    if '+' in iso_value or '-' in iso_value[10:]:  # Timezone after position 10
                        # Remove timezone part
                        tz_pos = iso_value.find('+', 10)
                        if tz_pos == -1:
                            tz_pos = iso_value.find('-', 10)
                        if tz_pos > 0:
                            iso_value = iso_value[:tz_pos]
                    dt = datetime.fromisoformat(iso_value)
                
                # Format as EXIF format: YYYY:MM:DD HH:MM:SS+HH:MM
                date_str = dt.strftime('%Y:%m:%d %H:%M:%S')
                # Add timezone if present
                if dt.tzinfo:
                    offset = dt.utcoffset()
                    if offset:
                        hours = int(offset.total_seconds() // 3600)
                        minutes = int((offset.total_seconds() % 3600) // 60)
                        if hours >= 0:
                            date_str += f"+{hours:02d}:{minutes:02d}"
                        else:
                            date_str += f"{hours:03d}:{minutes:02d}"
                return date_str
            except (ValueError, AttributeError):
                pass
        
        return None
