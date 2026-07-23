# Copyright 2026 FIQ AS, Loym AS
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFiqMultiCompany(TransactionCase):
    """Verifiserer at company_id finnes på alle fire modellene, og at den
    globale multi-company record-rulen faktisk skjermer per selskap."""

    def test_01_company_id_field_present(self):
        for model in ("crm.stage", "crm.lost.reason",
                      "mail.template", "res.partner.category"):
            self.assertIn(
                "company_id", self.env[model]._fields,
                "company_id mangler på %s" % model,
            )

    def test_02_record_rule_scopes_by_company(self):
        company_a = self.env["res.company"].create({"name": "FIQ Test A"})
        company_b = self.env["res.company"].create({"name": "FIQ Test B"})

        stage_a = self.env["crm.stage"].create(
            {"name": "Scoped A", "company_id": company_a.id}
        )
        stage_shared = self.env["crm.stage"].create({"name": "Delt"})

        user_b = self.env["res.users"].create({
            "name": "B-bruker",
            "login": "fiq_mc_test_b",
            "company_id": company_b.id,
            "company_ids": [(6, 0, [company_b.id])],
            "group_ids": [(6, 0, [self.env.ref("sales_team.group_sale_salesman").id])],
        })

        visible = self.env["crm.stage"].with_user(user_b).search([])
        self.assertIn(
            stage_shared, visible,
            "Delt stadium (company_id=False) skal være synlig for alle.",
        )
        self.assertNotIn(
            stage_a, visible,
            "Stadium scopet til selskap A skal IKKE være synlig for B-bruker.",
        )
