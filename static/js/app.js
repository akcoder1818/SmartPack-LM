/**
 * SmartPack-LM: Client-Side Interactive Logic
 * Handles image previews, drag-and-drop, gallery upload, in-browser camera capture,
 * form validation, and analysis progress simulation.
 */

/* =========================================================
   CAMERA MODULE — getUserMedia-based in-browser camera
   ========================================================= */
const CameraUI = (function () {
    let stream = null;          // active MediaStream
    let targetInputId = null;   // 'frontImageInput' or 'backImageInput'
    let capturedBlob = null;    // Blob from canvas snapshot

    const modal       = () => document.getElementById('cameraModal');
    const bsModal     = () => bootstrap.Modal.getOrCreateInstance(modal());
    const video       = () => document.getElementById('cameraVideo');
    const canvas      = () => document.getElementById('cameraCanvas');
    const viewfinder  = () => document.getElementById('cameraViewfinder');
    const reviewPane  = () => document.getElementById('cameraCaptureReview');
    const errPane     = () => document.getElementById('cameraPermissionError');
    const httpPane    = () => document.getElementById('cameraHttpWarning');
    const capturedImg = () => document.getElementById('capturedPreviewImg');
    const titleEl     = () => document.getElementById('cameraModalTitle');

    function stopStream() {
        if (stream) {
            stream.getTracks().forEach(t => t.stop());
            stream = null;
        }
        const v = video();
        if (v) { v.srcObject = null; }
    }

    function showPane(which) {
        // which: 'viewfinder' | 'review' | 'error' | 'http'
        viewfinder().classList.toggle('d-none',  which !== 'viewfinder');
        reviewPane().classList.toggle('d-none',  which !== 'review');
        errPane().classList.toggle('d-none',     which !== 'error');
        httpPane().classList.toggle('d-none',    which !== 'http');
    }

    async function startCamera() {
        capturedBlob = null;
        showPane('viewfinder');

        // Check secure context — getUserMedia is blocked on plain HTTP (non-localhost)
        if (!window.isSecureContext) {
            stopStream();
            showPane('http');
            return;
        }

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            stopStream();
            showPane('http'); // API not available (same root cause)
            return;
        }

        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } },
                audio: false
            });
            video().srcObject = stream;
        } catch (err) {
            stopStream();
            // NotAllowedError = user denied; NotFoundError = no camera
            showPane('error');
            console.warn('Camera error:', err.name, err.message);
        }
    }

    function captureFrame() {
        const v = video();
        const c = canvas();
        if (!v || !c || !stream) return;

        c.width  = v.videoWidth  || 1280;
        c.height = v.videoHeight || 720;
        const ctx = c.getContext('2d');
        ctx.drawImage(v, 0, 0, c.width, c.height);

        c.toBlob(function (blob) {
            capturedBlob = blob;
            const url = URL.createObjectURL(blob);
            capturedImg().src = url;
            stopStream();          // stop camera immediately after capture
            showPane('review');
        }, 'image/jpeg', 0.92);
    }

    function usePhoto() {
        if (!capturedBlob || !targetInputId) return;
        const input = document.getElementById(targetInputId);
        if (!input) return;

        const file = new File([capturedBlob], 'camera_capture.jpg', { type: 'image/jpeg' });
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;

        // Trigger change event so the dropzone preview updates
        input.dispatchEvent(new Event('change', { bubbles: true }));
        bsModal().hide();
    }

    function open(inputId, label) {
        targetInputId = inputId;
        capturedBlob  = null;
        if (titleEl()) titleEl().textContent = label || 'Take Photo';
        // If not a secure context, cannot use getUserMedia. Fall back to file input with capture attribute.
        if (!window.isSecureContext) {
            const fallbackInput = document.getElementById(inputId);
            if (fallbackInput) {
                fallbackInput.click();
            }
            return;
        }
        showPane('viewfinder');
        bsModal().show();
    }

    function close() {
        stopStream();
        capturedBlob = null;
        bsModal().hide();
    }

    function useGalleryFallback() {
        const inputId = targetInputId;
        close();
        if (inputId) {
            const galleryInput = document.getElementById(inputId === 'frontImageInput' ? 'frontGalleryInput' : 'backGalleryInput');
            if (galleryInput) {
                galleryInput.click();
            } else {
                const fileInput = document.getElementById(inputId);
                if (fileInput) fileInput.click();
            }
        }
    }

    function init() {
        // Close button (×)
        document.getElementById('cameraCloseBtn')?.addEventListener('click', close);

        // Cancel button (in viewfinder)
        document.getElementById('cameraCancelBtn')?.addEventListener('click', close);

        // Cancel button (after capture review)
        document.getElementById('cancelAfterCaptureBtn')?.addEventListener('click', close);

        // Capture Photo button
        document.getElementById('captureBtn')?.addEventListener('click', captureFrame);

        // Retake button (in review pane)
        document.getElementById('retakeBtn')?.addEventListener('click', startCamera);

        // Use Photo button
        document.getElementById('usePhotoBtn')?.addEventListener('click', usePhoto);

        // Fallback buttons in error / http panes -> seamlessly trigger file upload
        document.getElementById('cameraErrorCloseBtn')?.addEventListener('click', useGalleryFallback);
        document.getElementById('cameraHttpCloseBtn')?.addEventListener('click', useGalleryFallback);

        // When the Bootstrap modal finishes hiding, stop the stream
        modal()?.addEventListener('hidden.bs.modal', stopStream);

        // When the Bootstrap modal fully opens, start the camera
        modal()?.addEventListener('shown.bs.modal', startCamera);
    }

    return { init, open };
})();


