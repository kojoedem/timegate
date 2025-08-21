document.addEventListener("DOMContentLoaded", () => {
    // Global variables
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const apiUrl = "/api/";
    let faceLoginInterval = null;
    let cameraStream = null;

    // === UTILITY FUNCTIONS ===

    function showNotification(message, type = 'info') {
        const notificationArea = document.getElementById('notification-area');
        if (!notificationArea) return;
        const alertClass = `alert alert-${type} alert-dismissible fade show`;
        notificationArea.innerHTML = `
            <div class="${alertClass}" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>`;
    }

    function stopCamera() {
        if (cameraStream) {
            cameraStream.getTracks().forEach(track => track.stop());
            cameraStream = null;
        }
    }

    function startCamera() {
        return new Promise((resolve, reject) => {
            if (navigator.mediaDevices.getUserMedia) {
                navigator.mediaDevices.getUserMedia({ video: true })
                    .then(stream => {
                        cameraStream = stream;
                        video.srcObject = stream;
                        video.style.display = 'block';
                        resolve(stream);
                    }).catch(error => {
                        showNotification("Could not access camera. Please grant permission.", "danger");
                        reject(error);
                    });
            } else {
                showNotification("Camera not supported.", "danger");
                reject(new Error("getUserMedia not supported"));
            }
        });
    }

    function captureImage() {
        const context = canvas.getContext('2d');
        context.drawImage(video, 0, 0, 320, 240);
        return canvas.toDataURL('image/png');
    }

    // === API & LOGIN LOGIC ===

    async function attemptFaceLogin() {
        if (!cameraStream) return;
        const imageData = captureImage();
        try {
            const response = await fetch(`${apiUrl}face-login/`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({face_capture: imageData})
            });
            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('authToken', data.token);
                localStorage.setItem('username', data.username);
                clearInterval(faceLoginInterval);
                stopCamera();
                // On successful login, redirect to the profile page.
                window.location.href = '/profile/';
            } else {
                // Optional: Provide feedback on failed login attempt if desired
                console.log("Face login attempt failed. Will retry.");
            }
        } catch (error) {
            console.error("Face login request failed:", error);
        }
    }

    // === INITIALIZATION LOGIC ===

    function initializeLoginPage() {
        // On page load, first check if the user is already authenticated.
        const authToken = localStorage.getItem('authToken');
        if (authToken) {
            // If a token exists, the user is already logged in. Redirect them to their dashboard.
            // This prevents a logged-in user from seeing the login camera again.
            window.location.href = '/profile/';
        } else {
            // If not logged in, start the camera and attempt to log in via facial recognition.
            const greetingEl = document.getElementById('user-greeting');
            if (greetingEl) {
                greetingEl.innerText = 'Please look at the camera to log in...';
            }
            showNotification("Please look at the camera to log in.", "info");
            startCamera().then(() => {
                faceLoginInterval = setInterval(attemptFaceLogin, 2500);
            }).catch(err => {
                console.error("Could not start camera for login.", err);
            });
        }
    }

    // Start the process when the DOM is loaded.
    initializeLoginPage();
});
