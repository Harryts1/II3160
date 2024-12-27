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