// document.addEventListener("DOMContentLoaded", () => {

//     const startCheckBtn = document.getElementById("startCheckBtn");
//     const checker = document.getElementById("checker");

//     const inputCards = document.querySelectorAll(".input-type-card");

//     const textPanel = document.getElementById("textPanel");
//     const filePanel = document.getElementById("filePanel");
//     const urlPanel = document.getElementById("urlPanel");

//     const jobText = document.getElementById("jobText");
//     const jobUrl = document.getElementById("jobUrl");

//     const charCounter = document.getElementById("charCounter");

//     const uploadZone = document.getElementById("uploadZone");
//     const fileInput = document.getElementById("fileInput");

//     const selectedFile = document.getElementById("selectedFile");
//     const fileName = document.getElementById("fileName");
//     const fileSize = document.getElementById("fileSize");

//     const removeFile = document.getElementById("removeFile");

//     const uploadTitle = document.getElementById("uploadTitle");
//     const uploadDescription = document.getElementById("uploadDescription");
//     const uploadFormats = document.getElementById("uploadFormats");

//     const analyzeBtn = document.getElementById("analyzeBtn");

//     const loadingState = document.getElementById("loadingState");
//     const errorBox = document.getElementById("errorBox");
//     const errorMessage = document.getElementById("errorMessage");


//     let currentType = "text";
//     let selectedUpload = null;


//     /* =====================================================
//        START CHECK
//     ===================================================== */

//     startCheckBtn.addEventListener("click", () => {

//         checker.scrollIntoView({
//             behavior: "smooth",
//             block: "start"
//         });

//     });


//     /* =====================================================
//        INPUT TYPE SWITCHING
//     ===================================================== */

//     inputCards.forEach(card => {

//         card.addEventListener("click", () => {

//             inputCards.forEach(item => {
//                 item.classList.remove("active");
//             });

//             card.classList.add("active");

//             currentType = card.dataset.type;

//             textPanel.classList.add("hidden");
//             filePanel.classList.add("hidden");
//             urlPanel.classList.add("hidden");

//             if (currentType === "text") {

//                 textPanel.classList.remove("hidden");

//             }

//             else if (
//                 currentType === "image" ||
//                 currentType === "document"
//             ) {

//                 filePanel.classList.remove("hidden");

//                 configureUploadType();

//             }

//             else if (currentType === "url") {

//                 urlPanel.classList.remove("hidden");

//             }

//             hideError();

//         });

//     });


//     /* =====================================================
//        CHARACTER COUNTER
//     ===================================================== */

//     jobText.addEventListener("input", () => {

//         const length = jobText.value.length;

//         charCounter.textContent =
//             `${length.toLocaleString()} characters`;

//     });


//     /* =====================================================
//        FILE TYPE CONFIG
//     ===================================================== */

//     function configureUploadType() {

//         selectedUpload = null;
//         selectedFile.classList.add("hidden");
//         uploadZone.classList.remove("hidden");

//         fileInput.value = "";

//         if (currentType === "image") {

//             uploadTitle.textContent = "Drop your image here";

//             uploadDescription.textContent =
//                 "or click to browse from your device";

//             uploadFormats.textContent =
//                 "PNG, JPG, JPEG";

//             fileInput.accept =
//                 ".png,.jpg,.jpeg,image/png,image/jpeg";

//         }

//         else {

//             uploadTitle.textContent = "Drop your document here";

//             uploadDescription.textContent =
//                 "or click to browse from your device";

//             uploadFormats.textContent =
//                 "PDF, DOCX, TXT";

//             fileInput.accept =
//                 ".pdf,.docx,.txt,application/pdf," +
//                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain";

//         }

//     }


//     /* =====================================================
//        FILE UPLOAD
//     ===================================================== */

//     uploadZone.addEventListener("click", () => {
//         fileInput.click();
//     });


//     fileInput.addEventListener("change", event => {

//         const file = event.target.files[0];

//         if (file) {
//             setSelectedFile(file);
//         }

//     });


//     function setSelectedFile(file) {

//         selectedUpload = file;

//         fileName.textContent = file.name;

