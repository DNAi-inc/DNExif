# Changelog

All notable changes to DNExif will be documented in this file.

## December 12, 2025 - License Update and Project Consolidation

### License and Copyright Updates

**Major Change**: Updated project licensing from Apache License 2.0 to dual-license model.

1. **License Header Updates**:
   - ✅ Updated all 136 Python source files in `dnexif/` directory with new DNAi license headers
   - ✅ Added license headers as comments at the top of each file:
     ```python
     # Copyright 2025 DNAi inc.
     #
     # Dual-licensed under the DNAi Free License v1.1 and the
     # DNAi Commercial License v1.1.
     # See the LICENSE files in the project root for details.
     ```
   - ✅ Removed Apache License text from docstrings while preserving module descriptions
   - ✅ Maintained code structure and functionality

2. **License Files**:
   - ✅ `LICENSE`: DNAi Free License v1.1 (for non-commercial use)
   - ✅ `LICENSE-COMMERCIAL`: DNAi Commercial License v1.1 (for commercial use)
   - ✅ Both license files present in project root

3. **Documentation Updates**:
   - ✅ Updated `README.md` with comprehensive dual-license information
   - ✅ Added license precedence information
   - ✅ Updated contributing section with license grant notice
   - ✅ Enhanced feature documentation with advanced capabilities

### Project Status Summary

**Current Version**: 0.1.3

**Format Support**:
- ✅ **120+ file formats** supported for reading
- ✅ **36 formats verified** with comprehensive tag extraction
- ✅ Full write support for JPEG, TIFF, PNG, WebP, GIF, HEIC, and many RAW formats
- ⚠️ 4 RAW formats need improvement: CR2 (24.1%), CRW (7.0%), MOS (19.4%), DCR (9.9%)

**Key Features Implemented**:
- ✅ 100% Pure Python implementation (no external dependencies)
- ✅ EXIF, IPTC, and XMP metadata support
- ✅ Metadata normalization and conflict resolution
- ✅ Privacy-focused metadata stripping with PII detection
- ✅ Metadata diffing and comparison tools
- ✅ Image hash calculation for integrity verification
- ✅ Batch processing capabilities
- ✅ Comprehensive MakerNote parsing (Canon, Nikon, Sony, Fujifilm, Olympus, Panasonic, Pentax, Samsung, and more)

**Format Verification Status** (36 formats with comprehensive tag extraction):
1. ORF: 255 tags
2. RAF: 260 tags
3. PEF: 273 tags
4. TIFF: 68 tags
5. PNG: 48 tags
6. DNG: 252 tags
7. MRW: 24 tags
8. SRW: 213 tags
9. JPEG: 253 tags
10. WebP: 38 tags
11. GIF: 45 tags
12. HEIC: 172 tags
13. HEIF: 162 tags
14. 3FR: 149 tags
15. ERF: 24 tags
16. MEF: 158 tags
17. NEF: 342 tags
18. RW2: 348 tags
19. NRW: 292 tags
20. ICO: 43 tags
21. PSD: 41 tags
22. SVG: 46 tags
23. TGA: 44 tags
24. GPX: 107 tags
25. PDF: 112 tags
26. XCF: 39 tags
27. MNG: 43 tags
28. WBMP: 41 tags
29. XBM: 37 tags
30. PCX: 45 tags
31. XPM: 39 tags
32. XWD: 59 tags
33. SGI: 46 tags
34. RAS: 43 tags
35. RAR: 35 tags
36. 7Z: 33 tags

**Remaining Formats Needing Improvement**:
- CR2: 27.0% (85/315 tags matched) - Needs sub-IFD parsing improvements
- MOS: 19.4% (30/155 tags matched) - Needs parser improvements
- X3F: 98.1% (158/160 tags) - Essentially complete
- CRW: 6.2% (32/178 tags) - Needs HEAP-based format parsing
- DCR: 9.9% (183/484 tags) - Needs parser improvements
- ZIP: 0.0% (0/18 tags) - Needs improvement

