// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeProfileForm();
    setupWhatsAppButton();
});

// Profile Form Handler
function initializeProfileForm() {
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
        profileForm.addEventListener('submit', handleProfileSubmit);
    }
}

async function handleProfileSubmit(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    try {
        const response = await fetch('/update-profile', {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });
        
        if (response.ok) {
            showNotification('Profile updated successfully!', 'success');
        } else {
            const errorData = await response.json();
            showNotification(errorData.detail || 'Failed to update profile', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('An error occurred while updating profile', 'error');
    }
}

// WhatsApp Integration
function setupWhatsAppButton() {
    updateWhatsAppLink();
}

function formatWhatsAppMessage() {
    const baseMessage = "Halo, saya ingin memesan makanan sesuai rekomendasi:";
    const recommendations = [
        "- Breakfast: Oatmeal with fruits and nuts (300 kcal)",
        "- Lunch: Grilled chicken salad (400 kcal)",
        "- Dinner: Salmon with vegetables (450 kcal)"
    ].join("\n");
    
    return encodeURIComponent(`${baseMessage}\n\n${recommendations}`);
}

function updateWhatsAppLink() {
    const whatsappButton = document.querySelector('.whatsapp-button');
    if (whatsappButton) {
        const message = formatWhatsAppMessage();
        whatsappButton.href = `https://wa.me/+6281275722872?text=${message}`;
    }
}

// Notification System
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    Object.assign(notification.style, {
        position: 'fixed',
        top: '1rem',
        right: '1rem',
        padding: '1rem',
        borderRadius: '0.375rem',
        backgroundColor: type === 'success' ? '#10B981' : '#EF4444',
        color: 'white',
        zIndex: 1000,
        opacity: 0,
        transition: 'opacity 0.3s ease'
    });
    
    document.body.appendChild(notification);
    
    // Fade in
    setTimeout(() => {
        notification.style.opacity = '1';
    }, 10);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}