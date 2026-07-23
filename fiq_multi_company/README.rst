================
FIQ Multi-Company
================

.. |badge1| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3

|badge1|

Slank, 19-native FIQ-modul som erstatter fire OCA-moduler uten 19.0:
``crm_stage_multi_company``, ``crm_lost_reason_multi_company``,
``mail_template_multi_company`` og ``partner_category_multi_company``.

Funksjon
========

Legger et valgfritt ``company_id`` + en global multi-company record-rule på:

* ``crm.stage`` – per-firma salgstrinn
* ``crm.lost.reason`` – per-firma tapsårsaker
* ``mail.template`` – per-firma e-postmaler (egen signatur/logo per selskap)
* ``res.partner.category`` – per-firma partnerkategorier

Oppførsel
=========

* ``company_id`` tomt = posten er **delt** på tvers av alle selskaper
  (bevarer eksisterende oppførsel – ingen migrering nødvendig).
* ``company_id`` satt = posten er synlig kun for det selskapet (+ delte).

Record-rulen er global og bruker standard Odoo-mønster::

    ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]

Feltet vises i skjemaene kun når fler-selskap er aktivert
(``base.group_multi_company``).

Migrering fra OCA
=================

Feltnavnet ``company_id`` er identisk med OCA-modulene, så eksisterende
data bevares. Avinstaller OCA-modulene og installer denne i samme
oppgraderingssteg.

Testing
=======

Se ``tests/test_fiq_multi_company.py``::

    odoo-bin -d <db> -i fiq_multi_company --test-enable --stop-after-init

Vedlikeholder
=============

FIQ AS – https://www.fiq.no
