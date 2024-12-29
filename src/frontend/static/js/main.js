// Auth0 configuration
const auth0Config = {
    domain: 'YOUR_AUTH0_DOMAIN',
    clientId: 'YOUR_AUTH0_CLIENT_ID',
    audience: 'YOUR_AUTH0_AUDIENCE',
};

let auth0Client = null;
let token = null;

// Initialize Auth0
const initAuth0 = async () => {
    auth0Client = new auth0.WebAuth({
        domain: auth0Config.domain,
        clientID: auth0Config.clientId,
        responseType: 'token id_token',
        audience: auth0Config.audience,
        scope: 'openid profile email',
        redirectUri: window.location.origin
    });

    // Check if user is returning from Auth0 with hash
    if (window.location.hash) {
        handleAuth0Callback();
    } else {
        updateUI();
    }
};

// Handle Auth0 callback
const handleAuth0Callback = () => {
    auth0Client.parseHash((err, authResult) => {
        if (authResult && authResult.accessToken) {
            token = authResult.accessToken;
            localStorage.setItem('token', token);
            updateUI();
            loadUserData();
        } else if (err) {
            console.error('Authentication error:', err);
        }
    });
};

// Update UI based on authentication state
const updateUI = () => {
    const token = localStorage.getItem('token');
    const loginBtn = document.getElementById('loginBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const userContent = document.getElementById('userContent');
    const welcomeMessage = document.getElementById('welcomeMessage');

    if (token) {
        loginBtn.classList.add('hidden');
        logoutBtn.classList.remove('hidden');
        userContent.classList.remove('hidden');
        welcomeMessage.classList.add('hidden');
    } else {
        loginBtn.classList.remove('hidden');
        logoutBtn.classList.add('hidden');
        userContent.classList.add('hidden');
        welcomeMessage.classList.remove('hidden');
    }
};

// Load user data from API
const loadUserData = async () => {
    try {
        const token = localStorage.getItem('token');
        if (!token) return;

        // Example API call to get user data
        const response = await fetch('YOUR_BACKEND_API_URL/users/1', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error('Failed to fetch user data');

        const userData = await response.json();
        displayUserData(userData);
    } catch (error) {
        console.error('Error loading user data:', error);
    }
};

// Display user data in the UI
const displayUserData = (userData) => {
    const healthProfile = document.getElementById('healthProfile');
    healthProfile.innerHTML = `
        <div class="space-y-2">
            <p><strong>Name:</strong> ${userData.name}</p>
            <p><strong>Email:</strong> ${userData.email}</p>
            <p><strong>Age:</strong> ${userData.health_profile.age}</p>
            <p><strong>Weight:</strong> ${userData.health_profile.weight} kg</p>
            <p><strong>Height:</strong> ${userData.health_profile.height} cm</p>
        </div>
    `;
};

// Event Listeners
document.getElementById('loginBtn').addEventListener('click', () => {
    auth0Client.authorize();
});

document.getElementById('logoutBtn').addEventListener('click', () => {
    localStorage.removeItem('token');
    window.location.href = window.location.origin;
});

// Initialize the application
initAuth0();

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
    [profileTab, recommendationsTab].forEach(tab => {
        tab.classList.remove('bg-blue-50', 'text-blue-600');
    });
    
    if (tabName === 'profile') {
        profileSection.classList.remove('hidden');
        recommendationsSection.classList.add('hidden');
        profileTab.classList.add('bg-blue-50', 'text-blue-600');
    } else {
        profileSection.classList.add('hidden');
        recommendationsSection.classList.remove('hidden');
        recommendationsTab.classList.add('bg-blue-50', 'text-blue-600');
        loadRecommendations();
    }
}

// Profile Form Handler
function initializeProfileForm() {
    const form = document.getElementById('profileForm');
    form.addEventListener('submit', handleProfileSubmit);
}

async function handleProfileSubmit(e) {
    e.preventDefault();
    const form = e.target;
    form.classList.add('loading');
    
    try {
        const formData = new FormData(form);
        const response = await fetch('/update-profile', {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });

        if (response.ok) {
            showNotification('Profile updated successfully!', 'success');
            loadRecommendations();
        } else {
            throw new Error('Failed to update profile');
        }
    } catch (error) {
        showNotification(error.message, 'error');
    } finally {
        form.classList.remove('loading');
    }
}

// Recommendations Section
async function loadRecommendations() {
    const recommendationsSection = document.getElementById('recommendationsSection');
    recommendationsSection.classList.add('loading');
    
    try {
        const response = await fetch('/recommendations');
        if (response.ok) {
            const data = await response.json();
            updateRecommendationsUI(data);
        } else {
            throw new Error('Failed to load recommendations');
        }
    } catch (error) {
        showNotification(error.message, 'error');
    } finally {
        recommendationsSection.classList.remove('loading');
    }
}

function updateRecommendationsUI(data) {
    // Update Nutrition Goals
    updateNutritionGoals(data);
    // Update Menu Recommendations
    updateMenuRecommendations(data);
}

function updateNutritionGoals(data) {
    const container = document.getElementById('nutritionGoals');
    container.innerHTML = `
        <div class="bg-white p-4 rounded-md shadow-sm">
            <p class="text-sm text-gray-500">Calories</p>
            <p class="text-lg font-semibold">${data.calories_target} kcal</p>
        </div>
        <div class="bg-white p-4 rounded-md shadow-sm">
            <p class="text-sm text-gray-500">Protein</p>
            <p class="text-lg font-semibold">${data.protein_target}g</p>
        </div>
        <div class="bg-white p-4 rounded-md shadow-sm">
            <p class="text-sm text-gray-500">Carbs</p>
            <p class="text-lg font-semibold">${data.carbs_target}g</p>
        </div>
        <div class="bg-white p-4 rounded-md shadow-sm">
            <p class="text-sm text-gray-500">Fat</p>
            <p class="text-lg font-semibold">${data.fat_target}g</p>
        </div>
    `;
}

function updateMenuRecommendations(data) {
    const container = document.getElementById('menuRecommendations');
    if (data.meal_plan && data.meal_plan.length > 0) {
        const menuItems = data.meal_plan.map(meal => 
            `<li class="menu-item p-3 bg-white rounded-md shadow-sm">
                <div class="font-medium">${meal.name}</div>
                <div class="text-sm text-gray-600">${meal.calories} kcal</div>
                ${meal.description ? `<div class="text-sm text-gray-500">${meal.description}</div>` : ''}
             </li>`
        ).join('');

        container.innerHTML = `
            <p class="text-green-600 mb-4">Here are your recommended meals:</p>
            <ul class="space-y-3">
                ${menuItems}
            </ul>
            ${data.special_instructions ? 
                `<div class="mt-4 p-3 bg-yellow-50 rounded-md">
                    <p class="text-yellow-700">${data.special_instructions}</p>
                </div>` : ''
            }
        `;
    }
}

// WhatsApp Integration
function setupWhatsAppButton() {
    const whatsappButton = document.getElementById('whatsappButton');
    whatsappButton.addEventListener('click', handleWhatsAppClick);
}

function handleWhatsAppClick() {
    const menuItems = document.querySelectorAll('.menu-item');
    let message = "Halo, saya ingin memesan makanan sesuai rekomendasi:\n\n";
    
    if (menuItems.length > 0) {
        menuItems.forEach(item => {
            const name = item.querySelector('.font-medium').textContent;
            const calories = item.querySelector('.text-gray-600').textContent;
            message += `- ${name} (${calories})\n`;
        });
    } else {
        // Default message if no recommendations loaded
        message += "- Oatmeal with fruits (300 kcal)\n";
        message += "- Grilled chicken salad (400 kcal)\n";
        message += "- Salmon with vegetables (450 kcal)";
    }

    const whatsappUrl = `https://wa.me/+6281275722872?text=${encodeURIComponent(message)}`;
    window.open(whatsappUrl, '_blank');
}

// Notification System
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 p-4 rounded-md text-white ${
        type === 'success' ? 'bg-green-500' : 'bg-red-500'
    }`;
    notification.style.zIndex = '1000';
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transition = 'opacity 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Helper Functions
function formatNumber(value, unit = '') {
    return `${parseFloat(value).toLocaleString()}${unit}`;
}