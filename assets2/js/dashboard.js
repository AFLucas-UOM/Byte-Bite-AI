document.addEventListener("DOMContentLoaded", () => {
    const favicon = document.getElementById("favicon");
    const appleIcon = document.getElementById("apple-touch-icon");
    const isNight = new Date().getHours() >= 18 || new Date().getHours() < 5;

    const iconSrc = isNight ? favicon.dataset.darkIcon : favicon.dataset.lightIcon;
    favicon.href = iconSrc;
    appleIcon.href = iconSrc;
});

function signOut() {
    // Step 1: Clear localStorage
    localStorage.removeItem('BBAIcurrentuser');

    // Step 2: Clear cookies by sending a POST request to '/clear-cookies'
    fetch('/clear-cookies', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        if (response.ok) {
            console.log('Cookies cleared');
        }
    })
    .catch(error => console.error('Error clearing cookies:', error));

    // Step 3: Redirect to homepage after clearing everything
    window.location.href = "/";
}