// Backend API Configuration
const API_BASE = "http://localhost:8000";

// State Management
let sessionToken = localStorage.getItem("token") || null;
let currentUser = { username: localStorage.getItem("username") || "", role: localStorage.getItem("role") || "" };
let sessionId = null;
let charts = { inventory: null, shipping: null };
let apiStats = null;
let activeFilters = { type: "", source: "" };

// Generate random session id on startup
function initSession() {
    sessionId = "session_" + Math.random().toString(36).substring(2, 11);
}

// DOM Elements - Login
const loginScreen = document.getElementById("loginScreen");
const loginForm = document.getElementById("loginForm");
const usernameInput = document.getElementById("usernameInput");
const passwordInput = document.getElementById("passwordInput");
const demoUserBtns = document.querySelectorAll(".demo-user-btn");

// DOM Elements - Main Layout
const appMainContainer = document.getElementById("appMainContainer");
const userBadgeName = document.getElementById("userBadgeName");
const userBadgeRole = document.getElementById("userBadgeRole");
const logoutBtn = document.getElementById("logoutBtn");
const currentViewTitle = document.getElementById("currentViewTitle");
const navTabs = document.querySelectorAll(".nav-tab");
const viewPanels = document.querySelectorAll(".view-panel");

// DOM Elements - Chat
const chatHistory = document.getElementById("chatHistory");
const chatInputForm = document.getElementById("chatInputForm");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");

// DOM Elements - RAG Trace
const expandedQueriesList = document.getElementById("expandedQueriesList");
const sparseResultsBody = document.getElementById("sparseResultsBody");
const denseResultsBody = document.getElementById("denseResultsBody");
const rrfResultsBody = document.getElementById("rrfResultsBody");

// DOM Elements - Products
const productSearchInput = document.getElementById("productSearchInput");
const productSearchBtn = document.getElementById("productSearchBtn");
const productResultsBody = document.getElementById("productResultsBody");

// DOM Elements - Inventory KPIs
const kpiTotalInventory = document.getElementById("kpiTotalInventory");
const kpiLowStock = document.getElementById("kpiLowStock");
const kpiShipments = document.getElementById("kpiShipments");
const kpiOtif = document.getElementById("kpiOtif");
const kpiLowStockCard = document.getElementById("kpiLowStockCard");
const lowStockTableBody = document.getElementById("lowStockTableBody");

// DOM Elements - Knowledge / Document Base
const docList = document.getElementById("documentList");
const docCountBadge = document.getElementById("docCountBadge");
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const filterDocType = document.getElementById("filterDocType");
const filterSource = document.getElementById("filterSource");

// DOM Elements - Admin Security Logs
const adminAccessDenied = document.getElementById("adminAccessDenied");
const adminAccessGranted = document.getElementById("adminAccessGranted");
const restrictedUserRole = document.getElementById("restrictedUserRole");
const auditLogsBody = document.getElementById("auditLogsBody");

// DOM Elements - Modal & API Config
const configKeyBtn = document.getElementById("configKeyBtn");
const modalOverlay = document.getElementById("modalOverlay");
const modalCloseBtn = document.getElementById("modalCloseBtn");
const apiKeyInput = document.getElementById("apiKeyInput");
const apiKeyToggle = document.getElementById("apiKeyToggle");
const saveKeyBtn = document.getElementById("saveKeyBtn");
const clearKeyBtn = document.getElementById("clearKeyBtn");

/* ==========================================
   INITIALIZATION & SETUP
   ========================================== */
document.addEventListener("DOMContentLoaded", () => {
    initSession();
    
    // Check if token already exists (Auto login)
    if (sessionToken) {
        showMainApp();
    } else {
        showLoginScreen();
    }

    // Set up standard key configs from storage
    const cachedKey = localStorage.getItem("gemini_api_key");
    if (cachedKey) {
        apiKeyInput.value = cachedKey;
        updateBackendKey(cachedKey);
    } else {
        const dot = document.querySelector(".engine-indicator .status-dot");
        const statusText = document.getElementById("engineStatusText");
        if (dot && statusText) {
            dot.className = "status-dot yellow";
            statusText.textContent = "RAG Engine Online (Demo Mode)";
        }
    }

    setupEventListeners();
    setupDropzone();
});

// View switching & Navigation
function showLoginScreen() {
    loginScreen.style.display = "flex";
    appMainContainer.style.display = "none";
}

