class CourtManager {
    constructor() {
        this.initializeEventSource();
        this.initializeTimer();
    }

    initializeEventSource() {
        this.evtSource = new EventSource('/court-updates');
        
        this.evtSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.courts) {
                this.updateCourtsDisplay(data.courts);
            }
        };
        
        this.evtSource.onerror = (err) => {
            console.error('EventSource failed:', err);
            this.evtSource.close();
            setTimeout(() => this.initializeEventSource(), 5000);
        };
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

            // Update players list
            const playersUl = courtElement.querySelector('.current-players');
            if (playersUl) {
                // Important: Add check for if the array exists AND has length
                if (Array.isArray(courtData.players) && courtData.players.length > 0) {
                    playersUl.innerHTML = courtData.players
                        .map(player => `
                            <li>
                                <span class="player-name">${player}</span>
                                ${player === window.currentUser ? 
                                    '<span class="player-indicator">You</span>' : 
                                    ''}
                            </li>
                        `).join('');
                } else {
                    // Always show the empty message when no players
                    playersUl.innerHTML = '<li class="empty-message">No players currently on court</li>';
                }
            }

            // Update queue list with numbers
            const queueUl = courtElement.querySelector('.queue');
            if (queueUl) {
                // Important: Add check for if the array exists AND has length
                if (Array.isArray(courtData.queue) && courtData.queue.length > 0) {
                    queueUl.innerHTML = courtData.queue
                        .map((player, index) => `
                            <li>
                                <span class="queue-number">${index + 1}</span>
                                <span class="player-name">${player}</span>
                                ${player === window.currentUser ? 
                                    '<span class="player-indicator">You</span>' : 
                                    ''}
                            </li>
                        `).join('');
                } else {
                    // Always show the empty message when no queue entries
                    queueUl.innerHTML = '<li class="empty-message">No one in queue</li>';
                }
            }
        }

        this.updateButtonStates(courts);
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