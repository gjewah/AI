from odoo import models, fields, api

class DocumentsDocument(models.Model):
    _inherit = 'documents.document'
    
    def action_document_form(self):
        """
        Opens the document form view for the current document.
        """
        # Ensure that the action is available only for documents
        if not self:
            return {}
        
        # Return an action to open the form view of the document
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Document Form',
            'res_model': 'documents.document',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(self.env.ref('documents_form.document_view_form').id, 'form')],
        }
