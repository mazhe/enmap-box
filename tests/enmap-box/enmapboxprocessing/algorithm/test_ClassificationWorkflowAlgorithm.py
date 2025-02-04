from sklearn.base import ClassifierMixin

from enmapboxprocessing.algorithm.prepareclassificationdatasetfromcategorizedvectoralgorithm import \
    PrepareClassificationDatasetFromCategorizedVectorAlgorithm
from enmapboxtestdata import enmap, landcover_potsdam_point, enmap_potsdam
from enmapboxprocessing.algorithm.classificationworkflowalgorithm import ClassificationWorkflowAlgorithm
from enmapboxprocessing.algorithm.fitclassifieralgorithmbase import FitClassifierAlgorithmBase
from enmapboxprocessing.algorithm.testcase import TestCase
from enmapboxtestdata import classifierDumpPkl


class FitTestClassifierAlgorithm(FitClassifierAlgorithmBase):

    def displayName(self) -> str:
        return ''

    def shortDescription(self) -> str:
        return ''

    def helpParameterCode(self) -> str:
        return ''

    def code(self) -> ClassifierMixin:
        from sklearn.ensemble import RandomForestClassifier
        classifier = RandomForestClassifier(n_estimators=10, oob_score=True, random_state=42)
        return classifier


class TestClassificationAlgorithm(TestCase):

    def test(self):
        alg = ClassificationWorkflowAlgorithm()
        parameters = {
            alg.P_DATASET: classifierDumpPkl,
            alg.P_CLASSIFIER: FitTestClassifierAlgorithm().defaultCodeAsString(),
            alg.P_RASTER: enmap,
            alg.P_NFOLD: 10,
            alg.P_OPEN_REPORT: self.openReport,
            alg.P_OUTPUT_CLASSIFIER: self.filename('classifier.pkl'),
            alg.P_OUTPUT_CLASSIFICATION: self.filename('classification.tif'),
            alg.P_OUTPUT_PROBABILITY: self.filename('probability.tif'),
            alg.P_OUTPUT_REPORT: self.filename('report.html')
        }
        self.runalg(alg, parameters)

    def _DISABLED_test_trainingOnly(self):
        alg = ClassificationWorkflowAlgorithm()
        parameters = {
            alg.P_DATASET: classifierDumpPkl,
            alg.P_CLASSIFIER: FitTestClassifierAlgorithm().defaultCodeAsString(),
            alg.P_OUTPUT_CLASSIFIER: self.filename('classifier.pkl'),
        }
        self.runalg(alg, parameters)

    def test_badBandsHandling_withNameMatching(self):

        alg1 = PrepareClassificationDatasetFromCategorizedVectorAlgorithm()
        parameters1 = {
            alg1.P_CATEGORIZED_VECTOR: landcover_potsdam_point,
            alg1.P_FEATURE_RASTER: enmap_potsdam,
            alg1.P_EXCLUDE_BAD_BANDS: True,
            alg1.P_OUTPUT_DATASET: self.filename('dataset.pkl')
        }
        self.runalg(alg1, parameters1)

        alg2 = ClassificationWorkflowAlgorithm()
        parameters2 = {
            alg2.P_DATASET: parameters1[alg1.P_OUTPUT_DATASET],
            alg2.P_CLASSIFIER: FitTestClassifierAlgorithm().defaultCodeAsString(),
            alg2.P_RASTER: enmap_potsdam,
            alg2.P_MATCH_BY_NAME: True,
            alg2.P_OUTPUT_CLASSIFIER: self.filename('classifier.pkl'),
            alg2.P_OUTPUT_CLASSIFICATION: self.filename('classification.tif'),
            alg2.P_OUTPUT_PROBABILITY: self.filename('probability.tif')
        }
        self.runalg(alg2, parameters2)

    def test_badBandsHandling_withoutNameMatching(self):

        alg1 = PrepareClassificationDatasetFromCategorizedVectorAlgorithm()
        parameters1 = {
            alg1.P_CATEGORIZED_VECTOR: landcover_potsdam_point,
            alg1.P_FEATURE_RASTER: enmap_potsdam,
            alg1.P_EXCLUDE_BAD_BANDS: True,
            alg1.P_OUTPUT_DATASET: self.filename('dataset.pkl')
        }
        self.runalg(alg1, parameters1)

        alg2 = ClassificationWorkflowAlgorithm()
        parameters2 = {
            alg2.P_DATASET: parameters1[alg1.P_OUTPUT_DATASET],
            alg2.P_CLASSIFIER: FitTestClassifierAlgorithm().defaultCodeAsString(),
            alg2.P_RASTER: enmap_potsdam,
            alg2.P_MATCH_BY_NAME: False,
            alg2.P_OUTPUT_CLASSIFIER: self.filename('classifier.pkl'),
            alg2.P_OUTPUT_CLASSIFICATION: self.filename('classification.tif'),
            alg2.P_OUTPUT_PROBABILITY: self.filename('probability.tif')
        }
        self.runalg(alg2, parameters2)
