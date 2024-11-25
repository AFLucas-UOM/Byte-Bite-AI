let isWebcamActive = false;
let mediaStream;

//---------------------------- Toggle Functions ----------------------------//

// Function to toggle the display of labels (probability of each emotion)
function toggleLabels() {
  const allRestaurantsSection = document.getElementById("all-restaurants-section");
  const toggleLabelsButton = document.getElementById("toggleLabels");

  // Determine current visibility
  const isHidden = allRestaurantsSection.style.display === "none";

  if (isHidden) {
      fadeInElement(allRestaurantsSection); // Fade in the section
      toggleLabelsButton.innerHTML = "Hide Predictions";
  } else {
      fadeOutElement(allRestaurantsSection); // Fade out the section
      toggleLabelsButton.innerHTML = "Show Predictions";
  }
}

// Toggles the visibility of the webcam display
function toggleDisplay() {
    const webcamContainer = document.getElementById("webcam-container");
    const toggleButton = document.getElementById("toggleDisplay");

    if (!isWebcamActive) {
      displayModal("Please enable the webcam first");
      return;
    }

    const isHidden = webcamContainer.style.display === "none";
    if (isHidden) {
      fadeInElement(webcamContainer);
      toggleButton.textContent = "Hide Display";
    } else {
      fadeOutElement(webcamContainer);
      toggleButton.textContent = "Show Display";
    }
}

// Update the toggleWebcam function
async function toggleWebcam() {
  const webcamContainer = document.getElementById("webcam-container");
  const webcamPlaceholder = document.getElementById("webcam-placeholder");
  const toggleCamButton = document.getElementById("toggleCam");
  const restaurantInfoSection = document.getElementById("restaurant-info-section"); // Get the restaurant-info-section

  if (!isWebcamActive) {
    try {
      // Existing logic for enabling the webcam
      mediaStream = await navigator.mediaDevices.getUserMedia({ video: true });
      const webcamPlayback = document.getElementById("webcamPlayback");
      webcamPlayback.srcObject = mediaStream;
      fadeInElement(webcamContainer);
      webcamPlaceholder.style.display = "none";
      toggleCamButton.textContent = "Disable Webcam";
      isWebcamActive = true;
    } catch (error) {
      displayModal("Could not access the webcam - check your permissions");
      console.error("Webcam access error:", error);
    }
  } else {
    // Existing logic for disabling the webcam
    stopMediaStream(mediaStream);
    fadeOutElement(webcamContainer, () => {
      webcamPlaceholder.style.display = "block";
    });
    toggleCamButton.textContent = "Enable Webcam";
    isWebcamActive = false;

    // Fade out the restaurant-info-section
    fadeOutElement(restaurantInfoSection);
  }
}

// Toggles the visibility of the information section
function toggleInfo() {
  const infoArea = document.getElementById("info-area");
  const infoButton = document.getElementById("info-button");

  const isHidden = infoArea.style.display === "none";
  infoArea.style.display = isHidden ? "block" : "none";
  infoButton.textContent = isHidden
    ? "Hide Additional Info"
    : "Click here to find out more about this page.";
}

// Stops all tracks in the provided media stream
function stopMediaStream(stream) {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
  }
}

//---------------------------- Aesthetic Functions ----------------------------//

// Displays a modal with the provided message
function displayModal(message) {
  const modal = document.getElementById("modalPopup");
  const modalMessage = document.getElementById("modal-message");
  modalMessage.textContent = message;
  modal.style.display = "block";
}

// Closes the modal
function closeModal() {
  const modal = document.getElementById("modalPopup");
  modal.style.display = "none";
}


// Utility to fade in an element
function fadeInElement(element) {
  element.style.opacity = "0";
  element.style.display = "block";
  setTimeout(() => {
    element.style.transition = "opacity 0.5s ease-in-out";
    element.style.opacity = "1";
  }, 10); // Trigger transition
}

// Utility to fade out an element
function fadeOutElement(element, callback = () => {}) {
  element.style.transition = "opacity 0.5s ease-in-out";
  element.style.opacity = "0";
  setTimeout(() => {
    element.style.display = "none";
    callback();
  }, 500); // Matches the fade-out duration
}

//---------------------------- Prediction Functions ----------------------------//

let isModelActive = false;
let isPredicting = false;  // Flag to control prediction
let model, maxPredictions;

// Teachable Machine Model URL
const URL = "https://teachablemachine.withgoogle.com/models/M6fwGM3tz/";

