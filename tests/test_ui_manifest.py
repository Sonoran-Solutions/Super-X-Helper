import unittest

from superx_helper.ui_manifest import PAGES


class UiManifestTests(unittest.TestCase):
    def test_expected_pages_are_stable(self):
        self.assertEqual([page.page_id for page in PAGES], ["dashboard", "performance", "cooling", "display", "power", "storage", "profiles", "diagnostics"])


if __name__ == "__main__":
    unittest.main()
