This module adds sequence and display of projects and tasks.

All features of `project_sequence` and `project_task_code` are included,
except for the changes listed below.
Generic features are moved to dependency modules `base_sequence_number` and `expression_value_mixin`.

Important changes:

- Licence is LGPL-3 (`project_sequence` has LGPL-3, `project_task_code` has AGPL-3).
- Project ir.sequence is not auto-created.
- Project field "sequence_code" is now "sequence_number".
- Task ir.sequence is not auto-created.
- Task field "code" is now "sequence_number".
- Task "sequence_number" is unique, not unique per company.
- Task "sequence_number" is not required. No pre_init_hook.
- Task "sequence_number" is not auto-filled with post_init_hook.
  You may customize the sequence first.
  Then go to list of tasks, select all, click the Action menu, Set No.
- Views are updated (id, name etc.).
- Translations are not copied for now.
