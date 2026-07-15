from freezegun import freeze_time
from psycopg2 import IntegrityError

from odoo import fields
from odoo.tests import Form
from odoo.tests.common import TransactionCase, new_test_user, users
from odoo.tools import mute_logger


@freeze_time("2023-01-01 12:00:00")
class TestProjectProject(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prj_seq = cls.env['ir.sequence'].search(
            [('code', '=', "project.sequence"), '|', ('company_id', '=', cls.env.company.id), ('company_id', '=', False)],
            order='company_id desc',  # company-specific first, then global
            limit=1
        )
        cls.prj_seq.write(
            {
                "name": "Project sequence",
                "code": "project.sequence",
                "prefix": "%(y)s-",
                "use_date_range": True,
                "padding": 5,
                "company_id": False,
            }
        )

    def setUp(self):
        super().setUp()
        self.prj_seq._get_current_sequence().number_next = 11

    def test_internal_external(self):
        project = self.env["project.project"].create(
            {"name": "Test Project", "internal_external": "e"}
        )
        self.assertEqual(project.sequence_code, "Pe23-00011")
        project.sequence_sequence = None
        self.assertEqual(project.sequence_code, False) # Do not accept ""
        project.set_sequence_field_and_name()
        self.assertEqual(project.sequence_code, "Pe23-00012")
