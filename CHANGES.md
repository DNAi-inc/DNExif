# Changelog

All notable changes to DNExif will be documented in this file.

## December 23, 2025 - Builds 1716-1718

**MOS Parser & SubIFD Improvements (1718)**: Enhanced SubIFD traversal to process up to 50 SubIFDs (from 10), improved Leaf tag extraction with SLONG/SRATIONAL support, better error handling and bounds checking.

**Code Quality (1717)**: Removed 25+ debug print statements from `exif_parser.py` and PKTS parser, set DEBUG_PKTS to False for production.

**RAW Writing (1716)**: Implemented ORF header preservation with proper endianness handling, X3F structure preservation, created comprehensive RAW format test suite.

## December 12, 2025 - Builds 1712-1715

**Test Infrastructure (1715)**: Created base test framework with ExifTool integration, metadata comparison, round-trip testing, and JSON result reporting.

**Code Quality & TODO System (1714)**: Established `.dnai/TODO.md` task tracking system, removed debug statements from MOS parser, improved error handling and documentation.

**Code Review (1713)**: Reviewed MOS and audio parsers, verified code standards compliance, documented improvement opportunities.

**MOS Testing (1712)**: Created MOS test script for read/write verification with ExifTool comparison and round-trip testing.

## December 12, 2025 - Project Consolidation

Updated license headers across 136 Python files, enhanced README with dual-license info and DICOM documentation (5,200+ data elements). Created GitHub Wiki structure. Version 0.1.3. Supports 120+ formats for reading, 36 verified with tag extraction, full write support for JPEG/TIFF/PNG/WebP/GIF/HEIC and many RAW formats.

---

**Copyright © 2025 DNAi inc.** All rights reserved.

**Dual-licensed under the DNAi Free License v1.1 and the DNAi Commercial License v1.1.**
