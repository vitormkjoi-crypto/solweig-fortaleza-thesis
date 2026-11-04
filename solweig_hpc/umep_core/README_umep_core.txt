These modules are copied from the UMEP QGIS plugin (UMEP-dev team, GPL-3, https://github.com/UMEP-dev/UMEP) with only these edits:
qgis.PyQt imports replaced by qtshim.py, osgeo/GDAL removed from solweigworker.py (saveraster now calls a writer object), and
scipy.ndimage.interpolation -> scipy.ndimage. Lindberg et al. (2008) SOLWEIG; Lindberg et al. (2018) UMEP.
