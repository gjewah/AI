Activate debug mode.

Open the model (e.g. Contacts), and in the debug menu, go to Model (e.g. res.partner).

Or go to *Settings \> Technical \> Database Structure \> Models* and open the model.

---

There are three sequence options:

0. Do not use a sequence.

1. Use one sequence.
    - Create a sequence.

2. Choose sequence by a field.
    - Select a field. Possible field types: selection, boolean, many2one.
    - Save. A sequence will be auto-created for each existing field value.
    - Click the button with the list icon, to customize the sequences.

The sequence will be stored in the field `sequence_code`.

---

*"Contact No."* defines how to compute the "No.", with a python expression for safe_eval.

- sequence: `{r.sequence_code}`
- 5 digiets: `{r.id:0>5}`
- date: `{r.create_date:%Y-%m-%d}`
- related: `{r.related_id.field}`
- conditional: `{'A' if r.active else 'B'}`

Learn more at https://www.geeksforgeeks.org/formatted-string-literals-f-strings-python/
