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
            
            // If timer expired, update courts immediately
            if (data.expired) {
                console.log("Timer expired, updating courts...");
                // If the data includes courts info, use it directly
                if (data.courts) {
                    this.updateCourtsDisplay(data.courts);
                } else {
                    // Otherwise fetch the latest court data
                    try {
                        const courtsResponse = await fetch('/court-updates-poll');
                        const courtsData = await courtsResponse.json();
                        if (courtsData.courts) {
                            this.updateCourtsDisplay(courtsData.courts);
                        }
                    } catch (error) {
                        console.error('Error fetching courts after timer expiration:', error);
                    }
                }
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
        this.courts = courts; // Store the courts data for helper methods
        
        for (const [courtName, courtData] of Object.entries(courts)) {
            const courtId = courtName.replace(' ', '-');
            const courtElement = document.getElementById(courtId);
            if (!courtElement) continue;

            // Update active groups
            const playersContainer = courtElement.querySelector('.court-group');
            if (playersContainer) {
                // Compare new data with current DOM state to avoid unnecessary updates
                // Only update if there are changes to the groups or players
                const shouldUpdate = this.shouldUpdateDisplay(courtData.active_groups, playersContainer);
                
                if (shouldUpdate) {
                    if (courtData.active_groups && courtData.active_groups.length > 0) {
                        let groupsHTML = '';
                        
                        courtData.active_groups.forEach(group => {
                            let playerSlotsHTML = '';
                            
                            // Add occupied slots
                            group.players.forEach(player => {
                                playerSlotsHTML += this.generatePlayerSlotHTML(player, group);
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
                        // Handle empty court case
                        this.handleEmptyCourt(playersContainer, courtData.id);
                    }
                }
            }

            // Update queue groups with the same approach
            const queueContainer = courtElement.querySelector('.queue-groups');
            if (queueContainer) {
                // Always update queue data on changes to ensure visibility of newly joined groups
                if (courtData.queue_groups && courtData.queue_groups.length > 0) {
                    let queueHTML = '';
                    
                    // Sort queue groups by position
                    const sortedQueueGroups = [...courtData.queue_groups].sort((a, b) => a.position - b.position);
                    
                    sortedQueueGroups.forEach(group => {
                        queueHTML += `
                            <div class="queue-group">
                                <div class="queue-header">
                                    <span class="queue-number">${group.position}</span>
                                </div>
                                
                                <div class="queue-slots">
                        `;
                        
                        // Add occupied slots
                        group.players.forEach(player => {
                            queueHTML += `
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
                            queueHTML += `
                                <div class="player-slot empty" ${!isUserActive ? `data-group-id="${group.id}"` : ''}>
                                    <span class="slot-placeholder">Empty Slot</span>
                                </div>
                            `;
                        }
                        
                        queueHTML += `
                                </div>
                            </div>
                        `;
                    });
                    
                    // Add the "Create New Group" button if user is not active
                    const isUserActive = this.isUserActive();
                    if (window.currentUser && !isUserActive) {
                        queueHTML += `
                            <div class="create-group-container">
                                <button class="create-group-button" data-court-id="${courtData.id}">
                                    Create New Group
                                </button>
                            </div>
                        `;
                    }
                    
                    queueContainer.innerHTML = queueHTML;
                    
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
                    let queueHTML = `<div class="empty-message">No one in queue</div>`;
                    
                    // Add the "Create New Group" button if user is not active
                    const isUserActive = this.isUserActive();
                    if (window.currentUser && !isUserActive) {
                        queueHTML += `
                            <div class="create-group-container">
                                <button class="create-group-button" data-court-id="${courtData.id}">
                                    Create New Group
                                </button>
                            </div>
                        `;
                    }
                    
                    queueContainer.innerHTML = queueHTML;
                    
                    // Add click event listeners to create group buttons
                    queueContainer.querySelectorAll('.create-group-button').forEach(button => {
                        button.addEventListener('click', function() {
                            const courtId = this.getAttribute('data-court-id');
                            createNewGroup(courtId);
                        });
                    });
                }
            }
        }
    }

    shouldUpdateDisplay(groups, container) {
        // If there's no data or container, we need to update
        if (!groups || !container) return true;
        
        // If there's a loading-slot showing, we need to update
        if (container.querySelector('.loading-slot')) return true;
        
        try {
            // If a user just joined or left (indicated by URL param or sessionStorage)
            if (sessionStorage.getItem('forceUpdate') === 'true') {
                sessionStorage.removeItem('forceUpdate');
                return true;
            }
            
            // Check if user is hovering over their slot - if so, don't update while hovering
            const userSlot = container.querySelector('.player-slot.my-slot:hover');
            if (userSlot) {
                return false;
            }
            
            // Check if number of groups changed
            const currentGroupElements = container.querySelectorAll('.player-group');
            if (!groups || currentGroupElements.length !== groups.length) return true;
            
            // Check if any group's player count changed
            let playersChanged = false;
            
            currentGroupElements.forEach((groupElement, i) => {
                if (i >= groups.length) return;
                
                const currentOccupiedSlots = groupElement.querySelectorAll('.player-slot.occupied');
                if (!groups[i].players || currentOccupiedSlots.length !== groups[i].players.length) {
                    playersChanged = true;
                    return;
                }
                
                // Check if player names match
                const currentPlayerNames = Array.from(currentOccupiedSlots).map(slot => 
                    slot.querySelector('.player-name').textContent.trim());
                
                if (!this.arraysEqual(currentPlayerNames, groups[i].players)) {
                    playersChanged = true;
                    return;
                }
            });
            
            return playersChanged;
        } catch (e) {
            console.error('Error checking if display should update:', e);
            return true; // Update if there's an error
        }
    }

    arraysEqual(a, b) {
        if (a.length !== b.length) return false;
        return a.every((val, i) => val === b[i]);
    }

    handleEmptyCourt(container, courtId) {
        // Instead of showing "No players", create a new group automatically
        // First, fetch the court ID
        fetch(`/create-empty-active-group/${courtId}`, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Now display the empty slots with the new group ID
                let emptyGroupHTML = `
                    <div class="player-group">
                `;
                
                // Generate empty slots with the new group ID
                const isUserActive = this.isUserActive();
                for (let i = 0; i < window.MAX_PLAYERS; i++) {
                    emptyGroupHTML += `
                        <div class="player-slot empty" ${!isUserActive ? `data-group-id="${data.group_id}"` : ''}>
                            <span class="slot-placeholder">Empty Slot</span>
                        </div>
                    `;
                }
                
                emptyGroupHTML += `</div>`;
                container.innerHTML = emptyGroupHTML;
                
                // Add click event listeners
                container.querySelectorAll('.player-slot.empty[data-group-id]').forEach(slot => {
                    slot.addEventListener('click', function() {
                        const groupId = this.getAttribute('data-group-id');
                        joinGroup(groupId);
                    });
                });
            } else {
                // Fallback if there's an error
                container.innerHTML = `
                    <div class="player-group">
                        ${Array(window.MAX_PLAYERS).fill(`
                            <div class="player-slot empty">
                                <span class="slot-placeholder">Empty Slot</span>
                            </div>
                        `).join('')}
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error creating empty active group:', error);
            // Fallback if there's an error
            container.innerHTML = `
                <div class="player-group">
                    ${Array(window.MAX_PLAYERS).fill(`
                        <div class="player-slot empty">
                            <span class="slot-placeholder">Empty Slot</span>
                        </div>
                    `).join('')}
                </div>
            `;
        });
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

function joinGroup(groupId) {
  fetch(`/join-slot/${groupId}`, {
    method: 'POST',
    headers: { 'X-Requested-With': 'XMLHttpRequest' }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showFlashMessage(data.message, 'success');
      
      // Force an immediate refresh of the display
      sessionStorage.setItem('forceUpdate', 'true');
      refreshCourts();
    } else {
      showFlashMessage(data.message, 'error');
    }
  })
  .catch(error => {
    console.error('Error joining group:', error);
    showFlashMessage('Error joining group', 'error');
  });
}

function createNewGroup(courtId) {
  fetch(`/create-new-group/${courtId}`, {
    method: 'POST',
    headers: { 'X-Requested-With': 'XMLHttpRequest' }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showFlashMessage(data.message, 'success');
      
      // Force an immediate refresh of the display
      sessionStorage.setItem('forceUpdate', 'true');
      refreshCourts();
    } else {
      showFlashMessage(data.message, 'error');
    }
  })
  .catch(error => {
    console.error('Error creating group:', error);
    showFlashMessage('Error creating group', 'error');
  });
}

function leaveGroup() {
  fetch('/leave-group', {
    method: 'POST',
    headers: { 'X-Requested-With': 'XMLHttpRequest' }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showFlashMessage(data.message, 'warning');
      
      // Force an immediate refresh of the display
      sessionStorage.setItem('forceUpdate', 'true');
      refreshCourts();
    } else {
      showFlashMessage(data.message, 'error');
    }
  })
  .catch(error => {
    console.error('Error leaving group:', error);
    showFlashMessage('Error leaving group', 'error');
  });
}

// Add this helper function for immediate refresh
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