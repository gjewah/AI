# Copyright 2025 FIQ as
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "FIQ Mail Apps",
    "author": "FIQ as, Odoo Community Association (OCA)",
    "website": "https://fiq.no",
    "version": "19.0.5.0.1",
    "license": "AGPL-3",
    "data": [
        "data/ir_config_parameter_data.xml",
        # "security/mail_message_security.xml",
        "views/res_users_views.xml",
    ],
    "depends": [
        # Odoo
        "mail",
        "microsoft_outlook",

        # OCA
        "mail_composer_cc_bcc", # git@github.com:norlinhenrik/oca-mail.git      ### 19.0-fix-mail_mail-email_to                  ### beta/mail
        # "mail_force_email_notification",
        "mail_message_search",
        # "mail_optional_follower_notification", # git@github.com:odoonz/mail.git ### 19.0-mig-mail_optional_follower_notification ### beta/.mail_optional_follower_notification
        #     # shell
        #     #   cd src/user/beta
        #     #   git checkout Staging
        #     #   ln -s ./.mail_optional_follower_notification/mail_optional_follower_notification mail_optional_follower_notification
        #     #   git add mail_optional_follower_notification
        #     #   git commit -am "link mail_optional_follower_notification"
        #     #   git push -u origin Staging
        # "mail_quoted_reply",
        "mail_send_confirmation",
        # "mail_tracking",

        # Loym/FIQ
        "base_fiq",
        "mail_config_by_user",
        # "mail_force_email_notification_compose",
        "mail_message_search_global",
        "mail_message_security",
        "mail_never_autofollow", # consider mail_optional_autofollow https://github.com/OCA/mail/pull/29

        # Wishlist
        # - mail_message_security: Do not forward emails from the Odoo gateway
        # - mail_quoted_reply_all
        # - User setting: Handle important notifications in Email, otherwise in Odoo

        # Consider
        # - https://github.com/OCA/social/tree/17.0/mail_disable_follower_notification
    ],
}