//         fileSize.textContent =
//             formatFileSize(file.size);

//         uploadZone.classList.add("hidden");
//         selectedFile.classList.remove("hidden");

//     }


//     function formatFileSize(bytes) {

//         if (bytes < 1024) {
//             return `${bytes} B`;
//         }

//         if (bytes < 1024 * 1024) {
//             return `${(bytes / 1024).toFixed(1)} KB`;
//         }

//         return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

//     }


//     removeFile.addEventListener("click", () => {

//         selectedUpload = null;

//         fileInput.value = "";

//         selectedFile.classList.add("hidden");
//         uploadZone.classList.remove("hidden");

//     });


//     /* =====================================================
//        DRAG & DROP
//     ===================================================== */

//     ["dragenter", "dragover"].forEach(eventName => {

//         uploadZone.addEventListener(eventName, event => {

//             event.preventDefault();

//             uploadZone.classList.add("dragging");

//         });

//     });


//     ["dragleave", "drop"].forEach(eventName => {

//         uploadZone.addEventListener(eventName, event => {

//             event.preventDefault();

//             uploadZone.classList.remove("dragging");

//         });

//     });


//     uploadZone.addEventListener("drop", event => {

//         const file = event.dataTransfer.files[0];

//         if (!file) {
//             return;
//         }

//         setSelectedFile(file);

//     });


//     /* =====================================================
//        ANALYZE
//     ===================================================== */

//     analyzeBtn.addEventListener("click", async () => {

//         hideError();

//         const formData = new FormData();


//         /* ---------------------------------------------
//            TEXT
//         --------------------------------------------- */

//         if (currentType === "text") {

//             const text = jobText.value.trim();

//             if (!text) {

//                 showError(
//                     "Please paste the job posting or recruiter message first."
//                 );

//                 jobText.focus();

//                 return;
//             }

//             formData.append("text", text);

//         }


//         /* ---------------------------------------------
//            IMAGE / DOCUMENT
//         --------------------------------------------- */

//         else if (
//             currentType === "image" ||
//             currentType === "document"
//         ) {

//             if (!selectedUpload) {

//                 showError(
//                     "Please choose a file before starting the analysis."
//                 );

//                 return;
//             }

//             formData.append("file", selectedUpload);

//         }


//         /* ---------------------------------------------
//            URL
//         --------------------------------------------- */

//         else if (currentType === "url") {

//             const url = jobUrl.value.trim();

//             if (!url) {

//                 showError(
//                     "Please enter a job URL before starting the analysis."
//                 );

//                 jobUrl.focus();

//                 return;
//             }

//             formData.append("url", url);

//         }


//         setLoading(true);


//         try {

//             /*
//              * IMPORTANT:
//              *
//              * This calls your Flask backend.
//              *
//              * The backend should run:
//              *
//              * run_investigation(...)
//              *
//              * and return the actual investigation result.
//              *
//              * No risk assessment is calculated here.
//              */

//             const response = await fetch("/analyze", {
//                 method: "POST",
//                 body: formData
//             });


//             let data;

//             try {
//                 data = await response.json();
//             }

//             catch {
//                 throw new Error(
//                     "The server returned an invalid response."
//                 );
//             }


//             if (!response.ok) {

//                 throw new Error(
//                     data.error ||
//                     data.message ||
//                     "The analysis could not be completed."
//                 );

//             }


//             /*
//              * Store the real backend result temporarily.
//              *
//              * results.html reads this data.
//              */

//             sessionStorage.setItem(
//                 "jobGuardResult",
//                 JSON.stringify(data)
//             );


//             window.location.href = "/results";

//         }

//         catch (error) {

//             setLoading(false);

//             showError(
//                 error.message ||
//                 "Something went wrong while analyzing the job."
//             );

//         }

//     });


//     /* =====================================================
//        LOADING STATE
//     ===================================================== */

//     function setLoading(isLoading) {

//         if (isLoading) {

//             analyzeBtn.disabled = true;

//             analyzeBtn.innerHTML = `
//                 Analyzing
//                 <span class="button-arrow">...</span>
//             `;

//             loadingState.classList.remove("hidden");