// Initialize webcam, model, and start prediction
async function setupWebcamAndModel() {
  const video = document.getElementById("webcamPlayback");

  // Request webcam access
  const mediaStream = await navigator.mediaDevices.getUserMedia({ video: true });
  video.srcObject = mediaStream;

  // Set webcam state to active
  isWebcamActive = true;

  // Load the Teachable Machine model
  const modelURL = URL + "model.json";
  const metadataURL = URL + "metadata.json";

  model = await tmImage.load(modelURL, metadataURL);
  maxPredictions = model.getTotalClasses();

  // Start prediction when model is ready
  startPrediction();
}

// Function to start/stop prediction when the "Start" or "Stop" button is clicked
let predictionsHistory = {}; // Store prediction history

// Function to start/stop prediction and calculate the average likelihood
async function toggleModel() {
  const toggleButton = document.getElementById("toggleModel");
  const extraButtons = document.getElementById("extraButtons"); // Get the extra buttons div
  const allRestaurantsSection = document.getElementById("all-restaurants-section"); // Get the all-restaurants-section
  const restaurantInfoSection = document.getElementById("restaurant-info-section"); // Get the restaurant info section

  if (!isModelActive) {
    // If the webcam is not active, display an error message
    if (!isWebcamActive) {
      displayModal("Enable camera to start model prediction");
      return;
    }

    // If the model is not active, initialize the webcam and model
    await setupWebcamAndModel();
    
    // Start predictions
    isPredicting = true;
    toggleButton.textContent = "Stop"; // Change button text to "Stop"
    
    // Show the extra buttons div
    extraButtons.style.display = "block"; // Show the div with the extra buttons
    
    // Show the all-restaurants-section
    allRestaurantsSection.style.display = "block"; // Make the section visible
    
    // Initialize predictionsHistory for storing prediction percentages
    predictionsHistory = {
      "Amami": [],
      "Boost": [],
      "BurgerKing": [],
      "CafeCuba": [],
      "Joli": [],
      "Ottoman": [],
      "PizzaHut": [],
      "Starbucks": []
    };

    // Hide restaurant info section by default
    restaurantInfoSection.style.display = "none";

    isModelActive = true;
  } else {
    // If the model is active, stop the predictions but keep the webcam feed running
    isPredicting = false;
    toggleButton.textContent = "Start"; // Change button text to "Start"
    
    // Hide the extra buttons div
    extraButtons.style.display = "none"; // Hide the div with the extra buttons
    
    // Hide the all-restaurants-section
    allRestaurantsSection.style.display = "none"; // Hide the section
    
    // Calculate the average likelihood for each restaurant
    const avgLikelihoods = calculateAverageLikelihood(predictionsHistory);

    // Find the restaurant with the highest average likelihood
    const highestPrediction = findHighestPrediction(avgLikelihoods);

    // Update the restaurant-info-section with the highest prediction
    updateRestaurantInfo(highestPrediction);

    // Show the restaurant info section
    restaurantInfoSection.style.display = "block";

    isModelActive = false;
  }
}

// Function to accumulate predictions for each restaurant
async function startPrediction() {
  const video = document.getElementById("webcamPlayback");

  // Map predicted classes to restaurant card IDs
  const restaurantMap = {
    "Amami": "amami-likelihood",
    "Boost": "boost-likelihood",
    "BurgerKing": "burgerking-likelihood",
    "CafeCuba": "cafecuba-likelihood",
    "Joli": "joli-likelihood",
    "Ottoman": "ottoman-likelihood",
    "PizzaHut": "pizzahut-likelihood",
    "Starbucks": "starbucks-likelihood"
  };

  // Keep running the predictions only if isPredicting is true
  setInterval(async () => {
    if (!isPredicting) return;

    // Predict the current frame
    const predictions = await model.predict(video, false);

    // Accumulate prediction percentages for each restaurant
    predictions.forEach(pred => {
      const restaurant = pred.className;
      const percentage = pred.probability * 100;

      // Accumulate percentages in the predictionsHistory object
      if (predictionsHistory[restaurant]) {
        predictionsHistory[restaurant].push(percentage);
      }

      // Update each restaurant's card with the prediction probability
      const element = document.getElementById(restaurantMap[restaurant]);
      element.innerText = `${percentage.toFixed(2)}%`;
    });
  }, 1000); // Run every second
}

