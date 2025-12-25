# Changelog

All notable changes to DNExif will be documented in this file.

## December 23, 2025 - Build 1718 - MOS Parser Improvements and Enhanced SubIFD Traversal

**Focus**: Improved MOS parser to extract more metadata blocks and enhanced SubIFD traversal for better Leaf tag extraction.

**Changes**: Enhanced SubIFD (0x014A) tag handling to process up to 50 SubIFDs (increased from 10), added multiple offset calculation strategies, improved handling of inline vs. offset-based SubIFD values. Improved Leaf tag extraction with enhanced UNDEFINED type handling, added support for SLONG and SRATIONAL types, better error handling with alternative extraction methods. Professional error handling with specific exception types, better bounds checking and data validation. Location: `dnexif/raw_parser.py` - lines 8586-8603, 8668-8750.

---

## December 23, 2025 - Build 1717 - Code Quality Improvements and Debug Statement Removal

**Focus**: Code quality improvements, debug statement removal, and professional code cleanup.

**Changes**: Removed all debug print statements from `exif_parser.py` (25 debug statements removed), removed EXIF PARSER DEBUG, LEAFDATA DEBUG, and PKTS DEBUG statements throughout PKTS format parser, set DEBUG_PKTS flag to False for production code. Cleaned up PKTS parser implementation while maintaining full functionality. Code is now production-ready without debug output. Location: `dnexif/exif_parser.py` - lines 1702-1764, 3624-4037.

---

## December 23, 2025 - Build 1716 - ORF/X3F Writing Improvements and Comprehensive Test Suite

**Focus**: Improved ORF and X3F metadata writing, comprehensive test infrastructure, and professional code enhancements.

**Changes**: Implemented proper ORF header preservation with `_write_orf_with_header` method, enhanced ORF structure handling (IIRO/MMOR header + TIFF structure), proper endianness handling for both little-endian and big-endian ORF files. Implemented X3F structure preservation with `_write_x3f_with_structure` method, enhanced X3F header parsing with proper big-endian byte order handling. Created `test_raw_formats.py` comprehensive RAW format testing suite with `RAWTester` class. Location: `dnexif/raw_writer.py` - replaced TODOs at lines 284 and 349.

---

## December 12, 2025 - Build 1715 - Test Infrastructure and Code Quality Enhancements

**Focus**: Test infrastructure improvements, code quality enhancements, and professional code structure.

**Changes**: Created comprehensive base test framework (`test_framework_base.py`) with reusable `TestFrameworkBase` class for format-specific testing. Added ExifTool integration utilities, metadata comparison functionality, round-trip testing capabilities, file integrity verification methods, and comprehensive result reporting with JSON export. Reviewed all TODO comments in codebase, verified all TODO items are properly documented in `.dnai/TODO.md`. Location: `.test/test_framework_base.py`.

---

## December 12, 2025 - Build 1714 - Code Quality Improvements and TODO System

**Focus**: Code quality improvements, TODO system setup, and professional code cleanup.

**Changes**: Created comprehensive TODO.md system with `.dnai/TODO.md` for task tracking, created `.dnai/A1/` directory structure and `.test/` directory with test infrastructure documentation. Removed debug print statements from MOS parser (`raw_parser.py`), improved error handling (replaced generic `except:` with specific exception handling), enhanced code comments and documentation. Created `.test/README.md` with test infrastructure documentation. Location: `dnexif/raw_parser.py`, `.dnai/TODO.md`, `.test/README.md`.

---

## December 12, 2025 - Build 1713 - Code Review and Test Infrastructure Setup

**Focus**: Code review, test infrastructure setup, and documentation improvements.

**Changes**: Created `.dnai/TODO.md` to track all development tasks, updated `CHANGES.md` with Build 1712 and 1713 entries. Reviewed MOS parser implementation in `raw_parser.py` and audio parser implementation in `audio_parser.py`, verified code follows project standards (proper comments, type hints). Confirmed no TODO/FIXME comments in critical code paths, documented MOS parser complexity and improvement opportunities. Established systematic approach to testing and verification.

---

## December 12, 2025 - Build 1712 - MOS File Type Testing and Comprehensive Write Verification

**Focus**: MOS file type testing and comprehensive file type write verification with ExifTool.

**Changes**: Created root-level `TODO.md` to track all development tasks, updated `CHANGES.md` with Build 1712 entry. Identified 4 MOS test files in `tests/TESTING/`, verified MOS files are TIFF-based and handled by `raw_writer.py` via `TIFFWriter`. Created comprehensive MOS test script (`test_mos_read_write.py`) that tests reading MOS files with DNExif and ExifTool, compares outputs before and after writing, verifies round-trip functionality and file integrity. Verified comprehensive test framework `test_all_formats_write_verification.py` already exists.

---

## December 12, 2025 - Project Consolidation

**Focus**: License and copyright updates, project status documentation, and comprehensive documentation improvements.

**Changes**: Updated `README.md` with comprehensive dual-license information, added extensive DICOM documentation (5,200+ data elements, private tags, sequence parsing). Created comprehensive GitHub Wiki structure with 8+ documentation pages including dedicated DICOM-Support.md page. Updated all 136 Python files in `dnexif/` directory with proper license headers. Current version: 0.1.3. Format support: 120+ file formats for reading, 36 formats verified with comprehensive tag extraction, full write support for JPEG, TIFF, PNG, WebP, GIF, HEIC, and many RAW formats. 4 RAW formats need improvement: CR2 (24.1%), CRW (7.0%), MOS (19.4%), DCR (9.9%).

---

**Copyright © 2025 DNAi inc.** All rights reserved.

**Dual-licensed under the DNAi Free License v1.1 and the DNAi Commercial License v1.1.**