function showMainApp() {
    loginScreen.style.display = "none";
    appMainContainer.style.display = "flex";
    
    // Set user badges
    userBadgeName.textContent = currentUser.username;
    userBadgeRole.textContent = currentUser.role;
    
    // Apply UI role restrictions
    applyRoleRestrictions();
    
    // Fetch initial workspace data
    fetchDocuments();
    fetchStats();
    searchProducts("");
}
function applyRoleRestrictions() {
    const role = currentUser.role;
    
    // Document uploads: Only Administrator, Category Manager, Procurement Manager
    const allowedToUpload = ["Administrator", "Category Manager", "Procurement Manager"].includes(role);
    if (allowedToUpload) {
        dropzone.style.pointerEvents = "auto";
        dropzone.style.opacity = "1";
    } else {
        dropzone.style.pointerEvents = "none";
        dropzone.style.opacity = "0.4";
        // Update prompt text to denote restriction
        const secondaryPrompt = dropzone.querySelector(".secondary-prompt");
        if (secondaryPrompt) {
            secondaryPrompt.textContent = "Upload Restricted (Requires Manager Privileges)";
        }
    }
    
    // Ingestion Hub: Only Administrator, Category Manager, Procurement Manager
    const allowedToIngest = ["Administrator", "Category Manager", "Procurement Manager"].includes(role);
    const apiSubmitBtn = document.getElementById("apiIngestSubmitBtn");
    const osSubmitBtn = document.getElementById("opensourceSubmitBtn");
    const demoPdfBtn = document.getElementById("downloadSamplePdfBtn");
    
    if (allowedToIngest) {
        if (apiSubmitBtn) apiSubmitBtn.disabled = false;
        if (osSubmitBtn) osSubmitBtn.disabled = false;
        if (demoPdfBtn) demoPdfBtn.disabled = false;
    } else {
        if (apiSubmitBtn) {
            apiSubmitBtn.disabled = true;
            const spanText = apiSubmitBtn.querySelector("span");
            if (spanText) spanText.textContent = "Ingestion Restricted (Requires Manager Privileges)";
        }
        if (osSubmitBtn) {
            osSubmitBtn.disabled = true;
            const spanText = osSubmitBtn.querySelector("span");
            if (spanText) spanText.textContent = "Ingestion Restricted (Requires Manager Privileges)";
        }
        if (demoPdfBtn) {
            demoPdfBtn.disabled = true;
        }
    }
}

function setupEventListeners() {
    // 1. LOGIN SUBMIT
    loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const username = usernameInput.value.trim();
        const password = passwordInput.value;
        
        await executeLogin(username, password);
    });

    // 2. DEMO LOGIN BUTTONS
    demoUserBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const username = btn.getAttribute("data-username");
            executeLogin(username, "password123");
        });
    });

    // 3. LOGOUT BUTTON
    logoutBtn.addEventListener("click", () => {
        localStorage.removeItem("token");
        localStorage.removeItem("username");
        localStorage.removeItem("role");
        sessionToken = null;
        currentUser = { username: "", role: "" };
        initSession();
        
        // Reset panels
        document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
        document.querySelector(".nav-tab[data-view='chat-view']").classList.add("active");
        document.querySelectorAll(".view-panel").forEach(vp => vp.classList.remove("active"));
        document.getElementById("view-chat-view").classList.add("active");
        chatHistory.innerHTML = "";
        
        showToast("Logged out successfully", "info");
        showLoginScreen();
    });

    // 4. VIEW TABS NAVIGATION
    navTabs.forEach(tab => {
        tab.addEventListener("click", () => {
            navTabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            
            const targetView = tab.getAttribute("data-view");
            viewPanels.forEach(panel => panel.classList.remove("active"));
            document.getElementById(`view-${targetView}`).classList.add("active");
            
            // Set header title
            const labelText = tab.querySelector("span").textContent;
            currentViewTitle.textContent = labelText;
            
            // Trigger specific actions when tabs become visible
            if (targetView === "inventory-view") {
                fetchStats();
            } else if (targetView === "products-view") {
                searchProducts(productSearchInput.value.trim());
            } else if (targetView === "admin-view") {
                loadAdminLogs();
            } else if (targetView === "knowledge-view") {
                fetchDocuments();
            } else if (targetView === "ingestion-view") {
                loadIngestionPresets();
                renderIngestionLogs();
            }
        });
    });

    // 5. CHAT SUBMIT
    chatInputForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (!text) return;
        
        submitUserQuery(text);
        chatInput.value = "";
    });

    // 6. SUGGESTED CHAT BUTTONS
    document.querySelectorAll(".suggested-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            submitUserQuery(btn.textContent);
        });
    });

    // 7. KEY CONFIG DIALOG MODAL
    configKeyBtn.addEventListener("click", () => modalOverlay.classList.add("active"));
    modalCloseBtn.addEventListener("click", () => modalOverlay.classList.remove("active"));
    modalOverlay.addEventListener("click", (e) => {
        if (e.target === modalOverlay) modalOverlay.classList.remove("active");
    });

    apiKeyToggle.addEventListener("click", () => {
        const type = apiKeyInput.type === "password" ? "text" : "password";
        apiKeyInput.type = type;
        apiKeyToggle.innerHTML = type === "password" ? '<i class="fa-solid fa-eye"></i>' : '<i class="fa-solid fa-eye-slash"></i>';
    });

    saveKeyBtn.addEventListener("click", () => {
        const key = apiKeyInput.value.trim();
        if (key) {
            localStorage.setItem("gemini_api_key", key);
            updateBackendKey(key);
            showToast("Gemini API key configured", "success");
        } else {
            showToast("Please enter a valid key", "warning");
        }
        modalOverlay.classList.remove("active");
    });

    clearKeyBtn.addEventListener("click", () => {
        localStorage.removeItem("gemini_api_key");
        apiKeyInput.value = "";
        updateBackendKey("");
        showToast("Gemini API key cleared. Running locally.", "info");
        modalOverlay.classList.remove("active");
    });

    // 8. PRODUCT SEARCH TRIGGERS
    productSearchBtn.addEventListener("click", () => {
        searchProducts(productSearchInput.value.trim());
    });
    productSearchInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            searchProducts(productSearchInput.value.trim());
        }
    });

    // 9. METADATA FILTER DROPDOWNS
    filterDocType.addEventListener("change", () => {
        activeFilters.type = filterDocType.value;
        fetchDocuments();
    });
    filterSource.addEventListener("change", () => {
        activeFilters.source = filterSource.value;
    });

    // 10. THEME TOGGLE
    themeToggleBtn.addEventListener("click", () => {
        document.body.classList.toggle("light-theme");
        const isLight = document.body.classList.contains("light-theme");
        themeToggleBtn.innerHTML = isLight ? '<i class="fa-solid fa-moon"></i>' : '<i class="fa-solid fa-sun"></i>';
        initCharts(); // Redraw charts for light theme compatibility
    });
}

