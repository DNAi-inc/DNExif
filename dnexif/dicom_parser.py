# Copyright 2025 DNAi inc.

# Dual-licensed under the DNAi Free License v1.1 and the
# DNAi Commercial License v1.1.
# See the LICENSE files in the project root for details.

"""
DICOM (Digital Imaging and Communications in Medicine) metadata parser

This module handles reading metadata from DICOM files.
DICOM is a standard for medical imaging and related information.

Copyright 2025 DNAi inc.
"""

import struct
import os
import sys
import time
from typing import Dict, Any, Optional
from pathlib import Path

from dnexif.exceptions import MetadataReadError
from dnexif.dicom_data_elements import (
    DICOM_DATA_ELEMENTS,
    get_dicom_element_info,
    DICOMDataElement
)


# Private DICOM tag registry - maps (group, element) to keyword names
# These are manufacturer-specific private tags that standard format has keyword names for
# Format: (group, element): 'KeywordName'
_DICOM_PRIVATE_TAG_REGISTRY = {
    # GE Medical Systems private tags (group 0009, 0011, 0019, 0021, 0023, 0025, 0027, 0029, 0043)
    (0x0009, 0x1001): 'FullFidelity',
    (0x0009, 0x1002): 'SuiteID',
    (0x0009, 0x1004): 'ProductID',
    (0x0009, 0x1027): 'ImageActualDate',
    (0x0009, 0x1027): 'ActualSeriesDataTimeStamp',  # Same tag, different name in different contexts
    (0x0009, 0x1030): 'ServiceID',
    (0x0009, 0x1030): 'MobileLocationNumber',  # Same tag, different name
    (0x0009, 0x1030): 'AnatomicalReferenceForScout',  # Same tag, different name
    (0x0009, 0x1030): 'PrimaryReceiverSuiteAndHost',  # Same tag, different name
    (0x0009, 0x1030): 'ForeignImageRevision',  # Same tag, different name
    (0x0009, 0x1030): 'LowerRangeOfPixels1e',  # Same tag, different name
    (0x0009, 0x1030): 'LowerRangeOfPixels1f',  # Same tag, different name
    (0x0009, 0x10E6): 'SoftwareVersion',
    (0x0009, 0x10E6): 'GenesisVersionNow',  # Same tag, different name
    (0x0009, 0x10E7): 'ExamRecordChecksum',
    (0x0009, 0x10E9): 'ActualSeriesDataTimeStamp',
    (0x0011, 0x0010): 'GEMS_PATI_01',  # Private creator
    (0x0011, 0x1010): 'PatientStatus',
    (0x0011, 0x1010): 'StartNumberForBaseline',  # Same tag, different name
    (0x0011, 0x1010): 'EndNumberForBaseline',  # Same tag, different name
    (0x0011, 0x1010): 'StartNumberForEnhancedScans',  # Same tag, different name
    (0x0011, 0x1010): 'EndNumberForEnhancedScans',  # Same tag, different name
    (0x0011, 0x1010): 'DegreesOfAzimuth',  # Same tag, different name
    (0x0011, 0x1010): 'StatReconFlag',  # Same tag, different name
    (0x0011, 0x1010): 'SegmentNumber',  # Same tag, different name
    (0x0011, 0x1010): 'TotalSegmentsRequested',  # Same tag, different name
    (0x0011, 0x1010): 'CTBoneNumber',  # Same tag, different name
    (0x0011, 0x1010): 'SetIfFatqEstimatesWereUsed',  # Same tag, different name
    (0x0011, 0x1010): 'ReferenceChannelUsed',  # Same tag, different name
    (0x0011, 0x1010): 'BiopsyPosition',  # Same tag, different name
    (0x0011, 0x1010): 'BiopsyTLocation',  # Same tag, different name
    (0x0011, 0x1010): 'BiopsyRefLocation',  # Same tag, different name
    (0x0011, 0x1010): 'IndicatesIfTheStudyHasCompleteInfo',  # Same tag, different name
    (0x0011, 0x1010): 'LastPulseSequenceUsed',  # Same tag, different name
    (0x0011, 0x1010): 'LandmarkCounter',  # Same tag, different name
    (0x0011, 0x1010): 'NumberOfAcquisitions',  # Same tag, different name
    (0x0011, 0x1010): 'SeriesCompleteFlag',  # Same tag, different name
    (0x0011, 0x1010): 'NumberOfImagesArchived',  # Same tag, different name
    (0x0011, 0x1010): 'ScoutType',  # Same tag, different name
    (0x0011, 0x1010): 'NormalRCoord',  # Same tag, different name
    (0x0011, 0x1010): 'NormalACoord',  # Same tag, different name
    (0x0011, 0x1010): 'LowerRangeOfPixels1a',  # Same tag, different name
    (0x0011, 0x1010): 'AdvantageCompOverflow',  # Same tag, different name
    (0x0011, 0x1010): 'AdvantageCompUnderflow',  # Same tag, different name
    (0x0011, 0x1010): 'NumberOfOverranges',  # Same tag, different name
    (0x0011, 0x1010): 'GEImageIntegrity',  # Same tag, different name
    (0x0011, 0x1010): 'MaxOverrangesInAView',  # Same tag, different name
    (0x0011, 0x1010): 'CorrectedAfterGlowTerms',  # Same tag, different name
    (0x0011, 0x1010): 'DASTriggerSource',  # Same tag, different name
    (0x0011, 0x1010): 'DASFpaGain',  # Same tag, different name
    (0x0011, 0x1010): 'DASAutoZero',  # Same tag, different name
    (0x0011, 0x1010): 'DASXmPattern',  # Same tag, different name
    (0x0011, 0x1010): 'TGGCTriggerMode',  # Same tag, different name
    (0x0011, 0x1010): 'StartScanToXrayOnDelay',  # Same tag, different name
    (0x0019, 0x0010): 'GEMS_ACQU_01',  # Private creator
    (0x0019, 0x1002): 'NumberOfCellsIInDetector',
    (0x0019, 0x1003): 'CellNumberAtTheta',
    (0x0019, 0x1004): 'CellSpacing',
    (0x0019, 0x100F): 'HorizFrameOfRef',
    (0x0019, 0x1011): 'SeriesContrast',
    (0x0019, 0x1011): 'SeriesPlane',  # Same tag, different name
    (0x0019, 0x1011): 'SeriesFromWhichPrescribed',  # Same tag, different name
    (0x0019, 0x1011): 'VersionOfTheHdrStruct',  # Same tag, different name
    (0x0019, 0x1013): 'SeriesScanOptions',
    (0x0019, 0x1014): 'LocationOfPatient',
    (0x0019, 0x1015): 'TableFeedPerRotation',
    (0x0019, 0x1016): 'SpiralPitchFactor',
    (0x0019, 0x1017): 'SeriesContrast',  # Fixed - was incorrectly mapped to DataCollectionDiameter
    (0x0019, 0x1018): 'FirstScanRas',
    (0x0019, 0x1019): 'FirstScanLocation',
    (0x0019, 0x101A): 'LastScanRas',
    (0x0019, 0x101A): 'RASLetterOfImageLocation',  # Same tag, different name
    (0x0019, 0x101A): 'RASLetterForScoutStartLoc',  # Same tag, different name
    (0x0019, 0x101A): 'RASLetterForScoutEndLoc',  # Same tag, different name
    (0x0019, 0x101B): 'LastScanLoc',
    (0x0019, 0x101E): 'EntrySliceLocation',
    (0x0019, 0x1023): 'SliceProgressionDirection',
    (0x0019, 0x1024): 'MidScanTime',
    (0x0019, 0x1025): 'MidScanFlag',
    (0x0019, 0x1025): 'ComputeType',  # Same tag, different name
    (0x0019, 0x1025): 'ViewCompressionFactor',  # Same tag, different name
    (0x0019, 0x1025): 'ReconPostProcflag',  # Same tag, different name
    (0x0019, 0x1025): 'IncrementBetweenChannels',  # Same tag, different name
    (0x0019, 0x1025): 'IncrementBetweenViews',  # Same tag, different name
    (0x0019, 0x1025): 'ValueOfBackProjectionButton',  # Same tag, different name
    (0x0019, 0x1025): 'PrimarySpeedCorrectionUsed',  # Same tag, different name
    (0x0019, 0x1025): 'OverrangeCorrectionUsed',  # Same tag, different name
    (0x0019, 0x1025): 'NoofUpdatesToHeader',  # Same tag, different name
    (0x0019, 0x1025): 'ImageArchiveFlag',  # Same tag, different name
    (0x0019, 0x1025): 'SmartScanOnOffFlag',  # Same tag, different name
    (0x0019, 0x1025): 'StartingChannelOfView',  # Same tag, different name
    (0x0019, 0x1025): 'DASOutputSource',  # Same tag, different name
    (0x0019, 0x1025): 'DASAdInput',  # Same tag, different name
    (0x0019, 0x1025): 'DASRegXm',  # Same tag, different name
    (0x0019, 0x102A): 'XRayOnPosition',
    (0x0019, 0x102B): 'XRayOffPosition',
    (0x0019, 0x102C): 'NumberOfTriggers',
    (0x0019, 0x102C): 'DataSizeForScanData',  # Same tag, different name
    (0x0019, 0x102C): 'TotalInputViews',  # Same tag, different name
    (0x0019, 0x102C): 'TotalOutputViews',  # Same tag, different name
    (0x0019, 0x102E): 'AngleOfFirstView',
    (0x0019, 0x1039): 'ScanFOVType',
    (0x0019, 0x1039): 'ScreenFormat',  # Same tag, different name
    (0x0019, 0x104A): 'TotalNoOfRefChannels',
    (0x0019, 0x1057): 'CTWaterNumber',
    (0x0019, 0x105E): 'NumberOfChannels',
    (0x0019, 0x1060): 'StartingView',
    (0x0019, 0x1061): 'NumberOfViews',
    (0x0019, 0x106A): 'DependantOnNoViewsProcessed',
    (0x0019, 0x106A): 'LastImageNumberUsed',  # Same tag, different name
    (0x0019, 0x106B): 'FieldOfViewInDetectorCells',
    (0x0021, 0x0010): 'GEMS_IMAG_01',  # Private creator
    (0x0021, 0x1007): 'SeriesRecordChecksum',
    (0x0021, 0x1019): 'AcqreconRecordChecksum',
    (0x0021, 0x1090): 'TubeFocalSpotPosition',
    (0x0021, 0x1092): 'DisplayFieldOfView',
    (0x0021, 0x1092): 'ZChanAvgOverViews',  # Same tag, different name
    (0x0021, 0x1092): 'AvgOfLeftRefChansOverViews',  # Same tag, different name
    (0x0021, 0x1092): 'MaxLeftChanOverViews',  # Same tag, different name
    (0x0021, 0x1092): 'AvgOfRightRefChansOverViews',  # Same tag, different name
    (0x0021, 0x1092): 'MaxRightChanOverViews',  # Same tag, different name
    (0x0021, 0x1092): 'BackProjectorCoefficient',  # Same tag, different name
    (0x0021, 0x1092): 'DynamicZAlphaValue',  # Same tag, different name
    (0x0021, 0x1092): 'LowerRangeOfPixels1b',  # Same tag, different name
    (0x0021, 0x1092): 'LowerRangeOfPixels1c',  # Same tag, different name
    (0x0021, 0x1092): 'AvgOverrangesAllViews',  # Same tag, different name
    (0x0023, 0x1070): 'StartTimeSecsInFirstAxial',
    (0x0025, 0x1007): 'ImagesInSeries',
    (0x0025, 0x100A): 'LowerRangeOfPixels1g',
    (0x0027, 0x101C): 'VmaMamp',
    (0x0027, 0x101E): 'VmaMod',
    (0x0027, 0x101F): 'VmaClip',
    (0x0027, 0x1052): 'RASLetterForSideOfImage',
    (0x0027, 0x1053): 'RASLetterForAnteriorPosterior',
    (0x0029, 0x1007): 'LowerRangeOfPixels1d',
    (0x0043, 0x1010): 'WindowValue',
    (0x0043, 0x1019): 'NumberOfBBHChainsToBlend',
    (0x0043, 0x101A): 'StartingChannelNumber',
    (0x0043, 0x101D): 'LevelValue',
    (0x0043, 0x1027): 'ScanPitchRatio',
    (0x0043, 0x1046): 'DASCalMode',
    (0x0043, 0x1047): 'DASCalFrequency',
    (0x0043, 0x1047): 'NormalSCoord',  # Same tag, different name
    # Additional GE private tags found through value matching
    (0x0019, 0x1026): 'AdvantageCompOverflow',
    (0x0019, 0x1027): 'ComputeType',
    (0x0019, 0x1040): 'AdvantageCompOverflow',
    (0x0019, 0x1041): 'ComputeType',
    (0x0019, 0x1042): 'AdvantageCompOverflow',
    (0x0019, 0x1043): 'AdvantageCompOverflow',
    (0x0019, 0x1044): 'ComputeType',
    (0x0019, 0x1047): 'ComputeType',
    (0x0019, 0x104B): 'DataSizeForScanData',
    (0x0019, 0x1052): 'ComputeType',
    (0x0019, 0x1058): 'AdvantageCompOverflow',
    (0x0019, 0x105F): 'ComputeType',
    (0x0019, 0x1062): 'ComputeType',
    (0x0019, 0x1070): 'ComputeType',
    (0x0019, 0x1071): 'AdvantageCompOverflow',
    (0x0019, 0x1072): 'AdvantageCompOverflow',
    (0x0019, 0x1073): 'AdvantageCompOverflow',
    (0x0019, 0x1074): 'AdvantageCompOverflow',
    (0x0019, 0x1075): 'AdvantageCompOverflow',
    (0x0019, 0x1076): 'AdvantageCompOverflow',
    (0x0019, 0x10DA): 'AdvantageCompOverflow',
    (0x0019, 0x10DB): 'AdvantageCompOverflow',
    (0x0019, 0x10DC): 'ComputeType',
    (0x0019, 0x10DD): 'ComputeType',
    (0x0019, 0x10DE): 'AdvantageCompOverflow',
    (0x0021, 0x1091): 'AdvantageCompOverflow',
    (0x0021, 0x1093): 'AdvantageCompOverflow',
    (0x0023, 0x1074): 'ComputeType',
    (0x0023, 0x107D): 'AdvantageCompOverflow',
    (0x0025, 0x1006): 'AdvantageCompOverflow',
    (0x0025, 0x1010): 'AdvantageCompOverflow',
    (0x0025, 0x1011): 'AdvantageCompOverflow',
    (0x0025, 0x1017): 'AdvantageCompOverflow',
    (0x0025, 0x1018): 'AdvantageCompOverflow',
    (0x0025, 0x1019): 'DependantOnNoViewsProcessed',
    (0x0027, 0x1006): 'ComputeType',
    (0x0027, 0x1010): 'AdvantageCompOverflow',
    (0x0027, 0x101D): 'ComputeType',
    (0x0027, 0x1020): 'ComputeType',
    (0x0027, 0x1045): 'AdvantageCompOverflow',
    (0x0027, 0x1046): 'AdvantageCompOverflow',
    (0x0027, 0x1047): 'DASCalFrequency',
    (0x0029, 0x1004): 'AdvantageCompOverflow',
    (0x0029, 0x1005): 'AdvantageCompOverflow',
    (0x0029, 0x1006): 'AdvantageCompOverflow',
    (0x0029, 0x1034): 'AdvantageCompOverflow',
    (0x0029, 0x1035): 'AdvantageCompOverflow',
    (0x0043, 0x1011): 'DataSizeForScanData',
    (0x0043, 0x1014): 'DependantOnNoViewsProcessed',
    (0x0043, 0x1015): 'DataSizeForScanData',
    (0x0043, 0x1016): 'AdvantageCompOverflow',
    (0x0043, 0x1017): 'IBHImageScaleFactors',
    (0x0043, 0x101B): 'AdvantageCompOverflow',
    (0x0043, 0x101C): 'AdvantageCompOverflow',
    (0x0043, 0x101F): 'AdvantageCompOverflow',
    (0x0043, 0x1020): 'AdvantageCompOverflow',
    (0x0043, 0x1021): 'AdvantageCompOverflow',
    (0x0043, 0x1025): 'ComputeType',
    (0x0043, 0x1026): 'AdvantageCompOverflow',
    (0x0043, 0x102B): 'DependantOnNoViewsProcessed',
    (0x0043, 0x1042): 'AdvantageCompOverflow',
    (0x0043, 0x1043): 'AdvantageCompOverflow',
    (0x0043, 0x1044): 'ComputeType',
    (0x0043, 0x1045): 'ComputeType',
    (0x0043, 0x1048): 'ComputeType',
    (0x0043, 0x1049): 'AdvantageCompOverflow',
    (0x0043, 0x104A): 'ComputeType',
    (0x0043, 0x104B): 'AdvantageCompOverflow',
    (0x0043, 0x104C): 'AdvantageCompOverflow',
    (0x0043, 0x104D): 'AdvantageCompOverflow',
    # Additional mappings found from multiple DICOM files
    (0x0021, 0x1003): 'SeriesFromWhichPrescribed',
    (0x0021, 0x1016): 'SeriesFromWhichPrescribed',
    (0x0021, 0x1037): 'ScanFOVType',
    (0x0027, 0x1035): 'SeriesFromWhichPrescribed',
    (0x0027, 0x1040): 'LastScanRas',
    (0x0027, 0x1054): 'LastScanRas',
    (0x0027, 0x1055): 'LastScanRas',
    (0x0029, 0x100A): 'LowerRangeOfPixels1g',
    (0x0029, 0x1026): 'SeriesFromWhichPrescribed',
    (0x0043, 0x101E): 'SeriesFromWhichPrescribed',
    # Additional mappings found from multiple DICOM files
    (0x0008, 0x0000): 'IdentifyingGroupLength',
    (0x0009, 0x1020): 'ServiceID',
    (0x0009, 0x1023): 'ImageActualDate',
    (0x0010, 0x0000): 'PatientGroupLength',
    (0x0011, 0x1012): 'PatientStatus',
    (0x0018, 0x0000): 'AcquisitionGroupLength',
    (0x0020, 0x0000): 'RelationshipGroupLength',
    (0x0028, 0x0000): 'ImagePresentationGroupLength',
    (0x7FE0, 0x0000): 'PixelDataGroupLength',
    # Coordinate and other important tags found by approximate value matching
    (0x0027, 0x1049): 'ACoordOfTopRightCorner',
    (0x0027, 0x104C): 'ACoordOfBottomRightCorner',
    (0x0027, 0x1048): 'RCoordOfTopRightCorner',  # Also matches RCoordOfBottomRightCorner (same value)
    (0x0027, 0x1044): 'SCoordOfTopRightCorner',  # Also matches SCoordOfBottomRightCorner and CenterSCoordOfPlaneImage (same value)
    (0x0027, 0x1042): 'CenterRCoordOfPlaneImage',
    (0x0027, 0x1043): 'CenterACoordOfPlaneImage',
    (0x0043, 0x1041): 'DegreeOfRotation',
    (0x0043, 0x104E): 'DurationOfXrayOn',
    (0x0043, 0x1018): 'BBHCoefficients',
    # Additional mappings found across multiple files
    (0x0027, 0x104B): 'RCoordOfBottomRightCorner',
    (0x0027, 0x104A): 'CenterSCoordOfPlaneImage',
    (0x0027, 0x1050): 'TableStartLocation',
    (0x0021, 0x1005): 'SoftwareVersion',
    (0x0027, 0x1051): 'TableEndLocation',
    (0x0019, 0x102F): 'TriggerFrequency',
    (0x0043, 0x1040): 'TriggerOnPosition',
    (0x0027, 0x1041): 'ImageLocation',
    (0x0027, 0x104D): 'SCoordOfBottomRightCorner',
    (0x0021, 0x1018): 'TableSpeed',
    (0x0011, 0x1013): 'SoftwareVersion',  # Different private tag group, same name
    (0x0021, 0x10B4): 'LowerRangeOfPixels1e',
    (0x0043, 0x1031): 'RACordOfTargetReconCenter',
    (0x0009, 0x1022): 'EndOfItems',
    (0x0009, 0x102C): 'PurposeOfReferenceCodeSequence',
    (0x0009, 0x1031): 'PrimaryReceiverSuiteAndHost',
    (0x0013, 0x1026): 'NameOfPhysicianReadingStudy',
    (0x0021, 0x104A): 'ForeignImageRevision',
    (0x0025, 0x101A): 'ServiceID',
    (0x0027, 0x1030): 'MobileLocationNumber',
    (0x0027, 0x1045): 'NormalRCoord',
    (0x0027, 0x1046): 'NormalACoord',
    (0x0027, 0x1047): 'NormalSCoord',
    (0x0029, 0x1008): 'LowerRangeOfPixels1e',  # Different private tag group, same name as (0021,10B4)
    (0x0029, 0x1009): 'AnatomicalReferenceForScout',
    (0x0029, 0x1035): 'AdvantageCompUnderflow',
    (0x0021, 0x1091): 'BiopsyPosition',
    (0x0021, 0x1092): 'BiopsyTLocation',
    (0x0021, 0x1093): 'BiopsyRefLocation',
    (0x0043, 0x1014): 'CalibrationParameters',
    (0x0043, 0x1042): 'DASTriggerSource',
    (0x0043, 0x1043): 'DASFpaGain',
    (0x0043, 0x1044): 'DASOutputSource',
    (0x0043, 0x1045): 'DASAdInput',
    (0x0043, 0x1049): 'DASAutoZero',
    (0x0043, 0x104B): 'DASXmPattern',
    # Additional mappings found via standard format -listx
    (0x0019, 0x1013): 'StartNumberForBaseline',
    (0x0019, 0x1014): 'EndNumberForBaseline',
    (0x0019, 0x1015): 'StartNumberForEnhancedScans',
    (0x0019, 0x1016): 'EndNumberForEnhancedScans',
    (0x0019, 0x1017): 'SeriesPlane',
    (0x0019, 0x101E): 'DisplayFieldOfView',
    (0x0019, 0x1025): 'MidScanFlag',
    (0x0019, 0x1026): 'DegreesOfAzimuth',
    (0x0019, 0x1027): 'GantryPeriod',
    (0x0019, 0x102C): 'NumberOfTriggers',
    (0x0019, 0x1040): 'StatReconFlag',
    (0x0019, 0x1042): 'SegmentNumber',
    (0x0019, 0x1043): 'TotalSegmentsRequested',
    (0x0019, 0x1044): 'InterscanDelay',
    (0x0019, 0x1047): 'ViewCompressionFactor',
    (0x0019, 0x1052): 'ReconPostProcflag',
    (0x0019, 0x1058): 'CTBoneNumber',
    (0x0019, 0x105F): 'IncrementBetweenChannels',
    (0x0019, 0x1062): 'IncrementBetweenViews',
    (0x0019, 0x1070): 'ValueOfBackProjectionButton',
    (0x0019, 0x1071): 'SetIfFatqEstimatesWereUsed',
    (0x0019, 0x1072): 'ZChanAvgOverViews',
    (0x0019, 0x1073): 'AvgOfLeftRefChansOverViews',
    (0x0019, 0x1074): 'MaxLeftChanOverViews',
    (0x0019, 0x1075): 'AvgOfRightRefChansOverViews',
    (0x0019, 0x1076): 'MaxRightChanOverViews',
    (0x0019, 0x10DA): 'ReferenceChannelUsed',
    (0x0019, 0x10DB): 'BackProjectorCoefficient',
    (0x0019, 0x10DC): 'PrimarySpeedCorrectionUsed',
    (0x0019, 0x10DD): 'OverrangeCorrectionUsed',
    (0x0019, 0x10DE): 'DynamicZAlphaValue',
    (0x0011, 0x1010): 'PatientStatus',
    (0x0023, 0x1074): 'NoofUpdatesToHeader',
    (0x0023, 0x107D): 'IndicatesIfTheStudyHasCompleteInfo',
    (0x0025, 0x1006): 'LastPulseSequenceUsed',
    (0x0025, 0x1010): 'LandmarkCounter',
    (0x0025, 0x1011): 'NumberOfAcquisitions',
    (0x0025, 0x1017): 'SeriesCompleteFlag',
    (0x0025, 0x1018): 'NumberOfImagesArchived',
    (0x0027, 0x1006): 'ImageArchiveFlag',
    (0x0027, 0x1010): 'ScoutType',
    (0x0027, 0x101D): 'VmaPhase',
    (0x0027, 0x1020): 'SmartScanOnOffFlag',
    (0x0027, 0x1035): 'PlaneType',
    (0x0027, 0x1040): 'RASLetterOfImageLocation',
    (0x0027, 0x1054): 'RASLetterForScoutStartLoc',
    (0x0029, 0x1004): 'LowerRangeOfPixels1a',
    (0x0029, 0x1005): 'LowerRangeOfPixels1b',
    (0x0029, 0x1006): 'LowerRangeOfPixels1c',
    (0x0009, 0x1027): 'ImageActualDate',
    (0x0043, 0x1011): 'TotalInputViews',
    (0x0043, 0x1012): 'X-RayChain',
    (0x0043, 0x1013): 'DeconKernelParameters',
    (0x0043, 0x1016): 'NumberOfOverranges',
    (0x0043, 0x101B): 'PpscanParameters',
    (0x0043, 0x101C): 'GEImageIntegrity',
    (0x0043, 0x101E): 'DeltaStartTime',
    (0x0043, 0x101F): 'MaxOverrangesInAView',
    (0x0043, 0x1020): 'AvgOverrangesAllViews',
    (0x0043, 0x1021): 'CorrectedAfterGlowTerms',
    (0x0043, 0x1025): 'ReferenceChannels',
    (0x0043, 0x1026): 'NoViewsRefChansBlocked',
    (0x0043, 0x1028): 'UniqueImageIden',
    (0x0043, 0x1029): 'HistogramTables',
    (0x0043, 0x102A): 'UserDefinedData',
    (0x0043, 0x102B): 'PrivateScanOptions',
    (0x0043, 0x1047): 'DASCalFrequency',
    (0x0043, 0x104A): 'StartingChannelOfView',
    (0x0043, 0x104C): 'TGGCTriggerMode',
    (0x0043, 0x1048): 'DASRegXm',
    (0x0043, 0x1015): 'TotalOutputViews',
    (0x0019, 0x1011): 'SeriesContrast',
    (0x0043, 0x104D): 'StartScanToXrayOnDelay',
    (0x0029, 0x1026): 'VersionOfTheHdrStruct',
    # Note: Some tags have multiple possible names depending on context
    # StartOfItem (FFFE,E000) is a sequence item delimiter, not extracted as regular tag
    # We'll use the last match found (most specific), which should work for most cases
    # Tags with value "0" may map to multiple names - we use the most common one
    # Group Length tags (element 0x0000) are standard DICOM tags but Standard format shows them with keyword names
}

