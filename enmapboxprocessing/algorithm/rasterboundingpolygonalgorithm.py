from typing import Dict, Any, List, Tuple

import numpy as np

from enmapbox.typeguard import typechecked
from enmapboxprocessing.driver import Driver
from enmapboxprocessing.enmapalgorithm import EnMAPProcessingAlgorithm, Group
from enmapboxprocessing.rasterreader import RasterReader
from enmapboxprocessing.utils import Utils
from qgis.core import (QgsProcessingContext, QgsProcessingFeedback)


@typechecked
class RasterBoundingPolygonAlgorithm(EnMAPProcessingAlgorithm):
    P_RASTER, _RASTER = 'raster', 'Raster layer'
    P_OUTPUT_VECTOR, _OUTPUT_VECTOR = 'outputVector', 'Output vector layer'

    def displayName(self) -> str:
        return 'Raster layer bounding polygon'

    def shortDescription(self) -> str:
        return 'Compute raster layer bounding polygon that encloses all data pixel.'

    def helpParameters(self) -> List[Tuple[str, str]]:
        return [
            (self._RASTER, 'A raster layer used for bounding polygon calculation.'),
            (self._OUTPUT_VECTOR, self.VectorFileDestination)
        ]

    def group(self):
        return Group.RasterMiscellaneous.value

    def initAlgorithm(self, configuration: Dict[str, Any] = None):
        self.addParameterRasterLayer(self.P_RASTER, self._RASTER)
        self.addParameterVectorDestination(self.P_OUTPUT_VECTOR, self._OUTPUT_VECTOR)

    def processAlgorithm(
            self, parameters: Dict[str, Any], context: QgsProcessingContext, feedback: QgsProcessingFeedback
    ) -> Dict[str, Any]:
        raster = self.parameterAsRasterLayer(parameters, self.P_RASTER, context)
        filename = self.parameterAsOutputLayer(parameters, self.P_OUTPUT_VECTOR, context)

        with open(filename + '.log', 'w') as logfile:
            feedback, feedback2 = self.createLoggingFeedback(feedback, logfile)
            self.tic(feedback, parameters, context)

            filenameMask = Utils().tmpFilename(filename, 'mask.tif')
            filenamePolygon = Utils().tmpFilename(filename, 'polygon.gpkg')

            reader = RasterReader(raster)
            array = reader.array()
            mask = np.any(reader.maskArray(array), 0, keepdims=True)
            writer = Driver(filenameMask).createFromArray(mask, reader.extent(), reader.crs())
            writer.close()
            del writer

            # vectorize binary mask
            alg = 'gdal:polygonize'
            parameters = {
                'INPUT': filenameMask,
                'BAND': 1,
                'FIELD': 'DN',
                'EIGHT_CONNECTEDNESS': False,
                'EXTRA': '-mask ' + filenameMask,
                'OUTPUT': filenamePolygon
            }
            self.runAlg(alg, parameters, None, feedback2, context, True)

            # simplify to convex hull polygon
            alg = 'native:convexhull'
            parameters = {
                'INPUT': filenamePolygon,
                'OUTPUT': filename
            }
            self.runAlg(alg, parameters, None, feedback2, context, True)

            result = {self.P_OUTPUT_VECTOR: filename}
            self.toc(feedback, result)

        return result
