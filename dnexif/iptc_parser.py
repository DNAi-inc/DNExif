# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
IPTC metadata parser

This module handles reading and writing IPTC (International Press Telecommunications Council)
metadata from image files. IPTC metadata is commonly embedded in JPEG files.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List

from dnexif.exceptions import MetadataReadError, MetadataWriteError


# IPTC DataSet tags (complete IPTC-IIM standard)
IPTC_TAG_NAMES = {
    # Record 1: Envelope Record
    0: "RecordVersion",
    5: "Destination",
    20: "FileFormat",
    22: "FileVersion",
    30: "ServiceIdentifier",
    40: "EnvelopeNumber",
    50: "ProductID",
    60: "EnvelopePriority",
    70: "DateSent",
    80: "TimeSent",
    90: "CodedCharacterSet",
    100: "UniqueObjectName",
    120: "ARMIdentifier",
    122: "ARMVersion",
    
    # Record 2: Application Record (commonly used)
    0: "RecordVersion",  # Duplicate but needed
    5: "ObjectName",
    7: "EditStatus",
    8: "EditorialUpdate",
    10: "Urgency",
    12: "SubjectReference",
    15: "Category",
    20: "SupplementalCategories",
    22: "FixtureIdentifier",
    25: "Keywords",
    26: "ContentLocationCode",
    27: "ContentLocationName",
    30: "ReleaseDate",
    35: "ReleaseTime",
    37: "ExpirationDate",
    38: "ExpirationTime",
    40: "SpecialInstructions",
    42: "ActionAdvised",
    50: "ReferenceService",
    55: "ReferenceDate",
    60: "ReferenceNumber",
    62: "DateCreated",
    63: "TimeCreated",
    65: "DigitalCreationDate",
    66: "DigitalCreationTime",
    70: "OriginatingProgram",
    75: "ProgramVersion",
    80: "ObjectCycle",
    85: "Byline",
    90: "BylineTitle",
    92: "City",
    95: "Sublocation",
    100: "ProvinceState",
    101: "CountryCode",
    102: "CountryName",
    103: "OriginalTransmissionReference",
    105: "Headline",
    110: "Credit",
    115: "Source",
    116: "CopyrightNotice",
    118: "Contact",
    120: "Caption",
    121: "LocalCaption",
    122: "WriterEditor",
    125: "RasterizedCaption",
    130: "ImageType",
    131: "ImageOrientation",
    135: "LanguageIdentifier",
    150: "AudioType",
    151: "AudioSamplingRate",
    152: "AudioSamplingResolution",
    153: "AudioDuration",
    154: "AudioOutcue",
    200: "ObjectDataPreviewFileFormat",
    201: "ObjectDataPreviewFileFormatVersion",
    202: "ObjectDataPreviewData",
    221: "PrefixedObjectData",
    225: "ObjectData",
    237: "ObjectDataReference",
    
    # IPTC Extension tags (Record 7)
    700: "AboutCvTerm",
    701: "AboutCvTermCvId",
    702: "AboutCvTermId",
    703: "AboutCvTermName",
    704: "AboutCvTermRefinedAbout",
    710: "Contributor",
    715: "Coverage",
    720: "Creator",
    725: "CreatorWorkEmail",
    730: "CreatorWorkTelephone",
    735: "CreatorWorkURL",
    740: "CreditLine",
    745: "CopyrightOwnerID",
    750: "CopyrightOwnerName",
    755: "CopyrightOwnerImageID",
    760: "ImageSupplier",
    765: "ImageSupplierImageID",
    770: "ImageCreator",
    775: "ImageCreatorImageID",
    800: "Licensor",
    805: "LicensorCity",
    810: "LicensorCountry",
    815: "LicensorEmail",
    820: "LicensorExtendedAddress",
    825: "LicensorID",
    830: "LicensorName",
    835: "LicensorPostalCode",
    840: "LicensorRegion",
    845: "LicensorStreetAddress",
    850: "LicensorTelephone1",
    855: "LicensorTelephone2",
    860: "LicensorURL",
    900: "LocationCreated",
    905: "City",
    910: "Sublocation",
    915: "ProvinceState",
    920: "CountryCode",
    925: "CountryName",
    950: "WorldRegion",
    1000: "IntellectualGenre",
    1010: "Event",
    1030: "OrganisationInImageName",
    1100: "PersonInImage",
    1160: "PersonInImageWDetails",
    1200: "ProductInImage",
    1210: "CVterm",
    1220: "CVtermCvId",
    1230: "CVtermId",
    1240: "CVtermName",
    1250: "CVtermRefinedAbout",
}


