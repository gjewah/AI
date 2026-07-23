// // Code suggestion from Odoo AI
// // IT DOES NOT WORK AND IT CREATES ERRORS!!!

// odoo.define('your_module.kanban_color_picker', function (require) {
//     "use strict";

//     var KanbanRenderer = require('web.KanbanRenderer');
//     var rpc = require('web.rpc');

//     KanbanRenderer.include({
//         events: _.extend({}, KanbanRenderer.prototype.events, {
//             'change .o_color_picker': '_onColorChange',
//         }),

//         _onColorChange: function (event) {
//             var self = this;
//             var color = $(event.target).val(); // Get the selected color value
//             var recordId = $(event.target).data('record-id'); // Get the ID of the record

//             rpc.query({
//                 model: 'documents.document',
//                 method: 'write',
//                 args: [[recordId], {'color': color}],
//             }).then(function () {
//                 // Optionally, you can add some visual feedback here,
//                 // like re-rendering the Kanban card.
//                 self.updateRecord(recordId);
//             });
//         },
//     });
// });