/* =========================================================
   DROPZONE MODULE — drag-and-drop + gallery + camera + preview
   ========================================================= */
function setupDropzone(cfg) {
    const {
        zoneId, inputId, galleryInputId, contentId,
        previewBoxId, previewImgId, nameId,
        removeBtnId, retakeBtnId, cameraBtnId,
        cameraLabel
    } = cfg;

    const zone       = document.getElementById(zoneId);
    const input      = document.getElementById(inputId);           // named form input
    const galleryIn  = document.getElementById(galleryInputId);    // labelled gallery picker
    const content    = document.getElementById(contentId);
    const previewBox = document.getElementById(previewBoxId);
    const previewImg = document.getElementById(previewImgId);
    const nameLabel  = document.getElementById(nameId);
    const removeBtn  = document.getElementById(removeBtnId);
    const retakeBtn  = document.getElementById(retakeBtnId);
    const cameraBtn  = document.getElementById(cameraBtnId);

    if (!zone || !input) return;

    /* ---- helpers ---- */
    function resetPreview() {
        input.value = '';
        if (galleryIn) galleryIn.value = '';
        previewBox.classList.add('d-none');
        content.classList.remove('d-none');
        previewImg.src = '';
        nameLabel.innerText = '';
    }

    /* ---- drag & drop ---- */
    ['dragenter', 'dragover'].forEach(ev => {
        zone.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); zone.classList.add('dragover'); });
    });
    ['dragleave', 'drop'].forEach(ev => {
        zone.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); zone.classList.remove('dragover'); });
    });
    zone.addEventListener('drop', e => {
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const dt = new DataTransfer();
            dt.items.add(e.dataTransfer.files[0]);
            input.files = dt.files;
            handleFileSelect(e.dataTransfer.files[0], content, previewBox, previewImg, nameLabel);
        }
    });

    /* ---- named form input change (fired by usePhoto via dispatchEvent, or drag-drop above) ---- */
    input.addEventListener('change', function () {
        if (this.files && this.files.length > 0) {
            handleFileSelect(this.files[0], content, previewBox, previewImg, nameLabel);
        }
    });

    /* ---- gallery / Browse Files picker ---- */
    if (galleryIn) {
        galleryIn.addEventListener('change', function () {
            if (this.files && this.files.length > 0) {
                const dt = new DataTransfer();
                dt.items.add(this.files[0]);
                input.files = dt.files;
                handleFileSelect(this.files[0], content, previewBox, previewImg, nameLabel);
            }
        });
    }

    /* ---- Camera button → open getUserMedia modal ---- */
    if (cameraBtn) {
        cameraBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            CameraUI.open(inputId, cameraLabel);
        });
    }

    /* ---- Replace button ---- */
    const replaceBtn = cfg.replaceBtnId ? document.getElementById(cfg.replaceBtnId) : null;
    if (replaceBtn) {
        replaceBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (galleryIn) galleryIn.click();
            else input.click();
        });
    }

    /* ---- Remove button ---- */
    if (removeBtn) {
        removeBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            resetPreview();
        });
    }

    /* ---- Retake button — reopen camera modal ---- */
    if (retakeBtn) {
        retakeBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            resetPreview();
            CameraUI.open(inputId, cameraLabel);
        });
    }
}


