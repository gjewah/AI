import logging
import re

from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class ExpressionValueMixin(models.AbstractModel):
    _name = "expression.value.mixin"
    _description = "expression.value.mixin"

    def get_ir_model(self, prefetch_fields=True):
        IrModel = self.env["ir.model"].sudo()
        IrModel = IrModel.with_context(prefetch_fields=prefetch_fields)
        # To install apps without errors:
        # - Order by a field which always exists.
        return IrModel.search([("model", "=", self._name)], order="id")
    
    def get_value_from_source(self, source, lookup):
        expression = self.get_expression_from_source(source, lookup)
        return self.get_value_from_expression(expression)
    
    def get_valid_field_paths_from_source(self, source, lookup):
        expression = self.get_expression_from_source(source, lookup)
        field_paths = self.get_field_paths_from_expression(expression)
        return self.get_valid_field_paths(field_paths)

    def raise_error_if_invalid_expression(self, expression):
        field_paths = self.get_field_paths_from_expression(expression)
        self.raise_error_if_invalid_field_paths(field_paths)
        method_paths = self.get_method_paths_from_expression(expression)
        self.raise_error_if_invalid_method_paths(method_paths)

    def get_expression_from_source(self, source, source_lookup):
        """
        Return: A user-defined string with a python expression.
        """
        # To install apps without errors:
        # - Do not prefetch fields.
        if source == "ir.model":
            ir_model = self.get_ir_model(prefetch_fields=False)
            return getattr(ir_model, source_lookup) or ""
        elif source == "ir.config_parameter":
            param = self.env["ir.config_parameter"].sudo().get_param(source_lookup)
            return param or ""

    def get_value_from_expression(self, expression):
        for record in self:
            try:
                value = safe_eval(f"f{repr(expression)}", {"r": record})
                if value in ("False"):
                    return None
                return str(value).strip()
            except Exception as e:
                _logger.warning("Error evaluating expression %r for %s(%d): %s", expression, record._name, record.id, e)

    def pick(self, field_name):
        """
        Return the value of the given field if it exists and differs from the record's name.
        Supports dot notation, e.g., 'company_id.code'.
        """
        value = self
        for part in field_name.split("."):
            value = getattr(value, part, None)
            if value is None:
                return ""  # stop if any part is missing

        name = getattr(self, "name", None)
        return value if value and value != name else ""

    ##################

    @api.model
    def get_field_paths_from_expression(self, expression):
        """
        Return a set of r.field.paths (without 'r.') in the expression,
        ignoring method calls and respecting optional f-string format specifiers.
        """
        r_field_pattern = r"r\.([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)(?=\s*(?::|$))"
        return self._extract_pattern_from_placeholders(expression, r_field_pattern)

    @api.model
    def get_method_paths_from_expression(self, expression):
        """
        Return a set of r.method calls (with arguments) in the expression.
        The format specifier in f-strings is ignored.
        """
        r_method_pattern = r"r\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\("

        return self._extract_pattern_from_placeholders(expression, r_method_pattern)

    @api.model
    def _extract_pattern_from_placeholders(self, expression, pattern):
        """
        Extract all matches of the given regex pattern inside placeholders {}.
        Returns a set of matches.
        """
        if not expression:
            return set()

        # Find all placeholders
        placeholders = re.findall(r"\{([^{}]+)\}", expression)
        matches = set()
        for placeholder in placeholders:
            matches.update(re.findall(pattern, placeholder))
        return matches

    ##################

    @api.model
    def get_valid_field_paths(self, field_paths):
        """
        Return only valid field paths from the input list.
        Return as tuple, required by @api.depends().
        """
        model = self.env[self._name]
        valid_paths = (
            path for path in field_paths
            if self._is_field_path_valid(model, path.split('.'))
        )
        return valid_paths

    def raise_error_if_invalid_field_paths(self, field_paths):
        model = self.env[self._name]
        for path in field_paths:
            if not self._is_field_path_valid(model, path.split('.')):
                raise ValidationError(
                    f"Not all field_paths are valid: {field_paths}"
                )

    def raise_error_if_invalid_method_paths(self, method_paths):
        model = self.env[self._name]
        for path in method_paths:
            if not self._is_method_path_valid(model, path.split('.')):
                raise ValidationError(
                    f"Not all method_paths are valid: {method_paths}"
                )

    @api.model
    def _is_field_path_valid(self, model, path_parts):
        """
        Recursive helper to check if a dotted field path exists on a model.
        """
        if not path_parts:
            return True
        field_name = path_parts[0]
        field = model._fields.get(field_name)
        if not field:
            return False
        # Follow relational fields
        if field.type in ('many2one', 'one2many', 'many2many'):
            rel_model = self.env[field.comodel_name]
            return self._is_field_path_valid(rel_model, path_parts[1:])
        elif len(path_parts) > 1:
            # Non-relational field cannot have further parts
            return False
        return True

    @api.model
    def _is_method_path_valid(self, model, path_parts):
        """
        Recursive helper to check if a dotted method path exists on a model.

        Example:
            path_parts = ["partner_id", "get_full_name"]
        """
        if not path_parts:
            return True

        method_or_field = path_parts[0]

        # 1️⃣ Check if it's a relational field
        field = model._fields.get(method_or_field)
        if field and field.type in ('many2one', 'one2many', 'many2many'):
            rel_model = self.env[field.comodel_name]
            return self._is_method_path_valid(rel_model, path_parts[1:])

        # 2️⃣ If it's the last part, check if the method exists
        if len(path_parts) == 1:
            method = path_parts[0].partition('(')[0]
            return hasattr(model, method) and callable(getattr(model, method))

        # 3️⃣ If non-relational field and more parts exist, invalid
        if field:
            return False

        # 4️⃣ Otherwise, invalid path
        return False
