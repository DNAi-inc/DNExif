# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Document format metadata parser

This module provides metadata parsing for document formats like PDF
which can contain XMP and other metadata.

Copyright 2025 DNAi inc.
"""

import re
from typing import Dict, Any, Optional
from pathlib import Path
from dnexif.exceptions import MetadataReadError
from dnexif.xmp_parser import XMPParser


class DocumentParser:
    """
    Document format metadata parser.
    
    Supports PDF format which can contain XMP metadata.
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize document parser.
        
        Args:
            file_path: Path to document file
            file_data: Raw file data
        """
        self.file_path = file_path
        self.file_data = file_data
        self.metadata: Dict[str, Any] = {}
    
    def parse(self) -> Dict[str, Any]:
        """
        Parse document file metadata.
        
        Returns:
            Dictionary containing all extracted metadata
        """
        if not self.file_data and self.file_path:
            with open(self.file_path, 'rb') as f:
                self.file_data = f.read()
        
        if not self.file_data:
            return {}
        
        metadata = {}
        
        # Detect format
        format_type = self._detect_format()
        if not format_type:
            return metadata
        
        # Parse based on format
        if format_type == 'PDF':
            metadata.update(self._parse_pdf())
        
        return metadata
    
    def _detect_format(self) -> Optional[str]:
        """Detect document format."""
        if not self.file_data:
            return None
        
        # PDF starts with '%PDF'
        if self.file_data.startswith(b'%PDF'):
            return 'PDF'
        
        # Check extension
        if self.file_path:
            ext = Path(self.file_path).suffix.lower()
            if ext == '.pdf':
                return 'PDF'
        
        return None
    
    def _parse_pdf(self) -> Dict[str, Any]:
        """Parse PDF metadata."""
        metadata = {}
        
        try:
            if not self.file_data:
                return metadata
            
            # Extract PDF version from header (e.g., %PDF-1.6 or %PDF-2.0)
            pdf_version_match = re.search(rb'%PDF-(\d+\.\d+)', self.file_data)
            if pdf_version_match:
                pdf_version = pdf_version_match.group(1).decode('ascii', errors='ignore')
                metadata['PDF:PDFVersion'] = pdf_version
                
                # Detect PDF 2.0
                try:
                    version_parts = pdf_version.split('.')
                    major_version = int(version_parts[0])
                    if major_version >= 2:
                        metadata['PDF:PDF2.0'] = True
                        metadata['PDF:PDFStandard'] = 'PDF 2.0'
                except (ValueError, IndexError):
                    pass
            
            # Check for Linearized PDF (has /Linearized in the file)
            if b'/Linearized' in self.file_data:
                metadata['PDF:Linearized'] = 'Yes'
            else:
                metadata['PDF:Linearized'] = 'No'
            
            # PDF metadata can be in:
            # 1. Document Info Dictionary (trailer)
            # 2. XMP packet (in stream object)
            
            # Look for XMP packet (can appear multiple times, use the most complete one)
            # XMP packets can be in different formats:
            # 1. <x:xmpmeta>...</x:xmpmeta>
            # 2. <rdf:RDF>...</rdf:RDF> (standalone RDF)
            # 3. Embedded in PDF stream objects
            xmp_patterns = [
                rb'<x:xmpmeta[^>]*>.*?</x:xmpmeta>',
                rb'<rdf:RDF[^>]*xmlns:xmp=.*?</rdf:RDF>',
                rb'<xmp:Metadata[^>]*>.*?</xmp:Metadata>',
            ]
            
            xmp_data = None
            for pattern in xmp_patterns:
                xmp_match = re.search(pattern, self.file_data, re.DOTALL)
                if xmp_match:
                    candidate = xmp_match.group(0)
                    # Prefer longer/more complete XMP packets
                    if xmp_data is None or len(candidate) > len(xmp_data):
                        xmp_data = candidate
            
            if xmp_data:
                metadata['Document:HasXMP'] = True
                # Try to parse XMP
                try:
                    # XMPParser expects file_path, but we can try to parse the packet
                    # This is a simplified approach
                    if b'xmlns:dc=' in xmp_data:
                        metadata['Document:XMP:HasDublinCore'] = True
                    if b'xmlns:exif=' in xmp_data:
                        metadata['Document:XMP:HasEXIF'] = True
                except Exception:
                    pass
            
            # Look for PDF Document Info Dictionary
            # Format: /Title (text) or /Title <hex>
            info_pattern = rb'/Title\s*\(([^)]+)\)|/Title\s*<([^>]+)>'
            title_match = re.search(info_pattern, self.file_data)
            if title_match:
                # Extract actual title value
                title_value = title_match.group(1) or title_match.group(2)
                if title_value:
                    try:
                        # Try to decode hex if it's hex
                        if title_match.group(2):
                            # Hex string - decode
                            hex_str = title_value.decode('ascii', errors='ignore')
                            if all(c in '0123456789ABCDEFabcdef' for c in hex_str):
                                title = bytes.fromhex(hex_str).decode('utf-8', errors='ignore')
                            else:
                                title = hex_str
                        else:
                            # Text string
                            title = title_value.decode('utf-8', errors='ignore')
                        metadata['PDF:Title'] = title.strip()
                        metadata['Document:PDF:Title'] = title.strip()  # Keep for backward compatibility
                    except Exception:
                        metadata['PDF:Title'] = True
                        metadata['Document:PDF:Title'] = True
            
            author_pattern = rb'/Author\s*\(([^)]+)\)|/Author\s*<([^>]+)>'
            author_match = re.search(author_pattern, self.file_data)
            if author_match:
                author_value = author_match.group(1) or author_match.group(2)
                if author_value:
                    try:
                        if author_match.group(2):
                            hex_str = author_value.decode('ascii', errors='ignore')
                            if all(c in '0123456789ABCDEFabcdef' for c in hex_str):
                                author = bytes.fromhex(hex_str).decode('utf-8', errors='ignore')
                            else:
                                author = hex_str
                        else:
                            author = author_value.decode('utf-8', errors='ignore')
                        metadata['PDF:Author'] = author.strip()
                        metadata['Document:PDF:Author'] = author.strip()  # Keep for backward compatibility
                    except Exception:
                        metadata['PDF:Author'] = True
                        metadata['Document:PDF:Author'] = True
            
            creator_pattern = rb'/Creator\s*\(([^)]+)\)|/Creator\s*<([^>]+)>'
            creator_match = re.search(creator_pattern, self.file_data)
            if creator_match:
                creator_value = creator_match.group(1) or creator_match.group(2)
                if creator_value:
                    try:
                        if creator_match.group(2):
                            hex_str = creator_value.decode('ascii', errors='ignore')
                            if all(c in '0123456789ABCDEFabcdef' for c in hex_str):
                                creator = bytes.fromhex(hex_str).decode('utf-8', errors='ignore')
                            else:
                                creator = hex_str
                        else:
                            creator = creator_value.decode('utf-8', errors='ignore')
                        # standard format prioritizes XMP:CreatorTool over PDF Creator
                        # Only use PDF Creator if XMP:CreatorTool or XMP-xmp:CreatorTool is not available
                        xmp_meta = metadata.get('_XMP_Metadata', {})
                        if not xmp_meta or ('XMP:CreatorTool' not in xmp_meta and 'XMP-xmp:CreatorTool' not in xmp_meta):
                            metadata['PDF:Creator'] = creator.strip()
                        metadata['Document:PDF:Creator'] = creator.strip()  # Keep for backward compatibility
                    except Exception:
                        if '_XMP_Metadata' not in metadata or 'XMP:CreatorTool' not in metadata.get('_XMP_Metadata', {}):
                            metadata['PDF:Creator'] = True
                        metadata['Document:PDF:Creator'] = True
            
            # Standard format uses the LAST Producer value found in the PDF document info
            producer_pattern = rb'/Producer\s*\(([^)]+)\)|/Producer\s*<([^>]+)>'
            producer_matches = list(re.finditer(producer_pattern, self.file_data))
            if producer_matches:
                # Use the last match (standard behavior)
                producer_match = producer_matches[-1]
                producer_value = producer_match.group(1) or producer_match.group(2)
                if producer_value:
                    try:
                        if producer_match.group(2):
                            hex_str = producer_value.decode('ascii', errors='ignore')
                            if all(c in '0123456789ABCDEFabcdef' for c in hex_str):
                                producer = bytes.fromhex(hex_str).decode('utf-8', errors='ignore')
                            else:
                                producer = hex_str
                        else:
                            producer = producer_value.decode('utf-8', errors='ignore')
                        pdf_producer = producer.strip()
                        metadata['PDF:Producer'] = pdf_producer
                        metadata['Document:PDF:Producer'] = pdf_producer  # Keep for backward compatibility
                        # Standard format uses PDF document info Producer for XMP:Producer when available
                        # Store it so we can use it to override XMP:Producer if needed
                        metadata['_PDF_Producer'] = pdf_producer
                    except Exception:
                        metadata['PDF:Producer'] = True
                        metadata['Document:PDF:Producer'] = True
            
            # Parse XMP stream for richer metadata (e.g., XMP:Title, XMP:CreateDate, etc.)
            # IMPORTANT: Store XMP metadata in _XMP_Metadata for later merging AFTER Document Info parsing
            # This allows XMP values to override Document Info values (matching standard behavior)
            try:
                xmp_parser = XMPParser(file_data=self.file_data)
                xmp_metadata = xmp_parser.read(scan_entire_file=True)  # Scan entire file for XMP
                if xmp_metadata:
                    metadata['Document:HasXMP'] = True
                    # Store XMP metadata for later merging (after Document Info parsing)
                    metadata['_XMP_Metadata'] = xmp_metadata
            except Exception:
                pass
            
            # Extract PDF-specific tags from Document Info Dictionary
            # ModifyDate (ModDate)
            # standard format prioritizes XMP:ModifyDate over PDF ModDate
            moddate_pattern = rb'/ModDate\s*\(([^)]+)\)|/ModDate\s*<([^>]+)>'
            moddate_match = re.search(moddate_pattern, self.file_data)
            if moddate_match:
                moddate_value = moddate_match.group(1) or moddate_match.group(2)
                if moddate_value:
                    try:
                        if moddate_match.group(2):
                            hex_str = moddate_value.decode('ascii', errors='ignore')
                            if all(c in '0123456789ABCDEFabcdef' for c in hex_str):
                                moddate = bytes.fromhex(hex_str).decode('utf-8', errors='ignore')
                            else:
                                moddate = hex_str
                        else:
                            moddate = moddate_value.decode('utf-8', errors='ignore')
                        moddate_str = moddate.strip()
                        # Format PDF date to standard format (D:YYYYMMDDHHmmssOH'H'mm' -> YYYY:MM:DD HH:mm:ss+HH:mm)
                        formatted_moddate = self._format_pdf_date(moddate_str)
                        # Only use PDF ModDate if XMP:ModifyDate or XMP-xmp:ModifyDate is not available
                        xmp_meta = metadata.get('_XMP_Metadata', {})
                        if not xmp_meta or ('XMP:ModifyDate' not in xmp_meta and 'XMP-xmp:ModifyDate' not in xmp_meta):
                            metadata['PDF:ModifyDate'] = formatted_moddate
                        metadata['Document:PDF:ModifyDate'] = moddate_str  # Keep original for backward compatibility
                    except Exception:
                        pass
            
            # CreateDate (CreationDate)
            # standard format prioritizes XMP:CreateDate over PDF CreationDate
            creationdate_pattern = rb'/CreationDate\s*\(([^)]+)\)|/CreationDate\s*<([^>]+)>'
            creationdate_match = re.search(creationdate_pattern, self.file_data)
            if creationdate_match:
                creationdate_value = creationdate_match.group(1) or creationdate_match.group(2)
                if creationdate_value:
                    try:
                        if creationdate_match.group(2):
                            hex_str = creationdate_value.decode('ascii', errors='ignore')
                            if all(c in '0123456789ABCDEFabcdef' for c in hex_str):
                                creationdate = bytes.fromhex(hex_str).decode('utf-8', errors='ignore')
                            else:
                                creationdate = hex_str
                        else:
                            creationdate = creationdate_value.decode('utf-8', errors='ignore')
                        creationdate_str = creationdate.strip()
                        # Format PDF date to standard format
                        formatted_creationdate = self._format_pdf_date(creationdate_str)
                        # Only use PDF CreationDate if XMP:CreateDate or XMP-xmp:CreateDate is not available
                        xmp_meta = metadata.get('_XMP_Metadata', {})
                        if not xmp_meta or ('XMP:CreateDate' not in xmp_meta and 'XMP-xmp:CreateDate' not in xmp_meta):
                            metadata['PDF:CreateDate'] = formatted_creationdate
                    except Exception:
                        pass
            
            # PageCount (from root /Pages object /Count)
            # Standard format uses the root Pages object's /Count value
            # Find root Pages object by following /Root -> /Pages reference
            root_pages_count = None
            
            # First, find /Root reference in trailer
            root_ref_pattern = rb'/Root\s+(\d+)\s+\d+\s+R'
            root_ref_match = re.search(root_ref_pattern, self.file_data)
            if root_ref_match:
                root_obj_num = int(root_ref_match.group(1))
                # Find root object and look for /Pages reference
                root_obj_pattern = f"{root_obj_num} 0 obj".encode('ascii')
                root_obj_match = re.search(root_obj_pattern, self.file_data)
                if root_obj_match:
                    root_obj_start = root_obj_match.start()
                    # Find /Pages reference in root object
                    pages_ref_pattern = rb'/Pages\s+(\d+)\s+\d+\s+R'
                    pages_ref_match = re.search(pages_ref_pattern, self.file_data[root_obj_start:root_obj_start+500])
                    if pages_ref_match:
                        pages_obj_num = int(pages_ref_match.group(1))
                        # Find Pages object and extract /Count
                        pages_obj_pattern = f"{pages_obj_num} 0 obj".encode('ascii')
                        pages_obj_match = re.search(pages_obj_pattern, self.file_data)
                        if pages_obj_match:
                            pages_obj_start = pages_obj_match.start()
                            # Look for /Count in Pages object (within next 200 bytes)
                            count_pattern = rb'/Count\s+(\d+)'
                            count_match = re.search(count_pattern, self.file_data[pages_obj_start:pages_obj_start+200])
                            if count_match:
                                root_pages_count = int(count_match.group(1))
            
            # Fallback: if root Pages /Count not found, use the largest /Count value
            # (root Pages object usually has the largest count)
            if root_pages_count is None:
                pagecount_pattern = rb'/Count\s+(\d+)'
                pagecount_matches = list(re.finditer(pagecount_pattern, self.file_data))
                if pagecount_matches:
                    # Use the largest /Count value (root page count is usually the largest)
                    max_count = 0
                    for match in pagecount_matches:
                        try:
                            count = int(match.group(1))
                            if count > max_count:
                                max_count = count
                        except (ValueError, TypeError):
                            continue
                    if max_count > 0:
                        root_pages_count = max_count
            
            if root_pages_count is not None and root_pages_count > 0:
                metadata['PDF:PageCount'] = root_pages_count
                metadata['Document:PDF:PageCount'] = root_pages_count  # Keep for backward compatibility
            
            # Extract Pages MediaBox (page boundaries)
            # MediaBox format: /MediaBox [llx lly urx ury]
            # MediaBox can be in:
            # 1. Page objects directly
            # 2. Page tree nodes (inherited by pages)
            # 3. Root Pages object (inherited by all pages)
            mediabox_pattern = rb'/MediaBox\s*\[\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\]'
            mediabox_matches = list(re.finditer(mediabox_pattern, self.file_data))
            
            if mediabox_matches:
                # Extract all MediaBox values found
                mediaboxes = []
                for match in mediabox_matches:
                    try:
                        llx = float(match.group(1).decode('ascii', errors='ignore'))
                        lly = float(match.group(2).decode('ascii', errors='ignore'))
                        urx = float(match.group(3).decode('ascii', errors='ignore'))
                        ury = float(match.group(4).decode('ascii', errors='ignore'))
                        # Format as "llx lly urx ury" (matching standard format)
                        mediabox_str = f"{llx:.2f} {lly:.2f} {urx:.2f} {ury:.2f}"
                        mediaboxes.append(mediabox_str)
                    except (ValueError, TypeError, AttributeError):
                        continue
                
                if mediaboxes:
                    # Use the first MediaBox found (typically from root Pages object or first page)
                    # standard format typically shows the MediaBox from the first page or root Pages object
                    metadata['PDF:PagesMediaBox'] = mediaboxes[0]
                    # Also store all MediaBoxes if multiple pages have different MediaBoxes
                    if len(mediaboxes) > 1:
                        # Check if all MediaBoxes are the same
                        if len(set(mediaboxes)) == 1:
                            # All pages have the same MediaBox
                            metadata['PDF:PagesMediaBox'] = mediaboxes[0]
                        else:
                            # Different MediaBoxes for different pages
                            # Store first one as primary, and indicate multiple values
                            metadata['PDF:PagesMediaBox'] = mediaboxes[0]
                            metadata['PDF:PagesMediaBox:Count'] = len(mediaboxes)
                            # Store all MediaBoxes as a list
                            metadata['PDF:PagesMediaBox:All'] = mediaboxes
            
            # Now merge XMP metadata (after Document Info parsing)
            # standard format prioritizes XMP values for most fields, but PDF Producer over XMP Producer
            if '_XMP_Metadata' in metadata:
                xmp_data = metadata.pop('_XMP_Metadata')
                # Merge XMP metadata, but preserve PDF Producer if it exists
                pdf_producer = metadata.get('PDF:Producer')
                metadata.update(xmp_data)
                
                # Add aliases for XMP tags with different namespaces to standard format naming
                # XMP:Format (from XMP-dc:format)
                if 'XMP-dc:format' in metadata and 'XMP:Format' not in metadata:
                    metadata['XMP:Format'] = metadata['XMP-dc:format']
                
                # XMP:CreatorTool (from XMP-xmp:CreatorTool)
                if 'XMP-xmp:CreatorTool' in metadata and 'XMP:CreatorTool' not in metadata:
                    metadata['XMP:CreatorTool'] = metadata['XMP-xmp:CreatorTool']
                
                # XMP:DocumentID (from XMPMM:DocumentID)
                if 'XMPMM:DocumentID' in metadata and 'XMP:DocumentID' not in metadata:
                    metadata['XMP:DocumentID'] = metadata['XMPMM:DocumentID']
                
                # XMP:InstanceID (from XMPMM:InstanceID)
                if 'XMPMM:InstanceID' in metadata and 'XMP:InstanceID' not in metadata:
                    metadata['XMP:InstanceID'] = metadata['XMPMM:InstanceID']
                
                # XMP:XMPToolkit (from XMP-xmp:XMPToolkit or other namespace)
                # Note: XMPToolkit might not be in XMP-xmp namespace, check if it exists elsewhere
                if 'XMP:XMPToolkit' not in metadata:
                    # Try to find XMPToolkit in any namespace
                    for key in metadata.keys():
                        if 'XMPToolkit' in key and key != 'XMP:XMPToolkit':
                            metadata['XMP:XMPToolkit'] = metadata[key]
                            break
                
                # standard format prioritizes PDF document info Producer over XMP Producer
                if pdf_producer:
                    if 'XMP:Producer' in metadata:
                        # Check if they differ significantly (Standard format uses PDF Producer)
                        if pdf_producer != metadata.get('XMP:Producer', ''):
                            metadata['XMP:Producer'] = pdf_producer
                    else:
                        # If XMP Producer doesn't exist, use PDF Producer
                        metadata['XMP:Producer'] = pdf_producer
                
                # Standard format uses XMP:CreateDate for PDF:CreateDate if available
                # Check both XMP:CreateDate and XMP-xmp:CreateDate (XMP parser may use different namespaces)
                xmp_createdate = metadata.get('XMP:CreateDate') or metadata.get('XMP-xmp:CreateDate')
                if xmp_createdate:
                    # Convert ISO 8601 format (2005-10-25T20:05:39+01:00) to standard format (2005:10:25 20:05:39+01:00)
                    formatted_createdate = xmp_createdate.replace('T', ' ').replace('-', ':')
                    metadata['PDF:CreateDate'] = formatted_createdate
                
                # Standard format uses XMP:CreatorTool for PDF:Creator if available
                # Check both XMP:CreatorTool and XMP-xmp:CreatorTool
                xmp_creatortool = metadata.get('XMP:CreatorTool') or metadata.get('XMP-xmp:CreatorTool')
                if xmp_creatortool:
                    metadata['PDF:Creator'] = xmp_creatortool.strip()
                
                # Standard format uses XMP:ModifyDate for PDF:ModifyDate if available
                # Check both XMP:ModifyDate and XMP-xmp:ModifyDate
                xmp_modifydate = metadata.get('XMP:ModifyDate') or metadata.get('XMP-xmp:ModifyDate')
                if xmp_modifydate:
                    # Convert ISO 8601 format (2005-10-25T20:57:06+01:00) to standard format (2005:10:25 20:57:06+01:00)
                    formatted_modifydate = xmp_modifydate.replace('T', ' ').replace('-', ':')
                    metadata['PDF:ModifyDate'] = formatted_modifydate
        
        except Exception:
            pass
        
        return metadata
    
    def _format_pdf_date(self, pdf_date_str: str) -> str:
        """
        Format PDF date string to standard format.
        
        PDF dates are in format: D:YYYYMMDDHHmmssOH'H'mm'
        standard format: YYYY:MM:DD HH:mm:ss+HH:mm
        
        Args:
            pdf_date_str: PDF date string (e.g., "D:20051013100048+02'00'")
            
        Returns:
            Formatted date string (e.g., "2005:10:13 10:00:48+02:00")
        """
        try:
            # Remove 'D:' prefix if present
            if pdf_date_str.startswith('D:'):
                pdf_date_str = pdf_date_str[2:]
            
            # Parse PDF date format: YYYYMMDDHHmmssOH'H'mm'
            # O is + or -, H'H'mm' is timezone offset
            if len(pdf_date_str) >= 14:
                year = pdf_date_str[0:4]
                month = pdf_date_str[4:6]
                day = pdf_date_str[6:8]
                hour = pdf_date_str[8:10]
                minute = pdf_date_str[10:12]
                second = pdf_date_str[12:14]
                
                # Parse timezone if present
                tz_offset = ''
                if len(pdf_date_str) > 14:
                    tz_part = pdf_date_str[14:]
                    # Remove quotes and parse timezone
                    tz_part = tz_part.replace("'", "")
                    if tz_part.startswith('+') or tz_part.startswith('-'):
                        tz_sign = tz_part[0]
                        if len(tz_part) >= 5:
                            tz_hour = tz_part[1:3]
                            tz_min = tz_part[3:5]
                            tz_offset = f"{tz_sign}{tz_hour}:{tz_min}"
                        elif len(tz_part) >= 3:
                            tz_hour = tz_part[1:3]
                            tz_offset = f"{tz_sign}{tz_hour}:00"
                
                # Format as standard format: YYYY:MM:DD HH:mm:ss+HH:mm
                formatted = f"{year}:{month}:{day} {hour}:{minute}:{second}{tz_offset}"
                return formatted
            else:
                # Fallback: return as-is if format is unexpected
                return pdf_date_str
        except Exception:
            # Fallback: return as-is if parsing fails
            return pdf_date_str

