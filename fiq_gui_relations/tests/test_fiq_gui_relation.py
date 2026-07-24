from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


# post_install is REQUIRED here, not a preference.
#
# Under the default at_install the registry holds only this module's own depends, while
# the database still carries NOT NULL columns added by modules that are installed but not
# yet in the registry - group_rfq on res.partner (purchase_stock) is the one that bites.
# The constraint lives in Postgres, but the default is set by Odoo in Python, so a field
# unknown to the registry never gets its default and the INSERT omits the column
# entirely: NotNullViolation on a field this module neither owns nor can see.
#
# Every test below creates res.partner records, so all of them would hit it.
# Odoo core does the same thing - project/tests/test_project_mail_features.py:9.
@tagged("-at_install", "post_install", "fiq")
class TestFiqGuiRelation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        cls.person = Partner.create({"name": "Test Person", "is_company": False})
        cls.person_b = Partner.create({"name": "Other Person", "is_company": False})
        cls.company_a = Partner.create({"name": "Alpha AS", "is_company": True})
        cls.company_b = Partner.create({"name": "Beta AS", "is_company": True})

        cls.Type = cls.env["fiq.gui.relation.type"]
        cls.Relation = cls.env["fiq.gui.relation"]
        cls.type_employee = cls.env.ref("fiq_gui_relations.type_employee")
        cls.type_partner = cls.env.ref("fiq_gui_relations.type_partner")

    def _foreign_company(self):
        """A company that is OUT of scope for this test, whichever way we get one.

        Two earlier attempts both broke on a real database, and the reason is worth
        keeping: res.company.create() drags in every enterprise module that extends the
        model, and one of them refuses the write ("Company Project Folders cannot be
        linked to another company"). Searching for a company the user is not a member of
        then failed too - the test administrator belongs to every company that exists,
        so the search came back empty and fell straight back to create().

        Once tillatte_firmaer() is read rather than assumed
        (fiq_gui_control_config.py:85): without the 000 right it returns the ACTIVE
        company only. So any company id that is not the active one is out of scope.

        Three attempts failed before this one, all for the same underlying reason:
        creating a company is impossible on a real database. res.company.create() drags
        in every enterprise module extending the model, and documents_project refuses
        the write outright (res_company.py:25, "Company Project Folders cannot be linked
        to another company"). Searching first and creating as a fallback still hits it
        whenever the search comes back empty.

        So we never create. If no second company exists, the test skips - a skipped test
        states honestly that the condition could not be produced here, which is worth
        more than a test that fails for reasons having nothing to do with relations.
        """
        other = self.env["res.company"].search(
            [("id", "!=", self.env.company.id)], limit=1
        )
        if not other:
            self.skipTest(
                "needs a second company; creating one is blocked by "
                "documents_project on this database"
            )
        return other

    def _uten_000(self):
        """Make the 'no cross-company insight' assumption explicit.

        Both scope tests only mean something for a user WITHOUT the 000 right - with it,
        seeing another company's relation is correct behaviour, not a leak. The test
        administrator may well hold the group, so it is removed here rather than assumed
        absent. Stated in the test instead of left implicit: an assumption that is only
        true by accident is the kind that silently stops being true.
        """
        group = self.env.ref(
            "fiq_gui_control.group_000_kryss_firma", raise_if_not_found=False
        )
        if group and group in self.env.user.all_group_ids:
            self.env.user.write({"group_ids": [(3, group.id)]})

    # ---- the core case: one person, several companies -----------------------------

    def test_one_person_many_companies(self):
        """The whole reason the module exists: a person holds several affiliations at
        once, each with its own job title, without being duplicated as a contact."""
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
                "note": "Backoffice",
            }
        )
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_b.id,
                "type_id": self.env.ref("fiq_gui_relations.type_general_manager").id,
                "note": "General Manager",
            }
        )
        rels = self.Relation.relations_for_partner(self.person.id)
        self.assertEqual(len(rels), 2)
        notes = sorted(r["note"] for r in rels)
        self.assertEqual(notes, ["Backoffice", "General Manager"])
        # The person is still ONE contact - that is the point.
        self.assertEqual(
            self.env["res.partner"].search_count([("name", "=", "Test Person")]), 1
        )

    def test_parent_id_untouched(self):
        """The module must not disturb the native address book. A relation is added
        alongside parent_id, never instead of it."""
        self.person.parent_id = self.company_a
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_b.id,
                "type_id": self.type_employee.id,
            }
        )
        self.assertEqual(self.person.parent_id, self.company_a)

    # ---- reading from both sides ---------------------------------------------------

    def test_read_from_both_sides(self):
        """One stored row, read correctly from either end: forward from A, inverted
        from B. This is what a plain Many2many cannot do - it has no direction."""
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
            }
        )
        from_person = self.Relation.relations_for_partner(self.person.id)
        from_company = self.Relation.relations_for_partner(self.company_a.id)

        self.assertEqual(len(from_person), 1)
        self.assertEqual(len(from_company), 1)
        self.assertEqual(from_person[0]["label"], self.type_employee.name)
        self.assertEqual(from_company[0]["label"], self.type_employee.name_inverse)
        # Each side names the OTHER party, never itself.
        self.assertEqual(from_person[0]["partner_id"], self.company_a.id)
        self.assertEqual(from_company[0]["partner_id"], self.person.id)

    def test_symmetric_reads_same_both_ways(self):
        rel = self.Relation.create(
            {
                "partner_a_id": self.company_a.id,
                "partner_b_id": self.company_b.id,
                "type_id": self.type_partner.id,
            }
        )
        self.assertTrue(rel.type_id.symmetric)
        a = self.Relation.relations_for_partner(self.company_a.id)[0]
        b = self.Relation.relations_for_partner(self.company_b.id)[0]
        self.assertEqual(a["label"], b["label"])

    def test_relation_stored_once(self):
        """No mirror row is written. Two copies of the same fact drift apart."""
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
            }
        )
        self.assertEqual(self.Relation.search_count([]), 1)

    # ---- validity period -----------------------------------------------------------

    def test_ended_relation_keeps_person(self):
        """A relation that ends is dated, not deleted - and the person stays active.
        Explicit requirement: never archive someone because they changed employer."""
        rel = self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
                "date_start": "2020-01-01",
                "date_end": "2021-01-01",
            }
        )
        self.assertFalse(rel.is_current)
        self.assertTrue(rel.exists())
        self.assertTrue(self.person.active)
        # It still shows in history, just not among the current ones.
        self.assertEqual(len(self.Relation.relations_for_partner(self.person.id)), 1)
        self.assertEqual(
            len(self.Relation.relations_for_partner(self.person.id, only_current=True)),
            0,
        )

    def test_open_ended_is_current(self):
        rel = self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
                "date_start": "2020-01-01",
            }
        )
        self.assertTrue(rel.is_current)

    def test_end_before_start_rejected(self):
        with self.assertRaises(ValidationError):
            self.Relation.create(
                {
                    "partner_a_id": self.person.id,
                    "partner_b_id": self.company_a.id,
                    "type_id": self.type_employee.id,
                    "date_start": "2021-01-01",
                    "date_end": "2020-01-01",
                }
            )

    # ---- guards --------------------------------------------------------------------

    def test_self_relation_rejected(self):
        with self.assertRaises(ValidationError):
            self.Relation.create(
                {
                    "partner_a_id": self.person.id,
                    "partner_b_id": self.person.id,
                    "type_id": self.type_partner.id,
                }
            )

    def test_person_company_kind_enforced(self):
        """ "is employed by" expects a person on the A side. A company there is a
        catalogue mistake and should fail loudly at write time."""
        with self.assertRaises(ValidationError):
            self.Relation.create(
                {
                    "partner_a_id": self.company_a.id,
                    "partner_b_id": self.company_b.id,
                    "type_id": self.type_employee.id,
                }
            )

    def test_type_needs_inverse_unless_symmetric(self):
        with self.assertRaises(ValidationError):
            self.Type.create(
                {
                    "code": "test_no_inverse",
                    "name": "points at",
                    "symmetric": False,
                }
            )

    def test_type_code_unique(self):
        from odoo.tools.misc import mute_logger
        from psycopg2 import IntegrityError

        self.Type.create({"code": "test_unique", "name": "a", "name_inverse": "b"})
        with (
            mute_logger("odoo.sql_db"),
            self.assertRaises(IntegrityError),
            self.env.cr.savepoint(),
        ):
            self.Type.create({"code": "test_unique", "name": "c", "name_inverse": "d"})

    # ---- partner counters ----------------------------------------------------------

    def test_count_includes_both_sides(self):
        """The count must include relations where the partner is the B side - that is
        precisely the half native parent_id cannot express."""
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
            }
        )
        self.Relation.create(
            {
                "partner_a_id": self.person_b.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
            }
        )
        self.assertEqual(self.person.fiq_relation_count, 1)
        self.assertEqual(self.company_a.fiq_relation_count, 2)

    # ---- searching contacts BY their relations --------------------------------------

    def test_search_by_relation_type_finds_both_sides(self):
        """Searching by type must find the employee AND the employer.

        Only searching partner_a_id would return half the answer - the stored direction
        is a property of the row, not of the question.
        """
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
            }
        )
        Partner = self.env["res.partner"]
        found = Partner.search(
            [("fiq_search_relation_type_id", "=", self.type_employee.id)]
        )
        self.assertIn(self.person, found)
        self.assertIn(self.company_a, found)
        self.assertNotIn(self.person_b, found)

    def test_search_by_partner_excludes_the_target(self):
        """ "Who has a relation with Alpha AS" must not return Alpha AS itself, even
        though it appears in every one of those rows."""
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
            }
        )
        found = self.env["res.partner"].search(
            [("fiq_search_relation_partner_id", "=", self.company_a.id)]
        )
        self.assertIn(self.person, found)
        self.assertNotIn(self.company_a, found)

    def test_search_by_date_respects_the_window(self):
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
                "date_start": "2020-01-01",
                "date_end": "2021-01-01",
            }
        )
        Partner = self.env["res.partner"]
        self.assertIn(
            self.person,
            Partner.search([("fiq_search_relation_date", "=", "2020-06-01")]),
        )
        self.assertNotIn(
            self.person,
            Partner.search([("fiq_search_relation_date", "=", "2022-06-01")]),
        )

    def test_search_by_date_rejects_unsupported_operator(self):
        """A filter that silently ignores its own operator is worse than one that
        refuses: the user would trust a result that answered a different question."""
        with self.assertRaises(UserError):
            self.env["res.partner"].search(
                [("fiq_search_relation_date", ">", "2020-01-01")]
            )

    def test_search_fields_hold_nothing(self):
        """Search-only fields must never appear to carry data - they exist to filter."""
        self.assertFalse(self.person.fiq_search_relation_type_id)
        self.assertFalse(self.person.fiq_search_relation_partner_id)
        self.assertFalse(self.person.fiq_search_relation_date)

    # ---- the surface payload -------------------------------------------------------

    def test_graf_returns_nodes_and_edges(self):
        """Both parties become nodes; the relation becomes one edge."""
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
            }
        )
        graf = self.Relation.get_graf()
        ids = {n["id"] for n in graf["noder"]}
        self.assertIn(self.person.id, ids)
        self.assertIn(self.company_a.id, ids)
        self.assertEqual(len(graf["kanter"]), 1)

    def test_graf_labels_each_side_correctly(self):
        """Each node carries the relation worded from ITS side, not the stored side."""
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
            }
        )
        graf = self.Relation.get_graf()
        by_id = {n["id"]: n for n in graf["noder"]}
        self.assertEqual(
            by_id[self.person.id]["relasjoner"][0]["label"], self.type_employee.name
        )
        self.assertEqual(
            by_id[self.company_a.id]["relasjoner"][0]["label"],
            self.type_employee.name_inverse,
        )

    def test_graf_counts_what_it_cannot_show(self):
        """The key honesty guarantee: a relation the user may not see is COUNTED, not
        silently dropped. Half a graph looks complete, so the omission must be reported.
        """
        other = self._foreign_company()
        self._uten_000()
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
            }
        )
        self.Relation.create(
            {
                "partner_a_id": self.person_b.id,
                "partner_b_id": self.company_b.id,
                "type_id": self.type_employee.id,
                "company_id": other.id,
            }
        )
        graf = self.Relation.get_graf()
        self.assertEqual(len(graf["kanter"]), 1, "only the in-scope relation is shown")
        self.assertEqual(graf["utenfor"], 1, "the hidden one must still be counted")

    def test_graf_client_company_cannot_widen_scope(self):
        """A company id from the client can only narrow. Asking for a company the user
        has no access to must not reveal it."""
        other = self._foreign_company()
        self._uten_000()
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
                "company_id": other.id,
            }
        )
        graf = self.Relation.get_graf(firma_id=other.id)
        self.assertEqual(len(graf["kanter"]), 0)
        self.assertEqual(graf["utenfor"], 1)

    def test_graf_excludes_ended_relations(self):
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
                "date_start": "2020-01-01",
                "date_end": "2021-01-01",
            }
        )
        self.assertEqual(len(self.Relation.get_graf()["kanter"]), 0)

    # ---- short name (absorbed from partner_short_name) ------------------------------

    def test_short_name_stored_on_partner(self):
        """The field the absorbed module provided. It had no tests of its own, so the
        coverage has to come from this side."""
        self.company_a.short_name = "Alpha"
        self.assertEqual(self.company_a.short_name, "Alpha")

    def test_graph_prefers_short_name(self):
        """A graph node is a small box: the short name is what fits in it. The full name
        must still travel with the node, or the detail panel would show the abbreviation
        as if it were the real name."""
        self.company_a.short_name = "Alpha"
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
            }
        )
        node = next(
            n for n in self.Relation.get_graf()["noder"] if n["id"] == self.company_a.id
        )
        self.assertEqual(node["navn"], "Alpha")
        self.assertEqual(node["fullt_navn"], self.company_a.display_name)

    def test_graph_falls_back_to_full_name(self):
        """Most contacts will never get a short name. They must not render blank."""
        self.assertFalse(self.company_b.short_name)
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_b.id,
                "type_id": self.type_employee.id,
            }
        )
        node = next(
            n for n in self.Relation.get_graf()["noder"] if n["id"] == self.company_b.id
        )
        self.assertEqual(node["navn"], self.company_b.display_name)

    # ---- the card view --------------------------------------------------------------

    def _forvalter_oppsett(self):
        """Manager -> property, property -> owner. The shape the card view renders."""
        eiendom = self.env["res.partner"].create(
            {"name": "Oscarsgate 20", "is_company": True}
        )
        eier = self.env["res.partner"].create({"name": "Bufetat", "is_company": True})
        self.Relation.create(
            {
                "partner_a_id": self.company_a.id,
                "partner_b_id": eiendom.id,
                "type_id": self.env.ref("fiq_gui_relations.type_property_manager").id,
            }
        )
        self.Relation.create(
            {
                "partner_a_id": eier.id,
                "partner_b_id": eiendom.id,
                "type_id": self.env.ref("fiq_gui_relations.type_owner").id,
            }
        )
        return eiendom, eier

    def test_kort_shows_manager_with_properties(self):
        eiendom, _eier = self._forvalter_oppsett()
        kort = self.Relation.get_kort()
        managers = [f for f in kort["forvaltere"] if f["id"] == self.company_a.id]
        self.assertEqual(len(managers), 1)
        self.assertEqual(
            [e["adresse"] for e in managers[0]["eiendommer"]], [eiendom.display_name]
        )

    def test_kort_separates_manager_from_owner(self):
        """The whole reason this view exists: the manager is rarely the owner. If the
        two collapsed into one field, the distinction the view is built to show would
        be gone."""
        _eiendom, eier = self._forvalter_oppsett()
        kort = self.Relation.get_kort()
        manager = next(f for f in kort["forvaltere"] if f["id"] == self.company_a.id)
        prop = manager["eiendommer"][0]
        self.assertEqual(prop["eier"], eier.display_name)
        self.assertNotEqual(prop["eier"], manager["navn"])

    def test_kort_counts_what_it_cannot_show(self):
        """Same honesty rule as the graph: a managed property outside the user's scope
        is counted, not silently missing."""
        other = self._foreign_company()
        self._uten_000()
        eiendom = self.env["res.partner"].create(
            {"name": "Hidden Property", "is_company": True}
        )
        self.Relation.create(
            {
                "partner_a_id": self.company_b.id,
                "partner_b_id": eiendom.id,
                "type_id": self.env.ref("fiq_gui_relations.type_property_manager").id,
                "company_id": other.id,
            }
        )
        kort = self.Relation.get_kort()
        self.assertEqual(kort["utenfor"], 1)
        self.assertNotIn(self.company_b.id, [f["id"] for f in kort["forvaltere"]])

    def test_kort_empty_without_managers(self):
        self.assertEqual(self.Relation.get_kort()["forvaltere"], [])

    # ---- the daily refresh ---------------------------------------------------------

    def test_cron_fixes_expired_relation(self):
        """A stored compute does not recalculate because the calendar moved. Without the
        cron, a relation that ended last night keeps reading as current - and searches
        and groupings quietly return yesterday's truth."""
        rel = self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
                "date_start": "2020-01-01",
            }
        )
        self.assertTrue(rel.is_current)
        # End it behind the compute's back, exactly as the passage of time would.
        self.env.cr.execute(
            "UPDATE fiq_gui_relation SET date_end = '2021-01-01' WHERE id = %s",
            (rel.id,),
        )
        rel.invalidate_recordset(["date_end"])
        self.assertTrue(
            rel.is_current, "stale value should persist until the cron runs"
        )

        self.Relation._cron_recompute_is_current()
        self.assertFalse(rel.is_current)

    def test_cron_leaves_correct_rows_alone(self):
        """Only rows that actually disagree with today are touched, so the job stays
        cheap on a table that is mostly settled history."""
        self.Relation.create(
            {
                "partner_a_id": self.person.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
                "date_start": "2020-01-01",
            }
        )
        self.Relation.create(
            {
                "partner_a_id": self.person_b.id,
                "partner_b_id": self.company_a.id,
                "type_id": self.type_employee.id,
                "date_start": "2020-01-01",
                "date_end": "2021-01-01",
            }
        )
        self.assertEqual(self.Relation._cron_recompute_is_current(), 0)

    def test_no_relations_returns_empty(self):
        self.assertEqual(self.Relation.relations_for_partner(self.person.id), [])

    def test_missing_partner_returns_empty(self):
        """Defensive: a stale id must not raise for the caller."""
        self.assertEqual(self.Relation.relations_for_partner(999999999), [])