/* ==========================================
   AUTHENTICATION API
   ========================================== */
async function executeLogin(username, password) {
    try {
        const res = await fetch(`${API_BASE}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        
        if (res.ok && data.status === "success") {
            sessionToken = data.token;
            currentUser = { username: data.username, role: data.role };
            
            // Persist
            localStorage.setItem("token", data.token);
            localStorage.setItem("username", data.username);
            localStorage.setItem("role", data.role);
            
            showToast(`Signed in as ${data.username} (${data.role})`, "success");
            showMainApp();
            
            // Clean login forms
            usernameInput.value = "";
            passwordInput.value = "";
        } else {
            showToast(data.detail || "Authentication failed. Try again.", "error");
        }
    } catch (error) {
        console.error("Login failure:", error);
        showToast("Error connecting to auth server.", "error");
    }
}

/* ==========================================
   AI ASSISTANT CHAT HANDLER
   ========================================== */
function appendMessage(sender, text, citations = []) {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message", sender);
    
    let contentHtml = `<div class="message-content">`;
    
    // Parse Markdown Tables first
    if (text.includes("|")) {
        const lines = text.split("\n");
        let inTable = false;
        let tableHtml = "";
        let newLines = [];
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (line.startsWith("|") && line.endsWith("|")) {
                if (!inTable) {
                    inTable = true;
                    tableHtml = '<div class="grid-table-container"><table class="data-table"><thead>';
                    const cols = line.split("|").map(c => c.trim()).filter((c, idx, arr) => idx > 0 && idx < arr.length - 1);
                    tableHtml += "<tr>" + cols.map(c => `<th>${c}</th>`).join("") + "</tr></thead><tbody>";
                    if (i + 1 < lines.length && lines[i+1].trim().startsWith("|") && lines[i+1].includes("-")) {
                        i++; // Skip delimiter line
                    }
                } else {
                    const cols = line.split("|").map(c => c.trim()).filter((c, idx, arr) => idx > 0 && idx < arr.length - 1);
                    tableHtml += "<tr>" + cols.map(c => `<td>${c}</td>`).join("") + "</tr>";
                }
            } else {
                if (inTable) {
                    inTable = false;
                    tableHtml += "</tbody></table></div>";
                    newLines.push(tableHtml);
                    tableHtml = "";
                }
                newLines.push(lines[i]);
            }
        }
        if (inTable) {
            tableHtml += "</tbody></table></div>";
            newLines.push(tableHtml);
        }
        text = newLines.join("\n");
    }

    // Markdown formatting helper
    let formattedText = text
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>")
        .replace(/### (.*?)\n/g, "<h3>$1</h3>")
        .replace(/## (.*?)\n/g, "<h2>$1</h2>")
        .replace(/^- (.*?)$/gm, "<li>$1</li>")
        .replace(/(<li>.*?<\/li>)/gs, "<ul>$1</ul>")
        .replace(/<\/ul>\s*<ul>/g, "")
        .replace(/\n/g, "<br>");
        
    contentHtml += `<p>${formattedText}</p>`;
    
    // Check if assistant reply contains markdown report structure to allow downloading
    const isReport = text.includes("# ") || text.includes("## ") || text.includes("|");
    if (sender === "assistant" && isReport) {
        contentHtml += `
            <div class="report-actions" style="margin-top:12px; padding-top:8px; border-top:1px dashed rgba(255,255,255,0.05);">
                <button class="btn btn-secondary btn-xs" onclick="downloadReport('${text.replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/\n/g, '\\n')}')">
                    <i class="fa-solid fa-file-arrow-down"></i> Download Report (.md)
                </button>
            </div>
        `;
    }
    
    // Add citations
    if (citations && citations.length > 0) {
        contentHtml += `
            <div class="citations-area">
                <div class="citations-title">Sources consulted:</div>
                <div class="citations-list">
        `;
        
        citations.forEach((cit, idx) => {
            let label = cit.source;
            let detail = cit.text.substring(0, 200) + "...";
            if (cit.row_index) label += ` (Row ${cit.row_index})`;
            if (cit.pages) label += ` (Page ${cit.pages.join(",")})`;
            
            contentHtml += `
                <span class="citation-pill" title="Chunk excerpt: ${detail.replace(/"/g, '&quot;')}" onclick="alert('Document Citation Content:\\n\\n' + this.title)">
                    <i class="fa-solid fa-circle-info"></i> ${label}
                </span>
            `;
        });
        
        contentHtml += `</div></div>`;
    }
    
    contentHtml += `</div>`;
    msgDiv.innerHTML = contentHtml;
    
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function showTypingIndicator() {
    const indicator = document.createElement("div");
    indicator.classList.add("message", "assistant", "typing-loader");
    indicator.id = "typingIndicator";
    indicator.innerHTML = `
        <div class="message-content" style="padding: 10px 16px;">
            <span class="status-dot purple" style="display:inline-block; width:6px; height:6px; animation: bounce 0.6s infinite alternate;"></span>
            <span class="status-dot purple" style="display:inline-block; width:6px; height:6px; animation: bounce 0.6s infinite alternate 0.2s;"></span>
            <span class="status-dot purple" style="display:inline-block; width:6px; height:6px; animation: bounce 0.6s infinite alternate 0.4s;"></span>
        </div>
    `;
    chatHistory.appendChild(indicator);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById("typingIndicator");
    if (indicator) indicator.remove();
}

async function submitUserQuery(text) {
    appendMessage("user", text);
    showTypingIndicator();
    
    try {
        const payload = { 
            message: text,
            session_id: sessionId,
            filters: activeFilters.source ? { source: activeFilters.source } : null,
            api_key: localStorage.getItem("gemini_api_key") || ""
        };
        
        const headers = { "Content-Type": "application/json" };
        if (sessionToken) {
            headers["token"] = `Bearer ${sessionToken}`;
        }
        
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: "POST",
            headers: headers,
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        
        removeTypingIndicator();
        
        if (response.ok) {
            appendMessage("assistant", data.answer, data.citations);
            updateTraceDisplay(data.trace);
        } else {
            appendMessage("assistant", "⚠️ Server Error: Failed to compute response from Agentic RAG engine.");
        }
    } catch (error) {
        console.error("Chat error:", error);
        removeTypingIndicator();
        appendMessage("assistant", "❌ Network Error: Could not connect to the API server.");
    }
}

// Download markdown reports
window.downloadReport = async function(content) {
    try {
        const payload = {
            content: content,
            filename: `retail_operations_report_${Date.now()}.md`
        };
        
        const res = await fetch(`${API_BASE}/api/reports/download`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = payload.filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        showToast("Report download triggered successfully", "success");
    } catch (error) {
        console.error("Report download failed:", error);
        showToast("Failed to download report", "error");
    }
};

/* ==========================================
   RAG INSPECTOR PANEL
   ========================================== */
function updateTraceDisplay(trace) {
    if (!trace) return;
    
    // 1. Query Expansion
    expandedQueriesList.innerHTML = trace.expanded_queries.map((q, idx) => {
        return `<li>Variation ${idx+1}: "${q}"</li>`;
    }).join("");
    
    // 2. Sparse Results
    if (trace.sparse_results.length === 0) {
        sparseResultsBody.innerHTML = `<tr><td colspan="3" class="empty-trace">No sparse search records.</td></tr>`;
    } else {
        sparseResultsBody.innerHTML = trace.sparse_results.map(res => `
            <tr>
                <td title="${res.chunk_text}">${res.chunk_text.substring(0, 60)}...</td>
                <td><span class="badge">${res.source}</span></td>
                <td><code style="color:var(--blue)">${res.score.toFixed(4)}</code></td>
            </tr>
        `).join("");
    }
    
    // 3. Dense Results
    if (trace.dense_results.length === 0) {
        denseResultsBody.innerHTML = `<tr><td colspan="3" class="empty-trace">No dense search records.</td></tr>`;
    } else {
        denseResultsBody.innerHTML = trace.dense_results.map(res => `
            <tr>
                <td title="${res.chunk_text}">${res.chunk_text.substring(0, 60)}...</td>
                <td><span class="badge">${res.source}</span></td>
                <td><code style="color:var(--success)">${res.score.toFixed(4)}</code></td>
            </tr>
        `).join("");
    }
    
    // 4. RRF Merged Results
    if (trace.rrf_results.length === 0) {
        rrfResultsBody.innerHTML = `<tr><td colspan="3" class="empty-trace">No RRF rank records.</td></tr>`;
    } else {
        rrfResultsBody.innerHTML = trace.rrf_results.map((res, idx) => `
            <tr>
                <td><code style="color:var(--purple)">${res.rrf_score.toFixed(4)} (Rank ${idx+1})</code></td>
                <td title="${res.chunk_text}">${res.chunk_text.substring(0, 60)}...</td>
                <td><span class="badge">${res.source}</span></td>
            </tr>
        `).join("");
    }
    
    // Toggle active traces tabs switching
    const activeTabButton = document.querySelector(".trace-tab.active");
    if (activeTabButton) {
        activeTabButton.click();
    }
}

// Set up Trace tab switches
document.querySelectorAll(".trace-tab").forEach(tab => {
    tab.addEventListener("click", () => {
        document.querySelectorAll(".trace-tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        
        const targetTab = tab.getAttribute("data-tab");
        document.querySelectorAll(".trace-tab-content").forEach(content => {
            content.classList.remove("active");
        });
        document.getElementById(`tab-${targetTab}`).classList.add("active");
    });
});

/* ==========================================
   PRODUCT DIRECTORY SEARCH API
   ========================================== */
async function searchProducts(query) {
    try {
        const response = await fetch(`${API_BASE}/api/products/search?query=${query}`);
        const products = await response.json();
        
        if (products.length === 0) {
            productResultsBody.innerHTML = `<tr><td colspan="7" class="empty-table-state">No products found matching '${query}'.</td></tr>`;
            return;
        }
        
        productResultsBody.innerHTML = products.map(p => {
            return `
                <tr>
                    <td><code>${p.sku}</code></td>
                    <td><strong>${p.name}</strong></td>
                    <td><span class="badge">${p.category}</span></td>
                    <td>$${p.price.toFixed(2)} per ${p.unit}</td>
                    <td>${p.warehouse_stock || 0} units</td>
                    <td>${p.store_stock || 0} units</td>
                    <td><em>${p.supplier_name || 'N/A'}</em></td>
                </tr>
            `;
        }).join("");
    } catch (error) {
        console.error("Products fetch error:", error);
    }
}

/* ==========================================
   METRICS & CHART VISUALIZATIONS
   ========================================== */
async function fetchStats() {
    try {
        const response = await fetch(`${API_BASE}/api/dashboard/stats`);
        apiStats = await response.json();
        
        // Update KPI values
        kpiTotalInventory.textContent = apiStats.total_inventory_items.toLocaleString();
        kpiLowStock.textContent = apiStats.low_stock_sku_count.toLocaleString();
        kpiShipments.textContent = `${apiStats.pending_shipments} / ${apiStats.delayed_shipments}`;
        kpiOtif.textContent = `${apiStats.otif_delivery_rate}%`;
            
        // Toggle warning card states
        if (apiStats.low_stock_sku_count > 0) {
            kpiLowStockCard.classList.add("highlight-danger");
        } else {
            kpiLowStockCard.classList.remove("highlight-danger");
        }
        
        // Populate Low Stock tablealerts
        if (apiStats.low_stock_table && apiStats.low_stock_table.length > 0) {
            lowStockTableBody.innerHTML = apiStats.low_stock_table.map(item => `
                <tr>
                    <td><code>${item.sku}</code></td>
                    <td><strong>${item.name}</strong></td>
                    <td><span class="badge">${item.location}</span></td>
                    <td class="red" style="font-weight:600;">${item.stock}</td>
                    <td>${item.threshold}</td>
                    <td><em>${item.supplier}</em></td>
                </tr>
            `).join("");
        } else {
            lowStockTableBody.innerHTML = `<tr><td colspan="6" class="empty-trace">No low stock items detected.</td></tr>`;
        }
        
        // Redraw charts
        initCharts();
    } catch (error) {
        console.error("Dashboard stats fetch error:", error);
    }
}

function initCharts() {
    if (!apiStats) return;

    const isDark = !document.body.classList.contains("light-theme");
    const textColor = isDark ? "#a0aec0" : "#475569";
    const gridColor = isDark ? "rgba(43, 49, 86, 0.2)" : "rgba(203, 213, 225, 0.5)";

    // 1. Inventory Chart
    if (charts.inventory) charts.inventory.destroy();
    
    const invCtx = document.getElementById("inventoryChart").getContext("2d");
    const invLabels = apiStats.inventory_chart.labels;
    const invStock = apiStats.inventory_chart.stock;
    const invThreshold = apiStats.inventory_chart.threshold;

    charts.inventory = new Chart(invCtx, {
        type: 'bar',
        data: {
            labels: invLabels,
            datasets: [
                {
                    label: 'Current Stock',
                    data: invStock,
                    backgroundColor: 'rgba(99, 102, 241, 0.75)',
                    borderColor: 'rgb(99, 102, 241)',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: 'Reorder Level',
                    data: invThreshold,
                    backgroundColor: 'rgba(239, 68, 68, 0.45)',
                    borderColor: 'rgb(239, 68, 68)',
                    borderWidth: 1,
                    borderRadius: 4,
                    type: 'line',
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: textColor, font: { family: 'Plus Jakarta Sans', size: 10 } }
                }
            },
            scales: {
                x: {
                    grid: { color: 'transparent' },
                    ticks: { color: textColor, font: { size: 9 } }
                },
                y: {
                    grid: { color: gridColor },
                    ticks: { color: textColor, font: { size: 9 } }
                }
            }
        }
    });

    // 2. Shipping Chart
    if (charts.shipping) charts.shipping.destroy();
    
    const shipCtx = document.getElementById("shippingChart").getContext("2d");
    const shipCounts = apiStats.shipping_chart.counts;

    charts.shipping = new Chart(shipCtx, {
        type: 'doughnut',
        data: {
            labels: apiStats.shipping_chart.labels,
            datasets: [{
                data: shipCounts,
                backgroundColor: [
                    'rgba(16, 185, 129, 0.75)',  // On-time
                    'rgba(245, 158, 11, 0.75)',  // Late
                    'rgba(59, 130, 246, 0.75)',  // In Transit
                    'rgba(239, 68, 68, 0.75)'    // Delayed
                ],
                borderColor: isDark ? '#121424' : '#ffffff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: textColor, font: { family: 'Plus Jakarta Sans', size: 10 } }
                }
            },
            cutout: '60%'
        }
    });
}

/* ==========================================
   KNOWLEDGE BASE DOCUMENT MANAGEMENT
   ========================================== */
async function fetchDocuments() {
    try {
        const response = await fetch(`${API_BASE}/api/documents`);
        const docs = await response.json();
        
        docCountBadge.textContent = `${docs.length} File${docs.length === 1 ? '' : 's'}`;
        
        // Populate metadata source filter options dynamically
        const currentSelectedSource = filterSource.value;
        filterSource.innerHTML = '<option value="">All Sources</option>' + 
            docs.map(doc => `<option value="${doc.name}">${doc.name}</option>`).join("");
        filterSource.value = currentSelectedSource;
        
        // Filter local listing in UI if Doc Type filter matches
        let listedDocs = docs;
        if (activeFilters.type) {
            listedDocs = docs.filter(doc => doc.name.toLowerCase().endsWith(activeFilters.type));
        }

        if (listedDocs.length === 0) {
            docList.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-file-invoice"></i>
                    <p>No documents found matching filters.</p>
                </div>
            `;
            return;
        }

        docList.innerHTML = listedDocs.map(doc => {
            let iconClass = "fa-file-lines";
            if (doc.name.endsWith(".pdf")) iconClass = "fa-file-pdf";
            if (doc.name.endsWith(".csv")) iconClass = "fa-file-csv";
            if (doc.name.endsWith(".docx")) iconClass = "fa-file-word";
            if (doc.name.endsWith(".xlsx")) iconClass = "fa-file-excel";
            
            return `
                <div class="doc-item">
                    <div class="doc-icon"><i class="fa-solid ${iconClass}"></i></div>
                    <div class="doc-info">
                        <div class="doc-name" title="${doc.name}">${doc.name}</div>
                        <div class="doc-meta">
                            <span>${doc.size}</span>
                            <span>•</span>
                            <span>${doc.chunks} child chunk${doc.chunks === 1 ? '' : 's'}</span>
                        </div>
                    </div>
                    <div class="doc-actions">
                        <button class="btn-delete" onclick="deleteDoc('${doc.name}')" title="Delete document">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </div>
            `;
        }).join("");

    } catch (error) {
        console.error("Error retrieving documents:", error);
    }
}

