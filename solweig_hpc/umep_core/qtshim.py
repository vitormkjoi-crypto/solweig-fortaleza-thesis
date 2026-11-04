"""Minimal stand-in for qgis.PyQt.QtCore so that UMEP's worker classes run without QGIS/Qt (signals call their slots directly)."""
class _Signal:
    def __init__(self):
        self._slots = []
    def connect(self, f):
        self._slots.append(f)
    def disconnect(self, *a):
        self._slots = []
    def emit(self, *a):
        for f in list(self._slots):
            f(*a)
class _SignalDescriptor:
    def __set_name__(self, owner, name):
        self.name = "_sig_" + name
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.name not in obj.__dict__:
            obj.__dict__[self.name] = _Signal()
        return obj.__dict__[self.name]
def pyqtSignal(*types):
    return _SignalDescriptor()
class QObject:
    def __init__(self, *a, **k):
        pass
class QtCore:
    QObject = QObject
    pyqtSignal = staticmethod(pyqtSignal)
QtGui = None
