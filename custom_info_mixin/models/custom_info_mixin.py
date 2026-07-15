# Copyright 2026 FIQ
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class CustomInfoMixin(models.AbstractModel):
    _name = "custom.info.mixin"
    _description = "Custom Info Mixin"

    survey_id = fields.Many2one(
        comodel_name="survey.survey",
        string="Survey",
        ondelete="restrict",
        copy=True,
        help="cf. custom.info.template",
    )
    survey_user_input_id = fields.Many2one(
        comodel_name="survey.user_input",
        string="Survey User Input",
        ondelete="restrict",
    )
    # survey_user_input_line_ids = fields.One2many(
    #     comodel_name="survey.user_input_line",
    #     inverse_name="res_id",
    #     string="Survey User Input Lines",
    #     help="cf. custom.info.value",
    #     related="survey_user_input_id.user_input_line_ids",
    # )

    def _ensure_survey_user_input(self):
        self.ensure_one()
        self.survey_id.ensure_one()

        if self.survey_user_input_id:
            return self.survey_user_input_id
        
        existing = self.env["survey.user_input"].search([
            ("survey_id", "=", self.survey_id.id),
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
        ], limit=1)
        if existing:
            self.survey_user_input_id = existing
            return existing

        # Create user_input via survey
        user_input = self.survey_id._create_answer(
            user=self.env.user,
        )
        user_input.res_model = self._name
        user_input.res_id = self.id

        self.survey_user_input_id = user_input

        return user_input

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for record, vals in zip(records, vals_list):
            if vals.get("survey_id"):
                record._ensure_survey_user_input()

        return records
    
    def write(self, vals):
        res = super().write(vals)

        # hvis survey endres eller input mangler
        if "survey_id" in vals:
            for record in self:
                record.survey_user_input_id = False
                if vals["survey_id"]:
                    record._ensure_survey_user_input()

        else:
            for record in self:
                if record.survey_id and not record.survey_user_input_id:
                    record._ensure_survey_user_input()

        return res
    
    def action_open_survey(self):
        self.ensure_one()

        if not self.survey_user_input_id:
            self._ensure_survey_user_input()

        # reopen
        # self.survey_user_input_id.state = "in_progress"

        # Conditions:
        # - Enable survey option Allow Roaming (users_can_to_back).
        # - This field is not visible for "One page with all the questions".

        # File "/home/henrik/src/gh/odoo/odoo/19.0/addons/survey/controllers/main.py", line 435, in survey_display_page
        #     self._prepare_survey_data(access_data['survey_sudo'], answer_sudo, **post))
        #     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        # File "/home/henrik/src/gh/odoo/odoo/19.0/addons/survey/controllers/main.py", line 363, in _prepare_survey_data
        #     'previous_page_id': survey_sudo._get_next_page_or_question(answer_sudo, next_page_or_question.id, go_back=True).id
        #                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        # File "/home/henrik/src/gh/odoo/odoo/19.0/addons/survey/models/survey_survey.py", line 778, in _get_next_page_or_question
        #     current_page_index = pages_or_questions.ids.index(page_or_question_id)
        #                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        # ValueError: False is not in list

        return {
            "type": "ir.actions.act_url",
            "url": self.survey_user_input_id.get_start_url(),
            "target": "new",
        }

    def get_survey_answer(self, code):
        self.ensure_one()

        return self.survey_user_input_id.user_input_line_ids.filtered(
            lambda l: l.code == code
        )[:1]
