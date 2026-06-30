# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, new_test_user


class TestFiqHovedmeny(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Config = self.env["fiq.hovedmeny.config"]
        self.action = self.env.ref("fiq_hovedmeny.action_fiq_hovedmeny")

    def test_groups_exist_and_hierarchy(self):
        gu = self.env.ref("fiq_hovedmeny.group_user")
        gm = self.env.ref("fiq_hovedmeny.group_manager")
        ga = self.env.ref("fiq_hovedmeny.group_admin")
        self.assertTrue(gu and gm and ga)
        # Leder arver Bruker; Admin arver Leder
        self.assertIn(gu, gm.implied_ids)
        self.assertIn(gm, ga.implied_ids)
        # Alle interne brukere (base.group_user) får Hovedmeny-Bruker
        self.assertIn(gu, self.env.ref("base.group_user").implied_ids)

    def test_get_my_config_creates_and_returns(self):
        cfg = self.Config.get_my_config()
        for key in ("show", "level", "is_admin", "company_name", "accent"):
            self.assertIn(key, cfg)
        self.assertEqual(set(cfg["show"].keys()),
                         {"kpis", "projects", "kommunikasjon", "activity", "tasks", "chart", "copilot", "quick"})
        self.assertTrue(self.Config.search([("user_id", "=", self.env.uid)]))

    def test_set_widget_persists(self):
        self.Config.get_my_config()
        self.Config.set_widget("kpis", False)
        rec = self.Config.search(
            [("user_id", "=", self.env.uid), ("company_id", "=", self.env.company.id)], limit=1)
        self.assertFalse(rec.show_kpis)
        self.Config.set_widget("kpis", True)
        self.assertTrue(rec.show_kpis)

    def test_unique_per_user_company(self):
        self.Config.get_my_config()
        # andre kall gir samme record (ikke duplikat)
        n = self.Config.search_count(
            [("user_id", "=", self.env.uid), ("company_id", "=", self.env.company.id)])
        self.Config.get_my_config()
        self.assertEqual(
            self.Config.search_count(
                [("user_id", "=", self.env.uid), ("company_id", "=", self.env.company.id)]), n)

    def test_record_rule_isolation(self):
        userA = new_test_user(self.env, login="hm_a", groups="fiq_hovedmeny.group_user")
        userB = new_test_user(self.env, login="hm_b", groups="fiq_hovedmeny.group_user")
        self.Config.with_user(userA).get_my_config()
        # B skal ikke se A sitt oppsett
        seen_by_b = self.Config.with_user(userB).search([])
        self.assertFalse(seen_by_b.filtered(lambda c: c.user_id == userA))

    def test_get_kommunikasjon_shape_and_direction(self):
        # Logg en melding på et prosjekt → skal dukke opp med retning + avsender
        proj = self.env["project.project"].create({"name": "HM Komm Test"})
        proj.message_post(body="Hei", message_type="comment")
        rows = self.Config.get_kommunikasjon("alle", 50)
        self.assertIsInstance(rows, list)
        if rows:
            r = rows[0]
            for key in ("id", "kind", "author", "author_id", "direction",
                        "subject", "date", "model", "res_id", "element"):
                self.assertIn(key, r)
            self.assertIn(r["direction"], ("sendt", "mottatt"))

    def test_get_dashboards_only_existing_xmlids(self):
        rows = self.Config.get_dashboards()
        self.assertIsInstance(rows, list)
        for r in rows:
            self.assertIn("xmlid", r)
            self.assertIn("label", r)
            # Hver returnert xmlid MÅ faktisk resolve (env.ref-guard)
            self.assertTrue(self.env.ref(r["xmlid"], raise_if_not_found=False))

    def test_company_branding_fields(self):
        for f in ("fiq_hovedmeny_accent", "fiq_hovedmeny_logo", "fiq_hovedmeny_as_home"):
            self.assertIn(f, self.env.company._fields)

    def test_set_home_admin_controlled(self):
        u = new_test_user(self.env, login="hm_home", groups="fiq_hovedmeny.group_user")
        self.assertEqual(u.company_id, self.env.company)
        # Flag AV → lås opp (ingen påtvunget home)
        self.env.company.fiq_hovedmeny_as_home = False
        self.Config._action_set_home_all()
        # Flag PÅ → home settes til Hovedmeny for interne brukere i firmaet
        self.env.company.fiq_hovedmeny_as_home = True
        self.Config._action_set_home_all()
        u.invalidate_recordset(["action_id"])
        self.assertEqual(u.action_id.id, self.action.id)
