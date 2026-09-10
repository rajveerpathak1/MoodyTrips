let token = localStorage.getItem("moodytrips_token") || null;
let currentThreadId = localStorage.getItem("moodytrips_thread_id") || null;
let latestAnswerMarkdown = "";
let currentAuthTab = "login";

// =====================================================================
// Initialize App
// =====================================================================
document.addEventListener("DOMContentLoaded", async () => {
    if (token) {
        // Verify current token
        const success = await verifyToken();
        if (success) {
            showLoggedInUI();
            await loadChatList();
            if (currentThreadId) {
                switchChat(currentThreadId);
            }
        } else {
            clearSession();
            showLoggedOutUI();
        }
    } else {
        showLoggedOutUI();
    }

    // Ctrl+Enter to submit message
    document.getElementById("userInput").addEventListener("keydown", function(event) {
        if (event.ctrlKey && event.key === "Enter") {
            sendMessage();
        }
    });
});

// =====================================================================
// UI State Controls
// =====================================================================
function showLoggedInUI() {
    document.getElementById("authCard").classList.add("hidden");
    document.getElementById("sidebar").classList.remove("hidden");
    document.getElementById("chatWorkArea").classList.remove("hidden");
    
    // Set user avatar email
    const email = localStorage.getItem("moodytrips_user_email") || "User";
    document.getElementById("userEmail").textContent = email;
    document.querySelector(".avatar").textContent = email.charAt(0).toUpperCase();
}

function showLoggedOutUI() {
    document.getElementById("authCard").classList.remove("hidden");
    document.getElementById("sidebar").classList.add("hidden");
    document.getElementById("chatWorkArea").classList.add("hidden");
}

function clearSession() {
    token = null;
    currentThreadId = null;
    localStorage.removeItem("moodytrips_token");
    localStorage.removeItem("moodytrips_thread_id");
    localStorage.removeItem("moodytrips_user_email");
}

// =====================================================================
// Authentication Functions
// =====================================================================
async function verifyToken() {
    try {
        const response = await fetch("/api/auth/me", {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });
        if (!response.ok) return false;
        const data = await response.json();
        return data.success === true;
    } catch {
        return false;
    }
}

function switchAuthTab(tab) {
    currentAuthTab = tab;
    document.getElementById("authErrorBox").classList.add("hidden");
    
    const tabLogin = document.getElementById("tabLogin");
    const tabRegister = document.getElementById("tabRegister");
    const registerConfirmGroup = document.getElementById("registerConfirmGroup");
    const authSubmitBtn = document.getElementById("authSubmitBtn").querySelector("span");
    
    if (tab === "login") {
        tabLogin.classList.add("active");
        tabRegister.classList.remove("active");
        registerConfirmGroup.classList.add("hidden");
        authSubmitBtn.textContent = "Sign In";
        document.getElementById("authConfirmPassword").required = false;
    } else {
        tabLogin.classList.remove("active");
        tabRegister.classList.add("active");
        registerConfirmGroup.classList.remove("hidden");
        authSubmitBtn.textContent = "Sign Up";
        document.getElementById("authConfirmPassword").required = true;
    }
}

async function handleAuthSubmit(event) {
    event.preventDefault();
    document.getElementById("authErrorBox").classList.add("hidden");
    
    const email = document.getElementById("authEmail").value.trim();
    const password = document.getElementById("authPassword").value;
    const confirmPassword = document.getElementById("authConfirmPassword").value;
    
    if (currentAuthTab === "register" && password !== confirmPassword) {
        showAuthError("Passwords do not match.");
        return;
    }
    
    setAuthLoading(true);
    
    const url = currentAuthTab === "login" ? "/api/auth/login" : "/api/auth/register";
    try {
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || "Authentication failed.");
        }
        
        token = data.token;
        localStorage.setItem("moodytrips_token", token);
        localStorage.setItem("moodytrips_user_email", data.user.email);
        
        showLoggedInUI();
        await loadChatList();
        startNewChat();
        
        // Reset form
        document.getElementById("authForm").reset();
    } catch (err) {
        showAuthError(err.message);
    } finally {
        setAuthLoading(false);
    }
}

function setAuthLoading(isLoading) {
    const btn = document.getElementById("authSubmitBtn");
    const span = btn.querySelector("span");
    const loader = document.getElementById("authLoader");
    
    btn.disabled = isLoading;
    if (isLoading) {
        span.classList.add("hidden");
        loader.classList.remove("hidden");
    } else {
        span.classList.remove("hidden");
        loader.classList.add("hidden");
    }
}

function showAuthError(msg) {
    const box = document.getElementById("authErrorBox");
    box.textContent = msg;
    box.classList.remove("hidden");
}

function logout() {
    clearSession();
    showLoggedOutUI();
}

// =====================================================================
// Chat History Sidebar Functions
// =====================================================================
async function loadChatList() {
    try {
        const response = await fetch("/api/chats", {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });
        const data = await response.json();
        
        const chatList = document.getElementById("chatList");
        chatList.innerHTML = "";
        
        if (!data.success || !data.chats || data.chats.length === 0) {
            chatList.innerHTML = `<div class="chat-list-placeholder">No travel plans yet.</div>`;
            return;
        }
        
        data.chats.forEach(chat => {
            const dateStr = chat.created_at ? new Date(chat.created_at).toLocaleDateString(undefined, {month: 'short', day: 'numeric'}) : "";
            
            const btn = document.createElement("button");
            btn.className = `chat-item ${currentThreadId === chat.thread_id ? 'active' : ''}`;
            btn.setAttribute("data-thread-id", chat.thread_id);
            btn.onclick = () => switchChat(chat.thread_id);
            
            btn.innerHTML = `
                <div class="chat-item-title">${chat.title}</div>
                <div class="chat-item-date">${dateStr}</div>
            `;
            chatList.appendChild(btn);
        });
    } catch (err) {
        console.error("Failed to load chat list:", err);
    }
}