function setupDropzone() {
    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("dragover");
    });
    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            uploadFiles(files);
        }
    });

    fileInput.addEventListener("change", (e) => {
        const files = e.target.files;
        if (files.length > 0) {
            uploadFiles(files);
        }
    });
}

async function uploadFiles(files) {
    const role = currentUser.role;
    const allowed = ["Administrator", "Category Manager", "Procurement Manager"].includes(role);
    if (!allowed) {
        showToast("Access Denied: Your role is not authorized to ingest documents.", "error");
        return;
    }

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const formData = new FormData();
        formData.append("file", file);
        
        showToast(`Ingesting and indexing ${file.name}...`, "info");
        
        try {
            const headers = {};
            if (sessionToken) {
                headers["token"] = `Bearer ${sessionToken}`;
            }
            
            const res = await fetch(`${API_BASE}/api/documents/upload`, {
                method: "POST",
                headers: headers,
                body: formData
            });
            const data = await res.json();
            
            if (res.ok && data.status === "success") {
                showToast(`Indexed ${file.name} successfully`, "success");
            } else {
                showToast(data.detail || `Failed to parse ${file.name}`, "error");
            }
        } catch (error) {
            console.error("Upload error:", error);
            showToast(`Upload failed for ${file.name}`, "error");
        }
    }
    
    fetchDocuments();
    fetchStats();
}

