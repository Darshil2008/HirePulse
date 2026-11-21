// WorkLane Careers & Recruitment Platform JavaScript
let currentModalJobId = null;

document.addEventListener("DOMContentLoaded", function () {
    console.log("WorkLane Platform initialized successfully.");

    // Scroll Dock floating animation
    const dock = document.getElementById("tjScrollDock");
    if (dock) {
        window.addEventListener("scroll", function () {
            if (window.scrollY > 250) {
                dock.classList.add("is-visible");
            } else {
                dock.classList.remove("is-visible");
            }
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

// Progressive Load More for Results List
function loadMoreJobs() {
    const hiddenJobs = Array.from(document.querySelectorAll(".bb-job-hidden"));
    if (!hiddenJobs.length) {
        const wrap = document.getElementById("bbLoadMoreWrapper");
        if (wrap) wrap.style.display = "none";
        return;
    }
    const batchSize = 6;
    const toReveal = hiddenJobs.slice(0, batchSize);
    toReveal.forEach(function (jobEl) {
        jobEl.classList.remove("bb-job-hidden");
        jobEl.style.display = "";
        jobEl.style.animation = "fadeInJob 0.3s ease forwards";
    });

    const remainingHidden = document.querySelectorAll(".bb-job-hidden").length;
    const loadMoreBtn = document.getElementById("bbLoadMoreBtn");
    if (loadMoreBtn && remainingHidden > 0) {
        loadMoreBtn.innerText = `LOAD MORE POSITIONS (${remainingHidden} REMAINING)`;
    } else if (remainingHidden === 0) {
        const loadMoreWrap = document.getElementById("bbLoadMoreWrapper");
        if (loadMoreWrap) {
            loadMoreWrap.style.display = "none";
        }
    }
}

// Toggle Collapsible Filters Panel (On-Demand)
function toggleFiltersPanel() {
    const panel = document.getElementById("collapsibleFiltersPanel");
    const btnText = document.getElementById("filtersBtnText");
    const btn = document.getElementById("toggleFiltersBtn");
    if (!panel) return;

    const isCurrentlyHidden = (panel.style.display === "none" || window.getComputedStyle(panel).display === "none");
    if (isCurrentlyHidden) {
        panel.style.display = "block";
        panel.classList.remove("d-none");
        if (btnText) btnText.textContent = "Hide Filters";
        if (btn) btn.classList.add("active");
    } else {
        panel.style.display = "none";
        panel.classList.add("d-none");
        if (btnText) btnText.textContent = "View Filters";
        if (btn) btn.classList.remove("active");
    }
}

// Canvas Theme Switcher (Alabaster / Studio White / Soft Pearl / Warm Paper)
function setCanvasTheme(themeName) {
    let color = '#f7f7f4';
    if (themeName === 'studio-white') color = '#ffffff';
    else if (themeName === 'soft-pearl') color = '#f3f4f6';
    else if (themeName === 'warm-paper') color = '#f6f5ee';
    else if (themeName === 'cream') color = '#ffffeb';
    else color = '#f7f7f4';

    document.documentElement.style.setProperty('--color-lumen-cream', color, 'important');
    document.body.style.setProperty('background-color', color, 'important');
    
    try {
        localStorage.setItem('worklane_canvas_theme', themeName);
    } catch (e) {}

    document.querySelectorAll('.canvas-theme-btn').forEach(function(btn) {
        if (btn.getAttribute('data-theme') === themeName) {
            btn.classList.add('btn-dark', 'text-white');
            btn.classList.remove('btn-outline-dark');
        } else {
            btn.classList.remove('btn-dark', 'text-white');
            btn.classList.add('btn-outline-dark');
        }
    });
}

// Progressive Load More for Recruiter Active Postings
function loadMoreRecruiterJobs() {
    const hiddenRows = Array.from(document.querySelectorAll(".recruiter-job-hidden"));
    if (!hiddenRows.length) {
        const wrap = document.getElementById("recruiterLoadMoreWrapper");
        if (wrap) wrap.style.display = "none";
        return;
    }
    const batchSize = 5;
    const toReveal = hiddenRows.slice(0, batchSize);
    toReveal.forEach(function (row) {
        row.classList.remove("recruiter-job-hidden");
        row.style.display = "";
        row.style.animation = "fadeInJob 0.3s ease forwards";
    });

    const remaining = document.querySelectorAll(".recruiter-job-hidden").length;
    const btn = document.getElementById("recruiterLoadMoreBtn");
    if (btn && remaining > 0) {
        btn.innerText = `LOAD MORE POSTINGS (${remaining} REMAINING)`;
    } else if (remaining === 0) {
        const wrap = document.getElementById("recruiterLoadMoreWrapper");
        if (wrap) wrap.style.display = "none";
    }
}

// Restore saved canvas theme
try {
    const savedTheme = localStorage.getItem('worklane_canvas_theme');
    if (savedTheme) setCanvasTheme(savedTheme);
} catch (e) {}

// Open Job Details Modal via AJAX
function openJobDetail(jobId) {
    currentModalJobId = jobId;
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

            // Render Match Score if available
            const matchContainer = document.getElementById("modalMatchContainer");
            if (matchContainer) {
                if (job.match_score && job.match_score.match_pct > 0) {
                    matchContainer.classList.remove("d-none");
                    document.getElementById("modalMatchPct").textContent = `${job.match_score.match_pct}% Match`;
                    document.getElementById("modalMatchSummary").textContent = 
                        `${job.match_score.matching_skills.length} matching skills of ${job.match_score.total_skills.length} required (${job.match_score.matching_skills.join(", ")})`;
                } else {
                    matchContainer.classList.add("d-none");
                }
            }

            // Render Skills
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

            // Render Similar Jobs
            const similarContainer = document.getElementById("modalSimilarJobsContainer");
            const similarList = document.getElementById("modalSimilarJobsList");
            if (similarContainer && similarList) {
                if (job.similar_jobs && job.similar_jobs.length > 0) {
                    similarContainer.classList.remove("d-none");
                    similarList.innerHTML = job.similar_jobs.map(sj => `
                        <div class="d-flex justify-content-between align-items-center p-2 rounded bg-light border small">
                            <div>
                                <strong class="text-dark">${sj.title}</strong>
                                <span class="text-muted ms-2">${sj.company} • ${sj.location}</span>
                            </div>
                            <button type="button" class="btn btn-sm btn-outline-primary py-0" onclick="openJobDetail(${sj.id})">
                                View
                            </button>
                        </div>
                    `).join("");
                } else {
                    similarContainer.classList.add("d-none");
                }
            }

            // Render Apply button
            const actionContainer = document.getElementById("modalActionContainer");
            actionContainer.innerHTML = `
                <button type="button" class="btn btn-primary btn-sm px-4 fw-semibold" onclick="openApplyModal(${job.id}, '${job.title.replace(/'/g, "\\'")}', '${job.company.replace(/'/g, "\\'")}')">
                    Apply For Position →
                </button>
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