/* =========================================================
   VALIDATION & FILE PREVIEW HELPER
   ========================================================= */
function showValidationMessage(msg, type = 'danger') {
    const alertEl = document.getElementById('scanValidationAlert');
    if (alertEl) {
        alertEl.className = `alert alert-${type} py-2.5 px-3 rounded-3 small mb-3 shadow-xs d-flex align-items-center gap-2`;
        alertEl.innerHTML = `<i class="bi bi-exclamation-triangle-fill fs-6 text-danger"></i> <span>${msg}</span>`;
        alertEl.classList.remove('d-none');
        alertEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
        alert(msg);
    }
}

function handleFileSelect(file, content, previewBox, previewImg, nameLabel) {
    if (!file) return;

    const maxSize = 16 * 1024 * 1024;
    if (file.size > maxSize) {
        showValidationMessage('File is too large. Maximum allowed size is 16MB.', 'danger');
        return;
    }
    if (!file.type.match('image.*')) {
        showValidationMessage('Please select a valid image file (PNG, JPG, JPEG, WEBP, BMP).', 'warning');
        return;
    }

    // Dismiss any active validation alert
    const alertEl = document.getElementById('scanValidationAlert');
    if (alertEl) alertEl.classList.add('d-none');

    const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
    const reader = new FileReader();
    reader.onload = function (e) {
        previewImg.onload = function () {
            const w = this.naturalWidth;
            const h = this.naturalHeight;
            if (nameLabel) {
                nameLabel.innerHTML = `
                    <div class="d-flex flex-column text-start">
                        <span class="small fw-bold text-dark text-truncate" style="max-width: 220px;" title="${file.name}">${file.name}</span>
                        <div class="d-flex align-items-center gap-1.5 mt-0.5">
                            <span class="badge bg-success-subtle text-success py-0.5 px-1.5 font-monospace" style="font-size: 0.65rem;"><i class="bi bi-check2"></i> Ready</span>
                            <span class="text-muted small font-monospace" style="font-size: 0.7rem;">${sizeMb} MB &bull; ${w}&times;${h}px</span>
                        </div>
                    </div>
                `;
            }
        };
        previewImg.src = e.target.result;
        content.classList.add('d-none');
        previewBox.classList.remove('d-none');
    };
    reader.readAsDataURL(file);
}


/* =========================================================
   FORM SUBMISSION — progress bar simulation
   ========================================================= */
function setupFormSubmission() {
    const scanForm        = document.getElementById('scanForm');
    const submitBtn       = document.getElementById('submitBtn');
    const progressIndicator = document.getElementById('progressIndicator');
    const progressBar     = document.getElementById('progressBar');
    const progressStepText = document.getElementById('progressStepText');

    if (!scanForm) return;

    scanForm.addEventListener('submit', function (e) {
        const frontInput = document.getElementById('frontImageInput');
        if (!frontInput || !frontInput.files || frontInput.files.length === 0) {
            e.preventDefault();
            showValidationMessage('Please capture or select at least the Front Label (Primary Product View) before starting inspection.', 'danger');
            const frontDropzone = document.getElementById('frontDropzone');
            if (frontDropzone) {
                frontDropzone.scrollIntoView({ behavior: 'smooth', block: 'center' });
                frontDropzone.classList.add('border-danger');
                setTimeout(() => frontDropzone.classList.remove('border-danger'), 3000);
            }
            return;
        }

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Inspecting Packaging Label...';
        progressIndicator.classList.remove('d-none');

        const steps = [
            { width: '25%', text: '1/4 Preprocessing label images with OpenCV (CLAHE & Binarization)...' },
            { width: '55%', text: '2/4 Extracting statutory declarations via Multi-Pass OCR Token Engine...' },
            { width: '80%', text: '3/4 Validating against Legal Metrology Rules, 2011 Rule 6(1)...' },
            { width: '95%', text: '4/4 Generating visual bounding box evidence map & audit index...' }
        ];

        let stepIndex = 0;
        const interval = setInterval(function () {
            if (stepIndex < steps.length) {
                if (progressBar) progressBar.style.width = steps[stepIndex].width;
                if (progressStepText) progressStepText.innerText = steps[stepIndex].text;
                stepIndex++;
            } else {
                clearInterval(interval);
            }
        }, 700);
    });
}