### Documentation Improvements

1. **README.md Enhancements**:
   - ✅ Updated license section with comprehensive dual-license information
   - ✅ Added detailed feature documentation including advanced capabilities
   - ✅ **Added extensive DICOM documentation** highlighting comprehensive medical imaging support:
     - Dedicated DICOM section in metadata standards
     - Expanded DICOM coverage in specialized formats section
     - Detailed capabilities (5,200+ data elements, private tags, sequence parsing)
   - ✅ Expanded format support documentation (120+ formats)
   - ✅ Added code examples for advanced features (normalization, stripping, diffing, batch operations)
   - ✅ Added API reference section with key modules
   - ✅ Updated contributing section with license grant information

2. **GitHub Wiki Documentation**:
   - ✅ Created comprehensive wiki structure with 8+ documentation pages
   - ✅ **Created dedicated DICOM-Support.md page** with comprehensive medical imaging guide:
     - 5,200+ DICOM data elements documentation
     - Private tag registry details (GE Medical Systems, etc.)
     - Sequence parsing capabilities
     - Byte order and Value Representation support
     - Usage examples and CLI commands
   - ✅ Updated Features.md with expanded DICOM section
   - ✅ Updated Supported-Formats.md with detailed DICOM capabilities
   - ✅ Updated Home.md with DICOM highlights

3. **Code Documentation**:
   - ✅ All source files include proper license headers
   - ✅ Module docstrings preserved and enhanced
   - ✅ Professional code structure maintained

### Project Maintenance

**Git Configuration**:
- ✅ Updated `.gitignore` to exclude:
  - `__pycache__/` directories
  - `.claude/` directory
  - `.pytest_cache/` directory
  - `.venv/` and `venv/` directories
  - `tests/` directory
  - `pyproject.toml` and `setup.py` files

### Technical Achievements

**Architecture**:
- 100% pure Python stack—no subprocess calls, no binary bindings
- Direct parsing of TIFF/EXIF structures, IPTC APP13 segments, and embedded XMP packets
- Unified metadata object model merging EXIF, IPTC, XMP, MakerNotes, composite values, GPS composites, and vendor namespaces

**Metadata Standards Support**:
- EXIF 2.x/3.0 tag coverage including GPS, interoperability, makernote namespaces, and UTF-8 text tags
- IPTC IIM segments with write support
- XMP namespace parser (dc, xmp, xmpMM, xmpDM, photoshop, tiff, exif, aux, lr, plus vendor-specific)
- **DICOM Standard PS3.6 compliance** with 5,200+ data elements, comprehensive private tag registry (GE Medical Systems, etc.), sequence parsing, and full VR support

**Advanced Features**:
- Metadata normalization with conflict resolution
- Privacy-focused metadata stripping with configurable presets (minimal, standard, strict)
- PII detection capabilities
- Metadata diffing and comparison
- Image hash calculation for integrity verification
- Batch processing operations

### Next Steps

**Immediate Priorities**:
1. Continue incremental improvements to remaining RAW formats (CR2, MOS, CRW, DCR)
2. Focus on formats closest to completion (X3F at 98.1%)
3. Investigate proprietary format structures for improved parsing
4. Comprehensive file type testing and write verification

**Long-term Goals**:
- Achieve comprehensive format support for all formats
- Enhance write support for additional formats
- Improve performance for batch operations
- Expand test coverage

### Files Modified

**License Headers Updated** (136 files):
- All Python files in `dnexif/` directory

**Documentation Updated**:
- `README.md` - Comprehensive updates with license and feature information
- `CHANGES.md` - Consolidated into single entry
- `.gitignore` - Updated exclusion patterns

**License Files**:
- `LICENSE` - DNAi Free License v1.1
- `LICENSE-COMMERCIAL` - DNAi Commercial License v1.1

---

**Copyright © 2025 DNAi inc.** All rights reserved.

**Dual-licensed under the DNAi Free License v1.1 and the DNAi Commercial License v1.1.**
