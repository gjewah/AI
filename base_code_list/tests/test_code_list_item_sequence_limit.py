from odoo.exceptions import ValidationError
from odoo.tests.common import SavepointCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestCodeListItemSequenceLimit(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CodeList = cls.env["code.list"]
        cls.CodeListItem = cls.env["code.list.item"]

    def _create_list(self, compute_item_codes=True, sequence_separator=""):
        return self.CodeList.create(
            {
                "name": "Test List",
                "compute_item_codes": compute_item_codes,
                "sequence_separator": sequence_separator,
            }
        )

    def test_allow_nine_siblings_without_separator(self):
        code_list = self._create_list(compute_item_codes=True, sequence_separator="")

        for i in range(1, 10):
            self.CodeListItem.create(
                {
                    "name": f"Item {i}",
                    "list_id": code_list.id,
                }
            )

        self.assertEqual(
            self.CodeListItem.search_count(
                [("list_id", "=", code_list.id), ("parent_id", "=", False)]
            ),
            9,
        )

    def test_block_tenth_sibling_without_separator(self):
        code_list = self._create_list(compute_item_codes=True, sequence_separator="")

        for i in range(1, 10):
            self.CodeListItem.create(
                {
                    "name": f"Item {i}",
                    "list_id": code_list.id,
                }
            )

        with self.assertRaises(ValidationError):
            self.CodeListItem.create(
                {
                    "name": "Item 10",
                    "list_id": code_list.id,
                }
            )

    def test_block_switch_to_empty_separator_with_more_than_nine(self):
        code_list = self._create_list(compute_item_codes=False, sequence_separator=".")

        for i in range(1, 11):
            self.CodeListItem.create(
                {
                    "name": f"Item {i}",
                    "list_id": code_list.id,
                }
            )

        with self.assertRaises(ValidationError):
            code_list.write(
                {
                    "compute_item_codes": True,
                    "sequence_separator": "",
                }
            )
