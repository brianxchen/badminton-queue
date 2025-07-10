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
                }
            }
        }

        // At the end of the method, after all DOM updates
        this.reattachEventListeners();
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

    generatePlayerSlotHTML(player, group) {
        const isCurrentUser = player === window.currentUser;
        return `
            <div class="player-slot occupied ${isCurrentUser ? 'my-slot' : ''}">
                <span class="player-name">${player}</span>
                ${isCurrentUser ? 
                    '<span class="player-indicator">You</span><button class="leave-button" onclick="leaveGroup()">Leave</button>' : 
                    ''}
            </div>
        `;
    }

    reattachEventListeners() {
        // First, remove existing event listeners by cloning and replacing elements
        
        // Handle empty slot clicks to join a group
        document.querySelectorAll('.player-slot.empty[data-group-id]').forEach(slot => {
            const newSlot = slot.cloneNode(true);
            slot.parentNode.replaceChild(newSlot, slot);
            
            newSlot.addEventListener('click', function() {
                const groupId = this.getAttribute('data-group-id');
                joinGroup(groupId);
            });
        });
        
        // Handle create new group buttons
        document.querySelectorAll('.create-group-button').forEach(button => {
            const newButton = button.cloneNode(true);
            button.parentNode.replaceChild(newButton, button);
            
            newButton.addEventListener('click', function() {
                const courtId = this.getAttribute('data-court-id');
                createNewGroup(courtId);
            });
        });
        
        // Handle tap on user's own slot for mobile
        document.querySelectorAll('.player-slot.my-slot').forEach(slot => {
            const newSlot = slot.cloneNode(true);
            slot.parentNode.replaceChild(newSlot, slot);
            
            // Re-add the leave button click handler
            const leaveButton = newSlot.querySelector('.leave-button');
            if (leaveButton) {
                leaveButton.onclick = () => leaveGroup();
            }
            
            newSlot.addEventListener('click', function(e) {
                // Don't toggle if clicking directly on the leave button
                if (e.target.classList.contains('leave-button')) {
                    return;
                }
                
                // Toggle the show-leave-button class
                this.classList.toggle('show-leave-button');
                
                // Add a click handler to the document to close the button when clicking elsewhere
                const closeLeaveButton = function(event) {
                    if (!newSlot.contains(event.target)) {
                        newSlot.classList.remove('show-leave-button');
                        document.removeEventListener('click', closeLeaveButton);
                    }
                };
                
                // Add the document click handler with a slight delay to avoid immediate triggering
                if (this.classList.contains('show-leave-button')) {
                    setTimeout(() => {
                        document.addEventListener('click', closeLeaveButton);
                    }, 10);
                }
            });
        });
    }
}

// Add at the top of the file, outside any class
let isProcessingRequest = false;
let pendingActions = new Set();

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

function createNewGroup(courtId) {
  console.log('Creating new group for court:', courtId);
  
  // Global check if any request is currently processing
  if (isProcessingRequest) {
    console.log('Request already in progress, please wait...');
    return;
  }
  
  // Record this specific action to prevent duplicates
  const actionId = `create_group_${courtId}`;
  if (pendingActions.has(actionId)) {
    console.log('This action is already pending');
    return;
  }
  
  // Set global processing flag immediately
  isProcessingRequest = true;
  pendingActions.add(actionId);
  
  // Disable ALL interactive elements to prevent any other actions
  disableAllInteractions('Creating group...');
  
  // Visual feedback for the specific button
  const clickedButton = document.querySelector(`.create-group-button[data-court-id="${courtId}"]`);
  if (clickedButton) {
    clickedButton.disabled = true;
    clickedButton.textContent = 'Creating...';
    clickedButton.classList.add('processing');
  }
  
  // Immediately disable all other create group buttons to prevent double clicks
  document.querySelectorAll(`.create-group-button:not([data-court-id="${courtId}"])`).forEach(btn => {
    btn.disabled = true;
  });
  
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
      
      // For a more reliable update, just reload the page
      location.reload();
    } else {
      showFlashMessage(data.message, 'error');
      resetInteractionState(actionId, clickedButton, 'Create New Group');
    }
  })
  .catch(error => {
    console.error('Error creating group:', error);
    showFlashMessage('Error creating group', 'error');
    resetInteractionState(actionId, clickedButton, 'Create New Group');
  });
}