//         }

//         else {

//             analyzeBtn.disabled = false;

//             analyzeBtn.innerHTML = `
//                 Analyze Job
//                 <span class="button-arrow">→</span>
//             `;

//             loadingState.classList.add("hidden");

//         }

//     }


//     /* =====================================================
//        ERROR
//     ===================================================== */

//     function showError(message) {

//         errorMessage.textContent = message;

//         errorBox.classList.remove("hidden");

//         errorBox.scrollIntoView({
//             behavior: "smooth",
//             block: "nearest"
//         });

//     }


//     function hideError() {

//         errorBox.classList.add("hidden");

//     }

// });



document.addEventListener("DOMContentLoaded", () => {

    const startCheckBtn = document.getElementById("startCheckBtn");
    const checker = document.getElementById("checker");

    const inputCards = document.querySelectorAll(".input-type-card");

    const textPanel = document.getElementById("textPanel");
    const filePanel = document.getElementById("filePanel");
    const urlPanel = document.getElementById("urlPanel");

    const jobText = document.getElementById("jobText");
    const jobUrl = document.getElementById("jobUrl");

    const charCounter = document.getElementById("charCounter");

    const uploadZone = document.getElementById("uploadZone");
    const fileInput = document.getElementById("fileInput");

    const selectedFile = document.getElementById("selectedFile");
    const fileName = document.getElementById("fileName");
    const fileSize = document.getElementById("fileSize");

    const removeFile = document.getElementById("removeFile");

    const uploadTitle = document.getElementById("uploadTitle");
    const uploadDescription = document.getElementById("uploadDescription");
    const uploadFormats = document.getElementById("uploadFormats");

    const analyzeBtn = document.getElementById("analyzeBtn");

    const loadingState = document.getElementById("loadingState");
    const errorBox = document.getElementById("errorBox");
    const errorMessage = document.getElementById("errorMessage");

    let currentType = "text";
    let selectedUpload = null;

    /* =====================================================
       START CHECK
    ===================================================== */
    if (startCheckBtn && checker) {
        startCheckBtn.addEventListener("click", () => {
            checker.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        });
    }

    /* =====================================================
       INPUT TYPE SWITCHING
    ===================================================== */
    if (inputCards.length > 0) {
        inputCards.forEach(card => {
            card.addEventListener("click", () => {
                inputCards.forEach(item => {
                    item.classList.remove("active");
                });

                card.classList.add("active");
                currentType = card.dataset.type;

                if (textPanel) textPanel.classList.add("hidden");
                if (filePanel) filePanel.classList.add("hidden");
                if (urlPanel) urlPanel.classList.add("hidden");

                if (currentType === "text" && textPanel) {
                    textPanel.classList.remove("hidden");
                } else if ((currentType === "image" || currentType === "document") && filePanel) {
                    filePanel.classList.remove("hidden");
                    configureUploadType();
                } else if (currentType === "url" && urlPanel) {
                    urlPanel.classList.remove("hidden");
                }

                hideError();
            });
        });
    }

    /* =====================================================
       CHARACTER COUNTER
    ===================================================== */
    if (jobText && charCounter) {
        jobText.addEventListener("input", () => {
            const length = jobText.value.length;
            charCounter.textContent = `${length.toLocaleString()} characters`;
        });
    }

    /* =====================================================
       FILE TYPE CONFIG
    ===================================================== */
    function configureUploadType() {
        selectedUpload = null;
        if (selectedFile) selectedFile.classList.add("hidden");
        if (uploadZone) uploadZone.classList.remove("hidden");
        if (fileInput) fileInput.value = "";

        if (currentType === "image") {
            if (uploadTitle) uploadTitle.textContent = "Drop your image here";
            if (uploadDescription) uploadDescription.textContent = "or click to browse from your device";
            if (uploadFormats) uploadFormats.textContent = "PNG, JPG, JPEG";
            if (fileInput) fileInput.accept = ".png,.jpg,.jpeg,image/png,image/jpeg";
        } else {
            if (uploadTitle) uploadTitle.textContent = "Drop your document here";
            if (uploadDescription) uploadDescription.textContent = "or click to browse from your device";
            if (uploadFormats) uploadFormats.textContent = "PDF, DOCX, TXT";
            if (fileInput) {
                fileInput.accept =
                    ".pdf,.docx,.txt,application/pdf," +
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain";
            }
        }
    }

    /* =====================================================
       FILE UPLOAD & DRAG/DROP
    ===================================================== */
    if (uploadZone && fileInput) {
        uploadZone.addEventListener("click", () => {
            fileInput.click();
        });

        ["dragenter", "dragover"].forEach(eventName => {
            uploadZone.addEventListener(eventName, event => {
                event.preventDefault();
                uploadZone.classList.add("dragging");
            });
        });

        ["dragleave", "drop"].forEach(eventName => {
            uploadZone.addEventListener(eventName, event => {
                event.preventDefault();
                uploadZone.classList.remove("dragging");
            });
        });

        uploadZone.addEventListener("drop", event => {
            const file = event.dataTransfer.files[0];
            if (file) setSelectedFile(file);
        });
    }

    if (fileInput) {
        fileInput.addEventListener("change", event => {
            const file = event.target.files[0];
            if (file) setSelectedFile(file);
        });
    }

    function setSelectedFile(file) {
        selectedUpload = file;
        if (fileName) fileName.textContent = file.name;
        if (fileSize) fileSize.textContent = formatFileSize(file.size);
        if (uploadZone) uploadZone.classList.add("hidden");
        if (selectedFile) selectedFile.classList.remove("hidden");
    }

    function formatFileSize(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    if (removeFile) {
        removeFile.addEventListener("click", () => {
            selectedUpload = null;
            if (fileInput) fileInput.value = "";
            if (selectedFile) selectedFile.classList.add("hidden");
            if (uploadZone) uploadZone.classList.remove("hidden");
        });
    }

    /* =====================================================
       ANALYZE
    ===================================================== */
    if (analyzeBtn) {
        analyzeBtn.addEventListener("click", async () => {
            hideError();
            const formData = new FormData();

            if (currentType === "text") {
                const text = jobText ? jobText.value.trim() : "";
                if (!text) {
                    showError("Please paste the job posting or recruiter message first.");
                    if (jobText) jobText.focus();
                    return;
                }
                formData.append("text", text);
            } else if (currentType === "image" || currentType === "document") {
                if (!selectedUpload) {
                    showError("Please choose a file before starting the analysis.");
                    return;
                }
                formData.append("file", selectedUpload);
            } else if (currentType === "url") {
                const url = jobUrl ? jobUrl.value.trim() : "";
                if (!url) {
                    showError("Please enter a job URL before starting the analysis.");
                    if (jobUrl) jobUrl.focus();
                    return;
                }
                formData.append("url", url);
            }

            setLoading(true);

            try {
                const response = await fetch("/analyze", {
                    method: "POST",
                    body: formData
                });

                let data;
                try {
                    data = await response.json();
                } catch {
                    throw new Error("The server returned an invalid response.");
                }

                if (!response.ok) {
                    throw new Error(
                        data.error || data.message || "The analysis could not be completed."
                    );
                }

                sessionStorage.setItem("jobGuardResult", JSON.stringify(data));
                window.location.href = "/results";

            } catch (error) {
                setLoading(false);
                showError(error.message || "Something went wrong while analyzing the job.");
            }
        });
    }

    function setLoading(isLoading) {
        if (!analyzeBtn) return;
        if (isLoading) {
            analyzeBtn.disabled = true;
            analyzeBtn.innerHTML = `Analyzing <span class="button-arrow">...</span>`;
            if (loadingState) loadingState.classList.remove("hidden");
        } else {
            analyzeBtn.disabled = false;
            analyzeBtn.innerHTML = `Analyze Job <span class="button-arrow">→</span>`;
            if (loadingState) loadingState.classList.add("hidden");
        }
    }

    function showError(message) {
        if (!errorBox || !errorMessage) return;
        errorMessage.textContent = message;
        errorBox.classList.remove("hidden");
        errorBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function hideError() {
        if (errorBox) errorBox.classList.add("hidden");
    }
});