from odoo import models, fields

class SurveyUserInput(models.Model):
    _inherit = "survey.user_input"

    res_model = fields.Char(
        string="Related Model",
        index=True,
    )
    res_id = fields.Many2oneReference(
        string="Related Record",
        model_field="res_model",
        index=True,
    )