/* =========================================================
   LOCATION MODULE — Geolocation, Leaflet Map & Reverse Geocoding
   ========================================================= */
const LocationModule = (function () {
    let mapInstance = null;
    let mapMarker = null;
    let accuracyCircle = null;
    let currentLocationData = null;

    const detectBtn     = () => document.getElementById('detectLocationBtn');
    const detectBtnText = () => document.getElementById('detectLocationBtnText');
    const refreshBtn    = () => document.getElementById('refreshLocationBtn');
    const statusAlert   = () => document.getElementById('locationStatusAlert');
    const statusText    = () => document.getElementById('locationStatusText');
    const container     = () => document.getElementById('locationDetailsContainer');
    const mapEl         = () => document.getElementById('inspectionMap');
    const hiddenInput   = () => document.getElementById('locationDataInput');

    const coordsDisplay   = () => document.getElementById('locCoordsDisplay');
    const accuracyDisplay = () => document.getElementById('locAccuracyDisplay');
    const regionDisplay   = () => document.getElementById('locRegionDisplay');
    const postcodeDisplay = () => document.getElementById('locPostcodeDisplay');
    const addressDisplay  = () => document.getElementById('locAddressDisplay');

    function showStatus(msg, type = 'info', autoDismiss = false) {
        const el = statusAlert();
        const txt = statusText();
        if (!el || !txt) return;

        el.className = `alert alert-${type} py-2 px-3 small mb-2`;
        txt.innerHTML = msg;
        el.classList.remove('d-none');

        if (autoDismiss) {
            setTimeout(() => {
                el.classList.add('d-none');
            }, 5000);
        }
    }

    function hideStatus() {
        const el = statusAlert();
        if (el) el.classList.add('d-none');
    }

    function initMap(lat, lon, accuracy) {
        if (!mapEl() || typeof L === 'undefined') return;

        container().classList.remove('d-none');

        if (!mapInstance) {
            mapInstance = L.map('inspectionMap', {
                center: [lat, lon],
                zoom: 15,
                scrollWheelZoom: false
            });

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>'
            }).addTo(mapInstance);

            mapMarker = L.marker([lat, lon]).addTo(mapInstance);

            if (accuracy && accuracy > 0) {
                accuracyCircle = L.circle([lat, lon], {
                    radius: accuracy,
                    color: '#2563EB',
                    fillColor: '#3B82F6',
                    fillOpacity: 0.15,
                    weight: 1
                }).addTo(mapInstance);
            }
        } else {
            mapInstance.setView([lat, lon], 15);
            if (mapMarker) mapMarker.setLatLng([lat, lon]);
            if (accuracyCircle) {
                accuracyCircle.setLatLng([lat, lon]);
                if (accuracy && accuracy > 0) accuracyCircle.setRadius(accuracy);
            } else if (accuracy && accuracy > 0) {
                accuracyCircle = L.circle([lat, lon], {
                    radius: accuracy,
                    color: '#2563EB',
                    fillColor: '#3B82F6',
                    fillOpacity: 0.15,
                    weight: 1
                }).addTo(mapInstance);
            }
        }

        setTimeout(() => {
            if (mapInstance) mapInstance.invalidateSize();
        }, 200);
    }

    async function reverseGeocode(lat, lon) {
        const url = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}&addressdetails=1`;
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 6000);

            const res = await fetch(url, {
                headers: {
                    'Accept': 'application/json',
                    'User-Agent': 'SmartPack-LM-InspectionApp/1.0'
                },
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            return data;
        } catch (err) {
            console.warn('[SmartPack-LM] Reverse geocoding notice:', err.message);
            return null;
        }
    }

    function setDetectingState(isDetecting) {
        const btn = detectBtn();
        const txt = detectBtnText();
        const refBtn = refreshBtn();

        if (btn) btn.disabled = isDetecting;
        if (refBtn) refBtn.disabled = isDetecting;

        if (isDetecting) {
            if (txt) txt.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Locating...';
        } else {
            if (txt) txt.innerHTML = '<i class="bi bi-geo-alt-fill text-success me-1"></i> Location Acquired';
            if (btn) btn.classList.replace('btn-outline-primary', 'btn-outline-success');
            if (refBtn) refBtn.classList.remove('d-none');
        }
    }

    function getCurrentPositionPromise(options) {
        return new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, options);
        });
    }

    async function detectLocation() {
        if (!navigator.geolocation) {
            showStatus('<i class="bi bi-exclamation-octagon-fill text-danger me-1"></i> Geolocation is not supported by your browser.', 'warning');
            return;
        }

        setDetectingState(true);
        showStatus('<i class="bi bi-satellite-dish me-1"></i> Requesting GPS coordinates from device...', 'info');

        let position = null;
        try {
            // First try high accuracy GPS
            position = await getCurrentPositionPromise({
                enableHighAccuracy: true,
                timeout: 8000,
                maximumAge: 30000
            });
        } catch (gpsErr) {
            console.warn('[SmartPack-LM] High-accuracy geolocation failed, falling back to standard:', gpsErr.message);
            if (gpsErr.code === 1) { // PERMISSION_DENIED
                setDetectingState(false);
                if (detectBtnText()) detectBtnText().innerHTML = '📍 Detect My Location';
                if (detectBtn()) detectBtn().classList.replace('btn-outline-success', 'btn-outline-primary');
                showStatus('<i class="bi bi-shield-x text-warning me-1"></i> Location permission was denied. You can proceed without location or allow permission in browser settings.', 'warning');
                return;
            }
            try {
                // Fallback attempt with standard network location
                position = await getCurrentPositionPromise({
                    enableHighAccuracy: false,
                    timeout: 8000,
                    maximumAge: 60000
                });
            } catch (fallbackErr) {
                setDetectingState(false);
                if (detectBtnText()) detectBtnText().innerHTML = '📍 Detect My Location';
                if (detectBtn()) detectBtn().classList.replace('btn-outline-success', 'btn-outline-primary');
                let userMsg = 'Unable to determine location. You can proceed with the inspection.';
                if (fallbackErr.code === 1) {
                    userMsg = 'Location permission was denied. You can proceed with the inspection.';
                } else if (fallbackErr.code === 2) {
                    userMsg = 'Location position is currently unavailable.';
                } else if (fallbackErr.code === 3) {
                    userMsg = 'Location request timed out. Please check network/GPS and try again.';
                }
                showStatus(`<i class="bi bi-exclamation-triangle-fill text-warning me-1"></i> ${userMsg}`, 'warning');
                return;
            }
        }

        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
        const accuracy = position.coords.accuracy || 0;
        const timestamp = new Date(position.timestamp || Date.now()).toLocaleString();

        // Update UI coordinates immediately
        if (coordsDisplay()) coordsDisplay().innerText = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
        if (accuracyDisplay()) accuracyDisplay().innerText = `Accuracy: ±${Math.round(accuracy)} meters (${timestamp})`;

        // Show map immediately
        initMap(lat, lon, accuracy);

        showStatus('<i class="bi bi-search me-1"></i> Resolving postal address via OpenStreetMap Nominatim...', 'info');

        // Reverse geocoding
        const geoResult = await reverseGeocode(lat, lon);
        let address = '';
        let locality = '';
        let city = '';
        let district = '';
        let state = '';
        let pincode = '';
        let country = '';

        if (geoResult && geoResult.address) {
            const a = geoResult.address;
            address = geoResult.display_name || '';
            locality = a.suburb || a.neighbourhood || a.village || a.residential || a.road || '';
            city = a.city || a.town || a.municipality || a.county || '';
            district = a.state_district || a.district || a.county || '';
            state = a.state || '';
            pincode = a.postcode || '';
            country = a.country || '';

            if (regionDisplay()) {
                const parts = [locality, city, state].filter(Boolean);
                regionDisplay().innerText = parts.join(', ') || 'Resolved Location';
            }
            if (postcodeDisplay()) {
                const parts = [district ? `District: ${district}` : '', pincode ? `PIN: ${pincode}` : '', country].filter(Boolean);
                postcodeDisplay().innerText = parts.join(' • ') || country;
            }
            if (addressDisplay()) addressDisplay().innerText = address || 'Address details resolved.';
        } else {
            address = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
            if (regionDisplay()) regionDisplay().innerText = 'Coordinates recorded';
            if (postcodeDisplay()) postcodeDisplay().innerText = 'Reverse geocoding unavailable';
            if (addressDisplay()) addressDisplay().innerText = `GPS Location: Lat ${lat.toFixed(5)}, Lon ${lon.toFixed(5)} (Address lookup offline)`;
        }

        if (mapMarker) {
            const popupHtml = `<b>Inspection Site</b><br>${locality ? locality + '<br>' : ''}${city ? city + ', ' : ''}${state ? state : ''}<br><small class="text-muted">${lat.toFixed(5)}, ${lon.toFixed(5)}</small>`;
            mapMarker.bindPopup(popupHtml).openPopup();
        }

        // Build structured location object
        currentLocationData = {
            latitude: lat,
            longitude: lon,
            accuracy: accuracy,
            address: address,
            locality: locality,
            city: city,
            district: district,
            state: state,
            pincode: pincode,
            country: country,
            timestamp: timestamp
        };

        // Attach to hidden input
        if (hiddenInput()) {
            hiddenInput().value = JSON.stringify(currentLocationData);
        }

        setDetectingState(false);
        showStatus('<i class="bi bi-check-circle-fill text-success me-1"></i> Inspection location recorded successfully.', 'success', true);
    }

    function init() {
        if (detectBtn()) {
            detectBtn().addEventListener('click', function (e) {
                e.preventDefault();
                detectLocation();
            });
        }
        if (refreshBtn()) {
            refreshBtn().addEventListener('click', function (e) {
                e.preventDefault();
                detectLocation();
            });
        }
    }

    return { init, detectLocation, getLocationData: () => currentLocationData };
})();


/* =========================================================
   HERO MULTI-PRODUCT AI SHOWCASE MODULE
   ========================================================= */
const HeroShowcaseModule = (function () {
    const products = {
        chips: {
            title: 'Crispy Chips',
            subtitle: 'Tangy Tomato Masala',
            category: 'SNACKS',
            weight: '50g',
            mrp: '₹20.00',
            mfg: '08/2026',
            emoji: '🥔',
            theme: 'pack-theme-chips',
            statusText: 'AI Scanning: Classic Potato Chips (50g)',
            lensMrp: '₹20.00 (Incl. of all taxes)',
            lensQty: '50 g • Unit Sale Price: ₹0.40/g',
            lensDate: 'Mfg: 08/2026 | Best Before: 6 Months',
            lensCare: 'Origin: India | Care: 1800-202-9900',
            resultTitle: '100% Statutory Compliance',
            resultSub: 'All 7/7 Legal Metrology Declarations Detected'
        },
        biscuits: {
            title: 'Royal Biscuits',
            subtitle: 'Enriched Glucose & Milk',
            category: 'BAKERY',
            weight: '200g',
            mrp: '₹30.00',
            mfg: '07/2026',
            emoji: '🍪',
            theme: 'pack-theme-biscuits',
            statusText: 'AI Scanning: Royal Glucose Biscuits (200g)',
            lensMrp: '₹30.00 (Incl. of all taxes)',
            lensQty: '200 g • Unit Sale Price: ₹0.15/g',
            lensDate: 'Mfg: 07/2026 | Best Before: 9 Months',
            lensCare: 'Origin: India | Care: 1800-111-2233',
            resultTitle: '100% Statutory Compliance',
            resultSub: 'Weight, MRP & Standard Units Verified'
        },
        oil: {
            title: 'Pure Gold Oil',
            subtitle: 'Refined Sunflower Oil',
            category: 'EDIBLE OIL',
            weight: '1 Litre',
            mrp: '₹145.00',
            mfg: '06/2026',
            emoji: '🌻',
            theme: 'pack-theme-oil',
            statusText: 'AI Scanning: Refined Sunflower Oil (1L)',
            lensMrp: '₹145.00 (Incl. of all taxes)',
            lensQty: '1 L (910g) • Unit Sale Price: ₹145.00/L',
            lensDate: 'Mfg: 06/2026 | Best Before: 12 Months',
            lensCare: 'Origin: India | FSSAI & Metrology Verified',
            resultTitle: '100% Statutory Compliance',
            resultSub: 'Dual Metric (Volume & Mass) Clause Verified'
        },
        spices: {
            title: 'King Masala',
            subtitle: 'Pure Ground Spice Blend',
            category: 'SPICES',
            weight: '100g',
            mrp: '₹65.00',
            mfg: '08/2026',
            emoji: '🌶️',
            theme: 'pack-theme-spices',
            statusText: 'AI Scanning: Kitchen King Garam Masala (100g)',
            lensMrp: '₹65.00 (Incl. of all taxes)',
            lensQty: '100 g • Unit Sale Price: ₹0.65/g',
            lensDate: 'Mfg: 08/2026 | Best Before: 12 Months',
            lensCare: 'Origin: India | Agmark & Metrology OK',
            resultTitle: '100% Statutory Compliance',
            resultSub: 'Declarations on Principal Display Panel OK'
        },
        noodles: {
            title: 'Express Noodles',
            subtitle: '2-Minute Masala Magic',
            category: 'INSTANT FOOD',
            weight: '70g',
            mrp: '₹14.00',
            mfg: '08/2026',
            emoji: '🍜',
            theme: 'pack-theme-noodles',
            statusText: 'AI Scanning: Express Masala Noodles (70g)',
            lensMrp: '₹14.00 (Incl. of all taxes)',
            lensQty: '70 g • Unit Sale Price: ₹0.20/g',
            lensDate: 'Mfg: 08/2026 | Best Before: 9 Months',
            lensCare: 'Origin: India | Consumer Desk: care@brand.in',
            resultTitle: '100% Statutory Compliance',
            resultSub: 'Full Rule 6(1) Declaration Set Verified'
        },
        juice: {
            title: 'Fresh Mango',
            subtitle: '100% Real Fruit Juice',
            category: 'BEVERAGES',
            weight: '1000ml',
            mrp: '₹110.00',
            mfg: '08/2026',
            emoji: '🧃',
            theme: 'pack-theme-juice',
            statusText: 'AI Scanning: Orchard Fresh Mango Juice (1000ml)',
            lensMrp: '₹110.00 (Incl. of all taxes)',
            lensQty: '1000 ml (1 L) • Unit Price: ₹0.11/ml',
            lensDate: 'Mfg: 08/2026 | Best Before: 6 Months',
            lensCare: 'Origin: India | Toll-free: 1800-400-8800',
            resultTitle: '100% Statutory Compliance',
            resultSub: 'Standard Packaging Quantity Standardized'
        },
        pulses: {
            title: 'Organic Toor Dal',
            subtitle: 'Unpolished Desi Grains',
            category: 'PULSES',
            weight: '1 kg',
            mrp: '₹160.00',
            mfg: '08/2026',
            emoji: '🌾',
            theme: 'pack-theme-pulses',
            statusText: 'AI Scanning: Organic Toor Dal Pulses (1kg)',
            lensMrp: '₹160.00 (Incl. of all taxes)',
            lensQty: '1 kg (1000g) • Unit Sale Price: ₹0.16/g',
            lensDate: 'Packed: 08/2026 | Best Before: 12 Months',
            lensCare: 'Origin: India | Packer: Bharat Agro Ltd.',
            resultTitle: '100% Statutory Compliance',
            resultSub: 'Packer Address & Net Mass SI Standard OK'
        }
    };

    let autoTimer = null;
    const keys = Object.keys(products);
    let currentIndex = 0;

    function selectProduct(key, userInitiated = false) {
        const p = products[key];
        if (!p) return;

        // Update tabs
        const tabs = document.querySelectorAll('#heroProductShelf .shelf-product-tab');
        tabs.forEach(tab => {
            tab.classList.toggle('active', tab.getAttribute('data-product') === key);
        });

        // Update elements with smooth subtle fade
        const packEl = document.getElementById('heroProductPack');
        if (packEl) {
            // Remove previous theme class
            Object.values(products).forEach(item => packEl.classList.remove(item.theme));
            packEl.classList.add(p.theme);
        }

        const setTxt = (id, txt) => {
            const el = document.getElementById(id);
            if (el) el.textContent = txt;
        };

        setTxt('heroPackTitle', p.title);
        setTxt('heroPackSubtitle', p.subtitle);
        setTxt('heroPackCategory', p.category);
        setTxt('heroPackWeight', p.weight);
        setTxt('heroPackMrp', p.mrp);
        setTxt('heroPackMfg', p.mfg);
        setTxt('heroPackEmoji', p.emoji);

        setTxt('heroScannerStatusText', p.statusText);
        setTxt('lensMrpValue', p.lensMrp);
        setTxt('lensQtyValue', p.lensQty);
        setTxt('lensDateValue', p.lensDate);
        setTxt('lensCareValue', p.lensCare);
        setTxt('heroResultTitle', p.resultTitle);
        setTxt('heroResultSub', p.resultSub);

        currentIndex = keys.indexOf(key);

        if (userInitiated) {
            // Reset auto-timer if clicked manually
            clearInterval(autoTimer);
            autoTimer = setInterval(cycleNext, 5000);
        }
    }

    function cycleNext() {
        currentIndex = (currentIndex + 1) % keys.length;
        selectProduct(keys[currentIndex], false);
    }

    function init() {
        const shelf = document.getElementById('heroProductShelf');
        if (!shelf) return;

        shelf.addEventListener('click', function (e) {
            const tab = e.target.closest('.shelf-product-tab');
            if (tab) {
                const productKey = tab.getAttribute('data-product');
                selectProduct(productKey, true);
            }
        });

        // Start subtle auto rotation
        autoTimer = setInterval(cycleNext, 5000);
    }

    return { init, selectProduct };
})();


/* =========================================================
   BOOT
   ========================================================= */
document.addEventListener('DOMContentLoaded', function () {
    CameraUI.init();

    setupDropzone({
        zoneId: 'frontDropzone', inputId: 'frontImageInput', galleryInputId: 'frontGalleryInput',
        contentId: 'frontDropzoneContent', previewBoxId: 'frontPreviewBox',
        previewImgId: 'frontPreviewImg', nameId: 'frontFileName',
        removeBtnId: 'removeFrontBtn', retakeBtnId: 'retakeFrontBtn',
        replaceBtnId: 'replaceFrontBtn',
        cameraBtnId: 'frontCameraBtn', cameraLabel: 'Take Front Photo'
    });

    setupDropzone({
        zoneId: 'backDropzone', inputId: 'backImageInput', galleryInputId: 'backGalleryInput',
        contentId: 'backDropzoneContent', previewBoxId: 'backPreviewBox',
        previewImgId: 'backPreviewImg', nameId: 'backFileName',
        removeBtnId: 'removeBackBtn', retakeBtnId: 'retakeBackBtn',
        replaceBtnId: 'replaceBackBtn',
        cameraBtnId: 'backCameraBtn', cameraLabel: 'Take Back Photo'
    });

    setupFormSubmission();
    LocationModule.init();
    HeroShowcaseModule.init();
});


