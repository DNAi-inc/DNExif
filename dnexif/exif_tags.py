# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
Comprehensive EXIF tag definitions

This module contains all EXIF tag definitions to achieve 1:1 parity with standard format.
Based on EXIF 2.3 specification and standard tag database.

Copyright 2025 DNAi inc.
"""

# Comprehensive EXIF tag database
# Based on EXIF 2.3 specification and standard format tag definitions

EXIF_TAG_NAMES = {
    # ============================================================
    # IFD0 (Image) Tags (0x0000 - 0x01FF)
    # ============================================================
    0x000B: "ProcessingSoftware",
    0x00FE: "SubfileType",
    0x00FF: "OldSubfileType",
    0x0100: "ImageWidth",
    0x0101: "ImageLength",
    0x0102: "BitsPerSample",
    0x0103: "Compression",
    0x0106: "PhotometricInterpretation",
    0x0107: "Threshholding",
    0x0108: "CellWidth",
    0x0109: "CellLength",
    0x010A: "FillOrder",
    0x010D: "DocumentName",
    0x010E: "ImageDescription",
    0x010F: "Make",
    0x0110: "Model",
    0x0111: "StripOffsets",
    0x0112: "Orientation",
    0x0115: "SamplesPerPixel",
    0x0116: "RowsPerStrip",
    0x0117: "StripByteCounts",
    0x0118: "MinSampleValue",
    0x0119: "MaxSampleValue",
    0x011A: "XResolution",
    0x011B: "YResolution",
    0x011C: "PlanarConfiguration",
    0x011D: "PageName",
    0x011E: "XPosition",
    0x011F: "YPosition",
    0x0120: "FreeOffsets",
    0x0121: "FreeByteCounts",
    0x0122: "GrayResponseUnit",
    0x0123: "GrayResponseCurve",
    0x0124: "T4Options",
    0x0125: "T6Options",
    0x0128: "ResolutionUnit",
    0x0129: "PageNumber",
    0x012C: "ColorResponseUnit",
    0x012D: "TransferFunction",
    0x0131: "Software",
    0x0132: "DateTime",
    0x013B: "Artist",
    0x013C: "HostComputer",
    0x013D: "Predictor",
    0x013E: "WhitePoint",
    0x013F: "PrimaryChromaticities",
    0x0140: "ColorMap",
    0x0141: "HalftoneHints",
    0x0142: "TileWidth",
    0x0143: "TileLength",
    0x0144: "TileOffsets",
    0x0145: "TileByteCounts",
    0x014A: "SubIFDs",
    0x014C: "InkSet",
    0x014D: "InkNames",
    0x014E: "NumberOfInks",
    0x0150: "DotRange",
    0x0151: "TargetPrinter",
    0x0152: "ExtraSamples",
    0x0153: "SampleFormat",
    0x0154: "SMinSampleValue",
    0x0155: "SMaxSampleValue",
    0x0156: "TransferRange",
    0x0157: "ClipPath",
    0x0158: "XClipPathUnits",
    0x0159: "YClipPathUnits",
    0x015A: "Indexed",
    0x015B: "JPEGTables",
    # Private TIFF tags (0x5000-0x5FFF)
    0x5110: "PixelUnits",
    0x5111: "PixelsPerUnitX",
    0x5112: "PixelsPerUnitY",
    0x015F: "OPIProxy",
    0x0200: "JPEGProc",
    0x0201: "JPEGInterchangeFormat",
    0x0202: "JPEGInterchangeFormatLength",
    0x0203: "JPEGRestartInterval",
    0x0205: "JPEGLosslessPredictors",
    0x0206: "JPEGPointTransforms",
    0x0207: "JPEGQTables",
    0x0208: "JPEGDCTables",
    0x0209: "JPEGACTables",
    0x0211: "YCbCrCoefficients",
    0x0212: "YCbCrSubSampling",
    0x0213: "YCbCrPositioning",
    0x0214: "ReferenceBlackWhite",
    0x02BC: "XMLPacket",
    0x800D: "ImageID",
    0x80E3: "WangTag1",
    0x80E4: "WangAnnotation",
    0x80E5: "WangTag3",
    0x80E6: "WangTag4",
    # Leaf MOS tags (0x8000-0x8070 range) - Leaf-specific private IFD tags
    0x8000: "Leaf:CCDRect",
    0x8001: "Leaf:CCDValidRect",
    0x8002: "Leaf:CCDVideoRect",
    0x8003: "Leaf:CameraBackType",
    0x8004: "Leaf:CameraName",
    0x8005: "Leaf:CameraObjBackType",
    0x8006: "Leaf:CameraObjName",
    0x8007: "Leaf:CameraObjType",
    0x8008: "Leaf:CameraObjVersion",
    0x8009: "Leaf:CameraProfileVersion",
    0x800A: "Leaf:CameraType",
    0x800B: "Leaf:CaptProfBackType",
    0x800C: "Leaf:CaptProfName",
    0x800D: "Leaf:CaptProfType",
    0x800E: "Leaf:CaptProfVersion",
    0x800F: "Leaf:CaptureObjBackType",
    0x8010: "Leaf:CaptureObjName",
    0x8011: "Leaf:CaptureObjType",
    0x8012: "Leaf:CaptureObjVersion",
    0x8013: "Leaf:CaptureSerial",
    0x8014: "Leaf:CenterDarkRect",
    0x8015: "Leaf:ColorAverages",
    0x8016: "Leaf:ColorCasts",
    0x8017: "Leaf:ColorMatrix",
    0x8018: "Leaf:ColorObjBackType",
    0x8019: "Leaf:ColorObjName",
    0x801A: "Leaf:ColorObjType",
    0x801B: "Leaf:ColorObjVersion",
    0x801C: "Leaf:DarkCorrectionType",
    0x801D: "Leaf:DataLen",
    0x801E: "Leaf:Gamma",
    0x801F: "Leaf:HasICC",
    0x8020: "Leaf:HighlightEndPoints",
    0x8021: "Leaf:ISOSpeed",
    0x8022: "Leaf:ImageBounds",
    0x8023: "Leaf:ImageFields",
    0x8024: "Leaf:ImageOffset",
    0x8025: "Leaf:ImageStatus",
    0x8026: "Leaf:ImgProfBackType",
    0x8027: "Leaf:ImgProfName",
    0x8028: "Leaf:ImgProfType",
    0x8029: "Leaf:ImgProfVersion",
    0x802A: "Leaf:InputProfile",
    0x802B: "Leaf:LeafAutoActive",
    0x802C: "Leaf:LeafAutoBaseName",
    0x802D: "Leaf:LeafHotFolder",
    0x802E: "Leaf:LeafOpenProcHDR",
    0x802F: "Leaf:LeafOutputFileType",
    0x8030: "Leaf:LeafSaveSelection",
    0x8031: "Leaf:LeftDarkRect",
    0x8032: "Leaf:LensID",
    0x8033: "Leaf:LensType",
    0x8034: "Leaf:Locks",
    0x8035: "Leaf:LuminanceConsts",
    0x8036: "Leaf:MosaicPattern",
    0x8037: "Leaf:MultiQuality",
    0x8038: "Leaf:NeutObjBackType",
    0x8039: "Leaf:NeutObjName",
    0x803A: "Leaf:NeutObjType",
    0x803B: "Leaf:NeutObjVersion",
    0x803C: "Leaf:Neutrals",
    0x803D: "Leaf:Npts",
    0x803E: "Leaf:NumberOfPlanes",
    0x803F: "Leaf:Orientation",
    0x8040: "Leaf:OutputProfile",
    0x8041: "Leaf:PDAHistogram",
    0x8042: "Leaf:PreviewImage",
    0x8043: "Leaf:PreviewInfo",
    0x8044: "Leaf:RawDataRotation",
    0x8045: "Leaf:ReconstructionType",
    0x8046: "Leaf:Rect",
    0x8047: "Leaf:Resolution",
    0x8048: "Leaf:RightDarkRect",
    0x8049: "Leaf:RotationAngle",
    0x804A: "Leaf:SaveObjBackType",
    0x804B: "Leaf:SaveObjName",
    0x804C: "Leaf:SaveObjType",
    0x804D: "Leaf:SaveObjVersion",
    0x804E: "Leaf:Scale",
    0x804F: "Leaf:SelObjBackType",
    0x8050: "Leaf:SelObjName",
    0x8051: "Leaf:SelObjType",
    0x8052: "Leaf:SelObjVersion",
    0x8053: "Leaf:ShadowEndPoints",
    0x8054: "Leaf:SharpInfo",
    0x8055: "Leaf:SharpMethod",
    0x8056: "Leaf:SharpObjBackType",
    0x8057: "Leaf:SharpObjName",
    0x8058: "Leaf:SharpObjType",
    0x8059: "Leaf:SharpObjVersion",
    0x805A: "Leaf:ShootObjBackType",
    0x805B: "Leaf:ShootObjName",
    0x805C: "Leaf:ShootObjType",
    0x805D: "Leaf:ShootObjVersion",
    0x805E: "Leaf:SingleQuality",
    0x805F: "Leaf:StdAutoActive",
    0x8060: "Leaf:StdBaseName",
    0x8061: "Leaf:StdHotFolder",
    0x8062: "Leaf:StdOpenInPhotoshop",
    0x8063: "Leaf:StdOutputBitDepth",
    0x8064: "Leaf:StdOutputColorMode",
    0x8065: "Leaf:StdOutputFileType",
    0x8066: "Leaf:StdOxygen",
    0x8067: "Leaf:StdSaveSelection",
    0x8068: "Leaf:StdScaledOutput",
    0x8069: "Leaf:StdSharpenOutput",
    0x806A: "Leaf:Strobe",
    0x806B: "Leaf:ToneObjBackType",
    0x806C: "Leaf:ToneObjName",
    0x806D: "Leaf:ToneObjType",
    0x806E: "Leaf:ToneObjVersion",
    0x806F: "Leaf:Tones",
    0x8070: "Leaf:XYOffsetInfo",
    0x8214: "CFARepeatPatternDim",
    0x8216: "CFAPattern2",
    0x8218: "BatteryLevel",
    0x828D: "CFAPlaneColor",
    0x828E: "CFALayout",
    0x828F: "LinearizationTable",
    0x8290: "BlackLevelRepeatDim",
    0x8291: "BlackLevel",
    0x8292: "BlackLevelDeltaH",
    0x8293: "BlackLevelDeltaV",
    0x8294: "WhiteLevel",
    0x8295: "DefaultScale",
    0x8296: "DefaultCropOrigin",
    0x8297: "DefaultCropSize",
    # 0x8298 is the standard EXIF Copyright tag.
    # It was previously (incorrectly) mapped to "ColorMatrix1", which caused
    # DNG files to report the ColorMatrix1 value as a copyright string
    # instead of the proper color matrix rational array. The DNG-specific
    # ColorMatrix1 tags are correctly defined in the extended EXIF tag
    # tables (see exif_tags_complete.py / exif_tags_advanced.py), so we
    # restore the canonical mapping here to match the EXIF specification
    # and standard behavior.
    0x8298: "Copyright",
    0x8299: "ColorMatrix2",
    0x829A: "CameraCalibration1",
    0x829B: "CameraCalibration2",
    0x829C: "ReductionMatrix1",
    0x829D: "ReductionMatrix2",
    0x829E: "AnalogBalance",
    0x829F: "AsShotNeutral",
    0x82A0: "AsShotWhiteXY",
    0x82A1: "BaselineExposure",
    0x82A2: "BaselineNoise",
    0x82A3: "BaselineSharpness",
    0x82A4: "BayerGreenSplit",
    0x82A5: "LinearResponseLimit",
    0x82A6: "CameraSerialNumber",
    0x82A7: "LensInfo",
    0x82A8: "ChromaBlurRadius",
    0x82A9: "AntiAliasStrength",
    0x82AA: "ShadowScale",
    0x82AB: "DNGPrivateData",
    0x82AC: "MakerNoteSafety",
    0x82AD: "CalibrationIlluminant1",
    0x82AE: "CalibrationIlluminant2",
    0x82AF: "BestQualityScale",
    0x82B0: "RawDataUniqueID",
    0x82B1: "OriginalRawFileName",
    0x82B2: "OriginalRawFileData",
    0x82B3: "ActiveArea",
    0x82B4: "MaskedAreas",
    0x82B5: "AsShotICCProfile",
    0x82B6: "AsShotPreProfileMatrix",
    0x82B7: "CurrentICCProfile",
    0x82B8: "CurrentPreProfileMatrix",
    0x830E: "CameraCalibrationSignature",
    0x831F: "ProfileCalibrationSignature",
    0x8325: "AsShotProfileName",
    0x8332: "NoiseReductionApplied",
    0x8333: "ProfileName",
    0x8334: "ProfileHueSatMapDims",
    0x8335: "ProfileHueSatMapData1",
    0x8336: "ProfileHueSatMapData2",
    0x833C: "ProfileToneCurve",
    0x8340: "ProfileEmbedPolicy",
    0x8341: "ProfileCopyright",
    0x835C: "ForwardMatrix1",
    0x835D: "ForwardMatrix2",
    0x835E: "PreviewApplicationName",
    0x835F: "PreviewApplicationVersion",
    0x8360: "PreviewSettingsName",
    0x8361: "PreviewSettingsDigest",
    0x8362: "PreviewColorSpace",
    0x8363: "PreviewDateTime",
    0x8364: "RawImageDigest",
    0x8365: "OriginalRawFileDigest",
    0x8366: "SubTileBlockSize",
    0x8367: "RowInterleaveFactor",
    0x8370: "ProfileLookTableDims",
    0x8371: "ProfileLookTableData",
    0x8372: "OpcodeList1",
    0x8373: "OpcodeList2",
    0x8374: "OpcodeList3",
    0x8382: "NoiseProfile",
    0x85B8: "DefaultUserCrop",
    0x8773: "Copyright",
    
    # ============================================================
    # EXIF IFD Tags (0x8000 - 0x87FF)
    # ============================================================
    0x829A: "ExposureTime",
    0x829D: "FNumber",
    0x8822: "ExposureProgram",
    0x8824: "SpectralSensitivity",
    0x8825: "GPSInfo",
    0x8827: "ISOSpeedRatings",
    0x8828: "OECF",
    0x8829: "Interlace",
    0x882A: "TimeZoneOffset",
    0x882B: "SelfTimerMode",
    0x9000: "ExifVersion",
    # EXIF 2.3/3.0 core date/time fields:
    # 0x9003 = DateTimeOriginal, 0x9004 = CreateDate (a.k.a. DateTimeDigitized)
    # ComponentsConfiguration and CompressedBitsPerPixel live at 0x9101/0x9102.
    0x9003: "DateTimeOriginal",
    0x9004: "CreateDate",
    0x9101: "ComponentsConfiguration",
    0x9102: "CompressedBitsPerPixel",
    0x9005: "ShutterSpeedValue",
    0x9006: "ApertureValue",
    0x9007: "BrightnessValue",
    0x9008: "ExposureBiasValue",
    0x9009: "MaxApertureValue",
    0x900A: "SubjectDistance",
    0x900B: "MeteringMode",
    0x900C: "LightSource",
    0x900D: "Flash",
    0x900E: "FocalLength",
    0x900F: "FlashEnergy",
    0x9010: "SpatialFrequencyResponse",
    0x9011: "Noise",
    0x9012: "FocalPlaneXResolution",
    0x9013: "FocalPlaneYResolution",
    0x9014: "FocalPlaneResolutionUnit",
    0x9015: "ImageNumber",
    0x9016: "SecurityClassification",
    0x9017: "ImageHistory",
    0x9018: "SubjectLocation",
    0x9019: "ExposureIndex",
    0x901A: "TIFF/EPStandardID",
    0x901B: "SensingMethod",
    0x9201: "ShutterSpeedValue",
    0x9202: "ApertureValue",
    0x9203: "BrightnessValue",
    0x9204: "ExposureBiasValue",
    0x9205: "MaxApertureValue",
    0x9206: "SubjectDistance",
    0x9207: "MeteringMode",
    0x9208: "LightSource",
    0x9209: "Flash",
    0x920A: "FocalLength",
    0x920B: "FlashEnergy",
    0x920C: "SpatialFrequencyResponse",
    0x920D: "Noise",
    # Note: 0x920E, 0x920F, 0x9210 are duplicates - correct tags are 0xA20D, 0xA20E, 0xA20F
    # Removing incorrect mappings to avoid confusion
    0x9211: "ImageNumber",
    0x9212: "SecurityClassification",
    0x9213: "ImageHistory",
    0x9214: "SubjectArea",
    0x9215: "ExposureIndex",
    0x9216: "TIFF/EPStandardID",
    0x9217: "SensingMethod",
    0x927C: "MakerNote",
    0x9286: "UserComment",
    0x9290: "SubSecTime",
    0x9291: "SubSecTimeOriginal",
    0x9292: "SubSecTimeDigitized",
    0x9400: "Temperature",
    0x9401: "Humidity",
    0x9402: "Pressure",
    0x9403: "WaterDepth",
    0x9404: "Acceleration",
    0x9405: "CameraElevationAngle",
    0xA000: "FlashPixVersion",
    0xA001: "ColorSpace",
    0xA002: "PixelXDimension",
    0xA003: "PixelYDimension",
    0xA004: "RelatedSoundFile",
    0xA005: "InteroperabilityIFD",
    0xA20B: "FlashEnergy",
    0xA20C: "SpatialFrequencyResponse",
    0xA20D: "FocalPlaneXResolution",
    0xA20E: "FocalPlaneYResolution",
    0xA20F: "FocalPlaneResolutionUnit",
    0xA210: "SubjectLocation",
    0xA211: "ExposureIndex",
    0xA212: "SensingMethod",
    0xA213: "FileSource",
    0xA214: "SceneType",
    0xA215: "CFAPattern",
    0xA216: "CustomRendered",
    0xA217: "ExposureMode",
    0xA218: "WhiteBalance",
    0xA219: "DigitalZoomRatio",
    0xA21A: "FocalLengthIn35mmFilm",
    0xA21B: "SceneCaptureType",
    0xA21C: "GainControl",
    0xA21D: "Contrast",
    0xA21E: "Saturation",
    0xA21F: "Sharpness",
    0xA220: "DeviceSettingDescription",
    0xA221: "SubjectDistanceRange",
    0xA300: "FileSource",
    0xA301: "SceneType",
    0xA302: "CFAPattern",
    0xA401: "CustomRendered",
    0xA402: "ExposureMode",
    0xA403: "WhiteBalance",
    0xA404: "DigitalZoomRatio",
    0xA405: "FocalLengthIn35mmFilm",
    0xA406: "SceneCaptureType",
    0xA407: "GainControl",
    0xA408: "Contrast",
    0xA409: "Saturation",
    0xA40A: "Sharpness",
    0xA40B: "DeviceSettingDescription",
    0xA40C: "SubjectDistanceRange",
    0xA420: "ImageUniqueID",
    0xA430: "CameraOwnerName",
    0xA431: "BodySerialNumber",
    0xA432: "LensSpecification",
    0xA433: "LensMake",
    0xA434: "LensModel",
    0xA435: "LensSerialNumber",
    
    # ============================================================
    # GPS IFD Tags (0x0000 - 0x001F)
    # ============================================================
    0x0000: "GPSVersionID",
    0x0001: "GPSLatitudeRef",
    0x0002: "GPSLatitude",
    0x0003: "GPSLongitudeRef",
    0x0004: "GPSLongitude",
    0x0005: "GPSAltitudeRef",
    0x0006: "GPSAltitude",
    0x0007: "GPSTimeStamp",
    0x0008: "GPSSatellites",
    0x0009: "GPSStatus",
    0x000A: "GPSMeasureMode",
    0x000B: "GPSDOP",
    0x000C: "GPSSpeedRef",
    0x000D: "GPSSpeed",
    0x000E: "GPSTrackRef",
    0x000F: "GPSTrack",
    0x0010: "GPSImgDirectionRef",
    0x0011: "GPSImgDirection",
    0x0012: "GPSMapDatum",
    0x0013: "GPSDestLatitudeRef",
    0x0014: "GPSDestLatitude",
    0x0015: "GPSDestLongitudeRef",
    0x0016: "GPSDestLongitude",
    0x0017: "GPSDestBearingRef",
    0x0018: "GPSDestBearing",
    0x0019: "GPSDestDistanceRef",
    0x001A: "GPSDestDistance",
    0x001B: "GPSProcessingMethod",
    0x001C: "GPSAreaInformation",
    0x001D: "GPSDateStamp",
    0x001E: "GPSDifferential",
    0x001F: "GPSHPositioningError",
    
    # ============================================================
    # Interoperability IFD Tags
    # ============================================================
    0x0001: "InteroperabilityIndex",
    0x0002: "InteroperabilityVersion",
    0x1000: "RelatedImageFileFormat",
    0x1001: "RelatedImageWidth",
    0x1002: "RelatedImageLength",
    
    # ============================================================
    # IFD1 (Thumbnail) Tags
    # ============================================================
    # Uses same tags as IFD0, but in thumbnail IFD
    
    # ============================================================
    # Additional Common Tags
    # ============================================================
    0x0100: "ImageWidth",
    0x0101: "ImageLength",
    0x0102: "BitsPerSample",
    0x0103: "Compression",
    0x0106: "PhotometricInterpretation",
    0x0111: "StripOffsets",
    0x0115: "SamplesPerPixel",
    0x0116: "RowsPerStrip",
    0x0117: "StripByteCounts",
    0x011A: "XResolution",
    0x011B: "YResolution",
    0x011C: "PlanarConfiguration",
    0x0128: "ResolutionUnit",
}

# Utility to merge tag definitions without overriding existing tags
def _merge_tag_definitions(source: dict):
    """
    Merge additional tag definitions without overwriting existing standard tags.
    """
    for tag_id, tag_name in source.items():
        if tag_id not in EXIF_TAG_NAMES:
            EXIF_TAG_NAMES[tag_id] = tag_name

# Import extended tag definitions
try:
    from dnexif.exif_tags_extended import EXTENDED_EXIF_TAG_NAMES
except ImportError:
    EXTENDED_EXIF_TAG_NAMES = {}
_merge_tag_definitions(EXTENDED_EXIF_TAG_NAMES)

# Import manufacturer-specific tag definitions
try:
    from dnexif.exif_tags_manufacturer import MANUFACTURER_EXIF_TAGS
    # Merge manufacturer tags but preserve existing standard definitions
    _merge_tag_definitions(MANUFACTURER_EXIF_TAGS)
except ImportError:
    # Manufacturer tags not available, use base tags only
    pass

# Import advanced tag definitions
try:
    from dnexif.exif_tags_advanced import ADVANCED_EXIF_TAG_NAMES
    _merge_tag_definitions(ADVANCED_EXIF_TAG_NAMES)
except ImportError:
    # Advanced tags not available, use base tags only
    pass

# Import complete tag definitions
try:
    from dnexif.exif_tags_complete import COMPLETE_EXIF_TAG_NAMES
    _merge_tag_definitions(COMPLETE_EXIF_TAG_NAMES)
except ImportError:
    # Complete tags not available, use base tags only
    pass

# Import final tag definitions
try:
    from dnexif.exif_tags_final import FINAL_EXIF_TAG_NAMES
    _merge_tag_definitions(FINAL_EXIF_TAG_NAMES)
except ImportError:
    # Final tags not available, use base tags only
    pass

# Merge EXIF 3.0 tags
try:
    from dnexif.exif_tags_3_0 import EXIF_3_0_TAG_NAMES
    _merge_tag_definitions(EXIF_3_0_TAG_NAMES)
except ImportError:
    # EXIF 3.0 tags not available, use base tags only
    pass

# Note: This is a significant expansion but still needs more tags.
# standard format supports 25,000+ tags including many manufacturer-specific tags.
# This will be expanded further in subsequent updates.

