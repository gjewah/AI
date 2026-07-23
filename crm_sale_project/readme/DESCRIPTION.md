This module adds sequence and display of projects and tasks.

All features of `project_sequence` and `project_task_code` are included,
except for the changes listed below.
Generic features are moved to dependency modules `base_sequence_number` and `base_expression_value`.

Important changes:

- Licence is LGPL-3 (`project_sequence` has LGPL-3, `project_task_code` has AGPL-3).
- Project ir.sequence code "project.sequence" is now "project.project".
- Project "sequence_code" is not unique, but unique per company.
- Task field "code" is now "sequence_code".
- Task "sequence_code" is not required. No pre_init_hook.
- Task "sequence_code" is not auto-filled with post_init_hook.
  You may customize the sequence first.
  Then go to list of tasks, select all, click the Action menu, Set Sequence Code.
- Views are updated (id, name etc.).
- Translations are not copied for now.
