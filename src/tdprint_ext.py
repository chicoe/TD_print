import os
import sys
import platform
import tempfile
import threading
import subprocess
import time
import traceback


class TDPrint:
    """
    TouchDesigner extension that prints the image from input 0 (a TOP)
    when the `Print` pulse parameter is pressed or when `Print()` is
    called from scripts. Designed to print silently using the default
    system printer unless a specific printer is provided.

    - macOS: uses `lp` with optional fit-to-page.
    - Windows: uses `mspaint /pt` to print to default or named printer.

    Wire a TOP into input 0 of the COMP that owns this extension.
    """

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self._log('TDPrint initialized for', getattr(ownerComp, 'path', ownerComp))
        try:
            self._log('Auto-refreshing printer list on init')
            self._refresh_printer_list()
        except Exception as e:
            self._log('Initial printer refresh failed:', e)

    # TouchDesigner may call this in some builds; not required. Removed param creation.
    # def onSetupParameters(self, page):  # noqa: N802 (TD API name)
    #     return

    # TouchDesigner calls this when a pulse parameter is pressed
    def onPulse(self, par):  # noqa: N802 (TD API name)
        self._log('onPulse called for parameter:', par.name)
        if par.name == 'Print':
            self._log('Print pulse received')
            return self.Print()
        elif par.name == 'Refreshprinters':
            self._log('Refresh printers pulse received')
            self._refresh_printer_list()
        return None

    def onEnable(self, enable):  # noqa: N802
        self._log('Extension onEnable:', enable)
        return

    def onOpCreate(self, op):  # noqa: N802
        self._log('onOpCreate:', getattr(op, 'path', op))
        return

    # Public API: trigger a print job
    def Print(self):  # noqa: N802 (public API)
        # Use Printerlist menu if set and not (refresh)
        printerlist_par = getattr(self.ownerComp.par, 'Printerlist', None)
        printerlist_val = printerlist_par.eval() if printerlist_par else ''
        self._log('Print() invoked')
        top = None
        try:
            # Prefer input 0 of the owner COMP
            if hasattr(self.ownerComp, 'inputOP'):
                top = self.ownerComp.inputOP(0)
            if top is None and getattr(self.ownerComp, 'inputs', None):
                top = self.ownerComp.inputs[0]
        except Exception:
            self._log_exc('Error retrieving input TOP')
            top = None

        if top is None:
            self._log('No TOP connected to input 0.')
            return
        else:
            try:
                w = getattr(top, 'width', 'unknown')
                h = getattr(top, 'height', 'unknown')
                self._log('Using TOP:', getattr(top, 'path', top), 'size:', w, 'x', h)
            except Exception:
                pass

        # Save TOP to a temporary PNG synchronously on the main thread
        tmp_path = self._save_top_to_temp_png(top)
        if not tmp_path:
            self._log('Failed to save TOP to a temporary file.')
            return
        self._log('Saved TOP to', tmp_path)

        # Capture parameters
        printer = getattr(self.ownerComp.par, 'Printer', None)
        printer = printer.eval().strip() if printer else ''
        if printerlist_val and printerlist_val != '(refresh)':
            printer = printerlist_val
        copies_par = getattr(self.ownerComp.par, 'Copies', None)
        copies = int(copies_par.eval()) if copies_par else 1
        copies = max(1, copies)
        fit_par = getattr(self.ownerComp.par, 'Fittopage', None)
        fit_to_page = bool(fit_par.eval()) if fit_par else True
        fill_par = getattr(self.ownerComp.par, 'Filltopage', None)
        fill_to_page = bool(fill_par.eval()) if fill_par else False
        orient_par = getattr(self.ownerComp.par, 'Orientation', None)
        orientation = orient_par.eval().strip().lower() if orient_par else 'auto'
        if orientation not in ('auto', 'portrait', 'landscape'):
            orientation = 'auto'
        self._log('Print settings → printer:', repr(printer), 'copies:', copies, 'fit_to_page:', fit_to_page, 'fill_to_page:', fill_to_page, 'orientation:', orientation)

        # Run the OS print in a background thread to avoid blocking TD
        t = threading.Thread(
            target=self._print_worker,
            args=(tmp_path, printer, copies, fit_to_page, fill_to_page, orientation, self._debug_enabled()),
            daemon=True,
        )
        t.start()
        self._log('Background print thread started')
        return True

    # Parameter auto-creation removed; component expects parameters created manually.

    def _refresh_printer_list(self):
        # Detect platform and query printers
        system = platform.system().lower()
        printers = []
        try:
            if 'darwin' in sys.platform or system == 'darwin' or system == 'mac':
                # macOS: lpstat -p
                out = subprocess.check_output(['lpstat', '-p'], universal_newlines=True)
                for line in out.splitlines():
                    if line.startswith('printer '):
                        name = line.split()[1]
                        printers.append(name)
            elif system == 'windows':
                # Windows: wmic printer get name
                try:
                    out = subprocess.check_output(['wmic', 'printer', 'get', 'name'], universal_newlines=True)
                    for line in out.splitlines()[1:]:
                        name = line.strip()
                        if name:
                            printers.append(name)
                except Exception:
                    # PowerShell fallback
                    ps = 'Get-Printer | Select-Object -ExpandProperty Name'
                    out = subprocess.check_output(['powershell', '-Command', ps], universal_newlines=True)
                    for line in out.splitlines():
                        name = line.strip()
                        if name:
                            printers.append(name)
            else:
                # POSIX fallback
                out = subprocess.check_output(['lpstat', '-p'], universal_newlines=True)
                for line in out.splitlines():
                    if line.startswith('printer '):
                        name = line.split()[1]
                        printers.append(name)
        except Exception as e:
            self._log('Printer list refresh failed:', e)
        # Always add (refresh) at top
        menuNames = ['(refresh)'] + printers
        menuLabels = ['(refresh)'] + printers
        try:
            printerlist_par = getattr(self.ownerComp.par, 'Printerlist', None)
            if printerlist_par:
                printerlist_par.menuNames = menuNames
                printerlist_par.menuLabels = menuLabels
                # Auto-select first detected printer if available
                if printers:
                    try:
                        printerlist_par.val = printers[0]
                    except Exception:
                        try:
                            printerlist_par.menuIndex = 1  # 0 is (refresh)
                        except Exception:
                            pass
                    self._log('Printer list updated; selected:', printers[0])
                else:
                    self._log('Printer list updated: no printers found')
        except Exception as e:
            self._log('Failed to update Printerlist menu:', e)
        # Only updates the Printerlist menu; does not launch print thread or extract print parameters

    def _save_top_to_temp_png(self, top):
        try:
            fd, path = tempfile.mkstemp(suffix='.png', prefix='tdprint_')
            os.close(fd)
            norm = os.path.normpath(path)
            # TouchDesigner TOP.save supports PNG by extension
            ok = top.save(norm)
            if not ok:
                try:
                    os.remove(norm)
                except Exception:
                    pass
                return None
            return norm
        except Exception as e:
            self._log('Error saving TOP:', e)
            self._log_exc('TOP save exception')
            return None

    def _print_worker(self, image_path, printer, copies, fit_to_page, fill_to_page, orientation, debug_enabled):
        try:
            system = platform.system().lower()
            self._tlog(debug_enabled, 'Print worker on system:', system, '| settings:', {'fit': fit_to_page, 'fill': fill_to_page, 'orientation': orientation})
            if 'darwin' in sys.platform or system == 'darwin' or system == 'mac':
                self._print_macos(image_path, printer, copies, fit_to_page, fill_to_page, orientation, debug_enabled)
            elif system == 'windows':
                self._print_windows(image_path, printer, copies, orientation, debug_enabled)
            else:
                # Fallback to CUPS if available
                self._print_posix(image_path, printer, copies, fit_to_page, fill_to_page, orientation, debug_enabled)
        finally:
            # Allow a short delay to ensure the printing app has opened the file
            time.sleep(2.0)
            try:
                os.remove(image_path)
                self._tlog(debug_enabled, 'Temporary file deleted:', image_path)
            except Exception:
                self._tlog(debug_enabled, 'Could not delete temporary file (might be in use):', image_path)

    def _print_macos(self, image_path, printer, copies, fit_to_page, fill_to_page, orientation, debug_enabled):
        # Use CUPS lp command; silent, no dialogs
        base_cmd = ['lp']
        if printer:
            base_cmd += ['-d', printer]
        if copies and copies > 1:
            base_cmd += ['-n', str(copies)]
        # Scaling options
        if fill_to_page:
            base_cmd += ['-o', 'print-scaling=fill']
        elif fit_to_page:
            base_cmd += ['-o', 'fit-to-page']
        # Orientation options (auto = no option)
        if orientation == 'landscape':
            base_cmd += ['-o', 'landscape']
        elif orientation == 'portrait':
            base_cmd += ['-o', 'landscape=false']
        cmd = base_cmd + [image_path]
        self._tlog(debug_enabled, 'macOS print command:', cmd)
        try:
            res = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self._tlog(debug_enabled, 'macOS print submitted. stdout:', res.stdout.decode('utf-8', 'ignore'))
        except Exception as e:
            self._tlog(debug_enabled, 'macOS print failed:', e)
            self._tlog_exc(debug_enabled, 'macOS print exception')

    def _print_posix(self, image_path, printer, copies, fit_to_page, fill_to_page, orientation, debug_enabled):
        # Generic POSIX path using lp
        self._print_macos(image_path, printer, copies, fit_to_page, fill_to_page, orientation, debug_enabled)

    def _print_windows(self, image_path, printer, copies, orientation, debug_enabled):
        # Prefer mspaint silent printing. Syntax:
        # mspaint /pt <file> [printer]
        # Copies are handled by repeating the command.
        if orientation in ('portrait', 'landscape'):
            self._tlog(debug_enabled, 'Windows: orientation cannot be set via mspaint; using printer defaults. Requested:', orientation)
        def run_once():
            try:
                if printer:
                    cmd = ['mspaint.exe', '/pt', image_path, printer]
                else:
                    cmd = ['mspaint.exe', '/pt', image_path]
                self._tlog(debug_enabled, 'Windows mspaint command:', cmd)
                res = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self._tlog(debug_enabled, 'mspaint submitted. stdout:', res.stdout.decode('utf-8', 'ignore'))
                return
            except Exception as e:
                self._tlog(debug_enabled, 'mspaint print failed, trying Photo Viewer:', e)
                self._tlog_exc(debug_enabled, 'mspaint exception')

            # Fallback to Windows Photo Viewer
            program_files = os.environ.get('ProgramFiles', r'C:\Program Files')
            program_files_x86 = os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')
            candidates = [
                os.path.join(program_files, 'Windows Photo Viewer', 'PhotoViewer.dll'),
                os.path.join(program_files_x86, 'Windows Photo Viewer', 'PhotoViewer.dll'),
            ]
            dll_path = next((p for p in candidates if os.path.exists(p)), candidates[0])
            dll_entry = dll_path + ',ImageView_PrintTo'
            rundll_cmd = ['rundll32.exe', dll_entry, image_path]
            if printer:
                rundll_cmd.append(printer)
            try:
                self._tlog(debug_enabled, 'Windows Photo Viewer command:', rundll_cmd)
                res = subprocess.run(rundll_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self._tlog(debug_enabled, 'Photo Viewer submitted. stdout:', res.stdout.decode('utf-8', 'ignore'))
            except Exception as e2:
                self._tlog(debug_enabled, 'Windows print failed (Photo Viewer fallback):', e2)
                self._tlog_exc(debug_enabled, 'Photo Viewer exception')

        for i in range(max(1, copies)):
            self._tlog(debug_enabled, 'Submitting copy', i + 1, 'of', copies)
            run_once()

    # ---------- debug helpers ----------
    def _debug_enabled(self):
        try:
            p = getattr(self.ownerComp.par, 'Debug', None)
            return bool(p.eval()) if p is not None else True
        except Exception:
            return True

    def _log(self, *args):
        if self._debug_enabled():
            try:
                print('[TDPrint]', *args)
            except Exception:
                pass

    def _log_exc(self, context=''):
        if self._debug_enabled():
            try:
                print('[TDPrint]', context)
                print(traceback.format_exc())
            except Exception:
                pass

    # Thread-safe logging (does not touch TD APIs)
    def _tlog(self, enabled, *args):
        if enabled:
            try:
                print('[TDPrint]', *args)
            except Exception:
                pass

    def _tlog_exc(self, enabled, context=''):
        if enabled:
            try:
                print('[TDPrint]', context)
                print(traceback.format_exc())
            except Exception:
                pass