class IPTCParser:
    """
    Parser for IPTC metadata from image files.
    
    IPTC metadata is typically embedded in JPEG APP13 segments or
    as XMP-IPTC data in XMP packets.
    """
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize the IPTC parser.
        
        Args:
            file_path: Path to the image file
            file_data: Raw file data (alternative to file_path)
        """
        self.file_path = file_path
        self.file_data = file_data
        self.metadata: Dict[str, Any] = {}
    
    def read(self) -> Dict[str, Any]:
        """
        Read IPTC metadata from the file.
        
        Returns:
            Dictionary containing all IPTC metadata
            
        Raises:
            MetadataReadError: If the file cannot be read or parsed
        """
        if self.file_path:
            with open(self.file_path, 'rb') as f:
                self.file_data = f.read()
        elif not self.file_data:
            raise MetadataReadError("No file path or file data provided")
        
        try:
            # Check if it's a JPEG file
            if self.file_data[:2] == b'\xff\xd8':
                return self._parse_jpeg()
            else:
                # IPTC is primarily in JPEG files
                return {}
        except Exception as e:
            raise MetadataReadError(f"Failed to read IPTC data: {str(e)}")
    
    def _parse_jpeg(self) -> Dict[str, Any]:
        """Parse IPTC data from a JPEG file (APP13 segment)."""
        offset = 2  # Skip JPEG SOI marker
        metadata = {}
        
        # Find APP13 segment (IPTC)
        while offset < len(self.file_data):
            # Check for segment marker
            if self.file_data[offset] != 0xFF:
                break
            
            marker = self.file_data[offset + 1]
            
            # APP13 marker (0xED) may contain IPTC data
            if marker == 0xED:
                # Read segment length
                length = struct.unpack('>H', self.file_data[offset + 2:offset + 4])[0]
                
                # Check for Photoshop header (IPTC is often in Photoshop format)
                segment_data = self.file_data[offset + 4:offset + 2 + length]
                
                # Look for "Photoshop 3.0" or "8BIM" markers
                if b'Photoshop 3.0' in segment_data or b'8BIM' in segment_data:
                    iptc_data = self._extract_iptc_from_photoshop(segment_data)
                    metadata.update(iptc_data)
            
            # Skip to next segment
            if marker == 0xD8:  # SOI
                offset += 2
            elif marker == 0xD9:  # EOI
                break
            elif marker >= 0xE0 and marker <= 0xEF:  # APP segments
                length = struct.unpack('>H', self.file_data[offset + 2:offset + 4])[0]
                offset += 2 + length
            else:
                # Skip other segments
                if offset + 2 < len(self.file_data):
                    length = struct.unpack('>H', self.file_data[offset + 2:offset + 4])[0]
                    offset += 2 + length
                else:
                    break
        
        return metadata
    
    def _extract_iptc_from_photoshop(self, segment_data: bytes) -> Dict[str, Any]:
        """
        Extract IPTC data from Photoshop APP13 segment.
        
        Args:
            segment_data: The APP13 segment data
            
        Returns:
            Dictionary of IPTC metadata
        """
        metadata = {}
        offset = 0
        
        # Look for IPTC data block (tag 0x0404)
        while offset < len(segment_data) - 4:
            # Check for "8BIM" marker
            if segment_data[offset:offset + 4] == b'8BIM':
                # Read resource ID (2 bytes, big-endian)
                if offset + 6 >= len(segment_data):
                    break
                
                resource_id = struct.unpack('>H', segment_data[offset + 4:offset + 6])[0]
                
                # Resource ID 0x0404 is IPTC data
                if resource_id == 0x0404:
                    # Read name (pascal string)
                    name_len = segment_data[offset + 6]
                    name_start = offset + 7
                    name_end = name_start + name_len
                    
                    # Name must be even length (padded)
                    if name_len % 2 == 0:
                        name_end += 1
                    
                    # Read data length (4 bytes, big-endian)
                    if name_end + 4 > len(segment_data):
                        break
                    
                    data_length = struct.unpack('>I', segment_data[name_end:name_end + 4])[0]
                    
                    # Data length must be even (padded)
                    if data_length % 2 != 0:
                        data_length += 1
                    
                    # Extract IPTC data
                    iptc_start = name_end + 4
                    iptc_end = iptc_start + data_length
                    
                    if iptc_end <= len(segment_data):
                        iptc_data = segment_data[iptc_start:iptc_end]
                        parsed = self._parse_iptc_data(iptc_data)
                        metadata.update(parsed)
                
                # Move to next resource
                # Skip name and data
                name_len = segment_data[offset + 6]
                name_start = offset + 7
                name_end = name_start + name_len
                if name_len % 2 == 0:
                    name_end += 1
                
                if name_end + 4 <= len(segment_data):
                    data_length = struct.unpack('>I', segment_data[name_end:name_end + 4])[0]
                    if data_length % 2 != 0:
                        data_length += 1
                    offset = name_end + 4 + data_length
                else:
                    offset += 1
            else:
                offset += 1
        
        return metadata
    
    def _parse_iptc_data(self, iptc_data: bytes) -> Dict[str, Any]:
        """
        Parse raw IPTC data block.
        
        IPTC data is stored as a series of records, each containing:
        - 1 byte: Record marker (0x1C)
        - 1 byte: Dataset number
        - 1 byte: Data type
        - 2 bytes: Data length (big-endian)
        - N bytes: Data
        
        Args:
            iptc_data: Raw IPTC data bytes
            
        Returns:
            Dictionary of parsed IPTC metadata
        """
        metadata = {}
        offset = 0
        
        while offset < len(iptc_data) - 5:
            # Check for record marker
            if iptc_data[offset] != 0x1C:
                offset += 1
                continue
            
            # Read dataset number and data type
            dataset = iptc_data[offset + 1]
            data_type = iptc_data[offset + 2]
            
            # Read data length (big-endian)
            data_length = struct.unpack('>H', iptc_data[offset + 3:offset + 5])[0]
            
            # Read data
            if offset + 5 + data_length > len(iptc_data):
                break
            
            data = iptc_data[offset + 5:offset + 5 + data_length]
            
            # Get tag name
            tag_name = IPTC_TAG_NAMES.get(dataset, f"Unknown_{dataset}")
            
            # Parse data based on type
            if data_type == 2:  # String
                value = data.decode('utf-8', errors='replace').strip()
                # Some tags can have multiple values
                if tag_name in metadata:
                    if isinstance(metadata[tag_name], list):
                        metadata[tag_name].append(value)
                    else:
                        metadata[tag_name] = [metadata[tag_name], value]
                else:
                    metadata[tag_name] = value
            
            offset += 5 + data_length
        
        return metadata

