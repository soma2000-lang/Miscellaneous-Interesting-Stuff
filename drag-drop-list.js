sap.ui.define([
  "sap/ui/core/Control",
  "sap/ui/dom/includeScript"
], function(Control, includeScript) {
  "use strict";
  
  return Control.extend("custom.DragDropList", {
    metadata: {
      properties: {
        listId: { type: "string", defaultValue: null }
      },
      events: {
        itemMoved: {
          parameters: {
            itemId: { type: "string" },
            newIndex: { type: "int" }
          }
        }
      }
    },

    init: function() {
      // Load jQuery UI if not present
      if (!window.jQuery.ui) {
        includeScript({
          url: "https://code.jquery.com/ui/1.12.1/jquery-ui.min.js"
        });
      }
    },

    onAfterRendering: function() {
      const listSelector = `#${this.getListId()}-listUl li`;
      
      jQuery(listSelector).sortable({
        revert: true,
        update: (event, ui) => {
          const itemId = ui.item.attr('id');
          const newIndex = ui.item.index();
          this.fireItemMoved({
            itemId: itemId,
            newIndex: newIndex
          });
        }
      });

      jQuery(listSelector).draggable({
        helper: "original",
        cursor: "move",
        containment: "parent"
      });
    }
  });
});