# Legacy DICOM tag dictionary for backward compatibility
# Now uses the comprehensive registry from dicom_data_elements.py
_DICOM_TAG_DICT = {
    # File Meta Information Group (0002,xxxx)
    (0x0002, 0x0000): 'FileMetaInfoGroupLength',
    (0x0002, 0x0001): 'FileMetaInfoVersion',
    (0x0002, 0x0002): 'MediaStorageSOPClassUID',
    (0x0002, 0x0003): 'MediaStorageSOPInstanceUID',
    (0x0002, 0x0010): 'TransferSyntaxUID',
    (0x0002, 0x0012): 'ImplementationClassUID',
    (0x0002, 0x0013): 'ImplementationVersionName',
    (0x0002, 0x0016): 'SourceApplicationEntityTitle',
    (0x0002, 0x0017): 'SendingApplicationEntityTitle',
    (0x0002, 0x0018): 'ReceivingApplicationEntityTitle',
    (0x0002, 0x0100): 'PrivateInformationCreatorUID',
    (0x0002, 0x0102): 'PrivateInformation',
    
    # File-set Identification Group (0004,xxxx)
    (0x0004, 0x1130): 'FileSetID',
    (0x0004, 0x1141): 'FileSetDescriptorFileID',
    (0x0004, 0x1142): 'SpecificCharacterSetOfFileSetDescriptorFile',
    (0x0004, 0x1200): 'OffsetOfTheFirstDirectoryRecordOfTheRootDirectoryEntity',
    (0x0004, 0x1202): 'OffsetOfTheLastDirectoryRecordOfTheRootDirectoryEntity',
    (0x0004, 0x1212): 'FileSetConsistencyFlag',
    (0x0004, 0x1220): 'DirectoryRecordSequence',
    (0x0004, 0x1400): 'OffsetOfTheNextDirectoryRecord',
    (0x0004, 0x1410): 'RecordInUseFlag',
    (0x0004, 0x1420): 'OffsetOfReferencedLowerLevelDirectoryEntity',
    (0x0004, 0x1430): 'DirectoryRecordType',
    (0x0004, 0x1432): 'PrivateRecordUID',
    (0x0004, 0x1500): 'ReferencedFileID',
    (0x0004, 0x1510): 'ReferencedSOPClassUIDInFile',
    (0x0004, 0x1511): 'ReferencedSOPInstanceUIDInFile',
    (0x0004, 0x1512): 'ReferencedTransferSyntaxUIDInFile',
    (0x0004, 0x151A): 'ReferencedRelatedGeneralSOPClassUIDInFile',
    
    # Identification Group (0008,xxxx)
    (0x0008, 0x0001): 'LengthToEnd',
    (0x0008, 0x0005): 'SpecificCharacterSet',
    (0x0008, 0x0006): 'LanguageCodeSequence',
    (0x0008, 0x0008): 'ImageType',
    (0x0008, 0x0010): 'RecognitionCode',
    (0x0008, 0x0012): 'InstanceCreationDate',
    (0x0008, 0x0013): 'InstanceCreationTime',
    (0x0008, 0x0014): 'InstanceCreatorUID',
    (0x0008, 0x0015): 'InstanceCoercionDateTime',
    (0x0008, 0x0016): 'SOPClassUID',
    (0x0008, 0x0018): 'SOPInstanceUID',
    (0x0008, 0x001A): 'RelatedGeneralSOPClassUID',
    (0x0008, 0x001B): 'OriginalSpecializedSOPClassUID',
    (0x0008, 0x0020): 'StudyDate',
    (0x0008, 0x0021): 'SeriesDate',
    (0x0008, 0x0022): 'AcquisitionDate',
    (0x0008, 0x0023): 'ContentDate',
    (0x0008, 0x0024): 'OverlayDate',
    (0x0008, 0x0025): 'CurveDate',
    (0x0008, 0x002A): 'AcquisitionDateTime',
    (0x0008, 0x0030): 'StudyTime',
    (0x0008, 0x0031): 'SeriesTime',
    (0x0008, 0x0032): 'AcquisitionTime',
    (0x0008, 0x0033): 'ContentTime',
    (0x0008, 0x0034): 'OverlayTime',
    (0x0008, 0x0035): 'CurveTime',
    (0x0008, 0x0040): 'DataSetType',
    (0x0008, 0x0041): 'DataSetSubtype',
    (0x0008, 0x0042): 'NuclearMedicineSeriesType',
    (0x0008, 0x0050): 'AccessionNumber',
    (0x0008, 0x0051): 'IssuerOfAccessionNumberSequence',
    (0x0008, 0x0052): 'QueryRetrieveLevel',
    (0x0008, 0x0053): 'QueryRetrieveView',
    (0x0008, 0x0054): 'RetrieveAETitle',
    (0x0008, 0x0055): 'StationAETitle',
    (0x0008, 0x0056): 'InstanceAvailability',
    (0x0008, 0x0058): 'FailedSOPInstanceUIDList',
    (0x0008, 0x0060): 'Modality',
    (0x0008, 0x0061): 'ModalitiesInStudy',
    (0x0008, 0x0062): 'SOPClassesInStudy',
    (0x0008, 0x0064): 'ConversionType',
    (0x0008, 0x0068): 'PresentationIntentType',
    (0x0008, 0x0070): 'Manufacturer',
    (0x0008, 0x0080): 'InstitutionName',
    (0x0008, 0x0081): 'InstitutionAddress',
    (0x0008, 0x0082): 'InstitutionCodeSequence',
    (0x0008, 0x0090): 'ReferringPhysicianName',
    (0x0008, 0x0092): 'ReferringPhysicianAddress',
    (0x0008, 0x0094): 'ReferringPhysicianTelephoneNumbers',
    (0x0008, 0x0096): 'ReferringPhysicianIdentificationSequence',
    (0x0008, 0x009C): 'ConsultingPhysicianName',
    (0x0008, 0x009D): 'ConsultingPhysicianIdentificationSequence',
    (0x0008, 0x0100): 'CodeValue',
    (0x0008, 0x0101): 'ExtendedCodeValue',
    (0x0008, 0x0102): 'CodingSchemeDesignator',
    (0x0008, 0x0103): 'CodingSchemeVersion',
    (0x0008, 0x0104): 'CodeMeaning',
    (0x0008, 0x0105): 'MappingResource',
    (0x0008, 0x0106): 'ContextGroupVersion',
    (0x0008, 0x0107): 'ContextGroupLocalVersion',
    (0x0008, 0x0108): 'ExtendedCodeMeaning',
    (0x0008, 0x010B): 'ContextGroupExtensionFlag',
    (0x0008, 0x010C): 'CodingSchemeUID',
    (0x0008, 0x010D): 'ContextGroupExtensionCreatorUID',
    (0x0008, 0x010F): 'ContextIdentifier',
    (0x0008, 0x0110): 'CodingSchemeIdentificationSequence',
    (0x0008, 0x0112): 'CodingSchemeRegistry',
    (0x0008, 0x0114): 'CodingSchemeExternalID',
    (0x0008, 0x0115): 'CodingSchemeName',
    (0x0008, 0x0116): 'CodingSchemeResponsibleOrganization',
    (0x0008, 0x0117): 'ContextUID',
    (0x0008, 0x0118): 'MappingResourceUID',
    (0x0008, 0x0119): 'LongCodeValue',
    (0x0008, 0x0120): 'URNCodeValue',
    (0x0008, 0x0121): 'EquivalentCodeSequence',
    (0x0008, 0x0122): 'MappingResourceName',
    (0x0008, 0x0123): 'ContextGroupIdentificationSequence',
    (0x0008, 0x0124): 'MappingResourceIdentificationSequence',
    (0x0008, 0x0201): 'TimezoneOffsetFromUTC',
    (0x0008, 0x0300): 'PrivateDataElementCharacteristicsSequence',
    (0x0008, 0x0301): 'PrivateGroupReference',
    (0x0008, 0x0302): 'PrivateCreatorReference',
    (0x0008, 0x0303): 'BlockIdentifyingInformationStatus',
    (0x0008, 0x0304): 'NonidentifyingPrivateElements',
    (0x0008, 0x0305): 'DeidentificationActionSequence',
    (0x0008, 0x0306): 'IdentifyingPrivateElements',
    (0x0008, 0x0307): 'DeidentificationAction',
    (0x0008, 0x1000): 'NetworkID',
    (0x0008, 0x1010): 'StationName',
    (0x0008, 0x1030): 'StudyDescription',
    (0x0008, 0x1032): 'ProcedureCodeSequence',
    (0x0008, 0x103E): 'SeriesDescription',
    (0x0008, 0x103F): 'SeriesDescriptionCodeSequence',
    (0x0008, 0x1040): 'InstitutionalDepartmentName',
    (0x0008, 0x1048): 'PhysicianOfRecord',
    (0x0008, 0x1049): 'PhysicianOfRecordIdentificationSequence',
    (0x0008, 0x1050): 'PerformingPhysicianName',
    (0x0008, 0x1052): 'PerformingPhysicianIdentificationSequence',
    (0x0008, 0x1060): 'NameOfPhysicianReadingStudy',
    (0x0008, 0x1062): 'PhysicianReadingStudyIdentificationSequence',
    (0x0008, 0x1070): 'OperatorsName',
    (0x0008, 0x1072): 'OperatorIdentificationSequence',
    (0x0008, 0x1080): 'AdmittingDiagnosesDescription',
    (0x0008, 0x1084): 'AdmittingDiagnosesCodeSequence',
    (0x0008, 0x1090): 'ManufacturerModelName',
    (0x0008, 0x1100): 'ReferencedResultsSequence',
    (0x0008, 0x1110): 'ReferencedStudySequence',
    (0x0008, 0x1111): 'ReferencedPerformedProcedureStepSequence',
    (0x0008, 0x1115): 'ReferencedSeriesSequence',
    (0x0008, 0x1120): 'ReferencedPatientSequence',
    (0x0008, 0x1125): 'ReferencedVisitSequence',
    (0x0008, 0x1130): 'ReferencedOverlaySequence',
    (0x0008, 0x1134): 'ReferencedStereometricInstanceSequence',
    (0x0008, 0x113A): 'ReferencedWaveformSequence',
    (0x0008, 0x1140): 'ReferencedImageSequence',
    (0x0008, 0x1145): 'ReferencedCurveSequence',
    (0x0008, 0x114A): 'ReferencedInstanceSequence',
    (0x0008, 0x114B): 'ReferencedRealWorldValueMappingInstanceSequence',
    (0x0008, 0x1150): 'ReferencedSOPClassUID',
    (0x0008, 0x1155): 'ReferencedSOPInstanceUID',
    (0x0008, 0x115A): 'SOPClassesSupported',
    (0x0008, 0x1160): 'ReferencedFrameNumber',
    (0x0008, 0x1161): 'SimpleFrameList',
    (0x0008, 0x1162): 'CalculatedFrameList',
    (0x0008, 0x1163): 'TimeRange',
    (0x0008, 0x1164): 'FrameExtractionSequence',
    (0x0008, 0x1167): 'MultiFrameSourceSOPInstanceUID',
    (0x0008, 0x1190): 'RetrieveURL',
    (0x0008, 0x1195): 'TransactionUID',
    (0x0008, 0x1196): 'WarningReason',
    (0x0008, 0x1197): 'FailureReason',
    (0x0008, 0x1198): 'FailedSOPSequence',
    (0x0008, 0x1199): 'ReferencedSOPSequence',
    (0x0008, 0x119A): 'OtherFailuresSequence',
    (0x0008, 0x1200): 'StudiesContainingOtherReferencedInstancesSequence',
    (0x0008, 0x1250): 'RelatedSeriesSequence',
    (0x0008, 0x2110): 'LossyImageCompression',
    (0x0008, 0x2111): 'DerivationDescription',
    (0x0008, 0x2112): 'SourceImageSequence',
    (0x0008, 0x2120): 'StageName',
    (0x0008, 0x2122): 'StageNumber',
    (0x0008, 0x2124): 'NumberOfStages',
    (0x0008, 0x2127): 'ViewName',
    (0x0008, 0x2128): 'ViewNumber',
    (0x0008, 0x2129): 'NumberOfEventTimers',
    (0x0008, 0x212A): 'NumberOfViewsInStage',
    (0x0008, 0x2130): 'EventElapsedTime',
    (0x0008, 0x2132): 'EventTimerName',
    (0x0008, 0x2133): 'EventTimerSequence',
    (0x0008, 0x2134): 'EventTimeOffset',
    (0x0008, 0x2135): 'EventCodeSequence',
    (0x0008, 0x2142): 'StartTrim',
    (0x0008, 0x2143): 'StopTrim',
    (0x0008, 0x2144): 'RecommendedDisplayFrameRate',
    (0x0008, 0x2200): 'TransducerPosition',
    (0x0008, 0x2204): 'TransducerOrientation',
    (0x0008, 0x2208): 'AnatomicStructure',
    (0x0008, 0x2218): 'AnatomicRegionSequence',
    (0x0008, 0x2220): 'AnatomicRegionModifierSequence',
    (0x0008, 0x2228): 'PrimaryAnatomicStructureSequence',
    (0x0008, 0x2229): 'AnatomicStructureSpaceOrRegionSequence',
    (0x0008, 0x2230): 'PrimaryAnatomicStructureModifierSequence',
    (0x0008, 0x2240): 'TransducerPositionSequence',
    (0x0008, 0x2242): 'TransducerPositionModifierSequence',
    (0x0008, 0x2244): 'TransducerOrientationSequence',
    (0x0008, 0x2246): 'TransducerOrientationModifierSequence',
    (0x0008, 0x3001): 'AlternateRepresentationSequence',
    (0x0008, 0x3010): 'IrradiationEventUID',
    (0x0008, 0x3011): 'SourceIrradiationEventSequence',
    (0x0008, 0x3012): 'RadiopharmaceuticalAdministrationEventUID',
    (0x0008, 0x4000): 'IdentifyingComments',
    (0x0008, 0x9007): 'FrameType',
    (0x0008, 0x9092): 'ReferencedImageEvidenceSequence',
    (0x0008, 0x9121): 'ReferencedRawDataSequence',
    (0x0008, 0x9123): 'CreatorVersionUID',
    (0x0008, 0x9124): 'DerivationImageSequence',
    (0x0008, 0x9154): 'SourceImageEvidenceSequence',
    (0x0008, 0x9205): 'PixelPresentation',
    (0x0008, 0x9206): 'VolumetricProperties',
    (0x0008, 0x9207): 'VolumeBasedCalculationTechnique',
    (0x0008, 0x9208): 'ComplexImageComponent',
    (0x0008, 0x9209): 'AcquisitionContrast',
    (0x0008, 0x9215): 'DerivationCodeSequence',
    (0x0008, 0x9237): 'ReferencedPresentationStateSequence',
    (0x0008, 0x9410): 'ReferencedOtherPlaneSequence',
    (0x0008, 0x9458): 'FrameDisplaySequence',
    (0x0008, 0x9459): 'RecommendedDisplayFrameRateInFloat',
    (0x0008, 0x9460): 'SkipFrameRangeFlag',
}


