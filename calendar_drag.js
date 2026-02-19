// Calendar drag-and-drop functionality for ink scheduler
(function() {
    // =========================================================================
    // Ink Picker Modal - keyboard navigation and selection
    // =========================================================================

    // Track currently selected index in ink picker
    let selectedIndex = -1;

    // Initialize ink picker when modal content updates
    $(document).on('shiny:value', function(event) {
        if (event.target.id === 'ink_picker_list') {
            setTimeout(initInkPicker, 50);
        }
    });

    function initInkPicker() {
        const container = document.getElementById('ink-picker-list-container');
        if (!container) return;

        const items = container.querySelectorAll('.ink-picker-item');

        // Start with first item selected (so Enter works immediately)
        selectedIndex = items.length > 0 ? 0 : -1;

        // Add click handlers to items
        items.forEach((item, index) => {
            item.addEventListener('click', function() {
                selectInk(item);
            });
        });

        // Show initial selection (without scrollIntoView to avoid focus issues)
        if (items.length > 0) {
            items.forEach(item => item.classList.remove('ink-picker-selected'));
            items[0].classList.add('ink-picker-selected');
        }

        // Set up keyboard navigation on the search input
        const searchInput = document.getElementById('ink_picker_search_input');
        if (searchInput) {
            // Remove old listener if any
            searchInput.removeEventListener('keydown', handleInkPickerKeydown);
            searchInput.addEventListener('keydown', handleInkPickerKeydown);

            // Ensure focus stays on search input
            searchInput.focus();
        }

        // Also handle keyboard on the list container
        container.addEventListener('keydown', handleInkPickerKeydown);
    }

    function handleInkPickerKeydown(e) {
        const container = document.getElementById('ink-picker-list-container');
        if (!container) return;

        const items = container.querySelectorAll('.ink-picker-item');
        if (items.length === 0) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
            updateInkPickerSelection(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = Math.max(selectedIndex - 1, 0);
            updateInkPickerSelection(items);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (selectedIndex >= 0 && selectedIndex < items.length) {
                selectInk(items[selectedIndex]);
            }
        }
    }

    function updateInkPickerSelection(items) {
        // Remove selection from all items
        items.forEach(item => item.classList.remove('ink-picker-selected'));

        // Add selection to current item
        if (selectedIndex >= 0 && selectedIndex < items.length) {
            const selectedItem = items[selectedIndex];
            selectedItem.classList.add('ink-picker-selected');
            // Scroll into view if needed
            selectedItem.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    }

    function selectInk(item) {
        const inkIdx = item.dataset.inkIdx;
        const inkName = item.dataset.inkName;

        if (inkIdx !== undefined) {
            // Send selection to Shiny
            Shiny.setInputValue('ink_picker_select', {
                ink_idx: inkIdx,
                ink_name: inkName,
                timestamp: Date.now()
            });
        }
    }

    // =========================================================================
    // Drag and Drop functionality
    // =========================================================================
    // Track the currently dragged element
    let draggedElement = null;
    let draggedDate = null;
    let draggedInkIdx = null;

    // Initialize drag-and-drop after Shiny connects
    $(document).on('shiny:connected', function() {
        initDragDrop();
        initEmptyCellClick();
    });

    // Re-initialize empty cell clicks after calendar re-renders
    $(document).on('shiny:value', function(event) {
        if (event.target.id === 'main_view') {
            setTimeout(initEmptyCellClick, 50);
        }
    });

    function initEmptyCellClick() {
        // Add click handlers to empty calendar cells (cells without an ink assigned)
        const emptyCells = document.querySelectorAll('.calendar-cell:not(.calendar-cell-assigned)');

        emptyCells.forEach(cell => {
            // Remove existing listener to prevent duplicates
            cell.removeEventListener('click', handleEmptyCellClick);
            cell.addEventListener('click', handleEmptyCellClick);
            // Add pointer cursor
            cell.style.cursor = 'pointer';
        });
    }

    function handleEmptyCellClick(e) {
        const cell = e.currentTarget;
        const date = cell.dataset.date;

        if (date) {
            // Trigger the ink picker modal via Shiny input
            Shiny.setInputValue('calendar_empty_cell_click', {
                date: date,
                timestamp: Date.now()
            });
        }
    }

    // Re-initialize after any output updates (calendar re-renders)
    $(document).on('shiny:value', function(event) {
        if (event.target.id === 'main_view') {
            // Small delay to ensure DOM is updated
            setTimeout(initDragDrop, 50);
        }
    });

    function initDragDrop() {
        // Remove existing listeners by cloning elements (prevents duplicates)
        const draggables = document.querySelectorAll('.calendar-draggable');
        const dropTargets = document.querySelectorAll('.calendar-drop-target');

        // Set up drag events on draggable cells
        draggables.forEach(el => {
            el.addEventListener('dragstart', handleDragStart);
            el.addEventListener('dragend', handleDragEnd);
        });

        // Set up drop events on all potential drop targets
        dropTargets.forEach(el => {
            el.addEventListener('dragover', handleDragOver);
            el.addEventListener('dragenter', handleDragEnter);
            el.addEventListener('dragleave', handleDragLeave);
            el.addEventListener('drop', handleDrop);
        });
    }

    function handleDragStart(e) {
        const el = e.currentTarget;
        draggedElement = el;
        draggedDate = el.dataset.date;
        draggedInkIdx = el.dataset.inkIdx;

        // Set drag data
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', draggedDate);

        // Add dragging class after a small delay (for visual feedback)
        setTimeout(() => {
            el.classList.add('dragging');
        }, 0);
    }

    function handleDragEnd(e) {
        const el = e.currentTarget;
        el.classList.remove('dragging');

        // Clean up any remaining drag-over states
        document.querySelectorAll('.drag-over').forEach(target => {
            target.classList.remove('drag-over');
        });

        draggedElement = null;
        draggedDate = null;
        draggedInkIdx = null;
    }

    function handleDragOver(e) {
        e.preventDefault();
        const el = e.currentTarget;

        // Don't allow drop on protected cells
        if (el.dataset.protected === 'true') {
            e.dataTransfer.dropEffect = 'none';
            return;
        }

        // Don't allow drop on self
        if (el === draggedElement) {
            e.dataTransfer.dropEffect = 'none';
            return;
        }

        e.dataTransfer.dropEffect = 'move';
    }

    function handleDragEnter(e) {
        const el = e.currentTarget;

        // Don't highlight protected cells or self
        if (el.dataset.protected === 'true' || el === draggedElement) {
            return;
        }

        el.classList.add('drag-over');
    }

    function handleDragLeave(e) {
        const el = e.currentTarget;

        // Only remove if we're actually leaving the element (not entering a child)
        if (!el.contains(e.relatedTarget)) {
            el.classList.remove('drag-over');
        }
    }

    function handleDrop(e) {
        e.preventDefault();
        const targetEl = e.currentTarget;

        // Remove drag-over class
        targetEl.classList.remove('drag-over');

        // Don't allow drop on protected cells
        if (targetEl.dataset.protected === 'true') {
            return;
        }

        // Don't allow drop on self
        if (targetEl === draggedElement) {
            return;
        }

        const fromDate = draggedDate;
        const toDate = targetEl.dataset.date;
        const toInkIdx = targetEl.dataset.inkIdx;

        if (!fromDate || !toDate) {
            return;
        }

        // Send to Shiny server
        // Include whether this is a swap (target has an ink) or simple move (target is empty)
        Shiny.setInputValue('calendar_drag_drop', {
            from_date: fromDate,
            to_date: toDate,
            from_ink_idx: draggedInkIdx,
            to_ink_idx: toInkIdx || null,
            is_swap: !!toInkIdx,
            timestamp: Date.now()  // Force reactivity on repeated drags
        });
    }
})();
