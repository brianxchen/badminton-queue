class CourtManager {
    constructor() {
        this.connectionAttempts = 0;
        this.maxConnectionAttempts = 5;
        this.retryInterval = 3000; // 3 seconds
        this.initializeEventSource();
        this.initializeTimer();
    }

    initializeEventSource() {
        this.evtSource = new EventSource('/court-updates');
        
        this.evtSource.onmessage = (event) => {
            console.log("SSE message received"); // Debug log
            this.connectionAttempts = 0; // Reset connection attempts on successful message
            try {
                const data = JSON.parse(event.data);
                if (data.courts) {
                    this.updateCourtsDisplay(data.courts);
                }
            } catch (err) {
                console.error("Error parsing SSE data:", err);
            }
        };
        
        this.evtSource.onerror = (err) => {
            console.error('EventSource failed:', err);
            this.evtSource.close();
            
            // Increment connection attempts
            this.connectionAttempts++;
            
            if (this.connectionAttempts < this.maxConnectionAttempts) {
                console.log(`Retrying SSE connection (${this.connectionAttempts}/${this.maxConnectionAttempts})...`);
                setTimeout(() => this.initializeEventSource(), this.retryInterval);
            } else {
                console.error("Max SSE connection attempts reached. Falling back to polling.");
                this.startPolling();
            }
        };
        
        this.evtSource.onopen = () => {
            console.log("SSE connection opened");
            // If we were polling, stop it
            if (this.pollingInterval) {
                console.log("Stopping fallback polling");
                clearInterval(this.pollingInterval);
                this.pollingInterval = null;
            }
        };
    }
    
    // Fallback to polling if SSE fails
    startPolling() {
        console.log("Starting fallback polling for court updates");
        this.pollingInterval = setInterval(async () => {
            try {
                const response = await fetch('/court-updates-poll');
                const data = await response.json();
                if (data.courts) {
                    this.updateCourtsDisplay(data.courts);
                }
            } catch (error) {
                console.error('Error polling for updates:', error);
            }
        }, 2000); // Poll every 2 seconds
    }

    initializeTimer() {
        // Get initial timer state
        this.updateTimerDisplay();
        // Update timer every second
        this.timerInterval = setInterval(() => this.updateTimerDisplay(), 1000);
    }

    async updateTimerDisplay() {
        try {
            const response = await fetch('/timer/status');
            const data = await response.json();
            const timerElement = document.getElementById('timer');
            if (timerElement) {
                timerElement.textContent = this.formatTime(data.remaining);
            }
        } catch (error) {
            console.error('Error updating timer:', error);
        }
    }

    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    updateCourtsDisplay(courts) {
        for (const [courtName, courtData] of Object.entries(courts)) {
            const courtId = courtName.replace(' ', '-');
            const courtElement = document.getElementById(courtId);
            if (!courtElement) continue;

            // Update active groups
            const playersContainer = courtElement.querySelector('.court-group');
            if (playersContainer) {
                if (courtData.active_groups && courtData.active_groups.length > 0) {
                    let groupsHTML = '';
                    
                    courtData.active_groups.forEach(group => {
                        let playerSlotsHTML = '';
                        
                        // Add occupied slots
                        group.players.forEach(player => {
                            playerSlotsHTML += `
                                <div class="player-slot occupied ${player === window.currentUser ? 'my-slot' : ''}">
                                    <span class="player-name">${player}</span>
                                    ${player === window.currentUser ? 
                                        '<span class="player-indicator">You</span><button class="leave-button" onclick="leaveGroup()">Leave</button>' : 
                                        ''}
                                </div>
                            `;
                        });
                        
                        // Add empty slots
                        const emptySlots = MAX_PLAYERS - group.players.length;
                        for (let i = 0; i < emptySlots; i++) {
                            const isUserActive = this.isUserActive();
                            playerSlotsHTML += `
                                <div class="player-slot empty" ${!isUserActive ? `data-group-id="${group.id}"` : ''}>
                                    <span class="slot-placeholder">Empty Slot</span>
                                </div>
                            `;
                        }
                        
                        groupsHTML += `
                            <div class="player-group ${group.is_full ? 'full' : ''}">
                                ${playerSlotsHTML}
                            </div>
                        `;
                    });
                    
                    playersContainer.innerHTML = groupsHTML;
                    
                    // Add click event listeners to empty slots
                    playersContainer.querySelectorAll('.player-slot.empty[data-group-id]').forEach(slot => {
                        slot.addEventListener('click', function() {
                            const groupId = this.getAttribute('data-group-id');
                            joinGroup(groupId);
                        });
                    });
                } else {
                    playersContainer.innerHTML = '<div class="empty-message">No players currently on court</div>';
                }
            }

            // Update queue groups
            const queueContainer = courtElement.querySelector('.queue-groups');
            if (queueContainer) {
                if (courtData.queue_groups && courtData.queue_groups.length > 0) {
                    let groupsHTML = '';
                    
                    courtData.queue_groups.forEach(group => {
                        let playerSlotsHTML = '';
                        
                        // Add occupied slots
                        group.players.forEach(player => {
                            playerSlotsHTML += `
                                <div class="player-slot occupied ${player === window.currentUser ? 'my-slot' : ''}">
                                    <span class="player-name">${player}</span>
                                    ${player === window.currentUser ? 
                                        '<span class="player-indicator">You</span><button class="leave-button" onclick="leaveGroup()">Leave</button>' : 
                                        ''}
                                </div>
                            `;
                        });
                        
                        // Add empty slots
                        const emptySlots = MAX_PLAYERS - group.players.length;
                        for (let i = 0; i < emptySlots; i++) {
                            const isUserActive = this.isUserActive();
                            playerSlotsHTML += `
                                <div class="player-slot empty" ${!isUserActive ? `data-group-id="${group.id}"` : ''}>
                                    <span class="slot-placeholder">Empty Slot</span>
                                </div>
                            `;
                        }
                        
                        groupsHTML += `
                            <div class="queue-group">
                                <div class="queue-header">
                                    <span class="queue-number">${group.position}</span>
                                </div>
                                <div class="queue-slots">
                                    ${playerSlotsHTML}
                                </div>
                            </div>
                        `;
                    });
                    
                    // Always add "Create New Group" button if user is logged in and not active
                    if (window.currentUser && !this.isUserActive()) {
                        groupsHTML += `
                            <div class="create-group-container">
                                <button class="create-group-button" data-court-id="${courtData.id}">
                                    Create New Group
                                </button>
                            </div>
                        `;
                    }
                    
                    queueContainer.innerHTML = groupsHTML;
                    
                    // Add click event listeners to empty slots
                    queueContainer.querySelectorAll('.player-slot.empty[data-group-id]').forEach(slot => {
                        slot.addEventListener('click', function() {
                            const groupId = this.getAttribute('data-group-id');
                            joinGroup(groupId);
                        });
                    });
                    
                    // Add click event listeners to create group buttons
                    queueContainer.querySelectorAll('.create-group-button').forEach(button => {
                        button.addEventListener('click', function() {
                            const courtId = this.getAttribute('data-court-id');
                            createNewGroup(courtId);
                        });
                    });
                } else {
                    let html = '<div class="empty-message">No one in queue</div>';
                    
                    // Always add "Create New Group" button if user is logged in and not active
                    if (window.currentUser && !this.isUserActive()) {
                        html += `
                            <div class="create-group-container">
                                <button class="create-group-button" data-court-id="${courtData.id}">
                                    Create New Group
                                </button>
                            </div>
                        `;
                    }
                    
                    queueContainer.innerHTML = html;
                    
                    // Add click event listeners to create group buttons
                    queueContainer.querySelectorAll('.create-group-button').forEach(button => {
                        button.addEventListener('click', function() {
                            const courtId = this.getAttribute('data-court-id');
                            createNewGroup(courtId);
                        });
                    });
                }
            }
            
            // Update leave button visibility
            const leaveButton = courtElement.querySelector('.leave-group-button');
            if (leaveButton) {
                const isUserInThisCourt = this.isUserInCourt(courtData);
                leaveButton.style.display = isUserInThisCourt ? 'block' : 'none';
            }
        }
    }

    // Helper methods
    isUserActive() {
        if (!window.currentUser) return false;
        
        // Check all courts to see if user is in any group
        return Object.values(this.courts || {}).some(court => {
            return this.isUserInCourt(court);
        });
    }

    isUserInCourt(courtData) {
        if (!window.currentUser) return false;
        
        // Check active groups
        if (courtData.active_groups) {
            for (const group of courtData.active_groups) {
                if (group.players.includes(window.currentUser)) {
                    return true;
                }
            }
        }
        
        // Check queue groups
        if (courtData.queue_groups) {
            for (const group of courtData.queue_groups) {
                if (group.players.includes(window.currentUser)) {
                    return true;
                }
            }
        }
        
        return false;
    }

    updateButtonStates(courts) {
        if (!window.currentUser) return;
        
        const isUserActive = Object.values(courts).some(court => 
            (Array.isArray(court.players) && court.players.includes(window.currentUser)) || 
            (Array.isArray(court.queue) && court.queue.includes(window.currentUser))
        );

        document.querySelectorAll('.join-button').forEach(button => {
            button.disabled = isUserActive;
        });

        Object.entries(courts).forEach(([courtName, courtData]) => {
            const courtId = courtName.replace(' ', '-');
            const courtElement = document.getElementById(courtId);
            if (!courtElement) return;

            const isUserOnThisCourt = 
                (Array.isArray(courtData.players) && courtData.players.includes(window.currentUser)) || 
                (Array.isArray(courtData.queue) && courtData.queue.includes(window.currentUser));
                
            const leaveButton = courtElement.querySelector('.danger-button');
            if (leaveButton) {
                leaveButton.classList.toggle('hidden', !isUserOnThisCourt);
            }
        });
    }

    cleanup() {
        if (this.evtSource) {
            this.evtSource.close();
        }
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }
    }
}

// Initialize on page load
let courtManager;
document.addEventListener('DOMContentLoaded', () => {
    courtManager = new CourtManager();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (courtManager) {
        courtManager.cleanup();
    }
});

async function toggleClubStatus() {
    try {
        const response = await fetch('/toggle-club-status', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            const button = document.getElementById('clubStatusToggle');
            button.textContent = data.is_active ? 'Deactivate Club' : 'Activate Club';
            button.setAttribute('data-active', data.is_active);
            
            // Show confirmation message
            const message = data.is_active ? 
                'Club is now active. Members can join courts.' : 
                'Club is now inactive. Members cannot access the system.';
            alert(message);
            
            // Refresh page to update UI
            location.reload();
        }
    } catch (error) {
        console.error('Error toggling club status:', error);
        alert('Failed to toggle club status');
    }
}

// Initialize event listener for updates 
function initLiveUpdates() {
    // This function is called from base.html
    if (!courtManager) {
        courtManager = new CourtManager();
    }
}