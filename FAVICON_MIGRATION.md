# Favicon Migration Guide

## Current Status

The favicon has been properly organized for the GURU project.

## File Locations

### ✅ Correct Locations (Production)
```
desktop-agent/tray-app/dist/favicon.ico          # Web application favicon
desktop-agent/tray-app/dist/assets/favicon.ico   # Assets directory (backup)
desktop-agent/tray-app/src-tauri/icons/icon.ico  # Windows application icon
```

### ⚠️ Legacy Location (To Be Removed)
```
favicon.ico  # Root directory (legacy, should be removed after verification)
```

## Migration Steps Completed

1. ✅ Copied favicon.ico to `desktop-agent/tray-app/dist/`
2. ✅ Copied favicon.ico to `desktop-agent/tray-app/dist/assets/`
3. ✅ Updated `index.html` to reference favicon
4. ✅ Created comprehensive ASSETS.md documentation

## Next Steps

### Immediate Actions
1. **Verify the favicon displays correctly** in the tray application
2. **Test on all target platforms** (Windows, macOS, Android, iOS)
3. **Remove root favicon.ico** after verification (optional, can keep as source)

### Future Enhancements
1. **Generate multi-resolution favicon.ico** with 16x16, 32x32, 48x48 sizes
2. **Create PNG versions** for better quality on modern browsers
3. **Add SVG favicon** for perfect scaling
4. **Generate platform-specific icons** using Tauri icon CLI

## Verification Checklist

- [ ] Favicon displays in browser tab when tray app is open
- [ ] Favicon displays correctly on Windows
- [ ] Favicon displays correctly on macOS (if applicable)
- [ ] Favicon displays correctly on Android (if applicable)
- [ ] Favicon displays correctly on iOS (if applicable)
- [ ] No console errors related to favicon loading
- [ ] Favicon displays on high-DPI displays (Retina, 4K)

## Recommended Favicon Specifications

### Modern Best Practice
```html
<!-- In <head> section of index.html -->
<link rel="icon" type="image/x-icon" href="favicon.ico">
<link rel="icon" type="image/png" sizes="32x32" href="assets/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="assets/favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="assets/apple-touch-icon.png">
<link rel="manifest" href="site.webmanifest">
```

### File Sizes
- **favicon.ico**: Multi-resolution (16x16, 32x32, 48x48) - ~15-30 KB
- **favicon-16x16.png**: 16x16 pixels - ~1-2 KB
- **favicon-32x32.png**: 32x32 pixels - ~2-4 KB
- **apple-touch-icon.png**: 180x180 pixels - ~10-20 KB

## Generating Optimal Favicons

### Using Online Tools
1. Visit https://realfavicongenerator.net/
2. Upload your source image (minimum 512x512 PNG)
3. Configure platform-specific settings
4. Download generated package
5. Extract to `desktop-agent/tray-app/dist/assets/`

### Using Tauri Icon CLI
```bash
# From project root
cd desktop-agent/tray-app/src-tauri
cargo tauri icon path/to/source-icon.png

# This generates all platform icons automatically
```

### Using ImageMagick (Manual)
```bash
# Generate ICO with multiple resolutions
convert source.png -define icon:auto-resize=16,32,48 favicon.ico

# Generate PNG versions
convert source.png -resize 16x16 favicon-16x16.png
convert source.png -resize 32x32 favicon-32x32.png
convert source.png -resize 180x180 apple-touch-icon.png
```

## Platform-Specific Considerations

### Windows
- **ICO format required** for native Windows applications
- **32x32 PNG** for system tray icon
- **Multiple resolutions** in ICO for different contexts

### macOS
- **ICNS format** for native macOS applications
- **Retina support** requires @2x versions
- **Transparency** supported and recommended

### Android
- **PNG format** with transparency
- **Adaptive icons** (foreground + background layers)
- **Multiple densities** (mdpi, hdpi, xhdpi, xxhdpi, xxxhdpi)

### iOS
- **PNG format** without transparency (Apple requirement)
- **Multiple sizes** required (20x20 to 1024x1024)
- **Rounded corners** applied automatically by iOS

## Troubleshooting

### Favicon Not Displaying
1. Clear browser cache (Ctrl+Shift+Delete)
2. Hard refresh (Ctrl+F5)
3. Check browser console for 404 errors
4. Verify file path is correct
5. Check file permissions

### Favicon Blurry
1. Ensure source image is high resolution (minimum 512x512)
2. Generate proper multi-resolution ICO
3. Provide PNG versions for modern browsers
4. Test on high-DPI displays

### Favicon Wrong Color
1. Check color space (should be sRGB)
2. Verify transparency is correct
3. Test on light and dark browser themes
4. Consider providing theme-specific favicons

## Cleanup Commands

### Remove Root Favicon (After Verification)
```bash
# Windows PowerShell
Remove-Item "favicon.ico"

# Linux/macOS
rm favicon.ico
```

### Verify All Favicon Locations
```bash
# Windows PowerShell
Get-ChildItem -Recurse -Filter "favicon*"

# Linux/macOS
find . -name "favicon*"
```

## Documentation References

- [ASSETS.md](desktop-agent/tray-app/dist/assets/ASSETS.md) - Complete assets documentation
- [Tauri Icons Guide](https://tauri.app/v1/guides/features/icons)
- [Favicon Cheat Sheet](https://github.com/audreyfeldroy/favicon-cheat-sheet)

## Status

**Migration Status**: ✅ Complete
**Verification Status**: ⏳ Pending
**Cleanup Status**: ⏳ Pending (optional)

---

**Created**: January 15, 2026
**Last Updated**: January 15, 2026
**Maintained By**: GURU Development Team
