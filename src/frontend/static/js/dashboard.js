// Tab Navigation
document.addEventListener('DOMContentLoaded', function() {
    initializeTabs();
    initializeProfileForm();
    setupWhatsAppButton();
});

function initializeTabs() {
    const profileTab = document.getElementById('profileTab');
    const recommendationsTab = document.getElementById('recommendationsTab');
    
    profileTab.addEventListener('click', () => switchTab('profile'));
    recommendationsTab.addEventListener('click', () => switchTab('recommendations'));
}

function switchTab(tabName) {
    const profileSection = document.getElementById('profileSection');
    const recommendationsSection = document.getElementById('recommendationsSection');
    const profileTab = document.getElementById('profileTab');
    const recommendationsTab = document.getElementById('recommendationsTab');

    // Reset active states
    [profileTab, recommendationsTab].forEach(tab => tab.classList.remove('active'));
    
    if (tabName === 'profile') {
        profileSection.classList.remove('hidden');
        recommendationsSection.classList.add('hidden');
        profileTab.classList.add('active');
    } else {
        profileSection.classList.add('hidden');
        recommendationsSection.classList.remove('hidden');
        recommendationsTab.classList.add('active');
        loadHealthRecommendations();
    }
}

// Profile Form Handler
function initializeProfileForm() {
    const form = document.getElementById('profileForm');
    form.addEventListener('submit', handleProfileSubmit);
    loadUserProfile();
}

async function loadUserProfile() {
    try {
        const response = await fetch('/api/profile');
        if (response.ok) {
            const profile = await response.json();
            populateProfileForm(profile);
        }
    } catch (error) {
        showNotification('Error loading profile', 'error');
    }
}

function populateProfileForm(profile) {
    const form = document.getElementById('profileForm');
    Object.entries(profile).forEach(([key, value]) => {
        const input = form.elements[key];
        if (input) {
            input.value = Array.isArray(value) ? value.join(', ') : value;
        }
    });
}

async function handleProfileSubmit(e) {
    e.preventDefault();
    const form = e.target;
    
    try {
        form.classList.add('loading');
        const formData = new FormData(form);
        const profileData = Object.fromEntries(formData);

        // Convert comma-separated strings to arrays
        ['medicalConditions', 'allergies', 'dietaryPreferences'].forEach(field => {
            if (profileData[field]) {
                profileData[field] = profileData[field].split(',').map(item => item.trim());
            }
        });

        const response = await fetch('/api/profile/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(profileData)
        });

        if (response.ok) {
            showNotification('Profile updated successfully!', 'success');
            loadHealthRecommendations();
        } else {
            throw new Error('Failed to update profile');
        }
    } catch (error) {
        showNotification(error.message, 'error');
    } finally {
        form.classList.remove('loading');
    }
}

// AI Recommendations
async function loadHealthRecommendations() {
    const recommendationsSection = document.getElementById('recommendationsSection');
    try {
        recommendationsSection.classList.add('loading');
        
        const response = await fetch('/api/recommendations');
        if (response.ok) {
            const recommendations = await response.json();
            updateRecommendationsUI(recommendations);
        } else {
            throw new Error('Failed to load recommendations');
        }
    } catch (error) {
        showNotification(error.message, 'error');
    } finally {
        recommendationsSection.classList.remove('loading');
    }
}

function updateRecommendationsUI(recommendations) {
    updateNutritionGoals(recommendations.nutritionGoals);
    updateMenuRecommendations(recommendations.menuItems);
    updateHealthAdvice(recommendations.healthAdvice);
}

function updateNutritionGoals(goals) {
    const container = document.getElementById('nutritionGoals');
    container.innerHTML = '';

    Object.entries(goals).forEach(([nutrient, value]) => {
        const nutrientCard = document.createElement('div');
        nutrientCard.className = 'nutrition-item';
        nutrientCard.innerHTML = `
            <div class="nutrition-label">${nutrient}</div>
            <div class="nutrition-value">${value}</div>
        `;
        container.appendChild(nutrientCard);
    });
}

function updateMenuRecommendations(menuItems) {
    const container = document.getElementById('menuRecommendations');
    container.innerHTML = `
        <p>Recommended meals based on your health profile:</p>
        <ul class="menu-list">
            ${menuItems.map(item => `
                <li class="menu-item">
                    ${item.name} (${item.calories} kcal)
                    <small>${item.description || ''}</small>
                </li>
            `).join('')}
        </ul>
    `;
}

function updateHealthAdvice(advice) {
    if (!advice) return;
    
    const container = document.createElement('div');
    container.className = 'recommendation-card';
    container.innerHTML = `
        <h3 class="card-title">Health Recommendations</h3>
        <p>${advice}</p>
    `;
    
    const recommendationsSection = document.getElementById('recommendationsSection');
    recommendationsSection.appendChild(container);
}

// WhatsApp Integration
function setupWhatsAppButton() {
    const whatsappButton = document.getElementById('whatsappButton');
    whatsappButton.addEventListener('click', handleWhatsAppClick);
}

function handleWhatsAppClick() {
    // Get current recommendations
    const menuItems = document.querySelectorAll('.menu-item');
    let message = "Halo, saya ingin memesan makanan sesuai rekomendasi:\n\n";
    
    menuItems.forEach(item => {
        message += `- ${item.textContent.trim()}\n`;
    });

    const whatsappUrl = `https://wa.me/+6281275722872?text=${encodeURIComponent(message)}`;
    window.open(whatsappUrl, '_blank');
}

// Notification System
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Helper Functions
function formatNumber(value, unit = '') {
    return `${parseFloat(value).toLocaleString()}${unit}`;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}