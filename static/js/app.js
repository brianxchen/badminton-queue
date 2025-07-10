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
                    
                    // Show success message
                    showFlashMessage(data.message, 'success');
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
        const courtId = data.court_id;
        const username = data.username;
        const action = data.action;
        
        // Find the court container
        const courtContainer = document.querySelector(`.court-container[data-court-id="${courtId}"]`);
        
        if (action === 'join_queue') {
            // Hide join buttons
            courtContainer.querySelector('.join-buttons').style.display = 'none';
            // Show leave button
            courtContainer.querySelector('.leave-button').style.display = 'block';
            
            // Update queue display
            const queueList = courtContainer.querySelector('.queue-list');
            const listItem = document.createElement('li');
            listItem.textContent = username;
            listItem.classList.add('queue-item');
            listItem.dataset.username = username;
            queueList.appendChild(listItem);
        } 
        else if (action === 'join_court') {
            // Hide join buttons
            courtContainer.querySelector('.join-buttons').style.display = 'none';
            // Show leave button
            courtContainer.querySelector('.leave-button').style.display = 'block';
            
            // Update players display
            const playersList = courtContainer.querySelector('.players-list');
            const listItem = document.createElement('li');
            listItem.textContent = username;
            listItem.classList.add('player-item');
            listItem.dataset.username = username;
            playersList.appendChild(listItem);
        }
        else if (action === 'leave_court') {
            // Show join buttons
            courtContainer.querySelector('.join-buttons').style.display = 'block';
            // Hide leave button
            courtContainer.querySelector('.leave-button').style.display = 'none';
            
            // Remove from players/queue
            const playerItem = courtContainer.querySelector(`.player-item[data-username="${username}"]`);
            if (playerItem) playerItem.remove();
            
            const queueItem = courtContainer.querySelector(`.queue-item[data-username="${username}"]`);
            if (queueItem) queueItem.remove();
        }
    }
    
    // Function to show flash messages
    function showFlashMessage(message, category) {
        const flashContainer = document.getElementById('flashMessages');
        const msgElement = document.createElement('div');
        msgElement.className = `flash-message ${category}`;
        msgElement.textContent = message;
        
        flashContainer.appendChild(msgElement);
        
        // Fade in
        setTimeout(() => {
            msgElement.style.opacity = '1';
        }, 10);
        
        // Fade out after 3 seconds
        setTimeout(() => {
            msgElement.style.opacity = '0';
            setTimeout(() => {
                msgElement.remove();
            }, 500);
        }, 3000);
    }
});