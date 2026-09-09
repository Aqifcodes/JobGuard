document.addEventListener("DOMContentLoaded", () => {

    const container = document.getElementById("jobsContainer");
    const noJobs = document.getElementById("noJobs");
    const summary = document.getElementById("searchSummary");

    const stored = sessionStorage.getItem("jobGuardJobs");

    console.log("JobGuard stored job data:", stored);

    if (!stored) {
        if (noJobs) {
            noJobs.hidden = false;
        }

        if (summary) {
            summary.textContent =
                "No search information was found.";
        }

        console.warn("JobGuard: No job data found in sessionStorage.");
        return;
    }

    let data;

    try {
        data = JSON.parse(stored);
    } catch (error) {

        console.error(
            "JobGuard: Failed to parse stored job data.",
            error
        );

        if (noJobs) {
            noJobs.hidden = false;
        }

        if (summary) {
            summary.textContent =
                "Unable to load the search results.";
        }

        return;
    }

    console.log("JobGuard parsed job data:", data);

    const jobs = Array.isArray(data.jobs)
        ? data.jobs
        : [];

    console.log("JobGuard jobs received:", jobs.length);

    if (summary) {
        summary.textContent =
            `Showing ${jobs.length} relevant opportunities` +
            (data.role
                ? ` for ${data.role}`
                : "") +
            (data.location
                ? ` in ${data.location}`
                : "");
    }

    if (!container) {
        console.error(
            "JobGuard: jobsContainer element was not found."
        );
        return;
    }

    if (jobs.length === 0) {

        if (noJobs) {
            noJobs.hidden = false;
        }

        return;
    }

    if (noJobs) {
        noJobs.hidden = true;
    }

    container.innerHTML = "";

    jobs.forEach((job, index) => {

        const card = document.createElement("article");

        card.className = "job-card";

        const title = escapeHtml(
            job.title || "Job opportunity"
        );

        const company = escapeHtml(
            job.company || "Company not specified"
        );

        const location = escapeHtml(
            job.location || "Location not specified"
        );

        const description = escapeHtml(
            truncate(
                job.description || "",
                240
            )
        );

        const source = escapeHtml(
            job.source || "Job source"
        );

        const url = escapeAttribute(
            job.url || "#"
        );

        card.innerHTML = `
            <div class="job-card-number">
                ${index + 1}
            </div>

            <div class="job-card-content">

                <h2>
                    ${title}
                </h2>

                <div class="job-company">
                    ${company}
                </div>

                <div class="job-location">
                    ${location}
                </div>

                <p class="job-description">
                    ${description}
                </p>

                <div class="job-source">
                    <span>
                        Source: ${source}
                    </span>
                </div>

                <a
                    class="apply-button"
                    href="${url}"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    View Job & Apply →
                </a>

            </div>
        `;

        container.appendChild(card);
    });

});


function truncate(text, maxLength) {

    if (!text) {
        return "";
    }

    if (text.length <= maxLength) {
        return text;
    }

    return text.substring(0, maxLength).trim() + "...";
}


function escapeHtml(value) {

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function escapeAttribute(value) {

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}