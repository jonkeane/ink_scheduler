// Calendar drag-and-drop functionality for ink scheduler
(function() {
    // Track the currently dragged element
    let draggedElement = null;
    let draggedDate = null;
    let draggedInkIdx = null;

    // Initialize drag-and-drop after Shiny connects
    $(document).on('shiny:connected', function() {
        initDragDrop();
    });

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