// Function to calculate the average likelihood for each restaurant
function calculateAverageLikelihood(predictionsHistory) {
  const avgLikelihoods = {};
  for (const restaurant in predictionsHistory) {
    const predictions = predictionsHistory[restaurant];
    if (predictions.length > 0) {
      const sum = predictions.reduce((acc, val) => acc + val, 0);
      avgLikelihoods[restaurant] = sum / predictions.length;
    }
  }
  return avgLikelihoods;
}

// Function to find the restaurant with the highest likelihood
function findHighestPrediction(avgLikelihoods) {
  let highestPrediction = null;
  let highestPercentage = 0;

  for (const restaurant in avgLikelihoods) {
    const percentage = avgLikelihoods[restaurant];
    if (percentage > highestPercentage) {
      highestPercentage = percentage;
      highestPrediction = restaurant;
    }
  }

  return highestPrediction;
}

// Function to update the restaurant info section with the highest prediction
function updateRestaurantInfo(highestPrediction) {
  const logoImg = document.getElementById("restaurant-logo");
  const likelihoodSpan = document.getElementById("likelihood-percentage");
  const nameH3 = document.getElementById("restaurant-name");
  const healthScoreSpan = document.getElementById("stars");
  const kjValueSpan = document.getElementById("kj-value");

  // Get the average likelihood of the highest predicted restaurant
  const avgLikelihood = calculateAverageLikelihood(predictionsHistory)[highestPrediction];

  // Add the restaurant info (name, logo, average likelihood) to the restaurant-info-section
  logoImg.src = `assets/img/Outlets/${highestPrediction.toLowerCase()}.png`; // Adjust the path as needed
  logoImg.alt = `${highestPrediction} logo`;

  likelihoodSpan.textContent = `${avgLikelihood.toFixed(2)}%`;
  
  nameH3.textContent = highestPrediction;
  
  // Assume that health score and average kilojoules are pre-defined or fetched dynamically
  healthScoreSpan.textContent = getHealthScore(highestPrediction); // Replace with your actual function to fetch health score
  kjValueSpan.textContent = getAverageKilojoules(highestPrediction); // Replace with your actual function to fetch average kilojoules
}

// Dummy function to return health score based on restaurant name
function getHealthScore(restaurant) {
  const healthScores = {
    "Amami": "★★★★☆",
    "Boost": "★★★★☆",
    "BurgerKing": "★☆☆☆☆",
    "CafeCuba": "★★★★☆",
    "Joli": "★★★★☆",
    "Ottoman": "★★★★☆",
    "PizzaHut": "★★☆☆☆",
    "Starbucks": "★★★☆☆"
  };
  return healthScores[restaurant] || "☆☆☆☆☆";
}

// Dummy function to return average kilojoules based on restaurant name
function getAverageKilojoules(restaurant) {
  const averageKJs = {
    "Amami": 2200,
    "Boost": 1800,
    "BurgerKing": 3500,
    "CafeCuba": 2100,
    "Joli": 2500,
    "Ottoman": 2300,
    "PizzaHut": 2900,
    "Starbucks": 2000
  };
  return averageKJs[restaurant] || "XXXX";
}

// Function to temporarily reset the UI and clear averages
function toggleReset() {
  // Clear averages and set temporary placeholders
  const restaurantMap = {
    "Amami": "amami-likelihood",
    "Boost": "boost-likelihood",
    "BurgerKing": "burgerking-likelihood",
    "CafeCuba": "cafecuba-likelihood",
    "Joli": "joli-likelihood",
    "Ottoman": "ottoman-likelihood",
    "PizzaHut": "pizzahut-likelihood",
    "Starbucks": "starbucks-likelihood"
  };

  // Save the current state to revert back later
  const previousState = {};
  for (const restaurant in restaurantMap) {
    const element = document.getElementById(restaurantMap[restaurant]);
    previousState[restaurant] = element.innerText;
    element.innerText = "XX%"; // Temporary reset
  }

  // Clear averages from the predictions history
  predictionsHistory = {
    "Amami": [],
    "Boost": [],
    "BurgerKing": [],
    "CafeCuba": [],
    "Joli": [],
    "Ottoman": [],
    "PizzaHut": [],
    "Starbucks": []
  };

  // Restore the previous state after 0.5 seconds
  setTimeout(() => {
    for (const restaurant in restaurantMap) {
      const element = document.getElementById(restaurantMap[restaurant]);
      element.innerText = previousState[restaurant]; // Restore original values
    }
  }, 500); // Delay of 0.5 seconds
}
