from odoo.tests.common import TransactionCase
from odoo import Command


class TestProjectDocumentsTags(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Project = cls.env["project.project"]
        cls.Task = cls.env["project.task"]
        cls.Tag = cls.env["documents.tag"]
        cls.Attachment = cls.env["ir.attachment"]

        # Create tags once
        cls.main_tag = cls.Tag.create({"name": "Main Tag"})
        cls.alt_main_tag = cls.Tag.create({"name": "Alt Main Tag"})
        cls.tag_a = cls.Tag.create({"name": "Tag A"})
        cls.tag_b = cls.Tag.create({"name": "Tag B"})

        # Create attachment once
        cls.attachment = cls.Attachment.create({
            "name": "Test Attachment",
            "datas": "dGVzdA==",  # base64: "test"
            "mimetype": "text/plain",
        })

    # ---------------------------------------------------------
    # PROJECT
    # ---------------------------------------------------------
    def test_project_default_main_tag(self):
        """Project: _get_document_vals applies default main tag."""
        project = self.Project.create({
            "name": "Test Project",
            "documents_tag_id": self.main_tag.id,
        })

        vals = project._get_document_vals(self.attachment)
        self.assertEqual(vals.get("documents_tag_id"), self.main_tag.id)

    # ---------------------------------------------------------
    # TASK – MAIN TAG LOGIC
    # ---------------------------------------------------------
    def test_task_uses_own_main_tag(self):
        """If task has its own main tag, use it."""
        project = self.Project.create({
            "name": "P",
            "documents_tag_id": self.main_tag.id,
        })

        task = self.Task.create({
            "name": "T",
            "project_id": project.id,
            "documents_tag_id": self.alt_main_tag.id,
        })

        vals = task._get_document_vals(self.attachment)
        self.assertEqual(vals.get("documents_tag_id"), self.alt_main_tag.id)

    def test_task_falls_back_to_project_main_tag(self):
        """If task has no main tag, use project main tag."""
        project = self.Project.create({
            "name": "P",
            "documents_tag_id": self.main_tag.id,
        })

        task = self.Task.create({
            "name": "T",
            "project_id": project.id,
        })

        vals = task._get_document_vals(self.attachment)
        self.assertEqual(vals.get("documents_tag_id"), self.main_tag.id)

    # ---------------------------------------------------------
    # TASK – TAG LIST
    # ---------------------------------------------------------
    def test_task_applies_default_tags(self):
        """Task: _get_document_vals returns correct tag_ids."""
        task = self.Task.create({
            "name": "T",
            "documents_tag_ids": [
                Command.link(self.tag_a.id),
                Command.link(self.tag_b.id),
            ],
        })

        vals = task._get_document_vals(self.attachment)

        tag_ids = [
            cmd[1]
            for cmd in vals.get("tag_ids", [])
            if cmd[0] == 4  # Command.link
        ]

        self.assertIn(self.tag_a.id, tag_ids)
        self.assertIn(self.tag_b.id, tag_ids)

    # ---------------------------------------------------------
    # COMPUTED BOOLEAN FIELD
    # ---------------------------------------------------------
    def test_documents_tag_ids_filter_always_true(self):
        """Computed field always returns True."""
        task = self.Task.create({"name": "T"})
        project = self.Project.create({"name": "P"})

        self.assertTrue(task.documents_tag_ids_filter)
        self.assertTrue(project.documents_tag_ids_filter)
