# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Tag listing utilities

Provides functionality to list available tags, writable tags, and tag names
compatible with standard -list, -listw, and -listx options.

Copyright 2025 DNAi inc.
"""

from typing import Dict, List, Set, Optional
from pathlib import Path

from dnexif.exif_tags import EXIF_TAG_NAMES
from dnexif.exif_tags_3_0 import EXIF_3_0_TAG_NAMES
from dnexif.iptc_parser import IPTC_TAG_NAMES
# MakerNote tags are accessed via get_makernote_tag_name function
try:
    from dnexif.makernote_tags import get_makernote_tag_name
    HAS_MAKERNOTE = True
except ImportError:
    HAS_MAKERNOTE = False


class TagLister:
    """
    Utility class for listing available tags.
    
    Provides methods to list all tags, writable tags, and tag names
    in various formats.
    """
    
    # Metadata groups
    GROUPS = ['EXIF', 'IPTC', 'XMP', 'GPS', 'IFD0', 'IFD1', 'MakerNote']
    
    @staticmethod
    def list_all_tags(group: Optional[str] = None) -> List[str]:
        """
        List all available tags.
        
        Args:
            group: Optional group name to filter by (e.g., 'EXIF', 'IPTC')
            
        Returns:
            List of tag names
        """
        tags = set()
        
        # EXIF tags
        if group is None or group == 'EXIF':
            for tag_id, tag_name in EXIF_TAG_NAMES.items():
                tags.add(f"EXIF:{tag_name}")
            for tag_id, tag_name in EXIF_3_0_TAG_NAMES.items():
                tags.add(f"EXIF:{tag_name}")
        
        # IPTC tags
        if group is None or group == 'IPTC':
            for tag_id, tag_name in IPTC_TAG_NAMES.items():
                tags.add(f"IPTC:{tag_name}")
        
        # XMP tags (common ones)
        if group is None or group == 'XMP':
            xmp_tags = [
                'XMP:Title', 'XMP:Description', 'XMP:Creator', 'XMP:Subject',
                'XMP:Keywords', 'XMP:Rights', 'XMP:DateCreated', 'XMP:DateModified',
                'XMP:Rating', 'XMP:ColorMode', 'XMP:ICCProfile', 'XMP:Copyright',
                'XMP:CreatorTool', 'XMP:MetadataDate', 'XMP:ModifyDate',
                'XMP:CreateDate', 'XMP:Creator', 'XMP:AuthorsPosition',
                'XMP:CaptionWriter', 'XMP:Category', 'XMP:Urgency',
                'XMP:Instructions', 'XMP:TransmissionReference', 'XMP:Headline',
                'XMP:DateCreated', 'XMP:City', 'XMP:State', 'XMP:Country',
                'XMP:CountryCode', 'XMP:Location', 'XMP:ProvinceState',
                'XMP:IntellectualGenre', 'XMP:Scene', 'XMP:ImageUniqueID',
                'XMP:DocumentID', 'XMP:OriginalDocumentID', 'XMP:History',
                'XMP:DerivedFrom', 'XMP:PreservedFileName', 'XMP:Version',
                'XMP:HistoryWhen', 'XMP:HistorySoftwareAgent', 'XMP:HistoryAction',
                'XMP:HistoryChanged', 'XMP:HistoryInstanceID', 'XMP:HistoryParameters',
                'XMP:SidecarForExtension', 'XMP:HasExtendedXMP', 'XMP:ExtendedXMP',
                'XMP:ExtendedXMPDigest', 'XMP:Thumbnails', 'XMP:ThumbnailImage',
                'XMP:ThumbnailFormat', 'XMP:ThumbnailWidth', 'XMP:ThumbnailHeight',
                'XMP:PhotoshopColorMode', 'XMP:PhotoshopICCProfile',
                'XMP:PhotoshopHistory', 'XMP:PhotoshopAuthorsPosition',
                'XMP:PhotoshopCaptionWriter', 'XMP:PhotoshopCategory',
                'XMP:PhotoshopUrgency', 'XMP:PhotoshopInstructions',
                'XMP:PhotoshopTransmissionReference', 'XMP:PhotoshopHeadline',
                'XMP:PhotoshopDateCreated', 'XMP:PhotoshopCity', 'XMP:PhotoshopState',
                'XMP:PhotoshopCountry', 'XMP:PhotoshopCountryCode',
                'XMP:PhotoshopLocation', 'XMP:PhotoshopProvinceState',
                'XMP:PhotoshopIntellectualGenre', 'XMP:PhotoshopScene',
                'XMP:PhotoshopImageUniqueID', 'XMP:PhotoshopDocumentID',
                'XMP:PhotoshopOriginalDocumentID', 'XMP:PhotoshopHistory',
                'XMP:PhotoshopDerivedFrom', 'XMP:PhotoshopPreservedFileName',
                'XMP:PhotoshopVersion', 'XMP:PhotoshopHistoryWhen',
                'XMP:PhotoshopHistorySoftwareAgent', 'XMP:PhotoshopHistoryAction',
                'XMP:PhotoshopHistoryChanged', 'XMP:PhotoshopHistoryInstanceID',
                'XMP:PhotoshopHistoryParameters', 'XMP:PhotoshopSidecarForExtension',
                'XMP:PhotoshopHasExtendedXMP', 'XMP:PhotoshopExtendedXMP',
                'XMP:PhotoshopExtendedXMPDigest', 'XMP:PhotoshopThumbnails',
                'XMP:PhotoshopThumbnailImage', 'XMP:PhotoshopThumbnailFormat',
                'XMP:PhotoshopThumbnailWidth', 'XMP:PhotoshopThumbnailHeight',
                'XMP:EXIFVersion', 'XMP:EXIFColorSpace', 'XMP:EXIFComponentsConfiguration',
                'XMP:EXIFCompressedBitsPerPixel', 'XMP:EXIFPixelXDimension',
                'XMP:EXIFPixelYDimension', 'XMP:EXIFUserComment', 'XMP:EXIFRelatedSoundFile',
                'XMP:EXIFDateTimeOriginal', 'XMP:EXIFDateTimeDigitized',
                'XMP:EXIFSubSecTime', 'XMP:EXIFSubSecTimeOriginal', 'XMP:EXIFSubSecTimeDigitized',
                'XMP:EXIFExposureTime', 'XMP:EXIFFNumber', 'XMP:EXIFExposureProgram',
                'XMP:EXIFSpectralSensitivity', 'XMP:EXIFISOSpeedRatings',
                'XMP:EXIFOECF', 'XMP:EXIFSensitivityType', 'XMP:EXIFStandardOutputSensitivity',
                'XMP:EXIFRecommendedExposureIndex', 'XMP:EXIFISOSpeed', 'XMP:EXIFISOSpeedLatitudeYYY',
                'XMP:EXIFISOSpeedLatitudeZZZ', 'XMP:EXIFShutterSpeedValue', 'XMP:EXIFApertureValue',
                'XMP:EXIFBrightnessValue', 'XMP:EXIFExposureBiasValue', 'XMP:EXIFMaxApertureValue',
                'XMP:EXIFSubjectDistance', 'XMP:EXIFMeteringMode', 'XMP:EXIFLightSource',
                'XMP:EXIFFlash', 'XMP:EXIFFocalLength', 'XMP:EXIFSubjectArea',
                'XMP:EXIFFlashEnergy', 'XMP:EXIFSpatialFrequencyResponse',
                'XMP:EXIFFocalPlaneXResolution', 'XMP:EXIFFocalPlaneYResolution',
                'XMP:EXIFFocalPlaneResolutionUnit', 'XMP:EXIFSubjectLocation',
                'XMP:EXIFExposureIndex', 'XMP:EXIFSensingMethod', 'XMP:EXIFFileSource',
                'XMP:EXIFSceneType', 'XMP:EXIFCFAPattern', 'XMP:EXIFCustomRendered',
                'XMP:EXIFExposureMode', 'XMP:EXIFWhiteBalance', 'XMP:EXIFDigitalZoomRatio',
                'XMP:EXIFFocalLengthIn35mmFilm', 'XMP:EXIFSceneCaptureType',
                'XMP:EXIFGainControl', 'XMP:EXIFContrast', 'XMP:EXIFSaturation',
                'XMP:EXIFSharpness', 'XMP:EXIFDeviceSettingDescription',
                'XMP:EXIFSubjectDistanceRange', 'XMP:EXIFImageUniqueID',
                'XMP:TIFFImageWidth', 'XMP:TIFFImageLength', 'XMP:TIFFBitsPerSample',
                'XMP:TIFFCompression', 'XMP:TIFFPhotometricInterpretation',
                'XMP:TIFFOrientation', 'XMP:TIFFSamplesPerPixel', 'XMP:TIFFPlanarConfiguration',
                'XMP:TIFFYCbCrSubSampling', 'XMP:TIFFYCbCrPositioning',
                'XMP:TIFFXResolution', 'XMP:TIFFYResolution', 'XMP:TIFFResolutionUnit',
                'XMP:TIFFTransferFunction', 'XMP:TIFFWhitePoint', 'XMP:TIFFPrimaryChromaticities',
                'XMP:TIFFYCbCrCoefficients', 'XMP:TIFFReferenceBlackWhite',
                'XMP:TIFFDateTime', 'XMP:TIFFImageDescription', 'XMP:TIFFMake',
                'XMP:TIFFModel', 'XMP:TIFFSoftware', 'XMP:TIFFArtist', 'XMP:TIFFCopyright',
                'XMP:TIFFCopyright', 'XMP:TIFFHostComputer', 'XMP:TIFFInkSet',
                'XMP:TIFFInkNames', 'XMP:TIFFNumberOfInks', 'XMP:TIFFDotRange',
                'XMP:TIFFTargetPrinter', 'XMP:TIFFExtraSamples', 'XMP:TIFFSampleFormat',
                'XMP:TIFFSMinSampleValue', 'XMP:TIFFSMaxSampleValue', 'XMP:TIFFTransferRange',
                'XMP:TIFFClipPath', 'XMP:TIFFXClipPathUnits', 'XMP:TIFFYClipPathUnits',
                'XMP:TIFFIndexed', 'XMP:TIFFJPEGTables', 'XMP:TIFFOPIProxy',
                'XMP:TIFFJPEGProc', 'XMP:TIFFJPEGInterchangeFormat',
                'XMP:TIFFJPEGInterchangeFormatLength', 'XMP:TIFFJPEGRestartInterval',
                'XMP:TIFFJPEGLosslessPredictors', 'XMP:TIFFJPEGPointTransforms',
                'XMP:TIFFJPEGQTables', 'XMP:TIFFJPEGDCTables', 'XMP:TIFFJPEGACTables',
                'XMP:TIFFYCbCrSubSampling', 'XMP:TIFFYCbCrPositioning',
                'XMP:TIFFReferenceBlackWhite', 'XMP:TIFFStripOffsets', 'XMP:TIFFRowsPerStrip',
                'XMP:TIFFStripByteCounts', 'XMP:TIFFXPosition', 'XMP:TIFFYPosition',
                'XMP:TIFFFreeOffsets', 'XMP:TIFFFreeByteCounts', 'XMP:TIFFGrayResponseCurve',
                'XMP:TIFFGrayResponseUnit', 'XMP:TIFFT4Options', 'XMP:TIFFT6Options',
                'XMP:TIFFTileWidth', 'XMP:TIFFTileLength', 'XMP:TIFFTileOffsets',
                'XMP:TIFFTileByteCounts', 'XMP:TIFFBadFaxLines', 'XMP:TIFFCleanFaxData',
                'XMP:TIFFConsecutiveBadFaxLines', 'XMP:TIFFSubIFDs', 'XMP:TIFFInkSet',
                'XMP:TIFFInkNames', 'XMP:TIFFNumberOfInks', 'XMP:TIFFDotRange',
                'XMP:TIFFTargetPrinter', 'XMP:TIFFExtraSamples', 'XMP:TIFFSampleFormat',
                'XMP:TIFFSMinSampleValue', 'XMP:TIFFSMaxSampleValue', 'XMP:TIFFTransferRange',
                'XMP:TIFFClipPath', 'XMP:TIFFXClipPathUnits', 'XMP:TIFFYClipPathUnits',
                'XMP:TIFFIndexed', 'XMP:TIFFJPEGTables', 'XMP:TIFFOPIProxy',
                'XMP:TIFFJPEGProc', 'XMP:TIFFJPEGInterchangeFormat',
                'XMP:TIFFJPEGInterchangeFormatLength', 'XMP:TIFFJPEGRestartInterval',
                'XMP:TIFFJPEGLosslessPredictors', 'XMP:TIFFJPEGPointTransforms',
                'XMP:TIFFJPEGQTables', 'XMP:TIFFJPEGDCTables', 'XMP:TIFFJPEGACTables',
                'XMP:TIFFYCbCrSubSampling', 'XMP:TIFFYCbCrPositioning',
                'XMP:TIFFReferenceBlackWhite', 'XMP:GPSVersionID', 'XMP:GPSLatitude',
                'XMP:GPSLongitude', 'XMP:GPSAltitude', 'XMP:GPSTimeStamp',
                'XMP:GPSSatellites', 'XMP:GPSStatus', 'XMP:GPSMeasureMode',
                'XMP:GPSDOP', 'XMP:GPSSpeedRef', 'XMP:GPSSpeed', 'XMP:GPSTrackRef',
                'XMP:GPSTrack', 'XMP:GPSImgDirectionRef', 'XMP:GPSImgDirection',
                'XMP:GPSMapDatum', 'XMP:GPSDestLatitude', 'XMP:GPSDestLongitude',
                'XMP:GPSDestBearingRef', 'XMP:GPSDestBearing', 'XMP:GPSDestDistanceRef',
                'XMP:GPSDestDistance', 'XMP:GPSProcessingMethod', 'XMP:GPSAreaInformation',
                'XMP:GPSDateStamp', 'XMP:GPSDifferential', 'XMP:GPSHPositioningError',
            ]
            tags.update(xmp_tags)
        
        # GPS tags
        if group is None or group == 'GPS':
            gps_tags = [
                'GPS:GPSVersionID', 'GPS:GPSLatitude', 'GPS:GPSLongitude',
                'GPS:GPSAltitude', 'GPS:GPSTimeStamp', 'GPS:GPSSatellites',
                'GPS:GPSStatus', 'GPS:GPSMeasureMode', 'GPS:GPSDOP',
                'GPS:GPSSpeedRef', 'GPS:GPSSpeed', 'GPS:GPSTrackRef',
                'GPS:GPSTrack', 'GPS:GPSImgDirectionRef', 'GPS:GPSImgDirection',
                'GPS:GPSMapDatum', 'GPS:GPSDestLatitude', 'GPS:GPSDestLongitude',
                'GPS:GPSDestBearingRef', 'GPS:GPSDestBearing', 'GPS:GPSDestDistanceRef',
                'GPS:GPSDestDistance', 'GPS:GPSProcessingMethod', 'GPS:GPSAreaInformation',
                'GPS:GPSDateStamp', 'GPS:GPSDifferential', 'GPS:GPSHPositioningError',
            ]
            tags.update(gps_tags)
        
        # MakerNote tags (if available)
        if group is None or group == 'MakerNote' and HAS_MAKERNOTE:
            # MakerNote tags are manufacturer-specific, so we'll add common ones
            # In a real implementation, we'd iterate through all manufacturers
            common_makers = ['Canon', 'Nikon', 'Sony', 'Fujifilm', 'Olympus', 'Panasonic']
            for maker in common_makers:
                # Add some common MakerNote tags (this is a simplified approach)
                for tag_id in range(0x0001, 0x0100):
                    tag_name = get_makernote_tag_name(maker, tag_id)
                    if tag_name:
                        tags.add(f"MakerNote:{tag_name}")
        
        return sorted(list(tags))
    
    @staticmethod
    def list_writable_tags(group: Optional[str] = None) -> List[str]:
        """
        List all writable tags.
        
        Args:
            group: Optional group name to filter by
            
        Returns:
            List of writable tag names
        """
        # Most tags are writable, but some are read-only
        # For now, return all tags (can be refined later)
        all_tags = TagLister.list_all_tags(group)
        
        # Filter out read-only tags
        read_only_tags = {
            'EXIF:ExifVersion',  # Version tags are typically read-only
            'EXIF:FlashPixVersion',
            'EXIF:InteroperabilityVersion',
        }
        
        writable_tags = [tag for tag in all_tags if tag not in read_only_tags]
        return writable_tags
    
    @staticmethod
    def list_tag_names(group: Optional[str] = None) -> List[str]:
        """
        List tag names (without group prefix).
        
        Args:
            group: Optional group name to filter by
            
        Returns:
            List of tag names without group prefix
        """
        all_tags = TagLister.list_all_tags(group)
        tag_names = [tag.split(':', 1)[1] if ':' in tag else tag for tag in all_tags]
        return sorted(list(set(tag_names)))
    
    @staticmethod
    def get_tag_info(tag_name: str) -> Dict[str, any]:
        """
        Get information about a specific tag.
        
        Args:
            tag_name: Tag name (with or without group prefix)
            
        Returns:
            Dictionary with tag information
        """
        info = {
            'name': tag_name,
            'group': None,
            'writable': True,
            'type': 'Unknown',
        }
        
        if ':' in tag_name:
            group, name = tag_name.split(':', 1)
            info['group'] = group
            info['name'] = name
        
        # Check if tag exists
        all_tags = TagLister.list_all_tags()
        if tag_name in all_tags:
            info['exists'] = True
        else:
            info['exists'] = False
        
        # Check if writable
        writable_tags = TagLister.list_writable_tags()
        if tag_name in writable_tags:
            info['writable'] = True
        else:
            info['writable'] = False
        
        return info

