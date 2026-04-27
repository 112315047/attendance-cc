// Theme
function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const newTheme = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
}
const savedTheme = localStorage.getItem('theme');
if (savedTheme) document.documentElement.setAttribute('data-theme', savedTheme);

// Elements
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const overlayCanvas = document.getElementById('overlayCanvas');
const overlayCtx = overlayCanvas.getContext('2d');
const spinner = document.getElementById('spinner');

const namePanel = document.getElementById('last-name');
const confPanel = document.getElementById('last-conf');
const confBar = document.getElementById('conf-bar');
const statusPanel = document.getElementById('last-status');
const logContainer = document.getElementById('logContainer');

let autoScanInterval = null;
let isScanning = false;

// Clock
setInterval(() => {
    document.getElementById('clock').innerText = new Date().toLocaleTimeString();
}, 1000);

async function setupCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } });
        video.srcObject = stream;
        video.onloadedmetadata = () => {
            overlayCanvas.width = video.videoWidth;
            overlayCanvas.height = video.videoHeight;
        };
    } catch (err) {
        showToast('Camera access denied.', 'error');
    }
}
setupCamera();

function showToast(message, type) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerText = message;
    container.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 400); }, 3000);
}

function logActivity(message, type = 'system') {
    const item = document.createElement('div');
    item.className = `log-item ${type}`;
    item.innerText = `[${new Date().toLocaleTimeString()}] ${message}`;
    logContainer.prepend(item);
    if(logContainer.children.length > 20) logContainer.lastChild.remove();
}

function updatePanel(name, conf, status, isSuccess) {
    namePanel.innerText = name;
    confPanel.innerText = conf ? conf + '%' : 'N/A';
    
    let color = '#e74c3c'; // red
    if (conf > 60) color = '#2ecc71'; // green
    else if (conf > 40) color = '#f1c40f'; // yellow
    
    confBar.style.width = conf ? conf + '%' : '0%';
    confBar.style.backgroundColor = color;
    
    statusPanel.innerText = status;
    statusPanel.style.color = isSuccess ? '#2ecc71' : '#e74c3c';
}

function drawBox(box, color, text) {
    overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
    if (!box) return;
    const [x, y, w, h] = box;
    
    overlayCtx.strokeStyle = color;
    overlayCtx.lineWidth = 3;
    overlayCtx.strokeRect(x, y, w, h);
    
    overlayCtx.fillStyle = color;
    overlayCtx.font = "16px Arial";
    overlayCtx.fillText(text, x, y - 5);
}

function toggleAutoScan() {
    const isChecked = document.getElementById('autoScanToggle').checked;
    const btnAtt = document.getElementById('btn-att');
    if (isChecked) {
        btnAtt.disabled = true;
        btnAtt.style.opacity = 0.5;
        logActivity("Auto-Attendance Enabled", "success");
        autoScanInterval = setInterval(() => {
            if (!isScanning) action('attendance', true);
        }, 3000); // scan every 3 seconds
    } else {
        btnAtt.disabled = false;
        btnAtt.style.opacity = 1;
        logActivity("Auto-Attendance Disabled", "system");
        clearInterval(autoScanInterval);
        overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
    }
}

async function action(type, autoMark = false) {
    if (isScanning) return;
    
    const nameInput = document.getElementById('name').value.trim();
    const rollInput = document.getElementById('roll').value.trim();

    if (type === 'register' && (!nameInput || !rollInput)) return showToast('Please enter Name and Roll Number', 'error');

    isScanning = true;
    if(!autoMark) spinner.classList.add('active');
    
    const context = canvas.getContext('2d');
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    const payload = { image: canvas.toDataURL('image/jpeg'), auto_mark: autoMark };
    if (type === 'register') { payload.name = nameInput; payload.roll = rollInput; }

    try {
        const response = await fetch(type === 'register' ? '/register' : '/login', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
        });
        const data = await response.json();
        spinner.classList.remove('active');

        if (data.error) {
            if(!autoMark) showToast(data.error, 'error');
            updatePanel('Unknown', 0, data.error, false);
            drawBox(data.box, '#e74c3c', 'No Match / Error');
            if(data.error === "Multiple faces detected") logActivity("Warning: Multiple faces detected", "error");
        } else if (type === 'register') {
            showToast(`Success! ${nameInput} registered.`, 'success');
            logActivity(`Registered new face: ${nameInput}`, 'success');
            document.getElementById('name').value = ''; document.getElementById('roll').value = '';
            updatePanel(nameInput, 100, 'Registered', true);
            drawBox(data.box, '#2ecc71', nameInput);
        } else {
            if (data.status === 'success') {
                const conf = (data.confidence * 100).toFixed(1);
                if (!autoMark) showToast(`Success: ${data.name} (${conf}%)`, 'success');
                
                if (autoMark) {
                    updatePanel(data.name, conf, 'Attendance Marked', true);
                    logActivity(`Marked Present: ${data.name} (${conf}%)`, 'success');
                    drawBox(data.box, '#2ecc71', `${data.name} - Marked`);
                } else {
                    updatePanel(data.name, conf, 'Verified', true);
                    drawBox(data.box, '#3498db', `${data.name} - Verified`);
                }
            } else if (data.status === 'duplicate') {
                if (!autoMark) showToast(`Already marked today: ${data.name}`, 'error');
                updatePanel(data.name, (data.confidence * 100).toFixed(1), 'Duplicate Entry', false);
                drawBox(data.box, '#f1c40f', `${data.name} - Duplicate`);
                logActivity(`Duplicate scan: ${data.name}`, 'system');
            } else {
                if(!autoMark) showToast('Face not recognized.', 'error');
                updatePanel('Unknown', 0, 'Not Recognized', false);
                drawBox(data.box, '#e74c3c', 'Unknown');
            }
        }
    } catch (err) {
        spinner.classList.remove('active'); 
        if(!autoMark) showToast('Server connection failed.', 'error');
    }
    
    isScanning = false;
    
    // Clear box after 2 seconds if not auto scanning continuously
    if(!autoMark) setTimeout(() => overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height), 2000);
}
