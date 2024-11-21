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

document.addEventListener("DOMContentLoaded", function() {
    const thumbsUpButton = document.getElementById("thumbs-up");
    const thumbsDownButton = document.getElementById("thumbs-down");
    const feedbackAlert = document.getElementById("feedback-alert");
    const feedbackText = document.getElementById("feedback-text");

    thumbsUpButton.addEventListener("click", function() {
      feedbackAlert.style.display = "block";
      feedbackText.textContent = "You liked the AI's Recommendation!";
      feedbackAlert.classList.remove("alert-danger");
      feedbackAlert.classList.add("alert-success");
      hideAlertAfterTimeout();
    });

    thumbsDownButton.addEventListener("click", function() {
      feedbackAlert.style.display = "block";
      feedbackText.textContent = "You disliked the AI's Recommendation!";
      feedbackAlert.classList.remove("alert-success");
      feedbackAlert.classList.add("alert-danger");
      hideAlertAfterTimeout();
    });

    // Function to hide the alert after 5 seconds
    function hideAlertAfterTimeout() {
      setTimeout(function() {
        feedbackAlert.style.display = "none";
      }, 3000); // 3 seconds
    }
  });