window.deleteDoc = async function(filename) {
    const role = currentUser.role;
    if (role !== "Administrator") {
        showToast("Access Denied: Document deletion restricted to Administrator only.", "error");
        return;
    }

    if (!confirm(`Are you sure you want to delete ${filename} from knowledge base?`)) return;
    
    try {
        const headers = {};
        if (sessionToken) {
            headers["token"] = `Bearer ${sessionToken}`;
        }
        
        const res = await fetch(`${API_BASE}/api/documents/${filename}`, {
            method: "DELETE",
            headers: headers
        });
        const data = await res.json();
        
        if (res.ok && data.status === "success") {
            showToast(`Deleted ${filename}`, "success");
            fetchDocuments();
            fetchStats();
        } else {
            showToast(data.detail || "Failed to delete file", "error");
        }
    } catch (error) {
        console.error("Delete error:", error);
        showToast("Failed to delete document", "error");
    }
};

/* ==========================================
   ADMIN AUDIT LOGS DISPLAY
   ========================================== */
async function loadAdminLogs() {
    const role = currentUser.role;
    
    if (role !== "Administrator") {
        adminAccessDenied.style.display = "flex";
        adminAccessGranted.style.display = "none";
        restrictedUserRole.textContent = role || "Guest User";
        return;
    }
    
    adminAccessDenied.style.display = "none";
    adminAccessGranted.style.display = "block";
    auditLogsBody.innerHTML = `<tr><td colspan="8" class="empty-table-state">Retrieving security audit trials...</td></tr>`;
    
    try {
        const headers = {};
        if (sessionToken) {
            headers["token"] = `Bearer ${sessionToken}`;
        }
        
        const response = await fetch(`${API_BASE}/api/admin/logs`, { headers });
        const logs = await response.json();
        
        if (!response.ok) {
            auditLogsBody.innerHTML = `<tr><td colspan="8" class="empty-table-state red">Error: ${logs.detail || 'Access Denied'}</td></tr>`;
            return;
        }
        
        if (logs.length === 0) {
            auditLogsBody.innerHTML = `<tr><td colspan="8" class="empty-table-state">No audit logs recorded yet.</td></tr>`;
            return;
        }
        
        auditLogsBody.innerHTML = logs.map(log => {
            const timeStr = new Date(log.timestamp).toLocaleString();
            const sqlText = log.execution_sql ? `<code>${log.execution_sql}</code>` : `<span style="color:var(--text-muted);">None</span>`;
            const statusClass = log.status === "SUCCESS" ? "green" : "red";
            
            return `
                <tr>
                    <td style="white-space:nowrap; font-size:11px;">${timeStr}</td>
                    <td><strong>${log.username}</strong></td>
                    <td><span class="badge">${log.user_role}</span></td>
                    <td title="${log.query}">${log.query.substring(0, 40)}...</td>
                    <td><span class="badge" style="background:var(--blue-bg); color:var(--blue);">${log.intent}</span></td>
                    <td title="${log.execution_sql || ''}">${sqlText}</td>
                    <td><code>${log.latency_ms} ms</code></td>
                    <td><strong class="${statusClass}">${log.status}</strong></td>
                </tr>
            `;
        }).join("");
    } catch (error) {
        console.error("Audit log error:", error);
        auditLogsBody.innerHTML = `<tr><td colspan="8" class="empty-table-state red">Failed to retrieve admin logs from server.</td></tr>`;
    }
}