function joinGroup(groupId) {
  if (isProcessingRequest) {
    console.log('Request already in progress, please wait...');
    return;
  }
  
  const actionId = `join_group_${groupId}`;
  if (pendingActions.has(actionId)) {
    console.log('This action is already pending');
    return;
  }
  
  isProcessingRequest = true;
  pendingActions.add(actionId);
  
  disableAllInteractions('Joining group...');
  
  const clickedSlot = document.querySelector(`.player-slot.empty[data-group-id="${groupId}"]`);
  if (clickedSlot) {
    clickedSlot.style.opacity = '0.5';
    clickedSlot.style.pointerEvents = 'none';
  }
  
  fetch(`/join-slot/${groupId}`, {
    method: 'POST',
    headers: { 'X-Requested-With': 'XMLHttpRequest' }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showFlashMessage(data.message, 'success');
      sessionStorage.setItem('forceUpdate', 'true');
      location.reload();
    } else {
      showFlashMessage(data.message, 'error');
      resetInteractionState(actionId, clickedSlot);
    }
  })
  .catch(error => {
    console.error('Error joining group:', error);
    showFlashMessage('Error joining group', 'error');
    resetInteractionState(actionId, clickedSlot);
  });
}

function leaveGroup() {
  if (isProcessingRequest) {
    console.log('Request already in progress, please wait...');
    return;
  }
  
  const actionId = 'leave_group';
  if (pendingActions.has(actionId)) {
    console.log('This action is already pending');
    return;
  }
  
  isProcessingRequest = true;
  pendingActions.add(actionId);
  
  disableAllInteractions('Leaving group...');
  
  // Visual feedback for leave buttons
  document.querySelectorAll('.leave-button').forEach(button => {
    button.disabled = true;
    button.textContent = 'Leaving...';
  });
  
  fetch('/leave-group', {
    method: 'POST',
    headers: { 'X-Requested-With': 'XMLHttpRequest' }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showFlashMessage(data.message, 'warning');
      sessionStorage.setItem('forceUpdate', 'true');
      location.reload();
    } else {
      showFlashMessage(data.message, 'error');
      resetInteractionState(actionId, null, null, '.leave-button');
    }
  })
  .catch(error => {
    console.error('Error leaving group:', error);
    showFlashMessage('Error leaving group', 'error');
    resetInteractionState(actionId, null, null, '.leave-button');
  });
}

// Add these helper functions
function disableAllInteractions(message = 'Processing...') {
  // Disable all buttons
  document.querySelectorAll('button').forEach(button => {
    if (!button.hasAttribute('data-original-text')) {
      button.setAttribute('data-original-text', button.textContent);
    }
    button.disabled = true;
  });
  
  // Disable all player slots
  document.querySelectorAll('.player-slot.empty[data-group-id]').forEach(slot => {
    slot.style.opacity = '0.5';
    slot.style.pointerEvents = 'none';
  });
  
  // Optional: Add a global overlay to prevent all interactions
  const overlay = document.createElement('div');
  overlay.id = 'processing-overlay';
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.1);
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
    pointer-events: all;
  `;
  
  // Only add if it doesn't already exist
  if (!document.getElementById('processing-overlay')) {
    document.body.appendChild(overlay);
  }
}

function resetInteractionState(actionId, specificElement = null, originalText = null, selectorForMultiple = null) {
  // Remove the action from pending
  pendingActions.delete(actionId);
  
  // Only fully reset if no other actions are pending
  if (pendingActions.size === 0) {
    isProcessingRequest = false;
    
    // Re-enable all buttons
    document.querySelectorAll('button').forEach(button => {
      button.disabled = false;
      if (button.hasAttribute('data-original-text')) {
        button.textContent = button.getAttribute('data-original-text');
        button.removeAttribute('data-original-text');
      }
    });
    
    // Re-enable all player slots
    document.querySelectorAll('.player-slot.empty[data-group-id]').forEach(slot => {
      slot.style.opacity = '';
      slot.style.pointerEvents = '';
    });
    
    // Remove the overlay
    const overlay = document.getElementById('processing-overlay');
    if (overlay) {
      overlay.remove();
    }
  }
  
  // Always handle the specific element that triggered the action
  if (specificElement) {
    specificElement.disabled = false;
    specificElement.style.opacity = '';
    specificElement.style.pointerEvents = '';
    specificElement.classList.remove('processing');
    if (originalText) {
      specificElement.textContent = originalText;
    }
  }
  
  // If a selector for multiple elements is provided
  if (selectorForMultiple) {
    document.querySelectorAll(selectorForMultiple).forEach(el => {
      el.disabled = false;
      el.textContent = originalText || 'Leave';
      el.style.opacity = '';
      el.style.pointerEvents = '';
    });
  }
}

// Add CSS for the processing state
document.addEventListener('DOMContentLoaded', function() {
  const style = document.createElement('style');
  style.textContent = `
    button.processing {
      opacity: 0.7;
      cursor: not-allowed;
      position: relative;
    }
    
    button.processing::after {
      content: '';
      position: absolute;
      width: 16px;
      height: 16px;
      top: calc(50% - 8px);
      left: calc(50% - 8px);
      border: 2px solid rgba(255,255,255,0.5);
      border-top: 2px solid white;
      border-radius: 50%;
      animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(style);
});

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