If incoming emails are pushed to Odoo through a gateway (e.g. Postfix / Exim / Outlook)
please pass the context variable `fetchmail_cron_running=True`
to disable email notifications of that message.

TODO: TEST IF THIS IS POSSIBLE

models.execute_kw(db, uid, password, 'mail.thread', 'message_process', [id], {'context': {'fetchmail_cron_running': True}})