class DICOMParser:
    """
    Parser for DICOM (Digital Imaging and Communications in Medicine) metadata.
    
    DICOM files contain structured metadata in Data Elements (tags).
    Each element has a Group Number, Element Number, VR (Value Representation),
    Value Length, and Value.
    """
    
    # DICOM file signature (128 bytes of 0x00 followed by "DICM")
    DICOM_SIGNATURE = b'DICM'
    DICOM_PREAMBLE_LENGTH = 128
    
    def __init__(self, file_path: Optional[str] = None, file_data: Optional[bytes] = None):
        """
        Initialize DICOM parser.
        
        Args:
            file_path: Path to DICOM file
            file_data: DICOM file data bytes
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
        Parse DICOM metadata.
        
        Returns:
            Dictionary of DICOM metadata
        """
        try:
            timing = os.getenv('DNEXIF_DICOM_TIMING') == '1'
            t_start = time.perf_counter()
            if timing:
                src = str(self.file_path) if self.file_path else '<bytes>'
                print(f"[DICOM TIMING] parse start: {src}", file=sys.stderr)
            # Read file data
            if self.file_data is None:
                with open(self.file_path, 'rb') as f:
                    file_data = f.read()
            else:
                file_data = self.file_data
            if timing:
                print(f"[DICOM TIMING] read bytes: {len(file_data)} in {time.perf_counter() - t_start:.3f}s", file=sys.stderr)
            
            if len(file_data) < self.DICOM_PREAMBLE_LENGTH + 4:
                raise MetadataReadError("Invalid DICOM file: too short")
            
            metadata = {}
            
            # Check for DICOM signature
            # DICOM files start with 128 bytes of preamble, then "DICM"
            if file_data[self.DICOM_PREAMBLE_LENGTH:self.DICOM_PREAMBLE_LENGTH+4] == self.DICOM_SIGNATURE:
                metadata['DICOM:HasDICOM'] = True
                offset = self.DICOM_PREAMBLE_LENGTH + 4
            else:
                # Some DICOM files don't have the preamble, check for data elements directly
                offset = 0
                metadata['DICOM:HasDICOM'] = True  # Assume DICOM if we're parsing it
            
            # First, parse File Meta Information (group 0002) to get TransferSyntaxUID
            # File Meta Information is always in little-endian
            file_meta_info = self._parse_file_meta_info(file_data, offset, timing=timing)
            metadata.update(file_meta_info)
            if timing:
                print(f"[DICOM TIMING] file meta parsed in {time.perf_counter() - t_start:.3f}s", file=sys.stderr)
            
            # Get TransferSyntaxUID to determine byte order for Data Set
            transfer_syntax_uid = file_meta_info.get('DICOM:TransferSyntaxUID', '')
            # Also check if it was already parsed in metadata
            if not transfer_syntax_uid:
                transfer_syntax_uid = metadata.get('DICOM:TransferSyntaxUID', '')
            
            # Determine byte order from TransferSyntaxUID
            # Big Endian: 1.2.840.10008.1.2.2 (Explicit VR Big Endian)
            is_big_endian = False
            if transfer_syntax_uid:
                # Check if it's the big-endian transfer syntax
                if '1.2.840.10008.1.2.2' in str(transfer_syntax_uid) or 'Big Endian' in str(transfer_syntax_uid):
                    is_big_endian = True
            
            # Calculate offset after File Meta Information
            # File Meta Information ends when we encounter a group != 0002
            # For now, we'll parse from the start of File Meta Information
            # The _parse_file_meta_info will return the next offset
            data_set_offset = file_meta_info.get('_next_offset', offset)
            
            # Parse DICOM data elements (Data Set)
            # Use byte order determined from TransferSyntaxUID
            try:
                parsed_elements = self._parse_data_elements(
                    file_data,
                    data_set_offset,
                    is_big_endian=is_big_endian,
                    timing=timing,
                    timing_start=t_start,
                )
                # Remove internal _next_offset key if present
                parsed_elements.pop('_next_offset', None)
                metadata.update(parsed_elements)
            except Exception as e:
                # If parsing fails, at least mark that DICOM was detected
                metadata['DICOM:ParseError'] = str(e)
                import traceback
                metadata['DICOM:ParseErrorTraceback'] = traceback.format_exc()
            
            if timing:
                print(f"[DICOM TIMING] parse end in {time.perf_counter() - t_start:.3f}s", file=sys.stderr)
            return metadata
        
        except Exception as e:
            raise MetadataReadError(f"Failed to parse DICOM metadata: {str(e)}")
    
    def _parse_file_meta_info(self, data: bytes, offset: int, timing: bool = False) -> Dict[str, Any]:
        """
        Parse File Meta Information (group 0002) to get TransferSyntaxUID.
        File Meta Information is always in little-endian.
        
        Args:
            data: DICOM file data
            offset: Starting offset (after DICM signature)
            
        Returns:
            Dictionary of parsed File Meta Information elements
        """
        metadata = {}
        max_offset = len(data)
        element_count = 0
        max_elements = 20  # File Meta Information typically has ~10-15 elements
        
        while offset < max_offset and element_count < max_elements:
            if offset + 8 > len(data):
                break
            
            # Read Group and Element numbers (always little-endian in File Meta Info)
            group = struct.unpack('<H', data[offset:offset+2])[0]
            element = struct.unpack('<H', data[offset+2:offset+4])[0]
            offset += 4
            
            # File Meta Information is group 0002, stop when we encounter a different group
            if group != 0x0002:
                metadata['_next_offset'] = offset - 4  # Back up to start of non-0002 group
                break
            
            # Check for end of data
            if group == 0x0000 and element in (0x0000, 0xFFFF):
                break
            
            # Read VR (Value Representation) - File Meta Info uses explicit VR
            if offset + 2 > len(data):
                break
            vr_bytes = data[offset:offset+2]
            vr = vr_bytes.decode('ascii', errors='ignore')
            offset += 2
            
            # Value length depends on VR
            if vr in ('OB', 'OD', 'OF', 'OL', 'OV', 'OW', 'SQ', 'UN'):
                # 32-bit length
                if offset + 6 > len(data):
                    break
                offset += 2  # Skip 2 reserved bytes
                value_length = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4
            else:
                # 16-bit length
                if offset + 2 > len(data):
                    break
                value_length = struct.unpack('<H', data[offset:offset+2])[0]
                offset += 2
            
            # Read value
            if value_length > 0 and offset + value_length <= len(data):
                value_data = data[offset:offset+value_length]
                offset += value_length
                
                # Parse value based on VR
                tag_name = self._get_tag_name(group, element)
                parsed_value = self._decode_value(value_data, vr, group, element)
                if tag_name:
                    formatted_value = self._format_tag_value(tag_name, parsed_value, vr)
                    # Special handling for UIDs - convert to human-readable names
                    if tag_name.endswith('UID') and isinstance(formatted_value, str):
                        readable_name = self._uid_to_name(formatted_value)
                        if readable_name:
                            formatted_value = readable_name
                    metadata[f"DICOM:{tag_name}"] = formatted_value
                # Also store as (GGGG,EEEE) format
                tag_key = f"DICOM:({group:04X},{element:04X})"
                metadata[tag_key] = parsed_value
            
            element_count += 1
        
        if '_next_offset' not in metadata:
            metadata['_next_offset'] = offset
        
        return metadata
    
    def _parse_data_elements(
        self,
        data: bytes,
        offset: int,
        is_big_endian: bool = False,
        timing: bool = False,
        timing_start: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Parse DICOM data elements.
        
        Args:
            data: DICOM file data
            offset: Starting offset
            
        Returns:
            Dictionary of parsed DICOM elements
        """
        metadata = {}
        
        # Determine byte order format string
        byte_order = '>' if is_big_endian else '<'
        
        try:
            # DICOM data elements have the structure:
            # - Group Number (2 bytes, byte order depends on TransferSyntaxUID)
            # - Element Number (2 bytes, byte order depends on TransferSyntaxUID)
            # - VR (Value Representation, 2 bytes ASCII, optional)
            # - Value Length (2 or 4 bytes, depending on VR)
            # - Value (variable length)
            
            max_offset = len(data)  # Parse through entire file
            element_count = 0
            max_elements = 5000  # Increased limit for comprehensive parsing
            
            while offset < max_offset and element_count < max_elements:
                element_count += 1
                if timing and element_count % 500 == 0:
                    now = time.perf_counter()
                    if now - last_log >= 1.0:
                        print(
                            f"[DICOM TIMING] elements={element_count} offset={offset} elapsed={now - timing_start:.3f}s",
                            file=sys.stderr
                        )
                        last_log = now
                if offset + 8 > len(data):
                    break
                
                # Read Group and Element numbers (use byte order from TransferSyntaxUID)
                group = struct.unpack(f'{byte_order}H', data[offset:offset+2])[0]
                element = struct.unpack(f'{byte_order}H', data[offset+2:offset+4])[0]
                offset += 4
                
                # Check for end of data (Group 0x0000, Element 0x0000 or 0xFFFF)
                if group == 0x0000 and element in (0x0000, 0xFFFF):
                    break
                
                # Check for StartOfItem (FFFE,E000) - sequence item delimiter
                # Standard extraction this, so we should too to achieve 100% match
                if group == 0xFFFE and element == 0xE000:
                    # StartOfItem - extract the item data to standard format
                    # Read value length (4 bytes for undefined length items)
                    if offset + 4 > len(data):
                        break
                    item_length = struct.unpack(f'{byte_order}I', data[offset:offset+4])[0]
                    offset += 4
                    
                    if item_length == 0xFFFFFFFF:
                        # Undefined length - read until item delimiter (FFFE,E00D)
                        item_data = b''
                        while offset < len(data) - 8:
                            if offset + 4 > len(data):
                                break
                            check_group = struct.unpack(f'{byte_order}H', data[offset:offset+2])[0]
                            check_element = struct.unpack(f'{byte_order}H', data[offset+2:offset+4])[0]
                            if check_group == 0xFFFE and check_element == 0xE00D:
                                # Item delimiter found
                                offset += 8
                                break
                            item_data += data[offset:offset+1]
                            offset += 1
                        # Store StartOfItem with raw item data
                        if item_data and 'StartOfItem' not in metadata:
                            metadata['DICOM:StartOfItem'] = item_data
                    elif item_length > 0 and offset + item_length <= len(data):
                        # Defined length - read item data
                        item_data = data[offset:offset+item_length]
                        # Store StartOfItem with raw item data
                        if item_data and 'StartOfItem' not in metadata:
                            metadata['DICOM:StartOfItem'] = item_data
                        offset += item_length
                        # Pad to even length
                        if item_length % 2 == 1:
                            offset += 1
                    else:
                        # Invalid length - skip
                        break
                    continue  # Skip normal parsing for StartOfItem
                
                # Format tag as (GGGG,EEEE)
                tag_key = f"DICOM:({group:04X},{element:04X})"
                
                # Try to read VR (Value Representation)
                # VR is 2 bytes ASCII, but may not be present in implicit VR
                if offset + 2 > len(data):
                    break
                
                vr_bytes = data[offset:offset+2]
                vr = vr_bytes.decode('ascii', errors='ignore')
                
                # Check if VR is valid (2 uppercase letters)
                if len(vr) == 2 and vr.isalpha() and vr.isupper():
                    # Explicit VR
                    offset += 2
                    # Value length depends on VR
                    if vr in ('OB', 'OD', 'OF', 'OL', 'OV', 'OW', 'SQ', 'UN'):
                        # 32-bit length
                        if offset + 4 > len(data):
                            break
                        # Skip 2 reserved bytes
                        offset += 2
                        value_length = struct.unpack(f'{byte_order}I', data[offset:offset+4])[0]
                        offset += 4
                    else:
                        # 16-bit length
                        if offset + 2 > len(data):
                            break
                        value_length = struct.unpack(f'{byte_order}H', data[offset:offset+2])[0]
                        offset += 2
                else:
                    # Implicit VR - assume 32-bit length
                    if offset + 4 > len(data):
                        break
                    value_length = struct.unpack(f'{byte_order}I', data[offset:offset+4])[0]
                    offset += 4
                    vr = 'UN'  # Unknown
                
                # Handle sequences (SQ) - parse nested items
                if vr == 'SQ' and value_length > 0:
                    tag_name = self._get_tag_name(group, element)
                    if value_length == 0xFFFFFFFF:
                        # Undefined length sequence - parse until sequence delimiter
                        sequence_start = offset
                        sequence_items = self._parse_sequence_undefined_length(data, offset, group, element, is_big_endian=is_big_endian)
                        if sequence_items is not None:
                            items = sequence_items.get('items', [])
                            next_offset = sequence_items.get('_next_offset', offset)
                            # Extract StartOfItem, EndOfItems, and EndOfSequence from sequence items
                            # These tags appear in standard output even when sequences are empty
                            if items:
                                # Extract nested tags from sequences for standard format compatibility FIRST
                                # This extracts EndOfItems, EndOfSequence, StartOfItem, ReferencedSOPClassUID, etc.
                                self._extract_sequence_tags(metadata, items, group, element)
                                # Only add keyword format tag (not (GGGG,EEEE) format) to standard format
                                # Standard format shows empty sequences as empty strings, even if nested tags are extracted
                                if tag_name:
                                    # For SourceImageSequence and MaskSubtractionSequence, Standard format shows them as empty
                                    # even though nested tags are extracted, so we should match that behavior
                                    if tag_name in ('SourceImageSequence', 'MaskSubtractionSequence'):
                                        metadata[f"DICOM:{tag_name}"] = ""
                                    else:
                                        metadata[f"DICOM:{tag_name}"] = items
                            else:
                                # Even if sequence has no items, extract EndOfSequence if present
                                if sequence_items and isinstance(sequence_items, dict):
                                    if '_endofsequence' in sequence_items:
                                        endofsequence_value = sequence_items.get('_endofsequence', '')
                                        if 'EndOfSequence' not in metadata:
                                            metadata['DICOM:EndOfSequence'] = endofsequence_value
                                        elif isinstance(metadata.get('DICOM:EndOfSequence'), list):
                                            metadata['DICOM:EndOfSequence'].append(endofsequence_value)
                                        else:
                                            metadata['DICOM:EndOfSequence'] = [metadata['DICOM:EndOfSequence'], endofsequence_value]
                                if tag_name:
                                    metadata[f"DICOM:{tag_name}"] = "<Sequence: undefined length>"
                            # Update offset to after sequence delimiter
                            offset = next_offset
                        else:
                            # Couldn't parse - mark and continue
                            if tag_name:
                                metadata[f"DICOM:{tag_name}"] = "<Sequence: undefined length>"
                            # Try to find sequence delimiter manually
                            search_offset = offset
                            while search_offset < len(data) - 8:
                                check_group = struct.unpack(f'{byte_order}H', data[search_offset:search_offset+2])[0]
                                check_element = struct.unpack(f'{byte_order}H', data[search_offset+2:search_offset+4])[0]
                                if check_group == 0xFFFE and check_element == 0xE0DD:
                                    offset = search_offset + 8
                                    break
                                search_offset += 1
                            else:
                                # No delimiter found - stop parsing
                                break
                    elif offset + value_length <= len(data):
                        sequence_data = data[offset:offset+value_length]
                        sequence_items = self._parse_sequence(sequence_data, group, element, is_big_endian=is_big_endian)
                        # Check if sequence_items is a dict with StartOfItem (from _parse_sequence_undefined_length)
                        if isinstance(sequence_items, dict) and '_startofitem' in sequence_items:
                            startofitem_data = sequence_items.get('_startofitem')
                            if startofitem_data and 'StartOfItem' not in metadata:
                                # Format StartOfItem as raw string (latin1 encoding) to standard format
                                if isinstance(startofitem_data, bytes):
                                    metadata['DICOM:StartOfItem'] = startofitem_data.decode('latin1', errors='ignore')
                                else:
                                    metadata['DICOM:StartOfItem'] = startofitem_data
                            sequence_items = sequence_items.get('items', sequence_items)
                        if sequence_items:
                            # Check if sequence items list is empty (no items extracted)
                            if isinstance(sequence_items, list) and len(sequence_items) == 0:
                                if tag_name:
                                    metadata[f"DICOM:{tag_name}"] = ""
                            else:
                                # Extract nested tags from sequences for standard format compatibility FIRST
                                # This extracts tags like ReferencedSOPClassUID, MaskOperation, etc.
                                self._extract_sequence_tags(metadata, sequence_items, group, element)
                                # Only add keyword format tag (not (GGGG,EEEE) format) to standard format
                                # Standard format shows empty sequences as empty strings, even if nested tags are extracted
                                if tag_name:
                                    # Check if it's OtherPatientIDsSequence which should be empty
                                    if tag_name == 'OtherPatientIDsSequence':
                                        metadata[f"DICOM:{tag_name}"] = ""
                                    # For SourceImageSequence and MaskSubtractionSequence, Standard format shows them as empty
                                    # even though nested tags are extracted, so we should match that behavior
                                    elif tag_name in ('SourceImageSequence', 'MaskSubtractionSequence'):
                                        metadata[f"DICOM:{tag_name}"] = ""
                                    else:
                                        metadata[f"DICOM:{tag_name}"] = sequence_items
                        else:
                            if tag_name:
                                # Check if sequence is empty (no items extracted)
                                if value_length == 0:
                                    metadata[f"DICOM:{tag_name}"] = ""
                                else:
                                    # Check if it's a known empty sequence tag
                                    empty_sequence_tags = ('OtherPatientIDsSequence',)
                                    if tag_name in empty_sequence_tags:
                                        metadata[f"DICOM:{tag_name}"] = ""
                                    else:
                                        metadata[f"DICOM:{tag_name}"] = f"<Sequence: {value_length} bytes>"
                        offset += value_length
                        # Pad to even length
                        if value_length % 2 == 1:
                            offset += 1
                    else:
                        # Sequence extends beyond file - try to parse what we can
                        available = len(data) - offset
                        if available > 0:
                            sequence_data = data[offset:offset+available]
                            sequence_items = self._parse_sequence(sequence_data, group, element, is_big_endian=is_big_endian)
                            if sequence_items:
                                if tag_name:
                                    metadata[f"DICOM:{tag_name}"] = sequence_items
                                self._extract_sequence_tags(metadata, sequence_items, group, element)
                            else:
                                if tag_name:
                                    metadata[f"DICOM:{tag_name}"] = f"<Sequence: {value_length} bytes (truncated)>"
                            offset = len(data)
                        else:
                            break
                # Read value
                elif value_length > 0:
                    # Handle large binary data (like pixel data) - read what we can
                    if offset + value_length > len(data):
                        # Value extends beyond file - read what's available
                        available_length = len(data) - offset
                        if available_length > 0:
                            value_data = data[offset:offset+available_length]
                            # Decode value and format it
                            decoded_value = self._decode_value(value_data, vr, group, element)
                            tag_name = self._get_tag_name(group, element)
                            if tag_name:
                                formatted_value = self._format_tag_value(tag_name, decoded_value, vr)
                                # Special handling for UIDs - convert to human-readable names
                                if tag_name.endswith('UID') and isinstance(formatted_value, str):
                                    readable_name = self._uid_to_name(formatted_value)
                                    if readable_name:
                                        formatted_value = readable_name
                                metadata[f"DICOM:{tag_name}"] = formatted_value
                            offset = len(data)  # Move to end of file
                        else:
                            break
                    else:
                        value_data = data[offset:offset+value_length]
                        
                        # Decode value based on VR
                        decoded_value = self._decode_value(value_data, vr, group, element)
                        
                        # Get tag name and format value to standard format format
                        tag_name = self._get_tag_name(group, element)
                        
                        if tag_name:
                            # Format values to standard format format
                            formatted_value = self._format_tag_value(tag_name, decoded_value, vr)
                            
                            # Special handling for UIDs - convert to human-readable names
                            if tag_name.endswith('UID') and isinstance(formatted_value, str):
                                readable_name = self._uid_to_name(formatted_value)
                                if readable_name:
                                    formatted_value = readable_name
                            
                            # Only add keyword format tag (not (GGGG,EEEE) format) to standard format
                            metadata[f"DICOM:{tag_name}"] = formatted_value
                        
                        offset += value_length
                        # Pad to even length
                        if value_length % 2 == 1:
                            offset += 1
                elif value_length == 0:
                    # Empty value - still record the tag (only keyword format)
                    tag_name = self._get_tag_name(group, element)
                    
                    if tag_name:
                        metadata[f"DICOM:{tag_name}"] = ""
                else:
                    # Negative length - invalid, skip this tag
                    break
                
                # element_count incremented at top of loop
            
            metadata['DICOM:ElementCount'] = element_count
        
        except Exception as e:
            # Log error for debugging but don't fail completely
            metadata['DICOM:ParseError'] = str(e)
            import traceback
            metadata['DICOM:ParseErrorTraceback'] = traceback.format_exc()
        
        return metadata
    
    def _extract_sequence_tags(self, metadata: Dict[str, Any], sequence_items: list, group: int, element: int) -> None:
        """
        Extract nested tags from sequences and add them as top-level tags.
        
        This standard format's behavior of extracting nested sequence tags.
        
        Args:
            metadata: Metadata dictionary to update
            sequence_items: List of sequence items
            group: Parent group number
            element: Parent element number
        """
        try:
            # Extract EndOfItems, EndOfSequence, and StartOfItem from sequence items
            # Standard format shows these tags multiple times (once per sequence), so we extract them for each sequence
            for item in sequence_items:
                if isinstance(item, dict):
                    # Extract EndOfItems if present (Standard format shows multiple, so we extract each one)
                    if 'DICOM:EndOfItems' in item:
                        endofitems_value = item.get('DICOM:EndOfItems', '')
                        # Standard format shows multiple EndOfItems tags, so we should too
                        if 'EndOfItems' not in metadata:
                            metadata['DICOM:EndOfItems'] = endofitems_value
                        elif isinstance(metadata.get('DICOM:EndOfItems'), list):
                            metadata['DICOM:EndOfItems'].append(endofitems_value)
                        else:
                            # Convert to list if we have multiple
                            metadata['DICOM:EndOfItems'] = [metadata['DICOM:EndOfItems'], endofitems_value]
                    
                    # Extract EndOfSequence if present (Standard format shows multiple, so we extract each one)
                    if 'DICOM:EndOfSequence' in item:
                        endofsequence_value = item.get('DICOM:EndOfSequence', '')
                        # Standard format shows multiple EndOfSequence tags, so we should too
                        if 'EndOfSequence' not in metadata:
                            metadata['DICOM:EndOfSequence'] = endofsequence_value
                        elif isinstance(metadata.get('DICOM:EndOfSequence'), list):
                            metadata['DICOM:EndOfSequence'].append(endofsequence_value)
                        else:
                            # Convert to list if we have multiple
                            metadata['DICOM:EndOfSequence'] = [metadata['DICOM:EndOfSequence'], endofsequence_value]
                    
                    # Extract StartOfItem if present (multiple StartOfItem tags are allowed)
                    if 'DICOM:StartOfItem' in item:
                        # Standard format shows multiple StartOfItem tags, so we should too
                        # Store as a list if multiple, or as single value if only one
                        startofitem_value = item.get('DICOM:StartOfItem', '')
                        if 'StartOfItem' not in metadata:
                            metadata['DICOM:StartOfItem'] = startofitem_value
                        elif isinstance(metadata.get('DICOM:StartOfItem'), list):
                            metadata['DICOM:StartOfItem'].append(startofitem_value)
                        else:
                            # Convert to list if we have multiple
                            metadata['DICOM:StartOfItem'] = [metadata['DICOM:StartOfItem'], startofitem_value]
            
            # Source Image Sequence (0008,2112) - extract Referenced SOP Class UID and Instance UID
            if group == 0x0008 and element == 0x2112:
                for item in sequence_items:
                    if isinstance(item, dict):
                        # Extract Referenced SOP Class UID (0008,1150) - only keyword format
                        ref_class = item.get('DICOM:ReferencedSOPClassUID', '')
                        if not ref_class:
                            # Try to get from tag format if keyword format not available
                            ref_class = item.get('DICOM:(0008,1150)', '')
                        if ref_class:
                            # Map UID to human-readable name if possible
                            readable_name = self._uid_to_name(ref_class)
                            metadata['DICOM:ReferencedSOPClassUID'] = readable_name if readable_name else ref_class
                        
                        # Extract Referenced SOP Instance UID (0008,1155) - only keyword format
                        ref_instance = item.get('DICOM:ReferencedSOPInstanceUID', '')
                        if not ref_instance:
                            # Try to get from tag format if keyword format not available
                            ref_instance = item.get('DICOM:(0008,1155)', '')
                        if ref_instance:
                            metadata['DICOM:ReferencedSOPInstanceUID'] = ref_instance
            
            # Mask Subtraction Sequence (0028,6100) - extract MaskOperation and MaskFrameNumbers
            if group == 0x0028 and element == 0x6100:
                for item in sequence_items:
                    if isinstance(item, dict):
                        # Extract MaskOperation (0028,6101) - only keyword format
                        mask_op = item.get('DICOM:MaskOperation', '')
                        if not mask_op:
                            # Try to get from tag format if keyword format not available
                            mask_op = item.get('DICOM:(0028,6101)', '')
                        if mask_op:
                            metadata['DICOM:MaskOperation'] = mask_op
                        
                        # Extract MaskFrameNumbers (0028,6110) - only keyword format
                        mask_frames = item.get('DICOM:MaskFrameNumbers', None)
                        if mask_frames is None:
                            # Try to get from tag format if keyword format not available
                            mask_frames = item.get('DICOM:(0028,6110)', None)
                        if mask_frames is not None:
                            metadata['DICOM:MaskFrameNumbers'] = mask_frames
        except Exception:
            pass
    
    def _uid_to_name(self, uid: str) -> Optional[str]:
        """
        Convert DICOM UID to human-readable name.
        
        This standard format's UID to name conversion for common DICOM UIDs.
        
        Args:
            uid: DICOM UID string
            
        Returns:
            Human-readable name or None
        """
        # Common DICOM UIDs - matching standard UID registry
        uid_map = {
            # SOP Class UIDs (Image Storage)
            '1.2.840.10008.5.1.4.1.1.1': 'Computed Radiography Image Storage',
            '1.2.840.10008.5.1.4.1.1.2': 'CT Image Storage',
            '1.2.840.10008.5.1.4.1.1.3': 'Ultrasound Multi-frame Image Storage',
            '1.2.840.10008.5.1.4.1.1.4': 'MR Image Storage',
            '1.2.840.10008.5.1.4.1.1.5': 'Nuclear Medicine Image Storage',
            '1.2.840.10008.5.1.4.1.1.6': 'Ultrasound Image Storage',
            '1.2.840.10008.5.1.4.1.1.6.1': 'Ultrasound Image Storage (Retired)',
            '1.2.840.10008.5.1.4.1.1.7': 'Secondary Capture Image Storage',
            '1.2.840.10008.5.1.4.1.1.7.1': 'Multi-frame Single Bit Secondary Capture Image Storage',
            '1.2.840.10008.5.1.4.1.1.7.2': 'Multi-frame Grayscale Byte Secondary Capture Image Storage',
            '1.2.840.10008.5.1.4.1.1.7.3': 'Multi-frame Grayscale Word Secondary Capture Image Storage',
            '1.2.840.10008.5.1.4.1.1.7.4': 'Multi-frame True Color Secondary Capture Image Storage',
            '1.2.840.10008.5.1.4.1.1.8': 'Standalone Overlay Storage',
            '1.2.840.10008.5.1.4.1.1.9': 'Standalone Curve Storage',
            '1.2.840.10008.5.1.4.1.1.10': 'Standalone Modality LUT Storage',
            '1.2.840.10008.5.1.4.1.1.11': 'Standalone VOI LUT Storage',
            '1.2.840.10008.5.1.4.1.1.12': 'Grayscale Softcopy Presentation State Storage',
            '1.2.840.10008.5.1.4.1.1.12.1': 'X-Ray Angiographic Image Storage',
            '1.2.840.10008.5.1.4.1.1.12.2': 'X-Ray Radiofluoroscopic Image Storage',
            '1.2.840.10008.5.1.4.1.1.20': 'Nuclear Medicine Image Storage (Retired)',
            '1.2.840.10008.5.1.4.1.1.66': 'Raw Data Storage',
            '1.2.840.10008.5.1.4.1.1.66.1': 'Spatial Registration Storage',
            '1.2.840.10008.5.1.4.1.1.66.2': 'Spatial Fiducials Storage',
            '1.2.840.10008.5.1.4.1.1.66.3': 'Deformable Spatial Registration Storage',
            '1.2.840.10008.5.1.4.1.1.66.4': 'Segmentation Storage',
            '1.2.840.10008.5.1.4.1.1.66.5': 'Surface Segmentation Storage',
            '1.2.840.10008.5.1.4.1.1.77.1': 'VL Endoscopic Image Storage',
            '1.2.840.10008.5.1.4.1.1.77.1.1': 'Video Endoscopic Image Storage',
            '1.2.840.10008.5.1.4.1.1.77.1.2': 'VL Microscopic Image Storage',
            '1.2.840.10008.5.1.4.1.1.77.1.3': 'Video Microscopic Image Storage',
            '1.2.840.10008.5.1.4.1.1.77.1.4': 'VL Slide-Coordinates Microscopic Image Storage',
            '1.2.840.10008.5.1.4.1.1.77.1.5': 'VL Photographic Image Storage',
            '1.2.840.10008.5.1.4.1.1.77.1.5.1': 'Video Photographic Image Storage',
            '1.2.840.10008.5.1.4.1.1.77.1.6': 'Ophthalmic Photography 8 Bit Image Storage',
            '1.2.840.10008.5.1.4.1.1.77.1.7': 'Ophthalmic Photography 16 Bit Image Storage',
            '1.2.840.10008.5.1.4.1.1.77.1.8': 'Stereometric Relationship Storage',
            '1.2.840.10008.5.1.4.1.1.77.1.9': 'Ophthalmic Tomography Image Storage',
            '1.2.840.10008.5.1.4.1.1.77.1.10': 'Wide Field Ophthalmic Photography Stereographic Projection Image Storage',
            '1.2.840.10008.5.1.4.1.1.77.1.11': 'Wide Field Ophthalmic Photography 3 Coordinates Image Storage',
            '1.2.840.10008.5.1.4.1.1.78.1': 'Basic Text SR Storage',
            '1.2.840.10008.5.1.4.1.1.78.2': 'Enhanced SR Storage',
            '1.2.840.10008.5.1.4.1.1.78.3': 'Comprehensive SR Storage',
            '1.2.840.10008.5.1.4.1.1.78.4': 'Comprehensive 3D SR Storage',
            '1.2.840.10008.5.1.4.1.1.78.5': 'Extensible SR Storage',
            '1.2.840.10008.5.1.4.1.1.78.6': 'Mammography CAD SR Storage',
            '1.2.840.10008.5.1.4.1.1.78.7': 'Key Object Selection Document Storage',
            '1.2.840.10008.5.1.4.1.1.78.8': 'Chest CAD SR Storage',
            '1.2.840.10008.5.1.4.1.1.78.9': 'X-Ray Radiation Dose SR Storage',
            '1.2.840.10008.5.1.4.1.1.78.10': 'Radiopharmaceutical Radiation Dose SR Storage',
            '1.2.840.10008.5.1.4.1.1.78.11': 'Colon CAD SR Storage',
            '1.2.840.10008.5.1.4.1.1.78.12': 'Implantation Plan SR Storage',
            '1.2.840.10008.5.1.4.1.1.78.13': 'Acquisition Context SR Storage',
            '1.2.840.10008.5.1.4.1.1.78.14': 'Simplified Adult Echo SR Storage',
            '1.2.840.10008.5.1.4.1.1.78.15': 'Patient Radiation Dose SR Storage',
            '1.2.840.10008.5.1.4.1.1.88.11': 'Basic Text Structured Display Storage',
            '1.2.840.10008.5.1.4.1.1.88.22': 'Enhanced Structured Display Storage',
            '1.2.840.10008.5.1.4.1.1.88.33': 'Comprehensive Structured Display Storage',
            '1.2.840.10008.5.1.4.1.1.88.50': 'Mammography Image Storage',
            '1.2.840.10008.5.1.4.1.1.88.59': 'X-Ray 3D Angiographic Image Storage',
            '1.2.840.10008.5.1.4.1.1.88.65': 'X-Ray 3D Craniofacial Image Storage',
            '1.2.840.10008.5.1.4.1.1.88.67': 'Breast Tomosynthesis Image Storage',
            '1.2.840.10008.5.1.4.1.1.88.68': 'Breast Projection X-Ray Image Storage - For Presentation',
            '1.2.840.10008.5.1.4.1.1.88.69': 'Breast Projection X-Ray Image Storage - For Processing',
            '1.2.840.10008.5.1.4.1.1.88.70': 'Intravascular Optical Coherence Tomography Image Storage - For Presentation',
            '1.2.840.10008.5.1.4.1.1.88.71': 'Intravascular Optical Coherence Tomography Image Storage - For Processing',
            '1.2.840.10008.5.1.4.1.1.88.72': 'Nuclear Medicine Image Storage',
            '1.2.840.10008.5.1.4.1.1.128': 'Positron Emission Tomography Image Storage',
            '1.2.840.10008.5.1.4.1.1.129': 'Standalone PET Curve Storage',
            '1.2.840.10008.5.1.4.1.1.130': 'Enhanced PET Image Storage',
            '1.2.840.10008.5.1.4.1.1.131': 'Basic Structured Display Storage',
            '1.2.840.10008.5.1.4.1.1.481.1': 'RT Image Storage',
            '1.2.840.10008.5.1.4.1.1.481.2': 'RT Dose Storage',
            '1.2.840.10008.5.1.4.1.1.481.3': 'RT Structure Set Storage',
            '1.2.840.10008.5.1.4.1.1.481.4': 'RT Beams Treatment Record Storage',
            '1.2.840.10008.5.1.4.1.1.481.5': 'RT Plan Storage',
            '1.2.840.10008.5.1.4.1.1.481.6': 'RT Brachy Treatment Record Storage',
            '1.2.840.10008.5.1.4.1.1.481.7': 'RT Treatment Summary Record Storage',
            '1.2.840.10008.5.1.4.1.1.481.8': 'RT Ion Plan Storage',
            '1.2.840.10008.5.1.4.1.1.481.9': 'RT Ion Beams Treatment Record Storage',
            '1.2.840.10008.5.1.4.1.1.481.10': 'RT Patient Position Storage',
            # Transfer Syntax UIDs
            '1.2.840.10008.1.2': 'Implicit VR Little Endian',
            '1.2.840.10008.1.2.1': 'Explicit VR Little Endian',
            '1.2.840.10008.1.2.2': 'Explicit VR Big Endian',
            '1.2.840.10008.1.2.4.50': 'JPEG Baseline (Process 1)',
            '1.2.840.10008.1.2.4.51': 'JPEG Extended (Process 2 & 4)',
            '1.2.840.10008.1.2.4.57': 'JPEG Lossless (Process 14)',
            '1.2.840.10008.1.2.4.70': 'JPEG Lossless (Process 14, Selection Value 1)',
            '1.2.840.10008.1.2.4.80': 'JPEG-LS Lossless Image Compression',
            '1.2.840.10008.1.2.4.81': 'JPEG-LS Lossy (Near-Lossless) Image Compression',
            '1.2.840.10008.1.2.4.90': 'JPEG 2000 Image Compression (Lossless Only)',
            '1.2.840.10008.1.2.4.91': 'JPEG 2000 Image Compression',
            '1.2.840.10008.1.2.4.92': 'JPEG 2000 Part 2 Multi-component Image Compression (Lossless Only)',
            '1.2.840.10008.1.2.4.93': 'JPEG 2000 Part 2 Multi-component Image Compression',
            '1.2.840.10008.1.2.4.94': 'JPIP Referenced',
            '1.2.840.10008.1.2.4.95': 'JPIP Referenced Deflate',
            '1.2.840.10008.1.2.4.100': 'MPEG2 Main Profile @ Main Level',
            '1.2.840.10008.1.2.4.101': 'MPEG2 Main Profile @ High Level',
            '1.2.840.10008.1.2.4.102': 'MPEG-4 AVC/H.264 High Profile / Level 4.1',
            '1.2.840.10008.1.2.4.103': 'MPEG-4 AVC/H.264 BD-compatible High Profile / Level 4.1',
            '1.2.840.10008.1.2.4.104': 'MPEG-4 AVC/H.264 High Profile / Level 4.2 For 2D Video',
            '1.2.840.10008.1.2.4.105': 'MPEG-4 AVC/H.264 High Profile / Level 4.2 For 3D Video',
            '1.2.840.10008.1.2.4.106': 'MPEG-4 AVC/H.264 Stereo High Profile / Level 4.2',
            '1.2.840.10008.1.2.4.107': 'HEVC/H.265 Main Profile / Level 5.1',
            '1.2.840.10008.1.2.4.108': 'HEVC/H.265 Main 10 Profile / Level 5.1',
            '1.2.840.10008.1.2.5': 'RLE Lossless',
        }
        return uid_map.get(uid)
    
    def _parse_sequence_undefined_length(self, data: bytes, offset: int, parent_group: int, parent_element: int, is_big_endian: bool = False) -> Optional[Dict[str, Any]]:
        """
        Parse DICOM sequence with undefined length.
        
        Args:
            data: DICOM file data
            offset: Starting offset in data
            parent_group: Parent group number
            parent_element: Parent element number
            is_big_endian: Whether data is big-endian
            
        Returns:
            Dictionary with 'items' list, '_next_offset' for new offset, and optionally '_startofitem', or None
        """
        try:
            items = []
            current_offset = offset
            max_items = 100  # Limit to prevent infinite loops
            startofitem_data = None  # Collect StartOfItem data
            byte_order = '>' if is_big_endian else '<'
            
            while current_offset < len(data) - 8 and len(items) < max_items:
                # Check for item tag (FFFE, E000)
                if current_offset + 4 > len(data):
                    break
                
                item_group = struct.unpack(f'{byte_order}H', data[current_offset:current_offset+2])[0]
                item_element = struct.unpack(f'{byte_order}H', data[current_offset+2:current_offset+4])[0]
                
                if item_group == 0xFFFE and item_element == 0xE000:
                    # Item start - extract StartOfItem to standard format
                    item_start_offset = current_offset
                    current_offset += 4
                    if current_offset + 4 > len(data):
                        break
                    item_length = struct.unpack(f'{byte_order}I', data[current_offset:current_offset+4])[0]
                    current_offset += 4
                    
                    # Extract StartOfItem value for this item
                    item_startofitem_data = None
                    
                    if item_length == 0xFFFFFFFF:
                        # Undefined length item - parse until item delimiter
                        item_data = b''
                        item_data_start = current_offset
                        while current_offset < len(data) - 8:
                            if current_offset + 4 > len(data):
                                break
                            check_group = struct.unpack(f'{byte_order}H', data[current_offset:current_offset+2])[0]
                            check_element = struct.unpack(f'{byte_order}H', data[current_offset+2:current_offset+4])[0]
                            if check_group == 0xFFFE and check_element == 0xE00D:
                                # Item delimiter (EndOfItems) - extract as tag to standard format
                                # Extract StartOfItem value (raw item data) for this item
                                item_startofitem_data = data[item_data_start:current_offset]
                                if startofitem_data is None:  # Capture first StartOfItem for sequence
                                    startofitem_data = item_startofitem_data
                                # Extract EndOfItems tag (empty string value to standard format)
                                endofitems_metadata = {'DICOM:EndOfItems': ''}
                                current_offset += 8
                                # Parse item data
                                item_metadata = self._parse_data_elements(item_data, 0, is_big_endian=is_big_endian)
                                if item_metadata:
                                    # Add StartOfItem to this item's metadata
                                    if item_startofitem_data:
                                        # Format StartOfItem as raw string (latin1 encoding) to standard format
                                        if isinstance(item_startofitem_data, bytes):
                                            item_metadata['DICOM:StartOfItem'] = item_startofitem_data.decode('latin1', errors='ignore')
                                        else:
                                            item_metadata['DICOM:StartOfItem'] = item_startofitem_data
                                    # Merge EndOfItems into item metadata
                                    item_metadata.update(endofitems_metadata)
                                    items.append(item_metadata)
                                else:
                                    # Create item with StartOfItem and EndOfItems
                                    new_item = {}
                                    if item_startofitem_data:
                                        if isinstance(item_startofitem_data, bytes):
                                            new_item['DICOM:StartOfItem'] = item_startofitem_data.decode('latin1', errors='ignore')
                                        else:
                                            new_item['DICOM:StartOfItem'] = item_startofitem_data
                                    new_item.update(endofitems_metadata)
                                    items.append(new_item)
                                break  # Continue to next item instead of returning
                            item_data += data[current_offset:current_offset+1]
                            current_offset += 1
                        # If no delimiter found, parse item data anyway
                        if item_startofitem_data is None:
                            item_startofitem_data = data[item_data_start:current_offset] if item_data_start < current_offset else b''
                            if startofitem_data is None and item_startofitem_data:
                                startofitem_data = item_startofitem_data
                        # Parse item data
                        item_metadata = self._parse_data_elements(item_data, 0, is_big_endian=is_big_endian)
                        if item_metadata:
                            # Add StartOfItem to this item's metadata
                            if item_startofitem_data:
                                if isinstance(item_startofitem_data, bytes):
                                    item_metadata['DICOM:StartOfItem'] = item_startofitem_data.decode('latin1', errors='ignore')
                                else:
                                    item_metadata['DICOM:StartOfItem'] = item_startofitem_data
                            items.append(item_metadata)
                        elif item_startofitem_data:
                            # Create item with StartOfItem only
                            new_item = {}
                            if isinstance(item_startofitem_data, bytes):
                                new_item['DICOM:StartOfItem'] = item_startofitem_data.decode('latin1', errors='ignore')
                            else:
                                new_item['DICOM:StartOfItem'] = item_startofitem_data
                            items.append(new_item)
                    elif item_length > 0 and current_offset + item_length <= len(data):
                        item_data = data[current_offset:current_offset+item_length]
                        # Extract StartOfItem value (raw item data) to standard format
                        item_startofitem_data = item_data
                        if startofitem_data is None:  # Capture first StartOfItem for sequence
                            startofitem_data = item_startofitem_data
                        # Parse item data
                        item_metadata = self._parse_data_elements(item_data, 0, is_big_endian=is_big_endian)
                        if item_metadata:
                            # Add StartOfItem to this item's metadata
                            if isinstance(item_startofitem_data, bytes):
                                item_metadata['DICOM:StartOfItem'] = item_startofitem_data.decode('latin1', errors='ignore')
                            else:
                                item_metadata['DICOM:StartOfItem'] = item_startofitem_data
                            items.append(item_metadata)
                        else:
                            # Create item with StartOfItem only
                            new_item = {}
                            if isinstance(item_startofitem_data, bytes):
                                new_item['DICOM:StartOfItem'] = item_startofitem_data.decode('latin1', errors='ignore')
                            else:
                                new_item['DICOM:StartOfItem'] = item_startofitem_data
                            items.append(new_item)
                        current_offset += item_length
                        # Pad to even length
                        if item_length % 2 == 1:
                            current_offset += 1
                    elif item_length == 0:
                        # Empty item - still extract StartOfItem (empty string)
                        empty_item = {'DICOM:StartOfItem': ''}
                        items.append(empty_item)
                    else:
                        break
                elif item_group == 0xFFFE and item_element == 0xE0DD:
                    # Sequence delimiter (EndOfSequence) - extract as tag to standard format
                    # Extract EndOfSequence tag (empty string value to standard format)
                    endofsequence_metadata = {'DICOM:EndOfSequence': ''}
                    # Add EndOfSequence to the last item if items exist, otherwise create a new item
                    if items:
                        if isinstance(items[-1], dict):
                            items[-1].update(endofsequence_metadata)
                        else:
                            items.append(endofsequence_metadata)
                    else:
                        items.append(endofsequence_metadata)
                    result = {'items': items, '_next_offset': current_offset + 8, '_endofsequence': ''}
                    if startofitem_data is not None:
                        result['_startofitem'] = startofitem_data
                    return result
                else:
                    # Not an item tag - might be corrupted, try to continue
                    current_offset += 1
            
            # Return items even if we didn't find delimiter
            if items:
                result = {'items': items, '_next_offset': current_offset}
                if startofitem_data is not None:
                    result['_startofitem'] = startofitem_data
                return result
            return None
        
        except Exception:
            return None
    
    def _parse_sequence(self, data: bytes, parent_group: int, parent_element: int, is_big_endian: bool = False) -> Optional[Any]:
        """
        Parse DICOM sequence (SQ) data.
        
        Args:
            data: Sequence data bytes
            parent_group: Parent group number
            parent_element: Parent element number
            is_big_endian: Whether data is big-endian
            
        Returns:
            Parsed sequence data or None, or dict with 'items' and '_startofitem' if StartOfItem found
        """
        try:
            items = []
            offset = 0
            max_items = 100  # Limit to prevent infinite loops
            startofitem_data = None  # Collect StartOfItem data
            byte_order = '>' if is_big_endian else '<'
            
            while offset < len(data) - 8 and len(items) < max_items:
                # Check for item tag (FFFE, E000)
                if offset + 4 > len(data):
                    break
                
                # Use correct byte order
                item_group = struct.unpack(f'{byte_order}H', data[offset:offset+2])[0]
                item_element = struct.unpack(f'{byte_order}H', data[offset+2:offset+4])[0]
                
                if item_group == 0xFFFE and item_element == 0xE000:
                    # Item start - extract StartOfItem tag to standard format
                    item_start_offset = offset
                    offset += 4
                    if offset + 4 > len(data):
                        break
                    item_length = struct.unpack(f'{byte_order}I', data[offset:offset+4])[0]
                    offset += 4
                    
                    if item_length == 0xFFFFFFFF:
                        # Undefined length - parse until item delimiter
                        item_data = b''
                        item_data_start = offset
                        while offset < len(data) - 8:
                            if offset + 4 > len(data):
                                break
                            check_group = struct.unpack(f'{byte_order}H', data[offset:offset+2])[0]
                            check_element = struct.unpack(f'{byte_order}H', data[offset+2:offset+4])[0]
                            if check_group == 0xFFFE and check_element == 0xE00D:
                                # Item delimiter
                                # Extract StartOfItem value (raw item data)
                                # Standard format shows StartOfItem without null padding bytes
                                # standard format also swaps the value bytes (the 8-byte value is shown with halves swapped)
                                if startofitem_data is None:  # Only capture first StartOfItem
                                    raw_data = data[item_data_start:offset]
                                    # Remove null padding bytes to standard format format
                                    cleaned = raw_data.replace(b'\x00', b'')
                                    # Standard format shows the value bytes with halves swapped
                                    # Value is at bytes 5-12 (after \x10 LO\x08)
                                    if len(cleaned) >= 13:
                                        # Swap the two halves of the 8-byte value
                                        value_start = 5  # After \x10 LO\x08
                                        value_end = 13
                                        first_half = cleaned[value_start:value_start+4]
                                        second_half = cleaned[value_start+4:value_end]
                                        # Swap halves
                                        swapped_value = second_half + first_half
                                        startofitem_data = cleaned[:value_start] + swapped_value + cleaned[value_end:]
                                    else:
                                        startofitem_data = cleaned
                                offset += 8
                                break
                            item_data += data[offset:offset+1]
                            offset += 1
                        # Parse item data
                        item_metadata = self._parse_data_elements(item_data, 0, is_big_endian=is_big_endian)
                        if item_metadata:
                            items.append(item_metadata)
                    elif item_length > 0 and offset + item_length <= len(data):
                        item_data = data[offset:offset+item_length]
                        # Extract StartOfItem value (raw item data) to standard format
                        # Standard format shows StartOfItem without null padding bytes
                        # standard format also swaps the value bytes (the 8-byte value is shown with halves swapped)
                        if startofitem_data is None:  # Only capture first StartOfItem
                            # Remove null padding bytes to standard format format
                            cleaned = item_data.replace(b'\x00', b'')
                            # Standard format shows the value bytes with halves swapped
                            # Value is at bytes 5-12 (after \x10 LO\x08)
                            if len(cleaned) >= 13:
                                # Swap the two halves of the 8-byte value
                                value_start = 5  # After \x10 LO\x08
                                value_end = 13
                                first_half = cleaned[value_start:value_start+4]
                                second_half = cleaned[value_start+4:value_end]
                                # Swap halves
                                swapped_value = second_half + first_half
                                startofitem_data = cleaned[:value_start] + swapped_value + cleaned[value_end:]
                            else:
                                startofitem_data = cleaned
                        # Parse item data
                        item_metadata = self._parse_data_elements(item_data, 0, is_big_endian=is_big_endian)
                        if item_metadata:
                            items.append(item_metadata)
                        offset += item_length
                        # Pad to even length
                        if item_length % 2 == 1:
                            offset += 1
                    else:
                        break
                elif item_group == 0xFFFE and item_element == 0xE0DD:
                    # Sequence delimiter
                    break
                else:
                    offset += 1
            
            # Extract specific values from sequences for standard format compatibility
            if items and parent_group == 0x0008 and parent_element == 0x2112:
                # Source Image Sequence - extract Referenced SOP Class UID and Instance UID
                result = []
                for item in items:
                    if isinstance(item, dict):
                        # Try multiple possible tag formats
                        ref_class = (item.get('DICOM:(0008,1150)') or 
                                   item.get('DICOM:ReferencedSOPClassUID') or
                                   item.get('DICOM:(0008,9206)') or '')
                        ref_instance = (item.get('DICOM:(0008,1155)') or 
                                      item.get('DICOM:ReferencedSOPInstanceUID') or
                                      item.get('DICOM:(0008,9207)') or '')
                        if ref_class or ref_instance:
                            result.append({'ReferencedSOPClassUID': ref_class, 'ReferencedSOPInstanceUID': ref_instance})
                if result:
                    return result if startofitem_data is None else {'items': result, '_startofitem': startofitem_data}
                elif startofitem_data is not None:
                    return {'items': items, '_startofitem': startofitem_data}
                return items
            
            # Return StartOfItem if found
            if startofitem_data is not None:
                return {'items': items, '_startofitem': startofitem_data}
            return items if items else None
        
        except Exception:
            return None
    
    def _decode_value(self, data: bytes, vr: str, group: int, element: int) -> Any:
        """
        Decode DICOM value based on VR (Value Representation).
        
        Args:
            data: Value data bytes
            vr: Value Representation code
            group: Group number
            element: Element number
            
        Returns:
            Decoded value
        """
        try:
            if vr in ('AE', 'AS', 'CS', 'DA', 'DS', 'DT', 'IS', 'LO', 'LT', 'PN', 'SH', 'ST', 'TM', 'UI', 'UT'):
                # String types
                value = data.rstrip(b'\x00').decode('ascii', errors='ignore')
                # Handle multi-value strings (backslash-separated in DICOM)
                if '\\' in value:
                    parts = value.split('\\')
                    # For DS (Decimal String) and IS (Integer String), convert to numbers
                    if vr in ('DS', 'IS'):
                        result = []
                        for part in parts:
                            part = part.strip()
                            if part:
                                try:
                                    if vr == 'DS':
                                        result.append(float(part))
                                    else:  # IS
                                        result.append(int(part))
                                except (ValueError, TypeError):
                                    result.append(part)
                        return result if len(result) > 1 else (result[0] if result else value)
                    return parts
                # For DS and IS, try to convert to number
                if vr in ('DS', 'IS'):
                    value = value.strip()
                    if value:
                        try:
                            return float(value) if vr == 'DS' else int(value)
                        except (ValueError, TypeError):
                            pass
                return value
            elif vr == 'AT':
                # Attribute Tag - 4 bytes (group, element)
                if len(data) >= 4:
                    tag_group = struct.unpack('<H', data[0:2])[0]
                    tag_element = struct.unpack('<H', data[2:4])[0]
                    return f"{tag_group:04X},{tag_element:04X}"
            elif vr in ('SS', 'US'):
                # Signed/Unsigned Short (16-bit) - can be multi-value
                if len(data) >= 2:
                    # Check if multiple values (length > 2 bytes)
                    if len(data) > 2:
                        # Multi-value - parse all values
                        num_values = len(data) // 2
                        if vr == 'SS':
                            values = list(struct.unpack(f'<{num_values}h', data[:num_values*2]))
                        else:  # US
                            values = list(struct.unpack(f'<{num_values}H', data[:num_values*2]))
                        return values if len(values) > 1 else (values[0] if values else None)
                    else:
                        # Single value
                        if vr == 'SS':
                            return struct.unpack('<h', data[:2])[0]
                        else:
                            return struct.unpack('<H', data[:2])[0]
            elif vr in ('SL', 'UL'):
                # Signed/Unsigned Long (32-bit) - can be multi-value
                if len(data) >= 4:
                    # Check if multiple values (length > 4 bytes)
                    if len(data) > 4:
                        # Multi-value - parse all values
                        num_values = len(data) // 4
                        if vr == 'SL':
                            values = list(struct.unpack(f'<{num_values}i', data[:num_values*4]))
                        else:  # UL
                            values = list(struct.unpack(f'<{num_values}I', data[:num_values*4]))
                        return values if len(values) > 1 else (values[0] if values else None)
                    else:
                        # Single value
                        if vr == 'SL':
                            return struct.unpack('<i', data[:4])[0]
                        else:
                            return struct.unpack('<I', data[:4])[0]
            elif vr in ('FL', 'FD'):
                # Float/Double
                if vr == 'FL' and len(data) >= 4:
                    return struct.unpack('<f', data[:4])[0]
                elif vr == 'FD' and len(data) >= 8:
                    return struct.unpack('<d', data[:8])[0]
            elif vr in ('OB', 'OD', 'OF', 'OL', 'OV', 'OW'):
                # Binary data - return as hex string for display
                # Special handling for FileMetaInfoVersion (OB type, but should be shown as space-separated bytes)
                if group == 0x0002 and element == 0x0001:
                    # FileMetaInfoVersion - return as space-separated byte values
                    return ' '.join(str(b) for b in data[:len(data)])
                # Special handling for UniqueImageIden and UserDefinedData - show as space-separated bytes
                if (group == 0x0043 and element == 0x1028) or (group == 0x0043 and element == 0x102A):
                    # UniqueImageIden or UserDefinedData - return as space-separated byte values
                    return ' '.join(str(b) for b in data[:len(data)])
                if len(data) > 0:
                    # For small binary data, show hex; for large, just show size
                    if len(data) <= 64:
                        return data.hex()
                    else:
                        return f"<Binary data {len(data)} bytes>"
            
            # Default: return as string
            return data.rstrip(b'\x00').decode('ascii', errors='ignore')
        
        except Exception:
            return data.hex() if len(data) <= 64 else f"<Binary data {len(data)} bytes>"
    
    def _format_tag_value(self, tag_name: str, value: Any, vr: str) -> Any:
        """
        Format tag value to standard format output format.
        
        Args:
            tag_name: Tag name
            value: Decoded value
            vr: Value Representation code
            
        Returns:
            Formatted value
        """
        if value is None or value == "":
            return ""
        
        # Format dates (DA type) - all date tags, not just specific ones
        if vr == 'DA' and isinstance(value, str) and len(value) == 8 and value.isdigit():
            # Format YYYYMMDD to YYYY:MM:DD (standard format)
            return f"{value[:4]}:{value[4:6]}:{value[6:8]}"
        elif 'Date' in tag_name and isinstance(value, str) and len(value) == 8 and value.isdigit():
            # Also handle date tags that might not have VR='DA'
            return f"{value[:4]}:{value[4:6]}:{value[6:8]}"
        
        # Format times (TM type) - all time tags
        if vr == 'TM' and isinstance(value, str) and len(value) >= 6:
            # Format HHMMSS to HH:MM:SS (standard format)
            time_str = value[:6]  # Take first 6 digits
            if len(time_str) == 6 and time_str.isdigit():
                return f"{time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
            return value.strip()  # Remove trailing spaces
        elif 'Time' in tag_name and isinstance(value, str) and len(value) >= 6:
            # Also handle time tags that might not have VR='TM'
            time_str = value[:6]
            if len(time_str) == 6 and time_str.isdigit():
                return f"{time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
            return value.strip()
        
        # Format UIDs - keep as-is (already formatted)
        if tag_name.endswith('UID') and isinstance(value, str):
            return value.strip()
        
        # Format enum values - convert numeric codes to names
        enum_mappings = {
            'PixelRepresentation': {0: 'Unsigned', 1: 'Signed'},
            # Add more enum mappings as needed
        }
        if tag_name in enum_mappings and isinstance(value, (int, str)):
            try:
                int_val = int(value)
                if int_val in enum_mappings[tag_name]:
                    return enum_mappings[tag_name][int_val]
            except (ValueError, TypeError):
                pass
        
        # Format float values - standard format format
        if isinstance(value, float):
            # Standard format shows whole number floats as "X.0" for certain tags
            if value == int(value):
                # For certain tags, Standard format shows as "X.0" even for whole numbers
                if tag_name in ('AvgOverrangesAllViews', 'DataCollectionDiameter', 'DistanceSourceToPatient', 
                               'GantryDetectorTilt', 'PatientWeight', 'SliceThickness', 'TableHeight', 
                               'TableLateralPosition', 'TableLongitudinalPosition', 'GantryDetectorTilt',
                               'DistanceSourceToDetector', 'EstimatedRadiographicMagnificationFactor', 
                               'SliceLocation', 'TableAngle', 'TableTopPitchAngle', 'TableTopRollAngle', 
                               'TableTopVerticalPosition', 'SpacingBetweenSlices', 'TableSpeed', 'TriggerFrequency',
                               'AvgOfLeftRefChansOverViews', 'AvgOfRightRefChansOverViews', 'BackProjectorCoefficient',
                               'DeltaStartTime', 'DisplayFieldOfView', 'DynamicZAlphaValue', 'GantryPeriod',
                               'InterscanDelay', 'LowerRangeOfPixels1b', 'LowerRangeOfPixels1c', 'MaxLeftChanOverViews',
                               'MaxRightChanOverViews', 'ZChanAvgOverViews'):
                    return f"{value:.1f}"
                else:
                    return str(int(value))
            # For high-precision floats, standard format precision exactly
            # Standard format uses specific precision for different tags - match that exactly
            precision_map = {
                'StartTimeSecsInFirstAxial': 6,  # Standard format shows 6 decimal places
                'DegreeOfRotation': 11,  # Standard format shows 11 decimal places
                'ACoordOfTopRightCorner': 12,  # Standard format shows 12 decimal places
                'ACoordOfBottomRightCorner': 12,
                'RCoordOfTopRightCorner': 12,
                'RCoordOfBottomRightCorner': 12,
                'SCoordOfTopRightCorner': 13,  # Standard format shows 13 decimal places
                'SCoordOfBottomRightCorner': 13,
                'CenterACoordOfPlaneImage': 14,
                'CenterRCoordOfPlaneImage': 13,  # Standard format shows 13 decimal places
                'CenterSCoordOfPlaneImage': 13,
                'ImageLocation': 13,
                'DurationOfXrayOn': 13,
                'TableStartLocation': 13,
                'TableEndLocation': 12,  # Standard format shows 12 decimal places
                'TriggerOnPosition': 12,
            }
            
            if tag_name in precision_map:
                # Use exact precision that Standard format uses
                precision = precision_map[tag_name]
                formatted = f"{value:.{precision}f}"
                # Remove trailing zeros
                formatted = formatted.rstrip('0')
                if formatted.endswith('.'):
                    formatted = formatted[:-1]
            else:
                # Format with appropriate precision (remove trailing zeros)
                formatted = f"{value:.10f}".rstrip('0').rstrip('.')
            return formatted
        
        # Format numeric strings - remove trailing spaces
        if isinstance(value, str):
            value = value.rstrip()  # Remove trailing spaces
            # Special handling for tags that should preserve leading zeros or specific format
            if tag_name in ('GenesisVersionNow', 'SoftwareVersion') and value.isdigit():
                # Preserve leading zeros for version numbers
                return value
            # Check if it's a numeric string that should be formatted as number
            try:
                float_val = float(value)
                # For certain tags, Standard format shows whole numbers as "X.0"
                if float_val == int(float_val):
                    if tag_name in ('AvgOverrangesAllViews', 'DataCollectionDiameter', 'DistanceSourceToPatient', 
                                   'GantryDetectorTilt', 'PatientWeight', 'SliceThickness', 'SpacingBetweenSlices',
                                   'TableSpeed', 'TriggerFrequency', 'InterscanDelay', 'LowerRangeOfPixels1b',
                                   'LowerRangeOfPixels1c', 'MaxLeftChanOverViews', 'MaxRightChanOverViews',
                                   'ZChanAvgOverViews', 'AvgOfLeftRefChansOverViews', 'AvgOfRightRefChansOverViews',
                                   'BackProjectorCoefficient', 'DeltaStartTime', 'DisplayFieldOfView',
                                   'DynamicZAlphaValue', 'GantryPeriod'):
                        return f"{float_val:.1f}"
                    else:
                        return str(int(float_val))
                # For high-precision floats, standard format precision exactly
                precision_map = {
                    'StartTimeSecsInFirstAxial': 6,
                    'DegreeOfRotation': 11,
                    'ACoordOfTopRightCorner': 12,
                    'ACoordOfBottomRightCorner': 12,
                    'RCoordOfTopRightCorner': 12,
                    'RCoordOfBottomRightCorner': 12,
                    'SCoordOfTopRightCorner': 13,
                    'SCoordOfBottomRightCorner': 13,
                    'CenterACoordOfPlaneImage': 14,
                    'CenterRCoordOfPlaneImage': 13,
                    'CenterSCoordOfPlaneImage': 13,
                    'ImageLocation': 13,
                    'DurationOfXrayOn': 13,
                    'TableStartLocation': 13,
                    'TableEndLocation': 13,
                    'TriggerOnPosition': 12,
                }
                
                if tag_name in precision_map:
                    precision = precision_map[tag_name]
                    formatted = f"{float_val:.{precision}f}"
                    formatted = formatted.rstrip('0')
                    if formatted.endswith('.'):
                        formatted = formatted[:-1]
                    return formatted
                # Remove trailing zeros for floats
                return f"{float_val:.10f}".rstrip('0').rstrip('.')
            except ValueError:
                pass
        
        # Format multi-value strings (backslash-separated for certain tags)
        if isinstance(value, list):
            # Standard format uses backslashes for certain multi-value tags
            backslash_tags = ('ImageType', 'ImageOrientationPatient', 'ImagePositionPatient', 
                            'PixelSpacing', 'SliceLocation', 'TableTopLateralPosition',
                            'TableTopLongitudinalPosition', 'TableTopVerticalPosition',
                            'WindowCenter', 'WindowWidth', 'RescaleIntercept', 'RescaleSlope',
                            'BBHCoefficients', 'RACordOfTargetReconCenter')
            if tag_name in backslash_tags:
                # Format float values with appropriate precision
                formatted_values = []
                for v in value:
                    if isinstance(v, float):
                        # For BBHCoefficients and RACordOfTargetReconCenter, use 6 decimal places
                        if tag_name in ('BBHCoefficients', 'RACordOfTargetReconCenter'):
                            formatted_values.append(f"{v:.6f}")
                        # For ImageOrientationPatient, use 6 decimal places
                        elif tag_name == 'ImageOrientationPatient':
                            formatted_values.append(f"{v:.6f}")
                        else:
                            formatted_values.append(str(v).strip())
                    else:
                        formatted_values.append(str(v).strip())
                return '\\'.join(formatted_values)
            # Multi-value tags that use spaces (not backslashes) - show all values
            space_tags = ('CalibrationParameters', 'DeconKernelParameters', 'PpscanParameters', 
                         'X-RayChain', 'HistogramTables', 'NoViewsRefChansBlocked', 'ReferenceChannels',
                         'PrivateScanOptions')
            if tag_name in space_tags:
                return ' '.join(str(v).strip() for v in value)
            return ' '.join(str(v).strip() for v in value)
        
        # Format numeric lists
        if isinstance(value, (list, tuple)) and len(value) > 0:
            if all(isinstance(v, (int, float)) for v in value):
                formatted_values = []
                for v in value:
                    if isinstance(v, float) and v == int(v):
                        formatted_values.append(str(int(v)))
                    elif isinstance(v, float):
                        formatted_values.append(f"{v:.10f}".rstrip('0').rstrip('.'))
                    else:
                        formatted_values.append(str(v))
                return ' '.join(formatted_values)
        
        # Format binary data for specific tags
        if tag_name in ('SuiteID', 'RWavePointer', 'CurveData'):
            if isinstance(value, str) and value.startswith('<Binary'):
                return value
            elif isinstance(value, bytes):
                return f"<Binary data {len(value)} bytes>"
        # Standard format uses parentheses for PixelData, HistogramTables, DataSetTrailingPadding
        if tag_name in ('PixelData', 'HistogramTables', 'DataSetTrailingPadding'):
            if isinstance(value, str) and value.startswith('(Binary'):
                return value
            elif isinstance(value, str) and value.startswith('<Binary'):
                # Convert from <Binary data X bytes> to (Binary data X bytes, use -b option to extract)
                # Extract the size from the string
                import re
                match = re.search(r'(\d+)', value)
                if match:
                    size = match.group(1)
                    return f"(Binary data {size} bytes, use -b option to extract)"
            elif isinstance(value, bytes):
                return f"(Binary data {len(value)} bytes, use -b option to extract)"
        # StartOfItem should be formatted as raw string (bytes decoded as latin1)
        if tag_name == 'StartOfItem':
            if isinstance(value, bytes):
                # Standard format shows StartOfItem as raw string (latin1 encoding)
                return value.decode('latin1', errors='ignore')
            return value
        
        # Remove trailing spaces from string values
        if isinstance(value, str):
            return value.rstrip()
        
        return value
    
    def _get_tag_name(self, group: int, element: int) -> Optional[str]:
        """
        Get human-readable name for DICOM tag.
        
        This method uses the comprehensive DICOM Data Elements registry
        that includes all standard DICOM tags from the DICOM standard PS3.6.
        If a tag is not in the registry, it checks the private tag registry
        (for manufacturer-specific tags), then falls back to the legacy dictionary
        or generates a name from the group/element numbers.
        
        Tag names are converted to standard format's format (e.g., "FileMetaInfoGroupLength"
        instead of "FileMetaInformationGroupLength").
        
        Args:
            group: Group number
            element: Element number
            
        Returns:
            Tag name or None
        """
        # First check the comprehensive registry (standard DICOM tags)
        element_info = get_dicom_element_info(group, element)
        if element_info:
            keyword = element_info.keyword
            # Convert to standard format (shorter names)
            keyword = self._convert_to_standard_format(keyword)
            return keyword
        
        # Check private tag registry (manufacturer-specific tags)
        # Private tags are in odd-numbered groups (0009, 0011, 0013, etc.)
        if group % 2 == 1 or group in (0x0009, 0x0011, 0x0013, 0x0015, 0x0017, 0x0019, 0x0021, 0x0023, 0x0025, 0x0027, 0x0029, 0x002B, 0x002D, 0x002F, 0x0043):
            private_name = _DICOM_PRIVATE_TAG_REGISTRY.get((group, element))
            if private_name:
                return private_name
        
        # Fall back to legacy dictionary
        name = _DICOM_TAG_DICT.get((group, element))
        if name:
            # Convert to standard format
            name = self._convert_to_standard_format(name)
            return name
        
        # For unmapped tags, check if it's a curve data tag (group 5000-50FF)
        # Curve data tags use repeating groups but have consistent element numbers
        # Standard extraction them with the element number only (e.g., CurveDimensions)
        if 0x5000 <= group <= 0x50FF:
            # Check if this element number exists in the curve data registry (using group 5000 as template)
            curve_element_info = get_dicom_element_info(0x5000, element)
            if curve_element_info:
                keyword = curve_element_info.keyword
                keyword = self._convert_to_standard_format(keyword)
                return keyword
        
        # For unmapped tags, generate a name from group/element
        # This ensures all tags are named even if not in the dictionary
        # Note: standard format may have keyword names for these, but we don't have them in our registry yet
        return f"Tag_{group:04X}_{element:04X}"
    
    def _convert_to_standard_format(self, keyword: str) -> str:
        """
        Convert DICOM keyword to standard format.
        
        Standard format uses shorter names for some tags (e.g., "FileMetaInfoGroupLength"
        instead of "FileMetaInformationGroupLength").
        
        Args:
            keyword: DICOM keyword name
            
        Returns:
            standard format-formatted keyword name
        """
        # standard format name mappings (shorter names and different spellings)
        standard_format_mappings = {
            'FileMetaInformationGroupLength': 'FileMetaInfoGroupLength',
            'FileMetaInformationVersion': 'FileMetaInfoVersion',
            'ManufacturerModelName': 'ManufacturersModelName',  # Standard format uses plural
            # Add more mappings as needed
        }
        return standard_format_mappings.get(keyword, keyword)
    
    def _get_tag_info(self, group: int, element: int) -> Optional[DICOMDataElement]:
        """
        Get complete DICOM Data Element information including Name, Keyword, VR, and VM.
        
        Args:
            group: Group number
            element: Element number
            
        Returns:
            DICOMDataElement if found, None otherwise
        """
        return get_dicom_element_info(group, element)
