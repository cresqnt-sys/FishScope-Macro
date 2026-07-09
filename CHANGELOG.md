# FishScope 2.4
- Stable release including all beta improvements and fish database updates.
### Added
- Updated fish database with new fish species and corrected rarities
- Dynamic sell-all count based on amount of fish in database
- Legendary rarity color support for webhook notifications
- Credited vex in footer (thanks vex!)
- Configuration file now saves to %APPDATA%/FishScope instead of the folder in which FS is executed in

### Changed
- Fish data now syncs with the latest version from GitHub on startup
- Improved auto-reconnect
- Changed some user interface colors
- Made user interface more consistent

### Fixed
- Guard against duplicate start/stop calls

---

# FishScope 2.4-Beta3
- Refined timing and version comparison improvements.
### Added
- Version comparison now handles pre-release labels (Beta, Alpha, RC) correctly

### Changed
- Reduced backslash sequence delay from 60s to 30s
- Increased auto-align camera delays for more reliable alignment

### Fixed
- Fixed up arrow emoji rendering in reconnect debug output

---

# FishScope 2.4-Beta2
- Major update fixing many bugs and adding many improvements. The macro is now up to 3x better than it was before for fishing.
### Added
- Reworked and improved major aspects of Auto Reconnect
- Improved error handling and fallback mechanisms for Roblox launching
### Changed
- Code formatting improvements with consistent spacing around operators
- Change Auto Reconnect to work with Sols RNG Eon 1-10
- Added a 2 second reset delay cause of Roblox's new update
- Reworked Fishing MiniGame Logic
- Made FishScope up to 3x better on lower end PCs than before. (Tested on Dell Inspiron 3670 | Intel Core i5 8th Gen | iGPU)

### Fixed
- Minor build and packaging issues
- Update check compatibility with pre-release tag names

---

# FishScope 2.4-Beta1
-# Beta release providing early access to 2.4 features and stability improvements.
### Added
- Beta updater improvements and clearer update dialog
- Indicator showing current build as Beta
- Improved build packaging metadata

### Changed
- Bumped product and file version to 2.4.0.0
- Updater now identifies as `2.4-Beta1`

### Fixed
- Minor build and packaging issues
- Update check now supports tag names that include pre-release labels

---

# FishScope 2.3
-# A major update featuring many requested features and many bug fixes.
### Added
- New OOTB (Out-Of-The-Box) Calibrations
- Server for updating calibrations without updating the whole macro
- Non VIP Support
- Toggleable delay for auto reconnect "click play"

### Changed
- GUI options and order
- Camera angle handling
- Auto reconnect kill and start method

### Fixed
- Many Auto Reconnect Bugs
- One memory leak
- Other minor issues
- Updater Bug

Tutorial: https://youtu.be/XgNnymJ-26E
Download: https://github.com/cresqnt-sys/FishScope-Macro/releases/tag/2.3
