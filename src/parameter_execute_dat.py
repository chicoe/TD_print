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
    if par.name == 'Print':
        try:
            debug('[TDPrint] Parameter Execute: Print pulse caught on {}'.format(par.owner.path))
            op('..').ext.TDPrint.Print()
        except Exception as e:
            debug('[TDPrint] Parameter Execute error: {}'.format(e))
    return
