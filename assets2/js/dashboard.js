/** Favicon Light & Dark Mode */
document.addEventListener("DOMContentLoaded", () => {
    const favicon = document.getElementById("favicon");
    const appleIcon = document.getElementById("apple-touch-icon");
    const isNight = new Date().getHours() >= 18 || new Date().getHours() < 5;

    const iconSrc = isNight ? favicon.dataset.darkIcon : favicon.dataset.lightIcon;
    favicon.href = iconSrc;
    appleIcon.href = iconSrc;
});

/** Signout Function */
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

/** Thumbs-up & Down Basic Alert */
document.addEventListener("DOMContentLoaded", () => {
  const thumbsUpButton = document.getElementById("thumbs-up");
  const thumbsDownButton = document.getElementById("thumbs-down");
  const feedbackAlert = document.getElementById("feedback-alert");
  const feedbackText = document.getElementById("feedback-text");

  let alertTimeout;  // Variable to hold the timeout reference

  const showFeedbackAlert = (message, isSuccess) => {
      feedbackText.textContent = message;
      feedbackAlert.classList.toggle("alert-success", isSuccess);
      feedbackAlert.classList.toggle("alert-danger", !isSuccess);
      feedbackAlert.style.display = "block";
      
      // Clear the previous timeout (if any)
      if (alertTimeout) {
          clearTimeout(alertTimeout);
      }
      // Set the new timeout
      hideAlertAfterTimeout();
  };

  thumbsUpButton.addEventListener("click", () => {
      showFeedbackAlert("You liked the AI's Recommendation!", true);
  });

  thumbsDownButton.addEventListener("click", () => {
      showFeedbackAlert("You disliked the AI's Recommendation!", false);
  });

  // Function to hide the alert after a timeout
  const hideAlertAfterTimeout = () => {
      alertTimeout = setTimeout(() => {
          feedbackAlert.style.display = "none";
      }, 3000); // 3 seconds
  };
  
  /** Current Time */
  const updateTime = () => {
      const now = new Date();
      const daysOfWeek = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
      const day = daysOfWeek[now.getDay()];
      const hours = String(now.getHours()).padStart(2, '0');
      const minutes = String(now.getMinutes()).padStart(2, '0');
      const timeString = `| ${day}, ${hours}:${minutes}`;
      document.getElementById("current-time").innerText = timeString;
  };

  // Update time immediately and then every minute
  updateTime();
  setInterval(updateTime, 60000);
});