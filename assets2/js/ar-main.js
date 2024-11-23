let isWebcamActive = false;
let mediaStream;


//---------------------------- Toggle Functions ----------------------------//

// Function to toggle the display of labels (probability of each emotion)
function toggleLabels(animate = false) {
    showLabels = !showLabels;
    var showLabelsButton = document.getElementById("toggleLabels");

    if (showLabels) {
        sideContainer.style.display = "Block"
        showLabelsButton.innerHTML = "Hide Labels";
    }
    else {
        sideContainer.style.display = "None";
        showLabelsButton.innerHTML = "Show Labels";
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
// Toggles the webcam on or off
async function toggleWebcam() {
  const webcamContainer = document.getElementById("webcam-container");
  const webcamPlaceholder = document.getElementById("webcam-placeholder");
  const toggleCamButton = document.getElementById("toggleCam");

  if (!isWebcamActive) {
    try {
      // Request access to the webcam
      mediaStream = await navigator.mediaDevices.getUserMedia({ video: true });

      // Display the webcam feed
      const webcamPlayback = document.getElementById("webcamPlayback");
      webcamPlayback.srcObject = mediaStream;

      // Show the webcam container with a fade-in transition
      fadeInElement(webcamContainer);
      webcamPlaceholder.style.display = "none";

      // Update button text and webcam state
      toggleCamButton.textContent = "Disable Webcam";
      isWebcamActive = true;
    } catch (error) {
      // Show error modal if webcam access fails
      displayModal("Could not access the webcam - check your permissions");
      console.error("Webcam access error:", error);
    }
  } else {
    // Stop the webcam and hide the webcam container
    stopMediaStream(mediaStream);
    fadeOutElement(webcamContainer, () => {
      webcamPlaceholder.style.display = "block";
    });

    // Update button text and webcam state
    toggleCamButton.textContent = "Enable Webcam";
    isWebcamActive = false;
  }
}

// Stops all tracks in the provided media stream
function stopMediaStream(stream) {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
  }
}

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
async function toggleModel() {
  const toggleButton = document.getElementById("toggleModel");
  const extraButtons = document.getElementById("extraButtons"); // Get the extra buttons div

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
    toggleButton.textContent = "Stop";  // Change button text to "Stop"
    
    // Show the extra buttons div
    extraButtons.style.display = "block";  // Show the div with the extra buttons
    
    isModelActive = true;
  } else {
    // If the model is active, stop the predictions but keep the webcam feed running
    isPredicting = false;
    toggleButton.textContent = "Start";  // Change button text to "Start"
    
    // Hide the extra buttons div
    extraButtons.style.display = "none";  // Hide the div with the extra buttons
    
    isModelActive = false;
  }
}

// Start the prediction process
async function startPrediction() {
  const video = document.getElementById("webcamPlayback");

  // Keep running the predictions only if isPredicting is true
  setInterval(async () => {
    if (!isPredicting) return;

    // Predict the current frame
    const prediction = await model.predict(video, false);
    console.clear();
    prediction.forEach(pred => {
      console.log(pred.className + ": " + pred.probability.toFixed(2));
    });
  }, 100); // Run prediction every 100ms
}

// Stops all tracks in the provided media stream (not used here, since we only stop predictions)
function stopMediaStream(stream) {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
  }
}

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