/* ==========================================
   UTILITY HELPER FUNCTIONS
   ========================================== */
async function updateBackendKey(key) {
    try {
        const response = await fetch(`${API_BASE}/api/config/key`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ api_key: key })
        });
        const data = await response.json();
        
        const dot = document.querySelector(".engine-indicator .status-dot");
        const statusText = document.getElementById("engineStatusText");
        
        if (data.has_key) {
            dot.className = "status-dot green";
            statusText.textContent = "RAG Engine Active (Gemini Connected)";
        } else {
            dot.className = "status-dot yellow";
            statusText.textContent = "RAG Engine Online (Demo Mode)";
        }
    } catch (error) {
        console.error("Key config sync error:", error);
    }
}

function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    
    let icon = "fa-circle-info";
    if (type === "success") icon = "fa-circle-check";
    if (type === "error") icon = "fa-circle-xmark";
    if (type === "warning") icon = "fa-circle-exclamation";
    
    toast.innerHTML = `
        <i class="fa-solid ${icon}"></i>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(10px)";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// CSS keyframes styling for typing bouncing dot
const bounceStyle = document.createElement("style");
bounceStyle.innerHTML = `
    @keyframes bounce {
        from { transform: translateY(0); }
        to { transform: translateY(-6px); }
    }
    .typing-loader .status-dot {
        margin: 0 2px;
    }
