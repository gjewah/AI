from odoo import api, fields, models
from odoo.exceptions import UserError

class DocumentsTag(models.Model):
    _inherit = "documents.tag"

    def action_copy_to_code_list(self):
        """
        Creates a single `code.list` named "Document Tags" and creates a `code.list.item` for every `documents.tag`.
        If the `parent_id` field exists on the `documents.tag` model, it will be used to set the `parent_id` on the `code.list.item`.
        Otherwise, the `parent_id` will remain blank.
        """
        CodeList = self.env['code.list']
        CodeListItem = self.env['code.list.item']

        # Check if the "Document Tags" code list already exists
        code_list = CodeList.search([('name', '=', 'Document Tags')], limit=1)
        if not code_list:
            # Create the "Document Tags" code list if it doesn't exist
            code_list = CodeList.create({
                "code": False,  # Code is empty
                "name": "Document Tags",
                "description": "A list of all document tags.",
            })

        # Check if the `parent_id` field exists on the `documents.tag` model
        has_parent_field = 'parent_id' in self._fields

        for tag in self:
            parent_item_id = False

            # If the `parent_id` field exists and the tag has a parent, find or create the parent item
            if has_parent_field and tag.parent_id:
                parent_item = CodeListItem.search([
                    ('name', '=', tag.parent_id.name),
                    ('list_id', '=', code_list.id)
                ], limit=1)
                if not parent_item:
                    parent_item = CodeListItem.create({
                        "code": False,  # Code is empty
                        "name": tag.parent_id.name,
                        "description": tag.parent_id.tooltip or "",
                        "list_id": code_list.id,
                    })
                parent_item_id = parent_item.id

            # Create the code.list.item for the current tag
            CodeListItem.create({
                "code": False,  # Code is empty
                "name": tag.name,  # Use the tag name as the item name
                "description": tag.tooltip,
                "list_id": code_list.id,  # Link to the "Document Tags" code list
                "parent_id": parent_item_id,  # Link to the parent item if it exists
            })

    def action_copy_to_code_lists(self):
        """
        Create a temporary server action to do this once.

        Copies `documents.tag` records to `code.list` and `code.list.item`.
        Records with a single-level code (e.g., "1", "2") are copied to `code.list`.
        Records with multi-level codes (e.g., "1.1", "1.1.1") are copied to `code.list.item`.
        """
        CodeList = self.env['code.list']
        CodeListItem = self.env['code.list.item']

        def get_or_create_parent_item(parent_code, top_level_code_list, full_name):
            """
            Recursively find or create the parent `code.list.item`.
            """
            parent_item = CodeListItem.search([
                ('name', '=', parent_code),
                ('list_id', '=', top_level_code_list.id)
            ], limit=1)
            if not parent_item:
                # Split the parent code to find its parent
                parent_code_parts = parent_code.split('.')
                if len(parent_code_parts) > 1:
                    grandparent_code = '.'.join(parent_code_parts[:-1])
                    parent_name = parent_code_parts[-1]

                    # Recursively create the grandparent item
                    grandparent_item = get_or_create_parent_item(grandparent_code, top_level_code_list, full_name)

                    # Create the parent item
                    parent_item = CodeListItem.create({
                        "code": False,  # Code is now empty
                        "name": parent_name,  # Use the parent name
                        "list_id": top_level_code_list.id,
                        "parent_id": grandparent_item.id,
                    })
                else:
                    # If no grandparent exists, create the top-level parent as a code.list
                    parent_item = CodeListItem.create({
                        "code": False,  # Code is now empty
                        "name": parent_code,  # Use the parent code as the name
                        "list_id": top_level_code_list.id,
                    })
            return parent_item

        for tag in self:
            # Split the tag name into parts based on the dot separator
            code_parts = tag.name.split('.')

            if len(code_parts) == 1:
                # Top-level code list
                CodeList.create({
                    "code": False,  # Code is now empty
                    "name": tag.name,  # Use the full name from documents.tag
                    "description": tag.tooltip,
                })
            else:
                # Multi-level code list item
                top_level_code = code_parts[0]  # First part is the top-level code
                parent_code = '.'.join(code_parts[:-1])  # All but the last part is the parent code

                # Find or create the top-level code list
                top_level_code_list = CodeList.search([('name', '=', top_level_code)], limit=1)
                if not top_level_code_list:
                    top_level_code_list = CodeList.create({
                        "code": False,  # Code is now empty
                        "name": top_level_code,  # Use the full name from documents.tag
                        "description": f"Auto-created for tag {tag.name}",
                    })

                # Recursively find or create the parent code list item
                parent_item = get_or_create_parent_item(parent_code, top_level_code_list, tag.name)

                # Ensure no duplicate code.list.item is created
                existing_item = CodeListItem.search([
                    ('name', '=', tag.name),
                    ('list_id', '=', top_level_code_list.id),
                    ('parent_id', '=', parent_item.id)
                ], limit=1)

                if not existing_item:
                    # Create the code list item
                    CodeListItem.create({
                        "code": False,  # Code is now empty
                        "name": tag.name,  # Use the full name from documents.tag
                        "description": tag.tooltip,
                        "list_id": top_level_code_list.id,  # Link to the top-level code list
                        "parent_id": parent_item.id,  # Link to the parent code list item
                    })
