# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Additional metadata standards support

This module provides support for additional metadata standards beyond
EXIF, IPTC, and XMP, including JFIF, ICC profiles, Photoshop IRB, etc.

Copyright 2025 DNAi inc.
"""

import struct
from typing import Dict, Any, Optional, List
from pathlib import Path

from dnexif.exceptions import MetadataReadError


class MetadataStandards:
    """
    Support for additional metadata standards.
    
    Provides parsers for JFIF, ICC profiles, Photoshop IRB, FlashPix, AFCP, etc.
    """
    
    @staticmethod
    def parse_jfif(file_data: bytes) -> Dict[str, Any]:
        """
        Parse JFIF (JPEG File Interchange Format) metadata.
        
        JFIF data is stored in JPEG APP0 segments.
        
        Args:
            file_data: JPEG file data
            
        Returns:
            Dictionary of JFIF metadata
        """
        metadata = {}
        
        try:
            if not file_data.startswith(b'\xff\xd8'):
                return metadata
            
            offset = 2  # Skip JPEG signature
            
            while offset < len(file_data) - 4:
                # Find APP0 marker (0xFFE0)
                if file_data[offset:offset+2] == b'\xff\xe0':
                    # Read segment length
                    length = struct.unpack('>H', file_data[offset+2:offset+4])[0]
                    
                    # Check for JFIF identifier
                    if file_data[offset+4:offset+9] == b'JFIF\x00':
                        # Parse JFIF data
                        version_major = file_data[offset+9]
                        version_minor = file_data[offset+10]
                        units = file_data[offset+11]
                        x_density = struct.unpack('>H', file_data[offset+12:offset+14])[0]
                        y_density = struct.unpack('>H', file_data[offset+14:offset+16])[0]
                        thumb_width = file_data[offset+16]
                        thumb_height = file_data[offset+17]
                        
                        # Standard format uses JFIF:JFIFVersion, not JFIF:Version
                        # Format version as "1.01" (2 decimal places) to standard format
                        metadata['JFIF:JFIFVersion'] = f"{version_major}.{version_minor:02d}"
                        
                        # JFIF:Units maps to ResolutionUnit
                        unit_names = ['None', 'DPI', 'DPC']
                        unit_name = unit_names[units] if units < 3 else 'Unknown'
                        metadata['JFIF:Units'] = unit_name
                        
                        # JFIF:ResolutionUnit - Standard format shows this as "inches" for DPI
                        if units == 1:  # DPI
                            metadata['JFIF:ResolutionUnit'] = 'inches'
                        elif units == 2:  # DPC
                            metadata['JFIF:ResolutionUnit'] = 'cm'
                        else:
                            metadata['JFIF:ResolutionUnit'] = 'None'
                        
                        metadata['JFIF:XResolution'] = x_density
                        metadata['JFIF:YResolution'] = y_density
                        metadata['JFIF:ThumbnailWidth'] = thumb_width
                        metadata['JFIF:ThumbnailHeight'] = thumb_height
                        
                        break
                    
                    offset += length
                else:
                    offset += 1
        
        except Exception:
            pass
        
        return metadata
    
    @staticmethod
    def parse_icc_profile(file_data: bytes) -> Dict[str, Any]:
        """
        Parse ICC color profile data.
        
        ICC profiles can be embedded in JPEG APP2 segments or TIFF files.
        
        Args:
            file_data: File data
            
        Returns:
            Dictionary of ICC profile metadata
        """
        metadata = {}
        
        try:
            # Check for JPEG APP2 segment with ICC profile
            if file_data.startswith(b'\xff\xd8'):
                offset = 2
                
                while offset < len(file_data) - 4:
                    if file_data[offset:offset+2] == b'\xff\xe2':  # APP2
                        length = struct.unpack('>H', file_data[offset+2:offset+4])[0]
                        
                        # Check for ICC profile identifier
                        if file_data[offset+4:offset+11] == b'ICC_PROFILE':
                            chunk_num = file_data[offset+11]
                            total_chunks = file_data[offset+12]
                            
                            metadata['ICC:ChunkNumber'] = chunk_num
                            metadata['ICC:TotalChunks'] = total_chunks
                            metadata['ICC:HasICCProfile'] = True
                            
                            # Extract profile data (simplified - full parsing is complex)
                            profile_data = file_data[offset+13:offset+length]
                            if len(profile_data) > 0:
                                metadata['ICC:ProfileSize'] = len(profile_data)
                            
                            break
                        
                        offset += length
                    else:
                        offset += 1
            
            # Check for TIFF ICC profile tag
            elif file_data[:2] in (b'II', b'MM'):
                # ICC profiles in TIFF are stored in specific tags
                # This is a simplified check
                if b'ICC_PROFILE' in file_data or b'acsp' in file_data:
                    metadata['ICC:HasICCProfile'] = True
        
        except Exception:
            pass
        
        return metadata
    
    @staticmethod
    def parse_photoshop_irb(file_data: bytes) -> Dict[str, Any]:
        """
        Parse Photoshop Image Resource Blocks (IRB).
        
        Photoshop IRB data is stored in JPEG APP13 segments.
        
        Args:
            file_data: JPEG file data
            
        Returns:
            Dictionary of Photoshop IRB metadata
        """
        metadata = {}
        
        try:
            if not file_data.startswith(b'\xff\xd8'):
                return metadata
            
            offset = 2
            
            while offset < len(file_data) - 4:
                if file_data[offset:offset+2] == b'\xff\xed':  # APP13
                    length = struct.unpack('>H', file_data[offset+2:offset+4])[0]
                    
                    # Check for Photoshop identifier
                    if file_data[offset+4:offset+8] == b'8BIM':
                        # Photoshop IRB found
                        resource_id = struct.unpack('>H', file_data[offset+8:offset+10])[0]
                        name_length = file_data[offset+10]
                        
                        metadata['Photoshop:HasIRB'] = True
                        metadata['Photoshop:ResourceID'] = resource_id
                        
                        # Common resource IDs (key Photoshop IRB resources)
                        resource_names = {
                            0x03E8: 'ResolutionInfo',
                            0x03E9: 'AlphaChannelsNames',
                            0x03EA: 'DisplayInfo',
                            0x03EB: 'Caption',
                            0x03ED: 'BorderInfo',
                            0x03EE: 'BackgroundColor',
                            0x0404: 'PrintFlags',
                            0x0405: 'ColorHalftoningInfo',
                            0x0406: 'ColorTransferFunctions',
                            0x0407: 'LayerStateInfo',
                            0x0408: 'LayersGroupInfo',
                            0x0409: 'IPTC-NAA',
                            0x040A: 'ImageModeForRawFormatFiles',
                            0x040B: 'JPEGQuality',
                            0x040C: 'GridAndGuidesInfo',
                            0x040D: 'ThumbnailResource',
                            0x040E: 'CopyrightInfo',
                            0x040F: 'URL',
                            0x0410: 'ThumbnailResource',
                            0x0411: 'GlobalAngle',
                            0x0412: 'ColorSamplersResource',
                            0x0413: 'ICC_Profile',
                            0x0414: 'Watermark',
                            0x0415: 'ICC_UntaggedProfile',
                            0x0416: 'EffectsVisible',
                            0x0417: 'SpotHalftone',
                            0x0418: 'DocumentSpecificIDs',
                            0x0419: 'UnicodeAlphaNames',
                            0x041A: 'IndexedColorTableCount',
                            0x041B: 'TransparentIndex',
                            0x041C: 'GlobalAltitude',
                            0x041D: 'Slices',
                            0x041E: 'WorkflowURL',
                            0x041F: 'JumpToXPEP',
                            0x0420: 'AlphaIdentifiers',
                            0x0421: 'URL_List',
                            0x0422: 'VersionInfo',
                            0x0423: 'EXIFData1',
                            0x0424: 'EXIFData3',
                            0x0425: 'XMPMetadata',
                            0x0426: 'CaptionDigest',
                            0x0427: 'PrintScale',
                            0x0428: 'PixelAspectRatio',
                            0x0429: 'LayerComps',
                            0x042A: 'AlternateDuotoneColors',
                            0x042B: 'AlternateSpotColors',
                            0x042C: 'LayerSelectionIDs',
                            0x042D: 'HDRToningInfo',
                            0x042E: 'PrintInfo',
                            0x042F: 'LayerGroupsEnabledID',
                            0x0430: 'ColorSamplersResource',
                            0x0431: 'MeasurementScale',
                            0x0432: 'TimelineInfo',
                            0x0433: 'SheetDisclosure',
                            0x0434: 'DisplayInfo',
                            0x0435: 'OnionSkins',
                            0x0436: 'CountInfo',
                        }
                        
                        resource_name = resource_names.get(resource_id, f'Unknown_{resource_id:04X}')
                        metadata['Photoshop:ResourceName'] = resource_name
                        
                        break
                    
                    offset += length
                else:
                    offset += 1
        
        except Exception:
            pass
        
        return metadata

