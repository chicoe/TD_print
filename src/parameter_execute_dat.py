try:
    op  # type: ignore  # noqa: F821
except Exception:
    def op(_):
        raise RuntimeError("TouchDesigner 'op' not available outside TD")

try:
    debug  # type: ignore  # noqa: F821
except Exception:
    def debug(msg):
        print(msg)


def onPulse(par):
    try:
        if par.name == 'Print':
            debug('[TDPrint] Parameter Execute: Print pulse caught on {}'.format(par.owner.path))
            op('..').ext.TDPrint.Print()
        elif par.name == 'Refreshprinters':
            debug('[TDPrint] Parameter Execute: Refresh printers pulse on {}'.format(par.owner.path))
            op('..').ext.TDPrint._refresh_printer_list()
    except Exception as e:
        debug('[TDPrint] Parameter Execute error: {}'.format(e))
    return
