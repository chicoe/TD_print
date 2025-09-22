TD_print (.tox)
================

Silent printer for TouchDesigner. Accepts a TOP on input 0 and, when triggered, prints the image directly to your system printer without showing any dialogs. Works on macOS and Windows.

Parameters
----------
- Printer: Optional printer name. Leave empty to use the system default printer.
- Copies: Number of copies to print (minimum 1).
- Fit To Page: Scale the image to fit the page (macOS/Posix only; ignored on Windows).
- Print Now: Pulse to immediately print the current image from input 0.
- Debug: Enables verbose logs in the Textport for troubleshooting.