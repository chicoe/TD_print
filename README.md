TD_print (.tox)
================

Silent printer for TouchDesigner. Accepts a TOP on input 0 and, when the "Print Now" pulse parameter is pressed, prints the image directly to your system printer without showing any dialogs. Works on macOS and Windows.

Parameters
----------
- Printer List: Dropdown of detected printers. Select to set the target printer.
- Refresh Printers: Pulse to rescan and populate the Printer List.
- Printer: Optional manual printer name. Leave empty to use the system default printer.
- Copies: Number of copies to print (minimum 1).
- Fit To Page: Scale the image to fit the page (macOS/Posix only; ignored on Windows).
- Fill To Page: Scale the image to fill the page (macOS/Posix only; may crop edges).
- Orientation: Page orientation: Auto, Portrait, or Landscape (macOS/Posix only; Windows uses printer defaults).
- Print Now: Pulse to immediately print the current image from input 0.
- Debug: Enables logs in the Textport for troubleshooting.