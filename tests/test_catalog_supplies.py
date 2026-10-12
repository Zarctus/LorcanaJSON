import io
import json
import unittest
from unittest.mock import patch

import GlobalConfig
from OutputGeneration import DataFilesGenerator
from util import Language, Translations


class CatalogSuppliesTests(unittest.TestCase):
    def test_supply_counters_are_excluded_before_card_preprocessing(self):
        for supplies_first in (True, False):
            with self.subTest(supplies_first=supplies_first):
                characters = [{
                    "culture_invariant_id": 1,
                    "card_identifier": "1/204 FR 1",
                    "rarity": "COMMON",
                }]
                supplies = [{
                    "culture_invariant_id": 3592,
                    "card_identifier": "FR 14",
                    "magic_ink_colors": [],
                }]
                categories = [("characters", characters), ("supplies", supplies)]
                if supplies_first:
                    categories.reverse()
                catalog = {"cards": dict(categories)}

                def open_input(path, *args, **kwargs):
                    return io.StringIO(json.dumps(catalog if str(path).endswith("carddata.fr.json") else {}))

                class PreprocessingComplete(Exception):
                    pass

                with (
                    patch.object(GlobalConfig, "language", Language.FRENCH),
                    patch.object(GlobalConfig, "translation", Translations.FRENCH),
                    patch.object(GlobalConfig, "useCachedOcr", True),
                    patch.object(GlobalConfig, "skipOcrCache", False),
                    patch("builtins.open", side_effect=open_input),
                    patch.object(DataFilesGenerator.os.path, "isdir", return_value=True),
                    patch.object(DataFilesGenerator.os.path, "isfile", side_effect=lambda path: str(path).endswith("carddata.fr.json")),
                    patch.object(DataFilesGenerator.OcrCacheHandler, "getCachedOcrResult", return_value=object()) as cached_ocr,
                    patch.object(DataFilesGenerator, "AllowedInFormatsHandler", side_effect=PreprocessingComplete),
                ):
                    with self.assertRaises(PreprocessingComplete):
                        DataFilesGenerator.createOutputFiles()

                self.assertEqual([call.args[0] for call in cached_ocr.call_args_list], [1])


if __name__ == "__main__":
    unittest.main()
