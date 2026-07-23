import contextlib
import logging

from odoo import api, models
from odoo.tools.translate import _
from odoo.orm.domains import Domain
# from odoo.fields import Domain
from odoo.orm.utils import COLLECTION_TYPES


_logger = logging.getLogger(__name__)


class ExpressionValueMixin(models.AbstractModel):
    _inherit = "expression.value.mixin"

    @api.depends(lambda self: self.get_valid_field_paths_from_source("ir.model", "display_name_expression"))
    def _compute_display_name(self):
        """
        If display_name is stored, restart Odoo after changing display_name_expression.
        """
        expression = self.get_expression_from_source("ir.model", "display_name_expression")
        if expression:
            for rec in self:
                rec.display_name = rec.get_value_from_expression(expression)
        else:
            return super()._compute_display_name()

    @api.model
    def _search_display_name(self, operator, value):
        search_fnames = list(self.get_valid_field_paths_from_source("ir.model", "display_name_expression"))
        if not search_fnames:
            search_fnames = self._rec_names_search or ([self._rec_name] if self._rec_name else [])
        # The rest is copied from orm/models.py #########################################################################
        if not search_fnames:
            _logger.warning("Cannot search on display_name, no _rec_name or _rec_names_search defined on %s", self._name)
            # do not restrain anything
            return Domain.TRUE
        if operator.endswith('like') and not value and '=' not in operator:
            # optimize out the default criterion of ``like ''`` that matches everything
            # return all when operator is positive
            return Domain.FALSE if operator in Domain.NEGATIVE_OPERATORS else Domain.TRUE
        aggregator = Domain.AND if operator in Domain.NEGATIVE_OPERATORS else Domain.OR
        domains = []
        for field_name in search_fnames:
            # field_name may be a sequence of field names (partner_id.name)
            # retrieve the last field in the sequence
            model = self
            for fname in field_name.split('.'):
                field = model._fields[fname]
                model = self.env.get(field.comodel_name)
            # depending on the operator, we may need to cast the value to the type of the field
            # ignore if we cannot convert
            if field.relational:
                # relational fields will search on the display_name
                domains.append([(field_name + '.display_name', operator, value)])
            elif operator.endswith('like'):
                domains.append([(field_name, operator, value)])
            elif isinstance(value, COLLECTION_TYPES):
                typed_value = []
                for v in value:
                    with contextlib.suppress(ValueError, TypeError):
                        typed_value.append(field.convert_to_write(v, self))
                domains.append([(field_name, operator, typed_value)])
            else:
                with contextlib.suppress(ValueError):
                    typed_value = field.convert_to_write(value, self)
                    domains.append([(field_name, operator, typed_value)])
                continue
            with contextlib.suppress(ValueError, TypeError):
                # ignore that case if the value doesn't match the field type
                domains.append([(field_name, operator, field.convert_to_write(value, self))])
        return aggregator(domains)
