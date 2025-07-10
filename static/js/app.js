document.addEventListener('DOMContentLoaded', function() {
    // Handle all court action forms (join court, join queue, leave court)
    document.querySelectorAll('.court-action-form').forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const courtId = this.dataset.courtId;
            const action = this.dataset.action;
            
            fetch(this.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Update UI immediately
                    updateUIForAction(data);
                    
                    // Determine message category based on action
                    let category = 'success';
                    if (action === 'leave_court') {
                        category = 'warning';
                    }
                    
                    // Show success message with proper category
                    showFlashMessage(data.message, category);
                } else {
                    showFlashMessage(data.message || 'An error occurred', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showFlashMessage('Failed to process request', 'error');
            });
        });
    });
    
    // Function to update UI based on action
    function updateUIForAction(data) {
        // Rather than trying to update the DOM directly,
        // we'll rely on the SSE events to update the court data
        // That's much cleaner and avoids sync issues
        
        // Disable/enable buttons as needed
        document.querySelectorAll('.court-section').forEach(courtSection => {
            const courtId = courtSection.dataset.courtId;
            const isUserAction = (data.username === window.currentUser);
            
            if (isUserAction) {
                // If this user did something, update all buttons
                const joinButtons = courtSection.querySelectorAll('.join-button');
                const leaveButton = courtSection.querySelector('.danger-button');
                
                if (data.action === 'join_court' || data.action === 'join_queue') {
                    // If user joined anywhere, disable join buttons everywhere
                    joinButtons.forEach(btn => btn.disabled = true);
                    
                    // Only show leave button on the court the user joined
                    if (parseInt(courtId) === data.court_id) {
                        leaveButton.classList.remove('hidden');
                    } else {
                        leaveButton.classList.add('hidden');
                    }
                }
                else if (data.action === 'leave_court') {
                    // If user left, enable join buttons everywhere
                    joinButtons.forEach(btn => btn.disabled = false);
                    
                    // Hide the leave button on the court the user left
                    if (parseInt(courtId) === data.court_id) {
                        leaveButton.classList.add('hidden');
                    }
                }
            }
        });
    }
    
    // Function to show flash messages
    function showFlashMessage(message, category) {
        const flashContainer = document.getElementById('flashMessages');
        const msgElement = document.createElement('div');
        msgElement.className = `flash-message ${category}`;
        msgElement.textContent = message;
        
        flashContainer.appendChild(msgElement);
        
        // Set color based on category
        switch(category) {
            case 'success':
                msgElement.style.backgroundColor = '#34C759'; // iOS Green
                break;
            case 'error':
                msgElement.style.backgroundColor = '#FF3B30'; // iOS Red
                break;
            case 'warning':
                msgElement.style.backgroundColor = '#FF9500'; // iOS Orange
                break;
            default:
                msgElement.style.backgroundColor = '#007AFF'; // iOS Blue
                break;
        }
        
        // Trigger reflow for animation to work
        void msgElement.offsetWidth;
        
        // Fade in
        msgElement.classList.add('fade-in');
        
        // Fade out after 4 seconds
        setTimeout(() => {
            msgElement.classList.remove('fade-in');
            msgElement.classList.add('fade-out');
            setTimeout(() => {
                msgElement.remove();
            }, 500);
        }, 4000);
    }
});

// Add a function to manually refresh courts if needed
async function refreshCourts() {
    try {
        const response = await fetch('/court-updates-poll');
        const data = await response.json();
        if (data.courts && courtManager) {
            courtManager.updateCourtsDisplay(data.courts);
        }
    } catch (error) {
        console.error('Error refreshing courts:', error);
    }
}

// Test if server-sent events are working, and if not, set up manual refresh
let sseWorkingTest = false;
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        if (!sseWorkingTest && courtManager) {
            console.log("SSE might not be working, setting up manual refresh trigger");
            
            // Add a manual refresh after court actions
            document.querySelectorAll('.court-action-form').forEach(form => {
                const originalSubmit = form.onsubmit;
                form.onsubmit = async function(e) {
                    if (originalSubmit) {
                        originalSubmit.call(this, e);
                    }
                    
                    // After a short delay, manually refresh
                    setTimeout(refreshCourts, 500);
                };
            });
            
            // Also set up periodic refresh just in case
            setInterval(refreshCourts, 5000);
        }
    }, 5000); // Check after 5 seconds
});

// Update the sse test flag when a message is received
if (courtManager && courtManager.evtSource) {
    courtManager.evtSource.addEventListener('message', () => {
        sseWorkingTest = true;
    });
}