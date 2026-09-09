// document.addEventListener("DOMContentLoaded", () => {

//     const findJobsBtn = document.getElementById("findJobsBtn");
//     const searchPanel = document.getElementById("jobSearchPanel");
//     const searchJobsBtn = document.getElementById("searchJobsBtn");

//     const roleSelect = document.getElementById("jobRole");
//     const locationSelect = document.getElementById("jobLocation");
//     const experienceSelect = document.getElementById("jobExperience");

//     const errorBox = document.getElementById("jobSearchError");
//     const loadingBox = document.getElementById("jobSearchLoading");

//     // Handle auto-opening panel from external redirects
//     const shouldOpen = sessionStorage.getItem("openJobSearch");

//     if (shouldOpen === "true") {
//         sessionStorage.removeItem("openJobSearch");

//         if (searchPanel) {
//             searchPanel.hidden = false;

//             setTimeout(() => {
//                 searchPanel.scrollIntoView({
//                     behavior: "smooth",
//                     block: "center"
//                 });
//             }, 100);
//         }
//     }


//     if (findJobsBtn) {
//         findJobsBtn.addEventListener("click", () => {
//             if (searchPanel) {
//                 searchPanel.hidden = false;

//                 searchPanel.scrollIntoView({
//                     behavior: "smooth",
//                     block: "center"
//                 });
//             }
//         });
//     }


//     if (searchJobsBtn) {
//         searchJobsBtn.addEventListener("click", async () => {

//             const role = roleSelect ? roleSelect.value : "";
//             const location = locationSelect ? locationSelect.value : "";
//             const experience = experienceSelect ? experienceSelect.value : "";


//             if (errorBox) {
//                 errorBox.hidden = true;
//                 errorBox.textContent = "";
//             }


//             if (!role) {
//                 if (errorBox) {
//                     errorBox.textContent =
//                         "Please select the type of job you're looking for.";
//                     errorBox.hidden = false;
//                 }
//                 return;
//             }


//             searchJobsBtn.disabled = true;
//             if (loadingBox) loadingBox.hidden = false;


//             try {

//                 const response = await fetch(
//                     "/api/jobs/search",
//                     {
//                         method: "POST",

//                         headers: {
//                             "Content-Type": "application/json"
//                         },

//                         body: JSON.stringify({
//                             role,
//                             location,
//                             experience
//                         })
//                     }
//                 );


//                 const data = await response.json();


//                 if (!response.ok || !data.success) {
//                     throw new Error(
//                         data.error ||
//                         "Unable to find jobs right now."
//                     );
//                 }


//                 sessionStorage.setItem(
//                     "jobGuardJobs",
//                     JSON.stringify(data)
//                 );


//                 window.location.href = "/jobs";


//             } catch (error) {

//                 if (errorBox) {
//                     errorBox.textContent =
//                         error.message ||
//                         "Something went wrong while searching for jobs.";
//                     errorBox.hidden = false;
//                 }

//             } finally {

//                 searchJobsBtn.disabled = false;
//                 if (loadingBox) loadingBox.hidden = true;

//             }

//         });
//     }

// });


document.addEventListener("DOMContentLoaded", () => {

    const findJobsBtn = document.getElementById("findJobsBtn");
    const searchPanel = document.getElementById("jobSearchModal") || document.getElementById("jobSearchPanel");
    const searchJobsBtn = document.getElementById("searchJobsBtn");
    const closeJobSearchBtn = document.getElementById("closeJobSearchBtn");

    const roleSelect = document.getElementById("jobRole");
    const locationSelect = document.getElementById("jobLocation");
    const experienceSelect = document.getElementById("jobExperience");

    const errorBox = document.getElementById("jobSearchError");
    const loadingBox = document.getElementById("jobSearchLoading");

    // Handle auto-opening panel from external redirects
    const shouldOpen = sessionStorage.getItem("openJobSearch");

    if (shouldOpen === "true") {
        sessionStorage.removeItem("openJobSearch");

        if (searchPanel) {
            searchPanel.hidden = false;
            searchPanel.removeAttribute("hidden");

            setTimeout(() => {
                searchPanel.scrollIntoView({
                    behavior: "smooth",
                    block: "center"
                });
            }, 100);
        }
    }

    if (findJobsBtn) {
        findJobsBtn.addEventListener("click", (e) => {
            e.preventDefault();

            if (searchPanel) {
                searchPanel.hidden = false;
                searchPanel.removeAttribute("hidden");

                searchPanel.scrollIntoView({
                    behavior: "smooth",
                    block: "center"
                });
            } else {
                // Redirect to home page and flag modal to open on load
                sessionStorage.setItem("openJobSearch", "true");
                window.location.href = "/";
            }
        });
    }


// Add this listener block:
        if (closeJobSearchBtn && searchPanel) {
            closeJobSearchBtn.addEventListener("click", () => {
            searchPanel.hidden = true;
            searchPanel.setAttribute("hidden", "true");
    });
}
    if (searchJobsBtn) {
        searchJobsBtn.addEventListener("click", async () => {

            const role = roleSelect ? roleSelect.value : "";
            const location = locationSelect ? locationSelect.value : "";
            const experience = experienceSelect ? experienceSelect.value : "";

            if (errorBox) {
                errorBox.hidden = true;
                errorBox.textContent = "";
            }

            if (!role) {
                if (errorBox) {
                    errorBox.textContent = "Please select the type of job you're looking for.";
                    errorBox.hidden = false;
                }
                return;
            }

            searchJobsBtn.disabled = true;
            if (loadingBox) loadingBox.hidden = false;

            try {
                const response = await fetch("/api/jobs/search", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        role,
                        location,
                        experience
                    })
                });

                const data = await response.json();

                if (!response.ok || !data.success) {
                    throw new Error(
                        data.error || "Unable to find jobs right now."
                    );
                }

                sessionStorage.setItem(
                    "jobGuardJobs",
                    JSON.stringify(data)
                );

                window.location.href = "/jobs";

            } catch (error) {
                if (errorBox) {
                    errorBox.textContent =
                        error.message || "Something went wrong while searching for jobs.";
                    errorBox.hidden = false;
                }
            } finally {
                searchJobsBtn.disabled = false;
                if (loadingBox) loadingBox.hidden = true;
            }
        });
    }
});
