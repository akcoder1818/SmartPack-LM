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
        showPane('viewfinder');
        bsModal().show();
    }

    function close() {
        stopStream();
        capturedBlob = null;
        bsModal().hide();
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

        // Close buttons in error / http panes
        document.getElementById('cameraErrorCloseBtn')?.addEventListener('click', close);
        document.getElementById('cameraHttpCloseBtn')?.addEventListener('click', close);

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
   FILE PREVIEW HELPER
   ========================================================= */
function handleFileSelect(file, content, previewBox, previewImg, nameLabel) {
    if (!file) return;

    const maxSize = 16 * 1024 * 1024;
    if (file.size > maxSize) {
        alert('File is too large. Maximum allowed size is 16MB.');
        return;
    }
    if (!file.type.match('image.*')) {
        alert('Please select an image file (PNG, JPG, JPEG, WEBP, BMP).');
        return;
    }

    nameLabel.innerText = file.name + ' (' + (file.size / (1024 * 1024)).toFixed(2) + ' MB)';

    const reader = new FileReader();
    reader.onload = function (e) {
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
            alert('Please select at least the Front Label image to proceed.');
            e.preventDefault();
            return;
        }

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Analyzing Commodity Label...';
        progressIndicator.classList.remove('d-none');

        const steps = [
            { width: '25%', text: '1/4 Preprocessing label images with OpenCV (CLAHE & Binarization)...' },
            { width: '55%', text: '2/4 Extracting statutory declarations via OCR Token Engine...' },
            { width: '80%', text: '3/4 Validating against Legal Metrology Rules, 2011 Rule 6(1)...' },
            { width: '95%', text: '4/4 Generating visual bounding box evidence map & audit index...' }
        ];

        let stepIndex = 0;
        const interval = setInterval(function () {
            if (stepIndex < steps.length) {
                progressBar.style.width = steps[stepIndex].width;
                progressStepText.innerText = steps[stepIndex].text;
                stepIndex++;
            } else {
                clearInterval(interval);
            }
        }, 600);
    });
}


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
        cameraBtnId: 'frontCameraBtn', cameraLabel: 'Take Front Photo'
    });

    setupDropzone({
        zoneId: 'backDropzone', inputId: 'backImageInput', galleryInputId: 'backGalleryInput',
        contentId: 'backDropzoneContent', previewBoxId: 'backPreviewBox',
        previewImgId: 'backPreviewImg', nameId: 'backFileName',
        removeBtnId: 'removeBackBtn', retakeBtnId: 'retakeBackBtn',
        cameraBtnId: 'backCameraBtn', cameraLabel: 'Take Back Photo'
    });

    setupFormSubmission();
});