`;
document.head.appendChild(bounceStyle);

/* ==========================================
   INGESTION HUB EVENT HANDLERS & LOGIC
   ========================================== */
let apiPresets = [];
let opensourcePresets = [];
let localIngestionLogs = JSON.parse(localStorage.getItem("ingestion_logs") || "[]");

async function loadIngestionPresets() {
    try {
        const response = await fetch(`${API_BASE}/api/ingest/presets`);
        const data = await response.json();
        
        apiPresets = data.api_presets;
        opensourcePresets = data.opensource_presets;
        
        // Populate select elements
        const apiSelect = document.getElementById("apiPresetSelect");
        if (apiSelect) {
            apiSelect.innerHTML = `<option value="">-- Choose a Preset --</option>` + 
                apiPresets.map((p, idx) => `<option value="${idx}">${p.name}</option>`).join("");
        }
        
        const osSelect = document.getElementById("opensourcePresetSelect");
        if (osSelect) {
            osSelect.innerHTML = `<option value="">-- Choose a Preset --</option>` + 
                opensourcePresets.map((p, idx) => `<option value="${idx}">${p.name}</option>`).join("");
        }
    } catch (error) {
        console.error("Presets loading error:", error);
    }
}

// Preset Change Event Listeners
document.getElementById("apiPresetSelect").addEventListener("change", (e) => {
    const val = e.target.value;
    if (val === "") {
        document.getElementById("apiIngestUrl").value = "";
        document.getElementById("apiTargetTable").value = "products";
        document.getElementById("apiMappingText").value = "";
        return;
    }
    const preset = apiPresets[parseInt(val)];
    document.getElementById("apiIngestUrl").value = preset.url;
    document.getElementById("apiTargetTable").value = preset.target_table;
    document.getElementById("apiMappingText").value = JSON.stringify(preset.mapping);
});

document.getElementById("opensourcePresetSelect").addEventListener("change", (e) => {
    const val = e.target.value;
    if (val === "") {
        document.getElementById("opensourceUrl").value = "";
        document.getElementById("opensourceFilename").value = "";
        document.getElementById("opensourceTitle").value = "";
        return;
    }
    const preset = opensourcePresets[parseInt(val)];
    document.getElementById("opensourceUrl").value = preset.url;
    document.getElementById("opensourceFilename").value = preset.filename;
    document.getElementById("opensourceTitle").value = preset.title;
});

// API Form Submit
document.getElementById("apiIngestForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = document.getElementById("apiIngestUrl").value.trim();
    const targetTable = document.getElementById("apiTargetTable").value;
    const authHeader = document.getElementById("apiAuthHeader").value.trim();
    const mappingVal = document.getElementById("apiMappingText").value.trim();
    
    let mapping = null;
    if (mappingVal) {
        try {
            mapping = JSON.parse(mappingVal);
        } catch (ex) {
            showToast("Invalid JSON mapping syntax. Please correct it.", "error");
            return;
        }
    }
    
    const headers = { "Content-Type": "application/json" };
    if (sessionToken) {
        headers["token"] = `Bearer ${sessionToken}`;
    }
    
    showToast("Starting API Ingest...", "info");
    const submitBtn = document.getElementById("apiIngestSubmitBtn");
    submitBtn.disabled = true;
    submitBtn.querySelector("span").textContent = "Ingesting Data...";
    
    try {
        const response = await fetch(`${API_BASE}/api/ingest/api`, {
            method: "POST",
            headers,
            body: JSON.stringify({ url, target_table: targetTable, mapping })
        });
        const resData = await response.json();
        
        if (response.ok) {
            showToast(resData.message, "success");
            addIngestionLog("REST API", url, `Import to SQL: ${targetTable}`, resData.message, "SUCCESS");
            
            // Refresh views
            fetchStats();
            searchProducts("");
        } else {
            showToast(resData.detail || "API Ingestion failed", "error");
            addIngestionLog("REST API", url, `Import to SQL: ${targetTable}`, resData.detail || "Error", "FAILED");
        }
    } catch (err) {
        showToast(`Network Error: ${err.message}`, "error");
        addIngestionLog("REST API", url, `Import to SQL: ${targetTable}`, err.message, "FAILED");
    } finally {
        submitBtn.disabled = false;
        submitBtn.querySelector("span").textContent = "Fetch & Ingest API";
        applyRoleRestrictions();
    }
});

// Open Source Form Submit
document.getElementById("opensourceIngestForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = document.getElementById("opensourceUrl").value.trim();
    const filename = document.getElementById("opensourceFilename").value.trim();
    const title = document.getElementById("opensourceTitle").value.trim();
    
    const headers = { "Content-Type": "application/json" };
    if (sessionToken) {
        headers["token"] = `Bearer ${sessionToken}`;
    }
    
    showToast("Starting Open Source Indexing...", "info");
    const submitBtn = document.getElementById("opensourceSubmitBtn");
    submitBtn.disabled = true;
    submitBtn.querySelector("span").textContent = "Downloading & Indexing...";
    
    try {
        const response = await fetch(`${API_BASE}/api/ingest/opensource`, {
            method: "POST",
            headers,
            body: JSON.stringify({ url, filename, title })
        });
        const resData = await response.json();
        
        if (response.ok) {
            showToast(resData.message, "success");
            addIngestionLog("Open Source URL", url, `Index: ${filename}`, resData.message, "SUCCESS");
            
            // Refresh views
            fetchDocuments();
            fetchStats();
            searchProducts("");
        } else {
            showToast(resData.detail || "Dataset Ingestion failed", "error");
            addIngestionLog("Open Source URL", url, `Index: ${filename}`, resData.detail || "Error", "FAILED");
        }
    } catch (err) {
        showToast(`Network Error: ${err.message}`, "error");
        addIngestionLog("Open Source URL", url, `Index: ${filename}`, err.message, "FAILED");
    } finally {
        submitBtn.disabled = false;
        submitBtn.querySelector("span").textContent = "Download & Index Dataset";
        applyRoleRestrictions();
    }
});

// Demo PDF copy button handler
document.getElementById("downloadSamplePdfBtn").addEventListener("click", async () => {
    const headers = {};
    if (sessionToken) {
        headers["token"] = `Bearer ${sessionToken}`;
    }
    
    showToast("Loading preset PDF SLA document...", "info");
    try {
        const response = await fetch(`${API_BASE}/api/documents/sample/q3_sla_review.pdf`, {
            method: "POST",
            headers
        });
        const data = await response.json();
        if (response.ok) {
            showToast(data.message, "success");
            addIngestionLog("Preset PDF File", "sample_documents/q3_sla_review.pdf", "Copy & Index PDF", data.message, "SUCCESS");
            fetchDocuments();
        } else {
            showToast(data.detail || "Failed to load sample document", "error");
        }
    } catch (err) {
        showToast(`Network Error: ${err.message}`, "error");
    }
});

// Ingestion Log helpers
function addIngestionLog(source, url, action, details, status) {
    const timestamp = new Date().toLocaleString();
    localIngestionLogs.unshift({ timestamp, source, url, action, details, status });
    if (localIngestionLogs.length > 20) {
        localIngestionLogs.pop();
    }
    localStorage.setItem("ingestion_logs", JSON.stringify(localIngestionLogs));
    renderIngestionLogs();
}

function renderIngestionLogs() {
    const body = document.getElementById("ingestionLogsBody");
    if (!body) return;
    
    if (localIngestionLogs.length === 0) {
        body.innerHTML = `<tr><td colspan="6" class="empty-trace">No ingestion tasks run in this session.</td></tr>`;
        return;
    }
    
    body.innerHTML = localIngestionLogs.map(log => {
        const statusClass = log.status === "SUCCESS" ? "green" : "red";
        return `
            <tr>
                <td style="white-space:nowrap; font-size:11px;">${log.timestamp}</td>
                <td><span class="badge" style="background:rgba(99, 102, 241, 0.1); color:var(--primary);">${log.source}</span></td>
                <td title="${log.url}" style="font-size:11px; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${log.url}</td>
                <td><strong>${log.action}</strong></td>
                <td title="${log.details}" style="font-size:11px; max-width:250px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${log.details}</td>
                <td><strong class="${statusClass}">${log.status}</strong></td>
            </tr>
        `;
    }).join("");
}