function startNewChat() {
    currentThreadId = null;
    localStorage.removeItem("moodytrips_thread_id");
    
    // Clear display
    document.getElementById("userInput").value = "";
    document.getElementById("resultSection").classList.add("hidden");
    hideError();
    
    // Deactivate items in sidebar
    document.querySelectorAll(".chat-item").forEach(item => item.classList.remove("active"));
}

async function switchChat(threadId) {
    currentThreadId = threadId;
    localStorage.setItem("moodytrips_thread_id", threadId);
    
    // UI selection highlights
    document.querySelectorAll(".chat-item").forEach(item => {
        if (item.getAttribute("data-thread-id") === threadId) {
            item.classList.add("active");
        } else {
            item.classList.remove("active");
        }
    });
    
    // Fetch conversation details
    try {
        const response = await fetch(`/api/chats/${threadId}`, {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.error || "Failed to load chat history.");
        }
        
        // Find the last assistant message (itinerary summary) to display
        const assistantMsgs = data.messages.filter(m => m.role === "assistant");
        if (assistantMsgs.length > 0) {
            const lastPlan = assistantMsgs[assistantMsgs.length - 1].content;
            showResult(lastPlan, threadId);
            
            // Set input value to the last user query for convenience
            const userMsgs = data.messages.filter(m => m.role === "user");
            if (userMsgs.length > 0) {
                document.getElementById("userInput").value = userMsgs[userMsgs.length - 1].content;
            }
        } else {
            // New empty thread
            document.getElementById("userInput").value = "";
            document.getElementById("resultSection").classList.add("hidden");
        }
    } catch (err) {
        showError(err.message);
    }
}

// =====================================================================
// Travel Request Processing
// =====================================================================
function setPrompt(text) {
    document.getElementById("userInput").value = text;
}

function setLoading(isLoading) {
    const sendBtn = document.getElementById("sendBtn");
    const btnText = document.getElementById("btnText");
    const btnLoader = document.getElementById("btnLoader");

    sendBtn.disabled = isLoading;

    if (isLoading) {
        btnText.classList.add("hidden");
        btnLoader.classList.remove("hidden");
    } else {
        btnText.classList.remove("hidden");
        btnLoader.classList.add("hidden");
    }
}

function showError(message) {
    const errorBox = document.getElementById("errorBox");
    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
}

function hideError() {
    const errorBox = document.getElementById("errorBox");
    errorBox.classList.add("hidden");
    errorBox.textContent = "";
}

function showResult(answer, threadId) {
    latestAnswerMarkdown = answer;

    const resultSection = document.getElementById("resultSection");
    const resultBox = document.getElementById("resultBox");
    const threadInfo = document.getElementById("threadInfo");

    if (typeof marked !== "undefined") {
        resultBox.innerHTML = marked.parse(answer);
    } else {
        resultBox.innerText = answer;
    }

    threadInfo.textContent = `Thread ID: ${threadId}`;
    resultSection.classList.remove("hidden");

    resultSection.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}

async function sendMessage() {
    hideError();

    const input = document.getElementById("userInput");
    const message = input.value.trim();

    if (!message) {
        showError("Please enter your travel request first.");
        return;
    }

    setLoading(true);

    try {
        const response = await fetch("/api/travel", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                message: message,
                thread_id: currentThreadId
            })
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || "Something went wrong.");
        }

        currentThreadId = data.thread_id;
        localStorage.setItem("moodytrips_thread_id", currentThreadId);

        // Refresh sidebar and highlight active thread
        await loadChatList();
        showResult(data.answer, data.thread_id);

    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
    }
}

// =====================================================================
// Action Controls (Copy & PDF Export)
// =====================================================================
function copyResult() {
    const resultBox = document.getElementById("resultBox");
    const text = resultBox.innerText;

    if (!text) return;

    navigator.clipboard.writeText(text)
        .then(() => {
            const copyBtn = document.querySelector(".copy-btn");
            const oldText = copyBtn.textContent;

            copyBtn.textContent = "✓ Copied!";

            setTimeout(() => {
                copyBtn.textContent = oldText;
            }, 1500);
        })
        .catch(() => {
            showError("Could not copy result.");
        });
}

function downloadPDF() {
    const pdfContent = document.getElementById("pdfContent");

    if (!latestAnswerMarkdown || !pdfContent) {
        showError("No travel plan available to download.");
        return;
    }

    const downloadBtn = document.querySelector(".download-btn");
    const oldText = downloadBtn.textContent;

    downloadBtn.textContent = "Preparing PDF...";
    downloadBtn.disabled = true;

    const options = {
        margin: 0.5,
        filename: `moodytrips-plan-${currentThreadId.substring(5, 12)}.pdf`,
        image: {
            type: "jpeg",
            quality: 0.98
        },
        html2canvas: {
            scale: 2,
            useCORS: true,
            backgroundColor: "#ffffff"
        },
        jsPDF: {
            unit: "in",
            format: "a4",
            orientation: "portrait"
        },
        pagebreak: {
            mode: ["avoid-all", "css", "legacy"]
        }
    };

    html2pdf()
        .set(options)
        .from(pdfContent)
        .save()
        .then(() => {
            downloadBtn.textContent = oldText;
            downloadBtn.disabled = false;
        })
        .catch((err) => {
            console.error("PDF generation error:", err);
            downloadBtn.textContent = oldText;
            downloadBtn.disabled = false;
            showError("Could not download PDF.");
        });
}