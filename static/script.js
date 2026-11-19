// HirePulse Careers Platform JavaScript
document.addEventListener("DOMContentLoaded", function () {
    console.log("HirePulse Platform initialized successfully.");

    // Scroll Dock floating animation
    const dock = document.getElementById("tjScrollDock");
    if (dock) {
        let lastScrollY = window.scrollY;
        window.addEventListener("scroll", function () {
            if (window.scrollY > 250) {
                dock.classList.add("is-visible");
            } else {
                dock.classList.remove("is-visible");
            }
            lastScrollY = window.scrollY;
        }, { passive: true });
    }

    // Auto-dismiss alert banners after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000);
    });
});

// Toggle More Locations filter dropdown
function toggleMoreLocations(linkEl) {
    const moreDiv = document.getElementById("bbMoreLocations");
    if (!moreDiv) return;

    if (moreDiv.style.display === "none" || moreDiv.style.display === "") {
        moreDiv.style.display = "block";
        if (linkEl) linkEl.textContent = "- Fewer locations";
    } else {
        moreDiv.style.display = "none";
        if (linkEl) linkEl.textContent = "+ More locations";
    }
}

// Progressive Load More for Results List (Bloomberg style)
function loadMoreJobs() {
    const hiddenJobs = document.querySelectorAll(".bb-job-hidden");
    const batchSize = 10;
    
    let revealed = 0;
    hiddenJobs.forEach(function (jobEl) {
        if (revealed < batchSize) {
            jobEl.classList.remove("bb-job-hidden");
            revealed++;
        }
    });

    const remainingHidden = document.querySelectorAll(".bb-job-hidden");
    if (remainingHidden.length === 0) {
        const loadMoreWrap = document.getElementById("bbLoadMoreWrapper");
        if (loadMoreWrap) {
            loadMoreWrap.style.display = "none";
        }
    }
}

// Open Job Details Modal via AJAX
function openJobDetail(jobId) {
    fetch(`/api/job/${jobId}`)
        .then(response => {
            if (!response.ok) throw new Error("Failed to load job details");
            return response.json();
        })
        .then(job => {
            document.getElementById("modalJobTitle").textContent = job.title;
            document.getElementById("modalJobCompany").textContent = job.company;
            document.getElementById("modalJobLocation").textContent = job.location;
            document.getElementById("modalJobType").textContent = job.job_type;
            document.getElementById("modalJobMode").textContent = job.work_mode;
            document.getElementById("modalJobSalary").textContent = job.salary;
            document.getElementById("modalJobDate").textContent = job.formatted_date;
            document.getElementById("modalJobDesc").textContent = job.description;
            document.getElementById("modalJobFunction").textContent = job.function;

            // Render skills
            const skillsContainer = document.getElementById("modalJobSkills");
            skillsContainer.innerHTML = "";
            if (job.skills) {
                const skillsList = job.skills.split(",");
                skillsList.forEach(s => {
                    const tag = document.createElement("span");
                    tag.className = "badge bg-light text-dark border px-2 py-1";
                    tag.textContent = s.trim();
                    skillsContainer.appendChild(tag);
                });
            }

            // Render Apply button
            const actionContainer = document.getElementById("modalActionContainer");
            actionContainer.innerHTML = `
                <form method="POST" action="/apply/${job.id}" style="display:inline;">
                    <button type="submit" class="btn btn-dark btn-sm px-4 fw-semibold">Apply For This Position →</button>
                </form>
            `;

            // Open Modal
            const modalEl = document.getElementById("bbJobModal");
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        })
        .catch(err => {
            console.error(err);
            window.location.href = `/?search=${jobId}`;
        });
}

// 1-Click Demo Login Fill
function fillDemo(email, password) {
    const emailField = document.getElementById("email");
    const passField = document.getElementById("password");
    if (emailField) emailField.value = email;
    if (passField) passField.value = password;
}

// Password Visibility Toggle
function togglePasswordVisibility(fieldId, btn) {
    const field = document.getElementById(fieldId);
    if (!field) return;

    if (field.type === "password") {
        field.type = "text";
        if (btn) btn.innerHTML = '<i class="bi bi-eye-slash"></i>';
    } else {
        field.type = "password";
        if (btn) btn.innerHTML = '<i class="bi bi-eye"></i>';
    }
}
